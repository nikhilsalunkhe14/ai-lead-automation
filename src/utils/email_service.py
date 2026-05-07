"""
Email Service - Professional email handling
"""

import logging
from typing import Dict, Any, Optional
import resend
from src.config.settings import settings

class EmailService:
    """Professional email service with templates and tracking"""
    
    def __init__(self):
        self.config = settings.get_email_config()
        resend.api_key = self.config['api_key']
        self.from_email = self.config['from_email']
        self.from_name = self.config['from_name']
    
    def send_lead_notification(self, lead) -> bool:
        """Send notification when new lead is created"""
        try:
            subject = f"New Lead: {lead.name} - {lead.company or 'No Company'}"
            
            html_content = self._create_lead_notification_template(lead)
            text_content = self._create_lead_notification_text(lead)
            
            params = {
                "from": f"{self.from_name} <{self.from_email}>",
                "to": [self.from_email],  # Send to admin
                "subject": subject,
                "html": html_content,
                "text": text_content,
                "reply_to": lead.email
            }
            
            r = resend.Emails.send(params)
            
            if r.status_code == 200:
                logging.info(f"✅ Lead notification sent for {lead.email}")
                return True
            else:
                logging.error(f"❌ Failed to send lead notification: {r}")
                return False
                
        except Exception as e:
            logging.error(f"Error sending lead notification: {e}")
            return False
    
    def send_welcome_email(self, lead) -> bool:
        """Send welcome email to lead"""
        try:
            subject = "Thank you for your inquiry"
            
            html_content = self._create_welcome_template(lead)
            text_content = self._create_welcome_text(lead)
            
            params = {
                "from": f"{self.from_name} <{self.from_email}>",
                "to": [lead.email],
                "subject": subject,
                "html": html_content,
                "text": text_content
            }
            
            r = resend.Emails.send(params)
            
            if r.status_code == 200:
                logging.info(f"✅ Welcome email sent to {lead.email}")
                return True
            else:
                logging.error(f"❌ Failed to send welcome email: {r}")
                return False
                
        except Exception as e:
            logging.error(f"Error sending welcome email: {e}")
            return False
    
    def send_admin_notification(self, admin_email: str, message: str, subject: str = "System Notification") -> bool:
        """Send notification to admin"""
        try:
            html_content = self._create_admin_notification_template(message)
            text_content = message
            
            params = {
                "from": f"{self.from_name} <{self.from_email}>",
                "to": [admin_email],
                "subject": subject,
                "html": html_content,
                "text": text_content
            }
            
            r = resend.Emails.send(params)
            
            if r.status_code == 200:
                logging.info(f"✅ Admin notification sent to {admin_email}")
                return True
            else:
                logging.error(f"❌ Failed to send admin notification: {r}")
                return False
                
        except Exception as e:
            logging.error(f"Error sending admin notification: {e}")
            return False
    
    def send_lead_update_notification(self, lead, update_type: str) -> bool:
        """Send notification when lead status is updated"""
        try:
            subject = f"Lead Update: {lead.name} - {update_type.title()}"
            
            html_content = self._create_update_notification_template(lead, update_type)
            text_content = f"Lead {lead.name} has been updated: {update_type}"
            
            params = {
                "from": f"{self.from_name} <{self.from_email}>",
                "to": [self.from_email],
                "subject": subject,
                "html": html_content,
                "text": text_content,
                "reply_to": lead.email
            }
            
            r = resend.Emails.send(params)
            
            if r.status_code == 200:
                logging.info(f"✅ Lead update notification sent for {lead.email}")
                return True
            else:
                logging.error(f"❌ Failed to send lead update notification: {r}")
                return False
                
        except Exception as e:
            logging.error(f"Error sending lead update notification: {e}")
            return False
    
    def _create_lead_notification_template(self, lead) -> str:
        """Create HTML template for lead notification"""
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>New Lead Notification</title>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: #4f46e5; color: white; padding: 20px; text-align: center; }}
                .content {{ background: #f9fafb; padding: 30px; border-radius: 8px; }}
                .lead-info {{ background: white; padding: 20px; border-radius: 8px; margin: 20px 0; }}
                .field {{ margin: 10px 0; }}
                .field-label {{ font-weight: bold; color: #6b7280; }}
                .field-value {{ color: #1f2937; }}
                .ai-response {{ background: #eff6ff; padding: 20px; border-radius: 8px; margin: 20px 0; }}
                .score {{ background: #10b981; color: white; padding: 10px; border-radius: 20px; display: inline-block; }}
                .footer {{ text-align: center; color: #6b7280; margin-top: 30px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🎯 New Lead Received</h1>
                </div>
                <div class="content">
                    <div class="lead-info">
                        <div class="field">
                            <span class="field-label">Name:</span>
                            <span class="field-value">{lead.name}</span>
                        </div>
                        <div class="field">
                            <span class="field-label">Email:</span>
                            <span class="field-value">{lead.email}</span>
                        </div>
                        <div class="field">
                            <span class="field-label">Phone:</span>
                            <span class="field-value">{lead.phone or 'Not provided'}</span>
                        </div>
                        <div class="field">
                            <span class="field-label">Company:</span>
                            <span class="field-value">{lead.company or 'Not provided'}</span>
                        </div>
                        <div class="field">
                            <span class="field-label">Status:</span>
                            <span class="field-value">{lead.status}</span>
                        </div>
                        <div class="field">
                            <span class="field-label">Priority:</span>
                            <span class="field-value">{lead.priority}</span>
                        </div>
                        <div class="field">
                            <span class="field-label">Score:</span>
                            <span class="score">{lead.score}/100</span>
                        </div>
                    </div>
                    
                    <div class="lead-info">
                        <div class="field-label">Message:</div>
                        <div class="field-value">{lead.message}</div>
                    </div>
                    
                    {f'''<div class="ai-response">
                        <div class="field-label">AI Response:</div>
                        <div class="field-value">{lead.ai_response}</div>
                        
                        <div class="field-label" style="margin-top: 15px;">AI Summary:</div>
                        <div class="field-value">{lead.ai_summary}</div>
                    </div>''' if lead.ai_response else ''}
                </div>
                <div class="footer">
                    <p>This notification was sent by AI Lead Automation System</p>
                </div>
            </div>
        </body>
        </html>
        """
    
    def _create_lead_notification_text(self, lead) -> str:
        """Create text version of lead notification"""
        return f"""
        NEW LEAD NOTIFICATION
        
        Name: {lead.name}
        Email: {lead.email}
        Phone: {lead.phone or 'Not provided'}
        Company: {lead.company or 'Not provided'}
        Status: {lead.status}
        Priority: {lead.priority}
        Score: {lead.score}/100
        
        Message:
        {lead.message}
        
        {f'''AI Response:
        {lead.ai_response}
        
        AI Summary:
        {lead.ai_summary}''' if lead.ai_response else ''}
        
        ---
        This notification was sent by AI Lead Automation System
        """
    
    def _create_welcome_template(self, lead) -> str:
        """Create HTML template for welcome email"""
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Thank You for Your Inquiry</title>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: #10b981; color: white; padding: 20px; text-align: center; }}
                .content {{ background: #f9fafb; padding: 30px; border-radius: 8px; }}
                .footer {{ text-align: center; color: #6b7280; margin-top: 30px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Thank You for Your Inquiry!</h1>
                </div>
                <div class="content">
                    <p>Dear {lead.name},</p>
                    <p>Thank you for reaching out to us. We have received your inquiry and our team will review it shortly.</p>
                    
                    <p>We appreciate your interest and will get back to you as soon as possible with the information you need.</p>
                    
                    <p>Best regards,<br>The Team</p>
                </div>
                <div class="footer">
                    <p>This email was sent by AI Lead Automation System</p>
                </div>
            </div>
        </body>
        </html>
        """
    
    def _create_welcome_text(self, lead) -> str:
        """Create text version of welcome email"""
        return f"""
        Dear {lead.name},
        
        Thank you for reaching out to us. We have received your inquiry and our team will review it shortly.
        
        We appreciate your interest and will get back to you as soon as possible with the information you need.
        
        Best regards,
        The Team
        
        ---
        This email was sent by AI Lead Automation System
        """
    
    def _create_admin_notification_template(self, message: str) -> str:
        """Create HTML template for admin notification"""
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>System Notification</title>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: #ef4444; color: white; padding: 20px; text-align: center; }}
                .content {{ background: #f9fafb; padding: 30px; border-radius: 8px; }}
                .footer {{ text-align: center; color: #6b7280; margin-top: 30px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🔔 System Notification</h1>
                </div>
                <div class="content">
                    <p>{message}</p>
                </div>
                <div class="footer">
                    <p>This notification was sent by AI Lead Automation System</p>
                </div>
            </div>
        </body>
        </html>
        """
    
    def _create_update_notification_template(self, lead, update_type: str) -> str:
        """Create HTML template for lead update notification"""
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Lead Update Notification</title>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: #f59e0b; color: white; padding: 20px; text-align: center; }}
                .content {{ background: #f9fafb; padding: 30px; border-radius: 8px; }}
                .update-info {{ background: white; padding: 20px; border-radius: 8px; margin: 20px 0; }}
                .footer {{ text-align: center; color: #6b7280; margin-top: 30px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>📝 Lead Updated</h1>
                </div>
                <div class="content">
                    <div class="update-info">
                        <h3>Lead: {lead.name}</h3>
                        <p><strong>Update Type:</strong> {update_type.title()}</p>
                        <p><strong>Email:</strong> {lead.email}</p>
                        <p><strong>Current Status:</strong> {lead.status}</p>
                        <p><strong>Priority:</strong> {lead.priority}</p>
                    </div>
                </div>
                <div class="footer">
                    <p>This notification was sent by AI Lead Automation System</p>
                </div>
            </div>
        </body>
        </html>
        """
