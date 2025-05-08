import json, requests, os
from pathlib import Path

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

def create_labels(repo_url: str, labels: list[dict]):
    api_base = f"https://api.github.com/repos/{repo_url}/labels"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    for lbl in labels:
        resp = requests.post(api_base, headers=headers, json=lbl)
        if resp.status_code == 201:
            print(f"✅ Created label {lbl['name']}")
        else:
            print(f"❌ Failed {lbl['name']}: {resp.status_code}", resp.json())

def add_labels_to_discussion(repo_url: str, discussion_number: int, labels: list[str]):
    """
    Add labels to a GitHub discussion.
    
    Args:
        repo_url (str): The repository URL in the format 'owner/repo'
        discussion_number (int): The discussion number to add labels to
        labels (list[str]): List of label names to add to the discussion
    """
    # GitHub API endpoint for adding labels to a discussion
    api_base = f"https://api.github.com/repos/{repo_url}/discussions/{discussion_number}/labels"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    # Payload for the API call
    payload = {"labels": labels}
    
    # Make the API call
    resp = requests.post(api_base, headers=headers, json=payload)
    
    if resp.status_code == 200:
        print(f"✅ Added labels to discussion #{discussion_number}: {', '.join(labels)}")
    else:
        print(f"❌ Failed to add labels to discussion #{discussion_number}: {resp.status_code}", resp.json())

if __name__ == "__main__":
    # read tags.json from the same directory as this script
    tags_file = Path(__file__).parent / "tags.json"
    data = json.loads(tags_file.read_text())
    
    # Update to use 'labels' key instead of 'tags'
    labels_data = data.get("labels", [])

    new_labels = [
        {
            "name": t["name"],
            "description": t.get("description", ""),
            "color": t.get("color", "ededed")
        }
        for t in labels_data
        if "name" in t
    ]

    # Create labels in the repository
    create_labels("golclinics/discussions", new_labels)
    
    # Example of how to add labels to a discussion
    # Uncomment and modify the line below to add labels to a specific discussion
    # discussion_number = 1  # Replace with the actual discussion number
    # labels_to_add = ["ai-agents", "documentation"]  # Replace with actual label names
    # add_labels_to_discussion("golclinics/discussions", discussion_number, labels_to_add)
    
    # To use interactively, you can prompt for the discussion number and labels
    try:
        discussion_number = int(input("Enter the discussion number to add labels to (or press Enter to skip): ").strip())
        if discussion_number > 0:
            available_labels = [label["name"] for label in labels_data]
            print(f"Available labels: {', '.join(available_labels)}")
            labels_input = input("Enter comma-separated label names to add: ").strip()
            if labels_input:
                labels_to_add = [label.strip() for label in labels_input.split(",")]
                add_labels_to_discussion("golclinics/discussions", discussion_number, labels_to_add)
    except ValueError:
        print("No labels were added to any discussions.")