#
# DEMO CODE! DO NOT USE IN PRODUCTION!
#
# The entire purpose of this bash script is to
# generate some keys to show how kasumi might be
# used.
#
# Do not use for legitimate work.
#
echo "[+] Generating demo key pairs for use with Kasumi.\n"
members=("dave" "alice" "bob" "mallory" "oscar" "larry")

for name in "${members[@]}";do
    echo " - Generating a key pair for $name."
    openssl genrsa -out $name-private.pem 2048 > /dev/null 2>&1 && openssl rsa -in $name-private.pem -pubout -out $name-public.pem > /dev/null 2>&1
done

echo 
echo "[+] Done. Remember to only use these keys for testing kasumi. "
echo 
ls *.pem
