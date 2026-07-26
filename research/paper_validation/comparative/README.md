# Controlled framework comparison

This benchmark uses one 12-question JSONL dataset, one two-stage call
contract, and one measurement proxy. Praval 0.8.1, LangGraph 1.2.9, and
CrewAI 1.15.6 run in separate virtual environments.

The deterministic track gives every model call the same configured delay and
returns fixture-derived JSON. It isolates workflow and coordination overhead;
it does not measure model quality. The optional OpenAI track uses the same
schedule, prompts, two-call budget, temperature, and structured-output schema.
It runs only when `OPENAI_API_KEY` and
`PRAVAL_COMPARISON_OPENAI_MODEL` are set.

The controller randomizes question order and rotates framework order. It
records setup time, the first warm invocation, steady-state workflow time,
model time, call count, correctness, failures, returned model IDs, usage, and
resolved dependency locks. Each isolated environment is installed against a
hash-registered constraint file under `locks/`, then checked against it.
Paper results must use measured rows only and keep cold-start values separate.
