from flask import Flask, jsonify, request, render_template, send_from_directory, session
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_socketio import SocketIO, emit, join_room, leave_room, rooms
from dotenv import load_dotenv
from groq import Groq
import resend
import os
import json
import re
import webbrowser
import threading
import time
import bcrypt
import logging
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from bson.objectid import ObjectId
from datetime import datetime, timezone, timedelta
from dateutil import parser
import traceback
import secrets

# Import security modules
from config.security import SecurityConfig, PasswordValidator, SecurityUtils, init_security, log_security_event
from middleware.auth import AuthMiddleware, SessionManager, RequestValidator

# Load environment variables
load_dotenv()

# Create Flask app
app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'your-secret-key-here-change-in-production')

# Enable CORS for all routes
CORS(app)

# Initialize SocketIO for real-time communication
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Initialize security features
security_headers = init_security(app)

# Initialize Groq client
try:
    api_key = os.getenv('GROQ_API_KEY')
    if api_key and api_key != 'your_groq_api_key_here':
        # Try to initialize Groq client with different approaches
        try:
            # Try standard initialization
            client = Groq(api_key=api_key)
            print(f"✅ Groq client initialized successfully")
        except Exception as init_error:
            # If standard fails, try without any additional parameters
            print(f"⚠️ Standard Groq init failed: {init_error}")
            try:
                import importlib
                groq_module = importlib.import_module('groq')
                # Try creating client with minimal parameters
                client = groq_module.Groq(api_key=api_key)
                print(f"✅ Groq client initialized with minimal config")
            except Exception as minimal_error:
                print(f"⚠️ Minimal Groq init failed: {minimal_error}")
                client = None
    else:
        print("⚠️ Warning: GROQ_API_KEY not configured properly")
        client = None
except Exception as e:
    print(f"⚠️ Warning: Could not initialize Groq client: {e}")
    client = None

# Initialize Resend client
resend.api_key = os.getenv('RESEND_API_KEY')

# ================================
# MONGODB CONNECTION SETUP
# ================================

# MongoDB connection variables
mongodb_uri = os.getenv('MONGODB_URI')
db_client = None
mongo_database = None

def connect_to_mongodb():
    """
    Establish connection to MongoDB Atlas
    Returns: MongoDB client and database objects
    """
    global db_client, mongo_database
    
    try:
        # Check if MongoDB URI is configured
        if not mongodb_uri or mongodb_uri == 'mongodb+srv://username:password@cluster.mongodb.net/?retryWrites=true&w=majority':
            print("❌ MongoDB URI not configured in .env file")
            print("Please update MONGODB_URI with your actual MongoDB Atlas connection string")
            return None, None
        
        print("🔗 Connecting to MongoDB Atlas...")
        
        # Create MongoDB client with connection timeout
        db_client = MongoClient(
            mongodb_uri,
            serverSelectionTimeoutMS=5000,  # 5 second timeout
            connectTimeoutMS=5000,
            socketTimeoutMS=5000
        )
        
        # Test the connection
        db_client.admin.command('ping')
        
        # Get database (will create if it doesn't exist)
        mongo_database = db_client.aileads
        
        print("✅ Successfully connected to MongoDB Atlas")
        print(f"📊 Database: {mongo_database.name}")
        
        # Create collections with indexes for better performance
        create_collections_and_indexes()
        
        return db_client, mongo_database
        
    except ConnectionFailure as e:
        print(f"❌ MongoDB Connection Failure: {e}")
        print("Please check your MongoDB URI and network connection")
        return None, None
    except ServerSelectionTimeoutError as e:
        print(f"❌ MongoDB Server Timeout: {e}")
        print("Server is taking too long to respond")
        return None, None
    except Exception as e:
        print(f"❌ MongoDB Connection Error: {e}")
        return None, None

def create_collections_and_indexes():
    """
    Create collections and set up indexes for optimal performance
    """
    try:
        # Create leads collection with indexes
        leads_collection = mongo_database.leads
        leads_collection.create_index("email")
        leads_collection.create_index("timestamp")
        leads_collection.create_index("name")
        
        # Create chat_history collection with indexes
        chat_collection = mongo_database.chat_history
        chat_collection.create_index([("email", 1), ("timestamp", -1)])
        chat_collection.create_index("session_id")
        
        # Create summaries collection with indexes
        summaries_collection = mongo_database.summaries
        summaries_collection.create_index("email")
        summaries_collection.create_index("timestamp")
        summaries_collection.create_index("status")
        
        # Create admin collection with indexes
        admin_collection = mongo_database.admins
        admin_collection.create_index("username", unique=True)
        admin_collection.create_index("email", unique=True)
        admin_collection.create_index("created_at")

        # Messages collection for admin-client chat
        messages_collection = mongo_database.messages
        messages_collection.create_index([("lead_id", 1), ("timestamp", 1)])

        # Client accounts (password + optional OTP login)
        clients_collection = mongo_database.clients
        clients_collection.create_index("email", unique=True)
        clients_collection.create_index("primary_lead_id")
        clients_collection.create_index("created_at")
        
        print("📋 Collections and indexes created successfully")
        
    except Exception as e:
        print(f"⚠️ Warning: Could not create indexes: {e}")

def get_collection(collection_name):
    """
    Get a MongoDB collection with error handling
    """
    try:
        if mongo_database is None:
            print("❌ Database not connected")
            return None
        return mongo_database[collection_name]
    except Exception as e:
        print(f"❌ Error getting collection {collection_name}: {e}")
        return None


def get_public_base_url():
    """Base URL for links in emails (set PUBLIC_BASE_URL in .env for production)."""
    base = os.getenv('PUBLIC_BASE_URL', '').strip()
    if base:
        return base.rstrip('/')
    return request.host_url.rstrip('/') if request else 'http://127.0.0.1:5000'


def find_lead_by_identifier(lead_id_str):
    """Find a lead by MongoDB ObjectId string."""
    leads_collection = get_collection('leads')
    if leads_collection is None or not lead_id_str:
        return None, None
    lead_id_str = str(lead_id_str).strip()
    try:
        oid = ObjectId(lead_id_str)
        lead = leads_collection.find_one({'_id': oid})
        if lead:
            return lead, oid
    except Exception as e:
        print(f"⚠️ Invalid lead id '{lead_id_str}': {e}")
    return None, None


def find_lead_by_email(email):
    """Find the most recent lead for an email address."""
    leads_collection = get_collection('leads')
    if leads_collection is None or not email:
        return None, None
    email = email.strip().lower()
    lead = leads_collection.find_one(
        {'email': {'$regex': f'^{re.escape(email)}$', '$options': 'i'}},
        sort=[('timestamp', -1)]
    )
    if lead:
        return lead, lead['_id']
    return None, None


def normalize_change_request(change_request):
    """Unify change_request.changes and change_request.requested_changes."""
    if not change_request:
        return None
    changes = (change_request.get('changes') or change_request.get('requested_changes') or '').strip()
    budget = (change_request.get('budget_changes') or '').strip()
    normalized = dict(change_request)
    normalized['changes'] = changes
    normalized['requested_changes'] = changes
    normalized['budget_changes'] = budget
    requested_at = change_request.get('requested_at')
    if requested_at is not None and hasattr(requested_at, 'isoformat'):
        normalized['requested_at'] = requested_at.isoformat()
    return normalized


def emit_new_change_request_to_admins(lead):
    """Push change request to all admins on the dashboard (real-time)."""
    lead_id = str(lead['_id'])
    cr = normalize_change_request(lead.get('change_request')) or {}
    payload = {
        'lead_id': lead_id,
        'client_name': lead.get('name'),
        'client_email': lead.get('email'),
        'requested_changes': cr.get('changes', ''),
        'budget_changes': cr.get('budget_changes', ''),
        'timestamp': datetime.now(timezone.utc).isoformat(),
    }
    socketio.emit('new_change_request', payload, room='admin_dashboard')
    socketio.emit('new_change_request_realtime', payload, room='admin_dashboard')


def normalize_email(email):
    return (email or '').strip().lower()


def find_client_by_email(email):
    clients_collection = get_collection('clients')
    if clients_collection is None:
        return None
    return clients_collection.find_one({'email': normalize_email(email)})


def _bind_client_session_from_lead(lead, lead_oid, client_doc=None):
    """Set Flask session for an authenticated client linked to a lead."""
    display_name = (
        (client_doc.get('name') if client_doc else None)
        or lead.get('name')
        or 'Client'
    ).strip()
    client_session_id = secrets.token_urlsafe(32)

    leads_collection = get_collection('leads')
    if leads_collection is not None:
        leads_collection.update_one(
            {'_id': lead_oid},
            {'$set': {
                'name': display_name,
                'last_session': datetime.now(timezone.utc),
                'client_session_id': client_session_id,
            }},
        )

    session['client_email'] = lead.get('email', client_doc.get('email') if client_doc else '')
    session['client_name'] = display_name
    session['client_lead_id'] = str(lead_oid)
    session['client_session_id'] = client_session_id
    session['client_authenticated'] = True
    if client_doc:
        session['client_id'] = str(client_doc['_id'])
    else:
        session.pop('client_id', None)


def _client_auth_response(lead):
    email = lead.get('email') or session.get('client_email')
    return jsonify({
        'status': 'success',
        'message': 'Authenticated',
        'email': email,
        'name': session.get('client_name'),
        'lead_id': session.get('client_lead_id'),
        'redirect': f"/client_chat?email={email}&lead_id={session.get('client_lead_id')}",
    }), 200


def send_client_otp_email(email, name, otp_code):
    """Email a one-time login code to the client."""
    try:
        base = os.getenv('PUBLIC_BASE_URL', 'http://127.0.0.1:5000').rstrip('/')
        html = f"""
        <div style="font-family:Arial,sans-serif;max-width:520px;margin:0 auto;padding:24px;">
            <h2>Your login code</h2>
            <p>Hello <strong>{name or 'there'}</strong>,</p>
            <p>Use this code to sign in to your project portal (valid 10 minutes):</p>
            <p style="font-size:32px;font-weight:bold;letter-spacing:8px;color:#4f46e5;">{otp_code}</p>
            <p><a href="{base}/client_login">Open client portal</a></p>
        </div>
        """
        send_email_via_python_smtp(email, 'Your AI Lead Automation login code', html)
        return True
    except Exception as e:
        print(f"❌ OTP email failed: {e}")
        return False


def build_unified_conversation_timeline(email, lead_oid):
    """Merge AI requirement chat + admin/client messages, sorted by time."""
    timeline = []
    email_norm = normalize_email(email)

    chat_collection = get_collection('chat_history')
    if chat_collection is not None:
        for row in chat_collection.find(
            {'email': {'$regex': f'^{re.escape(email_norm)}$', '$options': 'i'}},
        ).sort('timestamp', 1):
            role = row.get('role', 'user')
            if role == 'assistant':
                text = (row.get('ai_reply') or row.get('message') or '').strip()
                sender = 'ai'
            else:
                text = (row.get('message') or '').strip()
                sender = 'client'
            if not text:
                continue
            ts = row.get('timestamp')
            timeline.append({
                'type': 'ai',
                'sender': sender,
                'sender_name': 'AI Assistant' if sender == 'ai' else (row.get('name') or 'You'),
                'message': text,
                'timestamp': ts.isoformat() if ts and hasattr(ts, 'isoformat') else None,
                '_sort': ts or datetime(1970, 1, 1, tzinfo=timezone.utc),
            })

    messages_collection = get_collection('messages')
    if messages_collection is not None and lead_oid:
        for msg in messages_collection.find({'lead_id': lead_oid}).sort('timestamp', 1):
            ts = msg.get('timestamp')
            timeline.append({
                'type': 'support',
                'sender': msg.get('sender_type', 'admin'),
                'sender_name': msg.get('sender_name') or ('Admin' if msg.get('sender_type') == 'admin' else 'You'),
                'message': msg.get('message', ''),
                'timestamp': ts.isoformat() if ts and hasattr(ts, 'isoformat') else None,
                '_sort': ts or datetime(1970, 1, 1, tzinfo=timezone.utc),
            })

    timeline.sort(key=lambda x: x['_sort'])
    for item in timeline:
        item.pop('_sort', None)
    return timeline


# Initialize MongoDB connection on startup
db_client, mongo_database = connect_to_mongodb()

# ================================
# EMAIL FUNCTIONALITY (Unchanged)
# ================================

