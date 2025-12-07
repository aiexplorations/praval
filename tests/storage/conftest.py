"""
Testcontainer fixtures for storage provider integration tests.

These fixtures spin up real Docker containers for PostgreSQL, Redis, and Qdrant
to enable comprehensive integration testing of storage providers.

Usage:
    Tests using these fixtures will be automatically marked as integration tests.
    Run with: pytest tests/storage/ -m integration
    Skip with: pytest tests/storage/ -m "not integration"
"""

import os
import pytest
import pytest_asyncio
from typing import Generator, Any

# Integration test marker - applied to all tests using container fixtures
INTEGRATION_MARKER = pytest.mark.integration


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers",
        "integration: mark test as integration test requiring Docker containers"
    )


# ============================================================================
# PostgreSQL Fixtures
# ============================================================================


@pytest.fixture(scope="session")
def postgres_container():
    """
    Spin up real PostgreSQL container for integration tests.

    Uses testcontainers to create an isolated PostgreSQL instance.
    The container is shared across all tests in the session for efficiency.
    """
    try:
        from testcontainers.postgres import PostgresContainer
    except ImportError:
        pytest.skip("testcontainers[postgres] not installed")

    with PostgresContainer("postgres:15") as postgres:
        # Create test table using psycopg2 (sync) for setup
        # Tests will use asyncpg through the provider
        try:
            import psycopg2
            conn = psycopg2.connect(
                host=postgres.get_container_host_ip(),
                port=postgres.get_exposed_port(5432),
                database=postgres.dbname,
                user=postgres.username,
                password=postgres.password
            )
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS test_table (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(255),
                    data JSONB,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)
            conn.commit()
            cursor.close()
            conn.close()
        except ImportError:
            # psycopg2 not available - table will be created in tests
            pass

        yield postgres


@pytest.fixture
def postgres_config(postgres_container) -> dict:
    """Configuration dict for PostgreSQL provider."""
    return {
        "host": postgres_container.get_container_host_ip(),
        "port": int(postgres_container.get_exposed_port(5432)),
        "database": postgres_container.dbname,
        "user": postgres_container.username,
        "password": postgres_container.password,
    }


@pytest_asyncio.fixture
async def postgres_provider(postgres_config):
    """
    Create PostgreSQL provider connected to test container.

    The provider is connected and ready to use.
    Cleanup happens automatically after each test.
    """
    try:
        import asyncpg
    except ImportError:
        pytest.skip("asyncpg not installed")

    try:
        from praval.storage.providers.postgresql import PostgreSQLProvider
    except ImportError:
        pytest.skip("PostgreSQL provider not available")

    provider = PostgreSQLProvider("test_postgres", postgres_config)
    await provider.connect()

    yield provider

    # Cleanup: truncate test tables
    if provider.is_connected:
        try:
            await provider.query("test_table", "TRUNCATE TABLE test_table RESTART IDENTITY")
        except Exception:
            pass
        await provider.disconnect()


# ============================================================================
# Redis Fixtures
# ============================================================================


@pytest.fixture(scope="session")
def redis_container():
    """
    Spin up real Redis container for integration tests.

    Uses testcontainers to create an isolated Redis instance.
    """
    try:
        from testcontainers.redis import RedisContainer
    except ImportError:
        pytest.skip("testcontainers[redis] not installed")

    with RedisContainer("redis:7") as redis:
        yield redis


@pytest.fixture
def redis_config(redis_container) -> dict:
    """Configuration dict for Redis provider."""
    return {
        "host": redis_container.get_container_host_ip(),
        "port": int(redis_container.get_exposed_port(6379)),
        "database": 0,
    }


@pytest_asyncio.fixture
async def redis_provider(redis_config):
    """
    Create Redis provider connected to test container.

    The provider is connected and ready to use.
    Keys are flushed after each test.
    """
    try:
        from praval.storage.providers.redis_provider import RedisProvider
    except ImportError:
        pytest.skip("Redis provider not available")

    provider = RedisProvider("test_redis", redis_config)
    await provider.connect()

    yield provider

    # Cleanup: flush test database
    if provider.is_connected:
        try:
            await provider._client.flushdb()
        except Exception:
            pass
        await provider.disconnect()


# ============================================================================
# Qdrant Fixtures
# ============================================================================


