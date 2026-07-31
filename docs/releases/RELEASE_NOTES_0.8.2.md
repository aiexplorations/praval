# Praval 0.8.2

Praval 0.8.2 adds correlation safe request and reply waits to Reef. It keeps
the public request and reply contracts from Praval 0.7.22 and 0.8.1.

## Highlights

- `Reef.send_spore()` sends an existing Spore through authorization and the
  configured backend without rebuilding it.
- `request_and_wait()` and `arequest_and_wait()` return the complete matched
  response Spore.
- Waits subscribe before dispatch, support progress callbacks, and remove
  temporary state after every exit path.
- Reef matches the request ID, reversed participants, correlation ID, trace ID,
  run ID, idempotency key, causation, and expiry.
- `reply_to_request()`, `notify_request()`, and `forward_request()` derive the
  lifecycle fields that connect a request chain.
- `Agent.request_knowledge()` uses the safe wait and keeps its existing
  `dict | None` result.
- RabbitMQ cleanup now cancels one consumer at a time. It deletes temporary
  queues that Praval owns and keeps configured queues.
- Native AMQP messages preserve arbitrary Spore metadata, payloads, content
  parts, and both reference lists.

## Compatibility

Existing positional calls to `send()`, `request()`, and `reply()` remain valid.
These methods still return the sent Spore ID. Their new Spore fields are
keyword options.

Older replies may omit `causation_id`. A waited reply still needs the correct
request ID and reversed participants. Correlation, trace, run, and idempotency
values must match exactly, including `None`.

`Agent.request_knowledge()` still returns `None` on timeout. Direct users of
the new wait methods receive the built-in `TimeoutError`.

## Lifecycle and failure behavior

Reef removes temporary wait handlers and backend consumers after success,
timeout, callback failure, async cancellation, reset, or shutdown. Reset and
shutdown wake blocked callers with a lifecycle error.

The synchronous wait cannot run inside an active event loop. Async code must
use `arequest_and_wait()`.

A custom distributed backend must support precise subscription handles to use
the new wait methods. This requirement prevents a timeout from disconnecting
other consumers. Existing channel subscription methods are unchanged.

## Scope

This patch does not add automatic retries, durable workflows, domain storage,
exactly once delivery, or an iterator based streaming API. Applications still
own those policies and state.

The offline example at `examples/017_correlated_reef_requests.py` shows
concurrent requests, progress notifications, forwarding, and cleanup. The
[Reef guide](../sphinx/guide/reef-protocol.md) covers sync and async use.

## Release evidence

The release process creates the exact wheel, `build-manifest.json`,
`SHA256SUMS`, coverage reports, offline and service certification reports, and
the documentation manifest. The notes do not copy test totals, coverage
percentages, durations, or artifact hashes because CI records those values for
the exact release commit.
