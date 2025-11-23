# Tweepy - Twitter API Client

A Python client library for interacting with Twitter's REST and Stream APIs.

## Features

- Twitter API v2 support
- REST API client
- Stream API client
- Authentication handling
- Tweet search and retrieval
- User timeline access

## Installation

### Prerequisites
- Python 3.8+
- pip

### Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd tweepy
```

2. Create and activate virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

## Configuration

Set your Twitter API credentials as environment variables:

```bash
export TWITTER_API_KEY="your-api-key"
export TWITTER_API_SECRET="your-api-secret"
export TWITTER_ACCESS_TOKEN="your-access-token"
export TWITTER_ACCESS_SECRET="your-access-secret"
```

Or create a `.env` file:
```
TWITTER_API_KEY=your-api-key
TWITTER_API_SECRET=your-api-secret
TWITTER_ACCESS_TOKEN=your-access-token
TWITTER_ACCESS_SECRET=your-access-secret
```

## Usage

```python
from src import TwitterClient, Auth

# Initialize authentication
auth = Auth()

# Create client
client = TwitterClient(
    api_key=auth.api_key,
    api_secret=auth.api_secret,
    access_token=auth.access_token,
    access_secret=auth.access_secret,
)

# Get user timeline
tweets = client.get_user_timeline("twitter", count=10)

# Search tweets
results = client.search_tweets("python", count=5)
```

## Testing

Run the test suite:

```bash
python -m pytest tests/
```

Run with coverage:

```bash
python -m pytest tests/ --cov=src
```

## Project Structure

```
tweepy/
├── src/
│   ├── __init__.py           # Package initialization
│   ├── client.py             # Main Twitter API client
│   ├── auth.py               # Authentication module
│   └── utils.py              # Utility functions
├── tests/
│   ├── __init__.py
│   └── test_client.py        # Client tests
├── .gitignore
├── requirements.txt          # Project dependencies
├── setup.py                  # Package setup
├── pyproject.toml           # Project configuration
└── README.md                # This file
```

## Development

1. Activate virtual environment:
```bash
source venv/bin/activate
```

2. Install development dependencies:
```bash
pip install -r requirements-dev.txt
```

3. Run tests:
```bash
pytest tests/
```

4. Format code:
```bash
black src/ tests/
```

5. Lint code:
```bash
pylint src/
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For issues and questions, please open an issue on GitHub.

## Acknowledgments

- [Twitter API Documentation](https://developer.twitter.com/en/docs)
- Python Community
