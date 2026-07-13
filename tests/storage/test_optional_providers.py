from datetime import datetime, timezone
from fnmatch import fnmatch
from types import SimpleNamespace

import pytest


@pytest.mark.asyncio
async def test_postgresql_provider_basic_flow(monkeypatch):
    from praval.storage.providers import postgresql as pg

    class FakeRecord(dict):
        pass

    class FakeConn:
        def __init__(self):
            self.queries = []

        async def fetchrow(self, query, *values):
            self.queries.append((query, values))
            return FakeRecord({"id": 1})

        async def execute(self, query, *values):
            self.queries.append((query, values))
            return "DELETE 1"

        async def fetch(self, query, *params):
            self.queries.append((query, params))
            if "information_schema.tables" in query:
                return [FakeRecord({"table_name": "items"})]
            return [FakeRecord({"id": 1, "name": "row"})]

        async def executemany(self, query, values_list):
            self.queries.append((query, values_list))
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

    provider = pg.PostgreSQLProvider(
        "pg",
        {
            "host": "localhost",
            "database": "db",
            "user": "user",
            "password": "pw",
        },
    )

    await provider.connect()
    res = await provider.store("items", {"id": 1, "name": "row"})
    assert res.success
    assert (await provider.store("items", {"id": 2}, returning="id")).data == {"id": 1}
    assert (await provider.store("items", [])).data == {"inserted": 0}
    assert (await provider.store("items", [{"id": 1}, {"id": 2}])).data == {
        "inserted": 2
    }
    assert (await provider.store("items", "invalid")).success is False

    res = await provider.retrieve(
        "items",
        where={"age": {"$gte": 18}, "status": {"$in": ["active", "new"]}},
        order_by="id DESC",
        limit=10,
        offset=1,
    )
    assert res.success

    res = await provider.query("items", "SELECT * FROM items")
    assert res.success
    assert (await provider.query("items", "UPDATE items SET id = 2")).success
    assert (
        await provider.query(
            "items",
            {
                "operation": "select",
                "fields": ["id", "name"],
                "where": {"age": {"$gt": 10}},
                "order_by": "id",
                "limit": 2,
            },
        )
    ).success
    assert (await provider.query("items", {"operation": "update"})).success is False
    assert (await provider.query("items", 42)).success is False

    res = await provider.delete("items", where={"id": 1})
    assert res.success
    assert (await provider.delete("items")).success is False
    resources = await provider.list_resources(prefix="it")
    assert resources.data == ["items"]

    clause, params = provider._build_where_clause(
        {
            "a": {"$lt": 2},
            "b": {"$lte": 3},
            "c": {"$ne": 4},
            "d": 5,
        }
    )
    assert "$1" in clause and params == [2, 3, 4, 5]
    with pytest.raises(ValueError, match="Unsupported operator"):
        provider._build_where_clause({"a": {"$bad": 1}})

    await provider.disconnect()


@pytest.mark.asyncio
async def test_redis_provider_basic_flow(monkeypatch):
    from praval.storage.providers import redis_provider as rp

    class FakeRedis:
        def __init__(self, **kwargs):
            self.store = {}
            self.set_result = True

        async def ping(self):
            return True

        async def close(self):
            return None

        async def set(self, key, value, ex=None, px=None, nx=False, xx=False):
            self.store[key] = value
            return self.set_result

        async def ttl(self, key):
            return 10

        async def get(self, key):
            return self.store.get(key)

        async def keys(self, pattern):
            return [key for key in self.store if fnmatch(key, pattern)]

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
    assert (await provider.store("scalar", 7, ex=10)).success
    provider.redis_client.set_result = False
    assert (await provider.store("blocked", "value", nx=True)).success is False
    provider.redis_client.set_result = True

    res = await provider.retrieve("k1")
    assert res.success
    assert (await provider.retrieve("missing")).success is False
    provider.redis_client.store["invalid-json"] = "{invalid"
    invalid_json = await provider.retrieve("invalid-json")
    assert invalid_json.success and invalid_json.data == "{invalid"
    assert (await provider.retrieve("scalar", decode_json=False)).data == "7"

    res = await provider.query("k*", "keys")
    assert res.success
    assert (await provider.query("k*", "scan", count=2)).success
    assert (await provider.query("k1", "exists", keys=["k1", "missing"])).success
    assert (
        await provider.query("", {"operation": "mget", "keys": ["k1", "scalar"]})
    ).success

    res = await provider.query("k1", "hgetall")
    assert res.success
    assert (await provider.query("k1", "hget", field="a")).success
    assert (await provider.query("k1", "hkeys")).success
    assert (await provider.query("k1", "hvals")).success
    assert (await provider.query("k1", "hget")).success is False

    res = await provider.query("k1", "lrange")
    assert res.success
    assert (await provider.query("k1", "llen")).success
    assert (await provider.query("k1", "lindex", index=0)).success

    res = await provider.query("k1", "smembers")
    assert res.success
    assert (await provider.query("k1", "scard")).success
    assert (await provider.query("k1", "sismember", member="x")).success
    assert (await provider.query("k1", "sismember")).success is False
    assert (await provider.query("k1", "unsupported")).success is False
    assert (await provider.query("k1", {"operation": "unsupported"})).success is False
    assert (await provider.query("k1", 42)).success is False

    res = await provider.delete("k1")
    assert res.success
    assert (await provider.delete("missing*", pattern_delete=True)).data == {
        "deleted": 0
    }

    await provider.disconnect()


