"""Real PostgreSQL fixture for evaluation-store parity tests."""

from __future__ import annotations

import sys
from collections.abc import Iterator

import pytest
import pytest_asyncio

from praval.eval import PostgresEvaluationStore


@pytest.fixture(scope="session")
def eval_postgres_dsn() -> Iterator[str]:
    if sys.gettrace() is not None:
        pytest.skip(
            "asyncpg 0.31 crashes during traced connection setup; "
            "run this real-database suite without coverage"
        )
    try:
        from testcontainers.postgres import PostgresContainer
    except ImportError:
        pytest.skip("testcontainers[postgres] is not installed")

    container = PostgresContainer("postgres:15")
    try:
        with container as postgres:
            host = postgres.get_container_host_ip()
            port = postgres.get_exposed_port(5432)
            yield (
                f"postgresql://{postgres.username}:{postgres.password}@"
                f"{host}:{port}/{postgres.dbname}?sslmode=disable"
            )
    except Exception as exc:
        message = str(exc).lower()
        if "docker" in message or "permission denied" in message:
            pytest.skip(f"Docker is unavailable for PostgreSQL tests: {exc}")
        raise


@pytest_asyncio.fixture
async def postgres_eval_store(eval_postgres_dsn: str):
    store = PostgresEvaluationStore(eval_postgres_dsn, min_pool_size=1, max_pool_size=5)
    await store.migrate()
    pool = await store._get_pool()
    async with pool.acquire() as connection:
        await connection.execute(
            """
            TRUNCATE TABLE
                evaluation_attempts,
                evaluation_jobs,
                evaluation_baselines,
                evaluation_results,
                evaluation_gate_results,
                evaluation_judge_results,
                evaluation_metric_results,
                evaluation_subjects,
                evaluation_runs,
                evaluation_suites,
                evaluation_cases
            """
        )
    yield store
    await store.close()
