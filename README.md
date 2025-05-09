# GitHub Discussion Auto-Labeler

Automatically labels GitHub discussions using AI to analyze content and apply appropriate tags.

## Features

- Automatically applies labels to new GitHub discussions
- Uses Azure OpenAI for content analysis
- Supports both GitHub token and GitHub App authentication
- Can be run locally or as a GitHub Action
- Includes a utility to create repository labels

## Setup

### Prerequisites

- Python 3.10+
- GitHub token or GitHub App credentials
- Azure OpenAI service (for AI-based labeling)

### Installation

1. Clone this repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Copy `.env.sample` to `.env` and fill in your credentials

### Environment Variables

| Variable | Description |
|----------|-------------|
| `TOKEN` | GitHub personal access token |
| `APP_ID` | GitHub App ID |
| `APP_PRIVATE_KEY` | GitHub App private key (content as string) |
| `APP_INSTALLATION_ID` | GitHub App installation ID |
| `DEFAULT_REPO` | Repository to monitor in format `owner/repo` |
| `AZURE_OPENAI_ENDPOINT` | Azure OpenAI API endpoint |
| `AZURE_OPENAI_KEY` | Azure OpenAI API key |
| `AZURE_OPENAI_API_VERSION` | Azure OpenAI API version |
| `RUN_INTERVAL_MINUTES` | How often to check for new discussions (in minutes) |

## Usage

### Running Locally

To run the script locally and continuously monitor for new discussions:

```bash
python basic.py
```

### Creating Repository Labels

To create the labels defined in `tags.json` in your repository:

```bash
python new-labels.py
```

### GitHub Action

This repo includes a GitHub Action workflow that automatically runs when new discussions are created.

To set up the GitHub Action:
1. Configure repository secrets with the environment variables listed above
2. The Action will run automatically when new discussions are created

## Customizing Labels

Edit the `tags.json` file to customize the available labels:

```json
{
  "tags": [
    {"name": "label-name", "description": "Label description", "color": "hex-color"}
  ]
}
```

## License

MIT
