"""
Lead Model - Professional lead data structure and operations
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from src.models.database import get_collection

class Lead:
    """Professional lead model with validation and methods"""
    
    def __init__(self, data: Dict[str, Any]):
        self.id = str(data.get('_id', '')) if '_id' in data else None
        self.name = data.get('name', '').strip()
        self.email = data.get('email', '').strip().lower()
        self.phone = data.get('phone', '').strip()
        self.company = data.get('company', '').strip()
        self.message = data.get('message', '').strip()
        self.status = data.get('status', 'new')
        self.priority = data.get('priority', 'medium')
        self.source = data.get('source', 'website')
        self.ai_response = data.get('ai_response', '')
        self.ai_summary = data.get('ai_summary', '')
        self.score = data.get('score', 0)
        self.tags = data.get('tags', [])
        self.notes = data.get('notes', [])
        self.created_at = data.get('created_at', datetime.now(timezone.utc))
        self.updated_at = data.get('updated_at', datetime.now(timezone.utc))
        self.last_contacted = data.get('last_contacted', None)
        self.converted = data.get('converted', False)
        self.assigned_to = data.get('assigned_to', None)
        self.follow_up_date = data.get('follow_up_date', None)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert lead to dictionary"""
        return {
            '_id': self.id,
            'name': self.name,
            'email': self.email,
            'phone': self.phone,
            'company': self.company,
            'message': self.message,
            'status': self.status,
            'priority': self.priority,
            'source': self.source,
            'ai_response': self.ai_response,
            'ai_summary': self.ai_summary,
            'score': self.score,
            'tags': self.tags,
            'notes': self.notes,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'last_contacted': self.last_contacted,
            'converted': self.converted,
            'assigned_to': self.assigned_to,
            'follow_up_date': self.follow_up_date
        }
    
    def validate(self) -> List[str]:
        """Validate lead data"""
        errors = []
        
        if not self.name:
            errors.append("Name is required")
        elif len(self.name) < 2:
            errors.append("Name must be at least 2 characters")
        
        if not self.email:
            errors.append("Email is required")
        elif '@' not in self.email or '.' not in self.email:
            errors.append("Invalid email format")
        
        if self.phone and len(self.phone) < 10:
            errors.append("Phone number must be at least 10 digits")
        
        if not self.message:
            errors.append("Message is required")
        elif len(self.message) < 10:
            errors.append("Message must be at least 10 characters")
        
        valid_statuses = ['new', 'contacted', 'qualified', 'proposal', 'negotiation', 'closed_won', 'closed_lost']
        if self.status not in valid_statuses:
            errors.append(f"Invalid status. Must be one of: {valid_statuses}")
        
        valid_priorities = ['low', 'medium', 'high', 'urgent']
        if self.priority not in valid_priorities:
            errors.append(f"Invalid priority. Must be one of: {valid_priorities}")
        
        return errors
    
    def update_status(self, new_status: str) -> bool:
        """Update lead status with validation"""
        valid_statuses = ['new', 'contacted', 'qualified', 'proposal', 'negotiation', 'closed_won', 'closed_lost']
        if new_status not in valid_statuses:
            return False
        
        self.status = new_status
        self.updated_at = datetime.now(timezone.utc)
        return True
    
    def add_note(self, note: str, author: str = 'system'):
        """Add a note to the lead"""
        note_data = {
            'content': note,
            'author': author,
            'timestamp': datetime.now(timezone.utc)
        }
        self.notes.append(note_data)
        self.updated_at = datetime.now(timezone.utc)
    
    def add_tag(self, tag: str):
        """Add a tag to the lead"""
        if tag not in self.tags:
            self.tags.append(tag)
            self.updated_at = datetime.now(timezone.utc)
    
    def remove_tag(self, tag: str):
        """Remove a tag from the lead"""
        if tag in self.tags:
            self.tags.remove(tag)
            self.updated_at = datetime.now(timezone.utc)
    
    def calculate_score(self) -> int:
        """Calculate lead score based on various factors"""
        score = 0
        
        # Message length indicates detail level
        if len(self.message) > 100:
            score += 10
        elif len(self.message) > 50:
            score += 5
        
        # Company information indicates seriousness
        if self.company:
            score += 15
        
        # Phone number indicates higher intent
        if self.phone:
            score += 10
        
        # Priority weighting
        priority_scores = {'low': 0, 'medium': 10, 'high': 20, 'urgent': 30}
        score += priority_scores.get(self.priority, 0)
        
        self.score = score
        return score

