import sys
import os
import logging
import time
import jwt

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("test-jwt")

# First try to get private key from args
APP_PRIVATE_KEY = None
if len(sys.argv) > 1:
    APP_PRIVATE_KEY = str(sys.argv[1])

# If not provided as arg, try to get from environment variable
if APP_PRIVATE_KEY is None:
    APP_PRIVATE_KEY = os.getenv("APP_PRIVATE_KEY")

# Also check if we have a file path available
APP_PRIVATE_KEY_PATH = os.getenv("APP_PRIVATE_KEY_PATH")
APP_ID = os.getenv("APP_ID")

def test_jwt_generation():
    """Test JWT generation with the private key"""
    if not APP_ID:
        logger.error("APP_ID environment variable is not set")
        return False
        
    if not APP_PRIVATE_KEY and not APP_PRIVATE_KEY_PATH:
        logger.error("Neither APP_PRIVATE_KEY nor APP_PRIVATE_KEY_PATH is available")
        return False
    
    try:
        # Use direct key if available
        private_key = APP_PRIVATE_KEY
        
        # Otherwise try to load from file
        if not private_key and APP_PRIVATE_KEY_PATH:
            try:
                with open(APP_PRIVATE_KEY_PATH, "r") as key_file:
                    private_key = key_file.read()
                logger.info(f"Successfully loaded private key from file: {APP_PRIVATE_KEY_PATH}")
            except Exception as e:
                logger.error(f"Error reading private key file: {str(e)}")
                return False
                
        # JWT generation parameters
        now = int(time.time())
        expiration = now + (10 * 60)  # 10 minutes
        
        payload = {
            'iat': now,               
            'exp': expiration,        
            'iss': APP_ID             
        }
        
        # Generate the JWT
        token = jwt.encode(
            payload,
            private_key,
            algorithm='RS256'
        )
        
        # If successful, print confirmation
        logger.info("JWT generation successful!")
        
        # For security, only print the first few characters of the token
        if isinstance(token, bytes):
            token = token.decode('utf-8')
        masked_token = token[:10] + "..." if len(token) > 10 else "..."
        logger.info(f"Generated JWT token (begins with): {masked_token}")
        
        return True
        
    except Exception as e:
        logger.error(f"JWT generation failed: {str(e)}")
        return False

if __name__ == "__main__":
    if APP_PRIVATE_KEY is None and APP_PRIVATE_KEY_PATH is None:
        logger.error("Please provide a private key as an argument or set APP_PRIVATE_KEY/APP_PRIVATE_KEY_PATH environment variable.")
        sys.exit(1)
    else:
        # Mask key for security in logs
        if APP_PRIVATE_KEY:
            masked_key = APP_PRIVATE_KEY[:5] + "..." if len(APP_PRIVATE_KEY) > 5 else "..."
            logger.info(f"Private key available (begins with: {masked_key})")
        elif APP_PRIVATE_KEY_PATH:
            logger.info(f"Private key path available: {APP_PRIVATE_KEY_PATH}")
            
        # Test JWT generation
        if test_jwt_generation():
            logger.info("JWT test successful")
            sys.exit(0)
        else:
            logger.error("JWT test failed")
            sys.exit(1)