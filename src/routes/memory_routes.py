"""
Memory Routes - Professional API endpoints for AI memory system
"""

from flask import Blueprint, request, jsonify
from src.services.memory_service import get_memory_service
from src.utils.security_utils_fixed import admin_required, csrf_protected
import logging

# Create Blueprint
memory_bp = Blueprint('memory', __name__, url_prefix='/api/memory')

# Initialize memory service
memory_service = get_memory_service()

@memory_bp.route('/status', methods=['GET'])
@admin_required
def memory_status():
    """Get memory system status and statistics"""
    try:
        if not memory_service.is_initialized():
            return jsonify({
                'success': False,
                'message': 'Memory service not initialized'
            }), 503
        
        # Get memory statistics
        stats = memory_service.get_memory_stats()
        
        return jsonify({
            'success': True,
            'status': 'active',
            'stats': stats
        }), 200
        
    except Exception as e:
        logging.error(f"Error in memory_status: {e}")
        return jsonify({
            'success': False,
            'message': 'Internal server error'
        }), 500

@memory_bp.route('/search', methods=['POST'])
@admin_required
@csrf_protected
def search_memory():
    """Search memory using semantic similarity"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'message': 'No data provided'
            }), 400
        
        # Validate required fields
        query = data.get('query', '').strip()
        if not query:
            return jsonify({
                'success': False,
                'message': 'Query is required'
            }), 400
        
        # Get search parameters
        category = data.get('category')
        limit = min(int(data.get('limit', 10)), 50)
        filters = data.get('filters', {})
        
        # Perform semantic search
        results = memory_service.search_memory(
            query=query,
            category=category,
            limit=limit,
            filters=filters
        )
        
        return jsonify({
            'success': True,
            'query': query,
            'results': results,
            'total': len(results)
        }), 200
        
    except Exception as e:
        logging.error(f"Error in search_memory: {e}")
        return jsonify({
            'success': False,
            'message': 'Internal server error'
        }), 500

@memory_bp.route('/store', methods=['POST'])
@admin_required
@csrf_protected
def store_memory():
    """Store a memory entry"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'message': 'No data provided'
            }), 400
        
        # Validate required fields
        content = data.get('content', '').strip()
        if not content:
            return jsonify({
                'success': False,
                'message': 'Content is required'
            }), 400
        
        # Extract optional fields
        category = data.get('category', 'general')
        content_type = data.get('content_type', 'text')
        client_id = data.get('client_id')
        lead_id = data.get('lead_id')
        conversation_id = data.get('conversation_id')
        project_id = data.get('project_id')
        tags = data.get('tags', [])
        lead_category = data.get('lead_category', 'unspecified')
        metadata = data.get('metadata', {})
        
        # Store memory entry
        memory_id = memory_service.store_memory(
            content=content,
            category=category,
            content_type=content_type,
            client_id=client_id,
            lead_id=lead_id,
            conversation_id=conversation_id,
            project_id=project_id,
            tags=tags,
            lead_category=lead_category,
            metadata=metadata
        )
        
        if memory_id:
            return jsonify({
                'success': True,
                'message': 'Memory stored successfully',
                'memory_id': memory_id
            }), 201
        else:
            return jsonify({
                'success': False,
                'message': 'Failed to store memory'
            }), 500
            
    except Exception as e:
        logging.error(f"Error in store_memory: {e}")
        return jsonify({
            'success': False,
            'message': 'Internal server error'
        }), 500

@memory_bp.route('/client/<client_id>/context', methods=['GET'])
@admin_required
def get_client_context(client_id):
    """Get comprehensive client context"""
    try:
        # Get query parameters
        limit = min(int(request.args.get('limit', 20)), 50)
        include_conversations = request.args.get('include_conversations', 'true').lower() == 'true'
        include_projects = request.args.get('include_projects', 'true').lower() == 'true'
        
        # Retrieve client context
        context = memory_service.retrieve_client_context(
            client_id=client_id,
            limit=limit,
            include_conversations=include_conversations,
            include_projects=include_projects
        )
        
        return jsonify({
            'success': True,
            'client_id': client_id,
            'context': context
        }), 200
        
    except Exception as e:
        logging.error(f"Error in get_client_context: {e}")
        return jsonify({
            'success': False,
            'message': 'Internal server error'
        }), 500

