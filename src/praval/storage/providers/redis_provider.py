"""
Redis storage provider for Praval framework

Provides key-value storage, caching, and pub/sub capabilities with
Redis backend.
"""

import json
import logging
from typing import Any, Dict, List, Optional, Union
from datetime import datetime, timedelta

try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None

from ..base_provider import BaseStorageProvider, StorageMetadata, StorageResult, StorageType, DataReference
from ..exceptions import StorageConnectionError, StorageConfigurationError

logger = logging.getLogger(__name__)


class RedisProvider(BaseStorageProvider):
    """
    Redis key-value storage provider with async support.
    
    Features:
    - Key-value operations (GET, SET, DEL)
    - Hash operations (HGET, HSET, HGETALL)
    - List operations (LPUSH, RPUSH, LRANGE)
    - Set operations (SADD, SMEMBERS)
    - Expiration and TTL management
    - Pub/Sub messaging
    - Lua script execution
    """
    
    def _create_metadata(self) -> StorageMetadata:
        return StorageMetadata(
            name=self.name,
            description="Redis key-value storage and cache provider",
            storage_type=StorageType.KEY_VALUE,
            supports_async=True,
            supports_transactions=True,
            supports_schemas=False,
            supports_indexing=False,
            supports_search=False,
            supports_streaming=True,
            max_connection_pool=20,
            default_timeout=5.0,
            required_config=["host"],
            optional_config=["port", "password", "database", "ssl", "pool_max_size"],
            connection_string_template="redis://:{password}@{host}:{port}/{database}"
        )
    
    def _initialize(self):
        """Initialize Redis-specific settings."""
        if not REDIS_AVAILABLE:
            raise ImportError("redis is required for Redis provider. Install with: pip install redis")
        
        # Set default values
        self.config.setdefault("port", 6379)
        self.config.setdefault("database", 0)
        self.config.setdefault("pool_max_size", 10)
        self.config.setdefault("ssl", False)
        
        self.redis_client: Optional[redis.Redis] = None
        self._connection_kwargs = self._build_connection_kwargs()
    
    def _build_connection_kwargs(self) -> Dict[str, Any]:
        """Build Redis connection parameters from config."""
        kwargs = {
            "host": self.config["host"],
            "port": self.config["port"],
            "db": self.config["database"],
            "decode_responses": True,
            "max_connections": self.config["pool_max_size"]
        }
        
        if "password" in self.config:
            kwargs["password"] = self.config["password"]
        
        if self.config.get("ssl"):
            kwargs["ssl"] = True
        
        return kwargs
    
    async def connect(self) -> bool:
        """Establish connection to Redis."""
        try:
            self.redis_client = redis.Redis(**self._connection_kwargs)
            
            # Test connection
            await self.redis_client.ping()
            
            self.is_connected = True
            logger.info(f"Connected to Redis: {self.config['host']}:{self.config['port']} db={self.config['database']}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise StorageConnectionError(self.name, str(e))
    
    async def disconnect(self):
        """Close Redis connection."""
        if self.redis_client:
            await self.redis_client.close()
            self.redis_client = None
            self.is_connected = False
            logger.info(f"Disconnected from Redis: {self.name}")
    
    async def store(self, resource: str, data: Any, **kwargs) -> StorageResult:
        """
        Store data in Redis.
        
        Args:
            resource: Redis key
            data: Data to store (will be JSON serialized if not string)
            **kwargs: Redis parameters (ex, px, nx, xx, etc.)
            
        Returns:
            StorageResult with operation outcome
        """
        if not self.is_connected:
            await self.connect()
        
        try:
            # Serialize data if needed
            if isinstance(data, (dict, list)):
                serialized_data = json.dumps(data)
            else:
                serialized_data = str(data)
            
            # Extract Redis-specific parameters
            ex = kwargs.get("ex")  # Expire in seconds
            px = kwargs.get("px")  # Expire in milliseconds
            nx = kwargs.get("nx", False)  # Only set if key doesn't exist
            xx = kwargs.get("xx", False)  # Only set if key exists
            
            # Store in Redis
            result = await self.redis_client.set(
                resource, serialized_data,
                ex=ex, px=px, nx=nx, xx=xx
            )
            
            if result:
                # Get TTL for metadata
                ttl = await self.redis_client.ttl(resource)
                
                return StorageResult(
                    success=True,
                    data={"key": resource, "stored": True},
                    metadata={
                        "operation": "set",
                        "ttl": ttl if ttl > 0 else None,
                        "size": len(serialized_data)
                    },
                    data_reference=DataReference(
                        provider=self.name,
                        storage_type=StorageType.KEY_VALUE,
                        resource_id=resource,
                        expires_at=datetime.now() + timedelta(seconds=ttl) if ttl > 0 else None
                    )
                )
            else:
                return StorageResult(
                    success=False,
                    error="Failed to store data (key may already exist with NX flag)"
                )
        
        except Exception as e:
            logger.error(f"Store operation failed: {e}")
            return StorageResult(
                success=False,
                error=f"Store operation failed: {str(e)}"
            )
    
    async def retrieve(self, resource: str, **kwargs) -> StorageResult:
        """
        Retrieve data from Redis.
        
        Args:
            resource: Redis key
            **kwargs: Additional parameters (decode_json, etc.)
            
        Returns:
            StorageResult with retrieved data
        """
        if not self.is_connected:
            await self.connect()
        
        try:
            value = await self.redis_client.get(resource)
            
            if value is None:
                return StorageResult(
                    success=False,
                    error=f"Key '{resource}' not found"
                )
            
            # Try to decode JSON if requested or if it looks like JSON
            decode_json = kwargs.get("decode_json", True)
            if decode_json and (value.startswith('{') or value.startswith('[')):
                try:
                    data = json.loads(value)
                except json.JSONDecodeError:
                    data = value
            else:
                data = value
            
            # Get TTL for metadata
            ttl = await self.redis_client.ttl(resource)
            
            return StorageResult(
                success=True,
                data=data,
                metadata={
                    "operation": "get",
                    "key": resource,
                    "ttl": ttl if ttl > 0 else None,
                    "size": len(value)
                }
            )
        
        except Exception as e:
            logger.error(f"Retrieve operation failed: {e}")
            return StorageResult(
                success=False,
                error=f"Retrieve operation failed: {str(e)}"
            )
    
    async def query(self, resource: str, query: Union[str, Dict], **kwargs) -> StorageResult:
        """
        Execute Redis operations or search queries.
        
        Args:
            resource: Pattern or specific key
            query: Query type or Redis command
            **kwargs: Query parameters
            
        Returns:
            StorageResult with query results
        """
        if not self.is_connected:
            await self.connect()
        
        try:
            if isinstance(query, str):
                if query == "keys":
                    # Pattern matching for keys
                    pattern = kwargs.get("pattern", resource)
                    keys = await self.redis_client.keys(pattern)
                    return StorageResult(
                        success=True,
                        data=keys,
                        metadata={"operation": "keys", "pattern": pattern, "count": len(keys)}
                    )
                
                elif query == "scan":
                    # Cursor-based scanning
                    cursor = kwargs.get("cursor", 0)
                    match = kwargs.get("match", resource)
                    count = kwargs.get("count", 10)
                    
                    cursor, keys = await self.redis_client.scan(cursor=cursor, match=match, count=count)
                    return StorageResult(
                        success=True,
                        data={"cursor": cursor, "keys": keys},
                        metadata={"operation": "scan", "pattern": match}
                    )
                
                elif query == "exists":
                    # Check if keys exist
                    keys = kwargs.get("keys", [resource])
                    count = await self.redis_client.exists(*keys)
                    return StorageResult(
                        success=True,
                        data={"exists_count": count, "keys": keys},
                        metadata={"operation": "exists"}
                    )
                
                elif query in ["hgetall", "hget", "hkeys", "hvals"]:
                    # Hash operations
                    return await self._execute_hash_operation(query, resource, **kwargs)
                
                elif query in ["lrange", "llen", "lindex"]:
                    # List operations
                    return await self._execute_list_operation(query, resource, **kwargs)
                
                elif query in ["smembers", "scard", "sismember"]:
                    # Set operations
                    return await self._execute_set_operation(query, resource, **kwargs)
                
                else:
                    raise ValueError(f"Unsupported query type: {query}")
            
            elif isinstance(query, dict):
                # Structured query
                operation = query.get("operation")
                if operation == "mget":
                    # Multi-get
                    keys = query.get("keys", [])
                    values = await self.redis_client.mget(keys)
                    result = dict(zip(keys, values))
                    return StorageResult(
                        success=True,
                        data=result,
                        metadata={"operation": "mget", "key_count": len(keys)}
                    )
                
                else:
                    raise ValueError(f"Unsupported structured operation: {operation}")
            
            else:
                raise ValueError(f"Unsupported query type: {type(query)}")
        
        except Exception as e:
            logger.error(f"Query operation failed: {e}")
            return StorageResult(
                success=False,
                error=f"Query operation failed: {str(e)}"
            )
    
    async def delete(self, resource: str, **kwargs) -> StorageResult:
        """
        Delete keys from Redis.
        
        Args:
            resource: Key or pattern to delete
            **kwargs: Delete parameters
            
        Returns:
            StorageResult with operation outcome
        """
        if not self.is_connected:
            await self.connect()
        
        try:
            if kwargs.get("pattern_delete", False):
                # Delete keys matching pattern
                keys = await self.redis_client.keys(resource)
                if keys:
                    deleted_count = await self.redis_client.delete(*keys)
                else:
                    deleted_count = 0
            else:
                # Delete specific key
                deleted_count = await self.redis_client.delete(resource)
            
            return StorageResult(
                success=True,
                data={"deleted": deleted_count},
                metadata={"operation": "delete", "key": resource}
            )
        
        except Exception as e:
            logger.error(f"Delete operation failed: {e}")
            return StorageResult(
                success=False,
                error=f"Delete operation failed: {str(e)}"
            )
    
    async def _execute_hash_operation(self, operation: str, key: str, **kwargs) -> StorageResult:
        """Execute Redis hash operations."""
        if operation == "hgetall":
            data = await self.redis_client.hgetall(key)
            return StorageResult(
                success=True,
                data=data,
                metadata={"operation": "hgetall", "field_count": len(data)}
            )
        
        elif operation == "hget":
            field = kwargs.get("field")
            if not field:
                raise ValueError("Field required for HGET operation")
            
            value = await self.redis_client.hget(key, field)
            return StorageResult(
                success=True,
                data={field: value},
                metadata={"operation": "hget", "field": field}
            )
        
        elif operation == "hkeys":
            keys = await self.redis_client.hkeys(key)
            return StorageResult(
                success=True,
                data=keys,
                metadata={"operation": "hkeys", "key_count": len(keys)}
            )
        
        elif operation == "hvals":
            values = await self.redis_client.hvals(key)
            return StorageResult(
                success=True,
                data=values,
                metadata={"operation": "hvals", "value_count": len(values)}
            )
    
    async def _execute_list_operation(self, operation: str, key: str, **kwargs) -> StorageResult:
        """Execute Redis list operations."""
        if operation == "lrange":
            start = kwargs.get("start", 0)
            end = kwargs.get("end", -1)
            
            items = await self.redis_client.lrange(key, start, end)
            return StorageResult(
                success=True,
                data=items,
                metadata={"operation": "lrange", "start": start, "end": end, "count": len(items)}
            )
        
        elif operation == "llen":
            length = await self.redis_client.llen(key)
            return StorageResult(
                success=True,
                data={"length": length},
                metadata={"operation": "llen"}
            )
        
        elif operation == "lindex":
            index = kwargs.get("index", 0)
            value = await self.redis_client.lindex(key, index)
            return StorageResult(
                success=True,
                data={"value": value},
                metadata={"operation": "lindex", "index": index}
            )
    
    async def _execute_set_operation(self, operation: str, key: str, **kwargs) -> StorageResult:
        """Execute Redis set operations."""
        if operation == "smembers":
            members = await self.redis_client.smembers(key)
            return StorageResult(
                success=True,
                data=list(members),
                metadata={"operation": "smembers", "member_count": len(members)}
            )
        
        elif operation == "scard":
            count = await self.redis_client.scard(key)
            return StorageResult(
                success=True,
                data={"count": count},
                metadata={"operation": "scard"}
            )
        
        elif operation == "sismember":
            member = kwargs.get("member")
            if not member:
                raise ValueError("Member required for SISMEMBER operation")
            
            is_member = await self.redis_client.sismember(key, member)
            return StorageResult(
                success=True,
                data={"is_member": is_member},
                metadata={"operation": "sismember", "member": member}
            )
    
    async def list_resources(self, prefix: str = "", **kwargs) -> StorageResult:
        """List keys in Redis."""
        if not self.is_connected:
            await self.connect()
        
        try:
            pattern = f"{prefix}*" if prefix else "*"
            keys = await self.redis_client.keys(pattern)
            
            return StorageResult(
                success=True,
                data=keys,
                metadata={"operation": "list_keys", "pattern": pattern, "count": len(keys)}
            )
        
        except Exception as e:
            logger.error(f"List resources failed: {e}")
            return StorageResult(
                success=False,
                error=f"List resources failed: {str(e)}"
            )