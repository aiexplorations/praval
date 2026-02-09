import asyncio
from datetime import datetime
from types import SimpleNamespace

import pytest


@pytest.mark.asyncio
async def test_postgresql_provider_basic_flow(monkeypatch):
    from praval.storage.providers import postgresql as pg

    class FakeRecord(dict):
        pass

    class FakeConn:
        async def fetchrow(self, query, *values):
            return FakeRecord({"id": 1})

        async def execute(self, query, *values):
            return "DELETE 1"

        async def fetch(self, query, *params):
            return [FakeRecord({"id": 1, "name": "row"})]

        async def executemany(self, query, values_list):
            return None

    class FakeAcquire:
        async def __aenter__(self):
            return FakeConn()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class FakePool:
        def acquire(self):
            return FakeAcquire()

        async def close(self):
            return None

    class FakeAsyncpg:
        @staticmethod
        async def create_pool(*args, **kwargs):
            return FakePool()

    monkeypatch.setattr(pg, "ASYNCPG_AVAILABLE", True)
    monkeypatch.setattr(pg, "asyncpg", FakeAsyncpg)

    provider = pg.PostgreSQLProvider("pg", {
        "host": "localhost",
        "database": "db",
        "user": "user",
        "password": "pw",
    })

    await provider.connect()
    res = await provider.store("items", {"id": 1, "name": "row"})
    assert res.success

    res = await provider.retrieve("items")
    assert res.success

    res = await provider.query("items", "SELECT * FROM items")
    assert res.success

    res = await provider.delete("items", where={"id": 1})
    assert res.success

    await provider.disconnect()


@pytest.mark.asyncio
async def test_redis_provider_basic_flow(monkeypatch):
    from praval.storage.providers import redis_provider as rp

    class FakeRedis:
        def __init__(self, **kwargs):
            self.store = {}

        async def ping(self):
            return True

        async def close(self):
            return None

        async def set(self, key, value, ex=None, px=None, nx=False, xx=False):
            self.store[key] = value
            return True

        async def ttl(self, key):
            return 10

        async def get(self, key):
            return self.store.get(key)

        async def keys(self, pattern):
            return [k for k in self.store.keys()]

        async def scan(self, cursor=0, match=None, count=10):
            return 0, list(self.store.keys())

        async def exists(self, *keys):
            return len([k for k in keys if k in self.store])

        async def mget(self, keys):
            return [self.store.get(k) for k in keys]

        async def delete(self, *keys):
            deleted = 0
            for k in keys:
                if k in self.store:
                    del self.store[k]
                    deleted += 1
            return deleted

        async def hgetall(self, key):
            return {"a": "1"}

        async def hget(self, key, field):
            return "1"

        async def hkeys(self, key):
            return ["a"]

        async def hvals(self, key):
            return ["1"]

        async def lrange(self, key, start, end):
            return ["x"]

        async def llen(self, key):
            return 1

        async def lindex(self, key, index):
            return "x"

        async def smembers(self, key):
            return {"x"}

        async def scard(self, key):
            return 1

        async def sismember(self, key, member):
            return True

    class FakeRedisModule:
        Redis = FakeRedis

    monkeypatch.setattr(rp, "REDIS_AVAILABLE", True)
    monkeypatch.setattr(rp, "redis", FakeRedisModule)

    provider = rp.RedisProvider("redis", {"host": "localhost"})
    await provider.connect()

    res = await provider.store("k1", {"a": 1})
    assert res.success

    res = await provider.retrieve("k1")
    assert res.success

    res = await provider.query("k*", "keys")
    assert res.success

    res = await provider.query("k1", "hgetall")
    assert res.success

    res = await provider.query("k1", "lrange")
    assert res.success

    res = await provider.query("k1", "smembers")
    assert res.success

    res = await provider.delete("k1")
    assert res.success

    await provider.disconnect()


