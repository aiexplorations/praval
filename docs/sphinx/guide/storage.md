# Storage System Guide

Praval's Unified Data Storage and Retrieval System provides a consistent interface for persisting data across multiple storage backends.

## Overview

The storage system abstracts away the complexity of different storage providers, giving you a single API to work with:

- **FileSystem**: Local file storage
- **PostgreSQL**: Relational database
- **Redis**: In-memory key-value cache
- **S3**: Cloud object storage (AWS, MinIO, etc.)
- **Qdrant**: Vector database for embeddings

## Quick Start

### Basic Storage

```python
from praval import get_data_manager

# Get the data manager
dm = get_data_manager()

# Store some data
ref = dm.store(
    data={"user": "alice", "preferences": {"theme": "dark"}},
    storage_type="filesystem",
    key="user_alice"
)

# Retrieve it later
user_data = dm.retrieve(ref)
print(user_data)  # {"user": "alice", "preferences": {"theme": "dark"}}
```

### Storage with Agents

```python
from praval import agent, get_data_manager

@agent("data_handler")
def handle_data(spore):
    dm = get_data_manager()

    # Store processing results
    result = process_data(spore.knowledge.get("input"))
    ref = dm.store(
        data=result,
        storage_type="postgresql",
        metadata={"processed_at": "2025-01-15"}
    )

    return {"stored_reference": ref}
```

## Storage Providers

### FileSystem Provider

**Best for**: Local development, small files, simple persistence

```python
# Register filesystem provider
from praval.storage.providers import FileSystemProvider

provider = FileSystemProvider(base_path="./data")
dm.register_provider("filesystem", provider)

# Store data
ref = dm.store(
    data={"content": "Hello, World!"},
    storage_type="filesystem",
    key="greeting.json"
)

# Data is stored at ./data/greeting.json
```

**Configuration**:
```python
provider = FileSystemProvider(
    base_path="./storage",    # Root directory
    auto_create=True,         # Create directory if missing
    pretty_json=True          # Format JSON nicely
)
```

### PostgreSQL Provider

**Best for**: Structured data, transactional operations, queries

```python
from praval.storage.providers import PostgreSQLProvider

provider = PostgreSQLProvider(
    host="localhost",
    port=5432,
    database="praval_db",
    user="praval_user",
    password="secure_password"
)

dm.register_provider("postgresql", provider)

# Store with metadata for querying
ref = dm.store(
    data={"user_id": 123, "action": "login"},
    storage_type="postgresql",
    key="event_001",
    metadata={"event_type": "authentication", "timestamp": "2025-01-15"}
)

# Query by metadata
events = dm.query(
    storage_type="postgresql",
    filters={"metadata.event_type": "authentication"}
)
```

**Schema**: PostgreSQL provider automatically creates tables with:
- `key` (primary key)
- `data` (JSONB column)
- `metadata` (JSONB column)
- `created_at` (timestamp)

### Redis Provider

**Best for**: Caching, temporary data, high-speed access

```python
from praval.storage.providers import RedisProvider

provider = RedisProvider(
    host="localhost",
    port=6379,
    db=0,
    password=None
)

dm.register_provider("redis", provider)

# Store with TTL (time-to-live)
ref = dm.store(
    data={"session_id": "abc123", "user": "alice"},
    storage_type="redis",
    key="session:abc123",
    metadata={"ttl": 3600}  # Expires in 1 hour
)
```

**Features**:
- Automatic expiration (TTL)
- Atomic operations
- Pub/Sub support
- High performance

### S3 Provider

**Best for**: Large files, cloud storage, scalable object storage

```python
from praval.storage.providers import S3Provider

provider = S3Provider(
    bucket_name="praval-data",
    aws_access_key_id="YOUR_KEY",
    aws_secret_access_key="YOUR_SECRET",
    region_name="us-east-1"
)

dm.register_provider("s3", provider)

# Store large data
ref = dm.store(
    data=large_dataset,
    storage_type="s3",
    key="datasets/training_data_v1.json"
)
```

**Compatible with**:
- AWS S3
- MinIO
- DigitalOcean Spaces
- Any S3-compatible storage

### Qdrant Provider

**Best for**: Vector embeddings, semantic search, AI/ML data

