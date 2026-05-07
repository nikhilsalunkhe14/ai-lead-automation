"""
Memory Models - Professional data models for AI memory system
"""

from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
import uuid
import numpy as np

@dataclass
class MemoryEntry:
    """
    Professional memory entry with vector embedding and metadata
    """
    
    # Core fields
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    content: str = ""
    content_type: str = "text"  # text, summary, requirement, etc.
    embedding: Optional[np.ndarray] = None
    
    # Metadata
    client_id: Optional[str] = None
    lead_id: Optional[str] = None
    conversation_id: Optional[str] = None
    project_id: Optional[str] = None
    
    # Classification
    category: str = "general"  # conversation, client, project, summary
    tags: List[str] = field(default_factory=list)
    lead_category: str = "unspecified"  # hot, warm, cool, cold
    
    # Timestamps
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Additional metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert memory entry to dictionary"""
        return {
            'id': self.id,
            'content': self.content,
            'content_type': self.content_type,
            'client_id': self.client_id,
            'lead_id': self.lead_id,
            'conversation_id': self.conversation_id,
            'project_id': self.project_id,
            'category': self.category,
            'tags': self.tags,
            'lead_category': self.lead_category,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'metadata': self.metadata,
            # Convert embedding to list for JSON serialization
            'embedding': self.embedding.tolist() if self.embedding is not None else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MemoryEntry':
        """Create memory entry from dictionary"""
        # Convert embedding back to numpy array if present
        embedding = None
        if data.get('embedding'):
            embedding = np.array(data['embedding'])
        
        # Convert timestamps
        created_at = datetime.fromisoformat(data['created_at']) if data.get('created_at') else datetime.now(timezone.utc)
        updated_at = datetime.fromisoformat(data['updated_at']) if data.get('updated_at') else datetime.now(timezone.utc)
        
        return cls(
            id=data.get('id', str(uuid.uuid4())),
            content=data.get('content', ''),
            content_type=data.get('content_type', 'text'),
            embedding=embedding,
            client_id=data.get('client_id'),
            lead_id=data.get('lead_id'),
            conversation_id=data.get('conversation_id'),
            project_id=data.get('project_id'),
            category=data.get('category', 'general'),
            tags=data.get('tags', []),
            lead_category=data.get('lead_category', 'unspecified'),
            created_at=created_at,
            updated_at=updated_at,
            metadata=data.get('metadata', {})
        )
    
    def validate(self) -> List[str]:
        """Validate memory entry"""
        errors = []
        
        if not self.content or not self.content.strip():
            errors.append("Content is required")
        
        if self.content_type not in ['text', 'summary', 'requirement', 'message', 'response']:
            errors.append("Invalid content type")
        
        if self.category not in ['conversation', 'client', 'project', 'summary', 'general']:
            errors.append("Invalid category")
        
        if self.lead_category not in ['hot', 'warm', 'cool', 'cold', 'unspecified']:
            errors.append("Invalid lead category")
        
        if self.embedding is not None and not isinstance(self.embedding, np.ndarray):
            errors.append("Embedding must be a numpy array")
        
        return errors
    
    def update_timestamp(self):
        """Update the updated_at timestamp"""
        self.updated_at = datetime.now(timezone.utc)

@dataclass
class ConversationMemory:
    """
    Professional conversation memory with threading and context
    """
    
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    client_id: Optional[str] = None
    lead_id: Optional[str] = None
    
    # Conversation metadata
    title: str = ""
    status: str = "active"  # active, closed, archived
    conversation_type: str = "general"  # sales, support, inquiry
    
    # Messages
    messages: List[MemoryEntry] = field(default_factory=list)
    
    # Summary and insights
    summary: str = ""
    key_points: List[str] = field(default_factory=list)
    action_items: List[str] = field(default_factory=list)
    
    # Timestamps
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_activity: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    ended_at: Optional[datetime] = None
    
    # Additional metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def add_message(self, message: MemoryEntry):
        """Add a message to the conversation"""
        self.messages.append(message)
        self.last_activity = datetime.now(timezone.utc)
        self.update_timestamp()
    
    def get_recent_messages(self, limit: int = 10) -> List[MemoryEntry]:
        """Get recent messages from conversation"""
        return self.messages[-limit:] if self.messages else []
    
    def get_context_summary(self, max_length: int = 500) -> str:
        """Get a summary of conversation context"""
        if self.summary:
            return self.summary
        
        # Generate basic summary from recent messages
        recent_messages = self.get_recent_messages(5)
        context_parts = []
        
        for msg in recent_messages:
            if msg.content_type in ['text', 'message', 'response']:
                context_parts.append(f"{msg.content_type}: {msg.content[:100]}...")
        
        return " | ".join(context_parts)[:max_length]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert conversation memory to dictionary"""
        return {
            'id': self.id,
            'client_id': self.client_id,
            'lead_id': self.lead_id,
            'title': self.title,
            'status': self.status,
            'conversation_type': self.conversation_type,
            'messages': [msg.to_dict() for msg in self.messages],
            'summary': self.summary,
            'key_points': self.key_points,
            'action_items': self.action_items,
            'started_at': self.started_at.isoformat(),
            'last_activity': self.last_activity.isoformat(),
            'ended_at': self.ended_at.isoformat() if self.ended_at else None,
            'metadata': self.metadata
        }
    
    def update_timestamp(self):
        """Update the last_activity timestamp"""
        self.last_activity = datetime.now(timezone.utc)

