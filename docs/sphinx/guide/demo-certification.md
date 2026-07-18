# Exact-wheel demo certification

Praval runs examples against the installed wheel rather than importing the
source checkout. The manifest at `examples/manifest.toml` maps every Python
example to its features, execution mode, extras, services, timeout, and output
artifacts.

## Offline and service checks

Run deterministic checks locally or in normal CI with a built wheel:

```bash
python scripts/run_demos.py \
  --manifest examples/manifest.toml \
  --wheel dist/praval-0.8.1-py3-none-any.whl \
  --mode offline \
  --report-dir /tmp/praval-demo-results
```

The runner creates a temporary virtual environment, installs the supplied
wheel and selected extras, clears `PYTHONPATH`, and executes outside the
checkout. It verifies the installed version and wheel hash. Service mode
expects the PostgreSQL, Redis, RabbitMQ, MinIO, Qdrant, and OTLP endpoints that
normal CI starts for the job.

Tutorial files are registered and compiled on every applicable run. Focused
certification examples execute deterministic paths for agents, Reef and
Spores, tools, memory, PDF extraction, storage, observability, MCP, and
packaging. A required demo cannot report `SKIP` or silently pass because a
credential is missing.

## Optional real OpenAI checks

Developers can supply their own OpenAI key and model names. These checks call
paid APIs and can incur charges. They are not required to install or use the
framework.

```bash
export OPENAI_API_KEY="your-key"
export PRAVAL_OPENAI_MODEL="your-model"
export PRAVAL_OPENAI_TRANSCRIPTION_MODEL="your-transcription-model"
export PRAVAL_OPENAI_TTS_MODEL="your-tts-model"
export PRAVAL_OPENAI_TTS_VOICE="your-voice"
export PRAVAL_DEMO_REPORT_DIR="$PWD/evidence/live-openai"

python examples/certification/live_hitl.py
python examples/certification/live_voice_roundtrip.py
```

The HITL check requires a real model to call an approval-protected tool. It
tests approve, edit, reject, SQLite persistence, and resume from another
process. The voice check runs this request-based path:

```text
committed WAV -> OpenAI STT -> Praval agent -> OpenAI TTS -> OpenAI STT
```

The voice check validates the input and output WAV files, transcript keywords,
model response, and round-trip speech. It writes media and sanitized JSON
evidence to `PRAVAL_DEMO_REPORT_DIR`. It is not a persistent realtime audio
session.

## Optional all-provider workflow

The `live-demos.yml` workflow has `workflow_dispatch` as its only trigger. It
runs from trusted `main` and uses the `live-demo` GitHub Environment. Configure
these environment secrets:

- `OPENAI_API_KEY`
- `ANTHROPIC_API_KEY`
- `COHERE_API_KEY`
- `GEMINI_API_KEY`
- `OPENAI_COMPATIBLE_BASE_URL`
- `OPENAI_COMPATIBLE_API_KEY`

Configure the matching `PRAVAL_<PROVIDER>_MODEL` environment variables plus
the OpenAI and Gemini embedding models, OpenAI transcription model, OpenAI TTS
model, and TTS voice listed in the workflow. The workflow retrieves the
successful CI wheel for the selected commit and never rebuilds it.

The report records the commit, wheel digest, installed version, provider and
model matrix, durations, usage, sanitized failures, and hashes for generated
artifacts. Secrets and configured endpoints are redacted. Two retries are
allowed only for transient network, rate-limit, or provider 5xx failures.

Live results are useful compatibility evidence, but they are not a publication
gate for this framework patch release. Praval Research can consume the same
wheel as optional downstream integration evidence.
