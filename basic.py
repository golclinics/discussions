import json
import os
import random
import logging
import time
from pathlib import Path
from typing import Dict, List, Optional, Union, Any

import requests
import schedule
import jwt  # Added for GitHub App JWT generation
from dotenv import load_dotenv

# Optional imports for Azure components
try:
    import prompty
    import prompty.azure
    from prompty.tracer import trace, Tracer, console_tracer, PromptyTracer
except ImportError:
    logging.warning("Prompty package not found. Ensure it's installed with: pip install prompty[azure]")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("discussion-labeler")

# Load environment variables from .env file - ensure .env is in .gitignore
load_dotenv()

# Configure tracers if prompty is available
if 'prompty' in globals():
    # Add console and json tracer at application startup
    Tracer.add("console", console_tracer)
    json_tracer = PromptyTracer()
    Tracer.add("PromptyTracer", json_tracer.tracer)

# GitHub API settings - get token from environment variables
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
DEFAULT_REPO = os.getenv("DEFAULT_REPO", "golclinics/discussions")
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "30"))  # Default 30 second timeout

# GitHub App settings
GITHUB_APP_ID = os.getenv("GITHUB_APP_ID")
GITHUB_APP_PRIVATE_KEY_PATH = os.getenv("GITHUB_APP_PRIVATE_KEY_PATH", "./azure-ai-foundry-discussions.2025-05-06.private-key.pem")
GITHUB_APP_INSTALLATION_ID = os.getenv("GITHUB_APP_INSTALLATION_ID")

# GitHub API rate limiting constants
MAX_RETRIES = 3
RETRY_BACKOFF = 2  # seconds, will be multiplied by attempt number

class TokenMissingError(Exception):
    """Exception raised when GitHub token is missing."""
    pass

class GithubAppAuthError(Exception):
    """Exception raised when GitHub App authentication fails."""
    pass

def validate_token() -> None:
    """Validate that the GitHub token is available."""
    if not GITHUB_TOKEN:
        raise TokenMissingError(
            "GitHub token not found in environment variables. "
            "Please set the GITHUB_TOKEN environment variable."
        )

def validate_github_app_config() -> None:
    """Validate that the GitHub App configuration is available."""
    missing = []
    if not GITHUB_APP_ID:
        missing.append("GITHUB_APP_ID")
    if not GITHUB_APP_PRIVATE_KEY_PATH:
        missing.append("GITHUB_APP_PRIVATE_KEY_PATH")
    if not GITHUB_APP_INSTALLATION_ID:
        missing.append("GITHUB_APP_INSTALLATION_ID")
        
    if missing:
        raise GithubAppAuthError(
            f"GitHub App configuration missing: {', '.join(missing)}. "
            "Please set the required environment variables."
        )

def generate_jwt() -> str:
    """Generate a JWT for GitHub App authentication.
    
    Returns:
        JWT token string
        
    Raises:
        GithubAppAuthError: If JWT generation fails
    """
    validate_github_app_config()
    
    try:
        # JWT expiration time (10 minutes is recommended by GitHub)
        now = int(time.time())
        expiration = now + (10 * 60)  # 10 minutes
        
        # Prepare the JWT payload
        payload = {
            'iat': now,               # Issued at time
            'exp': expiration,        # Expiration time
            'iss': GITHUB_APP_ID      # GitHub App ID
        }
        
        # Read private key from file path
        try:
            key_path = Path(GITHUB_APP_PRIVATE_KEY_PATH)
            if (key_path.exists()):
                with open(key_path, "r") as key_file:
                    private_key = key_file.read()
                logger.info(f"Successfully loaded private key from file: {GITHUB_APP_PRIVATE_KEY_PATH}")
            else:
                logger.error(f"Private key file not found at: {GITHUB_APP_PRIVATE_KEY_PATH}")
                raise FileNotFoundError(f"Private key file not found: {GITHUB_APP_PRIVATE_KEY_PATH}")
        except Exception as e:
            logger.error(f"Error reading private key file: {str(e)}")
            raise
        
        # Generate the JWT
        token = jwt.encode(
            payload,
            private_key,
            algorithm='RS256'
        )
        
        # If token is bytes, decode to string (depends on PyJWT version)
        if isinstance(token, bytes):
            token = token.decode('utf-8')
            
        return token
        
    except Exception as e:
        logger.error(f"Error generating JWT: {str(e)}")
        raise GithubAppAuthError(f"Failed to generate JWT: {str(e)}")

