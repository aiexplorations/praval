# Application configuration reference

Praval uses an immutable schema-versioned `PravalConfig`. Precedence is typed
defaults, an explicit or nearest `praval.toml`, supported environment
variables, then explicit API overrides. Unknown fields and invalid references
raise `PravalConfigurationError`.

## Root and application

`schema_version` is the integer `1`. `[app]` fields are `service_name`
(string, default `praval`), optional `service_version`, and optional
`deployment_environment`. Enabled observability requires a non-blank service
name.

## Model profiles

Each `[models.<name>]` requires `provider` and `model`. Optional `temperature`
is a float and `max_output_tokens` is a positive integer. Environment variables
`PRAVAL_DEFAULT_PROVIDER` and `PRAVAL_DEFAULT_MODEL` set the `models.default`
profile. Provider credentials remain in their provider-specific environment
variables and are not configuration fields.

## Embedding profiles

Each `[embeddings.<name>]` has required non-empty `provider` and `model`,
optional positive `dimensions`, optional non-empty `base_url`, and optional
`api_key_env`. `api_key_env` names an uppercase environment variable; it does
not contain the key.

## Agent profiles

Each `[agents.<name>]` may set `model`, `system_message`, `tools`,
`memory_enabled`, `memory_namespace`, and `max_tool_rounds` (default 8, from 1
through 1000). `model` must reference `[models]`. Enabled memory requires a
non-empty dedicated namespace.

At runtime `resolve_agent_profile()` combines the named model and agent profile
with explicit overrides into `ResolvedAgentConfig`: `name`, `provider`,
`model`, optional temperature/output bound, optional system message, tool
names, memory settings, and tool-round bound.

## Observability and evaluation

The complete `[observability]`, `[observability.otlp]`, and
`[observability.local]` fields are in {doc}`../observability/configuration`.
The complete `[eval]`, stores, RAGAS, judges, suites, gates, and online fields
are in {doc}`../evaluation/configuration`.

## Discovery and environment

Set `PRAVAL_CONFIG_FILE` to an explicit file. Otherwise `discover_config_path()`
searches from the current path toward the filesystem root for `praval.toml` and
does not load a hidden home default. Supported environment overrides are
documented on the relevant section page. Values not explicitly supported by
the typed loader are not silently interpreted.

```python
from praval import load_config

config = load_config(
    "praval.toml",
    overrides={"app": {"deployment_environment": "test"}},
)
resolved = config.resolve_agent_profile("quality_evaluator")
```

Loading reads configuration only. It does not construct agents, providers,
stores, exporters, evaluator workers, or other runtime resources.
