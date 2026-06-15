import hashlib, argparse, os, platform, sys, json
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives.serialization import load_pem_public_key
from cryptography.hazmat.primitives.serialization import load_pem_private_key
from cryptography.hazmat.primitives import hashes
from Crypto.Protocol.SecretSharing import Shamir
from Crypto.Random import get_random_bytes

'''
    1. Create the secret.
    2. Carve up the secret into shares.
    3. Return encrypted shares.
    4. Recombine the shares based on the threshold.
    5. Output the secret.
'''

def pp(x, color='', strext=''):
    '''
        PrettyPrint. Just a color hack. 
        I know there are multiple color libs. Do not want.

    '''
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
    except:
        print(x)
        pass

def generateshares(secret,k,n):
    '''
     Takes a secret and splits that secret into shares.
     Retuns an array of tuples, e.g.
       [(1,b"stuff"),(2,"more stuff")]

    '''
    # split the secret into shares
    shares = Shamir.split(k, n, secret)
    return shares

def decryptshare(privkey, ciphertext):
    '''
        Take a private key, and the encrypted share.
        Return decrypted share.
    '''
    with open(privkey, "rb") as f:
        try:
            private_key = load_pem_private_key(f.read(), password=None)
        except:
            raise SystemExit(f"Public key {privkey} not found. ")
    try:
        payload = private_key.decrypt(
            ciphertext,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None,
            ),
        )
    except:
        raise SystemExit(f"Decryption failed with key {privkey}. Likely invalid quorom member.")

    idx = int.from_bytes(payload[:2], "big")
    share_bytes = payload[2:]

    return (idx, share_bytes)

def encryptshares(pubkey, share):
    ''' 
        Takes a public key and share of the secret.
        Returns an encrypted share. 

    '''
    with open(pubkey, "rb") as f:
        try:
            public_key = load_pem_public_key(f.read())
        except:
            raise SystemExit(f"Public key {pubkey} not found. ")

    idx, share_bytes = share
    payload = idx.to_bytes(2, "big") + share_bytes
    
    ciphertext = public_key.encrypt(
        payload,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None,
        ),
    )

    return ciphertext

def getsecret():
    secret = get_random_bytes(16)
    return secret

def blackbox(members, k, n, secret=None):
    '''
        In an ideal world, this would live in an HSM. 
        - Generate a secret.
        - Carve the secret into encrypted shares for each member of the quorum.
        - Write the shares to JSON files.

    '''

    # just default to generating a secret
    if secret is None:
        secret = get_random_bytes(16)
    
    m_count = len(members)
    shares = generateshares(secret, k, n)
    encrypted_shares = {}

    for member, share in zip(members, shares):
        c = encryptshares(f"{member}-public.pem", share)
        encrypted_shares[member] = c

        pp(f" - Writing share for {member}.","g")
        with open(f"{member}-share","w") as f:
            f.write(c.hex())


def clearbox(members, k):
    '''
        In an idea world, unseal protected invisible secrets (e.g., in an HSM).
        - Collect the JSON files.
        - Recombine the encrypted secrets.
        - Output the secret (or keep it internal for the system to operate on).

    '''
    # recover the secret
    decrypted = []

    try:
        for member in members[:k]:
            with open(f"{member}-share") as f:
                encryptshare = bytes.fromhex(f.read())
            decrypted.append(
                decryptshare(f"{member}-private.pem", encryptshare)
            )
    except:
        raise SystemExit(f"Failed to decrypt using member {member}.")

    return Shamir.combine(decrypted)

def foolishdemo(members, k, n):
    secret = getsecret()
    pp("-- FOOLISH DEMO MODE DO NOT USE --","r")
    pp("[*] Creating secret and generating encrypted shares.","y")
    pp(f"[*] The demo secret is {secret.hex()}.")
    blackbox(members, k, n, secret)
    pp("[*] Attempting to recover the secret.","y")
    recovered = clearbox(members, k)
    print(f"[+] Recovered demo secret is {recovered.hex()}.")
    