@pytest.fixture(scope="session")
def qdrant_container():
    """
    Spin up real Qdrant container for integration tests.

    Uses testcontainers to create an isolated Qdrant instance.
    """
    try:
        from testcontainers.qdrant import QdrantContainer
    except ImportError:
        pytest.skip("testcontainers[qdrant] not installed")

    with QdrantContainer() as qdrant:
        yield qdrant


@pytest.fixture
def qdrant_config(qdrant_container) -> dict:
    """Configuration dict for Qdrant provider."""
    host = qdrant_container.get_container_host_ip()
    port = qdrant_container.get_exposed_port(6333)
    return {
        "url": f"http://{host}:{port}",
        "collection": "test_collection",
        "vector_size": 128,  # Small vectors for testing
    }


@pytest_asyncio.fixture
async def qdrant_provider(qdrant_config):
    """
    Create Qdrant provider connected to test container.

    The provider is connected and ready to use.
    Collections are cleaned up after each test.
    """
    try:
        from praval.storage.providers.qdrant_provider import QdrantProvider
    except ImportError:
        pytest.skip("Qdrant provider not available")

    provider = QdrantProvider("test_qdrant", qdrant_config)
    await provider.connect()

    yield provider

    # Cleanup: delete test collection
    if provider.is_connected:
        try:
            await provider._client.delete_collection("test_collection")
        except Exception:
            pass
        await provider.disconnect()


# ============================================================================
# S3 Fixtures (using moto mock)
# ============================================================================


@pytest.fixture(scope="session")
def aws_credentials():
    """Mocked AWS credentials for moto."""
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"


@pytest.fixture
def s3_mock(aws_credentials):
    """
    Create mocked S3 service using moto.

    This doesn't require Docker - moto mocks the AWS S3 API entirely.
    """
    try:
        from moto import mock_aws
        import boto3
    except ImportError:
        pytest.skip("moto[s3] not installed")

    with mock_aws():
        # Create test bucket
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket="test-bucket")
        yield client


@pytest.fixture
def s3_config(aws_credentials) -> dict:
    """Configuration dict for S3 provider."""
    return {
        "bucket_name": "test-bucket",
        "region": "us-east-1",
        "access_key": "testing",
        "secret_key": "testing",
    }


@pytest_asyncio.fixture
async def s3_provider(s3_mock, s3_config):
    """
    Create S3 provider using moto mock.

    The provider is connected to the mocked S3 service.
    Objects are cleaned up after each test.
    """
    try:
        from praval.storage.providers.s3_provider import S3Provider
    except ImportError:
        pytest.skip("S3 provider not available")

    provider = S3Provider("test_s3", s3_config)
    await provider.connect()

    yield provider

    # Cleanup: delete all objects
    if provider.is_connected:
        try:
            response = s3_mock.list_objects_v2(Bucket="test-bucket")
            for obj in response.get("Contents", []):
                s3_mock.delete_object(Bucket="test-bucket", Key=obj["Key"])
        except Exception:
            pass
        await provider.disconnect()


# ============================================================================
# Skip Markers for Container Tests
# ============================================================================


def pytest_collection_modifyitems(config, items):
    """
    Automatically mark tests using container fixtures as integration tests.

    This allows selective running of integration tests:
    - Run all: pytest tests/storage/
    - Skip integration: pytest tests/storage/ -m "not integration"
    - Only integration: pytest tests/storage/ -m integration
    """
    container_fixtures = {
        "postgres_container", "postgres_config", "postgres_provider",
        "redis_container", "redis_config", "redis_provider",
        "qdrant_container", "qdrant_config", "qdrant_provider",
        "s3_mock", "s3_config", "s3_provider",
    }

    for item in items:
        # Check if test uses any container fixtures
        fixtures_used = set(getattr(item, "fixturenames", []))
        if fixtures_used & container_fixtures:
            item.add_marker(INTEGRATION_MARKER)


# ============================================================================
# Utility Fixtures
# ============================================================================


@pytest.fixture
def sample_vector() -> list:
    """Generate a sample vector for testing vector operations."""
    import random
    return [random.random() for _ in range(128)]


@pytest.fixture
def sample_record() -> dict:
    """Generate a sample record for testing relational operations."""
    return {
        "name": "Test Record",
        "data": {"key": "value", "count": 42},
        "tags": ["test", "sample"],
    }


@pytest.fixture
def sample_document() -> dict:
    """Generate a sample document for testing object storage."""
    return {
        "title": "Test Document",
        "content": "This is a test document with some content.",
        "metadata": {
            "author": "Test Author",
            "version": 1,
            "tags": ["test", "document"],
        },
    }
