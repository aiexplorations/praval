# Correlation-Safe Reef Request/Reply Design

**Date:** 2026-07-31  
**Target release:** Praval 0.8.2  
**Issue:** [#23](https://github.com/aiexplorations/praval/issues/23)

## Context

`Spore` already carries request/reply lifecycle fields, but `Reef.send()`,
`request()`, and `reply()` cannot populate the complete envelope.
`Agent.request_knowledge()` waits for the first response with matching
participants, so simultaneous requests to the same agent can consume the same
response. Applications can work around this with `reply_to`, temporary
subscriptions, and direct `ReefChannel` access, but that duplicates lifecycle
logic and bypasses configured distributed backends.

The 0.8.2 change is additive. Existing `send()`, `request()`, and `reply()`
callers retain their positional arguments and string return values. The new
wait operations return the complete response `Spore`; the legacy Agent
convenience method continues to return response knowledge or `None`.

## Public API

`Reef.send_spore(spore, channel=None)` is the single public routing path for an
existing Spore. It applies authorization, rejects expired messages, validates
the channel, and selects local or configured distributed delivery without
changing the Spore.

`send()`, `request()`, and `reply()` accept keyword-only lifecycle, payload,
metadata, content-part, and reference fields, construct a Spore, and delegate
to `send_spore()`. Their return contract remains the sent Spore ID.

`request_and_wait()` and `arequest_and_wait()` register a response listener
before dispatch and return the final response Spore. They raise `TimeoutError`
on timeout. The asynchronous method preserves `CancelledError`. A synchronous
call from a running event loop is rejected with guidance to use the async
method. Both accept an `on_notification` callback for correlated
`NOTIFICATION` Spores.

`reply_to_request()`, `notify_request()`, and `forward_request()` derive
participants and lifecycle metadata from a received request. Forwarding
creates a new request ID, records the received request as its cause, preserves
the correlation/trace/run/idempotency context, and cannot extend the received
request's expiry.

## Correlation Rules

A final response or progress notification belongs to a request only when:

- it and the request are unexpired;
- `reply_to` equals the request ID;
- sender and recipient reverse the request participants;
- correlation, trace, run, and idempotency fields exactly match, including
  `None`; and
- causation is absent for a legacy reply or equals the immediate request ID.

These rules keep legacy `reply()` calls compatible because their optional
lifecycle fields remain `None`, while callers that supply a lifecycle envelope
receive strict matching for every supplied field. Notifications invoke the
callback but never complete the waiter.

## Waiter and Subscription Lifecycle

Reef owns an internal, locked waiter registry. A waiter contains the request,
completion primitive, handler, subscription handle, and terminal error/result.
Registration finishes before dispatch. Cleanup is idempotent and runs in a
`finally` block after success, timeout, callback failure, cancellation, reset,
or shutdown. Reset and shutdown actively wake blocked waiters.

Local delivery removes only the temporary handler from `SubscriptionManager`.
Distributed delivery uses an opaque handler-specific backend subscription.
RabbitMQ response listeners subscribe to `agent.<requester>` because direct
messages use agent routing keys. A custom distributed backend that does not
support precise subscription handles fails clearly for the new wait APIs
instead of disconnecting unrelated consumers.

AMQP subscriptions retain queue and consumer ownership. Cleanup cancels the
specific consumer, deletes only temporary transport-owned queues, and never
deletes a preconfigured queue. Transport shutdown cancels all remaining
subscriptions.

## Serialization

Scalar lifecycle fields remain AMQP headers. Arbitrary JSON-safe Spore metadata
is added to the existing V2 body envelope alongside payload, content parts,
and reference lists. Knowledge-only messages with no V2 envelope fields keep
their legacy body shape. JSON and AMQP round trips reconstruct the complete
request/reply envelope.

## Compatibility and Boundaries

`Agent.request_knowledge()` delegates to the safe Reef primitive, extracts
`response.knowledge`, and converts `TimeoutError` to `None`.

The feature does not add durable workflows, retries, job storage, exactly-once
business behavior, or an iterator streaming API. Applications still own
domain idempotency, retry policy, persistence, and terminal business states.

## Verification

Focused tests cover immediate replies, concurrent and out-of-order requests,
spoofed or mismatched messages, expiration, late responses, progress
notifications, forwarding, sync/async cleanup, reset/shutdown, legacy
compatibility, distributed routing, and AMQP consumer ownership. The exact
wheel offline certificate and a runnable example exercise the public API.

## Hosted Documentation

After the 0.8.2 package documentation passes its exact-wheel checks, stage the
verified Sphinx artifact into the companion `~/Github/praval-ai` repository:

- add immutable `docs/v0.8.2/` documentation and replace `docs/latest/` with
  the same verified artifact;
- update `docs/versions.json`, the documentation landing page, and the website
  version badge to identify 0.8.2 as current while retaining older versions;
- add a concise 0.8.2 release article that introduces correlation-safe
  request/reply behavior and links to the canonical Reef guide and issue; and
- validate internal links and preview the static site without changing its
  deployment configuration.

The companion repository already contains unrelated blog work. Its changes
must remain unmodified and unstaged; the 0.8.2 documentation update belongs on
a dedicated `codex/praval-082-docs` branch.