class LeadRepository:
    """Repository pattern for lead operations"""
    
    def __init__(self):
        self.collection = get_collection('leads')
    
    def create(self, lead: Lead) -> bool:
        """Create a new lead"""
        try:
            lead_data = lead.to_dict()
            lead_data['created_at'] = datetime.now(timezone.utc)
            lead_data['updated_at'] = datetime.now(timezone.utc)
            
            result = self.collection.insert_one(lead_data)
            lead.id = str(result.inserted_id)
            return True
        except Exception as e:
            logging.error(f"Error creating lead: {e}")
            return False
    
    def get_by_id(self, lead_id: str) -> Optional[Lead]:
        """Get lead by ID"""
        try:
            data = self.collection.find_one({'_id': lead_id})
            return Lead(data) if data else None
        except Exception as e:
            logging.error(f"Error getting lead: {e}")
            return None
    
    def get_by_email(self, email: str) -> Optional[Lead]:
        """Get lead by email"""
        try:
            data = self.collection.find_one({'email': email.lower()})
            return Lead(data) if data else None
        except Exception as e:
            logging.error(f"Error getting lead by email: {e}")
            return None
    
    def get_all(self, page: int = 1, page_size: int = 20, filters: Dict = None) -> List[Lead]:
        """Get all leads with pagination and filtering"""
        try:
            query = filters or {}
            
            # Apply filters
            if 'status' in filters:
                query['status'] = filters['status']
            if 'priority' in filters:
                query['priority'] = filters['priority']
            if 'search' in filters:
                search_term = filters['search']
                query['$or'] = [
                    {'name': {'$regex': search_term, '$options': 'i'}},
                    {'email': {'$regex': search_term, '$options': 'i'}},
                    {'company': {'$regex': search_term, '$options': 'i'}},
                    {'message': {'$regex': search_term, '$options': 'i'}}
                ]
            
            skip = (page - 1) * page_size
            cursor = self.collection.find(query).sort('created_at', -1).skip(skip).limit(page_size)
            
            return [Lead(doc) for doc in cursor]
        except Exception as e:
            logging.error(f"Error getting leads: {e}")
            return []
    
    def update(self, lead: Lead) -> bool:
        """Update lead"""
        try:
            lead_data = lead.to_dict()
            lead_data['updated_at'] = datetime.now(timezone.utc)
            
            self.collection.update_one(
                {'_id': lead.id},
                {'$set': lead_data}
            )
            return True
        except Exception as e:
            logging.error(f"Error updating lead: {e}")
            return False
    
    def delete(self, lead_id: str) -> bool:
        """Delete lead"""
        try:
            self.collection.delete_one({'_id': lead_id})
            return True
        except Exception as e:
            logging.error(f"Error deleting lead: {e}")
            return False
    
    def count(self, filters: Dict = None) -> int:
        """Count leads with filters"""
        try:
            query = filters or {}
            return self.collection.count_documents(query)
        except Exception as e:
            logging.error(f"Error counting leads: {e}")
            return 0
    
    def get_analytics(self) -> Dict:
        """Get lead analytics data"""
        try:
            pipeline = [
                {
                    '$group': {
                        '_id': '$status',
                        'count': {'$sum': 1}
                    }
                }
            ]
            
            status_counts = list(self.collection.aggregate(pipeline))
            
            # Get total count
            total = self.collection.count_documents({})
            
            # Get recent leads
            recent_count = self.collection.count_documents({
                'created_at': {'$gte': datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)}
            })
            
            return {
                'total_leads': total,
                'recent_leads': recent_count,
                'status_breakdown': {item['_id']: item['count'] for item in status_counts}
            }
        except Exception as e:
            logging.error(f"Error getting analytics: {e}")
            return {}