```python
from praval.storage.providers import QdrantProvider

provider = QdrantProvider(
    url="http://localhost:6333",
    collection_name="praval_vectors",
    vector_size=384  # Depends on your embedding model
)

dm.register_provider("qdrant", provider)

# Store vectors
ref = dm.store(
    data={
        "text": "Praval is a multi-agent AI framework",
        "vector": embedding_model.encode("Praval is...")
    },
    storage_type="qdrant",
    metadata={"category": "documentation"}
)

# Semantic search
results = dm.search(
    storage_type="qdrant",
    query_vector=embedding_model.encode("AI framework"),
    limit=5
)
```

## Data Manager API

### Storing Data

```python
reference = dm.store(
    data: Any,                    # Any serializable data
    storage_type: str,            # Provider name
    key: Optional[str] = None,    # Optional key (auto-generated if not provided)
    metadata: Optional[Dict] = None  # Optional metadata
) -> DataReference
```

**Returns**: `DataReference` with:
- `storage_type`: Which provider
- `key`: Storage key
- `metadata`: Associated metadata

### Retrieving Data

```python
data = dm.retrieve(
    reference: DataReference
) -> Any
```

Or by key:

```python
data = dm.retrieve_by_key(
    storage_type: str,
    key: str
) -> Any
```

### Deleting Data

```python
success = dm.delete(
    reference: DataReference
) -> bool
```

Or by key:

```python
success = dm.delete_by_key(
    storage_type: str,
    key: str
) -> bool
```

### Querying Data

```python
results = dm.query(
    storage_type: str,
    filters: Dict[str, Any],
    limit: int = 100
) -> List[Any]
```

### Searching (Vector Databases)

```python
results = dm.search(
    storage_type: str,
    query_vector: List[float],
    limit: int = 10,
    filters: Optional[Dict] = None
) -> List[Tuple[Any, float]]  # (data, similarity_score)
```

## Storage Decorators

### @storage_enabled

Make agents storage-aware:

```python
from praval import agent
from praval.storage import storage_enabled

@agent("data_agent")
@storage_enabled(providers=["filesystem", "postgresql"])
def agent_with_storage(spore):
    # storage_manager is automatically injected
    ref = agent_with_storage.storage.store(
        data={"result": "..."},
        storage_type="filesystem"
    )
    return {"reference": ref}
```

### @requires_storage

Enforce storage availability:

```python
from praval.storage import requires_storage

@agent("critical_agent")
@requires_storage(providers=["postgresql", "redis"])
def critical_agent(spore):
    # Fails fast if PostgreSQL or Redis unavailable
    pass
```

## Configuration

### Environment Variables

```bash
# PostgreSQL
export POSTGRES_HOST=localhost
export POSTGRES_PORT=5432
export POSTGRES_DB=praval
export POSTGRES_USER=praval
export POSTGRES_PASSWORD=secret

# Redis
export REDIS_HOST=localhost
export REDIS_PORT=6379
export REDIS_PASSWORD=optional

# S3
export AWS_ACCESS_KEY_ID=your_key
export AWS_SECRET_ACCESS_KEY=your_secret
export AWS_S3_BUCKET=praval-data
export AWS_REGION=us-east-1

# Qdrant
export QDRANT_URL=http://localhost:6333
export QDRANT_COLLECTION=praval_vectors
```

### Programmatic Configuration

Register providers directly with the data manager:

```python
from praval import get_data_manager
from praval.storage.providers import FileSystemProvider, PostgreSQLProvider, RedisProvider

dm = get_data_manager()

# Register filesystem provider
dm.register_provider("filesystem", FileSystemProvider(
    base_path="./data",
    auto_create=True
))

# Register PostgreSQL provider
dm.register_provider("postgresql", PostgreSQLProvider(
    host="localhost",
    database="praval"
))

# Register Redis provider
dm.register_provider("redis", RedisProvider(
    host="localhost",
    db=0
))
```

## Advanced Patterns

### Multi-Provider Storage

Store different data types in optimal storage:

```python
@agent("hybrid_storage")
def hybrid_agent(spore):
    dm = get_data_manager()

    # Cache in Redis
    dm.store(
        data={"session": "temp"},
        storage_type="redis",
        metadata={"ttl": 300}
    )

    # Persist in PostgreSQL
    dm.store(
        data={"transaction": "permanent"},
        storage_type="postgresql"
    )

    # Store large files in S3
    dm.store(
        data=large_file,
        storage_type="s3"
    )
```

