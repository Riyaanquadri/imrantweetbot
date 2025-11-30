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
    
    # ============ OAuth2 User Context Tokens ============
    # These are obtained via oauth_pkce.py + oauth_callback.py
    OAUTH2_USER_ACCESS_TOKEN = SecretsManager.get_secret('OAUTH2_USER_ACCESS_TOKEN')
    OAUTH2_USER_REFRESH_TOKEN = SecretsManager.get_secret('OAUTH2_USER_REFRESH_TOKEN')
    OAUTH2_TOKEN_EXPIRES_IN = int(SecretsManager.get_secret('OAUTH2_TOKEN_EXPIRES_IN', '7200'))
    OAUTH2_SCOPE = SecretsManager.get_secret('OAUTH2_SCOPE', 'tweet.read tweet.write users.read offline.access')

    # ============ LLM Provider Credentials ============
    LLM_PROVIDER = SecretsManager.get_secret('LLM_PROVIDER', 'openai')
    OPENAI_API_KEY = SecretsManager.get_secret('OPENAI_API_KEY')
    GROQ_API_KEY = SecretsManager.get_secret('GROQ_API_KEY')
    GROQ_MODEL = SecretsManager.get_secret('GROQ_MODEL', 'llama-3.3-70b-versatile')
    GROQ_BASE_URL = SecretsManager.get_secret('GROQ_BASE_URL', 'https://api.groq.com/openai/v1')
    LLM_TEMPERATURE = float(SecretsManager.get_secret('LLM_TEMPERATURE', '0.45'))
    LLM_MAX_TOKENS = int(SecretsManager.get_secret('LLM_MAX_TOKENS', '300'))
    ENABLE_RAG = SecretsManager.get_secret('ENABLE_RAG', 'false').lower() in ('1', 'true', 'yes')
    RAG_INDEX_PATH = SecretsManager.get_secret('RAG_INDEX_PATH', 'data/rag_index.pkl')
    RAG_TOP_K = int(SecretsManager.get_secret('RAG_TOP_K', '3'))
    AB_TEST_ENABLED = SecretsManager.get_secret('AB_TEST_ENABLED', 'false').lower() in ('1', 'true', 'yes')
    AB_VARIANTS = [
        variant.strip()
        for variant in SecretsManager.get_secret('AB_VARIANTS', '').split(',')
        if variant.strip()
    ]
    AB_DEFAULT_VARIANT = SecretsManager.get_secret(
        'AB_DEFAULT_VARIANT',
        AB_VARIANTS[0] if AB_VARIANTS else 'control'
    )

    _raw_variant_tones = SecretsManager.get_secret('AB_VARIANT_TONES', '')
    AB_VARIANT_TONES = {}
    for pair in _raw_variant_tones.split(','):
        if ':' not in pair:
            continue
        key, value = pair.split(':', 1)
        key = key.strip()
        value = value.strip()
        if key and value:
            AB_VARIANT_TONES[key] = value
    if AB_DEFAULT_VARIANT and AB_DEFAULT_VARIANT not in AB_VARIANT_TONES:
        AB_VARIANT_TONES[AB_DEFAULT_VARIANT] = 'concise'

    # ============ Bot Configuration ============
    BOT_HANDLE = SecretsManager.get_secret('BOT_HANDLE', 'bot')
    PROJECT_KEYWORDS = [
        k.strip() for k in SecretsManager.get_secret('PROJECT_KEYWORDS', '').split(',') 
        if k.strip()
    ]

    POST_INTERVAL_HOURS = int(SecretsManager.get_secret('POST_INTERVAL_HOURS', '3'))
    POST_INTERVAL_MINUTES = int(SecretsManager.get_secret('POST_INTERVAL_MINUTES', '0') or '0')
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
            'X_ACCESS_TOKEN', 'X_ACCESS_SECRET'
        ]
        
        # Check LLM provider-specific credentials
        if cls.LLM_PROVIDER == 'groq':
            required_keys.append('GROQ_API_KEY')
        else:
            required_keys.append('OPENAI_API_KEY')
        
        missing = [key for key in required_keys if not getattr(cls, key)]
        if missing:
            from .logger import logger
            logger.error(f'Missing required secrets: {", ".join(missing)}')
            return False
        return True