@dataclass
class ClientMemory:
    """
    Professional client memory with profile and interaction history
    """
    
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    client_id: str
    
    # Client profile
    name: str = ""
    email: str = ""
    phone: str = ""
    company: str = ""
    
    # Client characteristics
    communication_preferences: Dict[str, Any] = field(default_factory=dict)
    interaction_patterns: List[str] = field(default_factory=list)
    interests: List[str] = field(default_factory=list)
    requirements: List[str] = field(default_factory=list)
    
    # Relationship data
    relationship_score: float = 0.0  # 0-1 based on interaction quality
    engagement_level: str = "low"  # low, medium, high
    
    # Conversation history
    conversations: List[str] = field(default_factory=list)  # Conversation IDs
    total_interactions: int = 0
    
    # Timestamps
    first_contact: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_contact: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Additional metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def add_conversation(self, conversation_id: str):
        """Add conversation to client history"""
        if conversation_id not in self.conversations:
            self.conversations.append(conversation_id)
        self.total_interactions += 1
        self.last_contact = datetime.now(timezone.utc)
        self.update_timestamp()
    
    def update_engagement_level(self):
        """Update engagement level based on recent activity"""
        days_since_last_contact = (datetime.now(timezone.utc) - self.last_contact).days
        
        if days_since_last_contact <= 7:
            self.engagement_level = "high"
        elif days_since_last_contact <= 30:
            self.engagement_level = "medium"
        else:
            self.engagement_level = "low"
        
        self.update_timestamp()
    
    def get_profile_summary(self) -> str:
        """Get a summary of client profile"""
        summary_parts = []
        
        if self.company:
            summary_parts.append(f"Company: {self.company}")
        
        if self.interests:
            summary_parts.append(f"Interests: {', '.join(self.interests[:3])}")
        
        if self.requirements:
            summary_parts.append(f"Requirements: {len(self.requirements)} items")
        
        summary_parts.append(f"Engagement: {self.engagement_level}")
        summary_parts.append(f"Total interactions: {self.total_interactions}")
        
        return " | ".join(summary_parts)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert client memory to dictionary"""
        return {
            'id': self.id,
            'client_id': self.client_id,
            'name': self.name,
            'email': self.email,
            'phone': self.phone,
            'company': self.company,
            'communication_preferences': self.communication_preferences,
            'interaction_patterns': self.interaction_patterns,
            'interests': self.interests,
            'requirements': self.requirements,
            'relationship_score': self.relationship_score,
            'engagement_level': self.engagement_level,
            'conversations': self.conversations,
            'total_interactions': self.total_interactions,
            'first_contact': self.first_contact.isoformat(),
            'last_contact': self.last_contact.isoformat(),
            'metadata': self.metadata
        }
    
    def update_timestamp(self):
        """Update the last_contact timestamp"""
        self.last_contact = datetime.now(timezone.utc)

@dataclass
class ProjectMemory:
    """
    Professional project memory with requirements and progress tracking
    """
    
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    project_id: str
    client_id: Optional[str] = None
    
    # Project details
    name: str = ""
    description: str = ""
    status: str = "planning"  # planning, active, completed, cancelled
    
    # Requirements and specifications
    requirements: List[str] = field(default_factory=list)
    specifications: Dict[str, Any] = field(default_factory=dict)
    constraints: List[str] = field(default_factory=list)
    
    # Progress tracking
    milestones: List[Dict[str, Any]] = field(default_factory=list)
    deliverables: List[str] = field(default_factory=list)
    
    # Related data
    related_conversations: List[str] = field(default_factory=list)
    related_leads: List[str] = field(default_factory=list)
    
    # Timestamps
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    deadline: Optional[datetime] = None
    
    # Additional metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def add_requirement(self, requirement: str):
        """Add a requirement to the project"""
        if requirement not in self.requirements:
            self.requirements.append(requirement)
            self.update_timestamp()
    
    def add_milestone(self, milestone: Dict[str, Any]):
        """Add a milestone to the project"""
        milestone['id'] = str(uuid.uuid4())
        milestone['created_at'] = datetime.now(timezone.utc).isoformat()
        self.milestones.append(milestone)
        self.update_timestamp()
    
    def get_progress_summary(self) -> str:
        """Get a summary of project progress"""
        summary_parts = []
        
        summary_parts.append(f"Status: {self.status}")
        summary_parts.append(f"Requirements: {len(self.requirements)}")
        summary_parts.append(f"Milestones: {len(self.milestones)}")
        
        if self.deadline:
            days_to_deadline = (self.deadline - datetime.now(timezone.utc)).days
            summary_parts.append(f"Days to deadline: {days_to_deadline}")
        
        return " | ".join(summary_parts)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert project memory to dictionary"""
        return {
            'id': self.id,
            'project_id': self.project_id,
            'client_id': self.client_id,
            'name': self.name,
            'description': self.description,
            'status': self.status,
            'requirements': self.requirements,
            'specifications': self.specifications,
            'constraints': self.constraints,
            'milestones': self.milestones,
            'deliverables': self.deliverables,
            'related_conversations': self.related_conversations,
            'related_leads': self.related_leads,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'deadline': self.deadline.isoformat() if self.deadline else None,
            'metadata': self.metadata
        }
    
    def update_timestamp(self):
        """Update the updated_at timestamp"""
        self.updated_at = datetime.now(timezone.utc)
