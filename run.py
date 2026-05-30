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
    print("🌐 Starting Flask server on http://127.0.0.1:5000")
    print("📱 Admin Dashboard: http://127.0.0.1:5000/admin_dashboard")
    print("💬 Chat Interface: http://127.0.0.1:5000/dashboard")
    print("🔐 Admin Login: http://127.0.0.1:5000/admin_login")
    print("=" * 60)
    
    try:
        socketio.run(
            app,
            host='127.0.0.1',
            port=5000,
            debug=True,
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
