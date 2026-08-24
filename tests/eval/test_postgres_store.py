"""Real PostgreSQL parity tests for the async evaluation-store contract."""

from __future__ import annotations

import asyncio

import pytest

from praval.eval import PostgresEvaluationStore

from .store_contract import (
    assert_all_records_round_trip,
    assert_attempt_idempotency,
    assert_concurrent_writes,
    assert_explicit_baseline_promotion,
    assert_query_filters,
    assert_result_idempotency,
)
from .test_sqlite_store import _records

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_migrations_are_concurrent_and_idempotent(eval_postgres_dsn: str) -> None:
    stores = [PostgresEvaluationStore(eval_postgres_dsn) for _ in range(3)]
    try:
        for store in stores:
            await store._get_pool()
        await asyncio.gather(*(store.migrate() for store in stores))
        assert {await store.schema_version() for store in stores} == {1}
    finally:
        await asyncio.gather(*(store.close() for store in stores))


@pytest.mark.asyncio
async def test_all_e1_records_round_trip(postgres_eval_store) -> None:
    await assert_all_records_round_trip(postgres_eval_store, _records())


@pytest.mark.asyncio
async def test_query_filters_return_only_matching_records(postgres_eval_store) -> None:
    await assert_query_filters(postgres_eval_store, _records())


@pytest.mark.asyncio
async def test_duplicate_result_is_idempotent_but_conflict_is_rejected(
    postgres_eval_store,
) -> None:
    await assert_result_idempotency(postgres_eval_store, _records())


@pytest.mark.asyncio
async def test_concurrent_distinct_writes_are_not_lost(postgres_eval_store) -> None:
    await assert_concurrent_writes(postgres_eval_store, _records())


@pytest.mark.asyncio
async def test_baseline_changes_only_through_explicit_promotion(
    postgres_eval_store,
) -> None:
    await assert_explicit_baseline_promotion(postgres_eval_store, _records())


@pytest.mark.asyncio
async def test_attempt_number_is_idempotent_per_job(postgres_eval_store) -> None:
    await assert_attempt_idempotency(postgres_eval_store, _records())