@pytest.mark.asyncio
async def test_s3_provider_basic_flow(monkeypatch):
    from praval.storage.providers import s3_provider as s3

    class FakeClient:
        def __init__(self, **kwargs):
            self.objects = {}

        def head_bucket(self, Bucket=None):
            return None

        def put_object(self, Bucket=None, Key=None, Body=None, Metadata=None, ContentType=None):
            self.objects[Key] = Body
            return {"ETag": "etag"}

        def get_object(self, Bucket=None, Key=None):
            return {"Body": SimpleNamespace(read=lambda: self.objects.get(Key, b""))}

        def delete_object(self, Bucket=None, Key=None):
            self.objects.pop(Key, None)
            return None

        def list_objects_v2(self, **kwargs):
            return {"Contents": []}

        def head_object(self, Bucket=None, Key=None):
            return {"ContentLength": 0, "LastModified": datetime.utcnow(), "ETag": "etag"}

        def generate_presigned_url(self, *args, **kwargs):
            return "http://example.com"

    class FakeBoto3:
        @staticmethod
        def client(**kwargs):
            return FakeClient(**kwargs)

        class session:
            class Config:
                def __init__(self, **kwargs):
                    pass

    monkeypatch.setattr(s3, "BOTO3_AVAILABLE", True)
    monkeypatch.setattr(s3, "boto3", FakeBoto3)

    provider = s3.S3Provider("s3", {"bucket_name": "b"})
    await provider.connect()

    res = await provider.store("k1", b"data")
    assert res.success

    res = await provider.retrieve("k1")
    assert res.success

    res = await provider.query("", "list")
    assert res.success

    res = await provider.query("k1", "presigned_url")
    assert res.success

    res = await provider.delete("k1")
    assert res.success

    await provider.disconnect()


@pytest.mark.asyncio
async def test_qdrant_provider_basic_flow(monkeypatch):
    from praval.storage.providers import qdrant_provider as qp

    class FakeQdrant:
        def __init__(self, **kwargs):
            self.collections = []
            self.points = {}

        def get_collections(self):
            return {"collections": []}

        def get_collection(self, name):
            raise Exception("not found")

        def create_collection(self, collection_name=None, vectors_config=None):
            return None

        def upsert(self, collection_name=None, points=None):
            for p in points:
                self.points[p.id] = p

        def retrieve(self, collection_name=None, ids=None):
            return []

        def scroll(self, collection_name=None, limit=None, offset=None):
            return ([], None)

        def search(self, collection_name=None, query_vector=None, limit=None, with_payload=None, with_vectors=None, query_filter=None):
            return []

        def delete(self, collection_name=None, points_selector=None):
            return None

        def count(self, collection_name=None):
            return SimpleNamespace(count=0)

        def close(self):
            return None

    class FakeModels:
        class PointStruct:
            def __init__(self, id, vector, payload):
                self.id = id
                self.vector = vector
                self.payload = payload

        class Filter:
            def __init__(self, must=None):
                pass

        class FieldCondition:
            def __init__(self, key=None, match=None):
                pass

        class MatchValue:
            def __init__(self, value=None):
                pass

        class PointIdsList:
            def __init__(self, points=None):
                self.points = points or []

        class FilterSelector:
            def __init__(self, filter=None):
                self.filter = filter

    class FakeDistance:
        COSINE = "cosine"
        EUCLIDEAN = "euclidean"

    class FakeVectorParams:
        def __init__(self, size=None, distance=None):
            self.size = size
            self.distance = distance

    monkeypatch.setattr(qp, "QDRANT_AVAILABLE", True)
    monkeypatch.setattr(qp, "QdrantClient", FakeQdrant)
    monkeypatch.setattr(qp, "models", FakeModels)
    monkeypatch.setattr(qp, "PointStruct", FakeModels.PointStruct)
    monkeypatch.setattr(qp, "VectorParams", FakeVectorParams)
    monkeypatch.setattr(qp, "Distance", FakeDistance)

    provider = qp.QdrantProvider("q", {"url": "http://localhost:6333"})
    await provider.connect()

    res = await provider.store("items", {"id": "p1", "vector": [0.1, 0.2, 0.3], "payload": {"a": 1}})
    assert res.success

    res = await provider.query("items", "search", vector=[0.1, 0.2, 0.3])
    assert res.success

    res = await provider.delete("items", ids=["p1"])
    assert res.success

    await provider.disconnect()
