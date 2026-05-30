#!/usr/bin/env python3
"""
AI Lead Automation - Flask Application Runner
Main entry point for the Flask application
"""

import os
import sys
from app import app, socketio

def main():
    """Main function to run the Flask application"""
    
    # Print startup banner
    print("=" * 60)
    print("🚀 AI Lead Automation - Flask Application")
    print("=" * 60)
    print("📊 Advanced AI-Powered CRM Platform")
    print("🔗 MongoDB Integration: Active")
    print("🤖 AI Services: Active")
    print("📧 Email Automation: Active")
    print("🔐 Security System: Active")
    print("=" * 60)
    
    # Check environment variables
    required_env_vars = [
        'FLASK_SECRET_KEY',
        'GROQ_API_KEY',
        'RESEND_API_KEY',
        'MONGODB_URI'
    ]
    
    missing_vars = []
    for var in required_env_vars:
        if not os.getenv(var) or os.getenv(var) == f'your_{var.lower()}_here':
            missing_vars.append(var)
    
    if missing_vars:
        print("⚠️  WARNING: Missing environment variables:")
        for var in missing_vars:
            print(f"   - {var}")
        print("\nPlease configure these variables in your .env file")
        print("=" * 60)
    
    # Run the Flask application
    # Use PORT environment variable for Render, default to 5000 for local
    port = int(os.getenv('PORT', 5000))
    host = os.getenv('HOST', '0.0.0.0')
    debug = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
    
    print(f"🌐 Starting Flask server on http://{host}:{port}")
    print(f"📱 Admin Dashboard: http://{host}:{port}/admin_dashboard")
    print(f"💬 Chat Interface: http://{host}:{port}/dashboard")
    print(f"🔐 Admin Login: http://{host}:{port}/admin_login")
    print("=" * 60)
    
    try:
        socketio.run(
            app,
            host=host,
            port=port,
            debug=debug,
            allow_unsafe_werkzeug=True,
        )
    except KeyboardInterrupt:
        print("\n👋 Shutting down Flask application...")
        sys.exit(0)
    except Exception as e:
        print(f"❌ Error starting Flask application: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
