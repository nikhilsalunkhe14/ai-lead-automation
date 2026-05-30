"""
Security Configuration Module
Handles all security-related configurations and utilities
"""

import os
from datetime import timedelta, datetime
import secrets
import re
from flask import request

class SecurityConfig:
    """Security configuration class"""
    
    # Environment-based settings
    FLASK_ENV = os.getenv('FLASK_ENV', 'development')
    IS_PRODUCTION = FLASK_ENV == 'production'
    
    # Session security
    SESSION_TIMEOUT = int(os.getenv('SESSION_TIMEOUT_MINUTES', '30'))  # minutes
    SESSION_COOKIE_SECURE = IS_PRODUCTION
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # Password policy
    PASSWORD_MIN_LENGTH = int(os.getenv('PASSWORD_MIN_LENGTH', '8'))
    PASSWORD_REQUIRE_UPPER = os.getenv('PASSWORD_REQUIRE_UPPER', 'true').lower() == 'true'
    PASSWORD_REQUIRE_LOWER = os.getenv('PASSWORD_REQUIRE_LOWER', 'true').lower() == 'true'
    PASSWORD_REQUIRE_NUMBER = os.getenv('PASSWORD_REQUIRE_NUMBER', 'true').lower() == 'true'
    PASSWORD_REQUIRE_SPECIAL = os.getenv('PASSWORD_REQUIRE_SPECIAL', 'true').lower() == 'true'
    
    # Rate limiting
    LOGIN_RATE_LIMIT = os.getenv('LOGIN_RATE_LIMIT', '5 per 15 minutes')
    API_RATE_LIMIT = os.getenv('API_RATE_LIMIT', '100 per hour')
    CHAT_RATE_LIMIT = os.getenv('CHAT_RATE_LIMIT', '10 per minute')
    
    # Security headers
    SECURITY_HEADERS = {
        'X-Frame-Options': 'DENY',
        'X-Content-Type-Options': 'nosniff',
        'X-XSS-Protection': '1; mode=block',
        'Referrer-Policy': 'strict-origin-when-cross-origin',
        'Content-Security-Policy': (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com https://cdnjs.cloudflare.com; "
            "style-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com https://cdnjs.cloudflare.com; "
            "img-src 'self' data: https:; "
            "font-src 'self' https://cdnjs.cloudflare.com; "
            "connect-src 'self'"
        )
    }
    
    # CSRF settings
    WTF_CSRF_ENABLED = IS_PRODUCTION
    WTF_CSRF_TIME_LIMIT = timedelta(hours=1)
    
    # Admin route protection
    ADMIN_ROUTES = [
        '/admin_dashboard',
        '/admin_management',
        '/admin_register',
        '/api/admin/',
        '/api/leads',
        '/api/lead/',
        '/api/chat',
        '/api/summary',
        '/api/db-status'
    ]

class PasswordValidator:
    """Password validation utility"""
    
    @staticmethod
    def validate_password(password):
        """
        Validate password against security policy
        Returns: (is_valid, error_message)
        """
        config = SecurityConfig()
        
        errors = []
        
        # Length check
        if len(password) < config.PASSWORD_MIN_LENGTH:
            errors.append(f"Password must be at least {config.PASSWORD_MIN_LENGTH} characters")
        
        # Character requirements
        if config.PASSWORD_REQUIRE_UPPER and not re.search(r'[A-Z]', password):
            errors.append("Password must contain at least one uppercase letter")
        
        if config.PASSWORD_REQUIRE_LOWER and not re.search(r'[a-z]', password):
            errors.append("Password must contain at least one lowercase letter")
        
        if config.PASSWORD_REQUIRE_NUMBER and not re.search(r'\d', password):
            errors.append("Password must contain at least one number")
        
        if config.PASSWORD_REQUIRE_SPECIAL and not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            errors.append("Password must contain at least one special character")
        
        # Common password patterns
        common_patterns = [
            r'123', r'password', r'admin', r'qwerty', 
            r'abc', r'111', r'000'
        ]
        
        for pattern in common_patterns:
            if re.search(pattern, password, re.IGNORECASE):
                errors.append("Password is too common or weak")
                break
        
        return (len(errors) == 0, errors[0] if errors else None)

class SecurityUtils:
    """Security utility functions"""
    
    @staticmethod
    def generate_secure_token():
        """Generate cryptographically secure token"""
        return secrets.token_urlsafe(32)
    
    @staticmethod
    def is_safe_url(url):
        """Check if URL is safe for redirect"""
        if not url:
            return False
        
        # Allow only relative URLs or same origin
        if url.startswith('/') or url.startswith(window.location.origin):
            return True
        
        return False
    
    @staticmethod
    def sanitize_input(input_string):
        """Sanitize user input to prevent XSS"""
        if not input_string:
            return ""
        
        # Basic XSS prevention
        dangerous_chars = ['<', '>', '"', "'", '&', 'javascript:', 'onerror=', 'onload=']
        sanitized = input_string
        
        for char in dangerous_chars:
            sanitized = sanitized.replace(char, '')
        
        return sanitized.strip()

def init_security(app):
    """Initialize security features for Flask app"""
    
    # Configure security headers manually
    @app.after_request
    def after_request(response):
        # Add security headers
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        
        # Remove server information
        response.headers['Server'] = 'AI-Lead-Automation'
        response.headers['X-Powered-By'] = 'AI-Lead-Automation'
        
        # Add cache control for authenticated routes
        if request.path.startswith('/admin') or request.path.startswith('/api/admin'):
            response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
        
        return response
    
    return None  # No limiter for now
    
    # Configure session security
    app.config.update({
        'SESSION_COOKIE_SECURE': SecurityConfig.SESSION_COOKIE_SECURE,
        'SESSION_COOKIE_HTTPONLY': SecurityConfig.SESSION_COOKIE_HTTPONLY,
        'SESSION_COOKIE_SAMESITE': SecurityConfig.SESSION_COOKIE_SAMESITE,
        'PERMANENT_SESSION_LIFETIME': timedelta(minutes=SecurityConfig.SESSION_TIMEOUT),
        'SECRET_KEY': os.getenv('FLASK_SECRET_KEY', SecurityUtils.generate_secure_token()),
        'WTF_CSRF_ENABLED': SecurityConfig.WTF_CSRF_ENABLED,
        'WTF_CSRF_TIME_LIMIT': SecurityConfig.WTF_CSRF_TIME_LIMIT
    })
    
    return talisman, limiter

def get_client_ip():
    """Get real client IP address"""
    if request.headers.getlist("X-Forwarded-For"):
        return request.headers.getlist("X-Forwarded-For")[0]
    elif request.headers.get("X-Real-IP"):
        return request.headers.get("X-Real-IP")
    else:
        return request.remote_addr

def log_security_event(event_type, details, severity='INFO'):
    """Log security events"""
    import logging
    
    security_logger = logging.getLogger('security')
    security_logger.setLevel(logging.INFO if severity == 'INFO' else logging.WARNING)
    
    log_entry = {
        'timestamp': datetime.utcnow().isoformat(),
        'event_type': event_type,
        'details': details,
        'ip_address': get_client_ip(),
        'user_agent': request.headers.get('User-Agent', 'Unknown'),
        'severity': severity
    }
    
    if SecurityConfig.IS_PRODUCTION:
        # In production, log to file or external service
        security_logger.warning(f"Security Event: {log_entry}")
    else:
        # In development, print to console
        print(f"🔒 Security Event [{severity}]: {log_entry}")
