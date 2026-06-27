import argparse, os, platform, sys
from pathlib import Path

# try to be helpful for missing libs
try:
    from cryptography.hazmat.primitives.asymmetric import rsa, padding
    from cryptography.hazmat.primitives.serialization import load_pem_public_key
    from cryptography.hazmat.primitives.serialization import load_pem_private_key
    from cryptography.hazmat.primitives import hashes
    from Crypto.Protocol.SecretSharing import Shamir
    from Crypto.Random import get_random_bytes
except ImportError as e:
    sys.exit(
        f"Missing dependencies. Options:\n\n"
        "1) pip install cryptography pycryptodome\n"
        "2) python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt && python3 kasumi.py -h\n" 
    )


# define the default location for encrypted shares to live
SHARE_DIR = Path("shares")

# just a quick color hack
def pp(x, color='', strext=''):
    if platform.system() == "Windows":
        os.system('color')

    colors = {
        'r': f"\033[0;31m{x}\033[0m",
        'g': f"\033[0;92m{x}\033[0m",
        'b': f"\033[0;34m{x}\033[0m",
        'c': f"\033[0;96m{x}\033[0m",
        'm': f"\033[0;95m{x}\033[0m",
        'y': f"\033[0;93m{x}\033[0m",
        'k': f"\033[0;90m{x}\033[0m",
        '': x
    }

    try:
        print(f'{colors[color]} {strext}')
    except Exception:
        print(x)



def load_members_from_keydir(keydir, suffix):
    '''
        This function does some sanity checks for where
        key files and/or key directories are at.
    '''
    keydir = Path(keydir)

    if not keydir.is_dir():
        raise SystemExit(f"Key directory not found: {keydir}")

    members = []
    key_paths = {}

    for pem in sorted(keydir.glob(f"*{suffix}.pem")):
        member = pem.stem.removesuffix(suffix)

        if member in key_paths:
            raise SystemExit(f"Duplicate member detected: {member}")

        members.append(member)
        key_paths[member] = pem

    if not members:
        raise SystemExit(f"No *{suffix}.pem files found in {keydir}")

    return members, key_paths


def parse_members(member_csv):
    '''
        Parses a common-separated list of members in the case 
        where users provide 'dave,alice,bob', for example.    
    '''
    members = [m.strip() for m in member_csv.split(',') if m.strip()]

    if not members:
        raise SystemExit("No valid members supplied.")

    if len(set(members)) != len(members):
        raise SystemExit("Member names must be unique. I'm out!")

    return members


def generateshares(secret, k, n):
    '''
        Generate shares k(n) according to Shamir's algorithm. 
    '''
    return Shamir.split(k, n, secret)


def decryptshare(privkey, ciphertext):
    '''
        Decrypt encrypted shares. 
    '''
    with open(privkey, "rb") as f:
        try:
            private_key = load_pem_private_key(f.read(), password=None)
        except Exception:
            raise SystemExit(f"Private key {privkey} not found or invalid.")

    try:
        payload = private_key.decrypt(
            ciphertext,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None,
            ),
        )
    except Exception:
        raise SystemExit(f"Decryption failed with key {privkey}. Likely invalid quorum member.")

    idx = int.from_bytes(payload[:2], "big")
    share_bytes = payload[2:]

    return idx, share_bytes


def encryptshares(pubkey, share):
    '''
        Encrypt/produce shares according to supplied member public keys.
    '''
    with open(pubkey, "rb") as f:
        try:
            public_key = load_pem_public_key(f.read())
        except Exception:
            raise SystemExit(f"Public key {pubkey} not found or invalid.")

    idx, share_bytes = share
    payload = idx.to_bytes(2, "big") + share_bytes

    return public_key.encrypt(
        payload,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None,
        ),
    )


def getsecret():
    '''
        Just a secret generator. Obviously this could be anything. 
    '''
    return get_random_bytes(16)


def blackbox(members, k, n, secret=None, key_paths=None):
    '''
        The intention here is to enulate a "blackbox" of sorts.

        This function takes a list of members and the quorum recipe 
        and produces shares for each supplied member.
    '''
    if secret is None:
        secret = get_random_bytes(16)

    shares = generateshares(secret, k, n)
    SHARE_DIR.mkdir(exist_ok=True)

    for member, share in zip(members, shares):
        pubkey = key_paths[member] if key_paths else f"{member}-public.pem"
        ciphertext = encryptshares(pubkey, share)

        share_file = Path(f"{SHARE_DIR}/{member}.share")

        pp(f" - Writing share for {member}: {share_file}", "g")
        with open(share_file, "w") as f:
            f.write(ciphertext.hex())


