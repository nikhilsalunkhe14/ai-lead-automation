"""
Authentication Middleware
Handles authentication, authorization, and session management
"""

from functools import wraps
from flask import session, request, jsonify, redirect, url_for
from datetime import datetime, timedelta
import logging
import re

from config.security import SecurityConfig
from config.security import log_security_event

class AuthMiddleware:
    """Authentication middleware class"""
    
    @staticmethod
    def require_auth(f):
        """Decorator to require authentication"""
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Check if user is authenticated
            if not session.get('is_authenticated'):
                log_security_event('UNAUTHORIZED_ACCESS', {
                    'route': request.endpoint,
                    'method': request.method,
                    'path': request.path
                }, 'WARNING')
                
                if request.is_json:
                    return jsonify({
                        'status': 'error',
                        'message': 'Authentication required',
                        'code': 'AUTH_REQUIRED'
                    }), 401
                else:
                    return redirect(url_for('admin_login'))
            
            # Check session timeout
            last_activity = session.get('last_activity')
            if last_activity:
                last_activity = datetime.fromisoformat(last_activity)
                timeout = timedelta(minutes=SecurityConfig.SESSION_TIMEOUT)
                
                if datetime.utcnow() - last_activity > timeout:
                    session.clear()
                    log_security_event('SESSION_TIMEOUT', {
                        'user_id': session.get('admin_id'),
                        'username': session.get('admin_username'),
                        'session_age': str(datetime.utcnow() - last_activity)
                    }, 'WARNING')
                    
                    if request.is_json:
                        return jsonify({
                            'status': 'error',
                            'message': 'Session expired',
                            'code': 'SESSION_TIMEOUT'
                        }), 401
                    else:
                        return redirect(url_for('admin_login'))
            
            # Update last activity
            session['last_activity'] = datetime.utcnow().isoformat()
            
            return f(*args, **kwargs)
        
        return decorated_function
    
    @staticmethod
    def require_role(required_role):
        """Decorator to require specific role"""
        def decorator(f):
            @wraps(f)
            @AuthMiddleware.require_auth
            def decorated_function(*args, **kwargs):
                user_role = session.get('admin_role')
                
                if not user_role or user_role != required_role:
                    log_security_event('INSUFFICIENT_PERMISSIONS', {
                        'required_role': required_role,
                        'user_role': user_role,
                        'route': request.endpoint,
                        'method': request.method
                    }, 'WARNING')
                    
                    if request.is_json:
                        return jsonify({
                            'status': 'error',
                            'message': f'{required_role} role required',
                            'code': 'INSUFFICIENT_PERMISSIONS'
                        }), 403
                    else:
                        return redirect(url_for('admin_login'))
                
                return f(*args, **kwargs)
            
            return decorated_function
        return decorator
    
    @staticmethod
    def require_any_role(*allowed_roles):
        """Decorator to require any of the specified roles"""
        def decorator(f):
            @wraps(f)
            @AuthMiddleware.require_auth
            def decorated_function(*args, **kwargs):
                user_role = session.get('admin_role')
                
                if not user_role or user_role not in allowed_roles:
                    log_security_event('INSUFFICIENT_PERMISSIONS', {
                        'allowed_roles': list(allowed_roles),
                        'user_role': user_role,
                        'route': request.endpoint,
                        'method': request.method
                    }, 'WARNING')
                    
                    if request.is_json:
                        return jsonify({
                            'status': 'error',
                            'message': 'Insufficient permissions',
                            'code': 'INSUFFICIENT_PERMISSIONS'
                        }), 403
                    else:
                        return redirect(url_for('admin_login'))
                
                return f(*args, **kwargs)
            
            return decorated_function
        return decorator