def get_installation_token() -> str:
    """Get an installation access token for the GitHub App.
    
    Returns:
        Installation access token
        
    Raises:
        GithubAppAuthError: If token retrieval fails
    """
    validate_github_app_config()
    
    try:
        # Generate JWT for authentication
        jwt_token = generate_jwt()
        
        # API endpoint for getting an installation token
        url = f"https://api.github.com/app/installations/{GITHUB_APP_INSTALLATION_ID}/access_tokens"
        
        headers = {
            "Authorization": f"Bearer {jwt_token}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        response = handle_request_with_retry("post", url, headers)
        data = response.json()
        
        if "token" not in data:
            logger.error(f"No token in response: {data}")
            raise GithubAppAuthError("Failed to get installation token: No token in response")
            
        return data["token"]
        
    except Exception as e:
        logger.error(f"Error getting installation token: {str(e)}")
        raise GithubAppAuthError(f"Failed to get installation token: {str(e)}")

def get_auth_headers() -> Dict[str, str]:
    """Get authentication headers for GitHub API calls.
    
    Returns:
        Dictionary of headers including authorization
        
    Raises:
        GithubAppAuthError: If headers cannot be generated
    """
    try:
        token = get_installation_token()
        return {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json"
        }
    except Exception as e:
        logger.error(f"Error getting auth headers: {str(e)}")
        raise GithubAppAuthError(f"Failed to get auth headers: {str(e)}")

def validate_repo_url(repo_url: str) -> tuple:
    """Validate and parse the repository URL.
    
    Args:
        repo_url: Repository URL in the format "owner/name"
        
    Returns:
        Tuple of (owner, name)
        
    Raises:
        ValueError: If repo_url format is invalid
    """
    if not repo_url or "/" not in repo_url:
        raise ValueError(f"Invalid repository URL format: {repo_url}. Expected format: owner/name")
    
    parts = repo_url.split("/")
    if len(parts) != 2 or not all(parts):
        raise ValueError(f"Invalid repository URL format: {repo_url}. Expected format: owner/name")
    
    return parts[0], parts[1]

def handle_request_with_retry(
    method: str, 
    url: str, 
    headers: Dict[str, str], 
    json_data: Optional[Dict] = None,
    max_retries: int = MAX_RETRIES
) -> requests.Response:
    """Make HTTP request with retry logic and exponential backoff for rate limits.
    
    Args:
        method: HTTP method (get, post, patch)
        url: API URL
        headers: HTTP headers
        json_data: JSON payload
        max_retries: Maximum number of retry attempts
        
    Returns:
        Response object
        
    Raises:
        requests.exceptions.RequestException: If request fails after retries
    """
    attempt = 0
    last_exception = None
    
    while attempt < max_retries:
        try:
            if method.lower() == "get":
                response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
            elif method.lower() == "post":
                response = requests.post(url, headers=headers, json=json_data, timeout=REQUEST_TIMEOUT)
            elif method.lower() == "patch":
                response = requests.patch(url, headers=headers, json=json_data, timeout=REQUEST_TIMEOUT)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            # Check for rate limiting
            if response.status_code == 403 and "rate limit exceeded" in response.text.lower():
                retry_after = int(response.headers.get("Retry-After", RETRY_BACKOFF * (attempt + 1)))
                logger.warning(f"Rate limit exceeded. Retrying after {retry_after} seconds.")
                time.sleep(retry_after)
                attempt += 1
                continue
            
            # Check if successful
            response.raise_for_status()
            return response
            
        except requests.exceptions.RequestException as e:
            logger.warning(f"Request failed (attempt {attempt+1}/{max_retries}): {str(e)}")
            last_exception = e
            
            # Exponential backoff
            sleep_time = RETRY_BACKOFF * (2 ** attempt)
            time.sleep(sleep_time)
            attempt += 1
    
    # If we get here, all retries failed
    if last_exception:
        logger.error(f"All retry attempts failed: {str(last_exception)}")
        raise last_exception
    
    raise requests.exceptions.RequestException("All retry attempts failed.")

@trace
def fetch_github_discussions(repo_url: str) -> Optional[Dict]:
    """Fetch discussions from the specified GitHub repository.
    
    Args:
        repo_url: Repository URL in the format "owner/name"
        
    Returns:
        Dictionary containing discussion data or None if no discussions found
    """
    try:
        owner, name = validate_repo_url(repo_url)
        
        # GitHub GraphQL API endpoint
        api_url = "https://api.github.com/graphql"
        
        # Get auth headers for GitHub App
        headers = get_auth_headers()
        
        # GraphQL query to fetch discussions
        query = """
        query RepoDiscussions($owner: String!, $name: String!) {
          repository(owner: $owner, name: $name) {
            discussions(first: 10, orderBy: {field: CREATED_AT, direction: DESC}) {
              nodes {
                id
                number
                title
                body
                category {
                  name
                }
                labels(first: 10) {
                  nodes {
                    name
                  }
                }
              }
            }
          }
        }
        """
        
        variables = {"owner": owner, "name": name}
        payload = {"query": query, "variables": variables}
        
        response = handle_request_with_retry("post", api_url, headers, payload)
        
        data = response.json()
        
        # Validate response structure
        if not isinstance(data, dict) or "data" not in data:
            logger.error(f"Invalid response format: {data}")
            return None
            
        # Navigate through the response with safe gets
        repository = data.get("data", {}).get("repository", {})
        discussions = repository.get("discussions", {}).get("nodes", [])
        
        if not discussions:
            logger.info("No discussions found in the repository.")
            return None
            
        return random.choice(discussions)  # Pick a random discussion
        
    except (ValueError, GithubAppAuthError, requests.exceptions.RequestException) as e:
        logger.error(f"Error fetching discussions: {str(e)}")
        return None

@trace
def run_with_rag(title: str, description: str) -> List[str]:
    """Run Prompty with RAG integration and return a Python list of tags.
    
    Args:
        title: Discussion title
        description: Discussion description
        
    Returns:
        List of tags
    """
    try:
        # Load tags from JSON file with better error handling
        tags_file_path = Path("tags.json")
        if not tags_file_path.exists():
            logger.error("tags.json file not found")
            return []
            
        with open(tags_file_path, "r") as f:
            tags_data = json.load(f)
            
        # Validate tags format
        if not isinstance(tags_data, dict) or "tags" not in tags_data:
            logger.error("Invalid tags.json format")
            return []
            
        azure_tags = tags_data.get("tags", [])
        
        # Handle case with no tags
        if not azure_tags:
            logger.warning("No tags found in tags.json")
            return []
            
        # Convert tags to strings for joining if they're dictionaries
        tag_strings = []
        for tag in azure_tags:
            if isinstance(tag, dict):
                tag_string = f"{tag.get('name')}: {tag.get('description')}"
                tag_strings.append(tag_string)
            elif isinstance(tag, str):
                tag_strings.append(tag)
                
        # Combine search results with the original description
        augmented_description = description + "\n\n" + "\n".join(tag_strings)
        
        # Execute the Prompty file
        prompty_file_path = Path("basic.prompty")
        if not prompty_file_path.exists():
            logger.error("basic.prompty file not found")
            return []
            
        raw = prompty.execute(
            "basic.prompty",
            inputs={
                "title": title,
                "tags": azure_tags,
                "description": augmented_description
            }
        )
        
        # Parse prompty's JSON output
        try:
            parsed = json.loads(raw)
            # If prompty returns a bare list:
            if isinstance(parsed, list):
                return [str(item) for item in parsed]  # Ensure all items are strings
            # If it returns {"tags": [...]}:
            if isinstance(parsed, dict):
                tags = parsed.get("tags", [])
                return [str(item) for item in tags]  # Ensure all items are strings
                
        except json.JSONDecodeError as e:
            logger.error(f"Could not parse RAG output: {e}")
            logger.debug(f"RAG raw output: {raw}")
            
    except Exception as e:
        logger.error(f"Error in run_with_rag: {str(e)}")
        
    return []

@trace
def fetch_unlabeled_discussions(repo_url: str) -> List[Dict]:
    """Fetch open discussions that have no labels yet.
    
    Args:
        repo_url: Repository URL in the format "owner/name"
        
    Returns:
        List of dictionaries containing unlabeled discussion data
    """
    try:
        owner, name = validate_repo_url(repo_url)
        
        # GitHub GraphQL API endpoint
        api_url = "https://api.github.com/graphql"
        
        # Get auth headers for GitHub App
        headers = get_auth_headers()
        
        # GraphQL query to fetch discussions without labels
        query = """
        query RepoDiscussionsWithoutLabels($owner: String!, $name: String!) {
          repository(owner: $owner, name: $name) {
            discussions(first: 10, orderBy: {field: CREATED_AT, direction: DESC}) {
              nodes {
                id
                number
                title
                body
                category {
                  name
                }
                labels(first: 10) {
                  nodes {
                    name
                  }
                }
              }
            }
          }
        }
        """
        
        variables = {"owner": owner, "name": name}
        payload = {"query": query, "variables": variables}
        
        response = handle_request_with_retry("post", api_url, headers, payload)
        
        data = response.json()
        
        # Validate response structure
        if not isinstance(data, dict) or "data" not in data:
            logger.error(f"Invalid response format: {data}")
            return []
            
        # Navigate through the response with safe gets
        repository = data.get("data", {}).get("repository", {})
        discussions = repository.get("discussions", {}).get("nodes", [])
        
        if not discussions:
            logger.info("No discussions found in the repository.")
            return []
        
        # Filter discussions with no labels
        unlabeled_discussions = []
        for discussion in discussions:
            if not isinstance(discussion, dict):
                continue
                
            labels = discussion.get("labels", {}).get("nodes", [])
            if not labels:
                unlabeled_discussions.append(discussion)
        
        return unlabeled_discussions
        
    except (ValueError, GithubAppAuthError, requests.exceptions.RequestException) as e:
        logger.error(f"Error fetching unlabeled discussions: {str(e)}")
        return []

def get_discussion_node_id(owner: str, repo: str, discussion_number: int, headers: Dict[str, str]) -> str:
    """Fetch the node ID for a discussion given its number."""
    query = '''
    query($owner: String!, $repo: String!, $number: Int!) {
      repository(owner: $owner, name: $repo) {
        discussion(number: $number) {
          id
        }
      }
    }
    '''
    variables = {"owner": owner, "repo": repo, "number": discussion_number}
    payload = {"query": query, "variables": variables}
    response = requests.post("https://api.github.com/graphql", headers=headers, json=payload)
    response.raise_for_status()
    data = response.json()
    return data["data"]["repository"]["discussion"]["id"]

def get_label_node_ids(owner: str, repo: str, label_names: list, headers: Dict[str, str]) -> list:
    """Fetch node IDs for label names in a repo."""
    query = '''
    query($owner: String!, $repo: String!) {
      repository(owner: $owner, name: $repo) {
        labels(first: 50) {
          nodes {
            id
            name
          }
        }
      }
    }
    '''
    variables = {"owner": owner, "repo": repo}
    payload = {"query": query, "variables": variables}
    response = requests.post("https://api.github.com/graphql", headers=headers, json=payload)
    response.raise_for_status()
    data = response.json()
    all_labels = data["data"]["repository"]["labels"]["nodes"]
    label_ids = [label["id"] for label in all_labels if label["name"] in label_names]
    return label_ids

def assign_labels_to_discussion(repo_url: str, discussion_number: int, label_names: list) -> bool:
    """Assign labels to a discussion using GraphQL mutation."""
    owner, repo = validate_repo_url(repo_url)
    headers = get_auth_headers()
    headers["Content-Type"] = "application/json"
    try:
        discussion_id = get_discussion_node_id(owner, repo, discussion_number, headers)
        label_ids = get_label_node_ids(owner, repo, label_names, headers)
        if not label_ids:
            logger.error(f"No matching label IDs found for: {label_names}")
            return False
        mutation = '''
        mutation($labelableId: ID!, $labelIds: [ID!]!) {
          addLabelsToLabelable(input: {labelableId: $labelableId, labelIds: $labelIds}) {
            clientMutationId
          }
        }
        '''
        variables = {"labelableId": discussion_id, "labelIds": label_ids}
        payload = {"query": mutation, "variables": variables}
        response = requests.post("https://api.github.com/graphql", headers=headers, json=payload)
        response.raise_for_status()
        logger.info(f"Successfully labeled discussion #{discussion_number} with {label_names}")
        return True
    except Exception as e:
        logger.error(f"Failed to label discussion #{discussion_number}: {str(e)}")
        return False

def label_discussion(repo_url: str, discussion_number: Union[str, int], labels: List[str]) -> bool:
    """Assign labels to a discussion using GraphQL mutation."""
    if not labels:
        logger.info(f"No labels for #{discussion_number}, skipping.")
        return False
    try:
        return assign_labels_to_discussion(repo_url, int(discussion_number), labels)
    except Exception as e:
        logger.error(f"Failed to label discussion #{discussion_number}: {str(e)}")
        return False

@trace
def process_discussions(repo: str = None) -> None:
    """Process unlabeled discussions and apply labels.
    
    Args:
        repo: Repository URL in the format "owner/name" (optional)
    """
    if not repo:
        repo = DEFAULT_REPO
        
    try:
        # Validate GitHub App configuration
        validate_github_app_config()
        
        # Fetch unlabeled discussions
        discussions = fetch_unlabeled_discussions(repo)
        logger.info(f"Found {len(discussions)} unlabeled discussions")
        
        for discussion in discussions:
            if not isinstance(discussion, dict):
                continue
                
            # Extract data with safe gets
            discussion_number = discussion.get("number")
            if not discussion_number:
                continue
                
            title = discussion.get("title", "")
            body = discussion.get("body", "")
            
            # Generate labels
            labels = run_with_rag(title, body)
            
            # Apply labels if generated
            if labels:
                label_discussion(repo, discussion_number, labels)
                
    except GithubAppAuthError as e:
        logger.error(str(e))
    except Exception as e:
        logger.error(f"Error processing discussions: {str(e)}")

def main() -> None:
    """Main entry point for the application."""
    try:
        # Initial run
        logger.info("Performing initial run...")
        process_discussions()
        
        # Schedule periodic runs
        run_interval = int(os.getenv("RUN_INTERVAL_MINUTES", "1"))
        schedule.every(run_interval).minutes.do(process_discussions)
        
        logger.info(f"Agent started: checking for new discussions every {run_interval} minutes.")
        
        while True:
            schedule.run_pending()
            time.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("Application stopped by user.")
    except Exception as e:
        logger.error(f"Unhandled exception: {str(e)}")
        raise

if __name__ == "__main__":
    main()