"""
Vector Service - Professional vector database management with ChromaDB
"""

import logging
import os
from typing import List, Dict, Any, Optional, Tuple
import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions
import numpy as np
from src.models.memory import MemoryEntry
from src.utils.embeddings import get_embedding_service
from src.config.settings import settings

class VectorService:
    """
    Professional vector database service using ChromaDB
    Manages semantic search and similarity operations
    """
    
    def __init__(self):
        self.client = None
        self.collections = {}
        self.embedding_service = get_embedding_service()
        self.embedding_dimension = self.embedding_service.get_embedding_dimension()
        self._initialize_client()
        self._create_collections()
    
    def _initialize_client(self):
        """Initialize ChromaDB client"""
        try:
            # Configure ChromaDB settings
            chroma_settings = Settings(
                chroma_db_impl="duckdb+parquet",
                persist_directory=settings.MEMORY_CONFIG.VECTOR_DB_PATH,
                anonymized_telemetry=False
            )
            
            # Create client
            self.client = chromadb.PersistentClient(
                path=settings.MEMORY_CONFIG.VECTOR_DB_PATH,
                settings=chroma_settings
            )
            
            logging.info(f"✅ ChromaDB client initialized at {settings.MEMORY_CONFIG.VECTOR_DB_PATH}")
            
        except Exception as e:
            logging.error(f"❌ Failed to initialize ChromaDB client: {e}")
            raise RuntimeError(f"Vector database initialization failed: {e}")
    
    def _create_collections(self):
        """Create memory collections"""
        try:
            # Define collections to create
            collection_configs = [
                {
                    'name': 'conversation_memory',
                    'metadata': {'description': 'Conversation messages and context'}
                },
                {
                    'name': 'client_memory',
                    'metadata': {'description': 'Client profiles and preferences'}
                },
                {
                    'name': 'project_memory',
                    'metadata': {'description': 'Project requirements and specifications'}
                }
            ]
            
            # Create collections
            for config in collection_configs:
                try:
                    collection = self.client.get_collection(name=config['name'])
                    logging.info(f"📚 Collection '{config['name']}' already exists")
                except Exception:
                    collection = self.client.create_collection(
                        name=config['name'],
                        metadata=config['metadata'],
                        embedding_function=None  # We'll use our own embeddings
                    )
                    logging.info(f"📚 Created collection '{config['name']}'")
                
                self.collections[config['name']] = collection
            
            logging.info(f"✅ {len(self.collections)} collections initialized")
            
        except Exception as e:
            logging.error(f"❌ Failed to create collections: {e}")
            raise
    
    def store_memory_entry(self, memory_entry: MemoryEntry) -> bool:
        """
        Store a memory entry in the appropriate collection
        
        Args:
            memory_entry: MemoryEntry to store
            
        Returns:
            bool: Success status
        """
        try:
            # Generate embedding if not present
            if memory_entry.embedding is None:
                memory_entry.embedding = self.embedding_service.generate_embedding(memory_entry.content)
            
            # Determine collection
            collection_name = self._get_collection_name(memory_entry.category)
            if collection_name not in self.collections:
                logging.error(f"❌ Collection '{collection_name}' not found")
                return False
            
            collection = self.collections[collection_name]
            
            # Prepare data for ChromaDB
            embedding_list = memory_entry.embedding.tolist()
            
            # Store in ChromaDB
            collection.add(
                ids=[memory_entry.id],
                embeddings=[embedding_list],
                metadatas=[self._prepare_metadata(memory_entry)],
                documents=[memory_entry.content]
            )
            
            logging.debug(f"💾 Stored memory entry {memory_entry.id} in {collection_name}")
            return True
            
        except Exception as e:
            logging.error(f"❌ Failed to store memory entry: {e}")
            return False
    
    def search_similar(self, 
                      query: str, 
                      collection_name: str, 
                      limit: int = 10,
                      filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Search for similar entries using semantic search
        
        Args:
            query: Search query
            collection_name: Collection to search in
            limit: Maximum number of results
            filters: Optional metadata filters
            
        Returns:
            List of similar entries with similarity scores
        """
        try:
            if collection_name not in self.collections:
                logging.error(f"❌ Collection '{collection_name}' not found")
                return []
            
            collection = self.collections[collection_name]
            
            # Generate query embedding
            query_embedding = self.embedding_service.generate_embedding(query)
            
            # Prepare where clause for filters
            where_clause = self._prepare_where_clause(filters) if filters else None
            
            # Search in ChromaDB
            results = collection.query(
                query_embeddings=[query_embedding.tolist()],
                n_results=limit,
                where=where_clause,
                include=['metadatas', 'documents', 'distances']
            )
            
            # Process results
            search_results = []
            if results['ids'] and results['ids'][0]:
                for i, entry_id in enumerate(results['ids'][0]):
                    similarity_score = 1 - results['distances'][0][i]  # Convert distance to similarity
                    
                    search_results.append({
                        'id': entry_id,
                        'content': results['documents'][0][i],
                        'metadata': results['metadatas'][0][i],
                        'similarity': similarity_score,
                        'collection': collection_name
                    })
            
            logging.debug(f"🔍 Found {len(search_results)} similar entries in {collection_name}")
            return search_results
            
        except Exception as e:
            logging.error(f"❌ Failed to search similar entries: {e}")
            return []
    
    def get_client_context(self, client_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Get all memory entries related to a client
        
        Args:
            client_id: Client identifier
            limit: Maximum number of entries per collection
            
        Returns:
            List of client-related memory entries
        """
        try:
            client_context = []
            
            # Search across all collections for client-specific entries
            for collection_name in self.collections.keys():
                filters = {'client_id': client_id}
                results = self.search_similar(
                    query="",  # Empty query to get all matching entries
                    collection_name=collection_name,
                    limit=limit,
                    filters=filters
                )
                client_context.extend(results)
            
            # Sort by similarity (relevance) and timestamp
            client_context.sort(key=lambda x: (
                -x['similarity'],  # Higher similarity first
                x['metadata'].get('created_at', '')  # More recent first
            ))
            
            logging.debug(f"👤 Retrieved {len(client_context)} context entries for client {client_id}")
            return client_context
            
        except Exception as e:
            logging.error(f"❌ Failed to get client context: {e}")
            return []
    
    def get_related_projects(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Get projects related to a query
        
        Args:
            query: Search query
            limit: Maximum number of results
            
        Returns:
            List of related project entries
        """
        try:
            # Search in project memory collection
            results = self.search_similar(
                query=query,
                collection_name='project_memory',
                limit=limit
            )
            
            # Filter for project-specific entries
            project_results = [
                result for result in results
                if result['metadata'].get('category') == 'project'
            ]
            
            logging.debug(f"📋 Found {len(project_results)} related projects")
            return project_results
            
        except Exception as e:
            logging.error(f"❌ Failed to get related projects: {e}")
            return []
    
    def get_conversation_history(self, conversation_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get conversation history by conversation ID
        
        Args:
            conversation_id: Conversation identifier
            limit: Maximum number of entries
            
        Returns:
            List of conversation entries in chronological order
        """
        try:
            # Search in conversation memory collection
            filters = {'conversation_id': conversation_id}
            results = self.search_similar(
                query="",
                collection_name='conversation_memory',
                limit=limit,
                filters=filters
            )
            
            # Sort by timestamp
            results.sort(key=lambda x: x['metadata'].get('created_at', ''))
            
            logging.debug(f"💬 Retrieved {len(results)} conversation entries")
            return results
            
        except Exception as e:
            logging.error(f"❌ Failed to get conversation history: {e}")
            return []
    
    def delete_memory_entry(self, entry_id: str, collection_name: str) -> bool:
        """
        Delete a memory entry
        
        Args:
            entry_id: Entry identifier
            collection_name: Collection name
            
        Returns:
            bool: Success status
        """
        try:
            if collection_name not in self.collections:
                logging.error(f"❌ Collection '{collection_name}' not found")
                return False
            
            collection = self.collections[collection_name]
            collection.delete(ids=[entry_id])
            
            logging.debug(f"🗑️ Deleted memory entry {entry_id} from {collection_name}")
            return True
            
        except Exception as e:
            logging.error(f"❌ Failed to delete memory entry: {e}")
            return False
    
    def update_memory_entry(self, memory_entry: MemoryEntry) -> bool:
        """
        Update a memory entry
        
        Args:
            memory_entry: Updated memory entry
            
        Returns:
            bool: Success status
        """
        try:
            # Delete existing entry
            collection_name = self._get_collection_name(memory_entry.category)
            self.delete_memory_entry(memory_entry.id, collection_name)
            
            # Store updated entry
            return self.store_memory_entry(memory_entry)
            
        except Exception as e:
            logging.error(f"❌ Failed to update memory entry: {e}")
            return False
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """
        Get statistics for all collections
        
        Returns:
            Dictionary with collection statistics
        """
        try:
            stats = {}
            
            for collection_name, collection in self.collections.items():
                try:
                    count = collection.count()
                    stats[collection_name] = {
                        'count': count,
                        'status': 'active'
                    }
                except Exception as e:
                    stats[collection_name] = {
                        'count': 0,
                        'status': 'error',
                        'error': str(e)
                    }
            
            return stats
            
        except Exception as e:
            logging.error(f"❌ Failed to get collection stats: {e}")
            return {}
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on vector service
        
        Returns:
            Health check results
        """
        try:
            # Check client connection
            client_status = self.client is not None
            
            # Check collections
            collections_status = len(self.collections) > 0
            
            # Check embedding service
            embedding_health = self.embedding_service.health_check()
            
            # Test basic operation
            test_entry = MemoryEntry(
                content="Health check test entry",
                category="general"
            )
            
            # Test storage and retrieval
            storage_test = self.store_memory_entry(test_entry)
            retrieval_test = False
            
            if storage_test:
                search_results = self.search_similar(
                    query="health check test",
                    collection_name="conversation_memory",
                    limit=1
                )
                retrieval_test = len(search_results) > 0
                
                # Clean up test entry
                self.delete_memory_entry(test_entry.id, "conversation_memory")
            
            overall_status = (
                client_status and 
                collections_status and 
                embedding_health['status'] == 'healthy' and
                storage_test and 
                retrieval_test
            )
            
            return {
                'status': 'healthy' if overall_status else 'unhealthy',
                'client_connected': client_status,
                'collections_loaded': collections_status,
                'embedding_service': embedding_health,
                'storage_test': storage_test,
                'retrieval_test': retrieval_test,
                'collection_stats': self.get_collection_stats()
            }
            
        except Exception as e:
            logging.error(f"❌ Vector service health check failed: {e}")
            return {
                'status': 'unhealthy',
                'error': str(e)
            }
    
    def _get_collection_name(self, category: str) -> str:
        """Map memory category to collection name"""
        collection_mapping = {
            'conversation': 'conversation_memory',
            'client': 'client_memory',
            'project': 'project_memory',
            'summary': 'conversation_memory',  # Summaries stored with conversations
            'general': 'conversation_memory'   # General entries in conversation memory
        }
        return collection_mapping.get(category, 'conversation_memory')
    
    def _prepare_metadata(self, memory_entry: MemoryEntry) -> Dict[str, Any]:
        """Prepare metadata for ChromaDB storage"""
        metadata = {
            'client_id': memory_entry.client_id,
            'lead_id': memory_entry.lead_id,
            'conversation_id': memory_entry.conversation_id,
            'project_id': memory_entry.project_id,
            'category': memory_entry.category,
            'content_type': memory_entry.content_type,
            'tags': memory_entry.tags,
            'lead_category': memory_entry.lead_category,
            'created_at': memory_entry.created_at.isoformat(),
            'updated_at': memory_entry.updated_at.isoformat()
        }
        
        # Add additional metadata
        metadata.update(memory_entry.metadata)
        
        # Remove None values
        return {k: v for k, v in metadata.items() if v is not None}
    
    def _prepare_where_clause(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare where clause for ChromaDB filtering"""
        if not filters:
            return {}
        
        # ChromaDB where clause format
        where_clause = {}
        
        for key, value in filters.items():
            if isinstance(value, str):
                where_clause[key] = {"$eq": value}
            elif isinstance(value, list):
                where_clause[key] = {"$in": value}
            else:
                where_clause[key] = {"$eq": value}
        
        return where_clause

# Global vector service instance
vector_service = VectorService()

def get_vector_service() -> VectorService:
    """Get the global vector service instance"""
    return vector_service
