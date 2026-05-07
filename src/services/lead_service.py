"""
Lead Service - Business logic for lead management
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from src.models.lead import Lead, LeadRepository
from src.models.database import get_collection
from src.utils.ai_service import AIService
from src.utils.email_service import EmailService
from src.services.context_service import get_context_service
from src.services.memory_service import get_memory_service

class LeadService:
    """Professional lead service with business logic"""
    
    def __init__(self):
        self.repository = LeadRepository()
        self.ai_service = AIService()
        self.email_service = EmailService()
        self.context_service = get_context_service()
        self.memory_service = get_memory_service()
    
    def create_lead(self, lead_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new lead with AI processing"""
        try:
            # Create lead object
            lead = Lead(lead_data)
            
            # Validate lead data
            validation_errors = lead.validate()
            if validation_errors:
                return {
                    'success': False,
                    'errors': validation_errors,
                    'message': 'Validation failed'
                }
            
            # Check for duplicate email
            existing_lead = self.repository.get_by_email(lead.email)
            if existing_lead:
                return {
                    'success': False,
                    'message': 'Lead with this email already exists'
                }
            
            # Generate client ID for context (use email as identifier)
            client_id = lead.email if lead.email else f"lead_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            # Process with context-aware AI
            ai_response = self.ai_service.generate_contextual_response(
                message=lead.message,
                client_id=client_id
            )
            
            lead.ai_response = ai_response['response']
            lead.ai_summary = ai_response.get('context_usage_note', 'Lead inquiry processed')
            
            # Store conversation in memory
            if self.memory_service.is_initialized():
                # Store user message
                self.memory_service.store_memory(
                    content=lead.message,
                    category="conversation",
                    content_type="message",
                    client_id=client_id,
                    lead_category=lead.priority,
                    tags=["new_inquiry", "website"]
                )
                
                # Store AI response
                self.memory_service.store_memory(
                    content=lead.ai_response,
                    category="conversation",
                    content_type="response",
                    client_id=client_id,
                    lead_category=lead.priority,
                    tags=["ai_response", "contextual"]
                )
            
            # Calculate lead score
            lead.calculate_score()
            
            # Save lead
            if self.repository.create(lead):
                # Send email notification
                self.email_service.send_lead_notification(lead)
                
                return {
                    'success': True,
                    'lead_id': lead.id,
                    'message': 'Lead created successfully',
                    'data': lead.to_dict()
                }
            else:
                return {
                    'success': False,
                    'message': 'Failed to save lead'
                }
                
        except Exception as e:
            logging.error(f"Error creating lead: {e}")
            return {
                'success': False,
                'message': 'Internal server error'
            }
    
    def get_leads(self, page: int = 1, page_size: int = 20, filters: Dict = None) -> Dict[str, Any]:
        """Get leads with pagination and filtering"""
        try:
            leads = self.repository.get_all(page, page_size, filters)
            total = self.repository.count(filters)
            
            return {
                'success': True,
                'leads': [lead.to_dict() for lead in leads],
                'pagination': {
                    'page': page,
                    'page_size': page_size,
                    'total': total,
                    'pages': (total + page_size - 1) // page_size
                }
            }
        except Exception as e:
            logging.error(f"Error getting leads: {e}")
            return {
                'success': False,
                'message': 'Failed to retrieve leads'
            }
    
    def get_lead(self, lead_id: str) -> Dict[str, Any]:
        """Get a specific lead"""
        try:
            lead = self.repository.get_by_id(lead_id)
            if lead:
                return {
                    'success': True,
                    'lead': lead.to_dict()
                }
            else:
                return {
                    'success': False,
                    'message': 'Lead not found'
                }
        except Exception as e:
            logging.error(f"Error getting lead: {e}")
            return {
                'success': False,
                'message': 'Failed to retrieve lead'
            }
    
    def update_lead(self, lead_id: str, update_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update a lead"""
        try:
            lead = self.repository.get_by_id(lead_id)
            if not lead:
                return {
                    'success': False,
                    'message': 'Lead not found'
                }
            
            # Update lead properties
            for key, value in update_data.items():
                if hasattr(lead, key):
                    setattr(lead, key, value)
            
            # Validate updated lead
            validation_errors = lead.validate()
            if validation_errors:
                return {
                    'success': False,
                    'errors': validation_errors,
                    'message': 'Validation failed'
                }
            
            # Update in database
            if self.repository.update(lead):
                return {
                    'success': True,
                    'message': 'Lead updated successfully',
                    'lead': lead.to_dict()
                }
            else:
                return {
                    'success': False,
                    'message': 'Failed to update lead'
                }
                
        except Exception as e:
            logging.error(f"Error updating lead: {e}")
            return {
                'success': False,
                'message': 'Internal server error'
            }
    
    def delete_lead(self, lead_id: str) -> Dict[str, Any]:
        """Delete a lead"""
        try:
            lead = self.repository.get_by_id(lead_id)
            if not lead:
                return {
                    'success': False,
                    'message': 'Lead not found'
                }
            
            if self.repository.delete(lead_id):
                return {
                    'success': True,
                    'message': 'Lead deleted successfully'
                }
            else:
                return {
                    'success': False,
                    'message': 'Failed to delete lead'
                }
                
        except Exception as e:
            logging.error(f"Error deleting lead: {e}")
            return {
                'success': False,
                'message': 'Internal server error'
            }
    
    def update_lead_status(self, lead_id: str, new_status: str) -> Dict[str, Any]:
        """Update lead status"""
        try:
            lead = self.repository.get_by_id(lead_id)
            if not lead:
                return {
                    'success': False,
                    'message': 'Lead not found'
                }
            
            if lead.update_status(new_status):
                if self.repository.update(lead):
                    return {
                        'success': True,
                        'message': f'Lead status updated to {new_status}',
                        'lead': lead.to_dict()
                    }
            
            return {
                'success': False,
                'message': 'Invalid status'
            }
            
        except Exception as e:
            logging.error(f"Error updating lead status: {e}")
            return {
                'success': False,
                'message': 'Internal server error'
            }
    
    def add_lead_note(self, lead_id: str, note: str, author: str = 'system') -> Dict[str, Any]:
        """Add a note to a lead"""
        try:
            lead = self.repository.get_by_id(lead_id)
            if not lead:
                return {
                    'success': False,
                    'message': 'Lead not found'
                }
            
            lead.add_note(note, author)
            
            if self.repository.update(lead):
                return {
                    'success': True,
                    'message': 'Note added successfully',
                    'lead': lead.to_dict()
                }
            else:
                return {
                    'success': False,
                    'message': 'Failed to add note'
                }
                
        except Exception as e:
            logging.error(f"Error adding note: {e}")
            return {
                'success': False,
                'message': 'Internal server error'
            }
    
    def get_analytics(self) -> Dict[str, Any]:
        """Get lead analytics"""
        try:
            analytics = self.repository.get_analytics()
            
            # Add additional analytics
            analytics['conversion_rate'] = self._calculate_conversion_rate()
            analytics['average_score'] = self._calculate_average_score()
            analytics['top_sources'] = self._get_top_sources()
            
            return {
                'success': True,
                'analytics': analytics
            }
            
        except Exception as e:
            logging.error(f"Error getting analytics: {e}")
            return {
                'success': False,
                'message': 'Failed to get analytics'
            }
    
    def export_leads(self, format: str = 'json', filters: Dict = None) -> Dict[str, Any]:
        """Export leads in specified format"""
        try:
            leads = self.repository.get_all(page_size=1000, filters=filters)
            
            if format.lower() == 'csv':
                return self._export_csv(leads)
            elif format.lower() == 'excel':
                return self._export_excel(leads)
            else:
                return {
                    'success': True,
                    'data': [lead.to_dict() for lead in leads],
                    'format': 'json'
                }
                
        except Exception as e:
            logging.error(f"Error exporting leads: {e}")
            return {
                'success': False,
                'message': 'Failed to export leads'
            }
    
    def _calculate_conversion_rate(self) -> float:
        """Calculate lead conversion rate"""
        try:
            analytics = self.repository.get_analytics()
            total = analytics.get('total_leads', 0)
            converted = analytics.get('status_breakdown', {}).get('closed_won', 0)
            
            if total == 0:
                return 0.0
            
            return round((converted / total) * 100, 2)
        except:
            return 0.0
    
    def _calculate_average_score(self) -> float:
        """Calculate average lead score"""
        try:
            leads = self.repository.get_all(page_size=1000)
            if not leads:
                return 0.0
            
            total_score = sum(lead.score for lead in leads)
            return round(total_score / len(leads), 2)
        except:
            return 0.0
    
    def _get_top_sources(self) -> List[Dict]:
        """Get top lead sources"""
        try:
            collection = get_collection('leads')
            pipeline = [
                {
                    '$group': {
                        '_id': '$source',
                        'count': {'$sum': 1}
                    }
                },
                {
                    '$sort': {'count': -1}
                },
                {
                    '$limit': 5
                }
            ]
            
            results = list(collection.aggregate(pipeline))
            return [{'source': item['_id'], 'count': item['count']} for item in results]
        except:
            return []
    
    def _export_csv(self, leads: List[Lead]) -> Dict[str, Any]:
        """Export leads to CSV format"""
        try:
            import csv
            import io
            
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Write header
            writer.writerow([
                'ID', 'Name', 'Email', 'Phone', 'Company', 'Status', 
                'Priority', 'Source', 'Score', 'Created At'
            ])
            
            # Write data
            for lead in leads:
                writer.writerow([
                    lead.id,
                    lead.name,
                    lead.email,
                    lead.phone,
                    lead.company,
                    lead.status,
                    lead.priority,
                    lead.source,
                    lead.score,
                    lead.created_at.isoformat() if lead.created_at else ''
                ])
            
            return {
                'success': True,
                'data': output.getvalue(),
                'format': 'csv',
                'filename': f'leads_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
            }
        except Exception as e:
            logging.error(f"Error exporting to CSV: {e}")
            return {
                'success': False,
                'message': 'Failed to export to CSV'
            }
    
    def _export_excel(self, leads: List[Lead]) -> Dict[str, Any]:
        """Export leads to Excel format"""
        try:
            # This would require openpyxl or similar library
            # For now, return CSV as fallback
            return self._export_csv(leads)
        except Exception as e:
            logging.error(f"Error exporting to Excel: {e}")
            return {
                'success': False,
                'message': 'Failed to export to Excel'
            }
