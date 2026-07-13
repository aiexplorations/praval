"""Certify Praval against real ephemeral storage, transport, and OTLP services."""

from __future__ import annotations

import asyncio
from datetime import datetime

from support import report_dir, require_environment, write_json_artifact

from praval.core.reef import Spore, SporeType
from praval.core.reef_backend import RabbitMQBackend
from praval.observability import OTLPExporter
from praval.storage import (
    FileSystemProvider,
    PostgreSQLProvider,
    QdrantProvider,
    RedisProvider,
    S3Provider,
)


async def certify_filesystem() -> dict:
    """Round-trip JSON through the real filesystem provider."""
    provider = FileSystemProvider(
        "service-filesystem", {"base_path": str(report_dir() / "filesystem")}
    )
    try:
        stored = await provider.store("state.json", {"service": "filesystem"})
        restored = await provider.retrieve("state.json")
        assert stored.success and restored.success
        assert restored.data == {"service": "filesystem"}
        return {"stored": True, "retrieved": True}
    finally:
        await provider.disconnect()


async def certify_postgresql() -> dict:
    """Create, insert, query, and clean up a real PostgreSQL table."""
    values = require_environment(
        "POSTGRES_HOST",
        "POSTGRES_PORT",
        "POSTGRES_DB",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
    )
    provider = PostgreSQLProvider(
        "service-postgresql",
        {
            "host": values["POSTGRES_HOST"],
            "port": int(values["POSTGRES_PORT"]),
            "database": values["POSTGRES_DB"],
            "user": values["POSTGRES_USER"],
            "password": values["POSTGRES_PASSWORD"],
        },
    )
    try:
        assert await provider.connect()
        created = await provider.query(
            "",
            "CREATE TABLE IF NOT EXISTS praval_certification "
            "(id INTEGER PRIMARY KEY, status TEXT NOT NULL)",
        )
        await provider.query("", "TRUNCATE TABLE praval_certification")
        stored = await provider.store(
            "praval_certification", {"id": 1, "status": "ready"}
        )
        restored = await provider.retrieve("praval_certification", where={"id": 1})
        assert created.success and stored.success and restored.success
        assert restored.data == [{"id": 1, "status": "ready"}]
        return {"created": True, "stored": True, "queried": True}
    finally:
        if provider.is_connected:
            await provider.query("", "DROP TABLE IF EXISTS praval_certification")
            await provider.disconnect()


async def certify_redis() -> dict:
    """Round-trip structured data through a real Redis server."""
    values = require_environment("REDIS_HOST", "REDIS_PORT")
    provider = RedisProvider(
        "service-redis",
        {
            "host": values["REDIS_HOST"],
            "port": int(values["REDIS_PORT"]),
            "database": 0,
        },
    )
    key = "praval:certification"
    try:
        assert await provider.connect()
        stored = await provider.store(key, {"service": "redis", "ready": True})
        restored = await provider.retrieve(key)
        assert stored.success and restored.success
        assert restored.data == {"service": "redis", "ready": True}
        return {"stored": True, "retrieved": True}
    finally:
        if provider.is_connected:
            await provider.delete(key)
            await provider.disconnect()


async def certify_minio() -> dict:
    """Round-trip bytes through an actual S3-compatible MinIO service."""
    values = require_environment(
        "MINIO_ENDPOINT", "MINIO_ACCESS_KEY", "MINIO_SECRET_KEY"
    )
    provider = S3Provider(
        "service-minio",
        {
            "bucket_name": "praval-certification",
            "endpoint_url": values["MINIO_ENDPOINT"],
            "aws_access_key_id": values["MINIO_ACCESS_KEY"],
            "aws_secret_access_key": values["MINIO_SECRET_KEY"],
            "region_name": "us-east-1",
            "use_ssl": values["MINIO_ENDPOINT"].startswith("https://"),
            "create_bucket": True,
        },
    )
    key = "exact-wheel.txt"
    try:
        assert await provider.connect()
        stored = await provider.store(key, b"Praval exact wheel")
        restored = await provider.retrieve(key)
        assert stored.success and restored.success
        assert restored.data == b"Praval exact wheel"
        return {"stored": True, "retrieved": True}
    finally:
        if provider.is_connected:
            await provider.delete(key)
            await provider.disconnect()


