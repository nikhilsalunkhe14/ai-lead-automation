"""
Configuration Management System
Professional environment-based configuration
"""

import os
from datetime import timedelta
from security_config import SecurityConfig

class Settings:
    """Main settings class for the application"""
    
    # Flask Configuration
    SECRET_KEY = os.getenv('FLASK_SECRET_KEY', 'your-secret-key-here-change-in-production')
    DEBUG = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    
    # MongoDB Configuration
    MONGODB_URI = os.getenv('MONGODB_URI', 'mongodb://localhost:27017/aileads')
    MONGODB_DB_NAME = 'aileads'
    MONGODB_TIMEOUT = 5000
    MONGODB_MAX_POOL_SIZE = 10
    MONGODB_MIN_POOL_SIZE = 2
    
    # Email Configuration
    RESEND_API_KEY = os.getenv('RESEND_API_KEY')
    EMAIL_FROM = os.getenv('EMAIL_FROM', 'noreply@aileads.com')
    EMAIL_FROM_NAME = os.getenv('EMAIL_FROM_NAME', 'AI Lead Automation')
    
    # AI Configuration
    GROQ_API_KEY = os.getenv('GROQ_API_KEY')
    GROQ_MODEL = os.getenv('GROQ_MODEL', 'llama3-70b-8192')
    
    # Embeddings Configuration
    EMBEDDINGS_MODEL_NAME = os.getenv('EMBEDDINGS_MODEL_NAME', 'all-MiniLM-L6-v2')
    EMBEDDINGS_DIMENSION = int(os.getenv('EMBEDDINGS_DIMENSION', '384'))
    
    # Memory Configuration
    MEMORY_DB_PATH = os.getenv('MEMORY_DB_PATH', './memory_db')
    MEMORY_MAX_RESULTS = int(os.getenv('MEMORY_MAX_RESULTS', '100'))
    MEMORY_SIMILARITY_THRESHOLD = float(os.getenv('MEMORY_SIMILARITY_THRESHOLD', '0.7'))
    MEMORY_MAX_CONTEXT_TOKENS = int(os.getenv('MEMORY_MAX_CONTEXT_TOKENS', '4000'))
    MEMORY_CONTEXT_WINDOW_HOURS = int(os.getenv('MEMORY_CONTEXT_WINDOW_HOURS', '168'))  # 1 week
    
    # Application Configuration
    APP_NAME = 'AI Lead Automation'
    APP_VERSION = '2.0.0'
    APP_DESCRIPTION = 'Professional AI-powered lead generation and management system'
    
    # Rate Limiting
    RATE_LIMIT_ENABLED = os.getenv('RATE_LIMIT_ENABLED', 'true').lower() == 'true'
    
    # File Upload Configuration
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
    UPLOAD_FOLDER = 'uploads'
    ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'}
    
    # Pagination
    DEFAULT_PAGE_SIZE = 20
    MAX_PAGE_SIZE = 100
    
    # Cache Configuration
    CACHE_TYPE = 'simple'
    CACHE_DEFAULT_TIMEOUT = 300
    
    # Logging Configuration
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FILE = os.getenv('LOG_FILE', None)
    LOG_MAX_BYTES = 10 * 1024 * 1024  # 10MB
    
    # Security Configuration (from SecurityConfig)
    SECURITY_CONFIG = SecurityConfig
    
    @classmethod
    def get_database_config(cls):
        """Get database configuration dictionary"""
        return {
            'uri': cls.MONGODB_URI,
            'db_name': cls.MONGODB_DB_NAME,
            'timeout': cls.MONGODB_TIMEOUT,
            'max_pool_size': cls.MONGODB_MAX_POOL_SIZE,
            'min_pool_size': cls.MONGODB_MIN_POOL_SIZE
        }
    
    @classmethod
    def get_email_config(cls):
        """Get email configuration dictionary"""
        return {
            'api_key': cls.RESEND_API_KEY,
            'from_email': cls.EMAIL_FROM,
            'from_name': cls.EMAIL_FROM_NAME
        }
    
    @classmethod
    def get_ai_config(cls):
        """Get AI configuration dictionary"""
        return {
            'api_key': cls.GROQ_API_KEY,
            'model': cls.GROQ_MODEL
        }
    
    @classmethod
    def is_production(cls):
        """Check if running in production"""
        return cls.SECURITY_CONFIG.IS_PRODUCTION
    
    @classmethod
    def is_development(cls):
        """Check if running in development"""
        return cls.SECURITY_CONFIG.IS_DEVELOPMENT

class EmbeddingsConfig:
    """Embeddings configuration"""
    MODEL_NAME = Settings.EMBEDDINGS_MODEL_NAME
    DIMENSION = Settings.EMBEDDINGS_DIMENSION

class MemoryConfig:
    """Memory system configuration"""
    VECTOR_DB_PATH = Settings.MEMORY_DB_PATH
    MAX_RESULTS = Settings.MEMORY_MAX_RESULTS
    SIMILARITY_THRESHOLD = Settings.MEMORY_SIMILARITY_THRESHOLD
    MAX_CONTEXT_TOKENS = Settings.MEMORY_MAX_CONTEXT_TOKENS
    CONTEXT_WINDOW_HOURS = Settings.MEMORY_CONTEXT_WINDOW_HOURS

class DevelopmentSettings(Settings):
    """Development environment settings"""
    DEBUG = True
    LOG_LEVEL = 'DEBUG'
    LOG_FILE = None

class ProductionSettings(Settings):
    """Production environment settings"""
    DEBUG = False
    LOG_LEVEL = 'INFO'
    LOG_FILE = 'app.log'

def get_settings():
    """Factory function to get appropriate settings class"""
    env = os.getenv('FLASK_ENV', 'development').lower()
    
    if env == 'production':
        return ProductionSettings
    else:
        return DevelopmentSettings

# Global settings instance
settings = get_settings()
