"""
Configuration management with support for development (.env) and production (secret stores).

Development: Uses python-dotenv to load from .env file
Production: Supports AWS Secrets Manager, GCP Secret Manager, or HashiCorp Vault

Never commit .env file with real credentials to git!
"""
from dotenv import load_dotenv
import os
import json
from typing import Optional

# Load from .env for development
load_dotenv()

class SecretsManager:
    """Handles secret retrieval from different sources."""
    
    @staticmethod
    def get_secret(key: str, default: Optional[str] = None) -> Optional[str]:
        """
        Get secret from environment variable or secret store.
        
        Priority order:
        1. Environment variable (if set explicitly)
        2. .env file (development)
        3. AWS Secrets Manager (production)
        4. Default value
        """
        # First check if explicitly set in environment (highest priority)
        if key in os.environ and os.environ[key]:
            return os.environ[key]
        
        # Try AWS Secrets Manager if in production
        if os.getenv('USE_AWS_SECRETS') == 'true':
            return SecretsManager._get_from_aws_secrets(key, default)
        
        # Fall back to .env or default
        return os.getenv(key, default)
    
    @staticmethod
    def _get_from_aws_secrets(secret_name: str, default: Optional[str] = None) -> Optional[str]:
        """Retrieve secret from AWS Secrets Manager."""
        try:
            import boto3
            client = boto3.client('secretsmanager', region_name=os.getenv('AWS_REGION', 'us-east-1'))
            response = client.get_secret_value(SecretId=secret_name)
            
            if 'SecretString' in response:
                secret = json.loads(response['SecretString'])
                return secret.get(secret_name, default)
            else:
                return response.get('SecretBinary', default)
        except Exception as e:
            from .logger import logger
            logger.warning(f'Failed to retrieve secret {secret_name} from AWS: {e}')
            return default


class Config:
    """Application configuration from secure sources."""
    
    # ============ Twitter/X API Credentials ============
    X_BEARER_TOKEN = SecretsManager.get_secret('X_BEARER_TOKEN')
    X_API_KEY = SecretsManager.get_secret('X_API_KEY')
    X_API_SECRET = SecretsManager.get_secret('X_API_SECRET')
    X_ACCESS_TOKEN = SecretsManager.get_secret('X_ACCESS_TOKEN')
    X_ACCESS_SECRET = SecretsManager.get_secret('X_ACCESS_SECRET')

    # ============ LLM Provider Credentials ============
    LLM_PROVIDER = SecretsManager.get_secret('LLM_PROVIDER', 'openai')
    OPENAI_API_KEY = SecretsManager.get_secret('OPENAI_API_KEY')

    # ============ Bot Configuration ============
    BOT_HANDLE = SecretsManager.get_secret('BOT_HANDLE', 'bot')
    PROJECT_KEYWORDS = [
        k.strip() for k in SecretsManager.get_secret('PROJECT_KEYWORDS', '').split(',') 
        if k.strip()
    ]

    POST_INTERVAL_HOURS = int(SecretsManager.get_secret('POST_INTERVAL_HOURS', '3'))
    MENTION_POLL_MINUTES = int(SecretsManager.get_secret('MENTION_POLL_MINUTES', '1'))
    POST_JITTER_SECONDS = int(SecretsManager.get_secret('POST_JITTER_SECONDS', '900'))
    MENTION_JITTER_SECONDS = int(SecretsManager.get_secret('MENTION_JITTER_SECONDS', '30'))
    MENTION_MAX_RESULTS = int(SecretsManager.get_secret('MENTION_MAX_RESULTS', '20'))

    POSTS_PER_DAY = int(SecretsManager.get_secret('POSTS_PER_DAY', '5'))
    REPLIES_PER_DAY = int(SecretsManager.get_secret('REPLIES_PER_DAY', '10'))
    GLOBAL_REPLIES_PER_HOUR = int(SecretsManager.get_secret('GLOBAL_REPLIES_PER_HOUR', '5'))
    REPLIES_PER_USER_PER_HOUR = int(SecretsManager.get_secret('REPLIES_PER_USER_PER_HOUR', '2'))
    MONTHLY_WRITE_LIMIT = int(SecretsManager.get_secret('MONTHLY_WRITE_LIMIT', '500'))
    MONTHLY_WRITE_LIMIT_DAYS = int(SecretsManager.get_secret('MONTHLY_WRITE_LIMIT_DAYS', '30'))

    REQUIRE_POST_APPROVAL = SecretsManager.get_secret('REQUIRE_POST_APPROVAL', 'true').lower() in ('1', 'true', 'yes')
    BIG_ACCOUNT_FOLLOWERS = int(SecretsManager.get_secret('BIG_ACCOUNT_FOLLOWERS', '10000'))

    # ============ Runtime Flags ============
    DRY_RUN = SecretsManager.get_secret('DRY_RUN', 'true').lower() in ('1', 'true', 'yes')
    LOG_LEVEL = SecretsManager.get_secret('LOG_LEVEL', 'INFO')
    USE_AWS_SECRETS = SecretsManager.get_secret('USE_AWS_SECRETS', 'false').lower() in ('1', 'true', 'yes')
    
    @classmethod
    def validate(cls):
        """Validate that all required secrets are configured."""
        required_keys = [
            'X_BEARER_TOKEN', 'X_API_KEY', 'X_API_SECRET',
            'X_ACCESS_TOKEN', 'X_ACCESS_SECRET', 'OPENAI_API_KEY'
        ]
        missing = [key for key in required_keys if not getattr(cls, key)]
        if missing:
            from .logger import logger
            logger.error(f'Missing required secrets: {", ".join(missing)}')
            return False
        return True
