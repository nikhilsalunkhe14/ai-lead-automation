"""
Lead Routes - Professional API endpoints for lead management
"""

from flask import Blueprint, request, jsonify, session
from src.services.lead_service import LeadService
from src.utils.security_utils_fixed import admin_required, csrf_protected, SecurityUtils
import logging

# Create Blueprint
lead_bp = Blueprint('leads', __name__, url_prefix='/api/leads')

# Initialize service
lead_service = LeadService()

@lead_bp.route('/', methods=['POST'])
@csrf_protected
def create_lead():
    """Create a new lead"""
    try:
        data = request.get_json()
        
        # Validate request data
        if not data:
            return jsonify({
                'success': False,
                'message': 'No data provided'
            }), 400
        
        # Create lead
        result = lead_service.create_lead(data)
        
        if result['success']:
            return jsonify(result), 201
        else:
            return jsonify(result), 400
            
    except Exception as e:
        logging.error(f"Error in create_lead: {e}")
        return jsonify({
            'success': False,
            'message': 'Internal server error'
        }), 500

@lead_bp.route('/', methods=['GET'])
@admin_required
def get_leads():
    """Get leads with pagination and filtering"""
    try:
        # Get pagination parameters
        page = int(request.args.get('page', 1))
        page_size = min(int(request.args.get('page_size', 20)), 100)
        
        # Get filter parameters
        filters = {}
        if request.args.get('status'):
            filters['status'] = request.args.get('status')
        if request.args.get('priority'):
            filters['priority'] = request.args.get('priority')
        if request.args.get('search'):
            filters['search'] = request.args.get('search')
        
        # Get leads
        result = lead_service.get_leads(page, page_size, filters)
        
        if result['success']:
            return jsonify(result), 200
        else:
            return jsonify(result), 400
            
    except Exception as e:
        logging.error(f"Error in get_leads: {e}")
        return jsonify({
            'success': False,
            'message': 'Internal server error'
        }), 500

@lead_bp.route('/<lead_id>', methods=['GET'])
@admin_required
def get_lead(lead_id):
    """Get a specific lead"""
    try:
        result = lead_service.get_lead(lead_id)
        
        if result['success']:
            return jsonify(result), 200
        else:
            return jsonify(result), 404
            
    except Exception as e:
        logging.error(f"Error in get_lead: {e}")
        return jsonify({
            'success': False,
            'message': 'Internal server error'
        }), 500

@lead_bp.route('/<lead_id>', methods=['PUT'])
@admin_required
@csrf_protected
def update_lead(lead_id):
    """Update a lead"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'message': 'No data provided'
            }), 400
        
        result = lead_service.update_lead(lead_id, data)
        
        if result['success']:
            return jsonify(result), 200
        else:
            return jsonify(result), 400
            
    except Exception as e:
        logging.error(f"Error in update_lead: {e}")
        return jsonify({
            'success': False,
            'message': 'Internal server error'
        }), 500

@lead_bp.route('/<lead_id>', methods=['DELETE'])
@admin_required
@csrf_protected
def delete_lead(lead_id):
    """Delete a lead"""
    try:
        result = lead_service.delete_lead(lead_id)
        
        if result['success']:
            return jsonify(result), 200
        else:
            return jsonify(result), 404
            
    except Exception as e:
        logging.error(f"Error in delete_lead: {e}")
        return jsonify({
            'success': False,
            'message': 'Internal server error'
        }), 500

@lead_bp.route('/<lead_id>/status', methods=['PUT'])
@admin_required
@csrf_protected
def update_lead_status(lead_id):
    """Update lead status"""
    try:
        data = request.get_json()
        new_status = data.get('status')
        
        if not new_status:
            return jsonify({
                'success': False,
                'message': 'Status is required'
            }), 400
        
        result = lead_service.update_lead_status(lead_id, new_status)
        
        if result['success']:
            return jsonify(result), 200
        else:
            return jsonify(result), 400
            
    except Exception as e:
        logging.error(f"Error in update_lead_status: {e}")
        return jsonify({
            'success': False,
            'message': 'Internal server error'
        }), 500

@lead_bp.route('/<lead_id>/notes', methods=['POST'])
@admin_required
@csrf_protected
def add_lead_note(lead_id):
    """Add a note to a lead"""
    try:
        data = request.get_json()
        note = data.get('note')
        author = data.get('author', session.get('admin_username', 'system'))
        
        if not note:
            return jsonify({
                'success': False,
                'message': 'Note is required'
            }), 400
        
        result = lead_service.add_lead_note(lead_id, note, author)
        
        if result['success']:
            return jsonify(result), 200
        else:
            return jsonify(result), 400
            
    except Exception as e:
        logging.error(f"Error in add_lead_note: {e}")
        return jsonify({
            'success': False,
            'message': 'Internal server error'
        }), 500

@lead_bp.route('/analytics', methods=['GET'])
@admin_required
def get_analytics():
    """Get lead analytics"""
    try:
        result = lead_service.get_analytics()
        
        if result['success']:
            return jsonify(result), 200
        else:
            return jsonify(result), 400
            
    except Exception as e:
        logging.error(f"Error in get_analytics: {e}")
        return jsonify({
            'success': False,
            'message': 'Internal server error'
        }), 500

@lead_bp.route('/export', methods=['GET'])
@admin_required
def export_leads():
    """Export leads in various formats"""
    try:
        # Get export format
        export_format = request.args.get('format', 'json')
        
        # Get filters
        filters = {}
        if request.args.get('status'):
            filters['status'] = request.args.get('status')
        if request.args.get('priority'):
            filters['priority'] = request.args.get('priority')
        
        result = lead_service.export_leads(export_format, filters)
        
        if result['success']:
            return jsonify(result), 200
        else:
            return jsonify(result), 400
            
    except Exception as e:
        logging.error(f"Error in export_leads: {e}")
        return jsonify({
            'success': False,
            'message': 'Internal server error'
        }), 500

@lead_bp.route('/score', methods=['POST'])
@admin_required
@csrf_protected
def score_lead():
    """Score a lead using AI"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'message': 'No data provided'
            }), 400
        
        result = lead_service.ai_service.score_lead(data)
        
        return jsonify({
            'success': True,
            'score': result
        }), 200
            
    except Exception as e:
        logging.error(f"Error in score_lead: {e}")
        return jsonify({
            'success': False,
            'message': 'Internal server error'
        }), 500
