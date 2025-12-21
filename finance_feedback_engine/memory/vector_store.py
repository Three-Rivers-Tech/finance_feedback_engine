"""
Vector memory store for semantic search capabilities.

Uses Ollama embeddings and cosine similarity for intelligent memory retrieval.
"""

import concurrent.futures
import io
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger(__name__)

timeout_val = os.getenv("EMBEDDING_TIMEOUT_SECS", "30")
try:
    EMBEDDING_TIMEOUT_SECS = int(timeout_val)
    if EMBEDDING_TIMEOUT_SECS <= 0:
        EMBEDDING_TIMEOUT_SECS = 30
        logger.warning(
            f"EMBEDDING_TIMEOUT_SECS must be positive, got {timeout_val}, using default 30"
        )
except (ValueError, TypeError):
    EMBEDDING_TIMEOUT_SECS = 30
    logger.warning(
        f"Invalid EMBEDDING_TIMEOUT_SECS value '{timeout_val}', using default 30"
    )


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
        # Allow callers to accidentally pass a dict; extract common keys safely
        if isinstance(storage_path, dict):
            storage_path = (
                storage_path.get("vector_store_path")
                or storage_path.get("vector_memory_path")
                or storage_path.get("dir")
                or "data/memory/vectors.pkl"
            )

        self.storage_path = Path(storage_path or "data/memory/vectors.pkl")
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

        # Storage for vectors and metadata
        self.vectors: List[np.ndarray] = []
        self.metadata: Dict[str, Dict[str, Any]] = {}
        self.ids: List[str] = []

        # Load existing index if available
        self._load_index()

        # Handle empty state gracefully
        if len(self.vectors) == 0:
            logger.info(
                "VectorMemory initialized with empty store (expected on first run)"
            )
            self.cold_start_mode = True
        else:
            logger.info(
                f"VectorMemory initialized with {len(self.vectors)} stored vectors"
            )
            self.cold_start_mode = False

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
        except ImportError:
            logger.error("Ollama package not installed")
            return None

        def _get_embedding(prompt):
            return ollama.embeddings(model="nomic-embed-text", prompt=prompt)

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_get_embedding, text)
            try:
                response = future.result(timeout=EMBEDDING_TIMEOUT_SECS)
                # Extract embedding vector
                embedding = np.array(response["embedding"])
                return embedding
            except concurrent.futures.TimeoutError:
                logger.warning(
                    f"Embedding generation timed out after {EMBEDDING_TIMEOUT_SECS} seconds"
                )
                return None
            except Exception as e:
                logger.warning(f"Failed to generate embedding: {e}")
                return None

    def add_record(
        self, id: str, text: str, metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
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
        if id in self.ids:
            index = self.ids.index(id)
            self.vectors[index] = embedding
            self.metadata[id]["text"] = text
            self.metadata[id]["metadata"] = metadata or {}
        else:
            self.vectors.append(embedding)
            self.ids.append(id)
            self.metadata[id] = {"text": text, "metadata": metadata or {}}

        logger.debug(f"Added/Updated record {id} to vector store")
        return True

    def find_similar(
        self, text: str, top_k: int = 5
    ) -> List[Tuple[str, float, Dict[str, Any]]]:
        """
        Find similar records using cosine similarity.

        Args:
            text: Query text to find similar records for
            top_k: Number of top similar records to return

        Returns:
            List of tuples: (id, similarity_score, metadata)
        """
        if not self.vectors:
            logger.debug("Vector store empty, returning no results (cold start mode)")
            return []

        # Validate top_k
        top_k = min(max(1, top_k), len(self.vectors))

        # Generate embedding for query
        query_embedding = self.get_embedding(text)
        if query_embedding is None:
            logger.error("Failed to generate embedding for query")
            return []

        # Validate dimension consistency
        try:
            vector_array = np.array(self.vectors)
        except Exception as e:
            logger.error(
                f"Failed to convert vectors to array (inconsistent dimensions?): {e}"
            )
            return []

        # Calculate cosine similarities
        similarities = cosine_similarity(
            query_embedding.reshape(1, -1), vector_array
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
            metadata.pop("vector", None)

            results.append((record_id, similarity, metadata))

        logger.debug(f"Found {len(results)} similar records for query")
        return results

    def save_index(self) -> bool:
        """
        Save the vector index to disk using JSON format.

        Returns:
            True if successfully saved, False otherwise
        """
        try:
            # Convert numpy arrays to lists for JSON serialization
            vectors_list = (
                [vec.tolist() for vec in self.vectors] if self.vectors else []
            )

            data = {
                "version": "2.0",
                "vectors": vectors_list,
                "metadata": self.metadata,
                "ids": self.ids,
            }

            # Change file extension to .json
            json_path = self.storage_path.with_suffix(".json")

            with open(json_path, "w") as f:
                json.dump(data, f, indent=2)

            logger.info(f"Saved {len(self.vectors)} vectors to {json_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to save index: {e}")
            return False

    def _load_index(self) -> None:
        """Load vector index from disk if it exists (supports both .pkl and .json formats)."""
        # Try JSON format first (.json extension)
        json_path = self.storage_path.with_suffix(".json")

        if json_path.exists():
            try:
                with open(json_path, "r") as f:
                    data = json.load(f)

                # Convert lists back to numpy arrays
                vectors_list = data.get("vectors", [])
                self.vectors = [np.array(vec) for vec in vectors_list]
                self.metadata = data.get("metadata", {})
                self.ids = data.get("ids", [])

                version = data.get("version", "unknown")
                logger.info(
                    f"Loaded {len(self.vectors)} vectors from {json_path} (version: {version})"
                )
                return

            except Exception as e:
                logger.error(f"Failed to load JSON index: {e}")
                # Reset to empty state
                self.vectors = []
                self.metadata = {}
                self.ids = []
                return

        # Fall back to legacy pickle format (.pkl extension) if JSON not found
        if self.storage_path.exists():
            logger.warning(
                f"Loading legacy pickle format from {self.storage_path}. "
                "This format is deprecated. Consider migrating to JSON format."
            )
            try:
                import pickle

                with open(self.storage_path, "rb") as f:
                    # Read the raw data
                    raw_data = f.read()

                    # Use a restricted unpickler to prevent arbitrary code execution
                    class RestrictedUnpickler(pickle.Unpickler):
                        def find_class(self, module, name):
                            # Only allow safe classes from these modules
                            if module in (
                                "numpy",
                                "collections",
                                "numpy.core.multiarray",
                                "__builtin__",
                                "builtins",
                            ):
                                return getattr(
                                    __import__(module, fromlist=[name]), name
                                )
                            # Prevent loading from unsafe modules that could execute arbitrary code
                            raise pickle.UnpicklingError(
                                f"Global '{module}.{name}' is forbidden"
                            )

                    # Use a BytesIO object to pass data to the restricted unpickler
                    data = RestrictedUnpickler(io.BytesIO(raw_data)).load()

                self.vectors = data.get("vectors", [])
                self.metadata = data.get("metadata", {})
                self.ids = data.get("ids", [])

                logger.info(
                    f"Loaded {len(self.vectors)} vectors from {self.storage_path}"
                )
                logger.warning(
                    "Pickle format loaded successfully. The data will be saved in JSON format on next save."
                )

            except Exception as e:
                logger.error(f"Failed to load pickle index: {e}")
                # Reset to empty state
                self.vectors = []
                self.metadata = {}
                self.ids = []
            return

        logger.info("No existing vector index found")
