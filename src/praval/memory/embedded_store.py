"""
Embedded Vector Store using established libraries

Uses well-tested, production-ready libraries:
- ChromaDB for embedded vector storage
- sentence-transformers for embeddings
- scikit-learn for similarity calculations
- Standard pathlib for file operations
"""

from typing import List, Optional, Dict, Any, Union
import logging
import os
import tempfile
from pathlib import Path
from datetime import datetime

try:
    import chromadb
    from chromadb.config import Settings
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False
    chromadb = None

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    SentenceTransformer = None

try:
    from sklearn.metrics.pairwise import cosine_similarity
    import numpy as np
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    cosine_similarity = None
    np = None

from .memory_types import MemoryEntry, MemoryType, MemoryQuery, MemorySearchResult

logger = logging.getLogger(__name__)


class EmbeddedVectorStore:
    """
    Production-ready embedded vector store
    
    Features:
    - ChromaDB for persistent vector storage
    - SentenceTransformers for quality embeddings
    - Scikit-learn for reliable similarity calculations
    - Automatic fallbacks for missing dependencies
    """
    
    def __init__(self,
                 storage_path: Optional[str] = None,
                 collection_name: str = "praval_memories",
                 embedding_model: str = "all-MiniLM-L6-v2",
                 enable_collection_separation: bool = True):
        """
        Initialize embedded vector store with separated collections for knowledge and memory
        
        Args:
            storage_path: Path for persistent storage
            collection_name: Base name for collections (will create _knowledge and _memory variants)
            embedding_model: SentenceTransformer model name
            enable_collection_separation: Whether to use separate collections for knowledge vs memory
        """
        self.base_collection_name = collection_name
        self.embedding_model_name = embedding_model
        self.enable_collection_separation = enable_collection_separation
        
        # Define collection names based on separation setting
        if enable_collection_separation:
            self.knowledge_collection_name = f"{collection_name}_knowledge"
            self.memory_collection_name = f"{collection_name}_memory"
            # For backward compatibility, also track the original collection name
            self.legacy_collection_name = collection_name
        else:
            # Legacy mode: single collection for everything
            self.knowledge_collection_name = collection_name
            self.memory_collection_name = collection_name
            self.legacy_collection_name = None
        
        # Setup storage path
        if storage_path is None:
            storage_path = os.path.join(tempfile.gettempdir(), "praval_memory")
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        # Initialize components
        self._init_chromadb()
        self._init_embedding_model()
        
        logger.info(f"Embedded vector store initialized at {self.storage_path}")
    
    def _init_chromadb(self):
        """Initialize ChromaDB with proper error handling and collection separation"""
        if not CHROMADB_AVAILABLE:
            raise ImportError(
                "ChromaDB is required for embedded vector store. "
                "Install with: pip install chromadb"
            )
        
        try:
            # Create ChromaDB client with persistent storage
            self.client = chromadb.PersistentClient(
                path=str(self.storage_path),
                settings=Settings(
                    anonymized_telemetry=False,
                    allow_reset=False  # Prevent accidental data loss
                )
            )
            
            # Initialize collections based on separation setting
            if self.enable_collection_separation:
                # Create separate collections for knowledge and memory
                self.knowledge_collection = self._get_or_create_collection(self.knowledge_collection_name)
                self.memory_collection = self._get_or_create_collection(self.memory_collection_name)
                
                # Check for legacy collection and migrate if needed
                self._migrate_legacy_collection_if_needed()
                
                logger.info(f"Initialized separated collections: {self.knowledge_collection_name}, {self.memory_collection_name}")
            else:
                # Legacy mode: single collection
                self.collection = self._get_or_create_collection(self.knowledge_collection_name)
                logger.info(f"Initialized single collection: {self.knowledge_collection_name}")
                
        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB: {e}")
            raise
    
    def _get_or_create_collection(self, collection_name: str):
        """Get or create a ChromaDB collection with proper error handling"""
        try:
            collection = self.client.get_collection(name=collection_name)
            logger.info(f"Using existing ChromaDB collection: {collection_name}")
            return collection
        except Exception as e:
            # Handle ChromaDB NotFoundError and other exceptions for collection not found
            logger.info(f"Collection '{collection_name}' not found, creating new collection")
            collection = self.client.create_collection(
                name=collection_name,
                metadata={"hnsw:space": "cosine"}
            )
            logger.info(f"Created new ChromaDB collection: {collection_name}")
            return collection
    
    def _migrate_legacy_collection_if_needed(self):
        """Migrate data from legacy single collection to separated collections if needed"""
        if not self.legacy_collection_name:
            return
        
        try:
            # Check if legacy collection exists
            legacy_collection = self.client.get_collection(name=self.legacy_collection_name)
            
            # Get all entries from legacy collection
            all_results = legacy_collection.get(
                include=["metadatas", "documents", "embeddings"]
            )
            
            if not all_results["ids"]:
                logger.info("Legacy collection is empty, no migration needed")
                return
            
            logger.info(f"Migrating {len(all_results['ids'])} entries from legacy collection {self.legacy_collection_name}")
            
            # Migrate entries to appropriate collections
            for i, memory_id in enumerate(all_results["ids"]):
                metadata = all_results["metadatas"][i]
                document = all_results["documents"][i]
                embedding = all_results["embeddings"][i] if all_results.get("embeddings") is not None and len(all_results["embeddings"]) > i else None
                
                # Determine target collection based on memory type
                memory_type = metadata.get("memory_type", "unknown")
                if memory_type == "semantic":
                    target_collection = self.knowledge_collection
                else:
                    target_collection = self.memory_collection
                
                # Store in target collection
                try:
                    if embedding is not None:
                        target_collection.upsert(
                            ids=[memory_id],
                            embeddings=[embedding],
                            metadatas=[metadata],
                            documents=[document]
                        )
                    else:
                        target_collection.upsert(
                            ids=[memory_id],
                            metadatas=[metadata],
                            documents=[document]
                        )
                    logger.debug(f"Migrated memory {memory_id} to {target_collection.name}")
                except Exception as e:
                    logger.error(f"Failed to migrate memory {memory_id}: {e}")
                    raise
            
            # Delete legacy collection after successful migration
            self.client.delete_collection(name=self.legacy_collection_name)
            logger.info(f"Successfully migrated and removed legacy collection {self.legacy_collection_name}")
            
        except Exception as e:
            # Legacy collection doesn't exist or migration failed - that's okay
            logger.warning(f"Legacy collection migration not needed or failed: {e}")
            import traceback
            logger.debug(f"Migration exception details: {traceback.format_exc()}")
    
    def _init_embedding_model(self):
        """Initialize embedding model with fallbacks"""
        if SENTENCE_TRANSFORMERS_AVAILABLE:
            try:
                self.embedding_model = SentenceTransformer(self.embedding_model_name)
                logger.info(f"Initialized SentenceTransformer model: {self.embedding_model_name}")
                self.embedding_size = self.embedding_model.get_sentence_embedding_dimension()
            except Exception as e:
                logger.warning(f"Failed to load SentenceTransformer model {self.embedding_model_name}: {e}")
                self.embedding_model = None
                self.embedding_size = 384  # Default size
        else:
            logger.warning("sentence-transformers not available, using fallback embeddings")
            self.embedding_model = None
            self.embedding_size = 384
    
    def store(self, memory: MemoryEntry) -> str:
        """Store a memory entry with vector embedding in appropriate collection"""
        try:
            # Generate embedding if not provided
            if memory.embedding is None:
                memory.embedding = self._generate_embedding(memory.content)
            
            # Prepare metadata for ChromaDB (must be simple types)
            metadata = {
                'agent_id': memory.agent_id,
                'memory_type': memory.memory_type.value,
                'created_at': memory.created_at.isoformat(),
                'importance': float(memory.importance),
                'access_count': int(memory.access_count),
            }
            
            # Add simple metadata fields (ChromaDB doesn't support nested dicts)
            for key, value in memory.metadata.items():
                if isinstance(value, (str, int, float, bool)):
                    metadata[f"meta_{key}"] = value
                else:
                    metadata[f"meta_{key}"] = str(value)
            
            # Choose appropriate collection
            target_collection = self._get_target_collection(memory.memory_type)
            
            # Store in ChromaDB
            target_collection.upsert(
                ids=[memory.id],
                embeddings=[memory.embedding],
                metadatas=[metadata],
                documents=[memory.content]
            )
            
            logger.debug(f"Stored memory {memory.id} in {target_collection.name} collection")
            return memory.id
            
        except Exception as e:
            logger.error(f"Failed to store memory {memory.id}: {e}")
            raise
    
    def _get_target_collection(self, memory_type: MemoryType):
        """Get the appropriate collection for a memory type"""
        if not self.enable_collection_separation:
            return self.collection
        
        # Semantic memories (knowledge base) go to knowledge collection
        if memory_type == MemoryType.SEMANTIC:
            return self.knowledge_collection
        else:
            # All other memory types go to memory collection
            return self.memory_collection
    
    def retrieve(self, memory_id: str) -> Optional[MemoryEntry]:
        """Retrieve a specific memory by ID from both collections if needed"""
        try:
            if self.enable_collection_separation:
                # Try both collections
                for collection in [self.knowledge_collection, self.memory_collection]:
                    result = collection.get(
                        ids=[memory_id],
                        include=["metadatas", "documents", "embeddings"]
                    )
                    
                    if result["ids"]:
                        return self._result_to_memory_entry(result, 0)
                return None
            else:
                # Single collection mode
                result = self.collection.get(
                    ids=[memory_id],
                    include=["metadatas", "documents", "embeddings"]
                )
                
                if not result["ids"]:
                    return None
                
                return self._result_to_memory_entry(result, 0)
            
        except Exception as e:
            logger.error(f"Failed to retrieve memory {memory_id}: {e}")
            return None
    
    def search(self, query: MemoryQuery) -> MemorySearchResult:
        """Search memories using vector similarity across appropriate collections"""
        try:
            # Generate query embedding
            query_embedding = self._generate_embedding(query.query_text)
            
            # Build where clause for filtering
            where_conditions = []
            
            if query.agent_id:
                where_conditions.append({"agent_id": {"$eq": query.agent_id}})
            
            if query.memory_types:
                # ChromaDB supports $in operator
                memory_type_values = [mt.value for mt in query.memory_types]
                if len(memory_type_values) == 1:
                    where_conditions.append({"memory_type": {"$eq": memory_type_values[0]}})
                else:
                    where_conditions.append({"memory_type": {"$in": memory_type_values}})
            
            # Construct final where clause
            if len(where_conditions) == 0:
                where = None
            elif len(where_conditions) == 1:
                where = where_conditions[0]
            else:
                where = {"$and": where_conditions}
            
            # Add temporal filtering if specified
            if query.temporal_filter:
                temporal_conditions = []
                # ChromaDB uses string comparison for ISO dates
                if 'after' in query.temporal_filter:
                    temporal_conditions.append({"created_at": {"$gte": query.temporal_filter['after'].isoformat()}})
                if 'before' in query.temporal_filter:
                    temporal_conditions.append({"created_at": {"$lte": query.temporal_filter['before'].isoformat()}})
                
                # Add temporal conditions to existing where clause
                if temporal_conditions:
                    if where is None:
                        if len(temporal_conditions) == 1:
                            where = temporal_conditions[0]
                        else:
                            where = {"$and": temporal_conditions}
                    else:
                        # Combine with existing conditions
                        if isinstance(where, dict) and "$and" in where:
                            where["$and"].extend(temporal_conditions)
                        else:
                            all_conditions = [where] + temporal_conditions
                            where = {"$and": all_conditions}
            
            # Determine which collections to search
            collections_to_search = self._get_collections_for_search(query)
            
            # Search across collections and combine results
            all_entries = []
            all_scores = []
            
            for collection in collections_to_search:
                results = collection.query(
                    query_embeddings=[query_embedding],
                    n_results=query.limit,
                    where=where if where else None,
                    include=["metadatas", "documents", "distances", "embeddings"]
                )
                
                # Convert results
                if results["ids"] and results["ids"][0]:
                    for i in range(len(results["ids"][0])):
                        distance = results["distances"][0][i]
                        
                        # Convert distance to similarity score
                        # ChromaDB returns cosine distance (1 - cosine_similarity)
                        similarity = 1.0 - distance
                        
                        # Apply similarity threshold
                        if similarity < query.similarity_threshold:
                            continue
                        
                        memory = self._result_to_memory_entry(results, i)
                        if memory:
                            memory.mark_accessed()
                            all_entries.append(memory)
                            all_scores.append(similarity)
            
            # Sort by similarity score and limit results
            if all_entries:
                sorted_pairs = sorted(zip(all_entries, all_scores), key=lambda x: x[1], reverse=True)
                all_entries, all_scores = zip(*sorted_pairs[:query.limit])
                all_entries, all_scores = list(all_entries), list(all_scores)
            
            return MemorySearchResult(
                entries=all_entries,
                scores=all_scores,
                query=query,
                total_found=len(all_entries)
            )
            
        except Exception as e:
            logger.error(f"Failed to search memories: {e}")
            return MemorySearchResult(entries=[], scores=[], query=query, total_found=0)
    
    def _get_collections_for_search(self, query: MemoryQuery) -> List:
        """Get list of collections to search based on query"""
        if not self.enable_collection_separation:
            return [self.collection]
        
        collections = []
        
        if query.memory_types:
            # Search specific memory types
            for memory_type in query.memory_types:
                if memory_type == MemoryType.SEMANTIC:
                    if self.knowledge_collection not in collections:
                        collections.append(self.knowledge_collection)
                else:
                    if self.memory_collection not in collections:
                        collections.append(self.memory_collection)
        else:
            # Search both collections if no specific types requested
            collections = [self.knowledge_collection, self.memory_collection]
        
        return collections
    
    def delete(self, memory_id: str) -> bool:
        """Delete a memory entry - only allowed from memory collection, not knowledge base"""
        try:
            if self.enable_collection_separation:
                # Only allow deletion from memory collection (conversational memory)
                # Knowledge base is immutable
                try:
                    # Check if memory exists in memory collection
                    result = self.memory_collection.get(ids=[memory_id])
                    if result["ids"]:  # Memory exists in memory collection
                        self.memory_collection.delete(ids=[memory_id])
                        logger.debug(f"Deleted memory {memory_id} from memory collection")
                        return True
                    else:
                        # Check if it's in knowledge collection (but don't delete)
                        knowledge_result = self.knowledge_collection.get(ids=[memory_id])
                        if knowledge_result["ids"]:
                            logger.warning(f"Cannot delete memory {memory_id}: it's in knowledge base collection (immutable)")
                            return False
                        else:
                            logger.debug(f"Memory {memory_id} not found in any collection")
                            return False
                except Exception as e:
                    logger.error(f"Error checking/deleting memory {memory_id}: {e}")
                    return False
            else:
                # Single collection mode - allow deletion
                self.collection.delete(ids=[memory_id])
                logger.debug(f"Deleted memory {memory_id}")
                return True
        except Exception as e:
            logger.error(f"Failed to delete memory {memory_id}: {e}")
            return False
    
    def clear_agent_memories(self, agent_id: str):
        """Clear agent memories - only from memory collection, knowledge base is immutable"""
        try:
            if self.enable_collection_separation:
                # Only clear from memory collection (conversational memory)
                # Knowledge base is immutable and should not be cleared
                try:
                    self.memory_collection.delete(where={"agent_id": agent_id})
                    logger.info(f"Cleared conversational memories for agent {agent_id}")
                    logger.debug(f"Knowledge base memories for agent {agent_id} preserved (immutable)")
                except Exception as e:
                    logger.warning(f"Failed to clear conversational memories for agent {agent_id}: {e}")
                    raise
            else:
                # Single collection mode - clear all
                self.collection.delete(where={"agent_id": agent_id})
                logger.info(f"Cleared memories for agent {agent_id}")
        except Exception as e:
            logger.error(f"Failed to clear memories for agent {agent_id}: {e}")
            raise
    
    def get_stats(self) -> Dict[str, Any]:
        """Get storage statistics for all collections"""
        try:
            if self.enable_collection_separation:
                knowledge_count = self.knowledge_collection.count()
                memory_count = self.memory_collection.count()
                total_count = knowledge_count + memory_count
                
                return {
                    "backend": "chromadb",
                    "total_memories": total_count,
                    "knowledge_memories": knowledge_count,
                    "conversational_memories": memory_count,
                    "storage_path": str(self.storage_path),
                    "knowledge_collection": self.knowledge_collection_name,
                    "memory_collection": self.memory_collection_name,
                    "collection_separation": True,
                    "embedding_model": self.embedding_model_name,
                    "embedding_size": self.embedding_size
                }
            else:
                count = self.collection.count()
                return {
                    "backend": "chromadb",
                    "total_memories": count,
                    "storage_path": str(self.storage_path),
                    "collection_name": self.knowledge_collection_name,
                    "collection_separation": False,
                    "embedding_model": self.embedding_model_name,
                    "embedding_size": self.embedding_size
                }
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {"backend": "chromadb", "error": str(e)}
    
    def health_check(self) -> bool:
        """Check if the vector store is healthy"""
        try:
            if self.enable_collection_separation:
                # Check both collections
                self.knowledge_collection.count()
                self.memory_collection.count()
            else:
                self.collection.count()
            return True
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False
    
    def _generate_embedding(self, text: str) -> List[float]:
        """Generate high-quality embedding using SentenceTransformers"""
        if not text:
            return [0.0] * self.embedding_size
        
        try:
            if self.embedding_model:
                # Use SentenceTransformer for quality embeddings
                embedding = self.embedding_model.encode(text, convert_to_tensor=False)
                return embedding.tolist() if hasattr(embedding, 'tolist') else list(embedding)
            else:
                # Fallback to simple hash-based embedding
                return self._fallback_embedding(text)
        except Exception as e:
            logger.warning(f"Failed to generate embedding, using fallback: {e}")
            return self._fallback_embedding(text)
    
    def _fallback_embedding(self, text: str) -> List[float]:
        """Simple fallback embedding for when SentenceTransformers unavailable"""
        import hashlib
        
        # Use multiple hash functions for better distribution
        hash_funcs = [hashlib.md5, hashlib.sha1, hashlib.sha256]
        embedding = []
        
        for hash_func in hash_funcs:
            hash_obj = hash_func(text.encode('utf-8'))
            hash_hex = hash_obj.hexdigest()
            
            # Convert hex to normalized floats
            for i in range(0, min(len(hash_hex), 16), 2):  # Limit to reasonable size
                byte_val = int(hash_hex[i:i+2], 16)
                normalized_val = (byte_val - 127.5) / 127.5  # Normalize to [-1, 1]
                embedding.append(normalized_val)
        
        # Pad or truncate to target size
        while len(embedding) < self.embedding_size:
            embedding.extend(embedding[:min(len(embedding), self.embedding_size - len(embedding))])
        
        return embedding[:self.embedding_size]
    
    def _result_to_memory_entry(self, results: Dict, index: int) -> Optional[MemoryEntry]:
        """Convert ChromaDB result to MemoryEntry"""
        try:
            
            # Handle both query results (nested arrays) and get results (flat arrays)
            # Check if this is a query result by checking if first element is a list/array
            if len(results["ids"]) > 0 and hasattr(results["ids"][0], '__len__') and not isinstance(results["ids"][0], str):
                # Query result format: [['id1', 'id2']]  
                memory_id = results["ids"][0][index]
                metadata = results["metadatas"][0][index]
                document = results["documents"][0][index]
                embedding = results["embeddings"][0][index] if results.get("embeddings") is not None and len(results["embeddings"]) > 0 else None
            else:
                # Get result format: ['id1', 'id2']
                memory_id = results["ids"][index]
                metadata = results["metadatas"][index]
                document = results["documents"][index]
                embedding = results["embeddings"][index] if results.get("embeddings") is not None and len(results["embeddings"]) > index else None
            
            # Reconstruct metadata dict (remove meta_ prefixes)
            reconstructed_metadata = {}
            for key, value in metadata.items():
                if key.startswith("meta_"):
                    reconstructed_metadata[key[5:]] = value
            
            # Create MemoryEntry
            memory = MemoryEntry(
                id=memory_id,
                agent_id=metadata['agent_id'],
                memory_type=MemoryType(metadata['memory_type']),
                content=document,
                metadata=reconstructed_metadata,
                embedding=embedding,
                created_at=datetime.fromisoformat(metadata['created_at']),
                importance=metadata.get('importance', 0.5),
                access_count=metadata.get('access_count', 0)
            )
            
            return memory
            
        except Exception as e:
            logger.error(f"Failed to convert result to memory entry at index {index}: {e}")
            return None
    
    def index_knowledge_files(self, knowledge_path: Union[str, Path], agent_id: str) -> int:
        """Index knowledge files from a directory"""
        knowledge_path = Path(knowledge_path)
        
        if not knowledge_path.exists():
            raise ValueError(f"Knowledge base path does not exist: {knowledge_path}")
        
        indexed_count = 0
        supported_extensions = {'.txt', '.md', '.rst', '.py', '.js', '.json', '.yaml', '.yml', '.pdf'}
        
        # Recursively find and index files
        for file_path in knowledge_path.rglob('*'):
            if file_path.is_file() and file_path.suffix.lower() in supported_extensions:
                try:
                    # Handle PDF files differently from text files
                    if file_path.suffix.lower() == '.pdf':
                        content = self._extract_pdf_text(file_path)
                        if not content or len(content.strip()) < 50:
                            logger.warning(f"PDF file appears to be empty or unreadable: {file_path}")
                            continue
                    else:
                        content = file_path.read_text(encoding='utf-8', errors='ignore')
                    
                    # Create memory entry for the file
                    memory = MemoryEntry(
                        id=None,  # Will be auto-generated
                        agent_id=agent_id,
                        memory_type=MemoryType.SEMANTIC,
                        content=content,
                        metadata={
                            'source_file': str(file_path),
                            'file_type': file_path.suffix,
                            'file_size': len(content),
                            'indexed_at': datetime.now().isoformat()
                        },
                        importance=0.8  # Knowledge base files are important
                    )
                    
                    # Store directly in knowledge collection (bypass automatic type detection)
                    if self.enable_collection_separation:
                        # Generate embedding if not provided
                        if memory.embedding is None:
                            memory.embedding = self._generate_embedding(memory.content)
                        
                        # Prepare metadata for ChromaDB
                        metadata = {
                            'agent_id': memory.agent_id,
                            'memory_type': memory.memory_type.value,
                            'created_at': memory.created_at.isoformat(),
                            'importance': float(memory.importance),
                            'access_count': int(memory.access_count),
                        }
                        
                        # Add simple metadata fields
                        for key, value in memory.metadata.items():
                            if isinstance(value, (str, int, float, bool)):
                                metadata[f"meta_{key}"] = value
                            else:
                                metadata[f"meta_{key}"] = str(value)
                        
                        # Store directly in knowledge collection
                        self.knowledge_collection.upsert(
                            ids=[memory.id],
                            embeddings=[memory.embedding],
                            metadatas=[metadata],
                            documents=[memory.content]
                        )
                    else:
                        # Use regular store method for legacy mode
                        self.store(memory)
                    
                    indexed_count += 1
                    logger.debug(f"Indexed knowledge file: {file_path}")
                    
                except Exception as e:
                    logger.warning(f"Failed to index file {file_path}: {e}")
                    continue
        
        logger.info(f"Indexed {indexed_count} knowledge files from {knowledge_path}")
        return indexed_count
    
    def _extract_pdf_text(self, pdf_path: Path) -> str:
        """
        Extract text content from a PDF file using PyPDF2
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            Extracted text content
            
        Raises:
            ImportError: If PyPDF2 is not installed
            Exception: If PDF cannot be read
        """
        try:
            import PyPDF2
        except ImportError:
            raise ImportError(
                "PyPDF2 is required for PDF processing. "
                "Install with: pip install PyPDF2"
            )
        
        try:
            text_content = []
            
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                
                # Extract text from all pages
                for page_num, page in enumerate(pdf_reader.pages):
                    try:
                        page_text = page.extract_text()
                        if page_text.strip():
                            # Add page separator for better context
                            text_content.append(f"=== Page {page_num + 1} ===\n{page_text}")
                    except Exception as e:
                        logger.warning(f"Failed to extract text from page {page_num + 1} of {pdf_path}: {e}")
                        continue
            
            if not text_content:
                logger.warning(f"No readable text found in PDF: {pdf_path}")
                return ""
            
            # Join all pages with double newlines
            full_text = "\n\n".join(text_content)
            
            # Basic text cleanup
            full_text = self._clean_pdf_text(full_text)
            
            logger.debug(f"Extracted {len(full_text)} characters from PDF: {pdf_path}")
            return full_text
            
        except Exception as e:
            logger.error(f"Failed to extract text from PDF {pdf_path}: {e}")
            return ""
    
    def _clean_pdf_text(self, text: str) -> str:
        """
        Clean up extracted PDF text for better indexing
        
        Args:
            text: Raw text extracted from PDF
            
        Returns:
            Cleaned text
        """
        import re
        
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove page headers/footers (common patterns)
        text = re.sub(r'=== Page \d+ ===\s*\d+\s*', '\n\n', text)
        
        # Remove URLs and email patterns that might confuse embeddings
        text = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '[URL]', text)
        text = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL]', text)
        
        # Remove excessive punctuation
        text = re.sub(r'[.]{3,}', '...', text)
        text = re.sub(r'[-]{3,}', '---', text)
        
        # Normalize whitespace again
        text = re.sub(r'\n\s*\n', '\n\n', text)
        text = text.strip()
        
        return text