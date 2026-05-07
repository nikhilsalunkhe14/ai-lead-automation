"""
Context Routes - Professional API endpoints for context management and analysis
"""

from flask import Blueprint, request, jsonify
from src.services.context_service import get_context_service
from src.services.memory_service import get_memory_service
from src.utils.ai_service import AIService
from src.utils.security_utils_fixed import admin_required, csrf_protected
import logging

# Create Blueprint
context_bp = Blueprint('context', __name__, url_prefix='/api/context')

# Initialize services
context_service = get_context_service()
memory_service = get_memory_service()
ai_service = AIService()

@context_bp.route('/client/<client_id>', methods=['GET'])
@admin_required
def get_client_context(client_id):
    """Get comprehensive context for a client"""
    try:
        # Get query parameters
        limit = min(int(request.args.get('limit', 20)), 50)
        include_conversations = request.args.get('include_conversations', 'true').lower() == 'true'
        include_projects = request.args.get('include_projects', 'true').lower() == 'true'
        
        # Build context for client
        context_data = context_service.build_context_for_conversation(
            message="",  # Empty message to get all client context
            client_id=client_id,
            max_tokens=4000
        )
        
        # Get additional client information
        client_context = memory_service.retrieve_client_context(
            client_id=client_id,
            limit=limit,
            include_conversations=include_conversations,
            include_projects=include_projects
        )
        
        # Analyze context usage
        context_analysis = context_service.analyze_context_usage(context_data)
        
        return jsonify({
            'success': True,
            'client_id': client_id,
            'context': context_data,
            'client_context': client_context,
            'analysis': context_analysis
        }), 200
        
    except Exception as e:
        logging.error(f"Error in get_client_context: {e}")
        return jsonify({
            'success': False,
            'message': 'Internal server error'
        }), 500

@context_bp.route('/analyze', methods=['POST'])
@admin_required
@csrf_protected
def analyze_context():
    """Analyze context for a message and client"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'message': 'No data provided'
            }), 400
        
        # Extract parameters
        message = data.get('message', '').strip()
        client_id = data.get('client_id')
        conversation_id = data.get('conversation_id')
        max_tokens = min(int(data.get('max_tokens', 4000)), 8000)
        
        if not message:
            return jsonify({
                'success': False,
                'message': 'Message is required'
            }), 400
        
        # Build context
        context_data = context_service.build_context_for_conversation(
            message=message,
            client_id=client_id,
            conversation_id=conversation_id,
            max_tokens=max_tokens
        )
        
        # Analyze context usage
        context_analysis = context_service.analyze_context_usage(context_data)
        
        # Generate contextual AI response
        ai_response = ai_service.generate_contextual_response(
            message=message,
            client_id=client_id,
            conversation_id=conversation_id,
            max_context_tokens=max_tokens
        )
        
        return jsonify({
            'success': True,
            'message': message,
            'context': context_data,
            'analysis': context_analysis,
            'ai_response': ai_response
        }), 200
        
    except Exception as e:
        logging.error(f"Error in analyze_context: {e}")
        return jsonify({
            'success': False,
            'message': 'Internal server error'
        }), 500

@context_bp.route('/related', methods=['POST'])
@admin_required
@csrf_protected
def get_related_context():
    """Get context related to a query"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'message': 'No data provided'
            }), 400
        
        # Extract parameters
        query = data.get('query', '').strip()
        client_id = data.get('client_id')
        category = data.get('category')
        limit = min(int(data.get('limit', 10)), 50)
        
        if not query:
            return jsonify({
                'success': False,
                'message': 'Query is required'
            }), 400
        
        # Search for related memories
        related_memories = memory_service.search_memory(
            query=query,
            category=category,
            limit=limit,
            filters={'client_id': client_id} if client_id else None
        )
        
        # Rank memories
        ranked_memories = context_service._rank_memories(
            memories=related_memories,
            message=query,
            client_id=client_id
        )
        
        # Build context for analysis
        context_data = context_service.build_context_for_conversation(
            message=query,
            client_id=client_id,
            max_tokens=2000
        )
        
        return jsonify({
            'success': True,
            'query': query,
            'related_memories': ranked_memories,
            'context': context_data,
            'total_found': len(ranked_memories)
        }), 200
        
    except Exception as e:
        logging.error(f"Error in get_related_context: {e}")
        return jsonify({
            'success': False,
            'message': 'Internal server error'
        }), 500

@context_bp.route('/conversation/<conversation_id>/context', methods=['GET'])
@admin_required
def get_conversation_context(conversation_id):
    """Get context for a specific conversation"""
    try:
        # Get query parameters
        limit = min(int(request.args.get('limit', 20)), 50)
        
        # Get conversation history
        conversation_history = memory_service.get_conversation_history(
            conversation_id=conversation_id,
            limit=limit
        )
        
        # Build context for conversation
        context_data = context_service.build_context_for_conversation(
            message="",  # Empty to get conversation context
            conversation_id=conversation_id,
            max_tokens=3000
        )
        
        # Analyze conversation
        conversation_analysis = {
            'total_messages': len(conversation_history),
            'context_used': len(context_data['context']),
            'conversation_continuity': _analyze_conversation_continuity(conversation_history),
            'engagement_level': _calculate_engagement_level(conversation_history)
        }
        
        return jsonify({
            'success': True,
            'conversation_id': conversation_id,
            'history': conversation_history,
            'context': context_data,
            'analysis': conversation_analysis
        }), 200
        
    except Exception as e:
        logging.error(f"Error in get_conversation_context: {e}")
        return jsonify({
            'success': False,
            'message': 'Internal server error'
        }), 500

