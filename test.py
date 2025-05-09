import sys

APP_PRIVATE_KEY = None

# get private key from args

if len(sys.argv) > 1:
    APP_PRIVATE_KEY = sys.argv[1]

if APP_PRIVATE_KEY is None:
    print("Please provide the path to the private key file as an argument.")
    sys.exit(1)
else:
    print(f"Private key path: {APP_PRIVATE_KEY}")