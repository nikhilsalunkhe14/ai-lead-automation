"""
Admin Model - Professional admin user management
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
import bcrypt
import logging
from src.models.database import get_collection

class Admin:
    """Professional admin model with security features"""
    
    def __init__(self, data: Dict[str, Any]):
        self.id = str(data.get('_id', '')) if '_id' in data else None
        self.username = data.get('username', '').strip().lower()
        self.email = data.get('email', '').strip().lower()
        self.password_hash = data.get('password_hash', '')
        self.role = data.get('role', 'viewer')
        self.is_active = data.get('is_active', True)
        self.login_attempts = data.get('login_attempts', 0)
        self.last_login = data.get('last_login', None)
        self.locked_until = data.get('locked_until', None)
        self.created_at = data.get('created_at', datetime.now(timezone.utc))
        self.updated_at = data.get('updated_at', datetime.now(timezone.utc))
        self.permissions = data.get('permissions', [])
        self.preferences = data.get('preferences', {})
    
    def to_dict(self, include_sensitive: bool = False) -> Dict[str, Any]:
        """Convert admin to dictionary"""
        data = {
            '_id': self.id,
            'username': self.username,
            'email': self.email,
            'role': self.role,
            'is_active': self.is_active,
            'login_attempts': self.login_attempts,
            'last_login': self.last_login,
            'locked_until': self.locked_until,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'permissions': self.permissions,
            'preferences': self.preferences
        }
        
        if include_sensitive:
            data['password_hash'] = self.password_hash
        
        return data
    
    def validate(self) -> List[str]:
        """Validate admin data"""
        errors = []
        
        if not self.username:
            errors.append("Username is required")
        elif len(self.username) < 3:
            errors.append("Username must be at least 3 characters")
        elif len(self.username) > 50:
            errors.append("Username must not exceed 50 characters")
        
        if not self.email:
            errors.append("Email is required")
        elif '@' not in self.email or '.' not in self.email:
            errors.append("Invalid email format")
        
        valid_roles = ['super_admin', 'admin', 'viewer']
        if self.role not in valid_roles:
            errors.append(f"Invalid role. Must be one of: {valid_roles}")
        
        return errors
    
    def set_password(self, password: str) -> bool:
        """Set password with proper hashing"""
        try:
            # Generate salt and hash
            salt = bcrypt.gensalt()
            self.password_hash = bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
            self.updated_at = datetime.now(timezone.utc)
            return True
        except Exception as e:
            logging.error(f"Error setting password: {e}")
            return False
    
    def verify_password(self, password: str) -> bool:
        """Verify password against stored hash"""
        try:
            if not self.password_hash:
                return False
            
            return bcrypt.checkpw(password.encode('utf-8'), self.password_hash.encode('utf-8'))
        except Exception as e:
            logging.error(f"Error verifying password: {e}")
            return False
    
    def is_locked(self) -> bool:
        """Check if account is locked"""
        if not self.locked_until:
            return False
        return datetime.now(timezone.utc) < self.locked_until
    
    def can_login(self) -> bool:
        """Check if user can login"""
        return self.is_active and not self.is_locked()
    
    def increment_login_attempts(self) -> bool:
        """Increment failed login attempts"""
        self.login_attempts += 1
        self.updated_at = datetime.now(timezone.utc)
        
        # Lock account after 5 failed attempts
        if self.login_attempts >= 5:
            self.locked_until = datetime.now(timezone.utc).replace(hour=23, minute=59, second=59)
            return True
        
        return False
    
    def reset_login_attempts(self):
        """Reset login attempts after successful login"""
        self.login_attempts = 0
        self.locked_until = None
        self.last_login = datetime.now(timezone.utc)
        self.updated_at = datetime.now(timezone.utc)
    
    def has_permission(self, permission: str) -> bool:
        """Check if admin has specific permission"""
        if self.role == 'super_admin':
            return True
        
        return permission in self.permissions
    
    def get_role_permissions(self) -> List[str]:
        """Get permissions based on role"""
        role_permissions = {
            'super_admin': [
                'admin.create', 'admin.read', 'admin.update', 'admin.delete',
                'lead.create', 'lead.read', 'lead.update', 'lead.delete',
                'analytics.read', 'settings.read', 'settings.update'
            ],
            'admin': [
                'lead.create', 'lead.read', 'lead.update', 'lead.delete',
                'analytics.read'
            ],
            'viewer': [
                'lead.read', 'analytics.read'
            ]
        }
        
        return role_permissions.get(self.role, [])

class AdminRepository:
    """Repository pattern for admin operations"""
    
    def __init__(self):
        self.collection = get_collection('admins')
    
    def create(self, admin: Admin) -> bool:
        """Create a new admin"""
        try:
            admin_data = admin.to_dict(include_sensitive=True)
            admin_data['created_at'] = datetime.now(timezone.utc)
            admin_data['updated_at'] = datetime.now(timezone.utc)
            
            result = self.collection.insert_one(admin_data)
            admin.id = str(result.inserted_id)
            return True
        except Exception as e:
            logging.error(f"Error creating admin: {e}")
            return False
    
    def get_by_id(self, admin_id: str) -> Optional[Admin]:
        """Get admin by ID"""
        try:
            data = self.collection.find_one({'_id': admin_id})
            return Admin(data) if data else None
        except Exception as e:
            logging.error(f"Error getting admin: {e}")
            return None
    
    def get_by_username(self, username: str) -> Optional[Admin]:
        """Get admin by username"""
        try:
            data = self.collection.find_one({'username': username.lower()})
            return Admin(data) if data else None
        except Exception as e:
            logging.error(f"Error getting admin by username: {e}")
            return None
    
    def get_by_email(self, email: str) -> Optional[Admin]:
        """Get admin by email"""
        try:
            data = self.collection.find_one({'email': email.lower()})
            return Admin(data) if data else None
        except Exception as e:
            logging.error(f"Error getting admin by email: {e}")
            return None
    
    def get_all(self, page: int = 1, page_size: int = 20) -> List[Admin]:
        """Get all admins with pagination"""
        try:
            skip = (page - 1) * page_size
            cursor = self.collection.find(
                {},  # No password field
                {'password_hash': 0}
            ).sort('created_at', -1).skip(skip).limit(page_size)
            
            return [Admin(doc) for doc in cursor]
        except Exception as e:
            logging.error(f"Error getting admins: {e}")
            return []
    
    def update(self, admin: Admin) -> bool:
        """Update admin"""
        try:
            admin_data = admin.to_dict(include_sensitive=True)
            admin_data['updated_at'] = datetime.now(timezone.utc)
            
            self.collection.update_one(
                {'_id': admin.id},
                {'$set': admin_data}
            )
            return True
        except Exception as e:
            logging.error(f"Error updating admin: {e}")
            return False
    
    def delete(self, admin_id: str) -> bool:
        """Delete admin"""
        try:
            self.collection.delete_one({'_id': admin_id})
            return True
        except Exception as e:
            logging.error(f"Error deleting admin: {e}")
            return False
    
    def count(self) -> int:
        """Count total admins"""
        try:
            return self.collection.count_documents({})
        except Exception as e:
            logging.error(f"Error counting admins: {e}")
            return 0
    
    def exists(self, username: str = None, email: str = None) -> bool:
        """Check if admin exists by username or email"""
        try:
            query = {}
            if username:
                query['username'] = username.lower()
            if email:
                query['email'] = email.lower()
            
            return self.collection.count_documents(query) > 0
        except Exception as e:
            logging.error(f"Error checking admin existence: {e}")
            return False
