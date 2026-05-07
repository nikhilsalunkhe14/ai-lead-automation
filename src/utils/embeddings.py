"""
Embeddings Utility - Professional text embedding generation and management
"""

import logging
import numpy as np
from typing import List, Dict, Any, Optional
from sentence_transformers import SentenceTransformer
from src.config.settings import settings

class EmbeddingService:
    """
    Professional embedding service for text vectorization
    Uses sentence-transformers for high-quality embeddings
    """
    
    def __init__(self):
        self.model = None
        self.model_name = settings.EMBEDDINGS_CONFIG.MODEL_NAME
        self.embedding_dimension = settings.EMBEDDINGS_CONFIG.DIMENSION
        self._initialize_model()
    
    def _initialize_model(self):
        """Initialize the sentence transformer model"""
        try:
            logging.info(f"🧠 Loading embedding model: {self.model_name}")
            self.model = SentenceTransformer(self.model_name)
            logging.info(f"✅ Embedding model loaded successfully (Dimension: {self.embedding_dimension})")
        except Exception as e:
            logging.error(f"❌ Failed to load embedding model: {e}")
            raise RuntimeError(f"Embedding model initialization failed: {e}")
    
    def generate_embedding(self, text: str) -> np.ndarray:
        """
        Generate embedding for a single text
        
        Args:
            text: Input text to embed
            
        Returns:
            numpy.ndarray: Text embedding vector
        """
        try:
            if not text or not text.strip():
                # Return zero vector for empty text
                return np.zeros(self.embedding_dimension)
            
            # Clean and prepare text
            cleaned_text = self._clean_text(text)
            
            # Generate embedding
            embedding = self.model.encode(
                cleaned_text,
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=False
            )
            
            return embedding
            
        except Exception as e:
            logging.error(f"❌ Error generating embedding: {e}")
            # Return zero vector as fallback
            return np.zeros(self.embedding_dimension)
    
    def generate_embeddings_batch(self, texts: List[str]) -> np.ndarray:
        """
        Generate embeddings for multiple texts efficiently
        
        Args:
            texts: List of texts to embed
            
        Returns:
            numpy.ndarray: Matrix of embeddings
        """
        try:
            if not texts:
                return np.array([])
            
            # Clean texts
            cleaned_texts = [self._clean_text(text) for text in texts]
            
            # Generate embeddings in batch for efficiency
            embeddings = self.model.encode(
                cleaned_texts,
                convert_to_numpy=True,
                normalize_embeddings=True,
                batch_size=32,
                show_progress_bar=False
            )
            
            return embeddings
            
        except Exception as e:
            logging.error(f"❌ Error generating batch embeddings: {e}")
            # Return zero vectors as fallback
            return np.zeros((len(texts), self.embedding_dimension))
    
    def calculate_similarity(self, embedding1: np.ndarray, embedding2: np.ndarray) -> float:
        """
        Calculate cosine similarity between two embeddings
        
        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector
            
        Returns:
            float: Cosine similarity score (0-1)
        """
        try:
            # Ensure embeddings are numpy arrays
            if not isinstance(embedding1, np.ndarray):
                embedding1 = np.array(embedding1)
            if not isinstance(embedding2, np.ndarray):
                embedding2 = np.array(embedding2)
            
            # Calculate cosine similarity
            similarity = np.dot(embedding1, embedding2)
            return float(similarity)
            
        except Exception as e:
            logging.error(f"❌ Error calculating similarity: {e}")
            return 0.0
    
    def find_most_similar(self, query_embedding: np.ndarray, 
                         candidate_embeddings: np.ndarray, 
                         top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Find most similar embeddings to query
        
        Args:
            query_embedding: Query embedding vector
            candidate_embeddings: Matrix of candidate embeddings
            top_k: Number of top results to return
            
        Returns:
            List of dictionaries with similarity scores and indices
        """
        try:
            if len(candidate_embeddings) == 0:
                return []
            
            # Calculate similarities
            similarities = np.dot(candidate_embeddings, query_embedding)
            
            # Get top k indices
            top_indices = np.argsort(similarities)[::-1][:top_k]
            
            # Create results
            results = []
            for idx in top_indices:
                results.append({
                    'index': int(idx),
                    'similarity': float(similarities[idx]),
                    'embedding': candidate_embeddings[idx]
                })
            
            return results
            
        except Exception as e:
            logging.error(f"❌ Error finding similar embeddings: {e}")
            return []
    
    def _clean_text(self, text: str) -> str:
        """
        Clean and prepare text for embedding
        
        Args:
            text: Raw text
            
        Returns:
            str: Cleaned text
        """
        if not text:
            return ""
        
        # Basic text cleaning
        cleaned = text.strip()
        
        # Remove excessive whitespace
        cleaned = ' '.join(cleaned.split())
        
        # Truncate if too long (sentence-transformers can handle long texts)
        max_length = 512
        if len(cleaned) > max_length:
            cleaned = cleaned[:max_length] + "..."
        
        return cleaned
    
    def get_embedding_dimension(self) -> int:
        """Get the dimension of embeddings"""
        return self.embedding_dimension
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the embedding model"""
        return {
            'model_name': self.model_name,
            'dimension': self.embedding_dimension,
            'is_loaded': self.model is not None,
            'max_sequence_length': 512  # Typical for sentence-transformers
        }
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check on embedding service"""
        try:
            # Test embedding generation
            test_text = "This is a test for embedding generation."
            test_embedding = self.generate_embedding(test_text)
            
            # Check embedding properties
            is_valid = (
                isinstance(test_embedding, np.ndarray) and
                test_embedding.shape == (self.embedding_dimension,) and
                not np.any(np.isnan(test_embedding))
            )
            
            return {
                'status': 'healthy' if is_valid else 'unhealthy',
                'model_loaded': self.model is not None,
                'embedding_dimension': self.embedding_dimension,
                'test_embedding_valid': is_valid,
                'test_embedding_shape': test_embedding.shape if is_valid else None
            }
            
        except Exception as e:
            logging.error(f"❌ Embedding service health check failed: {e}")
            return {
                'status': 'unhealthy',
                'error': str(e),
                'model_loaded': self.model is not None
            }

# Global embedding service instance
embedding_service = EmbeddingService()

def get_embedding_service() -> EmbeddingService:
    """Get the global embedding service instance"""
    return embedding_service
