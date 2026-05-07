"""
Admin Routes - Professional API endpoints for admin management
"""

from flask import Blueprint, request, jsonify, session
from src.models.admin import Admin, AdminRepository
from src.utils.security_utils_fixed import admin_required, super_admin_required, csrf_protected, SecurityUtils
import logging

# Create Blueprint
admin_bp = Blueprint('admin', __name__, url_prefix='/api/admin')

# Initialize repository
admin_repository = AdminRepository()

@admin_bp.route('/register', methods=['POST'])
@csrf_protected
def register_admin():
    """Register a new admin user"""
    try:
        # Check for suspicious requests
        is_suspicious, indicators = SecurityUtils.is_suspicious_request()
        if is_suspicious:
            SecurityUtils.log_security_event('SUSPICIOUS_REGISTRATION', f'Indicators: {indicators}')
            return jsonify({
                'success': False,
                'message': 'Request blocked for security reasons'
            }), 403
        
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['username', 'email', 'password', 'role']
        for field in required_fields:
            if not data.get(field):
                return jsonify({
                    'success': False,
                    'message': f'{field} is required'
                }), 400
        
        # Create admin object
        admin = Admin(data)
        
        # Validate admin data
        validation_errors = admin.validate()
        if validation_errors:
            return jsonify({
                'success': False,
                'message': 'Validation failed',
                'errors': validation_errors
            }), 400
        
        # Enhanced password validation
        is_valid_password, password_errors = SecurityUtils.validate_password(data.get('password'))
        if not is_valid_password:
            return jsonify({
                'success': False,
                'message': 'Password does not meet security requirements',
                'errors': password_errors
            }), 400
        
        # Enhanced email validation
        is_valid_email, email_errors = SecurityUtils.validate_email(data.get('email'))
        if not is_valid_email:
            return jsonify({
                'success': False,
                'message': 'Invalid email address',
                'errors': email_errors
            }), 400
        
        # Check for existing admin
        if admin_repository.exists(username=data.get('username'), email=data.get('email')):
            return jsonify({
                'success': False,
                'message': 'Admin with this username or email already exists'
            }), 400
        
        # Set password
        if not admin.set_password(data.get('password')):
            return jsonify({
                'success': False,
                'message': 'Failed to set password'
            }), 500
        
        # Create admin
        if admin_repository.create(admin):
            SecurityUtils.log_security_event('ADMIN_REGISTERED', f'New admin registered: {admin.username}', admin.id)
            return jsonify({
                'success': True,
                'message': 'Admin registered successfully',
                'admin': admin.to_dict()
            }), 201
        else:
            return jsonify({
                'success': False,
                'message': 'Failed to register admin'
            }), 500
            
    except Exception as e:
        logging.error(f"Error in register_admin: {e}")
        return jsonify({
            'success': False,
            'message': 'Internal server error'
        }), 500

