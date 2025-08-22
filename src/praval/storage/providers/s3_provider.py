"""
S3 object storage provider for Praval framework

Provides object storage capabilities with S3-compatible backends
including AWS S3, MinIO, and other S3-compatible services.
"""

import json
import logging
from typing import Any, Dict, List, Optional, Union, BinaryIO
from datetime import datetime, timedelta
from urllib.parse import urlparse
import io

try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False
    boto3 = None
    ClientError = Exception
    NoCredentialsError = Exception

from ..base_provider import BaseStorageProvider, StorageMetadata, StorageResult, StorageType, DataReference
from ..exceptions import StorageConnectionError, StorageConfigurationError

logger = logging.getLogger(__name__)


class S3Provider(BaseStorageProvider):
    """
    S3-compatible object storage provider.
    
    Features:
    - Object upload, download, and deletion
    - Bucket management
    - Presigned URLs for secure access
    - Metadata and tagging support
    - Multipart uploads for large files
    - Lifecycle management
    - Cross-region replication support
    """
    
    def _create_metadata(self) -> StorageMetadata:
        return StorageMetadata(
            name=self.name,
            description="S3-compatible object storage provider",
            storage_type=StorageType.OBJECT,
            supports_async=False,  # boto3 doesn't support async natively
            supports_transactions=False,
            supports_schemas=False,
            supports_indexing=False,
            supports_search=False,
            supports_streaming=True,
            default_timeout=60.0,
            required_config=["bucket_name"],
            optional_config=[
                "aws_access_key_id", "aws_secret_access_key", "region_name",
                "endpoint_url", "use_ssl", "signature_version"
            ],
            connection_string_template="s3://{bucket_name}"
        )
    
    def _initialize(self):
        """Initialize S3-specific settings."""
        if not BOTO3_AVAILABLE:
            raise ImportError("boto3 is required for S3 provider. Install with: pip install boto3")
        
        # Set default values
        self.config.setdefault("region_name", "us-east-1")
        self.config.setdefault("use_ssl", True)
        self.config.setdefault("signature_version", "s3v4")
        
        self.s3_client = None
        self.bucket_name = self.config["bucket_name"]
        self._client_kwargs = self._build_client_kwargs()
    
    def _build_client_kwargs(self) -> Dict[str, Any]:
        """Build S3 client parameters from config."""
        kwargs = {
            "service_name": "s3",
            "region_name": self.config["region_name"],
            "use_ssl": self.config["use_ssl"],
            "config": boto3.session.Config(
                signature_version=self.config["signature_version"]
            )
        }
        
        # Add credentials if provided
        if "aws_access_key_id" in self.config:
            kwargs["aws_access_key_id"] = self.config["aws_access_key_id"]
        
        if "aws_secret_access_key" in self.config:
            kwargs["aws_secret_access_key"] = self.config["aws_secret_access_key"]
        
        # Add endpoint URL for S3-compatible services (like MinIO)
        if "endpoint_url" in self.config:
            kwargs["endpoint_url"] = self.config["endpoint_url"]
        
        return kwargs
    
    async def connect(self) -> bool:
        """Establish connection to S3."""
        try:
            self.s3_client = boto3.client(**self._client_kwargs)
            
            # Test connection by checking if bucket exists
            try:
                self.s3_client.head_bucket(Bucket=self.bucket_name)
            except ClientError as e:
                error_code = int(e.response['Error']['Code'])
                if error_code == 404:
                    # Bucket doesn't exist, try to create it if allowed
                    if self.config.get("create_bucket", False):
                        self.s3_client.create_bucket(Bucket=self.bucket_name)
                        logger.info(f"Created S3 bucket: {self.bucket_name}")
                    else:
                        raise StorageConnectionError(
                            self.name,
                            f"Bucket '{self.bucket_name}' does not exist and create_bucket is disabled"
                        )
                else:
                    raise
            
            self.is_connected = True
            logger.info(f"Connected to S3 bucket: {self.bucket_name}")
            return True
            
        except NoCredentialsError:
            logger.error("AWS credentials not found")
            raise StorageConnectionError(self.name, "AWS credentials not found")
        except Exception as e:
            logger.error(f"Failed to connect to S3: {e}")
            raise StorageConnectionError(self.name, str(e))
    
    async def disconnect(self):
        """Close S3 connection."""
        if self.s3_client:
            # boto3 client doesn't need explicit closing
            self.s3_client = None
            self.is_connected = False
            logger.info(f"Disconnected from S3: {self.name}")
    
    async def store(self, resource: str, data: Any, **kwargs) -> StorageResult:
        """
        Store object in S3.
        
        Args:
            resource: S3 object key
            data: Data to store (bytes, string, file-like object, or dict/list for JSON)
            **kwargs: S3 parameters (content_type, metadata, acl, etc.)
            
        Returns:
            StorageResult with operation outcome
        """
        if not self.is_connected:
            await self.connect()
        
        try:
            # Prepare data for upload
            if isinstance(data, (dict, list)):
                # JSON data
                body = json.dumps(data).encode('utf-8')
                content_type = kwargs.get("content_type", "application/json")
            elif isinstance(data, str):
                # String data
                body = data.encode('utf-8')
                content_type = kwargs.get("content_type", "text/plain")
            elif isinstance(data, bytes):
                # Binary data
                body = data
                content_type = kwargs.get("content_type", "application/octet-stream")
            elif hasattr(data, 'read'):
                # File-like object
                body = data
                content_type = kwargs.get("content_type", "application/octet-stream")
            else:
                # Convert to string
                body = str(data).encode('utf-8')
                content_type = kwargs.get("content_type", "text/plain")
            
            # Prepare S3 parameters
            put_kwargs = {
                "Bucket": self.bucket_name,
                "Key": resource,
                "Body": body,
                "ContentType": content_type
            }
            
            # Add optional parameters
            if "metadata" in kwargs:
                put_kwargs["Metadata"] = kwargs["metadata"]
            
            if "acl" in kwargs:
                put_kwargs["ACL"] = kwargs["acl"]
            
            if "server_side_encryption" in kwargs:
                put_kwargs["ServerSideEncryption"] = kwargs["server_side_encryption"]
            
            if "cache_control" in kwargs:
                put_kwargs["CacheControl"] = kwargs["cache_control"]
            
            # Upload object
            response = self.s3_client.put_object(**put_kwargs)
            
            # Get object info for metadata
            head_response = self.s3_client.head_object(Bucket=self.bucket_name, Key=resource)
            
            return StorageResult(
                success=True,
                data={
                    "bucket": self.bucket_name,
                    "key": resource,
                    "etag": response["ETag"],
                    "size": head_response["ContentLength"]
                },
                metadata={
                    "operation": "put_object",
                    "content_type": content_type,
                    "last_modified": head_response["LastModified"].isoformat(),
                    "etag": response["ETag"]
                },
                data_reference=DataReference(
                    provider=self.name,
                    storage_type=StorageType.OBJECT,
                    resource_id=resource,
                    metadata={
                        "bucket": self.bucket_name,
                        "size": head_response["ContentLength"],
                        "content_type": content_type
                    }
                )
            )
        
        except Exception as e:
            logger.error(f"Store operation failed: {e}")
            return StorageResult(
                success=False,
                error=f"Store operation failed: {str(e)}"
            )
    
    async def retrieve(self, resource: str, **kwargs) -> StorageResult:
        """
        Retrieve object from S3.
        
        Args:
            resource: S3 object key
            **kwargs: Retrieval parameters (range, decode_json, etc.)
            
        Returns:
            StorageResult with retrieved data
        """
        if not self.is_connected:
            await self.connect()
        
        try:
            get_kwargs = {
                "Bucket": self.bucket_name,
                "Key": resource
            }
            
            # Add range if specified
            if "range" in kwargs:
                get_kwargs["Range"] = kwargs["range"]
            
            # Get object
            response = self.s3_client.get_object(**get_kwargs)
            
            # Read data
            body = response["Body"].read()
            
            # Decode based on content type or request
            content_type = response.get("ContentType", "")
            decode_json = kwargs.get("decode_json", content_type == "application/json")
            
            if decode_json and content_type == "application/json":
                try:
                    data = json.loads(body.decode('utf-8'))
                except (json.JSONDecodeError, UnicodeDecodeError):
                    data = body
            elif kwargs.get("decode_text", content_type.startswith("text/")):
                try:
                    data = body.decode('utf-8')
                except UnicodeDecodeError:
                    data = body
            else:
                data = body
            
            return StorageResult(
                success=True,
                data=data,
                metadata={
                    "operation": "get_object",
                    "key": resource,
                    "content_type": content_type,
                    "size": response["ContentLength"],
                    "last_modified": response["LastModified"].isoformat(),
                    "etag": response["ETag"],
                    "metadata": response.get("Metadata", {})
                }
            )
        
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'NoSuchKey':
                return StorageResult(
                    success=False,
                    error=f"Object '{resource}' not found"
                )
            else:
                logger.error(f"Retrieve operation failed: {e}")
                return StorageResult(
                    success=False,
                    error=f"Retrieve operation failed: {str(e)}"
                )
        except Exception as e:
            logger.error(f"Retrieve operation failed: {e}")
            return StorageResult(
                success=False,
                error=f"Retrieve operation failed: {str(e)}"
            )
    
    async def query(self, resource: str, query: Union[str, Dict], **kwargs) -> StorageResult:
        """
        Execute S3 operations or list objects.
        
        Args:
            resource: Prefix or specific key
            query: Query type ("list", "search", "metadata", etc.)
            **kwargs: Query parameters
            
        Returns:
            StorageResult with query results
        """
        if not self.is_connected:
            await self.connect()
        
        try:
            if isinstance(query, str):
                if query == "list":
                    # List objects with prefix
                    list_kwargs = {
                        "Bucket": self.bucket_name,
                        "Prefix": resource
                    }
                    
                    if "max_keys" in kwargs:
                        list_kwargs["MaxKeys"] = kwargs["max_keys"]
                    
                    if "continuation_token" in kwargs:
                        list_kwargs["ContinuationToken"] = kwargs["continuation_token"]
                    
                    response = self.s3_client.list_objects_v2(**list_kwargs)
                    
                    objects = []
                    if "Contents" in response:
                        for obj in response["Contents"]:
                            objects.append({
                                "key": obj["Key"],
                                "size": obj["Size"],
                                "last_modified": obj["LastModified"].isoformat(),
                                "etag": obj["ETag"]
                            })
                    
                    result_data = {
                        "objects": objects,
                        "count": len(objects),
                        "is_truncated": response.get("IsTruncated", False)
                    }
                    
                    if "NextContinuationToken" in response:
                        result_data["next_token"] = response["NextContinuationToken"]
                    
                    return StorageResult(
                        success=True,
                        data=result_data,
                        metadata={"operation": "list_objects", "prefix": resource}
                    )
                
                elif query == "metadata":
                    # Get object metadata
                    response = self.s3_client.head_object(Bucket=self.bucket_name, Key=resource)
                    
                    return StorageResult(
                        success=True,
                        data={
                            "key": resource,
                            "size": response["ContentLength"],
                            "last_modified": response["LastModified"].isoformat(),
                            "etag": response["ETag"],
                            "content_type": response.get("ContentType"),
                            "metadata": response.get("Metadata", {})
                        },
                        metadata={"operation": "head_object"}
                    )
                
                elif query == "exists":
                    # Check if object exists
                    try:
                        self.s3_client.head_object(Bucket=self.bucket_name, Key=resource)
                        return StorageResult(
                            success=True,
                            data={"exists": True},
                            metadata={"operation": "object_exists"}
                        )
                    except ClientError as e:
                        if e.response['Error']['Code'] == 'NoSuchKey':
                            return StorageResult(
                                success=True,
                                data={"exists": False},
                                metadata={"operation": "object_exists"}
                            )
                        else:
                            raise
                
                elif query == "presigned_url":
                    # Generate presigned URL
                    expiration = kwargs.get("expiration", 3600)  # 1 hour default
                    http_method = kwargs.get("method", "GET")
                    
                    url = self.s3_client.generate_presigned_url(
                        f"{http_method.lower()}_object",
                        Params={"Bucket": self.bucket_name, "Key": resource},
                        ExpiresIn=expiration
                    )
                    
                    return StorageResult(
                        success=True,
                        data={"url": url, "expires_in": expiration},
                        metadata={"operation": "presigned_url", "method": http_method}
                    )
                
                else:
                    raise ValueError(f"Unsupported query type: {query}")
            
            else:
                raise ValueError(f"Unsupported query format: {type(query)}")
        
        except Exception as e:
            logger.error(f"Query operation failed: {e}")
            return StorageResult(
                success=False,
                error=f"Query operation failed: {str(e)}"
            )
    
    async def delete(self, resource: str, **kwargs) -> StorageResult:
        """
        Delete object(s) from S3.
        
        Args:
            resource: Object key or prefix
            **kwargs: Delete parameters (recursive, etc.)
            
        Returns:
            StorageResult with operation outcome
        """
        if not self.is_connected:
            await self.connect()
        
        try:
            if kwargs.get("recursive", False):
                # Delete all objects with prefix
                list_response = self.s3_client.list_objects_v2(
                    Bucket=self.bucket_name,
                    Prefix=resource
                )
                
                if "Contents" not in list_response:
                    return StorageResult(
                        success=True,
                        data={"deleted": 0},
                        metadata={"operation": "delete_objects", "prefix": resource}
                    )
                
                # Prepare objects for deletion
                objects_to_delete = [{"Key": obj["Key"]} for obj in list_response["Contents"]]
                
                # Delete objects in batches
                deleted_count = 0
                batch_size = kwargs.get("batch_size", 1000)
                
                for i in range(0, len(objects_to_delete), batch_size):
                    batch = objects_to_delete[i:i + batch_size]
                    
                    delete_response = self.s3_client.delete_objects(
                        Bucket=self.bucket_name,
                        Delete={"Objects": batch}
                    )
                    
                    deleted_count += len(delete_response.get("Deleted", []))
                
                return StorageResult(
                    success=True,
                    data={"deleted": deleted_count},
                    metadata={"operation": "delete_objects", "prefix": resource}
                )
            
            else:
                # Delete single object
                self.s3_client.delete_object(Bucket=self.bucket_name, Key=resource)
                
                return StorageResult(
                    success=True,
                    data={"deleted": 1},
                    metadata={"operation": "delete_object", "key": resource}
                )
        
        except Exception as e:
            logger.error(f"Delete operation failed: {e}")
            return StorageResult(
                success=False,
                error=f"Delete operation failed: {str(e)}"
            )
    
    async def list_resources(self, prefix: str = "", **kwargs) -> StorageResult:
        """List objects in S3 bucket."""
        return await self.query(prefix, "list", **kwargs)