async def certify_qdrant() -> dict:
    """Store, retrieve, and search a vector in a real Qdrant service."""
    values = require_environment("QDRANT_URL")
    provider = QdrantProvider(
        "service-qdrant",
        {
            "url": values["QDRANT_URL"],
            "collection_name": "praval_certification",
            "vector_size": 4,
        },
    )
    try:
        assert await provider.connect()
        stored = await provider.store(
            "praval_certification",
            {
                "id": "exact-wheel",
                "vector": [1.0, 0.0, 0.0, 0.0],
                "payload": {"ready": True},
            },
        )
        restored = await provider.retrieve("praval_certification:exact-wheel")
        searched = await provider.query(
            "praval_certification", "search", vector=[1.0, 0.0, 0.0, 0.0]
        )
        assert stored.success and restored.success and searched.success
        assert restored.data["payload"]["ready"] is True
        assert searched.data
        return {"stored": True, "retrieved": True, "searched": True}
    finally:
        if provider.is_connected:
            await provider.delete("praval_certification")
            await provider.disconnect()


async def certify_rabbitmq() -> dict:
    """Publish and consume a native Spore through a real RabbitMQ broker."""
    values = require_environment("RABBITMQ_URL")
    backend = RabbitMQBackend()
    received = []
    delivered = asyncio.Event()

    async def handler(spore: Spore) -> None:
        received.append(spore)
        delivered.set()

    try:
        await backend.initialize(
            {
                "url": values["RABBITMQ_URL"],
                "exchange_name": "praval.certification",
            }
        )
        await backend.subscribe("agent.receiver", handler)
        spore = Spore(
            id="service-rabbitmq-spore",
            spore_type=SporeType.KNOWLEDGE,
            from_agent="sender",
            to_agent="receiver",
            knowledge={"service": "rabbitmq", "ready": True},
            created_at=datetime.now(),
            schema_version="2.0",
            correlation_id="service-rabbitmq",
        )
        await backend.send(spore, "agent.receiver")
        await asyncio.wait_for(delivered.wait(), timeout=15)
        assert received and received[0].knowledge == spore.knowledge
        return {"published": True, "consumed": True, "native_spore": True}
    finally:
        await backend.shutdown()


def certify_otlp() -> dict:
    """Export a completed span to a real OTLP HTTP collector."""
    endpoint = require_environment("OTLP_HTTP_ENDPOINT")["OTLP_HTTP_ENDPOINT"]
    exporter = OTLPExporter(endpoint)
    exported = exporter.export_spans(
        [
            {
                "trace_id": "0123456789abcdef0123456789abcdef",
                "span_id": "0123456789abcdef",
                "name": "praval.certification.services",
                "kind": "CLIENT",
                "start_time": datetime.now().isoformat(),
                "end_time": datetime.now().isoformat(),
                "attributes": {"exact_wheel": True},
                "events": [],
                "status": "ok",
            }
        ]
    )
    assert exported
    return {"exported": True, "endpoint_configured": True}


async def main() -> None:
    """Run every real service integration and write evidence."""
    evidence = {
        "filesystem": await certify_filesystem(),
        "postgresql": await certify_postgresql(),
        "redis": await certify_redis(),
        "minio": await certify_minio(),
        "qdrant": await certify_qdrant(),
        "rabbitmq": await certify_rabbitmq(),
        "otlp": certify_otlp(),
    }
    write_json_artifact("services.json", evidence)
    print("CERTIFIED: real storage, transport, and OTLP services")


if __name__ == "__main__":
    asyncio.run(main())