if __name__ == '__main__':
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('-m', '--members', help="Comma delimted list of member keys. --members 1,2,3,4.")
    parser.add_argument('-g', '--generate-shares', action='store_true', help="Generates encrypted shares by members. Requires public keys, 1-public.pem, 2-public.pem, etc.")
    parser.add_argument('-r', '--recover-shares', action='store_true',  help="Recover shares. Needs member named 'share' files, 1-share, 2-share, and associated member private keys.")
    parser.add_argument("-k", "--threshold", type=int, help="Number of shares required to recover secret.")
    parser.add_argument("-f", "--foolishdemo", action='store_true', help="DO NOT USE THIS. Demonstrates the tool. Not useful in the real world.")
    parser.add_argument('-h', '--help', action='store_true')

    # sweet banner
    banner = '''
     __                               __
    |  |--.---.-.-----.--.--.--------|__|
    |    <|  _  |__ --|  |  |        |  |
    |__|__|___._|_____|_____|__|__|__|__|
  
    Kasumi generates (and recovers) a secret based on a supplied list of public keys of a quorum.

    1. Get members you want to involve.
    2. Everyone generates a key pair.
    3. Members supply their public keys.
    4. System generates a secret.
    5. Each member gets a share of the secret.

    $ python3 ./kasumi.py -m alice,bob,mallory,oscar,dave -k 2

    '''

    args = parser.parse_args()

    # bail on help 
    if args.help:
         pp(banner,'g')
         parser.print_help()
         print('\n')
         sys.exit(0)
    
    # go for it
    if args.members:
        if "," in args.members:
            md = {}
            members = args.members.split(',') # read args into a list

        # just the k(n) for clarity
        n = len(members)
        k = args.threshold

        # Sanity checks
        if not args.threshold:
            raise SystemExit("Quorum threshold is a required value. (e.g., -k 2)")
        
        if k < 2:
            raise SystemExit("Quorum must be at least 2. Exiting!")

        if k > n:
            raise SystemExit(f"Threshold cannot be more than there are members! Threshold is {k}, members is {n}. Exiting!")

        if len(set(members)) != len(members):
            raise SystemExit("Member names must be unique. I'm out!")

        # the demo function - DO NOT USE THIS
        # hope you know what you're doing
        if args.foolishdemo:
            foolishdemo(members, k, n)
            sys.exit()

        # generate shares
        if args.generate_shares:
            # ditch this for real
            secret = getsecret()
            pp(f"Generated a secret {secret.hex()}. Note that this is printed only for testing.","k")
            print(f"The secret was generated and split into shares. To obtain the cleartext secret, you must provide the quorum {k} of {n} members.")
            blackbox(members, k, n, secret=secret)

        if args.recover_shares:
            recovered = clearbox(members, k)
            print(f"[+] Recovered secret {recovered.hex()}.")

        # create secret and encrypted shares
        ## pp("[*] Creating secret and generating encrypted shares.","y")
        ##blackbox(members, k, n)

        # secret = get_random_bytes(16)
        
        # m_count = len(members)
        # shares = generateshares(secret, k, n)
        # encrypted_shares = {}

        # for member, share in zip(members, shares):
        #     c = encryptshares(f"{member}-public.pem", share)
        #     encrypted_shares[member] = c

        #     # output junk
        #     pp(member,"g")
        #     pp(f"{c.hex()}","k")

        # recover the secret
        ##pp("[*] Attempting to recover the secret.","y")
        ##recovered = clearbox(members, k)

        # decrypted = []

        # for member in members[:k]:
        #     decrypted.append(
        #         decryptshare(f"{member}-private.pem", encrypted_shares[member])
        #     )

        # recovered = Shamir.combine(decrypted)
        
        # This is just for demo.
        # print("generated:", secret.hex())
        # print("recovered:", recovered.hex())

        # testing
        ##print(recovered.hex())
        