### Storage with Memory Integration

Combine storage and memory systems:

```python
@agent("smart_agent", memory=True)
@storage_enabled(providers=["qdrant"])
def smart_agent(spore):
    # Short-term memory (working memory)
    smart_agent.remember("Current task: process data")

    # Long-term storage (permanent)
    result = process_data(spore.knowledge.get("input"))
    ref = smart_agent.storage.store(
        data=result,
        storage_type="qdrant"
    )

    return {"stored": ref}
```

### Transaction-like Operations

Pseudo-transactions across providers:

```python
@agent("transactional")
def transactional_agent(spore):
    dm = get_data_manager()
    refs = []

    try:
        # Store in multiple places
        ref1 = dm.store(data1, "postgresql")
        refs.append(ref1)

        ref2 = dm.store(data2, "s3")
        refs.append(ref2)

        ref3 = dm.store(data3, "redis")
        refs.append(ref3)

        return {"success": True, "refs": refs}

    except Exception as e:
        # Rollback on failure
        for ref in refs:
            dm.delete(ref)
        return {"success": False, "error": str(e)}
```

## Custom Storage Providers

Create your own storage backend:

```python
from praval.storage import BaseStorageProvider, StorageResult

class MyCustomProvider(BaseStorageProvider):
    def __init__(self, config):
        super().__init__("custom")
        self.config = config

    def store(self, key: str, data: Any, metadata: dict) -> StorageResult:
        # Your storage logic
        return StorageResult(success=True, key=key)

    def retrieve(self, key: str) -> Any:
        # Your retrieval logic
        return data

    def delete(self, key: str) -> bool:
        # Your deletion logic
        return True

    def query(self, filters: dict, limit: int) -> List[Any]:
        # Optional: query support
        return results

# Register custom provider
dm.register_provider("custom", MyCustomProvider(config))
```

## Best Practices

### 1. Choose the Right Provider

- **Filesystem**: Development, small data, config files
- **PostgreSQL**: Structured data, transactions, complex queries
- **Redis**: Caching, sessions, temporary data, high-speed access
- **S3**: Large files, archives, media, backups
- **Qdrant**: Embeddings, semantic search, AI/ML vectors

### 2. Use Metadata

```python
# Good - rich metadata
ref = dm.store(
    data=result,
    storage_type="postgresql",
    metadata={
        "created_by": "agent_name",
        "version": "1.0",
        "category": "user_data",
        "tags": ["important", "verified"]
    }
)
```

### 3. Handle Failures Gracefully

```python
try:
    ref = dm.store(data, "postgresql")
except StorageError as e:
    # Fallback to filesystem
    ref = dm.store(data, "filesystem")
```

### 4. Clean Up Temporary Data

```python
# Use TTL for temporary data
dm.store(
    data=temp_result,
    storage_type="redis",
    metadata={"ttl": 3600}  # Auto-delete after 1 hour
)
```

### 5. Version Your Data

```python
ref = dm.store(
    data=model_weights,
    storage_type="s3",
    key=f"models/v{version}/weights.pkl",
    metadata={"version": version, "timestamp": now()}
)
```

## Troubleshooting

### Provider Not Available

```
StorageError: Provider 'postgresql' not registered
```

**Solution**: Register the provider:
```python
from praval.storage.providers import PostgreSQLProvider

provider = PostgreSQLProvider(...)
dm.register_provider("postgresql", provider)
```

### Connection Errors

```
ConnectionError: Could not connect to Redis
```

**Solution**: Check service is running and credentials:
```bash
# Test Redis
redis-cli ping

# Test PostgreSQL
psql -h localhost -U praval -d praval
```

### Serialization Errors

```
TypeError: Object of type 'datetime' is not JSON serializable
```

**Solution**: Convert non-serializable objects:
```python
from datetime import datetime
import json

data = {
    "timestamp": datetime.now().isoformat(),  # Convert to string
    "result": result
}
```

## See Also

- [Memory System Guide](memory-system.md) - Agent memory capabilities
- [API Reference](../api/index.rst) - Detailed API documentation
- [Examples](../examples/index.rst) - Storage usage examples