@context_bp.route('/test', methods=['POST'])
@admin_required
@csrf_protected
def test_context_generation():
    """Test context generation with sample data"""
    try:
        data = request.get_json()
        
        # Use sample data if not provided
        test_message = data.get('message', 'I also want payment integration for my e-commerce website')
        test_client_id = data.get('client_id', 'client_001')
        
        # Generate contextual response
        ai_response = ai_service.generate_contextual_response(
            message=test_message,
            client_id=test_client_id,
            max_context_tokens=3000
        )
        
        # Get context details
        context_data = ai_response.get('context_data', {})
        
        return jsonify({
            'success': True,
            'test_message': test_message,
            'test_client_id': test_client_id,
            'context_summary': context_data.get('summary', ''),
            'context_count': len(context_data.get('context', [])),
            'ai_response': ai_response,
            'context_used': ai_response.get('context_used', False)
        }), 200
        
    except Exception as e:
        logging.error(f"Error in test_context_generation: {e}")
        return jsonify({
            'success': False,
            'message': 'Internal server error'
        }), 500

@context_bp.route('/stats', methods=['GET'])
@admin_required
def get_context_stats():
    """Get context usage statistics"""
    try:
        # Get memory system stats
        memory_stats = memory_service.get_memory_stats()
        
        # Context-specific stats
        context_stats = {
            'total_context_requests': 0,  # Would be tracked in a real implementation
            'average_context_size': 0,
            'context_hit_rate': 0,
            'most_active_clients': [],
            'context_efficiency': 'good'
        }
        
        return jsonify({
            'success': True,
            'memory_stats': memory_stats,
            'context_stats': context_stats,
            'timestamp': request.args.get('timestamp', 'current')
        }), 200
        
    except Exception as e:
        logging.error(f"Error in get_context_stats: {e}")
        return jsonify({
            'success': False,
            'message': 'Internal server error'
        }), 500

@context_bp.route('/debug', methods=['POST'])
@admin_required
@csrf_protected
def debug_context():
    """Debug context retrieval and ranking"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'message': 'No data provided'
            }), 400
        
        message = data.get('message', '').strip()
        client_id = data.get('client_id')
        
        if not message:
            return jsonify({
                'success': False,
                'message': 'Message is required'
            }), 400
        
        # Get raw memories
        raw_memories = context_service._retrieve_relevant_memories(
            message=message,
            client_id=client_id
        )
        
        # Get ranked memories
        ranked_memories = context_service._rank_memories(
            memories=raw_memories,
            message=message,
            client_id=client_id
        )
        
        # Get final context
        context_data = context_service.build_context_for_conversation(
            message=message,
            client_id=client_id
        )
        
        # Debug information
        debug_info = {
            'raw_retrieved': len(raw_memories),
            'after_ranking': len(ranked_memories),
            'in_final_context': len(context_data['context']),
            'token_usage': context_data['total_tokens'],
            'retrieval_sources': {},
            'ranking_details': []
        }
        
        # Analyze retrieval sources
        for memory in raw_memories:
            source = memory.get('retrieval_reason', 'unknown')
            debug_info['retrieval_sources'][source] = debug_info['retrieval_sources'].get(source, 0) + 1
        
        # Add ranking details for top memories
        for i, memory in enumerate(ranked_memories[:5]):
            debug_info['ranking_details'].append({
                'rank': i + 1,
                'id': memory.get('id'),
                'content_preview': memory.get('content', '')[:100] + '...',
                'final_score': memory.get('final_score', 0),
                'relevance_score': memory.get('relevance_score', 0),
                'importance_score': memory.get('importance_score', 0),
                'recency_score': memory.get('recency_score', 0),
                'similarity': memory.get('similarity', 0),
                'retrieval_reason': memory.get('retrieval_reason', 'unknown')
            })
        
        return jsonify({
            'success': True,
            'debug_info': debug_info,
            'raw_memories': raw_memories[:10],  # Limit for response size
            'ranked_memories': ranked_memories[:10],
            'final_context': context_data
        }), 200
        
    except Exception as e:
        logging.error(f"Error in debug_context: {e}")
        return jsonify({
            'success': False,
            'message': 'Internal server error'
        }), 500

def _analyze_conversation_continuity(conversation_history):
    """Analyze conversation continuity"""
    if not conversation_history:
        return 'no_history'
    
    # Simple continuity analysis based on message flow
    message_count = len(conversation_history)
    
    if message_count == 1:
        return 'single_message'
    elif message_count <= 3:
        return 'short_conversation'
    elif message_count <= 10:
        return 'active_conversation'
    else:
        return 'extended_conversation'

def _calculate_engagement_level(conversation_history):
    """Calculate engagement level from conversation history"""
    if not conversation_history:
        return 'none'
    
    # Simple engagement calculation based on message count and content length
    total_length = sum(len(msg.get('content', '')) for msg in conversation_history)
    avg_length = total_length / len(conversation_history)
    
    if avg_length > 100:
        return 'high'
    elif avg_length > 50:
        return 'medium'
    else:
        return 'low'