def send_email_to_user(name, email, ai_reply):
    """
    Send professional email to user with AI-generated response
    
    Args:
        name (str): User's name
        email (str): User's email address
        ai_reply (str): AI-generated response content
    
    Returns:
        tuple: (success: bool, message: str)
    """
    try:
        # Check if Resend API key is configured
        api_key = os.getenv('RESEND_API_KEY')
        if not api_key or api_key == 'your_resend_api_key_here':
            print("Resend API key not configured properly")
            return False, "Email service not configured"
        
        # Create professional HTML email template
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>AI Lead Automation - Your Project Analysis</title>
            <style>
                * {{
                    margin: 0;
                    padding: 0;
                    box-sizing: border-box;
                }}
                body {{
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    line-height: 1.6;
                    color: #1e293b;
                    max-width: 650px;
                    margin: 0 auto;
                    padding: 20px;
                    background-color: #f8fafc;
                }}
                .email-container {{
                    background: white;
                    border-radius: 12px;
                    overflow: hidden;
                    box-shadow: 0 10px 25px rgba(0, 0, 0, 0.1);
                    margin: 20px 0;
                }}
                .header {{
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    padding: 40px 30px;
                    text-align: center;
                    position: relative;
                }}
                .header::before {{
                    content: '';
                    position: absolute;
                    top: 0;
                    left: 0;
                    right: 0;
                    bottom: 0;
                    background: url('data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><defs><pattern id="grain" width="100" height="100" patternUnits="userSpaceOnUse"><circle cx="25" cy="25" r="1" fill="white" opacity="0.1"/><circle cx="75" cy="75" r="1" fill="white" opacity="0.1"/><circle cx="50" cy="10" r="0.5" fill="white" opacity="0.15"/><circle cx="10" cy="50" r="0.5" fill="white" opacity="0.15"/><circle cx="90" cy="30" r="0.5" fill="white" opacity="0.15"/></pattern></defs><rect width="100" height="100" fill="url(%23grain)"/></svg>');
                    opacity: 0.3;
                }}
                .header-content {{
                    position: relative;
                    z-index: 1;
                }}
                .header h1 {{
                    font-size: 32px;
                    font-weight: 700;
                    margin-bottom: 10px;
                    text-shadow: 0 2px 4px rgba(0,0,0,0.1);
                }}
                .header .subtitle {{
                    font-size: 16px;
                    opacity: 0.9;
                    font-weight: 400;
                }}
                .content {{
                    padding: 40px 30px;
                }}
                .greeting {{
                    font-size: 24px;
                    font-weight: 600;
                    color: #1e293b;
                    margin-bottom: 15px;
                    border-left: 4px solid #667eea;
                    padding-left: 15px;
                }}
                .intro-text {{
                    color: #475569;
                    font-size: 16px;
                    margin-bottom: 25px;
                    line-height: 1.7;
                }}
                .customer-info {{
                    background: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%);
                    border-radius: 8px;
                    padding: 20px;
                    margin-bottom: 25px;
                    border: 1px solid #e2e8f0;
                }}
                .customer-info h3 {{
                    color: #334155;
                    font-size: 14px;
                    font-weight: 600;
                    margin-bottom: 10px;
                    text-transform: uppercase;
                    letter-spacing: 0.5px;
                }}
                .customer-details {{
                    display: flex;
                    gap: 20px;
                    flex-wrap: wrap;
                }}
                .customer-detail {{
                    flex: 1;
                    min-width: 200px;
                }}
                .customer-detail strong {{
                    color: #1e293b;
                    display: block;
                    font-size: 12px;
                    text-transform: uppercase;
                    letter-spacing: 0.5px;
                    margin-bottom: 4px;
                }}
                .customer-detail span {{
                    color: #475569;
                    font-size: 14px;
                }}
                .ai-response {{
                    background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%);
                    border: 1px solid #0ea5e9;
                    border-radius: 8px;
                    padding: 25px;
                    margin: 25px 0;
                    position: relative;
                }}
                .ai-response::before {{
                    content: '🤖';
                    position: absolute;
                    top: -15px;
                    left: 20px;
                    background: #0ea5e9;
                    color: white;
                    width: 30px;
                    height: 30px;
                    border-radius: 50%;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    font-size: 14px;
                }}
                .ai-label {{
                    color: #0369a1;
                    font-weight: 600;
                    margin-bottom: 15px;
                    font-size: 14px;
                    text-transform: uppercase;
                    letter-spacing: 0.5px;
                }}
                .ai-content {{
                    color: #0c4a6e;
                    font-size: 15px;
                    line-height: 1.8;
                    white-space: pre-wrap;
                }}
                .next-steps {{
                    background: #fef3c7;
                    border: 1px solid #f59e0b;
                    border-radius: 8px;
                    padding: 20px;
                    margin: 25px 0;
                }}
                .next-steps h3 {{
                    color: #92400e;
                    font-size: 16px;
                    margin-bottom: 10px;
                    display: flex;
                    align-items: center;
                    gap: 8px;
                }}
                .next-steps ul {{
                    color: #78350f;
                    margin-left: 20px;
                    font-size: 14px;
                }}
                .next-steps li {{
                    margin-bottom: 5px;
                }}
                .cta-section {{
                    text-align: center;
                    margin: 30px 0;
                }}
                .cta-button {{
                    display: inline-block;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    padding: 15px 30px;
                    text-decoration: none;
                    border-radius: 8px;
                    font-weight: 600;
                    font-size: 16px;
                    box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
                    transition: all 0.3s ease;
                }}
                .cta-button:hover {{
                    transform: translateY(-2px);
                    box-shadow: 0 6px 20px rgba(102, 126, 234, 0.4);
                }}
                .footer {{
                    background: #f8fafc;
                    text-align: center;
                    padding: 30px;
                    border-top: 1px solid #e2e8f0;
                    color: #64748b;
                    font-size: 13px;
                }}
                .footer strong {{
                    color: #334155;
                    display: block;
                    margin-bottom: 5px;
                }}
                .footer .divider {{
                    width: 50px;
                    height: 2px;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    margin: 15px auto;
                    border-radius: 1px;
                }}
                .timestamp {{
                    background: #f1f5f9;
                    color: #64748b;
                    padding: 8px 12px;
                    border-radius: 4px;
                    font-size: 12px;
                    text-align: center;
                    margin-bottom: 20px;
                }}
            </style>
        </head>
        <body>
            <div class="email-container">
                <div class="header">
                    <div class="header-content">
                        <h1>🚀 AI Lead Automation</h1>
                        <p class="subtitle">Intelligent Project Requirements Analysis</p>
                    </div>
                </div>
                
                <div class="content">
                    <div class="greeting">
                        Hello {name},
                    </div>
                    
                    <p class="intro-text">
                        Thank you for reaching out! Our AI assistant has carefully analyzed your project requirements and prepared a comprehensive analysis for your review.
                    </p>
                    
                    <div class="customer-info">
                        <h3>Client Information</h3>
                        <div class="customer-details">
                            <div class="customer-detail">
                                <strong>Name</strong>
                                <span>{name}</span>
                            </div>
                            <div class="customer-detail">
                                <strong>Email</strong>
                                <span>{email}</span>
                            </div>
                        </div>
                    </div>
                    
                    <div class="ai-response">
                        <div class="ai-label">📋 AI Analysis Report</div>
                        <div class="ai-content">{ai_reply}</div>
                    </div>
                    
                    <div class="next-steps">
                        <h3>🎯 What Happens Next?</h3>
                        <ul>
                            <li>Our team will review your requirements within 24 hours</li>
                            <li>You'll receive a detailed project proposal and timeline</li>
                            <li>Schedule a free consultation call to discuss further</li>
                        </ul>
                    </div>
                    
                    <div class="timestamp">
                        Generated on {time.strftime('%B %d, %Y at %I:%M %p')}
                    </div>
                    
                    <div class="cta-section">
                        <a href="http://127.0.0.1:5000" class="cta-button">
                            Start New Project Analysis
                        </a>
                    </div>
                </div>
                
                <div class="footer">
                    <strong>AI Lead Automation System</strong>
                    <div class="divider"></div>
                    <p>Transforming ideas into actionable project requirements</p>
                    <p>This is an automated message. Replies to this email are monitored.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        # Send email using Resend
        # For testing, we'll send to the verified email address
        # In production, you'll need to verify your domain at resend.com/domains
        verified_email = "nikhilsalunkhe9404@gmail.com"  # Your verified Resend email
        
        params = {
            "from": "AI Lead Automation <onboarding@resend.dev>",  # Use Resend's test domain
            "to": [verified_email],  # Send to verified email for testing
            "subject": f"Project Analysis for {name} ({email}) - AI Lead Automation",
            "html": html_content,
        }
        
        print(f"📧 SENDING EMAIL TO: {verified_email} (Original customer: {email})")
        print(f"📧 FROM: AI Lead Automation <onboarding@resend.dev>")
        print(f"📧 SUBJECT: Project Analysis for {name} ({email}) - AI Lead Automation")
        print(f"📧 EMAIL CONTENT PREVIEW: {html_content[:200]}...")
        
        result = resend.Emails.send(params)
        
        if result.get("id"):
            print(f"Email sent successfully to {verified_email}. Message ID: {result['id']}")
            return True, f"Email sent successfully to {verified_email}"
        else:
            print(f"Email sending failed: {result}")
            return False, "Email sending failed"
            
    except Exception as e:
        error_msg = str(e)
        print(f"Email sending error: {error_msg}")
        return False, f"Email error: {error_msg}"

def send_email_via_python_smtp(to_email, subject, html_content):
    """
    Send email using Python's built-in SMTP (Gmail alternative)
    
    Args:
        to_email (str): Recipient email
        subject (str): Email subject
        html_content (str): HTML email content
    
    Returns:
        tuple: (success: bool, message: str)
    """
    try:
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        
        # Create message
        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = os.getenv('EMAIL_FROM', 'onboarding@resend.dev')
        message["To"] = to_email
        
        # Add HTML content
        html_part = MIMEText(html_content, "html")
        message.attach(html_part)
        
        # Configure Gmail SMTP (you can use any SMTP service)
        smtp_server = "smtp.gmail.com"
        smtp_port = 587
        smtp_username = os.getenv('SMTP_USERNAME', 'your_email@gmail.com')
        smtp_password = os.getenv('SMTP_PASSWORD', 'your_app_password')
        
        print(f"📧 SENDING EMAIL TO: {to_email}")
        print(f"📧 SUBJECT: {subject}")
        print(f"📧 CONTENT LENGTH: {len(html_content)} characters")
        
        try:
            # Create SMTP session
            server = smtplib.SMTP(smtp_server, smtp_port)
            server.starttls()  # Secure the connection
            server.login(smtp_username, smtp_password)
            
            # Send email
            text = message.as_string()
            server.sendmail(smtp_username, to_email, text)
            server.quit()
            
            print(f"✅ Email sent successfully to {to_email}")
            return True, f"Email sent successfully to {to_email}"
            
        except Exception as smtp_error:
            print(f"❌ SMTP Error: {smtp_error}")
            # Fallback to simulation if SMTP fails
            return True, f"Email simulated (SMTP not configured): {to_email}"
        
    except Exception as e:
        error_msg = str(e)
        print(f"❌ SMTP email error: {error_msg}")
        return False, f"SMTP email error: {error_msg}"

