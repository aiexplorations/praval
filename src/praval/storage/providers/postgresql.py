"""
PostgreSQL storage provider for Praval framework

Provides relational database capabilities with SQL query support,
transactions, and schema management.
"""

import json
import logging
from typing import Any, Dict, List, Optional, Union
from datetime import datetime

try:
    import asyncpg
    import asyncpg.pool
    ASYNCPG_AVAILABLE = True
except ImportError:
    ASYNCPG_AVAILABLE = False
    asyncpg = None

from ..base_provider import BaseStorageProvider, StorageMetadata, StorageResult, StorageType, DataReference
from ..exceptions import StorageConnectionError, StorageConfigurationError

logger = logging.getLogger(__name__)


class PostgreSQLProvider(BaseStorageProvider):
    """
    PostgreSQL storage provider with async connection pooling.
    
    Features:
    - Async connection pooling
    - SQL query execution
    - Transaction support
    - Schema management
    - JSON column support
    - Full-text search capabilities
    """
    
    def _create_metadata(self) -> StorageMetadata:
        return StorageMetadata(
            name=self.name,
            description="PostgreSQL relational database provider",
            storage_type=StorageType.RELATIONAL,
            supports_async=True,
            supports_transactions=True,
            supports_schemas=True,
            supports_indexing=True,
            supports_search=True,
            max_connection_pool=20,
            default_timeout=30.0,
            required_config=["host", "database", "user", "password"],
            optional_config=["port", "ssl", "pool_min_size", "pool_max_size"],
            connection_string_template="postgresql://{user}:{password}@{host}:{port}/{database}"
        )
    
    def _initialize(self):
        """Initialize PostgreSQL-specific settings."""
        if not ASYNCPG_AVAILABLE:
            raise ImportError("asyncpg is required for PostgreSQL provider. Install with: pip install asyncpg")
        
        # Set default values
        self.config.setdefault("port", 5432)
        self.config.setdefault("pool_min_size", 1)
        self.config.setdefault("pool_max_size", 10)
        self.config.setdefault("ssl", False)
        
        self.connection_pool: Optional[asyncpg.pool.Pool] = None
        self._connection_string = self._build_connection_string()
    
    def _build_connection_string(self) -> str:
        """Build PostgreSQL connection string from config."""
        return (
            f"postgresql://{self.config['user']}:{self.config['password']}"
            f"@{self.config['host']}:{self.config['port']}/{self.config['database']}"
        )
    
    async def connect(self) -> bool:
        """Establish connection pool to PostgreSQL."""
        try:
            self.connection_pool = await asyncpg.create_pool(
                self._connection_string,
                min_size=self.config["pool_min_size"],
                max_size=self.config["pool_max_size"],
                command_timeout=self.metadata.default_timeout
            )
            
            # Test connection
            async with self.connection_pool.acquire() as conn:
                await conn.execute("SELECT 1")
            
            self.is_connected = True
            logger.info(f"Connected to PostgreSQL: {self.config['host']}:{self.config['port']}/{self.config['database']}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to PostgreSQL: {e}")
            raise StorageConnectionError(self.name, str(e))
    
    async def disconnect(self):
        """Close connection pool."""
        if self.connection_pool:
            await self.connection_pool.close()
            self.connection_pool = None
            self.is_connected = False
            logger.info(f"Disconnected from PostgreSQL: {self.name}")
    
    async def store(self, resource: str, data: Any, **kwargs) -> StorageResult:
        """
        Store data in PostgreSQL table.
        
        Args:
            resource: Table name
            data: Data to store (dict or list of dicts)
            **kwargs: Additional parameters (upsert, returning, etc.)
            
        Returns:
            StorageResult with operation outcome
        """
        if not self.is_connected:
            await self.connect()
        
        try:
            async with self.connection_pool.acquire() as conn:
                if isinstance(data, dict):
                    # Single record insert
                    columns = list(data.keys())
                    values = list(data.values())
                    placeholders = [f"${i+1}" for i in range(len(values))]
                    
                    query = f"INSERT INTO {resource} ({', '.join(columns)}) VALUES ({', '.join(placeholders)})"
                    
                    if kwargs.get("returning"):
                        query += f" RETURNING {kwargs['returning']}"
                    
                    if kwargs.get("returning"):
                        result = await conn.fetchrow(query, *values)
                        return StorageResult(
                            success=True,
                            data=dict(result) if result else None,
                            metadata={"operation": "insert", "table": resource}
                        )
                    else:
                        await conn.execute(query, *values)
                        return StorageResult(
                            success=True,
                            data={"inserted": 1},
                            metadata={"operation": "insert", "table": resource}
                        )
                
                elif isinstance(data, list):
                    # Bulk insert
                    if not data:
                        return StorageResult(success=True, data={"inserted": 0})
                    
                    columns = list(data[0].keys())
                    placeholders = [f"${i+1}" for i in range(len(columns))]
                    query = f"INSERT INTO {resource} ({', '.join(columns)}) VALUES ({', '.join(placeholders)})"
                    
                    values_list = [[row[col] for col in columns] for row in data]
                    await conn.executemany(query, values_list)
                    
                    return StorageResult(
                        success=True,
                        data={"inserted": len(data)},
                        metadata={"operation": "bulk_insert", "table": resource}
                    )
                
                else:
                    raise ValueError(f"Unsupported data type for storage: {type(data)}")
        
        except Exception as e:
            logger.error(f"Store operation failed: {e}")
            return StorageResult(
                success=False,
                error=f"Store operation failed: {str(e)}"
            )
    
    async def retrieve(self, resource: str, **kwargs) -> StorageResult:
        """
        Retrieve data from PostgreSQL table.
        
        Args:
            resource: Table name
            **kwargs: Query parameters (where, limit, offset, order_by, etc.)
            
        Returns:
            StorageResult with retrieved data
        """
        if not self.is_connected:
            await self.connect()
        
        try:
            async with self.connection_pool.acquire() as conn:
                query = f"SELECT * FROM {resource}"
                params = []
                
                # Build WHERE clause
                if "where" in kwargs:
                    where_clause, where_params = self._build_where_clause(kwargs["where"])
                    query += f" WHERE {where_clause}"
                    params.extend(where_params)
                
                # Add ORDER BY
                if "order_by" in kwargs:
                    query += f" ORDER BY {kwargs['order_by']}"
                
                # Add LIMIT and OFFSET
                if "limit" in kwargs:
                    query += f" LIMIT {kwargs['limit']}"
                
                if "offset" in kwargs:
                    query += f" OFFSET {kwargs['offset']}"
                
                rows = await conn.fetch(query, *params)
                data = [dict(row) for row in rows]
                
                return StorageResult(
                    success=True,
                    data=data,
                    metadata={
                        "operation": "select",
                        "table": resource,
                        "count": len(data)
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
        Execute SQL query against PostgreSQL.
        
        Args:
            resource: Table name (ignored for raw SQL)
            query: SQL query string or structured query dict
            **kwargs: Query parameters
            
        Returns:
            StorageResult with query results
        """
        if not self.is_connected:
            await self.connect()
        
        try:
            async with self.connection_pool.acquire() as conn:
                if isinstance(query, str):
                    # Raw SQL query
                    params = kwargs.get("params", [])
                    
                    if query.strip().upper().startswith("SELECT"):
                        rows = await conn.fetch(query, *params)
                        data = [dict(row) for row in rows]
                    else:
                        # Non-SELECT query
                        result = await conn.execute(query, *params)
                        data = {"result": result, "status": "executed"}
                    
                    return StorageResult(
                        success=True,
                        data=data,
                        metadata={"operation": "raw_query", "query_type": "sql"}
                    )
                
                elif isinstance(query, dict):
                    # Structured query
                    return await self._execute_structured_query(conn, resource, query, **kwargs)
                
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
        Delete data from PostgreSQL table.
        
        Args:
            resource: Table name
            **kwargs: Delete parameters (where clause required)
            
        Returns:
            StorageResult with operation outcome
        """
        if not self.is_connected:
            await self.connect()
        
        try:
            async with self.connection_pool.acquire() as conn:
                if "where" not in kwargs:
                    raise ValueError("WHERE clause is required for delete operations")
                
                where_clause, params = self._build_where_clause(kwargs["where"])
                query = f"DELETE FROM {resource} WHERE {where_clause}"
                
                result = await conn.execute(query, *params)
                deleted_count = int(result.split()[-1])  # Extract count from "DELETE n"
                
                return StorageResult(
                    success=True,
                    data={"deleted": deleted_count},
                    metadata={"operation": "delete", "table": resource}
                )
        
        except Exception as e:
            logger.error(f"Delete operation failed: {e}")
            return StorageResult(
                success=False,
                error=f"Delete operation failed: {str(e)}"
            )
    
    def _build_where_clause(self, where_dict: Dict[str, Any]) -> tuple[str, List[Any]]:
        """Build WHERE clause from dictionary."""
        conditions = []
        params = []
        param_index = 1
        
        for key, value in where_dict.items():
            if isinstance(value, dict):
                # Handle operators like {"age": {"$gt": 25}}
                for op, val in value.items():
                    if op == "$gt":
                        conditions.append(f"{key} > ${param_index}")
                    elif op == "$lt":
                        conditions.append(f"{key} < ${param_index}")
                    elif op == "$gte":
                        conditions.append(f"{key} >= ${param_index}")
                    elif op == "$lte":
                        conditions.append(f"{key} <= ${param_index}")
                    elif op == "$ne":
                        conditions.append(f"{key} != ${param_index}")
                    elif op == "$in":
                        placeholders = [f"${param_index + i}" for i in range(len(val))]
                        conditions.append(f"{key} IN ({', '.join(placeholders)})")
                        params.extend(val)
                        param_index += len(val) - 1
                        continue
                    else:
                        raise ValueError(f"Unsupported operator: {op}")
                    
                    params.append(val)
                    param_index += 1
            else:
                # Simple equality
                conditions.append(f"{key} = ${param_index}")
                params.append(value)
                param_index += 1
        
        return " AND ".join(conditions), params
    
    async def _execute_structured_query(self, conn, resource: str, query_dict: Dict, **kwargs) -> StorageResult:
        """Execute structured query dictionary."""
        operation = query_dict.get("operation", "select")
        
        if operation == "select":
            fields = query_dict.get("fields", "*")
            if isinstance(fields, list):
                fields = ", ".join(fields)
            
            sql = f"SELECT {fields} FROM {resource}"
            params = []
            
            if "where" in query_dict:
                where_clause, where_params = self._build_where_clause(query_dict["where"])
                sql += f" WHERE {where_clause}"
                params.extend(where_params)
            
            if "order_by" in query_dict:
                sql += f" ORDER BY {query_dict['order_by']}"
            
            if "limit" in query_dict:
                sql += f" LIMIT {query_dict['limit']}"
            
            rows = await conn.fetch(sql, *params)
            data = [dict(row) for row in rows]
            
            return StorageResult(
                success=True,
                data=data,
                metadata={"operation": "structured_select", "count": len(data)}
            )
        
        else:
            raise ValueError(f"Unsupported structured operation: {operation}")
    
    async def list_resources(self, prefix: str = "", **kwargs) -> StorageResult:
        """List tables in the database."""
        if not self.is_connected:
            await self.connect()
        
        try:
            async with self.connection_pool.acquire() as conn:
                query = """
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public'
                """
                
                if prefix:
                    query += f" AND table_name LIKE '{prefix}%'"
                
                query += " ORDER BY table_name"
                
                rows = await conn.fetch(query)
                tables = [row["table_name"] for row in rows]
                
                return StorageResult(
                    success=True,
                    data=tables,
                    metadata={"operation": "list_tables", "count": len(tables)}
                )
        
        except Exception as e:
            logger.error(f"List resources failed: {e}")
            return StorageResult(
                success=False,
                error=f"List resources failed: {str(e)}"
            )