class SessionManager:
    """Session management utilities"""
    
    @staticmethod
    def create_session(admin_data):
        """Create secure session for admin"""
        session.update({
            'admin_id': admin_data['id'],
            'admin_username': admin_data['username'],
            'admin_email': admin_data['email'],
            'admin_role': admin_data['role'],
            'is_authenticated': True,
            'last_activity': datetime.utcnow().isoformat(),
            'login_time': datetime.utcnow().isoformat(),
            'csrf_token': admin_data.get('csrf_token')
        })
        
        log_security_event('LOGIN_SUCCESS', {
            'admin_id': admin_data['id'],
            'username': admin_data['username'],
            'role': admin_data['role']
        })
    
    @staticmethod
    def destroy_session():
        """Destroy current session"""
        user_data = {
            'admin_id': session.get('admin_id'),
            'admin_username': session.get('admin_username'),
            'admin_role': session.get('admin_role'),
            'session_duration': str(datetime.utcnow() - datetime.fromisoformat(session.get('login_time', datetime.utcnow().isoformat())))
        }
        
        session.clear()
        
        log_security_event('LOGOUT', user_data)
    
    @staticmethod
    def is_valid_session():
        """Check if current session is valid"""
        if not session.get('is_authenticated'):
            return False
        
        # Check session timeout
        last_activity = session.get('last_activity')
        if last_activity:
            last_activity = datetime.fromisoformat(last_activity)
            timeout = timedelta(minutes=SecurityConfig.SESSION_TIMEOUT)
            
            if datetime.utcnow() - last_activity > timeout:
                return False
        
        return True
    
    @staticmethod
    def get_current_user():
        """Get current authenticated user data"""
        if not SessionManager.is_valid_session():
            return None
        
        return {
            'id': session.get('admin_id'),
            'username': session.get('admin_username'),
            'email': session.get('admin_email'),
            'role': session.get('admin_role'),
            'last_activity': session.get('last_activity')
        }

class SecurityHeaders:
    """Security headers middleware"""
    
    def __init__(self, app):
        self.app = app
        self.init_app(app)
    
    def init_app(self, app):
        """Initialize security headers"""
        @app.after_request
        def after_request(response):
            # Add security headers
            for header, value in SecurityConfig.SECURITY_HEADERS.items():
                if header not in ['Content-Security-Policy']:  # CSP handled by Talisman
                    response.headers[header] = value
            
            # Remove server information
            response.headers['Server'] = 'AI-Lead-Automation'
            response.headers['X-Powered-By'] = 'AI-Lead-Automation'
            
            # Add cache control for authenticated routes
            if request.path.startswith('/admin') or request.path.startswith('/api/admin'):
                response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
                response.headers['Pragma'] = 'no-cache'
                response.headers['Expires'] = '0'
            
            return response

class RequestValidator:
    """Request validation utilities"""
    
    @staticmethod
    def validate_json_request(required_fields=None, optional_fields=None):
        """Validate JSON request data"""
        try:
            data = request.get_json()
            if not data:
                return False, "Invalid JSON request", {}
            
            errors = {}
            
            # Check required fields
            if required_fields:
                for field in required_fields:
                    if field not in data or not data[field]:
                        errors[field] = f"{field} is required"
            
            # Validate field types and formats
            if 'email' in data:
                email_pattern = r'^[^\s@]+@[^\s@]+\.[^\s@]+$'
                if not re.match(email_pattern, data['email']):
                    errors['email'] = "Invalid email format"
            
            if 'password' in data:
                password = data['password']
                if len(password) < SecurityConfig.PASSWORD_MIN_LENGTH:
                    errors['password'] = f"Password must be at least {SecurityConfig.PASSWORD_MIN_LENGTH} characters"
            
            if 'username' in data:
                username = data['username']
                if len(username) < 3:
                    errors['username'] = "Username must be at least 3 characters"
                elif not re.match(r'^[a-zA-Z0-9_]+$', username):
                    errors['username'] = "Username can only contain letters, numbers, and underscores"
            
            return len(errors) == 0, errors, data
            
        except Exception as e:
            log_security_event('REQUEST_VALIDATION_ERROR', {
                'error': str(e),
                'path': request.path
            }, 'ERROR')
            return False, "Request validation failed", {}
    
    @staticmethod
    def sanitize_filename(filename):
        """Sanitize filename to prevent path traversal"""
        if not filename:
            return ""
        
        # Remove path separators
        filename = filename.replace('/', '').replace('\\', '').replace('..', '')
        
        # Remove dangerous characters
        import re
        filename = re.sub(r'[^\w\-_\.]', '', filename)
        
        return filename.strip()

# Rate limiting decorator for specific actions
def rate_limit_action(limit, scope):
    """Custom rate limiting decorator"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Get client identifier
            client_id = f"{get_client_ip()}:{scope}"
            
            # Check rate limit (simplified - in production use Redis)
            current_time = datetime.utcnow()
            window_start = current_time - timedelta(minutes=15)
            
            # This is a simplified version - use Flask-Limiter in production
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator
