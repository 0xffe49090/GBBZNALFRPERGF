# Kasumi

![alt text](mermaid.png)

Kasumi is a tool to generate a secret that is shared amongst a quorum of users. One use case might be in the generation of a very important secret for which no single user should be solely trusted with. A completely silly and fictional example might be the case of needing a missile launch code. It's an important secret, but we should not trust any single person to it. Instead, we can from a group (aka, a "quorum"), supply our public keys, supply them to the system which generates a secret for each of us. Since each of us now hold only a part of a secret, it requires some *k(n)* (e.g., 3 out 5 of us) of us to reconvene to obtain the full secret. 

> Kasumi is not intended to introduce a new cryptographic primitive. Rather, it demonstrates one possible composition of established primitives -- publickey encryption and Shamir's Secret Sharing -- to simplify the distribution and recovery ceremony for threshold secrets.

This system has the properties and goals:

- No single user can know the entire secret.
- Prevents some basic "rubber-hose" cryptanalysis because it requires several of us to get the secret.
- No single user can obtain the secret without collusion (and thus, we ideally select a lareg enough group).
- Assembles the secret quickly when we have that "break glass" moment.
- Typically, each member of the quorum typically maintain their own private keys. They share only their public keys during the secret generation and sharing process. Δ

> Δ Variations on the concept are easy to imagine. Private key generation protected by passphrases inside of a sealed HSM, Argon2 for secrets, etc. The original idea is to provide *only* something "public" to get a slice back. 

An ideal implementation would be key generation inside of a hardware security module, but for this example, we'll just do that in Docker and pretend. :)

## Implementation

I used Shamir's Secret Sharing algorithm to carve up some distribution which we define. We might say that we want 5 members in our quorum, and that 3 of them need to be present to get the secret. 

It should work like this:

1. Dave, Alice, Bob, Mallory, and Oscar form a group/quorum. They don't even need to know each other. It might be better if they don't know each other. A motivated adversary attempting to coerce one of us into providing the secret will then be useless.
2. Each member of the quorum generates a key pair by which their part of the encrypted share will be protected. In the real world, the ideal case is that each member of the quorum creates a really strong password on their own keys. 
3. Each member supplies their public key to an opaque system (i.e., a service of some kind). This could be a Docker container, a web service, or a hardware security module, depending on needs. Obviously this system needs to be as secure as we could make it. It is not the goal of this work to ensure perfect security or to belabor the points of how this could go wrong.
4. After each member supplies their public key, the opaque system generates a secret, splits the secret into shares, encrypts the share with each member's public key, and returns the encrypted shares. In this reference implementation, the encrypted shares are written to the `shares/` directory as individual `.share` files. It is not really important to protect these encrypted shares in this proof, although it could be designed so that each person only sees their share of the secret.
5. Each member holds a share of the secret. If they need the actual secret, a quorum of the members reconvene, supply their share, and obtain the ultimate result. This could technically be built so that none of the users ever see the secret - in fact, if the point was to take an action on behalf of the group, it wouldn't even be necessary. 

## Installation

This tool requires the Python modules:

- cryptography 
- pycryptodome

1. Use a virtual environment, then install modules via `pip`.

```
$ python3 -m venv venv
$ source venv/bin/activate
$ python3 -m pip install -r requirements.txt
```

2. Run it! Here is an example **generating** a secret for a 5-member quorum. In this example, it takes **3** members to obtain the cleartext secret.

![alt text](generate.png)

3. Reconvene with **3 out of 5** members to reveal the secret. 

![alt text](recover.png)

> Note that in the real world, you might not want to reveal the secret at all, but carry out some function that the system is capable of on its own, i.e., make the blackbox "launch the model rocket". 

4. As expected, a quorum of less than designed will return an invalid secret. This has the attribute of being somewhat "rubber hose cryptanalysis" resistant.

![alt text](invalid.png)


For testing, you can run the generate_sample_keys.sh shell script to create a keys/ directory containing RSA key pairs for five sample quorum members.

![alt text](keypairs.png)


### Flags

Run `python3 kasumi.py -h` to get started. You should see these flags.

Flag | Meaning
---- | -------
-d, --keydir | Directory containing quorum member key pairs. Public keys should be named `*-public.pem`; private keys should be named `*-private.pem`. Example: `keys/alice-public.pem`.
-m, --members | Optional comma-delimited list of quorum members (e.g., `alice,bob,dave`). When omitted, all matching keys in `--keydir` are used.
-g, --generate-shares | Generates a new secret, splits it into shares, encrypts each share with the corresponding public key, and writes the encrypted shares to the `shares/` directory.
-r, --recover-shares | Recovers the secret from the encrypted share files in the `shares/` directory using the corresponding private keys.
-k, --threshold | Number of quorum members required to reconstruct the secret.
-h, --help | Display help information.

### Examples

Generate a new secret using all public keys in the `keys/` directory:

```bash
python3 kasumi.py -d keys -k 3 -g
```

Recover the secret using all available private keys:

```bash
python3 kasumi.py -d keys -k 3 -r
```

Generate shares for only selected quorum members:

```bash
python3 kasumi.py -d keys -m alice,bob,dave -k 2 -g
```

## Threat model and limitations

While I do believe this is a good idea, I acknowlege it is incomplete and lacks hardending in a number of ways. 

* This is a reference implementation intended for education and experimentation.
* Shares are encrypted in transit/storage but the implementation is not hardened.
* No authenticated metadata or integrity protection beyond the public-key encryption.
* No HSM or hardware-backed key protection.
* No key revocation or quorum membership management.
* Not independently reviewed or audited.

## AI Usage

This project was designed and implemented by the author. In the latest verstion, AI was used as an interactive development assistant rather than as an autonomous code generator.

AI assistance included:
- Discussing design ideas and implementation tradeoffs.
- Answering language and library questions while developing the tool.
- Suggesting small code refactorings and debugging assistance.
- Assisting with documentation, diagrams, and editing this README.

The overall architecture, protocol design, implementation decisions, and integration of the system were developed by the author. All generated suggestions were reviewed, tested, and modified as necessary before being incorporated.
