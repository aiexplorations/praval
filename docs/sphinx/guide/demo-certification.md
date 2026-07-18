# Exact-wheel demo certification

Praval's release confidence comes from running the examples against the wheel
that CI built, rather than importing the checkout. The manifest at
`examples/manifest.toml` maps every Python example to its feature coverage,
execution mode, optional extras, services, timeout, and expected artifacts.

## Offline and service checks

Run deterministic checks locally or in normal CI with a built wheel:

```bash
python scripts/run_demos.py \
  --manifest examples/manifest.toml \
  --wheel dist/praval-0.8.0-py3-none-any.whl \
  --mode offline \
  --report-dir /tmp/praval-demo-results
```

The runner creates a temporary virtual environment, installs the supplied wheel
and the extras used by the selected demos, clears `PYTHONPATH`, and executes
from outside the checkout. It verifies the installed version and wheel hash.
Service mode expects the ephemeral PostgreSQL, Redis, RabbitMQ, MinIO, Qdrant,
and OTLP endpoints supplied by CI.

Tutorial files remain registered and are compiled on every applicable run.
Focused certification examples execute deterministic behavior for agents,
Reef and Spores, tools, memory, PDF extraction, storage, observability, MCP,
and packaging. A required demo cannot report `SKIP` or silently succeed because
credentials are missing.

## Protected live certification

Paid provider and speech calls run only from the manually dispatched
`live-demos.yml` workflow on trusted `main`, behind the protected `live-demo`
environment. The workflow retrieves the successful CI artifact for the exact
commit and never rebuilds it. It certifies all five provider families, real
HITL tool calls, and the request-based voice path:

```text
committed WAV -> OpenAI STT -> Praval agent -> OpenAI TTS (WAV) -> OpenAI STT
```

The report records the commit, wheel digest, installed version, provider/model
matrix, demo durations and usage, sanitized failures, and hashes for generated
artifacts. Secrets, static headers, commands, and environment values are
redacted from logs and reports. Two retries are allowed only for transient
network, rate-limit, or provider 5xx failures.

The live certificate is a release prerequisite. Praval Research can consume the
same wheel afterward as optional downstream integration evidence; its status is
not a framework publication gate.
