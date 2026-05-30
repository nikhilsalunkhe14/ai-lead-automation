"""
Context Service - Professional context management for AI memory system
Handles intelligent memory retrieval, ranking, and context building
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
from src.services.memory_service import get_memory_service
from src.services.vector_service import get_vector_service
from src.models.memory import MemoryEntry
from src.config.settings import settings

class ContextService:
    """
    Professional context service for intelligent memory retrieval and management
    Handles context ranking, filtering, and token-safe context building
    """
    
    def __init__(self):
        self.memory_service = get_memory_service()
        self.vector_service = get_vector_service()
        self.max_context_tokens = settings.MEMORY_CONFIG.MAX_CONTEXT_TOKENS
        self.similarity_threshold = settings.MEMORY_CONFIG.SIMILARITY_THRESHOLD
        self.context_window_hours = settings.MEMORY_CONFIG.CONTEXT_WINDOW_HOURS
        
    def build_context_for_conversation(self, 
                                   message: str,
                                   client_id: Optional[str] = None,
                                   conversation_id: Optional[str] = None,
                                   max_tokens: Optional[int] = None) -> Dict[str, Any]:
        """
        Build comprehensive context for AI response generation
        
        Args:
            message: Current user message
            client_id: Optional client identifier
            conversation_id: Optional conversation identifier
            max_tokens: Maximum tokens for context
            
        Returns:
            Dictionary with ranked context and metadata
        """
        try:
            if not self.memory_service.is_initialized():
                return {
                    'context': [],
                    'summary': 'Memory system not available',
                    'total_tokens': 0,
                    'retrieved_count': 0
                }
            
            # Initialize context building
            context_builder = ContextBuilder(max_tokens or self.max_context_tokens)
            
            # Retrieve relevant memories
            relevant_memories = self._retrieve_relevant_memories(
                message=message,
                client_id=client_id,
                conversation_id=conversation_id
            )
            
            # Rank and filter memories
            ranked_memories = self._rank_memories(
                memories=relevant_memories,
                message=message,
                client_id=client_id,
                conversation_id=conversation_id
            )
            
            # Build token-safe context
            final_context = context_builder.build_context(ranked_memories)
            
            # Generate context summary
            context_summary = self._generate_context_summary(final_context)
            
            return {
                'context': final_context,
                'summary': context_summary,
                'total_tokens': context_builder.used_tokens,
                'retrieved_count': len(ranked_memories),
                'client_id': client_id,
                'conversation_id': conversation_id,
                'retrieval_timestamp': datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logging.error(f"❌ Error building context: {e}")
            return {
                'context': [],
                'summary': 'Context building failed',
                'total_tokens': 0,
                'retrieved_count': 0,
                'error': str(e)
            }
    
    def _retrieve_relevant_memories(self, 
                                 message: str,
                                 client_id: Optional[str] = None,
                                 conversation_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Retrieve relevant memories from multiple sources
        
        Args:
            message: Current message for semantic search
            client_id: Client identifier for filtering
            conversation_id: Conversation identifier for threading
            
        Returns:
            List of relevant memory entries
        """
        try:
            all_memories = []
            
            # 1. Semantic search for similar conversations
            conversation_memories = self.memory_service.search_memory(
                query=message,
                category="conversation",
                limit=15,
                filters={'client_id': client_id} if client_id else None
            )
            all_memories.extend(conversation_memories)
            
            # 2. Retrieve client-specific context
            if client_id:
                client_context = self.memory_service.retrieve_client_context(
                    client_id=client_id,
                    limit=10,
                    include_conversations=True,
                    include_projects=True
                )
                
                # Add conversation memories
                for conv in client_context.get('conversations', []):
                    conv['retrieval_reason'] = 'client_context'
                    all_memories.append(conv)
                
                # Add project memories
                for proj in client_context.get('projects', []):
                    proj['retrieval_reason'] = 'client_project'
                    all_memories.append(proj)
            
            # 3. Retrieve related projects
            project_memories = self.memory_service.get_related_projects(
                query=message,
                client_id=client_id,
                limit=10
            )
            for proj in project_memories:
                proj['retrieval_reason'] = 'semantic_project'
                all_memories.append(proj)
            
            # 4. Get conversation history for threading
            if conversation_id:
                conversation_history = self.memory_service.get_conversation_history(
                    conversation_id=conversation_id,
                    limit=20
                )
                for conv in conversation_history:
                    conv['retrieval_reason'] = 'conversation_thread'
                    all_memories.append(conv)
            
            # Remove duplicates based on ID
            unique_memories = {}
            for memory in all_memories:
                memory_id = memory.get('id')
                if memory_id and memory_id not in unique_memories:
                    unique_memories[memory_id] = memory
                elif not memory_id:  # Handle memories without IDs
                    # Create a composite key for deduplication
                    key = f"{memory.get('content', '')[:50]}_{memory.get('created_at', '')}"
                    if key not in unique_memories:
                        unique_memories[key] = memory
            
            return list(unique_memories.values())
            
        except Exception as e:
            logging.error(f"❌ Error retrieving relevant memories: {e}")
            return []
    
    def _rank_memories(self, 
                      memories: List[Dict[str, Any]],
                      message: str,
                      client_id: Optional[str] = None,
                      conversation_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Rank memories by relevance and importance
        
        Args:
            memories: List of memory entries to rank
            message: Current message for relevance scoring
            client_id: Client identifier for prioritization
            conversation_id: Conversation identifier for threading
            
        Returns:
            List of ranked memory entries with scores
        """
        try:
            ranked_memories = []
            
            for memory in memories:
                # Calculate relevance score
                relevance_score = self._calculate_relevance_score(
                    memory=memory,
                    message=message,
                    client_id=client_id,
                    conversation_id=conversation_id
                )
                
                # Calculate importance score
                importance_score = self._calculate_importance_score(memory)
                
                # Calculate recency score
                recency_score = self._calculate_recency_score(memory)
                
                # Combine scores with weights
                final_score = (
                    relevance_score * 0.5 +      # 50% relevance
                    importance_score * 0.3 +      # 30% importance
                    recency_score * 0.2           # 20% recency
                )
                
                # Add scoring metadata
                memory['relevance_score'] = relevance_score
                memory['importance_score'] = importance_score
                memory['recency_score'] = recency_score
                memory['final_score'] = final_score
                memory['retrieval_reason'] = memory.get('retrieval_reason', 'semantic_search')
                
                ranked_memories.append(memory)
            
            # Sort by final score (descending)
            ranked_memories.sort(key=lambda x: x['final_score'], reverse=True)
            
            # Filter by minimum similarity threshold
            filtered_memories = [
                memory for memory in ranked_memories
                if memory.get('similarity', 0) >= self.similarity_threshold
            ]
            
            return filtered_memories
            
        except Exception as e:
            logging.error(f"❌ Error ranking memories: {e}")
            return memories
    
    def _calculate_relevance_score(self, 
                                memory: Dict[str, Any],
                                message: str,
                                client_id: Optional[str] = None,
                                conversation_id: Optional[str] = None) -> float:
        """
        Calculate relevance score for a memory entry
        
        Args:
            memory: Memory entry to score
            message: Current message
            client_id: Client identifier
            conversation_id: Conversation identifier
            
        Returns:
            Relevance score (0-1)
        """
        try:
            score = 0.0
            
            # Semantic similarity score (base score)
            similarity = memory.get('similarity', 0)
            score += similarity * 0.4
            
            # Client matching bonus
            memory_client_id = memory.get('metadata', {}).get('client_id')
            if client_id and memory_client_id == client_id:
                score += 0.3
            
            # Conversation threading bonus
            memory_conv_id = memory.get('metadata', {}).get('conversation_id')
            if conversation_id and memory_conv_id == conversation_id:
                score += 0.2
            
            # Content type relevance
            content_type = memory.get('metadata', {}).get('content_type', 'text')
            if content_type in ['requirement', 'summary']:
                score += 0.1
            
            # Lead category bonus
            lead_category = memory.get('metadata', {}).get('lead_category', 'unspecified')
            if lead_category in ['hot', 'warm']:
                score += 0.05
            
            return min(score, 1.0)
            
        except Exception as e:
            logging.error(f"❌ Error calculating relevance score: {e}")
            return 0.0
    
    def _calculate_importance_score(self, memory: Dict[str, Any]) -> float:
        """
        Calculate importance score for a memory entry
        
        Args:
            memory: Memory entry to score
            
        Returns:
            Importance score (0-1)
        """
        try:
            score = 0.0
            
            # Content type importance
            content_type = memory.get('metadata', {}).get('content_type', 'text')
            content_type_scores = {
                'requirement': 0.9,
                'summary': 0.8,
                'message': 0.6,
                'response': 0.5,
                'text': 0.4
            }
            score += content_type_scores.get(content_type, 0.4)
            
            # Lead category importance
            lead_category = memory.get('metadata', {}).get('lead_category', 'unspecified')
            lead_category_scores = {
                'hot': 0.9,
                'warm': 0.7,
                'cool': 0.5,
                'cold': 0.3,
                'unspecified': 0.2
            }
            score += lead_category_scores.get(lead_category, 0.2) * 0.3
            
            # Tag importance (more tags = more detailed)
            tags = memory.get('metadata', {}).get('tags', [])
            if len(tags) > 3:
                score += 0.2
            elif len(tags) > 1:
                score += 0.1
            
            # Length importance (longer content might be more detailed)
            content_length = len(memory.get('content', ''))
            if content_length > 200:
                score += 0.1
            elif content_length > 100:
                score += 0.05
            
            return min(score, 1.0)
            
        except Exception as e:
            logging.error(f"❌ Error calculating importance score: {e}")
            return 0.0
    
    def _calculate_recency_score(self, memory: Dict[str, Any]) -> float:
        """
        Calculate recency score for a memory entry
        
        Args:
            memory: Memory entry to score
            
        Returns:
            Recency score (0-1)
        """
        try:
            created_at_str = memory.get('metadata', {}).get('created_at')
            if not created_at_str:
                return 0.0
            
            try:
                created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
            except:
                created_at = datetime.now(timezone.utc)
            
            # Calculate age in hours
            age_hours = (datetime.now(timezone.utc) - created_at).total_seconds() / 3600
            
            # Recency scoring (newer is better)
            if age_hours <= 1:
                return 1.0
            elif age_hours <= 24:
                return 0.8
            elif age_hours <= 168:  # 1 week
                return 0.6
            elif age_hours <= 720:  # 1 month
                return 0.4
            else:
                return 0.2
                
        except Exception as e:
            logging.error(f"❌ Error calculating recency score: {e}")
            return 0.0
    
    def _generate_context_summary(self, context: List[Dict[str, Any]]) -> str:
        """
        Generate a summary of the retrieved context
        
        Args:
            context: List of context entries
            
        Returns:
            Context summary string
        """
        try:
            if not context:
                return "No relevant context found"
            
            summary_parts = []
            
            # Count different types of memories
            conversation_count = len([c for c in context if c.get('metadata', {}).get('category') == 'conversation'])
            project_count = len([c for c in context if c.get('metadata', {}).get('category') == 'project'])
            client_count = len(set(c.get('metadata', {}).get('client_id') for c in context if c.get('metadata', {}).get('client_id')))
            
            if conversation_count > 0:
                summary_parts.append(f"{conversation_count} conversation(s)")
            if project_count > 0:
                summary_parts.append(f"{project_count} project(s)")
            if client_count > 0:
                summary_parts.append(f"{client_count} client(s)")
            
            # Add average similarity
            if context:
                avg_similarity = sum(c.get('similarity', 0) for c in context) / len(context)
                summary_parts.append(f"avg similarity {avg_similarity:.2f}")
            
            return " | ".join(summary_parts)
            
        except Exception as e:
            logging.error(f"❌ Error generating context summary: {e}")
            return "Context summary unavailable"
    
    def analyze_context_usage(self, context_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze context usage for optimization
        
        Args:
            context_data: Context data from build_context_for_conversation
            
        Returns:
            Analysis of context usage and effectiveness
        """
        try:
            context = context_data.get('context', [])
            
            analysis = {
                'total_memories': len(context),
                'total_tokens': context_data.get('total_tokens', 0),
                'retrieval_sources': {},
                'content_types': {},
                'lead_categories': {},
                'average_similarity': 0.0,
                'context_efficiency': 'good'
            }
            
            if not context:
                return analysis
            
            # Analyze retrieval sources
            for memory in context:
                source = memory.get('retrieval_reason', 'unknown')
                analysis['retrieval_sources'][source] = analysis['retrieval_sources'].get(source, 0) + 1
                
                # Analyze content types
                content_type = memory.get('metadata', {}).get('content_type', 'text')
                analysis['content_types'][content_type] = analysis['content_types'].get(content_type, 0) + 1
                
                # Analyze lead categories
                lead_category = memory.get('metadata', {}).get('lead_category', 'unspecified')
                analysis['lead_categories'][lead_category] = analysis['lead_categories'].get(lead_category, 0) + 1
            
            # Calculate average similarity
            similarities = [m.get('similarity', 0) for m in context]
            analysis['average_similarity'] = sum(similarities) / len(similarities) if similarities else 0
            
            # Determine context efficiency
            if analysis['total_tokens'] > self.max_context_tokens * 0.9:
                analysis['context_efficiency'] = 'high_usage'
            elif analysis['total_tokens'] < self.max_context_tokens * 0.3:
                analysis['context_efficiency'] = 'low_usage'
            
            return analysis
            
        except Exception as e:
            logging.error(f"❌ Error analyzing context usage: {e}")
            return {'error': str(e)}


class ContextBuilder:
    """
    Helper class for building token-safe context
    """
    
    def __init__(self, max_tokens: int = 4000):
        self.max_tokens = max_tokens
        self.used_tokens = 0
        self.approximate_tokens_per_word = 1.3  # Rough estimate
    
    def build_context(self, memories: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Build context within token limits
        
        Args:
            memories: Ranked list of memories
            
        Returns:
            Token-safe context list
        """
        context = []
        
        for memory in memories:
            # Estimate tokens for this memory
            content = memory.get('content', '')
            metadata_text = self._format_metadata(memory)
            total_text = content + metadata_text
            
            estimated_tokens = len(total_text.split()) * self.approximate_tokens_per_word
            
            # Check if we can add this memory
            if self.used_tokens + estimated_tokens <= self.max_tokens:
                # Add token count to memory
                memory['estimated_tokens'] = estimated_tokens
                memory['context_position'] = len(context)
                
                context.append(memory)
                self.used_tokens += estimated_tokens
            else:
                # Can't add more memories
                break
        
        return context
    
    def _format_metadata(self, memory: Dict[str, Any]) -> str:
        """Format metadata for context inclusion"""
        metadata = memory.get('metadata', {})
        
        parts = []
        if metadata.get('client_id'):
            parts.append(f"Client: {metadata['client_id']}")
        if metadata.get('content_type'):
            parts.append(f"Type: {metadata['content_type']}")
        if metadata.get('lead_category'):
            parts.append(f"Category: {metadata['lead_category']}")
        if metadata.get('tags'):
            parts.append(f"Tags: {', '.join(metadata['tags'])}")
        
        return f" [{', '.join(parts)}]" if parts else ""


# Global context service instance
context_service = ContextService()

def get_context_service() -> ContextService:
    """Get the global context service instance"""
    return context_service
