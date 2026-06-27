#!/bin/bash
#
# DEMO CODE! DO NOT USE IN PRODUCTION!
#
# The entire purpose of this bash script is to
# generate some keys to show how kasumi might be
# used.
#
# Do not use for legitimate work.
#
BASE="keys"
SHARES="shares"

echo 
echo "------------------------------- DEMO ONLY -------------------------------"
echo -e "[!] This is for demonstration only."
echo -e "[!] You probably do not want all of your private keys in one place.\n"
echo -e "Right, generating demo key pairs for use with Kasumi.\n"
members=("dave" "alice" "bob" "mallory" "oscar" "larry")

mkdir -p "$BASE" "$SHARES"

for name in "${members[@]}";do
    echo " - Generating a key pair for $name."
    openssl genrsa -out "$BASE/$name-private.pem" 2048 > /dev/null 2>&1 
    openssl rsa -in "$BASE/$name-private.pem" -pubout -out "$BASE/$name-public.pem" > /dev/null 2>&1
done

echo 
echo "[+] Done. Keys saved in '$BASE/'. Remember to only use these keys for testing kasumi. Shares will be put into $SHARES folder."
echo 
