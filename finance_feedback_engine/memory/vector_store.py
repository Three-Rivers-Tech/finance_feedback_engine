"""
Vector memory store for semantic search capabilities.

Uses Ollama embeddings and cosine similarity for intelligent memory retrieval.
"""

import pickle
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger(__name__)


class VectorMemory:
    """
    Vector-based memory store using embeddings for semantic search.

    Features:
    - Ollama embeddings for text vectorization
    - Cosine similarity for finding similar memories
    - Persistent storage using pickle
    - Graceful error handling for offline Ollama
    """

    def __init__(self, storage_path: Optional[str] = None):
        """
        Initialize vector memory store.

        Args:
            storage_path: Path to store vectors (default: data/memory/vectors.pkl)
        """
        self.storage_path = Path(storage_path or 'data/memory/vectors.pkl')
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

        # Storage for vectors and metadata
        self.vectors: List[np.ndarray] = []
        self.metadata: Dict[str, Dict[str, Any]] = {}
        self.ids: List[str] = []

        # Load existing index if available
        self._load_index()

        logger.info(f"VectorMemory initialized with {len(self.vectors)} stored vectors")

    def get_embedding(self, text: str) -> Optional[np.ndarray]:
        """
        Generate embedding for text using Ollama.

        Args:
            text: Text to embed

        Returns:
            Numpy array embedding or None if failed
        """
        try:
            import ollama

            # Generate embedding using nomic-embed-text model
            response = ollama.embeddings(model='nomic-embed-text', prompt=text)

            # Extract embedding vector
            embedding = np.array(response['embedding'])
            return embedding

        except ImportError:
            logger.error("Ollama package not installed")
            return None
        except Exception as e:
            logger.warning(f"Failed to generate embedding: {e}")
            return None

    def add_record(self, id: str, text: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Add a new record to the vector store.

        Args:
            id: Unique identifier for the record
            text: Text content to embed and store
            metadata: Additional metadata to store

        Returns:
            True if successfully added, False otherwise
        """
        # Generate embedding
        embedding = self.get_embedding(text)
        if embedding is None:
            logger.error(f"Failed to generate embedding for record {id}")
            return False

        # Store the record
        self.vectors.append(embedding)
        self.ids.append(id)
        self.metadata[id] = {
            'text': text,
            'metadata': metadata or {},
            'vector': embedding
        }

        logger.debug(f"Added record {id} to vector store")
        return True

    def find_similar(self, text: str, top_k: int = 3) -> List[Tuple[str, float, Dict[str, Any]]]:
        """
        Find similar records using cosine similarity.

        Args:
            text: Query text to find similar records for
            top_k: Number of top similar records to return

        Returns:
            List of tuples: (id, similarity_score, metadata)
        """
        if not self.vectors:
            logger.warning("No vectors in store")
            return []

        # Generate embedding for query
        query_embedding = self.get_embedding(text)
        if query_embedding is None:
            logger.error("Failed to generate embedding for query")
            return []

        # Calculate cosine similarities
        similarities = cosine_similarity(
            query_embedding.reshape(1, -1),
            np.array(self.vectors)
        ).flatten()

        # Get top-k indices
        top_indices = np.argsort(similarities)[::-1][:top_k]

        # Return results
        results = []
        for idx in top_indices:
            record_id = self.ids[idx]
            similarity = float(similarities[idx])
            metadata = self.metadata[record_id].copy()
            # Remove vector from returned metadata for cleanliness
            metadata.pop('vector', None)

            results.append((record_id, similarity, metadata))

        logger.debug(f"Found {len(results)} similar records for query")
        return results

    def save_index(self) -> bool:
        """
        Save the vector index to disk.

        Returns:
            True if successfully saved, False otherwise
        """
        try:
            data = {
                'vectors': self.vectors,
                'metadata': self.metadata,
                'ids': self.ids
            }

            with open(self.storage_path, 'wb') as f:
                pickle.dump(data, f)

            logger.info(f"Saved {len(self.vectors)} vectors to {self.storage_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to save index: {e}")
            return False

    def _load_index(self) -> None:
        """Load vector index from disk if it exists."""
        if not self.storage_path.exists():
            logger.info("No existing vector index found")
            return

        try:
            with open(self.storage_path, 'rb') as f:
                data = pickle.load(f)

            self.vectors = data.get('vectors', [])
            self.metadata = data.get('metadata', {})
            self.ids = data.get('ids', [])

            logger.info(f"Loaded {len(self.vectors)} vectors from {self.storage_path}")

        except Exception as e:
            logger.error(f"Failed to load index: {e}")
            # Reset to empty state
            self.vectors = []
            self.metadata = {}
            self.ids = []