import sys

APP_PRIVATE_KEY = None

# get private key from args

if len(sys.argv) > 1:
    APP_PRIVATE_KEY = str(sys.argv[1])

if APP_PRIVATE_KEY is None:
    print("Please provide the path to the private key file as an argument.")
    sys.exit(1)
else:
    # Print only the first few characters as confirmation, not the entire key
    masked_key = APP_PRIVATE_KEY[:5] + "..." if len(APP_PRIVATE_KEY) > 5 else "..."
    print(f"Private key loaded successfully (begins with: {masked_key})")