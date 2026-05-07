"""
Main Entry Point - Professional application startup
"""

import os
import sys
from src.app import create_app
from src.config.settings import settings

def main():
    """Main application entry point"""
    # Create Flask app
    app = create_app()
    
    # Print startup information
    print(f"🚀 Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    print(f"📊 Environment: {'Production' if settings.is_production() else 'Development'}")
    print(f"🔐 Security: {'Enabled' if settings.SECURITY_CONFIG.IS_PRODUCTION else 'Development Mode'}")
    
    # Get host and port
    host = os.getenv('HOST', '0.0.0.0')
    port = int(os.getenv('PORT', 5000))
    debug = settings.DEBUG
    
    print(f"🌐 Server: http://{host}:{port}")
    print("=" * 50)
    
    # Run application
    try:
        app.run(
            host=host,
            port=port,
            debug=debug
        )
    except KeyboardInterrupt:
        print("\n👋 Application stopped by user")
    except Exception as e:
        print(f"❌ Failed to start application: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
