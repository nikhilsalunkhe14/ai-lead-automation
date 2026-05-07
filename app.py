"""
AI Lead Automation - Main Application Entry Point
Production-ready Flask application with advanced AI memory system
"""

import os
from flask import Flask, send_from_directory
from flask_cors import CORS
from src.config.settings import settings
from src.models.database import init_database
from src.services.context_service import get_context_service
from src.utils.security_utils_fixed import security_headers
import logging

def create_app():
    """Create and configure Flask application"""
    app = Flask(__name__)
    
    # Configuration
    app.secret_key = settings.SECRET_KEY
    app.config.update({
        'SESSION_COOKIE_SECURE': settings.SECURITY_CONFIG.SESSION_COOKIE_SECURE,
        'SESSION_COOKIE_HTTPONLY': settings.SECURITY_CONFIG.SESSION_COOKIE_HTTPONLY,
        'SESSION_COOKIE_SAMESITE': settings.SECURITY_CONFIG.SESSION_COOKIE_SAMESITE,
        'PERMANENT_SESSION_LIFETIME': settings.SECURITY_CONFIG.SESSION_TIMEOUT
    })
    
    # Enable CORS
    CORS(app)
    
    # Configure logging
    if settings.LOG_FILE:
        logging.basicConfig(
            level=getattr(logging, settings.LOG_LEVEL),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(settings.LOG_FILE, maxBytes=settings.LOG_MAX_BYTES),
                logging.StreamHandler()
            ]
        )
    else:
        logging.basicConfig(
            level=getattr(logging, settings.LOG_LEVEL),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
    # Initialize database
    with app.app_context():
        if not init_database():
            raise RuntimeError("Failed to initialize database")
        
        # Initialize memory system
        memory_service = get_context_service()
        if not memory_service.memory_service.is_initialized():
            logging.warning("⚠️ Memory system initialization failed - continuing without AI memory")
        else:
            logging.info("🧠 Memory system initialized successfully")
    
    # Register blueprints
    from src.routes.admin_routes import admin_bp
    from src.routes.lead_routes import lead_bp
    from src.routes.memory_routes import memory_bp
    from src.routes.context_routes import context_bp
    
    app.register_blueprint(admin_bp)
    app.register_blueprint(lead_bp)
    app.register_blueprint(memory_bp)
    app.register_blueprint(context_bp)
    
    # Register utility routes
    @app.route('/api/csrf-token', methods=['GET'])
    def get_csrf_token():
        """Generate and return CSRF token"""
        from src.utils.security_utils_fixed import SecurityUtils
        token = SecurityUtils.generate_csrf_token()
        return {
            'csrf_token': token,
            'status': 'success'
        }
    
    @app.route('/api/health', methods=['GET'])
    def health_check():
        """Application health check"""
        from src.models.database import get_db
        db_status = get_db().health_check()
        
        # Check memory system
        memory_service = get_context_service()
        memory_status = memory_service.memory_service.is_initialized()
        
        overall_healthy = db_status and memory_status
        
        return {
            'status': 'healthy' if overall_healthy else 'unhealthy',
            'database': 'connected' if db_status else 'disconnected',
            'memory_system': 'active' if memory_status else 'inactive',
            'version': settings.APP_VERSION,
            'environment': 'production' if settings.is_production() else 'development'
        }
    
    @app.route('/api/test', methods=['GET'])
    def api_test():
        """API test endpoint"""
        from src.models.database import get_db
        return {
            'status': 'success',
            'message': 'API is working',
            'database': 'connected' if get_db().is_connected() else 'disconnected',
            'version': settings.APP_VERSION
        }
    
    # Frontend routes
    @app.route('/')
    def index():
        """Serve landing page"""
        return send_from_directory('landing', 'index.html')
    
    @app.route('/admin_login')
    def admin_login():
        """Serve admin login page"""
        return send_from_directory('.', 'admin_login.html')
    
    @app.route('/admin_dashboard')
    def admin_dashboard():
        """Serve admin dashboard page"""
        return send_from_directory('.', 'admin_dashboard.html')
    
    @app.route('/admin_management')
    def admin_management():
        """Serve admin management page"""
        return send_from_directory('.', 'admin_management.html')
    
    @app.route('/admin_register')
    def admin_register():
        """Serve admin registration page"""
        return send_from_directory('.', 'admin_register.html')
    
    @app.route('/memory_dashboard')
    def memory_dashboard():
        """Serve memory dashboard page"""
        return send_from_directory('templates/admin', 'memory_dashboard.html')
    
    @app.route('/context_dashboard')
    def context_dashboard():
        """Serve context dashboard page"""
        return send_from_directory('templates/admin', 'context_dashboard.html')
    
    @app.route('/analytics_dashboard')
    def analytics_dashboard():
        """Serve analytics dashboard page"""
        return send_from_directory('templates/admin', 'analytics_dashboard.html')
    
    # Apply security headers to all routes
    app.after_request(security_headers)
    
    return app

# Create application instance
app = create_app()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = settings.DEBUG and not settings.is_production()
    
    logging.info(f"🚀 Starting AI Lead Automation on port {port}")
    logging.info(f"🌍 Environment: {'Production' if settings.is_production() else 'Development'}")
    logging.info(f"🧠 Memory System: {'Active' if get_context_service().memory_service.is_initialized() else 'Inactive'}")
    
    app.run(host='0.0.0.0', port=port, debug=debug)