@admin_bp.route('/login', methods=['POST'])
@csrf_protected
def login_admin():
    """Authenticate admin user"""
    try:
        # Check for suspicious requests
        is_suspicious, indicators = SecurityUtils.is_suspicious_request()
        if is_suspicious:
            SecurityUtils.log_security_event('SUSPICIOUS_LOGIN', f'Indicators: {indicators}')
            return jsonify({
                'success': False,
                'message': 'Request blocked for security reasons'
            }), 403
        
        data = request.get_json()
        
        # Validate required fields
        if not data.get('username') or not data.get('password'):
            return jsonify({
                'success': False,
                'message': 'Username and password are required'
            }), 400
        
        username = SecurityUtils.sanitize_input(data.get('username')).strip()
        password = data.get('password')
        
        # Get admin from database
        admin = admin_repository.get_by_username(username)
        
        if not admin:
            SecurityUtils.log_security_event('LOGIN_FAILED', f'Invalid username: {username}')
            return jsonify({
                'success': False,
                'message': 'Invalid credentials'
            }), 401
        
        # Check if account is locked
        if admin.is_locked():
            return jsonify({
                'success': False,
                'message': 'Account is temporarily locked. Please try again later.'
            }), 423
        
        # Check if account is active
        if not admin.is_active:
            return jsonify({
                'success': False,
                'message': 'Account is deactivated'
            }), 403
        
        # Verify password
        if admin.verify_password(password):
            # Reset login attempts
            admin.reset_login_attempts()
            admin_repository.update(admin)
            
            # Create session
            session['is_authenticated'] = True
            session['admin_id'] = admin.id
            session['admin_username'] = admin.username
            session['admin_email'] = admin.email
            session['admin_role'] = admin.role
            session['last_activity'] = SecurityUtils.update_session_activity()
            
            SecurityUtils.log_security_event('LOGIN_SUCCESS', f'Admin logged in: {admin.username}', admin.id)
            
            return jsonify({
                'success': True,
                'message': 'Login successful',
                'user': {
                    'id': admin.id,
                    'username': admin.username,
                    'email': admin.email,
                    'role': admin.role
                }
            }), 200
        else:
            # Increment login attempts
            if admin.increment_login_attempts():
                admin_repository.update(admin)
                SecurityUtils.log_security_event('ACCOUNT_LOCKED', f'Account locked: {admin.username}', admin.id)
                return jsonify({
                    'success': False,
                    'message': 'Account locked due to multiple failed attempts'
                }), 423
            else:
                admin_repository.update(admin)
                SecurityUtils.log_security_event('LOGIN_FAILED', f'Invalid password for: {admin.username}', admin.id)
                return jsonify({
                    'success': False,
                    'message': 'Invalid credentials'
                }), 401
            
    except Exception as e:
        logging.error(f"Error in login_admin: {e}")
        return jsonify({
            'success': False,
            'message': 'Internal server error'
        }), 500

@admin_bp.route('/logout', methods=['POST'])
@admin_required
def logout_admin():
    """Logout admin user"""
    try:
        admin_id = session.get('admin_id')
        username = session.get('admin_username')
        
        # Clear session
        session.clear()
        
        SecurityUtils.log_security_event('LOGOUT', f'Admin logged out: {username}', admin_id)
        
        return jsonify({
            'success': True,
            'message': 'Logged out successfully'
        }), 200
        
    except Exception as e:
        logging.error(f"Error in logout_admin: {e}")
        return jsonify({
            'success': False,
            'message': 'Internal server error'
        }), 500

@admin_bp.route('/list', methods=['GET'])
@admin_required
def list_admins():
    """Get list of all admin users"""
    try:
        page = int(request.args.get('page', 1))
        page_size = min(int(request.args.get('page_size', 20)), 100)
        
        admins = admin_repository.get_all(page, page_size)
        total = admin_repository.count()
        
        return jsonify({
            'success': True,
            'admins': [admin.to_dict() for admin in admins],
            'pagination': {
                'page': page,
                'page_size': page_size,
                'total': total,
                'pages': (total + page_size - 1) // page_size
            }
        }), 200
        
    except Exception as e:
        logging.error(f"Error in list_admins: {e}")
        return jsonify({
            'success': False,
            'message': 'Internal server error'
        }), 500

@admin_bp.route('/<admin_id>', methods=['DELETE'])
@super_admin_required
@csrf_protected
def delete_admin(admin_id):
    """Delete an admin user"""
    try:
        # Validate admin_id format
        if not admin_id or len(admin_id) != 24:
            return jsonify({
                'success': False,
                'message': 'Invalid admin ID format'
            }), 400
        
        # Prevent self-deletion
        current_admin_id = session.get('admin_id')
        if admin_id == current_admin_id:
            return jsonify({
                'success': False,
                'message': 'Cannot delete your own account'
            }), 400
        
        # Get admin to delete
        admin = admin_repository.get_by_id(admin_id)
        if not admin:
            return jsonify({
                'success': False,
                'message': 'Admin not found'
            }), 404
        
        # Delete admin
        if admin_repository.delete(admin_id):
            SecurityUtils.log_security_event('ADMIN_DELETED', f'Admin deleted: {admin.username}', current_admin_id)
            return jsonify({
                'success': True,
                'message': 'Admin deleted successfully'
            }), 200
        else:
            return jsonify({
                'success': False,
                'message': 'Failed to delete admin'
            }), 500
            
    except Exception as e:
        logging.error(f"Error in delete_admin: {e}")
        return jsonify({
            'success': False,
            'message': 'Internal server error'
        }), 500

