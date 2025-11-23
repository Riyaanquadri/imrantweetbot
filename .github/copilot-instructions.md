# Tweepy Project - Copilot Instructions

## Project Overview
Tweepy is a Python Twitter API client project for interacting with Twitter's REST and Stream APIs.

## Progress Checklist

- [x] Project structure created
- [x] Python environment setup
- [ ] Install dependencies
- [ ] Configure project
- [ ] Test setup
- [ ] Documentation review

## Project Structure
```
tweepy/
├── .github/
│   └── copilot-instructions.md
├── src/
│   ├── __init__.py
│   ├── client.py
│   ├── auth.py
│   └── utils.py
├── tests/
│   ├── __init__.py
│   └── test_client.py
├── .gitignore
├── README.md
├── requirements.txt
├── setup.py
└── pyproject.toml
```

## Setup Instructions

### 1. Create Python Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Run Tests
```bash
python -m pytest tests/
```

### 4. Development
- Use `venv` for development
- Follow PEP 8 style guide
- Add tests for new features
