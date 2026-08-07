# Retained pilot runs

Pilot results are preserved here when they change the canonical protocol. They
must not be used as paper evidence.

## Services protocol version 1

The first services run passed its registered checks, but its slow-consumer
probe used RabbitMQ's default prefetch of 100 and a 5 ms handler delay. The
consumer absorbed all 1,000 deliveries without a visible ready-message
backlog (`max_queue_depth = 0`). The run therefore did not demonstrate the
intended backpressure boundary.

- Run ID: `praval-paper-services-canonical-20260726`
- Run manifest SHA-256:
  `6aa016926e3f839f76716b4852b00e8c4a0af8d7e74096def90932cac1cab0a8`
- Outcome: invalid pilot; excluded from claim aggregation and paper results
- Protocol change: version 2 uses prefetch 1, a 20 ms handler delay, and
  requires a positive observed queue depth
- Replacement run ID:
  `praval-paper-services-canonical-v2-20260726`
- Replacement manifest SHA-256:
  `058039f6264dadef0ebda55cb06bdee51ddae8cfd31cf06c6bf7f6c1f3309b03`
- Replacement result: passed; the slow-consumer probe observed a maximum queue
  depth of 586

The raw pilot remains outside Git at its recorded run location. This file
retains the reason for rejection and the content hashes without promoting the
pilot's samples to evidence.

## Comparative protocol version 2, first attempt

The first attempt to recreate the comparative environments under protocol
version 2 failed before any experiment ran. The sandbox could not resolve
PyPI while installing the exact-wheel environment. This is an infrastructure
failure, not a framework result.

- Run ID: `praval-paper-comparative-canonical-v2-20260726`
- Run manifest SHA-256:
  `ef55ce44fae453c6734d797af3ce1a6c1a877b08e3f0a7a6a5aef23481d70dc6`
- Sanitized install-log SHA-256:
  `d493cf3dc9147de9194c62f2feca1202b7cf22d18514d13d3be135586e1ad7e7`
- Outcome: failed before experiment execution; excluded from claim
  aggregation
- Failure: no matching dependency could be resolved after sandbox DNS
  failures

The replacement run completed with scoped network access:

- Replacement run ID:
  `praval-paper-comparative-canonical-v2b-20260726`
- Replacement manifest SHA-256:
  `4b7842861d25efa5c5ece5b6e5fc5f84ab535b182c4c1518cfc322cb3c73df26`
- Replacement result: passed all eight registered controls