@memory_bp.route('/projects/related', methods=['POST'])
@admin_required
@csrf_protected
def get_related_projects():
    """Get projects related to a query"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'message': 'No data provided'
            }), 400
        
        # Validate required fields
        query = data.get('query', '').strip()
        if not query:
            return jsonify({
                'success': False,
                'message': 'Query is required'
            }), 400
        
        # Get optional parameters
        client_id = data.get('client_id')
        limit = min(int(data.get('limit', 5)), 20)
        
        # Get related projects
        projects = memory_service.get_related_projects(
            query=query,
            client_id=client_id,
            limit=limit
        )
        
        return jsonify({
            'success': True,
            'query': query,
            'projects': projects,
            'total': len(projects)
        }), 200
        
    except Exception as e:
        logging.error(f"Error in get_related_projects: {e}")
        return jsonify({
            'success': False,
            'message': 'Internal server error'
        }), 500

@memory_bp.route('/conversation/<conversation_id>/history', methods=['GET'])
@admin_required
def get_conversation_history(conversation_id):
    """Get conversation history by ID"""
    try:
        # Get query parameters
        limit = min(int(request.args.get('limit', 50)), 100)
        
        # Get conversation history
        history = memory_service.get_conversation_history(
            conversation_id=conversation_id,
            limit=limit
        )
        
        return jsonify({
            'success': True,
            'conversation_id': conversation_id,
            'history': history,
            'total': len(history)
        }), 200
        
    except Exception as e:
        logging.error(f"Error in get_conversation_history: {e}")
        return jsonify({
            'success': False,
            'message': 'Internal server error'
        }), 500

@memory_bp.route('/conversation/store', methods=['POST'])
@admin_required
@csrf_protected
def store_conversation_thread():
    """Store a conversation thread with multiple messages"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'message': 'No data provided'
            }), 400
        
        # Validate required fields
        messages = data.get('messages', [])
        conversation_id = data.get('conversation_id')
        
        if not messages or not conversation_id:
            return jsonify({
                'success': False,
                'message': 'Messages and conversation_id are required'
            }), 400
        
        # Get optional fields
        client_id = data.get('client_id')
        lead_id = data.get('lead_id')
        
        # Store conversation thread
        success = memory_service.store_conversation_thread(
            messages=messages,
            conversation_id=conversation_id,
            client_id=client_id,
            lead_id=lead_id
        )
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Conversation thread stored successfully',
                'conversation_id': conversation_id,
                'messages_stored': len(messages)
            }), 201
        else:
            return jsonify({
                'success': False,
                'message': 'Failed to store conversation thread'
            }), 500
            
    except Exception as e:
        logging.error(f"Error in store_conversation_thread: {e}")
        return jsonify({
            'success': False,
            'message': 'Internal server error'
        }), 500

@memory_bp.route('/<memory_id>', methods=['PUT'])
@admin_required
@csrf_protected
def update_memory_entry(memory_id):
    """Update a memory entry"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'message': 'No data provided'
            }), 400
        
        # Get optional update fields
        new_content = data.get('content')
        new_tags = data.get('tags')
        new_metadata = data.get('metadata')
        category = data.get('category', 'general')
        
        # Update memory entry
        success = memory_service.update_memory_entry(
            memory_id=memory_id,
            new_content=new_content,
            new_tags=new_tags,
            new_metadata=new_metadata
        )
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Memory entry updated successfully',
                'memory_id': memory_id
            }), 200
        else:
            return jsonify({
                'success': False,
                'message': 'Failed to update memory entry'
            }), 500
            
    except Exception as e:
        logging.error(f"Error in update_memory_entry: {e}")
        return jsonify({
            'success': False,
            'message': 'Internal server error'
        }), 500

@memory_bp.route('/<memory_id>', methods=['DELETE'])
@admin_required
@csrf_protected
def delete_memory_entry(memory_id):
    """Delete a memory entry"""
    try:
        # Get category from query parameters
        category = request.args.get('category', 'general')
        
        # Delete memory entry
        success = memory_service.delete_memory_entry(
            memory_id=memory_id,
            category=category
        )
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Memory entry deleted successfully',
                'memory_id': memory_id
            }), 200
        else:
            return jsonify({
                'success': False,
                'message': 'Failed to delete memory entry'
            }), 500
            
    except Exception as e:
        logging.error(f"Error in delete_memory_entry: {e}")
        return jsonify({
            'success': False,
            'message': 'Internal server error'
        }), 500

@memory_bp.route('/sample-data', methods=['POST'])
@admin_required
@csrf_protected
def generate_sample_data():
    """Generate sample data for testing"""
    try:
        # Generate sample data
        success = memory_service.generate_sample_data()
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Sample data generated successfully'
            }), 201
        else:
            return jsonify({
                'success': False,
                'message': 'Failed to generate sample data'
            }), 500
            
    except Exception as e:
        logging.error(f"Error in generate_sample_data: {e}")
        return jsonify({
            'success': False,
            'message': 'Internal server error'
        }), 500

@memory_bp.route('/health', methods=['GET'])
@admin_required
def memory_health():
    """Perform health check on memory system"""
    try:
        if not memory_service.is_initialized():
            return jsonify({
                'success': False,
                'status': 'unhealthy',
                'message': 'Memory service not initialized'
            }), 503
        
        # Get memory statistics
        stats = memory_service.get_memory_stats()
        
        # Determine health status
        is_healthy = (
            stats.get('status') == 'active' and
            stats.get('health', {}).get('status') == 'healthy'
        )
        
        return jsonify({
            'success': True,
            'status': 'healthy' if is_healthy else 'unhealthy',
            'stats': stats
        }), 200 if is_healthy else 503
        
    except Exception as e:
        logging.error(f"Error in memory_health: {e}")
        return jsonify({
            'success': False,
            'status': 'unhealthy',
            'message': 'Health check failed',
            'error': str(e)
        }), 503