@pytest.mark.asyncio
async def test_s3_provider_basic_flow(monkeypatch):
    from praval.storage.providers import s3_provider as s3

    class FakeClient:
        def __init__(self, **kwargs):
            self.objects = {}

        def head_bucket(self, Bucket=None):
            return None

        def put_object(
            self, Bucket=None, Key=None, Body=None, Metadata=None, ContentType=None
        ):
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
            return {
                "ContentLength": 0,
                "LastModified": datetime.now(timezone.utc),
                "ETag": "etag",
            }

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
            self.collections = set()
            self.points = {}

        def get_collections(self):
            return SimpleNamespace(
                collections=[
                    SimpleNamespace(name=name, points_count=len(self.points))
                    for name in sorted(self.collections)
                ]
            )

        def get_collection(self, name):
            if name not in self.collections:
                raise Exception("not found")
            return SimpleNamespace(
                points_count=len(self.points), segments_count=1, status="green"
            )

        def create_collection(self, collection_name=None, vectors_config=None):
            self.collections.add(collection_name)

        def upsert(self, collection_name=None, points=None):
            for p in points:
                self.points[p.id] = p
            return SimpleNamespace(operation_id="operation-1")

        def retrieve(self, collection_name=None, ids=None, **kwargs):
            return [
                self.points[point_id] for point_id in ids if point_id in self.points
            ]

        def scroll(self, collection_name=None, limit=None, offset=None, **kwargs):
            return (list(self.points.values())[:limit], "next")

        def search(
            self,
            collection_name=None,
            query_vector=None,
            limit=None,
            with_payload=None,
            with_vectors=None,
            query_filter=None,
        ):
            results = list(self.points.values())[:limit]
            for point in results:
                point.score = 0.9
            return results

        def delete(self, collection_name=None, points_selector=None):
            for point_id in getattr(points_selector, "points", []):
                self.points.pop(point_id, None)
            return None

        def count(self, collection_name=None, **kwargs):
            return SimpleNamespace(count=len(self.points))

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

    res = await provider.store(
        "items", {"id": "p1", "vector": [0.1, 0.2, 0.3], "payload": {"a": 1}}
    )
    assert res.success
    assert res.data["operation_id"] == "operation-1"
    assert (
        await provider.store(
            "items",
            [
                {"id": "p2", "vector": [0.2, 0.3, 0.4]},
                {"id": "p3", "vector": [0.3, 0.4, 0.5]},
            ],
        )
    ).success
    assert (
        await provider.store("items", [0.4, 0.5, 0.6], id="p4", payload={"kind": "raw"})
    ).success
    assert (await provider.store("items", {})).success is False
    assert (await provider.store("items", [])).success is False

    retrieved = await provider.retrieve("items:p1")
    assert retrieved.success and retrieved.data["id"] == "p1"
    assert (await provider.retrieve("items")).success is False

    res = await provider.query("items", "search", vector=[0.1, 0.2, 0.3])
    assert res.success
    assert res.data[0]["score"] == 0.9
    assert (await provider.query("items", "count")).data["count"] == 4
    assert (await provider.query("items", "scroll", limit=2)).success
    assert (await provider.query("items", [0.1, 0.2, 0.3])).success
    assert (await provider.query("items", "search")).success is False
    assert (await provider.query("items", "unsupported")).success is False
    assert (await provider.query("items", {"bad": True})).success is False

    res = await provider.delete("items", ids=["p1"])
    assert res.success
    assert (await provider.delete("items", filter=FakeModels.Filter())).success
    assert (await provider.delete("items")).success is False

    resources = await provider.list_resources(prefix="it")
    assert resources.success and resources.data[0]["name"] == "items"

    assert provider._to_qdrant_point_id("items", 1) == 1
    assert provider._from_qdrant_point("id", {}) == "id"

    await provider.disconnect()