@admin_bp.route('/<admin_id>', methods=['PUT'])
@super_admin_required
@csrf_protected
def update_admin(admin_id):
    """Update an admin user"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'message': 'No data provided'
            }), 400
        
        # Get admin to update
        admin = admin_repository.get_by_id(admin_id)
        if not admin:
            return jsonify({
                'success': False,
                'message': 'Admin not found'
            }), 404
        
        # Update allowed fields
        allowed_fields = ['email', 'role', 'is_active', 'permissions', 'preferences']
        for field, value in data.items():
            if field in allowed_fields and hasattr(admin, field):
                setattr(admin, field, value)
        
        # Validate updated admin
        validation_errors = admin.validate()
        if validation_errors:
            return jsonify({
                'success': False,
                'message': 'Validation failed',
                'errors': validation_errors
            }), 400
        
        # Update admin
        if admin_repository.update(admin):
            current_admin_id = session.get('admin_id')
            SecurityUtils.log_security_event('ADMIN_UPDATED', f'Admin updated: {admin.username}', current_admin_id)
            return jsonify({
                'success': True,
                'message': 'Admin updated successfully',
                'admin': admin.to_dict()
            }), 200
        else:
            return jsonify({
                'success': False,
                'message': 'Failed to update admin'
            }), 500
            
    except Exception as e:
        logging.error(f"Error in update_admin: {e}")
        return jsonify({
            'success': False,
            'message': 'Internal server error'
        }), 500

@admin_bp.route('/profile', methods=['GET'])
@admin_required
def get_profile():
    """Get current admin profile"""
    try:
        admin_id = session.get('admin_id')
        admin = admin_repository.get_by_id(admin_id)
        
        if admin:
            return jsonify({
                'success': True,
                'admin': admin.to_dict()
            }), 200
        else:
            return jsonify({
                'success': False,
                'message': 'Profile not found'
            }), 404
            
    except Exception as e:
        logging.error(f"Error in get_profile: {e}")
        return jsonify({
            'success': False,
            'message': 'Internal server error'
        }), 500

@admin_bp.route('/profile', methods=['PUT'])
@admin_required
@csrf_protected
def update_profile():
    """Update current admin profile"""
    try:
        admin_id = session.get('admin_id')
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'message': 'No data provided'
            }), 400
        
        # Get current admin
        admin = admin_repository.get_by_id(admin_id)
        if not admin:
            return jsonify({
                'success': False,
                'message': 'Profile not found'
            }), 404
        
        # Update allowed fields (excluding role for self-update)
        allowed_fields = ['email', 'preferences']
        for field, value in data.items():
            if field in allowed_fields and hasattr(admin, field):
                setattr(admin, field, value)
        
        # Handle password change
        if 'current_password' in data and 'new_password' in data:
            if admin.verify_password(data['current_password']):
                if not admin.set_password(data['new_password']):
                    return jsonify({
                        'success': False,
                        'message': 'Failed to set new password'
                    }), 500
            else:
                return jsonify({
                    'success': False,
                    'message': 'Current password is incorrect'
                }), 400
        
        # Validate updated admin
        validation_errors = admin.validate()
        if validation_errors:
            return jsonify({
                'success': False,
                'message': 'Validation failed',
                'errors': validation_errors
            }), 400
        
        # Update admin
        if admin_repository.update(admin):
            SecurityUtils.log_security_event('PROFILE_UPDATED', f'Profile updated: {admin.username}', admin_id)
            return jsonify({
                'success': True,
                'message': 'Profile updated successfully',
                'admin': admin.to_dict()
            }), 200
        else:
            return jsonify({
                'success': False,
                'message': 'Failed to update profile'
            }), 500
            
    except Exception as e:
        logging.error(f"Error in update_profile: {e}")
        return jsonify({
            'success': False,
            'message': 'Internal server error'
        }), 500
