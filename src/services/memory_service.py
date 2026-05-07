"""
Memory Service - Professional AI memory management and operations
"""

import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from src.models.memory import MemoryEntry, ConversationMemory, ClientMemory, ProjectMemory
from src.services.vector_service import get_vector_service
from src.utils.embeddings import get_embedding_service
from src.config.settings import settings

class MemoryService:
    """
    Professional memory service for AI system
    Manages storage, retrieval, and operations on memory data
    """
    
    def __init__(self):
        self.vector_service = get_vector_service()
        self.embedding_service = get_embedding_service()
        self._initialized = False
        self._initialize_service()
    
    def _initialize_service(self):
        """Initialize memory service"""
        try:
            # Perform health check
            health = self.vector_service.health_check()
            if health['status'] == 'healthy':
                self._initialized = True
                logging.info("🧠 Memory service initialized successfully")
            else:
                logging.error(f"❌ Memory service initialization failed: {health}")
                self._initialized = False
                
        except Exception as e:
            logging.error(f"❌ Memory service initialization error: {e}")
            self._initialized = False
    
    def is_initialized(self) -> bool:
        """Check if memory service is properly initialized"""
        return self._initialized
    
    def store_memory(self, 
                    content: str,
                    category: str = "general",
                    content_type: str = "text",
                    client_id: Optional[str] = None,
                    lead_id: Optional[str] = None,
                    conversation_id: Optional[str] = None,
                    project_id: Optional[str] = None,
                    tags: Optional[List[str]] = None,
                    lead_category: str = "unspecified",
                    metadata: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """
        Store a memory entry with embedding
        
        Args:
            content: Text content to store
            category: Memory category (conversation, client, project, general)
            content_type: Type of content (text, summary, requirement, message, response)
            client_id: Optional client identifier
            lead_id: Optional lead identifier
            conversation_id: Optional conversation identifier
            project_id: Optional project identifier
            tags: Optional list of tags
            lead_category: Lead category (hot, warm, cool, cold)
            metadata: Additional metadata
            
        Returns:
            str: Memory entry ID if successful, None otherwise
        """
        try:
            if not self._initialized:
                logging.error("❌ Memory service not initialized")
                return None
            
            # Create memory entry
            memory_entry = MemoryEntry(
                content=content,
                category=category,
                content_type=content_type,
                client_id=client_id,
                lead_id=lead_id,
                conversation_id=conversation_id,
                project_id=project_id,
                tags=tags or [],
                lead_category=lead_category,
                metadata=metadata or {}
            )
            
            # Validate entry
            validation_errors = memory_entry.validate()
            if validation_errors:
                logging.error(f"❌ Memory entry validation failed: {validation_errors}")
                return None
            
            # Store in vector database
            success = self.vector_service.store_memory_entry(memory_entry)
            
            if success:
                logging.debug(f"💾 Stored memory entry: {memory_entry.id}")
                return memory_entry.id
            else:
                logging.error(f"❌ Failed to store memory entry")
                return None
                
        except Exception as e:
            logging.error(f"❌ Error storing memory: {e}")
            return None
    
    def search_memory(self, 
                     query: str,
                     category: Optional[str] = None,
                     limit: int = 10,
                     filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Search memory using semantic similarity
        
        Args:
            query: Search query
            category: Optional category to search in
            limit: Maximum number of results
            filters: Optional metadata filters
            
        Returns:
            List of search results with similarity scores
        """
        try:
            if not self._initialized:
                logging.error("❌ Memory service not initialized")
                return []
            
            # Determine collection to search
            collection_name = self._get_collection_name(category) if category else "conversation_memory"
            
            # Perform semantic search
            results = self.vector_service.search_similar(
                query=query,
                collection_name=collection_name,
                limit=limit,
                filters=filters
            )
            
            # Post-process results
            processed_results = []
            for result in results:
                processed_result = {
                    'id': result['id'],
                    'content': result['content'],
                    'similarity': result['similarity'],
                    'metadata': result['metadata'],
                    'collection': result['collection']
                }
                processed_results.append(processed_result)
            
            logging.debug(f"🔍 Found {len(processed_results)} memory results for query: {query[:50]}...")
            return processed_results
            
        except Exception as e:
            logging.error(f"❌ Error searching memory: {e}")
            return []
    
    def retrieve_client_context(self, 
                              client_id: str, 
                              limit: int = 20,
                              include_conversations: bool = True,
                              include_projects: bool = True) -> Dict[str, Any]:
        """
        Retrieve comprehensive client context
        
        Args:
            client_id: Client identifier
            limit: Maximum number of entries per type
            include_conversations: Whether to include conversation history
            include_projects: Whether to include project information
            
        Returns:
            Dictionary with client context
        """
        try:
            if not self._initialized:
                logging.error("❌ Memory service not initialized")
                return {}
            
            context = {
                'client_id': client_id,
                'conversations': [],
                'projects': [],
                'summary': '',
                'total_entries': 0
            }
            
            # Get conversation history
            if include_conversations:
                conversations = self.vector_service.get_client_context(client_id, limit)
                context['conversations'] = conversations
                context['total_entries'] += len(conversations)
            
            # Get project information
            if include_projects:
                projects = self.search_memory(
                    query="",
                    category="project",
                    limit=limit,
                    filters={'client_id': client_id}
                )
                context['projects'] = projects
                context['total_entries'] += len(projects)
            
            # Generate context summary
            context['summary'] = self._generate_context_summary(context)
            
            logging.debug(f"👤 Retrieved context for client {client_id}: {context['total_entries']} entries")
            return context
            
        except Exception as e:
            logging.error(f"❌ Error retrieving client context: {e}")
            return {}
    
    def get_related_projects(self, 
                           query: str,
                           client_id: Optional[str] = None,
                           limit: int = 5) -> List[Dict[str, Any]]:
        """
        Get projects related to a query
        
        Args:
            query: Search query
            client_id: Optional client filter
            limit: Maximum number of results
            
        Returns:
            List of related projects
        """
        try:
            if not self._initialized:
                logging.error("❌ Memory service not initialized")
                return []
            
            # Prepare filters
            filters = {}
            if client_id:
                filters['client_id'] = client_id
            
            # Search for related projects
            projects = self.search_memory(
                query=query,
                category="project",
                limit=limit,
                filters=filters
            )
            
            logging.debug(f"📋 Found {len(projects)} related projects for query: {query[:50]}...")
            return projects
            
        except Exception as e:
            logging.error(f"❌ Error getting related projects: {e}")
            return []
    
    def store_conversation_thread(self, 
                                messages: List[Dict[str, Any]],
                                conversation_id: str,
                                client_id: Optional[str] = None,
                                lead_id: Optional[str] = None) -> bool:
        """
        Store a conversation thread with multiple messages
        
        Args:
            messages: List of message dictionaries
            conversation_id: Conversation identifier
            client_id: Optional client identifier
            lead_id: Optional lead identifier
            
        Returns:
            bool: Success status
        """
        try:
            if not self._initialized:
                logging.error("❌ Memory service not initialized")
                return False
            
            stored_count = 0
            
            for message in messages:
                # Extract message data
                content = message.get('content', '')
                content_type = message.get('type', 'message')
                role = message.get('role', 'user')  # user, assistant, system
                
                # Store each message
                memory_id = self.store_memory(
                    content=content,
                    category="conversation",
                    content_type=content_type,
                    client_id=client_id,
                    lead_id=lead_id,
                    conversation_id=conversation_id,
                    metadata={'role': role, 'message_index': message.get('index', 0)}
                )
                
                if memory_id:
                    stored_count += 1
            
            logging.debug(f"💬 Stored conversation thread: {stored_count}/{len(messages)} messages")
            return stored_count > 0
            
        except Exception as e:
            logging.error(f"❌ Error storing conversation thread: {e}")
            return False
    
    def get_conversation_history(self, 
                               conversation_id: str,
                               limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get conversation history by ID
        
        Args:
            conversation_id: Conversation identifier
            limit: Maximum number of messages
            
        Returns:
            List of conversation messages
        """
        try:
            if not self._initialized:
                logging.error("❌ Memory service not initialized")
                return []
            
            # Get conversation entries
            entries = self.vector_service.get_conversation_history(conversation_id, limit)
            
            # Sort by message index and timestamp
            entries.sort(key=lambda x: (
                x['metadata'].get('message_index', 0),
                x['metadata'].get('created_at', '')
            ))
            
            logging.debug(f"💬 Retrieved conversation history: {len(entries)} messages")
            return entries
            
        except Exception as e:
            logging.error(f"❌ Error getting conversation history: {e}")
            return []
    
    def update_memory_entry(self, 
                           memory_id: str,
                           new_content: Optional[str] = None,
                           new_tags: Optional[List[str]] = None,
                           new_metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Update an existing memory entry
        
        Args:
            memory_id: Memory entry ID
            new_content: Optional new content
            new_tags: Optional new tags
            new_metadata: Optional new metadata
            
        Returns:
            bool: Success status
        """
        try:
            if not self._initialized:
                logging.error("❌ Memory service not initialized")
                return False
            
            # Find the memory entry (this would require additional implementation)
            # For now, this is a placeholder for the update functionality
            logging.debug(f"📝 Update memory entry: {memory_id}")
            
            # TODO: Implement actual update logic
            # This would involve:
            # 1. Finding the entry in the vector database
            # 2. Updating the content and/or metadata
            # 3. Regenerating embeddings if content changed
            # 4. Storing the updated entry
            
            return True
            
        except Exception as e:
            logging.error(f"❌ Error updating memory entry: {e}")
            return False
    
    def delete_memory_entry(self, memory_id: str, category: str) -> bool:
        """
        Delete a memory entry
        
        Args:
            memory_id: Memory entry ID
            category: Memory category
            
        Returns:
            bool: Success status
        """
        try:
            if not self._initialized:
                logging.error("❌ Memory service not initialized")
                return False
            
            # Get collection name
            collection_name = self._get_collection_name(category)
            
            # Delete from vector database
            success = self.vector_service.delete_memory_entry(memory_id, collection_name)
            
            if success:
                logging.debug(f"🗑️ Deleted memory entry: {memory_id}")
            
            return success
            
        except Exception as e:
            logging.error(f"❌ Error deleting memory entry: {e}")
            return False
    
    def get_memory_stats(self) -> Dict[str, Any]:
        """
        Get memory service statistics
        
        Returns:
            Dictionary with memory statistics
        """
        try:
            if not self._initialized:
                return {
                    'status': 'not_initialized',
                    'collections': {}
                }
            
            # Get collection statistics
            collection_stats = self.vector_service.get_collection_stats()
            
            # Get embedding service info
            embedding_info = self.embedding_service.get_model_info()
            
            # Health check
            health = self.vector_service.health_check()
            
            return {
                'status': 'active',
                'initialized': self._initialized,
                'collections': collection_stats,
                'embedding_model': embedding_info,
                'health': health
            }
            
        except Exception as e:
            logging.error(f"❌ Error getting memory stats: {e}")
            return {
                'status': 'error',
                'error': str(e)
            }
    
    def generate_sample_data(self) -> bool:
        """
        Generate sample data for testing purposes
        
        Returns:
            bool: Success status
        """
        try:
            if not self._initialized:
                logging.error("❌ Memory service not initialized")
                return False
            
            # Sample conversations
            sample_conversations = [
                {
                    'content': 'I need a website for my small business with e-commerce functionality',
                    'category': 'conversation',
                    'content_type': 'message',
                    'client_id': 'client_001',
                    'lead_category': 'hot',
                    'tags': ['website', 'ecommerce', 'small business']
                },
                {
                    'content': 'We require a mobile app development for iOS and Android platforms',
                    'category': 'conversation',
                    'content_type': 'message',
                    'client_id': 'client_002',
                    'lead_category': 'warm',
                    'tags': ['mobile app', 'iOS', 'Android']
                },
                {
                    'content': 'Looking for digital marketing services including SEO and social media management',
                    'category': 'conversation',
                    'content_type': 'message',
                    'client_id': 'client_003',
                    'lead_category': 'medium',
                    'tags': ['digital marketing', 'SEO', 'social media']
                }
            ]
            
            # Sample projects
            sample_projects = [
                {
                    'content': 'E-commerce website project with payment gateway integration and inventory management',
                    'category': 'project',
                    'content_type': 'requirement',
                    'client_id': 'client_001',
                    'project_id': 'proj_001',
                    'tags': ['ecommerce', 'payment gateway', 'inventory']
                },
                {
                    'content': 'Mobile application with real-time chat and push notifications',
                    'category': 'project',
                    'content_type': 'requirement',
                    'client_id': 'client_002',
                    'project_id': 'proj_002',
                    'tags': ['mobile app', 'real-time chat', 'push notifications']
                }
            ]
            
            # Store sample data
            stored_count = 0
            
            for item in sample_conversations + sample_projects:
                memory_id = self.store_memory(**item)
                if memory_id:
                    stored_count += 1
            
            logging.info(f"📊 Generated {stored_count} sample memory entries")
            return stored_count > 0
            
        except Exception as e:
            logging.error(f"❌ Error generating sample data: {e}")
            return False
    
    def _get_collection_name(self, category: str) -> str:
        """Map memory category to collection name"""
        collection_mapping = {
            'conversation': 'conversation_memory',
            'client': 'client_memory',
            'project': 'project_memory',
            'summary': 'conversation_memory',
            'general': 'conversation_memory'
        }
        return collection_mapping.get(category, 'conversation_memory')
    
    def _generate_context_summary(self, context: Dict[str, Any]) -> str:
        """Generate a summary of client context"""
        try:
            summary_parts = []
            
            # Conversation summary
            if context.get('conversations'):
                conv_count = len(context['conversations'])
                summary_parts.append(f"{conv_count} conversation entries")
                
                # Get most recent conversation
                recent_convs = context['conversations'][:3]
                for conv in recent_convs:
                    content_preview = conv['content'][:50] + "..." if len(conv['content']) > 50 else conv['content']
                    summary_parts.append(f"Recent: {content_preview}")
            
            # Project summary
            if context.get('projects'):
                proj_count = len(context['projects'])
                summary_parts.append(f"{proj_count} related projects")
            
            return " | ".join(summary_parts) if summary_parts else "No context available"
            
        except Exception as e:
            logging.error(f"❌ Error generating context summary: {e}")
            return "Context summary unavailable"

# Global memory service instance
memory_service = MemoryService()

def get_memory_service() -> MemoryService:
    """Get the global memory service instance"""
    return memory_service