def clearbox(members, k, key_paths=None):
    '''
        This function decrypts encrypted shares for each member in the
        supplied quorum.
    '''
    decrypted = []

    for member in members[:k]:
        share_file = Path(f"{SHARE_DIR}/{member}.share")
        print(share_file)

        if not share_file.exists():
            pp("[-] Be sure you have '.share' files created for each member in the quorum.","y")
            raise SystemExit(f"Share file not found: {share_file}")

        with open(share_file) as f:
            encrypted_share = bytes.fromhex(f.read().strip())

        privkey = key_paths[member] if key_paths else Path(f"{member}-private.pem")
        decrypted.append(decryptshare(privkey, encrypted_share))

    return Shamir.combine(decrypted)


if __name__ == '__main__':
    # banner/help info 
    banner = '''
     __                               __
    |  |--.---.-.-----.--.--.--------|__|
    |    <|  _  |__ --|  |  |        |  |
    |__|__|___._|_____|_____|__|__|__|__|

    Kasumi generates and recovers a secret based on supplied quorum member keys.

    TESTING THIS TOOL
    
    To get the idea of how this might work, here's a suggested process. 

     1. Run the sample "generate_sample_keys.sh"
     2. Generate shares.
        $ python3 kasumi.py -d keys -k 3 -g
     3. Recover shares and obtain the secret.
        $ python3 kasumi.py -d keys -k 3 -r 

    KEYDIR mode: Provide a directory of keys. 

      keys/alice-public.pem
      keys/alice-private.pem
      keys/bob-public.pem
      keys/bob-private.pem

      python3 kasumi.py -d keys -k 3 -g.  --> GENERATE shares
      python3 kasumi.py -d keys -k 3 -r   --> RECOVER shares

    LIST mode: Simply provide a list of members. 
      Keys are assumed to be local to this tool and named "alice-public.pem", "alice-private.pem", etc.

      $ python3 kasumi.py -m alice,bob,dave -k 3 -g
      $ python3 kasumi.py -m alice,bob,dave -k 3 -r

    SHARES are written to and read from "shares" by default. 

      shares/alice.share
      shares/bob.share
    '''

    # arg parsing junk painful because I just have to be difficult
    # with my silly banner
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("-h", "--help", action="store_true")
    parser.add_argument('-m', '--members', help="CSV mode: alice,bob,dave")
    parser.add_argument('-d', '--keydir', help="DIR mode: directory containing member keys.")
    omode = parser.add_mutually_exclusive_group()
    omode.add_argument('-g', '--generate-shares', action='store_true', help="Generate encrypted shares.")
    omode.add_argument('-r', '--recover-shares', action='store_true', help="Recover shares.")
    parser.add_argument("-k", "--threshold", type=int, help="Number of shares required to recover secret.")

    args = parser.parse_args()

    # finally, show the help if the users wants it
    if args.help:
        pp(banner, "g")
        parser.print_help()
        print()
        sys.exit(0)


    # get to work, set k for k(n) defining number of member necessary for quorum
    k = args.threshold

    if k < 2:
        raise SystemExit("Quorum must be at least 2. Exiting!")

    # check for private and public key files
    suffix = "-private" if args.recover_shares else "-public"

    # most of this is logic for ensuring that member keys exist
    if args.members:
        members = parse_members(args.members)
        key_paths = {}
        # the user provided a directory of keys
        if args.keydir:
            keydir = Path(args.keydir)
            if not keydir.exists():
                pp("[!] Check your directory name and ensure keys are present within.","r")
                raise SystemExit(f"Invalid key directory '{keydir}'. Exiting.")
            key_paths = {
                member: keydir / f"{member}{suffix}.pem"
                for member in members
            }
        # the user provide a list of members, e.g., alice,bob,larry
        else:
            for member in members:
                p = Path(f"{member}{suffix}.pem")
                if not p.exists():
                    pp(f'[-] No such member key {member}{suffix}.pem. Check that the file exists, or use the -d switch to provide a directory of keys.','y')
                else:
                    key_paths = {
                        member: Path(f"{member}{suffix}.pem")
                        for member in members
                    }
            # Punt if there is a short
            if len(key_paths) < k:
                pp("[-] Failure to locate keys.","r")
                raise SystemExit(f"Not enough keys were provided for quorum of '{k}'. Ensure that you have provided key files local to this tool to in a directory containing keys.")
    elif args.keydir:
        members, key_paths = load_members_from_keydir(args.keydir, suffix)
    else:
        raise SystemExit("Provide -d keys and/or members list (e.g., -m alice,bob,dave).")

    # our members in the quorum
    n = len(members)

    # sanity check
    if k > n:
        raise SystemExit(f"Threshold cannot be more than there are members. Threshold is {k}, members is {n}. Exiting!")

    # generate some shares!
    if args.generate_shares:
        secret = getsecret()
        print(f"The secret was generated and split into shares. To recover it, provide a quorum of {k} of {n} members.")
        blackbox(members, k, n, secret=secret, key_paths=key_paths)

    # recover some shares!
    if args.recover_shares:
        recovered = clearbox(members, k, key_paths)
        print(f"[+] Recovered secret {recovered.hex()}.")
