# Reef protocol and Spores

Reef is Praval's agent communication system. It supports local delivery and an
optional RabbitMQ backend. Agents exchange structured messages called Spores.

```python
from praval import agent, broadcast, get_reef, start_agents


@agent("researcher", provider="ollama", responds_to=["query"])
def researcher(spore):
    broadcast({"type": "finding", "text": "answer"})


start_agents(researcher, initial_data={"type": "query"})
get_reef().wait_for_completion()
get_reef().shutdown()
```

`Spore.knowledge` remains the compatibility payload. Spore V2 also supports a
separate payload, content parts, metadata, knowledge references, data
references, and lifecycle fields.

## Send an existing Spore

Use `send_spore()` when your application already has a complete Spore:

```python
spore_id = reef.send_spore(existing_spore, channel="main")
```

Reef sends that same object through authorization and the configured backend.
It keeps the Spore ID, timestamps, envelope, references, and payload. Reef
rejects a Spore that has already expired.

`send()` creates a Spore and then uses the same route. Existing positional
calls remain valid. You can also provide metadata and lifecycle fields as
keywords:

```python
spore_id = reef.send(
    "client",
    "worker",
    {"task": "summarize"},
    correlation_id="case-42",
    trace_id="trace-9",
    run_id="run-3",
    idempotency_key="summary-case-42",
    metadata={"tenant": "north"},
)
```

The `send()`, `request()`, and `reply()` methods still return the sent Spore ID.

## Compatibility request and reply

The established request and reply flow still works:

```python
request_id = reef.request("client", "worker", {"question": "ready?"})
reply_id = reef.reply(
    "worker",
    "client",
    {"answer": "yes"},
    request_id,
)
```

These methods do not wait for a response. They also do not invent lifecycle
values that the caller did not provide. This keeps older responders compatible.
When you provide correlation, trace, run, or idempotency values, include the
same values in a manual reply.

Use `reply_to_request()` when the responder has the request Spore. The helper
fills the participant, reply, correlation, trace, run, idempotency, causation,
and expiry fields:

```python
def worker(request_spore):
    reef.reply_to_request(request_spore, {"answer": "yes"})
```

The reply cannot outlive the request.

## Wait for one matched response

Use `request_and_wait()` for synchronous code:

```python
response = reef.request_and_wait(
    "client",
    "worker",
    {"question": "ready?"},
    timeout=10,
    correlation_id="case-42",
)
print(response.knowledge)
```

Use `arequest_and_wait()` in asynchronous code:

```python
response = await reef.arequest_and_wait(
    "client",
    "worker",
    {"question": "ready?"},
    timeout=10,
    correlation_id="case-42",
)
```

Both methods return the complete final response Spore. Reef subscribes before
it sends the request, so an immediate reply is not lost. A timeout raises the
built-in `TimeoutError`. Async task cancellation raises `CancelledError`.
Calling the synchronous method from a running event loop raises an error that
points to `arequest_and_wait()`.

`Agent.request_knowledge()` uses the same matched wait. It keeps its existing
`dict | None` result. It returns `None` when the wait times out.

## How Reef matches a response

Reef accepts a response or progress notification only while the request is
active and both messages are unexpired. It then checks all of these fields:

- `reply_to` must equal the request ID.
- The sender and recipient must be the reverse of the request participants.
- `correlation_id`, `trace_id`, `run_id`, and `idempotency_key` must match
  exactly. `None` is a value for this check.
- `causation_id` may be absent for an older responder. When present, it must
  equal the immediate request ID.

This prevents two concurrent requests between the same agents from consuming
each other's replies. It also rejects replies with spoofed participants or
different lifecycle values.

## Progress notifications

A responder can report progress before it sends the final response:

```python
def worker(request_spore):
    reef.notify_request(request_spore, {"progress": 50})
    reef.reply_to_request(request_spore, {"answer": "complete"})


progress = []
response = reef.request_and_wait(
    "client",
    "worker",
    {"task": "build"},
    timeout=30,
    on_notification=lambda spore: progress.append(spore.knowledge),
)
```

Only a `RESPONSE` completes the wait. A `NOTIFICATION` calls
`on_notification`. The async wait accepts either a normal callback or an async
callback. If the callback raises an error, Reef removes the temporary
subscription and passes the error to the caller.

## Forward a request

`forward_request()` creates a new request for the next agent:

```python
def gateway(request_spore):
    reef.forward_request(request_spore, "specialist")
```

The forwarded Spore has a new ID. Its sender is the agent that received the
original request. It preserves correlation, trace, run, idempotency, payload,
content parts, metadata, and references. Its causation ID points to the
received request, and its expiry never exceeds the original expiry.

When the specialist replies, it replies to the gateway. The gateway can then
use `reply_to_request()` to complete the original client request. See
`examples/017_correlated_reef_requests.py` for a complete offline example with
two concurrent requests, progress, forwarding, and cleanup.

## Cleanup and transport behavior

Reef removes each temporary wait subscription after success, timeout, callback
failure, cancellation, reset, or shutdown. Reset and shutdown wake blocked
callers with a lifecycle error.

RabbitMQ waits bind to `agent.<requester>` because direct messages use agent
routing keys. Reef waits for the queue binding and consumer to be ready before
it publishes the request. Cleanup cancels only that wait's consumer. Reef
deletes temporary queues that it created and keeps configured queues.

A custom distributed backend must support precise subscription handles before
it can use the wait APIs. Reef reports a clear error when that capability is
missing. Existing channel subscription methods remain available.

## Application responsibilities

Reef handles in-process matching and transport cleanup. Your application still
owns domain storage, retry policy, durable workflow state, and business
idempotency. Reef does not add automatic retries, exactly-once delivery, or a
durable workflow engine.

Redis is not a Reef backend. It belongs to the storage system. AMQP, MQTT, and
STOMP adapters belong to the optional secure transport layer.