def send_final_confirmation_to_client(client_email, client_name, project_details, cost_estimate):
    """
    Send final confirmation email to client after both client and admin have confirmed
    
    Args:
        client_email (str): Client's email address
        client_name (str): Client's name
        project_details (str): Project requirements and details
        cost_estimate (str): Project cost breakdown
    
    Returns:
        tuple: (success: bool, message: str)
    """
    try:
        # Process project details for HTML display
        import re
        processed_details = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', project_details)
        processed_details = processed_details.replace('•', '•')
        processed_details = processed_details.replace('\n', '<br>')
        processed_details = re.sub(r'^\s+|\s+$', '', processed_details, flags=re.MULTILINE)
        
        # Process cost estimate for HTML display
        processed_cost = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', cost_estimate)
        processed_cost = processed_cost.replace('•', '•')
        processed_cost = processed_cost.replace('\n', '<br>')
        processed_cost = re.sub(r'^\s+|\s+$', '', processed_cost, flags=re.MULTILINE)
        
        # Create HTML email content
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Project Confirmed - {client_name}</title>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 700px; margin: 0 auto; padding: 20px; background: #f8f9fa; border-radius: 10px; }}
                .header {{ text-align: center; background: #10b981; color: white; padding: 30px; border-radius: 10px 10px 0 0; }}
                .content {{ background: white; padding: 30px; border-radius: 0 0 10px 10px; }}
                .project-details {{ background: #f8f9fa; padding: 20px; border-radius: 5px; margin: 20px 0; white-space: pre-wrap; }}
                .cost-estimate {{ background: #e8f5e8; padding: 20px; border-radius: 5px; margin: 20px 0; white-space: pre-wrap; }}
                .footer {{ text-align: center; margin-top: 30px; color: #666; }}
                .highlight {{ background: #d1fae5; padding: 15px; border-left: 4px solid #10b981; margin: 20px 0; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>✅ Project Confirmed!</h1>
                    <h2>AI Lead Automation - Final Approval</h2>
                </div>
                <div class="content">
                    <div class="highlight">
                        <h3>🎉 Congratulations, {client_name}!</h3>
                        <p>Your project has been officially confirmed and approved by both you and our team. We're excited to start working on your project!</p>
                    </div>
                    
                    <div class="project-details">
                        <h3>📝 Project Details</h3>
                        <div>{processed_details}</div>
                    </div>
                    
                    <div class="cost-estimate">
                        <h3>💰 Cost Estimate</h3>
                        <div>{processed_cost}</div>
                    </div>
                    
                    <div class="footer">
                        <p><strong>What's Next:</strong></p>
                        <p>1. Our team will begin project planning and design</p>
                        <p>2. You'll receive regular updates on progress</p>
                        <p>3. We'll schedule milestone reviews with you</p>
                        <p>4. Final delivery and deployment</p>
                        <p><em>This confirmation was sent on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</em></p>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """
        
        # Send email using Python SMTP
        return send_email_via_python_smtp(
            client_email, 
            f"✅ Project Confirmed - {client_name}", 
            html_content
        )
            
    except Exception as e:
        error_msg = str(e)
        print(f"❌ Final confirmation email error: {error_msg}")
        return False, f"Email error: {error_msg}"

def send_final_report_to_admin(client_email, client_name, project_details, cost_estimate, lead_id=None):
    """
    Send final project report to admin with client details
    
    Args:
        client_email (str): Client's email address
        client_name (str): Client's name
        project_details (str): Project requirements and details
        cost_estimate (str): Project cost breakdown
    
    Returns:
        tuple: (success: bool, message: str)
    """
    try:
        # Get admin email from environment or use default
        admin_email = os.getenv('ADMIN_EMAIL', 'nikhilsalunkhe9404@gmail.com')
        
        # Process project details for HTML display
        import re
        processed_details = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', project_details)  # Convert **bold** to <strong>
        processed_details = processed_details.replace('•', '•')  # Keep bullet points
        processed_details = processed_details.replace('\n', '<br>')  # Convert newlines to <br>
        processed_details = re.sub(r'^\s+|\s+$', '', processed_details, flags=re.MULTILINE)  # Remove leading/trailing spaces
        
        # Process cost estimate for HTML display
        processed_cost = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', cost_estimate)  # Convert **bold** to <strong>
        processed_cost = processed_cost.replace('•', '•')  # Keep bullet points
        processed_cost = processed_cost.replace('\n', '<br>')  # Convert newlines to <br>
        processed_cost = re.sub(r'^\s+|\s+$', '', processed_cost, flags=re.MULTILINE)  # Remove leading/trailing spaces
        
        # Create HTML email content
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Final Project Report - {client_name}</title>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 700px; margin: 0 auto; padding: 20px; background: #f8f9fa; border-radius: 10px; }}
                .header {{ text-align: center; background: #007bff; color: white; padding: 20px; border-radius: 10px 10px 0 0; }}
                .content {{ background: white; padding: 30px; border-radius: 0 0 10px 10px; }}
                .project-details {{ background: #f8f9fa; padding: 20px; border-radius: 5px; margin: 20px 0; white-space: pre-wrap; }}
                .cost-estimate {{ background: #e8f5e8; padding: 20px; border-radius: 5px; margin: 20px 0; white-space: pre-wrap; }}
                .footer {{ text-align: center; margin-top: 30px; color: #666; }}
                .highlight {{ background: #fff3cd; padding: 15px; border-left: 4px solid #ffc107; margin: 20px 0; }}
                .pdf-button {{ background: #28a745; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; display: inline-block; margin: 10px 0; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🎯 Final Project Report</h1>
                    <h2>AI Lead Automation - New Project</h2>
                </div>
                <div class="content">
                    <div class="highlight">
                        <h3>📋 Project Information</h3>
                        <p><strong>Client Name:</strong> {client_name}</p>
                        <p><strong>Client Email:</strong> {client_email}</p>
                        <p><strong>Report Generated:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                        <a href="{os.getenv('PUBLIC_BASE_URL', get_public_base_url())}/api/download-summary/{lead_id or 'default'}" class="pdf-button">📄 Download PDF Report</a>
                    </div>
                    
                    <div class="project-details">
                        <h3>📝 Project Details</h3>
                        <div>{processed_details}</div>
                    </div>
                    
                    <div class="cost-estimate">
                        <h3>💰 Cost Estimate</h3>
                        <div>{processed_cost}</div>
                    </div>
                    
                    <div class="footer">
                        <p><strong>Next Steps:</strong></p>
                        <p>1. Review the project requirements</p>
                        <p>2. Contact the client for confirmation</p>
                        <p>3. Begin development upon approval</p>
                        <p><em>This report was automatically generated by AI Lead Automation</em></p>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """
        
        # Send email using Python SMTP (no domain verification needed)
        return send_email_via_python_smtp(
            admin_email, 
            f"🎯 Final Project Report - {client_name}", 
            html_content
        )
            
    except Exception as e:
        error_msg = str(e)
        print(f"❌ Final report email error: {error_msg}")
        return False, f"Email error: {error_msg}"

def extract_cost_from_summary(summary):
    """
    Extract cost estimate from AI-generated summary to ensure consistency
    
    Args:
        summary (str): AI-generated project summary
    
    Returns:
        str: Cost estimate from summary or default
    """
    try:
        # Look for budget section in summary
        import re
        
        # Pattern to match budget information
        budget_patterns = [
            r'\*\*Budget Considerations\*\*[\s\S]*?\*\*Estimated budget\*\*:?\s*([^*•\n]+)',
            r'Estimated budget:?\s*([^*•\n]+)',
            r'\*\*Estimated budget\*\*:?\s*([^*•\n]+)',
            r'Budget:?\s*([^*•\n]+)'
        ]
        
        for pattern in budget_patterns:
            match = re.search(pattern, summary, re.IGNORECASE)
            if match:
                budget_text = match.group(1).strip()
                # Return the budget section from summary
                budget_section = re.search(r'\*\*Budget Considerations\*\*[\s\S]*?(?=\*\*|\Z)', summary, re.IGNORECASE)
                if budget_section:
                    return budget_section.group(0).strip()
                return f"**Budget Considerations**\n• Estimated budget: {budget_text}"
        
        # If no budget found, return empty
        return "Budget information not specified in summary"
        
    except Exception as e:
        print(f"Error extracting cost from summary: {e}")
        return "Budget information not available"

def generate_cost_estimate(project_summary):
    """
    Generate cost estimate based on project summary
    
    Args:
        project_summary (str): Project requirements summary
    
    Returns:
        str: Formatted cost estimate
    """
    try:
        # Basic cost estimation logic based on project complexity
        summary_lower = project_summary.lower()
        
        # Base costs
        base_website_cost = 5000
        base_app_cost = 8000
        base_system_cost = 12000
        
        # Feature-based cost adjustments
        cost_breakdown = {
            "Basic Website": base_website_cost,
            "Web Application": base_app_cost,
            "Management System": base_system_cost,
            "E-commerce Features": +3000,
            "User Authentication": +1500,
            "Database Integration": +2000,
            "API Development": +2500,
            "Admin Dashboard": +2000,
            "Payment Integration": +1500,
            "Advanced Features": +3000,
            "Mobile Responsive": +1000,
            "SEO Optimization": +800,
            "Performance Optimization": +1200
        }
        
        # Determine project type and calculate base cost
        if 'website' in summary_lower and 'management' in summary_lower:
            total_cost = base_system_cost
            project_type = "Product Management System"
        elif 'website' in summary_lower:
            total_cost = base_website_cost
            project_type = "Website"
        elif 'app' in summary_lower or 'application' in summary_lower:
            total_cost = base_app_cost
            project_type = "Web Application"
        else:
            total_cost = base_website_cost
            project_type = "Website"
        
        # Add feature costs
        additional_features = []
        for feature, cost in cost_breakdown.items():
            if feature != "Basic Website" and feature != "Web Application" and feature != "Management System":
                if any(keyword in summary_lower for keyword in feature.lower().split()):
                    total_cost += cost
                    additional_features.append(feature)
        
        # Timeline estimation
        if total_cost < 5000:
            timeline = "2-3 weeks"
        elif total_cost < 10000:
            timeline = "4-6 weeks"
        else:
            timeline = "6-10 weeks"
        
        # Format cost estimate
        cost_estimate = f"""
        <strong>Project Type:</strong> {project_type}<br>
        <strong>Estimated Cost:</strong> ${total_cost:,.2f}<br>
        <strong>Timeline:</strong> {timeline}<br>
        <strong>Includes:</strong><br>
        • Professional design and development<br>
        • Responsive layout for all devices<br>
        • Basic SEO optimization<br>
        • Testing and quality assurance<br>
        • 3 months of support and maintenance<br>
        """
        
        if additional_features:
            cost_estimate += f"<br><strong>Additional Features:</strong><br>"
            for feature in additional_features:
                cost_estimate += f"• {feature}<br>"
        
        return cost_estimate
        
    except Exception as e:
        print(f"Error generating cost estimate: {e}")
        return "Custom quote required. Please contact us for detailed pricing."

def send_confirmation_to_client(client_email, client_name, project_details, cost_estimate, confirmation_token):
    """
    Send project confirmation email to client with review and change request options
    
    Args:
        client_email (str): Client's email address
        client_name (str): Client's name
        project_details (str): Project requirements and details
        cost_estimate (str): Project cost breakdown
        confirmation_token (str): Unique token for client confirmation
    
    Returns:
        tuple: (success: bool, message: str)
    """
    try:
        # Check if Resend API key is configured
        api_key = os.getenv('RESEND_API_KEY')
        if not api_key or api_key == 'your_resend_api_key_here':
            print("Resend API key not configured properly")
            return False, "Email service not configured"
        
        # Get email configuration
        from_email = os.getenv('EMAIL_FROM', 'onboarding@resend.dev')
        
        # Create confirmation links using public base URL
        public_base_url = os.getenv('PUBLIC_BASE_URL', get_public_base_url())
        confirm_link = f"{public_base_url}/api/confirm-project/{confirmation_token}"
        change_request_link = f"{public_base_url}/api/request-changes/{confirmation_token}"
        
        # Create HTML content for client confirmation email
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #28a745 0%, #20c997 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
                .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
                .project-details {{ background: white; padding: 20px; border-left: 4px solid #28a745; margin: 20px 0; }}
                .cost-breakdown {{ background: #fff3cd; padding: 20px; border-radius: 5px; margin: 20px 0; }}
                .action-buttons {{ text-align: center; margin: 30px 0; }}
                .btn {{ display: inline-block; padding: 12px 24px; margin: 10px; text-decoration: none; border-radius: 5px; font-weight: bold; }}
                .btn-confirm {{ background: #28a745; color: white; }}
                .btn-changes {{ background: #ffc107; color: #212529; }}
                .footer {{ text-align: center; margin-top: 30px; color: #666; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>✅ Your Project is Ready!</h1>
                    <p>AI Lead Automation - Project Proposal</p>
                </div>
                <div class="content">
                    <h2>Hello {client_name}!</h2>
                    <p>Thank you for your interest in our services. Based on your requirements, we've prepared a comprehensive project proposal for you.</p>
                    
                    <h2>📋 Project Details</h2>
                    <div class="project-details">
                        <p>{project_details}</p>
                    </div>
                    
                    <h2>💰 Cost Estimate</h2>
                    <div class="cost-breakdown">
                        <p>{cost_estimate}</p>
                    </div>
                    
                    <h2>🎯 Next Steps</h2>
                    <p>Please review the project details and cost estimate above. You have two options:</p>
                    
                    <div class="action-buttons">
                        <a href="{confirm_link}" class="btn btn-confirm">✅ Confirm & Approve</a>
                        <a href="{change_request_link}" class="btn btn-changes">📝 Request Changes</a>
                    </div>
                    
                    <p><strong>Confirm & Approve:</strong> Proceed with the project as outlined above.</p>
                    <p><strong>Request Changes:</strong> Let us know what modifications you'd like to make.</p>
                </div>
                <div class="footer">
                    <p>This confirmation link is valid for 7 days.</p>
                    <p>Questions? Reply to this email or contact us at support@aileadautomation.com</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        # Send email using Python SMTP (no domain verification needed)
        return send_email_via_python_smtp(
            client_email, 
            f"🎯 Project Confirmation Required - {client_name}", 
            html_content
        )
            
    except Exception as e:
        error_msg = str(e)
        print(f"❌ Confirmation email error: {error_msg}")
        return False, f"Email error: {error_msg}"

def send_password_reset_email(email, reset_token):
    """
    Send password reset email to admin user
    
    Args:
        email (str): User's email address
        reset_token (str): Password reset token
    
    Returns:
        tuple: (success: bool, message: str)
    """
    try:
        # Check if Resend API key is configured
        api_key = os.getenv('RESEND_API_KEY')
        if not api_key or api_key == 'your_resend_api_key_here':
            print("Resend API key not configured properly")
            return False, "Email service not configured"
        
        # Get email configuration
        from_email = os.getenv('EMAIL_FROM', 'noreply@yourdomain.com')
        
        # Create password reset link using public base URL
        public_base_url = os.getenv('PUBLIC_BASE_URL', get_public_base_url())
        reset_link = f"{public_base_url}/api/admin/reset-password/{reset_token}"
        
        # Create professional HTML email template
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Password Reset - AI Lead Automation</title>
            <style>
                * {{
                    margin: 0;
                    padding: 0;
                    box-sizing: border-box;
                }}
                body {{
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    background-color: #f8fafc;
                    color: #1e293b;
                    line-height: 1.6;
                }}
                .container {{
                    max-width: 600px;
                    margin: 40px auto;
                    background: white;
                    border-radius: 12px;
                    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
                    overflow: hidden;
                }}
                .header {{
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    padding: 30px;
                    text-align: center;
                }}
                .header h1 {{
                    font-size: 28px;
                    font-weight: 600;
                    margin-bottom: 10px;
                }}
                .header p {{
                    font-size: 16px;
                    opacity: 0.9;
                }}
                .content {{
                    padding: 40px;
                }}
                .reset-info {{
                    background: #f1f5f9;
                    border-left: 4px solid #667eea;
                    padding: 20px;
                    margin: 20px 0;
                    border-radius: 8px;
                }}
                .reset-info h3 {{
                    color: #1e293b;
                    margin-bottom: 15px;
                    font-size: 18px;
                }}
                .reset-button {{
                    display: inline-block;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    text-decoration: none;
                    padding: 15px 30px;
                    border-radius: 8px;
                    font-weight: 600;
                    font-size: 16px;
                    text-align: center;
                    margin: 20px 0;
                    transition: all 0.3s ease;
                }}
                .reset-button:hover {{
                    transform: translateY(-2px);
                    box-shadow: 0 8px 25px rgba(102, 126, 234, 0.3);
                }}
                .security-info {{
                    background: #fef2f2;
                    border: 1px solid #fecaca;
                    padding: 15px;
                    border-radius: 8px;
                    margin: 20px 0;
                }}
                .security-info h4 {{
                    color: #dc2626;
                    margin-bottom: 10px;
                    font-size: 16px;
                }}
                .footer {{
                    background: #f8fafc;
                    padding: 20px;
                    text-align: center;
                    border-top: 1px solid #e2e8f0;
                }}
                .footer p {{
                    color: #64748b;
                    font-size: 14px;
                }}
                .token-info {{
                    background: #f3f4f6;
                    padding: 10px;
                    border-radius: 4px;
                    font-family: monospace;
                    font-size: 12px;
                    word-break: break-all;
                    margin: 10px 0;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🔐 Password Reset Request</h1>
                    <p>AI Lead Automation Admin Portal</p>
                </div>
                
                <div class="content">
                    <p>Hello,</p>
                    
                    <p>We received a request to reset the password for your admin account associated with this email address.</p>
                    
                    <div class="reset-info">
                        <h3>🔑 Reset Instructions</h3>
                        <p>Click the button below to reset your password. This link is valid for <strong>1 hour</strong> only.</p>
                        
                        <a href="{reset_link}" class="reset-button">
                            Reset My Password
                        </a>
                        
                        <p style="margin-top: 15px; font-size: 14px; color: #64748b;">
                            If the button doesn't work, copy and paste this link into your browser:
                        </p>
                        <div class="token-info">{reset_link}</div>
                    </div>
                    
                    <div class="security-info">
                        <h4>🛡️ Security Notice</h4>
                        <ul style="margin-left: 20px; color: #7f1d1d;">
                            <li>If you didn't request this password reset, please ignore this email</li>
                            <li>Never share this reset link with anyone</li>
                            <li>This link will expire after 1 hour for security</li>
                            <li>Make sure to choose a strong, unique password</li>
                        </ul>
                    </div>
                    
                    <p>Thank you for using AI Lead Automation!</p>
                </div>
                
                <div class="footer">
                    <p>© 2024 AI Lead Automation. All rights reserved.</p>
                    <p>This is an automated message. Please do not reply to this email.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        # Create plain text version
        text_content = f"""
        Password Reset - AI Lead Automation
        
        Hello,
        
        We received a request to reset the password for your admin account.
        
        Click the link below to reset your password (valid for 1 hour):
        {reset_link}
        
        If you didn't request this reset, please ignore this email.
        
        Security Notice:
        - Never share this reset link with anyone
        - This link expires after 1 hour
        - Choose a strong, unique password
        
        Thank you,
        AI Lead Automation Team
        """
        
        # Send email using Resend
        params = {
            "from": from_email,
            "to": [email],
            "subject": "🔐 Password Reset Request - AI Lead Automation",
            "html": html_content,
            "text": text_content
        }
        
        print(f"📧 Sending password reset email to {email}")
        result = resend.Emails.send(params)
        
        if result.get("id"):
            print(f"Password reset email sent successfully to {email}. Message ID: {result['id']}")
            return True, f"Password reset email sent to {email}"
        else:
            print(f"Password reset email sending failed: {result}")
            return False, "Email sending failed"
            
    except Exception as e:
        error_msg = str(e)
        print(f"Password reset email sending error: {error_msg}")
        return False, f"Email error: {error_msg}"

# ================================
# MONGODB HELPER FUNCTIONS
# ================================

def save_lead_to_mongodb(name, email, message, ai_reply=None, is_summary=False):
    """
    Save lead data to MongoDB Atlas
    
    Args:
        name (str): User's name
        email (str): User's email
        message (str): Message content
        ai_reply (str): AI-generated reply (optional)
        is_summary (bool): Whether this is a summary
    
    Returns:
        tuple: (success: bool, message: str, lead_id: str)
    """
    try:
        leads_collection = get_collection('leads')
        if leads_collection is None:
            return False, "Database not connected", None
        
        # Create lead document
        lead_doc = {
            "name": name.strip(),
            "email": email.strip(),
            "message": message.strip(),
            "timestamp": datetime.now(timezone.utc),
            "ai_reply": ai_reply.strip() if ai_reply else None,
            "is_summary": is_summary,
            "status": "new"
        }
        
        # Insert into MongoDB
        result = leads_collection.insert_one(lead_doc)
        
        print(f"💾 Lead saved to MongoDB: {name} ({email})")
        print(f"🆔 Lead ID: {result.inserted_id}")
        
        return True, "Lead saved successfully", str(result.inserted_id)
        
    except Exception as e:
        error_msg = str(e)
        print(f"❌ Error saving lead to MongoDB: {error_msg}")
        return False, f"Database error: {error_msg}", None

def save_chat_history_to_mongodb(email, session_id, message, role, name=None, ai_reply=None):
    """
    Save chat conversation to MongoDB
    
    Args:
        email (str): User's email
        session_id (str): Chat session identifier
        message (str): User message
        role (str): Message role (user/assistant)
        name (str): User's name (optional)
        ai_reply (str): AI response (optional)
    
    Returns:
        tuple: (success: bool, message: str)
    """
    try:
        chat_collection = get_collection('chat_history')
        if chat_collection is None:
            return False, "Database not connected"
        
        # Create chat document
        chat_doc = {
            "email": email.strip(),
            "session_id": session_id,
            "message": message.strip(),
            "role": role,
            "name": name.strip() if name else None,
            "ai_reply": ai_reply.strip() if ai_reply else None,
            "timestamp": datetime.now(timezone.utc)
        }
        
        # Insert into MongoDB
        chat_collection.insert_one(chat_doc)
        
        print(f"💬 Chat saved to MongoDB: {email} - {role}")
        
        return True, "Chat saved successfully"
        
    except Exception as e:
        error_msg = str(e)
        print(f"❌ Error saving chat to MongoDB: {error_msg}")
        return False, f"Database error: {error_msg}"

def get_all_leads_from_mongodb():
    """
    Retrieve all leads from MongoDB
    
    Returns:
        tuple: (success: bool, leads: list, message: str)
    """
    try:
        leads_collection = get_collection('leads')
        if leads_collection is None:
            return False, [], "Database not connected"
        
        # Get all leads, sorted by timestamp (newest first)
        leads = list(leads_collection.find().sort("timestamp", -1))
        
        # Convert ObjectId to string and format timestamps
        formatted_leads = []
        for lead in leads:
            formatted_lead = {
                "name": lead.get("name", ""),
                "email": lead.get("email", ""),
                "message": lead.get("message", ""),
                "timestamp": lead.get("timestamp", datetime.now(timezone.utc)).isoformat(),
                "ai_reply": lead.get("ai_reply"),
                "is_summary": lead.get("is_summary", False),
                "status": lead.get("status", "new"),
                "change_request": normalize_change_request(lead.get("change_request")),
                "project_details": lead.get("project_details"),
                "cost_estimate": lead.get("cost_estimate"),
                "_id": str(lead.get("_id"))
            }
            formatted_leads.append(formatted_lead)
        
        print(f"📊 Retrieved {len(formatted_leads)} leads from MongoDB")
        
        return True, formatted_leads, "Leads retrieved successfully"
        
    except Exception as e:
        error_msg = str(e)
        print(f"❌ Error retrieving leads from MongoDB: {error_msg}")
        return False, [], f"Database error: {error_msg}"

def delete_lead_from_mongodb(lead_index):
    """
    Delete a lead from MongoDB by index
    
    Args:
        lead_index (int): Index of lead to delete
    
    Returns:
        tuple: (success: bool, message: str)
    """
    try:
        leads_collection = get_collection('leads')
        if leads_collection is None:
            return False, "Database not connected"
        
        # Get all leads sorted by timestamp
        leads = list(leads_collection.find().sort("timestamp", -1))
        
        # Validate index
        if lead_index < 0 or lead_index >= len(leads):
            return False, "Lead not found"
        
        # Get lead to delete
        lead_to_delete = leads[lead_index]
        
        # Delete from MongoDB
        result = leads_collection.delete_one({"_id": lead_to_delete["_id"]})
        
        if result.deleted_count > 0:
            lead_name = lead_to_delete.get("name", "Unknown")
            lead_email = lead_to_delete.get("email", "Unknown")
            print(f"🗑️ Deleted lead from MongoDB: {lead_name} ({lead_email})")
            return True, "Lead deleted successfully"
        else:
            return False, "No lead was deleted"
            
    except Exception as e:
        error_msg = str(e)
        print(f"❌ Error deleting lead from MongoDB: {error_msg}")
        return False, f"Database error: {error_msg}"

# ================================
# FLASK ROUTES
# ================================

# Database health check route
@app.route('/api/db-status', methods=['GET'])
def db_status():
    """
    Health check for MongoDB connection
    Returns connection status and basic stats
    """
    try:
        if mongo_database is None:
            return jsonify({
                "database": "disconnected",
                "error": "Database not initialized",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }), 503
        
        # Test database connection
        db_client.admin.command('ping')
        
        # Simple status check without collection operations for now
        stats = {
            "database": "connected",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "collections": {
                "leads": "active",
                "chat_history": "active", 
                "summaries": "active"
            }
        }
        
        return jsonify(stats)
        
    except Exception as e:
        return jsonify({
            "database": "error",
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }), 500

# Root route - Welcome page
@app.route('/')
def welcome():
    return render_template('welcome.html')

# Dashboard route
@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

# Admin login route
@app.route('/admin_login')
def admin_login():
    return render_template('admin_login.html')

# Admin dashboard route
@app.route('/admin_dashboard')
def admin_dashboard():
    return render_template('admin_dashboard.html')

# Admin management page route
@app.route('/admin_management')
def admin_management_page():
    """Serve the admin management page"""
    return send_from_directory('.', 'admin_management.html')

# Chat interface route (for backward compatibility)
@app.route('/chat')
def chat_interface():
    return send_from_directory('.', 'chat_interface.html')

# API test route
@app.route('/api/test')
def api_test():
    return jsonify({
        "status": "success",
        "message": "API is working",
        "database": "connected" if mongo_database is not None else "disconnected"
    })

# Admin registration page route
@app.route('/admin_register')
def admin_register_page():
    """Serve the admin registration page"""
    return render_template('admin_register.html')

# Memory dashboard route
@app.route('/memory_dashboard')
def memory_dashboard():
    """Serve the memory dashboard page"""
    return render_template('memory_dashboard.html')

# Context dashboard route
@app.route('/context_dashboard')
def context_dashboard():
    """Serve the context dashboard page"""
    return render_template('context_dashboard.html')

# Analytics dashboard route
@app.route('/analytics_dashboard')
def analytics_dashboard():
    """Serve the analytics dashboard page"""
    return render_template('analytics_dashboard.html')

# Landing page route
@app.route('/landing')
def landing():
    """Serve the landing page"""
    return render_template('landing.html')

# Admin registration API endpoint
@app.route('/api/admin/register', methods=['POST'])
def register_admin():
    """
    Register a new admin user with password hashing and enhanced security
    """
    try:
        # Validate request
        is_valid, error_message, data = RequestValidator.validate_json_request(
            required_fields=['username', 'email', 'password', 'role']
        )
        
        if not is_valid:
            return jsonify({
                "status": "error",
                "message": error_message
            }), 400
        
        username = data.get('username', '').strip()
        email = data.get('email', '').strip()
        password = data.get('password', '')
        role = data.get('role', '').strip()
        
        # Enhanced password validation
        is_password_valid, password_error = PasswordValidator.validate_password(password)
        if not is_password_valid:
            return jsonify({
                "status": "error",
                "message": password_error
            }), 400
        
        # Validate role
        valid_roles = ['super_admin', 'admin', 'viewer']
        if role not in valid_roles:
            return jsonify({
                "status": "error",
                "message": "Invalid role specified"
            }), 400
        
        # Get admin collection
        admin_collection = get_collection('admins')
        if admin_collection is None:
            return jsonify({
                "status": "error",
                "message": "Database connection error"
            }), 500
        
        # Check if username already exists
        existing_username = admin_collection.find_one({"username": username})
        if existing_username:
            return jsonify({
                "status": "error",
                "message": "Username already exists"
            }), 409
        
        # Check if email already exists
        existing_email = admin_collection.find_one({"email": email})
        if existing_email:
            return jsonify({
                "status": "error",
                "message": "Email already registered"
            }), 409
        
        # Hash password
        salt = bcrypt.gensalt()
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), salt)
        
        # Create admin document
        admin_doc = {
            "username": username,
            "email": email,
            "password": hashed_password.decode('utf-8'),
            "role": role,
            "is_active": True,
            "created_at": datetime.now(timezone.utc),
            "last_login": None,
            "login_attempts": 0
        }
        
        # Insert into database
        result = admin_collection.insert_one(admin_doc)
        
        if result.inserted_id:
            print(f"✅ New admin registered: {username} ({email})")
            return jsonify({
                "status": "success",
                "message": "Admin registered successfully",
                "admin_id": str(result.inserted_id)
            }), 201
        else:
            return jsonify({
                "status": "error",
                "message": "Failed to register admin"
            }), 500
            
    except Exception as e:
        print(f"❌ Error registering admin: {e}")
        return jsonify({
            "status": "error",
            "message": "Internal server error"
        }), 500

@app.route('/api/csrf-token', methods=['GET'])
def get_csrf_token():
    """Generate and return a CSRF token for form protection"""
    try:
        import secrets
        token = secrets.token_urlsafe(32)
        return jsonify({
            "status": "success",
            "csrf_token": token
        }), 200
    except Exception as e:
        print(f"❌ Error generating CSRF token: {e}")
        return jsonify({
            "status": "error",
            "message": "Error generating CSRF token"
        }), 500

# Admin authentication API endpoint
@app.route('/api/admin/login', methods=['POST'])
def admin_login_auth():
    """
    Authenticate admin user with MongoDB credentials and enhanced security
    """
    try:
        # Validate request
        is_valid, error_message, data = RequestValidator.validate_json_request(
            required_fields=['username', 'password']
        )
        
        if not is_valid:
            return jsonify({
                "status": "error",
                "message": error_message
            }), 400
        
        username = data.get('username', '').strip()
        password = data.get('password', '')
        
        # Log login attempt
        try:
            log_security_event('LOGIN_ATTEMPT', {
                'username': username,
                'ip_address': request.remote_addr
            })
        except:
            print(f"Login attempt: username={username}, ip={request.remote_addr}")
        
        # Get admin collection
        admin_collection = get_collection('admins')
        if admin_collection is None:
            return jsonify({
                "status": "error",
                "message": "Database connection error"
            }), 500
        
        # Find admin by username
        admin = admin_collection.find_one({"username": username})
        
        if not admin:
            return jsonify({
                "status": "error",
                "message": "Invalid username or password"
            }), 401
        
        # Check if admin is active
        if not admin.get('is_active', True):
            return jsonify({
                "status": "error",
                "message": "Account is deactivated"
            }), 403
        
        # Verify password
        stored_password = admin['password'].encode('utf-8')
        if bcrypt.checkpw(password.encode('utf-8'), stored_password):
            # Update last login
            admin_collection.update_one(
                {"_id": admin["_id"]},
                {
                    "$set": {
                        "last_login": datetime.now(timezone.utc),
                        "login_attempts": 0
                    }
                }
            )
            
            # Store session (include last_activity for auth middleware)
            session['admin_id'] = str(admin['_id'])
            session['admin_username'] = admin['username']
            session['admin_email'] = admin.get('email', '')
            session['admin_role'] = admin['role']
            session['is_authenticated'] = True
            session['last_activity'] = datetime.now(timezone.utc).isoformat()
            
            print(f"✅ Admin login successful: {username}")
            
            return jsonify({
                "status": "success",
                "message": "Login successful",
                "redirect": "/admin_dashboard",
                "user": {
                    "username": admin['username'],
                    "email": admin['email'],
                    "role": admin['role']
                }
            }), 200
        else:
            # Increment login attempts
            admin_collection.update_one(
                {"_id": admin["_id"]},
                {"$inc": {"login_attempts": 1}}
            )
            
            return jsonify({
                "status": "error",
                "message": "Invalid username or password"
            }), 401
            
    except Exception as e:
        print(f"❌ Error during admin login: {e}")
        return jsonify({
            "status": "error",
            "message": "Internal server error"
        }), 500

# Admin logout endpoint
@app.route('/api/admin/logout', methods=['POST'])
def admin_logout():
    """Logout admin user"""
    try:
        session.clear()
        return jsonify({
            "status": "success",
            "message": "Logged out successfully"
        }), 200
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": "Logout failed"
        }), 500

# Admin forgot password endpoint
@app.route('/api/admin/forgot-password', methods=['POST'])
def admin_forgot_password():
    """Handle admin password reset request"""
    try:
        # Validate request
        is_valid, error_message, data = RequestValidator.validate_json_request(
            required_fields=['email']
        )
        
        if not is_valid:
            return jsonify({
                "status": "error",
                "message": error_message
            }), 400
        
        email = data.get('email', '').strip()
        
        # Validate email format
        email_regex = r'^[^\s@]+@[^\s@]+\.[^\s@]+$'
        if not re.match(email_regex, email):
            return jsonify({
                "status": "error",
                "message": "Invalid email address"
            }), 400
        
        # Get admin collection
        admin_collection = get_collection('admins')
        if admin_collection is None:
            return jsonify({
                "status": "error",
                "message": "Database connection error"
            }), 500
        
        # Check if email exists in admin database
        admin = admin_collection.find_one({"email": email})
        if not admin:
            # Don't reveal if email exists or not for security
            return jsonify({
                "status": "success",
                "message": "If an account with this email exists, a password reset link has been sent."
            }), 200
        
        # Generate secure reset token
        import secrets
        reset_token = secrets.token_urlsafe(32)
        reset_expiry = datetime.now(timezone.utc) + timedelta(hours=1)  # Token valid for 1 hour
        
        # Store reset token in database
        admin_collection.update_one(
            {"_id": admin["_id"]},
            {
                "$set": {
                    "reset_token": reset_token,
                    "reset_expiry": reset_expiry,
                    "reset_requested_at": datetime.now(timezone.utc)
                }
            }
        )
        
        # Send password reset email
        email_sent, email_message = send_password_reset_email(email, reset_token)
        if not email_sent:
            print(f"❌ Failed to send password reset email: {email_message}")
            # Still return success to avoid revealing if email exists
        else:
            print(f"📧 Password reset email sent to {email}")
        
        print(f"🔑 Password reset token generated for {email}: {reset_token}")
        
        return jsonify({
            "status": "success",
            "message": "Password reset link has been sent to your email address.",
            "debug_token": reset_token  # Only for development/testing
        }), 200
        
    except Exception as e:
        print(f"❌ Error in forgot password: {e}")
        return jsonify({
            "status": "error",
            "message": "Internal server error"
        }), 500

# Admin password reset endpoint
@app.route('/api/confirm-project/<token>', methods=['GET', 'POST'])
def confirm_project(token):
    """Handle client project confirmation"""
    try:
        # Get leads collection
        leads_collection = get_collection('leads')
        if leads_collection is None:
            return "Database connection error", 500
        
        # Find project by confirmation token
        print(f"🔍 Looking for token: {token}")
        print(f"🔍 Current time: {datetime.now(timezone.utc)}")
        
        project = leads_collection.find_one({
            "confirmation_token": token,
            "confirmation_expiry": {"$gt": datetime.now(timezone.utc)}
        })
        
        print(f"🔍 Found project: {project is not None}")
        
        if not project:
            print(f"❌ Token not found or expired")
            # Let's check if token exists at all
            token_check = leads_collection.find_one({"confirmation_token": token})
            print(f"🔍 Token exists (ignoring expiry): {token_check is not None}")
            if token_check:
                print(f"🔍 Token expiry: {token_check.get('confirmation_expiry')}")
                print(f"🔍 Token name: {token_check.get('name')}")
            return "Invalid or expired confirmation link", 400
        
        # Get the most recent name from chat history for this email
        chat_collection = get_collection('chat_history')
        if chat_collection:
            recent_chat = chat_collection.find_one(
                {"email": project.get('email')},
                sort=[("timestamp", -1)]
            )
            if recent_chat and recent_chat.get('name'):
                # Update project name with the most recent name from chat
                project['name'] = recent_chat['name']
                print(f"🔍 Updated name from chat history: {project['name']}")
        
        if request.method == 'GET':
            # Show confirmation page
            return render_template("confirm_project.html", project=project, token=token)
        
        elif request.method == 'POST':
            # Process confirmation
            leads_collection.update_one(
                {"_id": project["_id"]},
                {
                    "$set": {
                        "status": "client_confirmed",
                        "client_confirmed_at": datetime.now(timezone.utc),
                        "confirmation_token": None,
                        "confirmation_expiry": None
                    }
                }
            )
            
            print(f"✅ Project confirmed by client: {project.get('email')}")
            
            # Send notification to admin
            admin_email_sent, admin_msg = send_final_report_to_admin(
                project.get('email'),
                project.get('name'),
                project.get('project_details'),
                project.get('cost_estimate')
            )
            
            return render_template("confirmation_success.html", project=project)
            
    except Exception as e:
        print(f"❌ Error in project confirmation: {e}")
        return "Internal server error", 500

@app.route('/api/request-changes/<token>', methods=['GET', 'POST'])
def request_changes(token):
    """Handle client change requests"""
    try:
        # Get leads collection
        leads_collection = get_collection('leads')
        if leads_collection is None:
            return "Database connection error", 500
        
        # Find project by confirmation token
        print(f"🔍 Looking for token: {token}")
        print(f"🔍 Current time: {datetime.now(timezone.utc)}")
        
        project = leads_collection.find_one({
            "confirmation_token": token,
            "confirmation_expiry": {"$gt": datetime.now(timezone.utc)}
        })
        
        print(f"🔍 Found project: {project is not None}")
        
        if not project:
            print(f"❌ Token not found or expired")
            # Let's check if token exists at all
            token_check = leads_collection.find_one({"confirmation_token": token})
            print(f"🔍 Token exists (ignoring expiry): {token_check is not None}")
            if token_check:
                print(f"🔍 Token expiry: {token_check.get('confirmation_expiry')}")
                print(f"🔍 Token name: {token_check.get('name')}")
            return "Invalid or expired confirmation link", 400
        
        # Get the most recent name from chat history for this email
        chat_collection = get_collection('chat_history')
        if chat_collection:
            recent_chat = chat_collection.find_one(
                {"email": project.get('email')},
                sort=[("timestamp", -1)]
            )
            if recent_chat and recent_chat.get('name'):
                # Update project name with the most recent name from chat
                project['name'] = recent_chat['name']
                print(f"🔍 Updated name from chat history: {project['name']}")
        
        if request.method == 'GET':
            # Show change request form
            return render_template("request_changes.html", project=project, token=token)
        
        elif request.method == 'POST':
            # Process change request
            changes = request.form.get('changes', '')
            budget_changes = request.form.get('budget_changes', '')
            change_payload = {
                "changes": changes,
                "requested_changes": changes,
                "budget_changes": budget_changes,
                "requested_at": datetime.now(timezone.utc),
                "client_email": project.get('email'),
                "client_name": project.get('name'),
            }
            
            # Update project with change request
            leads_collection.update_one(
                {"_id": project["_id"]},
                {
                    "$set": {
                        "status": "changes_requested",
                        "change_request": change_payload,
                    }
                }
            )
            
            updated_lead = leads_collection.find_one({"_id": project["_id"]})
            if updated_lead:
                emit_new_change_request_to_admins(updated_lead)
                admin_email = os.getenv('ADMIN_EMAIL', 'nikhilsalunkhe9404@gmail.com')
                send_change_request_notification_email(
                    admin_email,
                    project.get('name'),
                    project.get('email'),
                    changes,
                    budget_changes,
                    str(project['_id']),
                )
            
            print(f"📝 Change request received from client: {project.get('email')}")
            print(f"📝 Changes: {changes}")
            
            return render_template(
                "change_request_success.html",
                project=updated_lead or project,
                changes=changes,
                lead_id=str(project['_id']),
            )
            
    except Exception as e:
        print(f"❌ Error in change request: {e}")
        return "Internal server error", 500

@app.route('/api/admin-confirm-project/<lead_id>', methods=['POST'])
def admin_confirm_project(lead_id):
    """Handle admin project confirmation"""
    try:
        # Get leads collection
        leads_collection = get_collection('leads')
        if leads_collection is None:
            return jsonify({"status": "error", "message": "Database connection error"}), 500
        
        project, lead_oid = find_lead_by_identifier(lead_id)
        
        if not project:
            return jsonify({"status": "error", "message": "Project not found"}), 404
        
        # Check if client has already confirmed
        if project.get('status') != 'client_confirmed':
            return jsonify({"status": "error", "message": "Client has not confirmed this project yet"}), 400
        
        # Update project with admin confirmation
        leads_collection.update_one(
            {"_id": lead_oid},
            {
                "$set": {
                    "status": "confirmed",
                    "admin_confirmed_at": datetime.now(timezone.utc)
                }
            }
        )
        
        print(f"✅ Project confirmed by admin: {project.get('email')}")
        
        # Send final confirmation email to client
        client_email_sent, client_msg = send_final_confirmation_to_client(
            project.get('email'),
            project.get('name'),
            project.get('project_details'),
            project.get('cost_estimate')
        )
        
        return jsonify({
            "status": "success",
            "message": "Project confirmed successfully",
            "client_email_sent": client_email_sent,
            "client_email_message": client_msg
        }), 200
            
    except Exception as e:
        print(f"❌ Error in admin project confirmation: {e}")
        return jsonify({"status": "error", "message": "Internal server error"}), 500

@app.route('/api/download-summary/<lead_id>')
def download_summary_pdf(lead_id):
    """Generate and download PDF summary"""
    try:
        # Get lead from MongoDB
        leads_collection = get_collection('leads')
        if leads_collection is None:
            return "Database connection error", 500
        
        lead = leads_collection.find_one({"_id": lead_id})
        if not lead:
            return "Lead not found", 404
        
        # Generate HTML content for PDF
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Project Summary - {lead.get('name', 'Client')}</title>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; margin: 40px; }}
                .header {{ text-align: center; border-bottom: 2px solid #007bff; padding-bottom: 20px; margin-bottom: 30px; }}
                .section {{ margin-bottom: 30px; }}
                .section h2 {{ color: #007bff; border-bottom: 1px solid #eee; padding-bottom: 10px; }}
                .highlight {{ background: #f8f9fa; padding: 15px; border-left: 4px solid #007bff; margin: 20px 0; }}
                .footer {{ text-align: center; margin-top: 50px; color: #666; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>🎯 Project Summary Report</h1>
                <h2>AI Lead Automation</h2>
                <p>Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            </div>
            
            <div class="highlight">
                <h3>📋 Client Information</h3>
                <p><strong>Name:</strong> {lead.get('name', 'N/A')}</p>
                <p><strong>Email:</strong> {lead.get('email', 'N/A')}</p>
                <p><strong>Lead ID:</strong> {lead_id}</p>
            </div>
            
            <div class="section">
                <h2>📝 Project Details</h2>
                <div style="white-space: pre-wrap;">{lead.get('project_details', 'No details available')}</div>
            </div>
            
            <div class="section">
                <h2>💰 Cost Estimate</h2>
                <div style="white-space: pre-wrap;">{lead.get('cost_estimate', 'No cost estimate available')}</div>
            </div>
            
            <div class="footer">
                <p>This report was automatically generated by AI Lead Automation</p>
                <p>For questions, please contact: nikhilsalunkhe9404@gmail.com</p>
            </div>
        </body>
        </html>
        """
        
        # For now, return HTML as a simple solution
        # In production, you'd use a PDF library like WeasyPrint or ReportLab
        response = app.response_class(
            response=html_content,
            status=200,
            mimetype='text/html'
        )
        response.headers['Content-Disposition'] = f'attachment; filename=project_summary_{lead_id}.html'
        return response
        
    except Exception as e:
        print(f"❌ PDF download error: {e}")
        return "Error generating PDF", 500

@app.route('/api/admin/reset-password/<token>', methods=['GET', 'POST'])
def admin_reset_password(token):
    """Handle admin password reset with token"""
    try:
        if request.method == 'GET':
            # Show reset password form
            return render_template('admin_reset_password.html', token=token)
        
        elif request.method == 'POST':
            # Process password reset
            is_valid, error_message, data = RequestValidator.validate_json_request(
                required_fields=['password', 'confirm_password']
            )
            
            if not is_valid:
                return jsonify({
                    "status": "error",
                    "message": error_message
                }), 400
            
            password = data.get('password', '')
            confirm_password = data.get('confirm_password', '')
            
            # Validate passwords
            if len(password) < 8:
                return jsonify({
                    "status": "error",
                    "message": "Password must be at least 8 characters long"
                }), 400
            
            if password != confirm_password:
                return jsonify({
                    "status": "error",
                    "message": "Passwords do not match"
                }), 400
            
            # Get admin collection
            admin_collection = get_collection('admins')
            if admin_collection is None:
                return jsonify({
                    "status": "error",
                    "message": "Database connection error"
                }), 500
            
            # Find admin by reset token
            admin = admin_collection.find_one({
                "reset_token": token,
                "reset_expiry": {"$gt": datetime.now(timezone.utc)}
            })
            
            if not admin:
                return jsonify({
                    "status": "error",
                    "message": "Invalid or expired reset token"
                }), 400
            
            # Hash new password
            salt = bcrypt.gensalt()
            hashed_password = bcrypt.hashpw(password.encode('utf-8'), salt)
            
            # Update password and clear reset token
            admin_collection.update_one(
                {"_id": admin["_id"]},
                {
                    "$set": {
                        "password": hashed_password.decode('utf-8'),
                        "reset_token": None,
                        "reset_expiry": None,
                        "password_changed_at": datetime.now(timezone.utc)
                    }
                }
            )
            
            print(f"🔐 Password reset successfully for admin: {admin['email']}")
            
            return jsonify({
                "status": "success",
                "message": "Password has been reset successfully. You can now login with your new password."
            }), 200
            
    except Exception as e:
        print(f"❌ Error in password reset: {e}")
        return jsonify({
            "status": "error",
            "message": "Internal server error"
        }), 500

# Admin management API endpoint
@app.route('/api/admin/list', methods=['GET'])
@AuthMiddleware.require_any_role('super_admin', 'admin')
def list_admins():
    """
    Get list of all admin users (for admin management)
    """
    try:
        
        # Get admin collection
        admin_collection = get_collection('admins')
        if admin_collection is None:
            return jsonify({
                "status": "error",
                "message": "Database connection error"
            }), 500
        
        # Get all admins (excluding passwords)
        admins = []
        for admin in admin_collection.find({}, {"password": 0}):
            admins.append({
                "id": str(admin["_id"]),
                "username": admin["username"],
                "email": admin["email"],
                "role": admin["role"],
                "is_active": admin.get("is_active", True),
                "created_at": admin.get("created_at"),
                "last_login": admin.get("last_login"),
                "login_attempts": admin.get("login_attempts", 0)
            })
        
        return jsonify({
            "status": "success",
            "admins": admins
        }), 200
        
    except Exception as e:
        print(f"❌ Error listing admins: {e}")
        return jsonify({
            "status": "error",
            "message": "Internal server error"
        }), 500

# Delete admin API endpoint
@app.route('/api/admin/<admin_id>', methods=['DELETE'])
@AuthMiddleware.require_role('super_admin')
def delete_admin(admin_id):
    """
    Delete an admin user
    """
    try:
        
        # Get admin collection
        admin_collection = get_collection('admins')
        if admin_collection is None:
            return jsonify({
                "status": "error",
                "message": "Database connection error"
            }), 500
        
        # Prevent self-deletion
        if session.get('admin_id') == admin_id:
            return jsonify({
                "status": "error",
                "message": "Cannot delete your own account"
            }), 400
        
        # Delete admin
        result = admin_collection.delete_one({"_id": admin_id})
        
        if result.deleted_count > 0:
            print(f"✅ Admin deleted: {admin_id}")
            return jsonify({
                "status": "success",
                "message": "Admin deleted successfully"
            }), 200
        else:
            return jsonify({
                "status": "error",
                "message": "Admin not found"
            }), 404
            
    except Exception as e:
        print(f"❌ Error deleting admin: {e}")
        return jsonify({
            "status": "error",
            "message": "Internal server error"
        }), 500

# POST route to save lead data (Updated for MongoDB)
@app.route('/api/lead', methods=['POST'])
def save_lead():
    """
    Save lead data to MongoDB with AI reply and email functionality
    """
    try:
        # Get JSON data from request
        data = request.get_json()
        
        # Validate required fields
        if not data:
            return jsonify({
                "status": "error",
                "message": "No data provided"
            }), 400
        
        required_fields = ['name', 'email', 'message']
        missing_fields = [field for field in required_fields if field not in data or not data[field].strip()]
        
        if missing_fields:
            return jsonify({
                "status": "error",
                "message": f"Missing required fields: {', '.join(missing_fields)}"
            }), 400
        
        # Generate AI reply
        ai_reply = ""
        try:
            # Check if API key is loaded
            api_key = os.getenv('GROQ_API_KEY')
            if not api_key or api_key == 'your_groq_api_key_here':
                print("Groq API key not configured properly")
                ai_reply = "Thanks for reaching out! We'll get back to you soon."
            else:
                if client is None:
                    # Smart fallback response based on user input
                    user_message = data['message'].lower()
                    if 'website' in user_message and ('product' in user_message or 'management' in user_message):
                        ai_reply = "Great! I can help you build a product management system website. This typically includes features like product catalog, inventory tracking, user management, and analytics. Would you like me to provide a detailed project plan?"
                    elif 'hello' in user_message or 'hi' in user_message:
                        ai_reply = "Hello! I'm your AI assistant ready to help with your project. What would you like to build today?"
                    elif 'help' in user_message:
                        ai_reply = "I'm here to help you with your project requirements. Tell me about what you want to build, and I'll provide personalized recommendations and guidance."
                    else:
                        ai_reply = f"I understand you're interested in: {data['message']}. I can help you plan and build this project. Could you provide more details about your specific requirements?"
                    print("❌ Groq client not initialized, using smart fallback response")
                else:
                    try:
                        response = client.chat.completions.create(
                            model="llama-3.1-8b-instant",
                            messages=[
                                {
                                    "role": "system",
                                    "content": "You are a helpful business assistant. Generate a short, professional reply (1-2 lines max) to customer inquiries. Be friendly and encouraging."
                                },
                                {
                                    "role": "user",
                                    "content": f"Customer message: {data['message']}\n\nGenerate a professional reply."
                                }
                            ],
                            max_tokens=50,
                            temperature=0.7
                        )
                    except Exception as e:
                        print(f"❌ Groq API Error: {e}")
                        ai_reply = "I apologize, but I'm experiencing technical difficulties. Please try again later."
                ai_reply = response.choices[0].message.content.strip()
                print(f"AI Reply generated: {ai_reply}")
        except Exception as e:
            error_msg = str(e)
            print(f"Groq API Error: {error_msg}")
            
            # Check for specific error types
            if "insufficient_quota" in error_msg or "429" in error_msg:
                ai_reply = "Thanks for reaching out! We've received your message and will get back to you soon."
            elif "invalid_api_key" in error_msg or "401" in error_msg:
                ai_reply = "Thanks for reaching out! We've received your message and will get back to you soon."
            else:
                ai_reply = "Thanks for reaching out! We've received your message and will get back to you soon."
        
        # Save lead to MongoDB
        success, message, lead_id = save_lead_to_mongodb(
            data['name'], 
            data['email'], 
            data['message'], 
            ai_reply
        )
        
        if not success:
            return jsonify({
                "status": "error",
                "message": message
            }), 500
        
        # Send email to user with AI response
        email_sent = False
        email_message = ""
        
        if ai_reply and data['name'] and data['email']:
            email_success, email_msg = send_email_to_user(data['name'], data['email'], ai_reply)
            email_sent = email_success
            email_message = email_msg
            print(f"Email sending result: {email_msg}")
        
        return jsonify({
            "status": "success",
            "message": "Lead saved successfully",
            "ai_reply": ai_reply,
            "email_sent": email_sent,
            "email_message": email_message,
            "lead_id": lead_id
        })
        
    except Exception as e:
        print(f"❌ Error in save_lead: {traceback.format_exc()}")
        return jsonify({
            "status": "error",
            "message": "Internal server error"
        }), 500

# Chat endpoint for continuous conversation (Updated for MongoDB)
@app.route('/api/chat', methods=['POST'])
def chat_with_ai():
    """
    Chat with AI and save conversation to MongoDB
    """
    try:
        data = request.get_json()
        
        if not data or not data.get('message'):
            return jsonify({
                "status": "error",
                "message": "No message provided"
            }), 400
        
        message = data['message']
        conversation_history = data.get('conversation_history', [])
        email = data.get('email', 'anonymous')
        name = data.get('name', 'Client')  # Extract client name from request
        session_id = data.get('session_id', f"session_{int(time.time())}")
        
        # Save user message to MongoDB
        save_chat_history_to_mongodb(email, session_id, message, 'user', name)
        
        # Build conversation context
        messages = [
            {
                "role": "system",
                "content": """You are a helpful business assistant. Your goal is to gather project requirements efficiently and provide structured responses. Follow these rules:

1. Keep responses concise and well-structured
2. Use proper formatting with clear sections and bullet points
3. Use markdown formatting for better readability:
   - Use **bold** for headers
   - Use bullet points (*) for lists
   - Use numbered lists for steps
   - Use proper line breaks between sections
4. Don't repeat questions already asked
5. When user says 'yes', 'done', 'complete', or 'finished', generate a summary
6. Focus on one topic at a time
7. Be direct and professional
8. Format responses like ChatGPT with clear structure and spacing
9. Always use proper paragraph breaks and formatting
10. CRITICAL: Never add leading spaces or extra whitespace at the beginning of any line. Start each section immediately without indentation. Do not use tabs or spaces to indent content."""
            }
        ]
        
        # Add conversation history
        for msg in conversation_history[-5:]:  # Keep last 5 messages for context
            messages.append({
                "role": msg['role'],
                "content": msg['content']
            })
        
        # Check if user wants to end conversation and generate summary
        completion_indicators = ['yes', 'done', 'complete', 'finished', 'summary', 'that\'s all', 'no more']
        if any(indicator in message.lower() for indicator in completion_indicators) and len(conversation_history) > 4:
            # Generate summary and send final report emails
            return generate_conversation_summary(data)
        
        # Add current message
        messages.append({
            "role": "user",
            "content": message
        })
        
        # Generate AI reply
        ai_reply = ""
        try:
            api_key = os.getenv('GROQ_API_KEY')
            if not api_key or api_key == 'your_groq_api_key_here':
                print("Groq API key not configured properly")
                ai_reply = "I'm here to help! What would you like to build?"
            else:
                response = client.chat.completions.create(
                    model="llama-3.1-8b-instant",
                    messages=messages,
                    max_tokens=500,  # Increased for complete responses
                    temperature=0.5   # Lower for more focused responses
                )
                ai_reply = response.choices[0].message.content.strip()
                print(f"Chat AI Reply: {ai_reply}")
        except Exception as e:
            error_msg = str(e)
            print(f"Groq API Error: {error_msg}")
            ai_reply = "I'm here to help! What would you like to build?"
        
        # Save AI reply to MongoDB (store reply text in message field for timeline display)
        save_chat_history_to_mongodb(email, session_id, ai_reply, 'assistant', name, ai_reply)
        
        return jsonify({
            "status": "success",
            "ai_reply": ai_reply
        })
        
    except Exception as e:
        print(f"❌ Error in chat_with_ai: {traceback.format_exc()}")
        return jsonify({
            "status": "error",
            "message": "Internal server error"
        }), 500

# API endpoint to get all leads for admin (Updated for MongoDB)
@app.route('/api/leads', methods=['GET'])
def get_leads():
    """
    Retrieve all leads from MongoDB for admin dashboard
    """
    try:
        # Check admin authentication
        if not session.get('is_authenticated'):
            return jsonify({
                "status": "error",
                "message": "Authentication required"
            }), 401
        
        success, leads, message = get_all_leads_from_mongodb()
        
        if success:
            return jsonify(leads)
        else:
            return jsonify({
                "status": "error",
                "message": message
            }), 500
            
    except Exception as e:
        print(f"❌ Error in get_leads: {traceback.format_exc()}")
        return jsonify({
            "status": "error",
            "message": "Error loading leads"
        }), 500

@app.route('/api/lead/by-id/<lead_id>', methods=['DELETE'])
def delete_lead_by_id(lead_id):
    """Delete a lead by MongoDB ObjectId (used by admin dashboard)."""
    try:
        lead, lead_oid = find_lead_by_identifier(lead_id)
        if not lead:
            return jsonify({"status": "error", "message": "Lead not found"}), 404
        leads_collection = get_collection('leads')
        result = leads_collection.delete_one({"_id": lead_oid})
        if result.deleted_count > 0:
            return jsonify({"status": "success", "message": "Lead deleted successfully"}), 200
        return jsonify({"status": "error", "message": "Lead not found"}), 404
    except Exception as e:
        print(f"❌ Error deleting lead by id: {e}")
        return jsonify({"status": "error", "message": "Error deleting lead"}), 500

def generate_conversation_summary(data):
    """
    Generate summary when user indicates completion (Updated for MongoDB)
    """
    name = data.get('name', 'Client')
    email = data.get('email', 'client@example.com')
    conversation_history = data.get('conversation_history', [])
    
    # Build summary prompt
    summary_prompt = f"""Based on the following conversation with {name} ({email}), generate a comprehensive project requirements summary:

Conversation:
{chr(10).join([f"{msg['role']}: {msg['content']}" for msg in conversation_history])}

Please provide a structured summary with the following format:

**Project Overview**
[Clear, concise overview of the project]

**Key Requirements**
• Requirement 1
• Requirement 2
• Requirement 3

**Technical Specifications**
• Frontend: [Details]
• Backend: [Details]
• Database: [Details]

**Timeline Considerations**
• Estimated duration: [Timeframe]
• Key milestones

**Budget Considerations**
• Estimated budget: [Range]
• Cost breakdown

**Next Steps**
1. Step 1
2. Step 2
3. Step 3

**Client Contact Information**
• Name: {name}
• Email: {email}

Format with proper markdown, clear sections, bullet points, and professional spacing like ChatGPT. CRITICAL: Do not add any leading spaces, tabs, or extra whitespace at the beginning of any line. Start each section immediately without any indentation. Never use spaces or tabs to format content."""
    
    # Generate AI summary
    summary = ""
    try:
        api_key = os.getenv('GROQ_API_KEY')
        if not api_key or api_key == 'your_groq_api_key_here':
            summary = "Summary generation unavailable. Please check API configuration."
        else:
            response = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a business analyst. Generate professional, structured project summaries based on client conversations. Always provide complete responses with all sections fully written out."
                    },
                    {
                        "role": "user",
                        "content": summary_prompt
                    }
                ],
                max_tokens=2000,
                temperature=0.3
            )
            summary = response.choices[0].message.content.strip()
            print(f"Auto Summary generated: {summary[:100]}...")
    except Exception as e:
        error_msg = str(e)
        print(f"Summary Generation Error: {error_msg}")
        summary = "Error generating summary. Please try again."
    
    # Save lead with summary to MongoDB
    success, message, lead_id = save_lead_to_mongodb(name, email, summary, None, is_summary=True)
    
    # Convert lead_id to string if it's an ObjectId
    if hasattr(lead_id, '__str__'):
        lead_id = str(lead_id)
    
    if not success:
        print(f"Error saving summary to MongoDB: {message}")
    
    # Extract cost estimate from summary instead of generating new one
    cost_estimate = extract_cost_from_summary(summary)
    
    # Generate confirmation token
    import secrets
    confirmation_token = secrets.token_urlsafe(32)
    confirmation_expiry = datetime.now(timezone.utc) + timedelta(days=7)
    
    # Update lead with confirmation token - use email to find the lead instead
    leads_collection = get_collection('leads')
    if leads_collection is not None:
        print(f"🔧 Storing token for email: {email}")
        print(f"🔧 Token: {confirmation_token}")
        print(f"🔧 Expiry: {confirmation_expiry}")
        
        # Find the lead by email (most recent one)
        lead = leads_collection.find_one({"email": email})
        if lead:
            print(f"🔧 Found lead: {lead.get('_id')}")
            
            result = leads_collection.update_one(
                {"_id": lead["_id"]},
                {
                    "$set": {
                        "confirmation_token": confirmation_token,
                        "confirmation_expiry": confirmation_expiry,
                        "cost_estimate": cost_estimate,
                        "project_details": summary
                    }
                }
            )
            
            print(f"🔧 Update result: {result.modified_count} documents modified")
            
            # Verify the token was stored
            verify_lead = leads_collection.find_one({"_id": lead["_id"]})
            if verify_lead:
                print(f"🔧 Verification - Token stored: {verify_lead.get('confirmation_token')}")
                print(f"🔧 Verification - Expiry stored: {verify_lead.get('confirmation_expiry')}")
            else:
                print(f"🔧 ERROR: Could not verify token storage")
        else:
            print(f"🔧 ERROR: Could not find lead with email: {email}")
    else:
        print(f"🔧 ERROR: leads_collection is None")
    
    # Send emails
    admin_email_sent = False
    client_email_sent = False
    admin_email_msg = ""
    client_email_msg = ""
    
    if summary and name and email:
        # Send final report to admin
        admin_success, admin_msg = send_final_report_to_admin(email, name, summary, cost_estimate, lead_id)
        admin_email_sent = admin_success
        admin_email_msg = admin_msg
        print(f"Admin email result: {admin_msg}")
        
        # Send confirmation to client
        client_success, client_msg = send_confirmation_to_client(email, name, summary, cost_estimate, confirmation_token)
        client_email_sent = client_success
        client_email_msg = client_msg
        print(f"Client email result: {client_msg}")
    
    return jsonify({
        "status": "success",
        "ai_reply": summary,
        "is_summary": True,
        "admin_email_sent": admin_email_sent,
        "client_email_sent": client_email_sent,
        "admin_email_message": admin_email_msg,
        "client_email_message": client_email_msg,
        "lead_id": lead_id,
        "confirmation_token": confirmation_token
    })

# Summary endpoint
@app.route('/api/summary', methods=['POST'])
def generate_summary():
    """
    Generate summary from conversation history
    """
    try:
        data = request.get_json()
        
        if not data or not data.get('conversation_history'):
            return jsonify({
                "status": "error",
                "message": "No conversation history provided"
            }), 400
        
        name = data.get('name', 'Client')
        email = data.get('email', 'client@example.com')
        conversation_history = data['conversation_history']
        
        # Build summary prompt
        summary_prompt = f"""
        Based on the following conversation with {name} ({email}), generate a comprehensive project requirements summary:

        Conversation:
        {chr(10).join([f"{msg['role']}: {msg['content']}" for msg in conversation_history])}

        Please provide a structured summary with:
        1. Project Overview
        2. Key Requirements
        3. Technical Specifications
        4. Timeline Considerations
        5. Budget Considerations (if mentioned)
        6. Next Steps

        Format as a professional business summary.
        """
        
        # Generate AI summary
        summary = ""
        try:
            api_key = os.getenv('GROQ_API_KEY')
            if not api_key or api_key == 'your_groq_api_key_here':
                summary = "Summary generation unavailable. Please check API configuration."
            else:
                response = client.chat.completions.create(
                    model="llama-3.1-8b-instant",
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a business analyst. Generate professional, structured project summaries based on client conversations."
                        },
                        {
                            "role": "user",
                            "content": summary_prompt
                        }
                    ],
                    max_tokens=500,
                    temperature=0.3
                )
                summary = response.choices[0].message.content.strip()
                print(f"Summary generated: {summary[:100]}...")
        except Exception as e:
            error_msg = str(e)
            print(f"Summary Generation Error: {error_msg}")
            summary = "Error generating summary. Please try again."
        
        return jsonify({
            "status": "success",
            "summary": summary
        })
        
    except Exception as e:
        print(f"❌ Error in generate_summary: {traceback.format_exc()}")
        return jsonify({
            "status": "error",
            "message": "Internal server error"
        }), 500

# ================================
# DASHBOARD API ENDPOINTS
# ================================

# Memory Dashboard APIs
@app.route('/api/memory/stats', methods=['GET'])
def memory_stats():
    """Get memory system statistics"""
    try:
        # Mock data for now - replace with actual MongoDB queries
        stats = {
            "totalMemories": 1250,
            "activeSessions": 45,
            "contextItems": 320,
            "aiResponses": 890,
            "activity": [
                {
                    "id": "1",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "email": "user@example.com",
                    "session_id": "sess_123",
                    "memory_type": "chat",
                    "content_preview": "User asked about project requirements..."
                },
                {
                    "id": "2", 
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "email": "client@example.com",
                    "session_id": "sess_124",
                    "memory_type": "context",
                    "content_preview": "Updated project preferences and timeline..."
                }
            ]
        }
        return jsonify(stats)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/memory/clear-old', methods=['POST'])
def clear_old_memories():
    """Clear old memory entries"""
    return jsonify({"status": "success", "message": "Old memories cleared successfully"})

@app.route('/api/memory/optimize', methods=['POST'])
def optimize_memory():
    """Optimize memory storage"""
    return jsonify({"status": "success", "message": "Memory optimization completed"})

@app.route('/api/memory/export')
def export_memory():
    """Export memory data"""
    return jsonify({"status": "success", "message": "Memory export started"})

# Context Dashboard APIs
@app.route('/api/context/stats', methods=['GET'])
def context_stats():
    """Get context system statistics"""
    try:
        stats = {
            "totalContexts": 850,
            "activeProjects": 25,
            "userProfiles": 120,
            "contextAccuracy": 87,
            "updates": [
                {
                    "id": "1",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "user": "john@example.com",
                    "context_type": "project",
                    "project": "E-commerce Platform",
                    "update_summary": "Added new feature requirements",
                    "confidence": 92
                },
                {
                    "id": "2",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "user": "jane@example.com", 
                    "context_type": "user",
                    "project": "Mobile App",
                    "update_summary": "Updated user preferences",
                    "confidence": 88
                }
            ]
        }
        return jsonify(stats)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/context/search')
def search_context():
    """Search context data"""
    query = request.args.get('q', '')
    return jsonify([
        {"title": f"Result for {query}", "description": "Sample search result", "updated_at": datetime.now(timezone.utc).isoformat()}
    ])

@app.route('/api/context/rebuild', methods=['POST'])
def rebuild_context():
    """Rebuild context index"""
    return jsonify({"status": "success", "message": "Context index rebuild started"})

@app.route('/api/context/analyze', methods=['POST'])
def analyze_context():
    """Analyze context patterns"""
    return jsonify({"status": "success", "message": "Context analysis completed"})

@app.route('/api/context/export')
def export_context():
    """Export context data"""
    return jsonify({"status": "success", "message": "Context export started"})

# Analytics Dashboard APIs
@app.route('/api/analytics/stats', methods=['GET'])
def analytics_stats():
    """Get analytics statistics"""
    try:
        period = request.args.get('period', 'month')
        stats = {
            "kpis": {
                "totalLeads": 1250,
                "conversionRate": 12.5,
                "aiResponses": 890,
                "avgResponseTime": 3.2
            },
            "charts": {
                "leadTrends": {
                    "labels": ["Week 1", "Week 2", "Week 3", "Week 4"],
                    "newLeads": [45, 52, 48, 58],
                    "convertedLeads": [5, 7, 6, 8]
                },
                "leadSources": [35, 25, 20, 15, 5],
                "leadQuality": [45, 65, 30, 10],
                "aiPerformance": {
                    "current": [85, 90, 78, 82, 88],
                    "previous": [80, 85, 75, 78, 82]
                }
            },
            "activity": [
                {
                    "id": "1",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "name": "John Doe",
                    "email": "john@example.com",
                    "lead_score": 85,
                    "status": "qualified",
                    "ai_response": True
                },
                {
                    "id": "2",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "name": "Jane Smith",
                    "email": "jane@example.com",
                    "lead_score": 72,
                    "status": "contacted",
                    "ai_response": True
                }
            ]
        }
        return jsonify(stats)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/analytics/export')
def export_analytics():
    """Export analytics report"""
    period = request.args.get('period', 'month')
    return jsonify({"status": "success", "message": f"Analytics export for {period} started"})

def open_browser():
    """Open browser after a short delay"""
    time.sleep(1.5)  # Wait for server to start
    webbrowser.open('http://127.0.0.1:5000')

@app.route('/api/approve-changes/<lead_id>', methods=['POST'])
def approve_changes(lead_id):
    """Approve client changes, notify client (email + real-time), send new confirm link."""
    try:
        data = request.get_json() or {}
        admin_response = data.get('admin_response', '')
        internal_notes = data.get('internal_notes') or data.get('admin_notes', '')
        
        leads_collection = get_collection('leads')
        if leads_collection is None:
            return jsonify({"status": "error", "message": "Database connection error"}), 500
        
        lead, lead_oid = find_lead_by_identifier(lead_id)
        if not lead:
            print(f"❌ approve-changes: lead not found for id={lead_id}")
            return jsonify({"status": "error", "message": "Lead not found"}), 404
        
        confirmation_token = secrets.token_urlsafe(32)
        confirmation_expiry = datetime.now(timezone.utc) + timedelta(days=7)
        
        leads_collection.update_one(
            {"_id": lead_oid},
            {
                "$set": {
                    "status": "changes_approved",
                    "admin_response": admin_response,
                    "internal_notes": internal_notes,
                    "admin_response_date": datetime.now(timezone.utc),
                    "confirmation_token": confirmation_token,
                    "confirmation_expiry": confirmation_expiry,
                    "approved_by": session.get('admin_username', 'admin'),
                }
            }
        )
        
        lead_id_str = str(lead_oid)
        socketio.emit('changes_approved', {
            "lead_id": lead_id_str,
            "status": "changes_approved",
            "admin_response": admin_response,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }, room=f"lead_{lead_id_str}")
        socketio.emit('changes_approved_realtime', {
            "lead_id": lead_id_str,
            "admin_response": admin_response,
            "status": "approved",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }, room=f"lead_{lead_id_str}")
        
        send_change_approval_email(
            lead.get('email'),
            lead.get('name', 'Client'),
            admin_response,
            confirmation_token,
        )
        
        print(f"✅ Changes approved for lead {lead_id_str}")
        return jsonify({
            "status": "success",
            "message": "Changes approved and client notified in real-time",
        }), 200
        
    except Exception as e:
        print(f"❌ Error approving changes: {e}")
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/request-clarification/<lead_id>', methods=['POST'])
def request_clarification(lead_id):
    """Request clarification from client"""
    try:
        data = request.get_json()
        admin_response = data.get('admin_response', '')
        
        # Get leads collection
        leads_collection = get_collection('leads')
        if leads_collection is None:
            return jsonify({"status": "error", "message": "Database connection error"}), 500
        
        lead, lead_oid = find_lead_by_identifier(lead_id)
        if not lead:
            return jsonify({"status": "error", "message": "Lead not found"}), 404
        
        leads_collection.update_one(
            {"_id": lead_oid},
            {
                "$set": {
                    "status": "clarification_requested",
                    "admin_response": admin_response,
                    "admin_response_date": datetime.now(timezone.utc)
                }
            }
        )
        
        # Send email to client requesting clarification
        try:
            email_subject = f"❓ Clarification Needed - {lead.get('name', 'Client')}"
            email_content = f"""
Dear {lead.get('name', 'Client')},

Thank you for your change request. We need some clarification to proceed with your request.

Admin Response/Questions:
{admin_response}

Original Project Details:
{lead.get('project_details', 'No details available')}

Original Cost Estimate:
{lead.get('cost_estimate', 'No cost estimate available')}

Please respond to this email with the requested clarification, and we'll update your proposal accordingly.

Best regards,
AI Lead Automation Team
"""
            
            send_email_via_python_smtp(
                lead.get('email'),
                email_subject,
                email_content
            )
            
            print(f"✅ Clarification request email sent to {lead.get('email')}")
            
        except Exception as e:
            print(f"❌ Error sending clarification email: {e}")
        
        lead_id_str = str(lead_oid)
        socketio.emit('clarification_requested', {
            "lead_id": lead_id_str,
            "admin_response": admin_response,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }, room=f"lead_{lead_id_str}")
        
        return jsonify({
            "status": "success",
            "message": "Clarification request sent to client"
        })
        
    except Exception as e:
        print(f"❌ Error requesting clarification: {e}")
        return jsonify({"status": "error", "message": "Error requesting clarification"}), 500

@app.route('/api/reject-changes/<lead_id>', methods=['POST'])
def reject_changes(lead_id):
    """Reject client changes and notify client (email + real-time)."""
    try:
        data = request.get_json() or {}
        admin_response = data.get('admin_response', '')
        admin_notes = data.get('internal_notes') or data.get('admin_notes', '')
        
        leads_collection = get_collection('leads')
        if leads_collection is None:
            return jsonify({"status": "error", "message": "Database connection error"}), 500
        
        lead, lead_oid = find_lead_by_identifier(lead_id)
        if not lead:
            return jsonify({"status": "error", "message": "Lead not found"}), 404
        
        leads_collection.update_one(
            {"_id": lead_oid},
            {
                "$set": {
                    "status": "changes_rejected",
                    "admin_response": admin_response,
                    "admin_notes": admin_notes,
                    "internal_notes": admin_notes,
                    "admin_response_date": datetime.now(timezone.utc),
                    "rejected_by": session.get('admin_username', 'admin'),
                }
            }
        )
        
        lead_id_str = str(lead_oid)
        socketio.emit('changes_rejected', {
            "lead_id": lead_id_str,
            "status": "changes_rejected",
            "admin_response": admin_response,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }, room=f"lead_{lead_id_str}")
        socketio.emit('changes_rejected_realtime', {
            "lead_id": lead_id_str,
            "admin_response": admin_response,
            "status": "rejected",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }, room=f"lead_{lead_id_str}")
        
        send_change_rejection_email(
            lead.get('email'),
            lead.get('name', 'Client'),
            admin_response,
        )
        
        print(f"✅ Changes rejected for lead {lead_id_str}")
        return jsonify({
            "status": "success",
            "message": "Changes rejected and client notified in real-time",
        }), 200
        
    except Exception as e:
        print(f"❌ Error rejecting changes: {e}")
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500

# ================================
# CLIENT AUTHENTICATION ROUTES
# ================================

@app.route('/client_login')
def client_login_page():
    """Serve the client portal (signup / password / OTP)."""
    return render_template('client_login.html')


@app.route('/client_chat')
def client_chat_page():
    """Serve client chat (requires session)."""
    if not session.get('client_authenticated'):
        return render_template('client_login.html')
    return render_template('client_chat.html')


@app.route('/api/client/signup', methods=['POST'])
def client_signup():
    """Create a client account (email must already have a project lead)."""
    try:
        data = request.get_json() or {}
        email = normalize_email(data.get('email', ''))
        name = (data.get('name') or '').strip()
        password = data.get('password', '')

        if not re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]+$', email):
            return jsonify({'status': 'error', 'message': 'Invalid email'}), 400

        is_valid, pwd_error = PasswordValidator.validate_password(password)
        if not is_valid:
            return jsonify({'status': 'error', 'message': pwd_error}), 400

        lead, lead_oid = find_lead_by_email(email)
        if not lead:
            return jsonify({
                'status': 'error',
                'message': 'No project found for this email. Complete the AI chat on the homepage first.',
            }), 404

        clients_collection = get_collection('clients')
        if clients_collection is None:
            return jsonify({'status': 'error', 'message': 'Database error'}), 500

        if clients_collection.find_one({'email': email}):
            return jsonify({
                'status': 'error',
                'message': 'An account already exists. Please log in or use email code.',
            }), 409

        display_name = name or lead.get('name') or 'Client'
        hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        client_doc = {
            'email': email,
            'name': display_name,
            'password': hashed,
            'primary_lead_id': lead_oid,
            'lead_ids': [lead_oid],
            'email_verified': True,
            'is_active': True,
            'created_at': datetime.now(timezone.utc),
            'last_login': None,
        }
        result = clients_collection.insert_one(client_doc)
        client_doc['_id'] = result.inserted_id

        _bind_client_session_from_lead(lead, lead_oid, client_doc)
        clients_collection.update_one(
            {'_id': result.inserted_id},
            {'$set': {'last_login': datetime.now(timezone.utc)}},
        )
        return _client_auth_response(lead)
    except Exception as e:
        print(f"❌ client signup: {e}")
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': 'Server error'}), 500


@app.route('/api/client/login', methods=['POST'])
def client_login():
    """Client login with email + password."""
    try:
        data = request.get_json() or {}
        email = normalize_email(data.get('email', ''))
        password = data.get('password', '')

        if not email or not password:
            return jsonify({'status': 'error', 'message': 'Email and password required'}), 400

        client = find_client_by_email(email)
        if not client or not client.get('password'):
            return jsonify({'status': 'error', 'message': 'Invalid email or password'}), 401

        if not client.get('is_active', True):
            return jsonify({'status': 'error', 'message': 'Account is deactivated'}), 403

        if not bcrypt.checkpw(password.encode('utf-8'), client['password'].encode('utf-8')):
            return jsonify({'status': 'error', 'message': 'Invalid email or password'}), 401

        lead, lead_oid = find_lead_by_identifier(str(client.get('primary_lead_id', '')))
        if not lead:
            lead, lead_oid = find_lead_by_email(email)
        if not lead:
            return jsonify({
                'status': 'error',
                'message': 'Project not found for this account.',
            }), 404

        _bind_client_session_from_lead(lead, lead_oid, client)
        get_collection('clients').update_one(
            {'_id': client['_id']},
            {'$set': {'last_login': datetime.now(timezone.utc)}},
        )
        return _client_auth_response(lead)
    except Exception as e:
        print(f"❌ client login: {e}")
        return jsonify({'status': 'error', 'message': 'Server error'}), 500


@app.route('/api/client/register', methods=['POST'])
def client_register():
    """Backward-compatible alias → signup."""
    return client_signup()


@app.route('/api/client/request-otp', methods=['POST'])
def client_request_otp():
    """Send a 6-digit login code to the client's email."""
    try:
        data = request.get_json() or {}
        email = normalize_email(data.get('email', ''))
        if not re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]+$', email):
            return jsonify({'status': 'error', 'message': 'Invalid email'}), 400

        lead, lead_oid = find_lead_by_email(email)
        if not lead:
            return jsonify({
                'status': 'error',
                'message': 'No project found for this email.',
            }), 404

        otp_code = f"{secrets.randbelow(1000000):06d}"
        otp_expiry = datetime.now(timezone.utc) + timedelta(minutes=10)
        clients_collection = get_collection('clients')
        if clients_collection is None:
            return jsonify({'status': 'error', 'message': 'Database error'}), 500

        name = lead.get('name') or 'Client'
        existing = clients_collection.find_one({'email': email})
        update_fields = {
            'otp_code': otp_code,
            'otp_expiry': otp_expiry,
            'otp_attempts': 0,
        }
        if existing:
            clients_collection.update_one({'email': email}, {'$set': update_fields})
        else:
            clients_collection.insert_one({
                'email': email,
                'name': name,
                'password': None,
                'primary_lead_id': lead_oid,
                'lead_ids': [lead_oid],
                'email_verified': False,
                'is_active': True,
                'created_at': datetime.now(timezone.utc),
                **update_fields,
            })

        send_client_otp_email(lead.get('email', email), name, otp_code)
        return jsonify({
            'status': 'success',
            'message': 'Login code sent to your email (valid 10 minutes).',
        }), 200
    except Exception as e:
        print(f"❌ request-otp: {e}")
        return jsonify({'status': 'error', 'message': 'Server error'}), 500


@app.route('/api/client/verify-otp', methods=['POST'])
def client_verify_otp():
    """Log in using email + one-time code."""
    try:
        data = request.get_json() or {}
        email = normalize_email(data.get('email', ''))
        otp = (data.get('otp') or data.get('code') or '').strip()

        if not email or not otp:
            return jsonify({'status': 'error', 'message': 'Email and code required'}), 400

        client = find_client_by_email(email)
        if not client:
            return jsonify({'status': 'error', 'message': 'Request a code first'}), 400

        stored = client.get('otp_code')
        expiry = client.get('otp_expiry')
        if not stored or not expiry or datetime.now(timezone.utc) > expiry:
            return jsonify({'status': 'error', 'message': 'Code expired. Request a new one.'}), 400

        if otp != stored:
            get_collection('clients').update_one(
                {'email': email},
                {'$inc': {'otp_attempts': 1}},
            )
            return jsonify({'status': 'error', 'message': 'Invalid code'}), 401

        lead, lead_oid = find_lead_by_identifier(str(client.get('primary_lead_id', '')))
        if not lead:
            lead, lead_oid = find_lead_by_email(email)
        if not lead:
            return jsonify({'status': 'error', 'message': 'Project not found'}), 404

        get_collection('clients').update_one(
            {'email': email},
            {
                '$set': {
                    'last_login': datetime.now(timezone.utc),
                    'email_verified': True,
                    'otp_code': None,
                    'otp_expiry': None,
                },
            },
        )
        client = find_client_by_email(email)
        _bind_client_session_from_lead(lead, lead_oid, client)
        return _client_auth_response(lead)
    except Exception as e:
        print(f"❌ verify-otp: {e}")
        return jsonify({'status': 'error', 'message': 'Server error'}), 500


@app.route('/api/client/me', methods=['GET'])
def client_me():
    """Current client session + lead status."""
    if not session.get('client_authenticated'):
        return jsonify({'status': 'error', 'message': 'Not authenticated'}), 401
    lead, _ = find_lead_by_identifier(session.get('client_lead_id', ''))
    if not lead:
        lead, _ = find_lead_by_email(session.get('client_email', ''))
    client = find_client_by_email(session.get('client_email', ''))
    return jsonify({
        'status': 'success',
        'email': session.get('client_email'),
        'name': session.get('client_name'),
        'lead_id': session.get('client_lead_id'),
        'has_password': bool(client and client.get('password')),
        'lead_status': lead.get('status') if lead else None,
        'admin_response': lead.get('admin_response') if lead else None,
        'change_request': normalize_change_request(lead.get('change_request')) if lead else None,
    }), 200


@app.route('/api/client/logout', methods=['POST'])
def client_logout():
    """Logout client (keeps admin session if present)."""
    try:
        for key in (
            'client_email', 'client_name', 'client_lead_id', 'client_session_id',
            'client_authenticated', 'client_id',
        ):
            session.pop(key, None)
        return jsonify({'status': 'success', 'message': 'Logged out'}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': 'Logout failed'}), 500

@app.route('/api/chat-history/<email>', methods=['GET'])
def get_chat_history(email):
    """Get chat history for a client email"""
    try:
        # Check client authentication
        if not session.get('client_authenticated'):
            return jsonify({'status': 'error', 'message': 'Authentication required'}), 401
        
        email = normalize_email(email)
        lead, lead_oid = find_lead_by_email(email)
        
        if not lead:
            return jsonify({'status': 'error', 'message': 'Lead not found'}), 404
        
        # Get chat history from MongoDB
        chat_collection = get_collection('chat_history')
        if chat_collection is None:
            return jsonify({'status': 'error', 'message': 'Database error'}), 500
        
        # Get chat messages for this email
        chat_messages = list(chat_collection.find(
            {'email': email},
            sort=[('timestamp', 1)]
        ))
        
        # Convert ObjectId to string for JSON serialization
        timeline = []
        for msg in chat_messages:
            timeline.append({
                'role': msg.get('role'),
                'content': msg.get('message'),
                'timestamp': msg.get('timestamp').isoformat() if msg.get('timestamp') else None,
                'name': msg.get('name')
            })
        
        return jsonify({
            'status': 'success',
            'lead_id': str(lead_oid),
            'timeline': timeline,
            'messages': timeline,
            'lead_status': lead.get('status'),
            'admin_response': lead.get('admin_response')
        }), 200
        
    except Exception as e:
        print(f"❌ Error getting chat history: {e}")
        return jsonify({'status': 'error', 'message': 'Error loading chat history'}), 500

@app.route('/api/send-client-message', methods=['POST'])
def send_client_message():
    """Send a message from client to admin"""
    try:
        # Check client authentication
        if not session.get('client_authenticated'):
            return jsonify({'status': 'error', 'message': 'Authentication required'}), 401
        
        data = request.get_json()
        client_email = normalize_email(data.get('client_email', ''))
        message = data.get('message', '').strip()
        
        if not message:
            return jsonify({'status': 'error', 'message': 'Message is required'}), 400
        
        lead, lead_oid = find_lead_by_email(client_email)
        if not lead:
            return jsonify({'status': 'error', 'message': 'Lead not found'}), 404
        
        # Save message to messages collection
        messages_collection = get_collection('messages')
        if messages_collection is None:
            return jsonify({'status': 'error', 'message': 'Database error'}), 500
        
        message_doc = {
            'lead_id': lead_oid,
            'sender_type': 'client',
            'sender_name': session.get('client_name', 'Client'),
            'sender_email': client_email,
            'message': message,
            'timestamp': datetime.now(timezone.utc),
            'read': False
        }
        
        messages_collection.insert_one(message_doc)
        
        # Emit via Socket.IO to admin dashboard
        socketio.emit('new_message', {
            'lead_id': str(lead_oid),
            'sender_type': 'client',
            'sender_name': session.get('client_name', 'Client'),
            'message': message,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }, room='admin_dashboard')
        
        return jsonify({'status': 'success', 'message': 'Message sent'}), 200
        
    except Exception as e:
        print(f"❌ Error sending client message: {e}")
        return jsonify({'status': 'error', 'message': 'Error sending message'}), 500

@app.route('/api/submit-change-request/<token>', methods=['POST'])
def submit_change_request(token):
    """Client submits change request - broadcasts to admin in real-time"""
    try:
        data = request.get_json()
        requested_changes = data.get('requested_changes', '')
        budget_changes = data.get('budget_changes', '')
        
        leads_collection = get_collection('leads')
        if leads_collection is None:
            return jsonify({"status": "error", "message": "Database connection error"}), 500
        
        # Find lead by confirmation token
        lead = leads_collection.find_one({"confirmation_token": token})
        if not lead:
            return jsonify({"status": "error", "message": "Invalid token"}), 404
        
        change_payload = {
            "changes": requested_changes,
            "requested_changes": requested_changes,
            "budget_changes": budget_changes,
            "requested_at": datetime.now(timezone.utc),
            "client_email": lead.get('email'),
            "client_name": lead.get('name'),
        }
        leads_collection.update_one(
            {"confirmation_token": token},
            {"$set": {"status": "changes_requested", "change_request": change_payload}},
        )
        updated_lead = leads_collection.find_one({"_id": lead["_id"]})
        if updated_lead:
            emit_new_change_request_to_admins(updated_lead)
        
        # Send email notification to admin
        admin_email = os.getenv('ADMIN_EMAIL', 'nikhilsalunkhe9404@gmail.com')
        send_change_request_notification_email(
            admin_email,
            lead.get('name'),
            lead.get('email'),
            requested_changes,
            budget_changes,
            str(lead.get('_id'))
        )
        
        print(f"✅ Change request submitted by {lead.get('email')}")
        
        return jsonify({
            "status": "success",
            "message": "Change request submitted and admin notified in real-time"
        }), 200
        
    except Exception as e:
        print(f"❌ Error submitting change request: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# ================================
# REAL-TIME MESSAGING ROUTES
# ================================

@app.route('/api/chat-history/<email>', methods=['GET'])
def chat_history_by_email(email):
    """Unified timeline: AI requirements chat + admin/client support messages."""
    try:
        if not session.get('client_authenticated'):
            return jsonify({'status': 'error', 'message': 'Please log in first'}), 401

        session_email = normalize_email(session.get('client_email') or email)
        if normalize_email(email) != session_email:
            return jsonify({'status': 'error', 'message': 'Unauthorized'}), 403

        lead, lead_oid = find_lead_by_email(session_email)
        if not lead:
            return jsonify({
                'status': 'success',
                'messages': [],
                'timeline': [],
                'lead_id': None,
            }), 200

        timeline = build_unified_conversation_timeline(session_email, lead_oid)
        return jsonify({
            'status': 'success',
            'messages': timeline,
            'timeline': timeline,
            'lead_id': str(lead_oid),
            'lead_status': lead.get('status'),
            'admin_response': lead.get('admin_response'),
            'project_details': lead.get('project_details'),
            'cost_estimate': lead.get('cost_estimate'),
        }), 200
    except Exception as e:
        print(f"❌ Error loading chat history: {e}")
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/send-client-message', methods=['POST'])
def send_client_message_api():
    """Client sends a chat message (resolves lead from email)."""
    try:
        data = request.get_json() or {}
        if not session.get('client_authenticated'):
            return jsonify({'status': 'error', 'message': 'Please log in first'}), 401

        email = normalize_email(data.get('client_email') or session.get('client_email') or '')
        message = (data.get('message') or '').strip()
        if not email or not message:
            return jsonify({'status': 'error', 'message': 'Email and message required'}), 400

        lead, lead_oid = find_lead_by_email(email)
        if not lead:
            return jsonify({"status": "error", "message": "No project found for this email"}), 404

        session['client_email'] = email
        session['client_name'] = session.get('client_name') or lead.get('name', 'Client')
        session['client_lead_id'] = str(lead_oid)
        session['client_authenticated'] = True

        messages_collection = get_collection('messages')
        if messages_collection is None:
            return jsonify({"status": "error", "message": "Database error"}), 500

        lead_id_str = str(lead_oid)
        message_doc = {
            "lead_id": lead_oid,
            "sender_type": "client",
            "sender_name": session.get('client_name') or lead.get('name', 'Client'),
            "sender_email": email,
            "message": message,
            "timestamp": datetime.now(timezone.utc),
            "read": False,
        }
        result = messages_collection.insert_one(message_doc)
        socketio.emit('new_message', {
            "lead_id": lead_id_str,
            "message_id": str(result.inserted_id),
            "sender_type": "client",
            "sender_name": message_doc["sender_name"],
            "message": message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }, room=f"lead_{lead_id_str}")

        return jsonify({
            "status": "success",
            "message": "Message sent",
            "message_id": str(result.inserted_id),
        }), 200
    except Exception as e:
        print(f"❌ Error in send-client-message: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/send-message/<lead_id>', methods=['POST'])
def send_message(lead_id):
    """Send a message in the chat (admin to client or client to admin)"""
    try:
        data = request.get_json() or {}
        message = data.get('message', '').strip()
        sender_type = data.get('sender_type', '')  # 'admin' or 'client'
        
        if not message:
            return jsonify({"status": "error", "message": "Message cannot be empty"}), 400
        
        if sender_type not in ['admin', 'client']:
            return jsonify({"status": "error", "message": "Invalid sender type"}), 400
        
        messages_collection = get_collection('messages')
        if messages_collection is None:
            return jsonify({"status": "error", "message": "Database error"}), 500
        
        lead, lead_obj_id = find_lead_by_identifier(lead_id)
        if not lead:
            return jsonify({"status": "error", "message": "Invalid lead ID"}), 400
        
        # Store message
        message_doc = {
            "lead_id": lead_obj_id,
            "sender_type": sender_type,
            "sender_name": session.get('admin_username') if sender_type == 'admin' else session.get('client_name'),
            "sender_email": session.get('admin_email') if sender_type == 'admin' else session.get('client_email'),
            "message": message,
            "timestamp": datetime.now(timezone.utc),
            "read": False
        }
        
        result = messages_collection.insert_one(message_doc)
        lead_id_str = str(lead_obj_id)
        
        # Broadcast message to all connected clients in real-time
        socketio.emit('new_message', {
            "lead_id": lead_id_str,
            "message_id": str(result.inserted_id),
            "sender_type": sender_type,
            "sender_name": message_doc["sender_name"],
            "message": message,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }, room=f"lead_{lead_id_str}")
        
        print(f"💬 Message sent by {sender_type} for lead {lead_id_str}")
        
        return jsonify({
            "status": "success",
            "message": "Message sent and broadcast in real-time",
            "message_id": str(result.inserted_id)
        }), 200
        
    except Exception as e:
        print(f"❌ Error sending message: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/get-messages/<lead_id>', methods=['GET'])
def get_messages(lead_id):
    """Get all messages for a lead"""
    try:
        messages_collection = get_collection('messages')
        if messages_collection is None:
            return jsonify({"status": "error", "message": "Database error"}), 500
        
        _, lead_obj_id = find_lead_by_identifier(lead_id)
        if not lead_obj_id:
            return jsonify({"status": "error", "message": "Invalid lead ID"}), 400
        
        # Retrieve all messages sorted by timestamp
        messages = list(messages_collection.find(
            {"lead_id": lead_obj_id}
        ).sort("timestamp", 1))
        
        # Format messages
        formatted_messages = []
        for msg in messages:
            formatted_messages.append({
                "message_id": str(msg.get('_id')),
                "sender_type": msg.get('sender_type'),
                "sender_name": msg.get('sender_name'),
                "message": msg.get('message'),
                "timestamp": msg.get('timestamp').isoformat() if msg.get('timestamp') else None,
                "read": msg.get('read', False)
            })
        
        return jsonify({
            "status": "success",
            "messages": formatted_messages
        }), 200
        
    except Exception as e:
        print(f"❌ Error retrieving messages: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# ================================
# EMAIL NOTIFICATION FUNCTIONS
# ================================

def send_change_approval_email(client_email, client_name, admin_response, confirmation_token):
    """Send email when admin approves changes"""
    try:
        html_content = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background: linear-gradient(135deg, #10b981 0%, #059669 100%); color: white; padding: 30px; border-radius: 10px 10px 0 0; text-align: center;">
                <h2>✅ Your Changes Have Been Approved!</h2>
            </div>
            
            <div style="background: #f8f9fa; padding: 30px; border: 1px solid #e5e7eb;">
                <p>Hello <strong>{client_name}</strong>,</p>
                
                <p>Great news! We've reviewed your requested changes and they've been approved and incorporated into your project proposal.</p>
                
                <div style="background: white; padding: 20px; border-left: 4px solid #10b981; margin: 20px 0;">
                    <h3>📝 Admin Response:</h3>
                    <p>{admin_response}</p>
                </div>
                
                <div style="background: #ecfdf5; padding: 20px; border-radius: 5px; margin: 20px 0;">
                    <p>Your updated project proposal is ready for review. Please confirm your approval by clicking the button below:</p>
                    <p style="text-align: center; margin: 20px 0;">
                        <a href="{get_public_base_url()}/api/confirm-project/{confirmation_token}" style="background: #10b981; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; display: inline-block;">
                            ✅ Confirm & Approve Project
                        </a>
                    </p>
                </div>
                
                <p>This confirmation link is valid for 7 days.</p>
                <p>If you have any questions, feel free to reply to this email or chat with us in your dashboard.</p>
            </div>
            
            <div style="text-align: center; margin-top: 20px; color: #666; font-size: 12px;">
                <p>© 2026 AI Lead Automation. All rights reserved.</p>
            </div>
        </div>
        """
        
        send_email_via_python_smtp(client_email, f"✅ Your Changes Have Been Approved - {client_name}", html_content)
        
    except Exception as e:
        print(f"❌ Error sending change approval email: {e}")

def send_change_rejection_email(client_email, client_name, admin_response):
    """Send email when admin rejects changes"""
    try:
        html_content = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%); color: white; padding: 30px; border-radius: 10px 10px 0 0; text-align: center;">
                <h2>📝 Feedback on Your Change Request</h2>
            </div>
            
            <div style="background: #f8f9fa; padding: 30px; border: 1px solid #e5e7eb;">
                <p>Hello <strong>{client_name}</strong>,</p>
                
                <p>Thank you for submitting your change request. We've reviewed it and have some feedback to share.</p>
                
                <div style="background: white; padding: 20px; border-left: 4px solid #f59e0b; margin: 20px 0;">
                    <h3>💬 Admin Response:</h3>
                    <p>{admin_response}</p>
                </div>
                
                <p>We'd love to work with you to find the best solution. Please reply to this email with your thoughts, or chat with us directly in your dashboard for real-time discussion.</p>
                
                <p>Our team is here to help! 🚀</p>
            </div>
            
            <div style="text-align: center; margin-top: 20px; color: #666; font-size: 12px;">
                <p>© 2026 AI Lead Automation. All rights reserved.</p>
            </div>
        </div>
        """
        
        send_email_via_python_smtp(client_email, f"📝 Feedback on Your Changes - {client_name}", html_content)
        
    except Exception as e:
        print(f"❌ Error sending change rejection email: {e}")

def send_change_request_notification_email(admin_email, client_name, client_email, requested_changes, budget_changes, lead_id):
    """Send email to admin when client requests changes"""
    try:
        html_content = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%); color: white; padding: 30px; border-radius: 10px 10px 0 0; text-align: center;">
                <h2>🔔 New Change Request from Client</h2>
            </div>
            
            <div style="background: #f8f9fa; padding: 30px; border: 1px solid #e5e7eb;">
                <p>You have received a new change request from a client:</p>
                
                <div style="background: white; padding: 20px; border-left: 4px solid #3b82f6; margin: 20px 0;">
                    <h3>👤 Client Information:</h3>
                    <p><strong>Name:</strong> {client_name}</p>
                    <p><strong>Email:</strong> {client_email}</p>
                    <p><strong>Lead ID:</strong> {lead_id}</p>
                </div>
                
                <div style="background: #eff6ff; padding: 20px; border-radius: 5px; margin: 20px 0;">
                    <h3>📝 Requested Changes:</h3>
                    <p>{requested_changes}</p>
                    
                    <h3 style="margin-top: 15px;">💰 Budget Changes:</h3>
                    <p>{budget_changes if budget_changes else 'No budget changes requested'}</p>
                </div>
                
                <p style="text-align: center; margin: 20px 0;">
                    <a href="{os.getenv('PUBLIC_BASE_URL', 'http://127.0.0.1:5000').rstrip('/')}/admin_dashboard" style="background: #3b82f6; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; display: inline-block;">
                        🔍 View in Admin Dashboard
                    </a>
                </p>
            </div>
            
            <div style="text-align: center; margin-top: 20px; color: #666; font-size: 12px;">
                <p>© 2026 AI Lead Automation. All rights reserved.</p>
            </div>
        </div>
        """
        
        send_email_via_python_smtp(admin_email, f"🔔 New Change Request from {client_name}", html_content)
        
    except Exception as e:
        print(f"❌ Error sending change request notification email: {e}")


# ================================
# WEBSOCKET EVENT HANDLERS (must register before server start)
# ================================

@socketio.on('connect')
def handle_connect():
    print(f"✅ Client connected: {request.sid}")
    emit('connection_response', {'data': 'Connected to real-time server'})


@socketio.on('disconnect')
def handle_disconnect():
    print(f"❌ Client disconnected: {request.sid}")


@socketio.on('join_lead_room')
def on_join_lead_room(data):
    try:
        lead_id = data.get('lead_id')
        user_type = data.get('user_type')
        if not lead_id:
            emit('error', {'message': 'Lead ID required'})
            return
        room_name = f"lead_{lead_id}"
        join_room(room_name)
        print(f"👤 {user_type} joined room: {room_name}")
        emit('room_joined', {
            'room': room_name,
            'user_type': user_type,
            'timestamp': datetime.now(timezone.utc).isoformat(),
        }, room=room_name)
    except Exception as e:
        print(f"❌ Error joining room: {e}")
        emit('error', {'message': 'Error joining room'})


@socketio.on('join_admin_dashboard')
def on_join_admin_dashboard():
    try:
        join_room('admin_dashboard')
        admin_username = session.get('admin_username', 'admin')
        print(f"👨‍💼 Admin {admin_username} joined admin dashboard")
        emit('admin_joined', {
            'admin_username': admin_username,
            'timestamp': datetime.now(timezone.utc).isoformat(),
        }, room='admin_dashboard')
    except Exception as e:
        print(f"❌ Error joining admin dashboard: {e}")
        emit('error', {'message': 'Error joining dashboard'})


@socketio.on('leave_lead_room')
def on_leave_lead_room(data):
    try:
        lead_id = data.get('lead_id')
        room_name = f"lead_{lead_id}"
        leave_room(room_name)
        emit('room_left', {
            'room': room_name,
            'timestamp': datetime.now(timezone.utc).isoformat(),
        }, room=room_name)
    except Exception as e:
        print(f"❌ Error leaving room: {e}")


@socketio.on('send_message')
def on_send_message(data):
    try:
        lead_id = data.get('lead_id')
        message = (data.get('message') or '').strip()
        sender_type = data.get('sender_type')
        if not message or not lead_id:
            emit('error', {'message': 'Message and lead ID required'})
            return
        room_name = f"lead_{lead_id}"
        socketio.emit('message_received', {
            'lead_id': lead_id,
            'sender_type': sender_type,
            'sender_name': session.get('admin_username') or session.get('client_name'),
            'message': message,
            'timestamp': datetime.now(timezone.utc).isoformat(),
        }, room=room_name)
    except Exception as e:
        print(f"❌ Error sending message: {e}")
        emit('error', {'message': 'Error sending message'})


@socketio.on('typing_indicator')
def on_typing_indicator(data):
    try:
        lead_id = data.get('lead_id')
        room_name = f"lead_{lead_id}"
        socketio.emit('user_typing', {
            'lead_id': lead_id,
            'user_type': data.get('user_type'),
            'is_typing': data.get('is_typing'),
        }, room=room_name, skip_sid=request.sid)
    except Exception as e:
        print(f"❌ Error broadcasting typing indicator: {e}")


# Run the app
if __name__ == '__main__':
    # Test MongoDB connection on startup
    if mongo_database is not None:
        print("🚀 Starting Flask app with MongoDB Atlas connected")
    else:
        print("⚠️ Starting Flask app without MongoDB connection")
        print("Please check your MONGODB_URI in .env file")
    
    print("🔗 WebSocket server initialized for real-time communications")
    print("📊 Admin Dashboard: http://127.0.0.1:5000/admin_dashboard")
    print("💬 Client Chat: http://127.0.0.1:5000/client_login")
    
    # Start browser opening in a separate thread
    browser_thread = threading.Thread(target=open_browser)
    browser_thread.daemon = True
    browser_thread.start()
    
    # Run app with SocketIO
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)
