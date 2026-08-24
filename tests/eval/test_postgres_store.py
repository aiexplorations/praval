"""Real PostgreSQL parity tests for the async evaluation-store contract."""

from __future__ import annotations

import asyncio
import time

import pytest

from praval.eval import OnlineEvaluationService, PostgresEvaluationStore

from .store_contract import (
    assert_all_records_round_trip,
    assert_attempt_idempotency,
    assert_concurrent_writes,
    assert_expired_lease_recovery_and_retry_exhaustion,
    assert_explicit_baseline_promotion,
    assert_job_leasing_and_duplicate_delivery,
    assert_query_filters,
    assert_result_idempotency,
)
from .test_online import _config, _observation, _suite, _wait_until
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


@pytest.mark.asyncio
async def test_job_leases_retries_and_duplicate_delivery_are_atomic(
    postgres_eval_store,
) -> None:
    await assert_job_leasing_and_duplicate_delivery(postgres_eval_store, _records())


@pytest.mark.asyncio
async def test_expired_leases_recover_and_exhausted_jobs_dead_letter(
    postgres_eval_store,
) -> None:
    await assert_expired_lease_recovery_and_retry_exhaustion(
        postgres_eval_store, _records()
    )


@pytest.mark.asyncio
async def test_request_path_is_isolated_when_postgres_is_unavailable(
    postgres_eval_store,
) -> None:
    async def processor(job, subject):
        raise AssertionError("processor must not run")

    service = OnlineEvaluationService(
        store=postgres_eval_store,
        suite=_suite(),
        processor=processor,
        config=_config(max_enqueue_attempts=2),
    )
    await service.start()
    await postgres_eval_store.close()
    postgres_eval_store.dsn = "postgresql://127.0.0.1:1/praval_unavailable"

    started = time.perf_counter()
    service.record(_observation())
    elapsed_ms = (time.perf_counter() - started) * 1000
    await _wait_until(lambda: service.stats().dropped == 1)

    assert elapsed_ms < 2
    assert service.stats().store_failures >= 2
    assert service.stats().persisted == 0
    assert await service.shutdown()
