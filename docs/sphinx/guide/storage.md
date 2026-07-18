# Storage

Praval's storage layer is asynchronous. A `StorageRegistry` owns provider
instances and their connections; `DataManager` provides uniform store, get,
query, delete, batch, and data-reference operations.

Install the optional dependencies before using remote providers:

```bash
python -m pip install "praval[storage]"
```

## Minimal filesystem example

```python
import asyncio
import tempfile

from praval import DataManager, FileSystemProvider, StorageRegistry


async def main():
    registry = StorageRegistry()
    with tempfile.TemporaryDirectory() as directory:
        provider = FileSystemProvider(
            "local-files",
            {"base_path": directory},
        )
        registered = await registry.register_provider(provider)
        if not registered:
            raise RuntimeError("filesystem provider registration failed")

        data = DataManager(registry)
        stored = await data.store(
            "local-files",
            "reports/result.json",
            {"status": "ready"},
        )
        if not stored.success:
            raise RuntimeError(stored.error)

        loaded = await data.get("local-files", "reports/result.json")
        print(loaded.data)
        await registry.unregister_provider("local-files")


asyncio.run(main())
```

Provider constructors take an instance name and a configuration dictionary.
`register_provider()` validates the provider, connects it by default, performs
an initial health check, and returns `True` or `False`.

## DataManager contract

The main methods return `StorageResult`:

```python
stored = await data.store(provider, resource, value, **options)
loaded = await data.get(provider, resource, **options)
matches = await data.query(provider, resource, query, **options)
deleted = await data.delete(provider, resource, **options)
```

Check `result.success` before using `result.data`. Failed provider operations
may return a result with `error`; missing or unauthorized provider selection
raises a storage exception.

The module-level helpers have the same asynchronous contract and use the global
data manager:

```python
from praval.storage.data_manager import delete_data, get_data, query_data, store_data

stored = await store_data("cache", "session:42", {"state": "open"})
loaded = await get_data("cache", "session:42")
```

## Registering providers

Use `StorageRegistry.register_provider(provider)`. `DataManager` does not have a
`register_provider()` method.

```python
from praval import RedisProvider, StorageRegistry

registry = StorageRegistry()
redis = RedisProvider(
    "cache",
    {
        "host": "127.0.0.1",
        "port": 6379,
        "database": 0,
    },
)
await registry.register_provider(redis, permissions=["support-agent"])
```

Always unregister or disconnect providers during shutdown:

```python
await registry.unregister_provider("cache")
```

## Provider roles

| Provider | Typical role | Important configuration |
| --- | --- | --- |
| `FileSystemProvider` | local JSON, bytes, and files | `base_path` |
| `PostgreSQLProvider` | relational data and SQL queries | host, database, user, password |
| `RedisProvider` | keys, cache, and expiring data | host, port, database |
| `S3Provider` | objects and MinIO-compatible storage | bucket and endpoint/credentials |
| `QdrantProvider` | vectors and similarity search | URL, collection, vector size |

The exact query and option shape remains provider-specific. Read the generated
provider API before passing SQL, Redis, S3, or vector-specific arguments.

Redis is a storage provider. It is not a Reef transport or distributed Reef
backend.

## Data references

`DataReference` is a small pointer suitable for a Spore:

```python
reference = data.create_data_reference(
    "local-files",
    "reports/result.json",
    content_type="application/json",
)
print(reference.provider)
print(reference.storage_type)
print(reference.resource_id)
print(reference.to_uri())

resolved = await data.resolve_data_reference(reference)
```

References contain `provider`, `storage_type`, and `resource_id`. They may also
contain metadata and an expiration time. Resolving an expired reference returns
an unsuccessful `StorageResult`.

## Smart selection and fallback

`smart_store()` and `smart_search()` select from registered providers using
the data manager's suitability rules. They do not provide a durability
guarantee or a transaction across backends.

Praval does not automatically move a failed write to another provider. If an
application needs fallback, make the policy explicit:

```python
primary = await data.store("postgres", "events", event)
if not primary.success:
    fallback = await data.store("local-files", "fallback/event.json", event)
    if not fallback.success:
        raise RuntimeError(fallback.error)
```

Only fall back for errors your application has classified as safe. A fallback
can change consistency, retention, access control, and query behavior.

## Storage-aware handlers

`@storage_enabled` can ensure configured providers exist and inject a
`storage` keyword argument. For new asynchronous handlers, explicit setup is
easier to reason about:

```python
from praval.storage import requires_storage


@requires_storage("postgres")
async def persist_event(spore, storage):
    return await storage.store("postgres", "events", spore.knowledge)
```

Decorator order and handler signatures matter. The storage decorator wraps a
function and passes `storage=...`; include that keyword in the wrapped
function's signature.

## Custom provider contract

A custom provider subclasses `BaseStorageProvider` and implements asynchronous
connection and CRUD/query methods:

```python
from praval.storage import (
    BaseStorageProvider,
    StorageMetadata,
    StorageResult,
    StorageType,
)


class CustomProvider(BaseStorageProvider):
    def _create_metadata(self):
        return StorageMetadata(
            name=self.name,
            description="Application storage",
            storage_type=StorageType.DOCUMENT,
        )

    async def connect(self):
        self.is_connected = True
        return True

    async def disconnect(self):
        self.is_connected = False

    async def store(self, resource, data, **kwargs):
        return StorageResult(success=True, data={"resource": resource})

    async def retrieve(self, resource, **kwargs):
        return StorageResult(success=False, error="not implemented")

    async def query(self, resource, query, **kwargs):
        return StorageResult(success=False, error="not implemented")

    async def delete(self, resource, **kwargs):
        return StorageResult(success=True)

    async def list_resources(self, prefix="", **kwargs):
        return StorageResult(success=True, data=[])
```

The provider must also return a valid schema through the base provider
contract. Document provider-specific exceptions and ensure secrets are not
included in exception or log messages.

## Failure and cleanup checklist

- Check every `StorageResult.success` value.
- Bound provider timeouts in service code.
- Treat permissions and blocked providers as hard failures.
- Do not put credentials into DataReferences or Spores.
- Keep vector dimensions compatible with the embedding model.
- Unregister providers so pools and clients disconnect.
- Test remote providers against real ephemeral services before release.

See {doc}`embeddings` for vector compatibility and {doc}`../api/index` for the
generated signatures.
