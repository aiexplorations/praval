"""
Qdrant vector storage provider for Praval framework

Integrates with existing Praval memory system to provide vector storage
capabilities through the storage framework.
"""

import logging
import uuid
from typing import Any, Dict, Optional, Union

try:
    from qdrant_client import QdrantClient
    from qdrant_client.http import models
    from qdrant_client.http.models import Distance, PointStruct, VectorParams

    QDRANT_AVAILABLE = True
except ImportError:
    QDRANT_AVAILABLE = False
    QdrantClient = None
    models = None
    Distance = None
    VectorParams = None
    PointStruct = None

from ..base_provider import (
    BaseStorageProvider,
    DataReference,
    StorageMetadata,
    StorageResult,
    StorageType,
)
from ..exceptions import StorageConnectionError

logger = logging.getLogger(__name__)


class QdrantProvider(BaseStorageProvider):
    """
    Qdrant vector database storage provider.

    Features:
    - Vector similarity search
    - Collection management
    - Point insertion and retrieval
    - Filtering and metadata search
    - Batch operations
    - Integration with Praval memory system
    """

    def _create_metadata(self) -> StorageMetadata:
        return StorageMetadata(
            name=self.name,
            description="Qdrant vector database storage provider",
            storage_type=StorageType.VECTOR,
            supports_async=True,
            supports_transactions=False,
            supports_schemas=True,  # Collections are like schemas
            supports_indexing=True,
            supports_search=True,
            supports_streaming=False,
            default_timeout=30.0,
            required_config=["url"],
            optional_config=[
                "collection_name",
                "vector_size",
                "distance_metric",
                "api_key",
                "timeout",
                "prefer_grpc",
            ],
            connection_string_template="qdrant://{url}/{collection_name}",
        )

    def _initialize(self):
        """Initialize Qdrant-specific settings."""
        if not QDRANT_AVAILABLE:
            raise ImportError(
                (
                    "qdrant-client is required for Qdrant provider. Install wit"
                    "h: pip install qdrant-client"
                )
            )

        # Set default values
        self.config.setdefault("collection_name", "praval_storage")
        self.config.setdefault("vector_size", 1536)  # OpenAI embedding size
        self.config.setdefault("distance_metric", "cosine")
        self.config.setdefault("timeout", 30.0)
        self.config.setdefault("prefer_grpc", False)

        self.qdrant_client: Optional[QdrantClient] = None
        self.default_collection = self.config["collection_name"]

    async def connect(self) -> bool:
        """Establish connection to Qdrant."""
        try:
            client_kwargs = {
                "url": self.config["url"],
                "timeout": self.config["timeout"],
                "prefer_grpc": self.config["prefer_grpc"],
            }

            if "api_key" in self.config:
                client_kwargs["api_key"] = self.config["api_key"]

            self.qdrant_client = QdrantClient(**client_kwargs)

            # Test connection
            _ = self.qdrant_client.get_collections()

            # Ensure default collection exists
            await self._ensure_collection_exists(self.default_collection)

            self.is_connected = True
            logger.info(f"Connected to Qdrant: {self.config['url']}")
            return True

        except Exception as e:
            logger.error(f"Failed to connect to Qdrant: {e}")
            raise StorageConnectionError(self.name, str(e))

    async def disconnect(self):
        """Close Qdrant connection."""
        if self.qdrant_client:
            self.qdrant_client.close()
            self.qdrant_client = None
            self.is_connected = False
            logger.info(f"Disconnected from Qdrant: {self.name}")

    async def _ensure_collection_exists(self, collection_name: str):
        """Ensure collection exists, create if not."""
        try:
            _ = self.qdrant_client.get_collection(collection_name)
            logger.debug(f"Collection '{collection_name}' exists")
        except Exception:
            # Collection doesn't exist, create it
            self.qdrant_client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(
                    size=self.config["vector_size"],
                    distance=(
                        Distance.COSINE
                        if self.config["distance_metric"] == "cosine"
                        else Distance.EUCLIDEAN
                    ),
                ),
            )
            logger.info(f"Created Qdrant collection: {collection_name}")

    async def store(self, resource: str, data: Any, **kwargs) -> StorageResult:
        """
        Store vector data in Qdrant.

        Args:
            resource: Collection name (optional, uses default if not specified)
            data: Data to store. Accepts a single point dictionary, a list of
                point dictionaries, or a vector list. Point dictionaries may
                include ``id``, ``vector``, and ``payload`` keys.
            **kwargs: Additional parameters

        Returns:
            StorageResult with operation outcome
        """
        if not self.is_connected:
            await self.connect()

        try:
            collection_name = resource or self.default_collection
            await self._ensure_collection_exists(collection_name)

            points = []

            if isinstance(data, dict):
                # Single point
                if "vector" in data:
                    point_id = data.get("id", str(uuid.uuid4()))
                    payload = dict(data.get("payload", {}) or {})
                    payload["_praval_point_id"] = str(point_id)
                    points.append(
                        PointStruct(
                            id=self._to_qdrant_point_id(collection_name, point_id),
                            vector=data["vector"],
                            payload=payload,
                        )
                    )
                else:
                    raise ValueError("Dictionary must contain 'vector' field")

            elif isinstance(data, list):
                if len(data) > 0 and isinstance(data[0], dict):
                    # Multiple points
                    for item in data:
                        if "vector" not in item:
                            raise ValueError("Each point must contain 'vector' field")

                        point_id = item.get("id", str(uuid.uuid4()))
                        payload = dict(item.get("payload", {}) or {})
                        payload["_praval_point_id"] = str(point_id)
                        points.append(
                            PointStruct(
                                id=self._to_qdrant_point_id(collection_name, point_id),
                                vector=item["vector"],
                                payload=payload,
                            )
                        )

                elif len(data) > 0 and isinstance(data[0], (int, float)):
                    # Single vector array
                    point_id = kwargs.get("id", str(uuid.uuid4()))
                    payload = dict(kwargs.get("payload", {}) or {})
                    payload["_praval_point_id"] = str(point_id)
                    points.append(
                        PointStruct(
                            id=self._to_qdrant_point_id(collection_name, point_id),
                            vector=data,
                            payload=payload,
                        )
                    )

                else:
                    raise ValueError("Invalid data format for vector storage")

            else:
                raise ValueError(f"Unsupported data type: {type(data)}")

            # Store points in Qdrant
            operation_info = self.qdrant_client.upsert(
                collection_name=collection_name, points=points
            )
            resource_id = collection_name
            if len(points) == 1:
                original_point_id = self._from_qdrant_point(
                    points[0].id,
                    points[0].payload,
                )
                resource_id = f"{collection_name}:{original_point_id}"

            return StorageResult(
                success=True,
                data={
                    "collection": collection_name,
                    "points_stored": len(points),
                    "operation_id": (
                        operation_info.operation_id
                        if hasattr(operation_info, "operation_id")
                        else None
                    ),
                },
                metadata={
                    "operation": "upsert_points",
                    "collection": collection_name,
                    "point_count": len(points),
                },
                data_reference=DataReference(
                    provider=self.name,
                    storage_type=StorageType.VECTOR,
                    resource_id=resource_id,
                    metadata={
                        "collection": collection_name,
                        "point_count": len(points),
                    },
                ),
            )

        except Exception as e:
            logger.error(f"Store operation failed: {e}")
            return StorageResult(
                success=False, error=f"Store operation failed: {str(e)}"
            )

    async def retrieve(self, resource: str, **kwargs) -> StorageResult:
        """
        Retrieve vectors from Qdrant.

        Args:
            resource: Collection name or "collection:point_id"
            **kwargs: Retrieval parameters (point_ids, with_vectors, with_payload)

        Returns:
            StorageResult with retrieved data
        """
        if not self.is_connected:
            await self.connect()

        try:
            # Parse resource
            if ":" in resource:
                collection_name, point_id = resource.split(":", 1)
                point_ids = [point_id]
            else:
                collection_name = resource
                point_ids = kwargs.get("point_ids", kwargs.get("ids", []))

            if not point_ids:
                raise ValueError("Point IDs required for retrieval")

            # Retrieve points
            points = self.qdrant_client.retrieve(
                collection_name=collection_name,
                ids=[
                    self._to_qdrant_point_id(collection_name, point_id)
                    for point_id in point_ids
                ],
                with_vectors=kwargs.get("with_vectors", True),
                with_payload=kwargs.get("with_payload", True),
            )

            # Format results
            results = []
            for point in points:
                result = self._point_to_result(point)
                if point.vector is not None:
                    result["vector"] = point.vector
                results.append(result)

            return StorageResult(
                success=True,
                data=results if len(results) > 1 else (results[0] if results else None),
                metadata={
                    "operation": "retrieve_points",
                    "collection": collection_name,
                    "point_count": len(results),
                },
            )

        except Exception as e:
            logger.error(f"Retrieve operation failed: {e}")
            return StorageResult(
                success=False, error=f"Retrieve operation failed: {str(e)}"
            )

    async def query(
        self, resource: str, query: Union[str, Dict], **kwargs
    ) -> StorageResult:
        """
        Execute vector search or other operations.

        Args:
            resource: Collection name
            query: Query type or search vector
            **kwargs: Query parameters

        Returns:
            StorageResult with query results
        """
        if not self.is_connected:
            await self.connect()

        try:
            collection_name = resource or self.default_collection

            if isinstance(query, str):
                if query == "search":
                    # Vector similarity search
                    query_vector = kwargs.get("vector")
                    if not query_vector:
                        raise ValueError("Search vector required")

                    limit = kwargs.get("limit", 10)
                    score_threshold = kwargs.get("score_threshold")
                    query_filter = kwargs.get("filter")

                    search_params = {
                        "collection_name": collection_name,
                        "query_vector": query_vector,
                        "limit": limit,
                        "with_vectors": kwargs.get("with_vectors", False),
                        "with_payload": kwargs.get("with_payload", True),
                    }

                    if score_threshold is not None:
                        search_params["score_threshold"] = score_threshold

                    if query_filter:
                        search_params["query_filter"] = query_filter

                    search_results = self._search_points(**search_params)

                    results = []
                    for result in search_results:
                        item = self._point_to_result(result)
                        item["score"] = result.score
                        if result.vector is not None:
                            item["vector"] = result.vector
                        results.append(item)

                    return StorageResult(
                        success=True,
                        data=results,
                        metadata={
                            "operation": "vector_search",
                            "collection": collection_name,
                            "result_count": len(results),
                            "limit": limit,
                        },
                    )

                elif query == "count":
                    # Count points in collection
                    count_result = self.qdrant_client.count(
                        collection_name=collection_name,
                        count_filter=kwargs.get("filter"),
                    )

                    return StorageResult(
                        success=True,
                        data={"count": count_result.count},
                        metadata={
                            "operation": "count_points",
                            "collection": collection_name,
                        },
                    )

                elif query == "scroll":
                    # Scroll through points
                    scroll_result = self.qdrant_client.scroll(
                        collection_name=collection_name,
                        scroll_filter=kwargs.get("filter"),
                        limit=kwargs.get("limit", 10),
                        offset=kwargs.get("offset"),
                        with_vectors=kwargs.get("with_vectors", False),
                        with_payload=kwargs.get("with_payload", True),
                    )

                    points, next_offset = scroll_result

                    results = []
                    for point in points:
                        item = {"id": point.id, "payload": point.payload or {}}
                        if point.vector is not None:
                            item["vector"] = point.vector
                        results.append(item)

                    return StorageResult(
                        success=True,
                        data={"points": results, "next_offset": next_offset},
                        metadata={
                            "operation": "scroll_points",
                            "collection": collection_name,
                            "point_count": len(results),
                        },
                    )

                else:
                    raise ValueError(f"Unsupported query type: {query}")

            elif isinstance(query, list) and all(
                isinstance(x, (int, float)) for x in query
            ):
                # Direct vector search
                search_results = self._search_points(
                    collection_name=collection_name,
                    query_vector=query,
                    limit=kwargs.get("limit", 10),
                    with_vectors=kwargs.get("with_vectors", False),
                    with_payload=kwargs.get("with_payload", True),
                )

                results = []
                for result in search_results:
                    item = self._point_to_result(result)
                    item["score"] = result.score
                    if result.vector is not None:
                        item["vector"] = result.vector
                    results.append(item)

                return StorageResult(
                    success=True,
                    data=results,
                    metadata={
                        "operation": "vector_search",
                        "collection": collection_name,
                        "result_count": len(results),
                    },
                )

            else:
                raise ValueError(f"Unsupported query format: {type(query)}")

        except Exception as e:
            logger.error(f"Query operation failed: {e}")
            return StorageResult(
                success=False, error=f"Query operation failed: {str(e)}"
            )

    async def delete(self, resource: str, **kwargs) -> StorageResult:
        """
        Delete points from Qdrant.

        Args:
            resource: Collection name or "collection:point_id"
            **kwargs: Delete parameters (point_ids, filter)

        Returns:
            StorageResult with operation outcome
        """
        if not self.is_connected:
            await self.connect()

        try:
            # Parse resource
            if ":" in resource:
                collection_name, point_id = resource.split(":", 1)
                point_ids = [point_id]
            else:
                collection_name = resource
                point_ids = kwargs.get("point_ids", kwargs.get("ids", []))

            if point_ids:
                # Delete specific points
                _ = self.qdrant_client.delete(
                    collection_name=collection_name,
                    points_selector=models.PointIdsList(
                        points=[
                            self._to_qdrant_point_id(collection_name, point_id)
                            for point_id in point_ids
                        ]
                    ),
                )

                return StorageResult(
                    success=True,
                    data={"deleted": len(point_ids)},
                    metadata={
                        "operation": "delete_points",
                        "collection": collection_name,
                        "point_ids": point_ids,
                    },
                )

            elif "filter" in kwargs:
                # Delete points matching filter
                _ = self.qdrant_client.delete(
                    collection_name=collection_name,
                    points_selector=models.FilterSelector(filter=kwargs["filter"]),
                )

                return StorageResult(
                    success=True,
                    data={"deleted": "filtered"},
                    metadata={
                        "operation": "delete_filtered",
                        "collection": collection_name,
                    },
                )

            else:
                raise ValueError(
                    "Either point_ids or filter must be specified for deletion"
                )

        except Exception as e:
            logger.error(f"Delete operation failed: {e}")
            return StorageResult(
                success=False, error=f"Delete operation failed: {str(e)}"
            )

    async def list_resources(self, prefix: str = "", **kwargs) -> StorageResult:
        """List collections in Qdrant."""
        if not self.is_connected:
            await self.connect()

        try:
            collections_response = self.qdrant_client.get_collections()

            collections = []
            for collection in collections_response.collections:
                if not prefix or collection.name.startswith(prefix):
                    collection_info = self.qdrant_client.get_collection(collection.name)
                    collections.append(
                        {
                            "name": collection.name,
                            "points_count": getattr(
                                collection_info,
                                "points_count",
                                getattr(collection, "points_count", 0),
                            ),
                            "segments_count": getattr(
                                collection_info,
                                "segments_count",
                                getattr(collection, "segments_count", 0),
                            ),
                            "status": self._normalize_status(
                                getattr(
                                    collection_info,
                                    "status",
                                    getattr(collection, "status", "unknown"),
                                )
                            ),
                        }
                    )

            return StorageResult(
                success=True,
                data=collections,
                metadata={"operation": "list_collections", "count": len(collections)},
            )

        except Exception as e:
            logger.error(f"List resources failed: {e}")
            return StorageResult(
                success=False, error=f"List resources failed: {str(e)}"
            )

    def _to_qdrant_point_id(self, collection_name: str, point_id: Any) -> Any:
        """Convert Praval's public point IDs to Qdrant-compatible IDs."""
        if isinstance(point_id, int):
            return point_id
        if isinstance(point_id, uuid.UUID):
            return str(point_id)

        point_id_str = str(point_id)
        try:
            return str(uuid.UUID(point_id_str))
        except ValueError:
            return str(
                uuid.uuid5(
                    uuid.NAMESPACE_URL,
                    f"praval:{self.name}:{collection_name}:{point_id_str}",
                )
            )

    def _from_qdrant_point(
        self, point_id: Any, payload: Optional[Dict[str, Any]]
    ) -> str:
        if payload and "_praval_point_id" in payload:
            return str(payload["_praval_point_id"])
        return str(point_id)

    def _point_to_result(self, point: Any) -> Dict[str, Any]:
        payload = dict(point.payload or {})
        original_id = self._from_qdrant_point(point.id, payload)
        payload.pop("_praval_point_id", None)
        return {"id": original_id, "payload": payload}

    def _search_points(self, **search_params: Any) -> Any:
        """Run vector search across old and new qdrant-client APIs."""
        if hasattr(self.qdrant_client, "search"):
            return self.qdrant_client.search(**search_params)

        response = self.qdrant_client.query_points(
            collection_name=search_params["collection_name"],
            query=search_params["query_vector"],
            query_filter=search_params.get("query_filter"),
            limit=search_params.get("limit", 10),
            with_vectors=search_params.get("with_vectors", False),
            with_payload=search_params.get("with_payload", True),
            score_threshold=search_params.get("score_threshold"),
        )
        return getattr(response, "points", response)

    def _normalize_status(self, status: Any) -> str:
        return str(getattr(status, "value", status))
