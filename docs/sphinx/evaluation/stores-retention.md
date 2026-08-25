# Stores and retention

`SQLiteEvaluationStore` is for local development and CI. It applies versioned
migrations, uses transactional idempotent writes, and supports the complete
record/query/baseline/job contract. Keep one process owner and do not mount one
SQLite file into multiple containers.

`PostgresEvaluationStore` is for shared CI, services, and online evaluation.
Install the storage extra, keep the DSN in the environment variable named by
`eval.stores.postgres.dsn_env`, and run `await store.migrate()` before workers.
Migrations use an advisory transaction lock and are safe under concurrent
startup.

Both stores persist cases, suites, runs, subjects, metric results, judge
results, gate results, terminal summaries, baselines, jobs, and attempts. They
enforce immutable natural identities: replaying identical data returns the
stored record; replaying a conflicting payload raises
`EvaluationConflictError`.

Complete candidate content is not an evaluation record. `ContentReference`
holds its hash, byte size, kind, media type, and application URI. If a content
store is enabled, apply separate encryption, access control, regional, and
retention policy. Deleting referenced content can preserve aggregate evaluation
records while intentionally making evidence unavailable.

Praval v0.8.3 does not run automatic evaluation-record retention. Applications
should partition or delete runs, subjects, results, attempts, and content under
one reviewed policy while retaining baseline referential integrity. Always
close the store on shutdown.
