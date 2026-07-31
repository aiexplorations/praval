"""Correlation-safe Reef request/reply contracts for Praval 0.8.2."""

import asyncio
import threading
import time
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from praval.core.reef import (
    Reef,
    ReefLifecycleError,
    Spore,
    SporeType,
    get_reef,
    reset_reef,
)


@pytest.fixture
def reef():
    instance = Reef()
    yield instance
    instance.shutdown(wait=False)


def test_send_spore_routes_existing_spore_through_distributed_backend():
    backend = AsyncMock()
    backend.get_stats.return_value = {}
    instance = Reef(backend=backend)
    instance._backend_initialized = True
    spore = Spore(
        id="existing-spore",
        spore_type=SporeType.REQUEST,
        from_agent="client",
        to_agent="service",
        knowledge={"question": "ready"},
        created_at=datetime.now(),
        metadata={"tenant": "reef"},
        correlation_id="correlation-1",
        trace_id="trace-1",
        run_id="run-1",
        idempotency_key="idempotency-1",
    )

    try:
        result = instance.send_spore(spore, channel="main")
    finally:
        instance._backend_initialized = False
        instance.shutdown(wait=False)

    assert result == spore.id
    backend.send.assert_awaited_once_with(spore, "main")
    assert list(instance.get_channel("main").spores) == []


def test_send_spore_applies_authorization_and_rejects_expired_messages():
    authorized = []
    instance = Reef(
        auth_provider=lambda action, context: authorized.append((action, context))
        or True
    )
    expired = Spore(
        id="expired",
        spore_type=SporeType.RESPONSE,
        from_agent="service",
        to_agent="client",
        knowledge={"answer": "late"},
        created_at=datetime.now() - timedelta(seconds=2),
        expires_at=datetime.now() - timedelta(seconds=1),
    )

    try:
        with pytest.raises(ValueError, match="expired"):
            instance.send_spore(expired)
    finally:
        instance.shutdown(wait=False)

    assert authorized == []


def test_request_and_reply_keep_string_contracts_and_accept_full_envelope(reef):
    request_id = reef.request(
        "client",
        "service",
        {"question": "ready"},
        "main",
        60,
        priority=8,
        metadata={"tenant": "reef"},
        data_references=["filesystem://requests/1"],
        content_parts=[{"type": "text", "text": "ready"}],
        schema_version="2.0",
        correlation_id="correlation-1",
        causation_id="cause-1",
        trace_id="trace-1",
        run_id="run-1",
        idempotency_key="idempotency-1",
    )
    reply_id = reef.reply(
        "service",
        "client",
        {"answer": "yes"},
        request_id,
        "main",
        priority=7,
        metadata={"source": "service"},
        knowledge_references=["memory://answers/1"],
        correlation_id="correlation-1",
        causation_id=request_id,
        trace_id="trace-1",
        run_id="run-1",
        idempotency_key="idempotency-1",
    )

    request_spore, reply_spore = list(reef.get_channel("main").spores)
    assert isinstance(request_id, str)
    assert isinstance(reply_id, str)
    assert request_spore.priority == 8
    assert request_spore.metadata == {"tenant": "reef"}
    assert request_spore.data_references == ["filesystem://requests/1"]
    assert request_spore.correlation_id == "correlation-1"
    assert reply_spore.metadata == {"source": "service"}
    assert reply_spore.knowledge_references == ["memory://answers/1"]
    assert reply_spore.reply_to == request_id


def test_request_and_wait_handles_an_immediate_reply(reef):
    def service(request):
        reef.reply_to_request(request, {"answer": 42})

    reef.subscribe("service", service)

    response = reef.request_and_wait(
        "client",
        "service",
        {"question": "life"},
        timeout=1,
        correlation_id="correlation-1",
        trace_id="trace-1",
        run_id="run-1",
        idempotency_key="idempotency-1",
    )

    assert response.spore_type is SporeType.RESPONSE
    assert response.knowledge == {"answer": 42}
    assert response.reply_to is not None
    assert reef.get_channel("main").subscribers.get("client", []) == []


def test_concurrent_requests_to_same_agent_receive_only_their_response(reef):
    requests = []
    requests_lock = threading.Lock()

    def service(request):
        with requests_lock:
            requests.append(request)
            if len(requests) != 2:
                return
            second, first = requests[1], requests[0]
        reef.reply_to_request(second, {"answer_for": second.knowledge["token"]})
        reef.reply_to_request(first, {"answer_for": first.knowledge["token"]})

    reef.subscribe("service", service)
    results = {}

    def ask(token):
        response = reef.request_and_wait(
            "client",
            "service",
            {"token": token},
            timeout=2,
            correlation_id=f"correlation-{token}",
        )
        results[token] = response.knowledge

    threads = [
        threading.Thread(target=ask, args=("A",)),
        threading.Thread(target=ask, args=("B",)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=3)

    assert not any(thread.is_alive() for thread in threads)
    assert results == {
        "A": {"answer_for": "A"},
        "B": {"answer_for": "B"},
    }
    assert reef.get_channel("main").subscribers.get("client", []) == []


@pytest.mark.parametrize(
    "mismatch",
    [
        {"reply_to": "other-request"},
        {"from_agent": "spoofed-service"},
        {"to_agent": "other-client"},
        {"correlation_id": "other-correlation"},
        {"trace_id": "other-trace"},
        {"run_id": "other-run"},
        {"idempotency_key": "other-key"},
        {"causation_id": "other-cause"},
    ],
)
def test_request_and_wait_ignores_mismatched_responses(reef, mismatch):
    def service(request):
        values = {
            "from_agent": request.to_agent,
            "to_agent": request.from_agent,
            "reply_to": request.id,
            "correlation_id": request.correlation_id,
            "causation_id": request.id,
            "trace_id": request.trace_id,
            "run_id": request.run_id,
            "idempotency_key": request.idempotency_key,
        }
        values.update(mismatch)
        reef.send(
            values.pop("from_agent"),
            values.pop("to_agent"),
            {"answer": "spoofed"},
            spore_type=SporeType.RESPONSE,
            **values,
        )
        reef.reply_to_request(request, {"answer": "trusted"})

    reef.subscribe("service", service)

    response = reef.request_and_wait(
        "client",
        "service",
        {"question": "ready"},
        timeout=1,
        correlation_id="correlation-1",
        trace_id="trace-1",
        run_id="run-1",
        idempotency_key="idempotency-1",
    )

    assert response.knowledge == {"answer": "trusted"}


def test_correlated_notifications_arrive_before_final_response(reef):
    notifications = []

    def service(request):
        reef.notify_request(request, {"progress": 25})
        reef.notify_request(request, {"progress": 75})
        reef.reply_to_request(request, {"answer": "complete"})

    reef.subscribe("service", service)

    response = reef.request_and_wait(
        "client",
        "service",
        {"work": "start"},
        timeout=1,
        on_notification=lambda spore: notifications.append(spore.knowledge),
    )

    assert notifications == [{"progress": 25}, {"progress": 75}]
    assert response.knowledge == {"answer": "complete"}


def test_timeout_and_notification_errors_cleanup_temporary_handlers(reef):
    reef.subscribe("service", lambda request: None)

    with pytest.raises(TimeoutError, match="timed out"):
        reef.request_and_wait("client", "service", {"work": "timeout"}, timeout=0.01)

    assert reef.get_channel("main").subscribers.get("client", []) == []
    assert reef._response_waiters == {}

    def notify_then_stop(request):
        reef.notify_request(request, {"progress": 10})

    reef.subscribe("service", notify_then_stop)

    def fail_notification(_spore):
        raise RuntimeError("notification failed")

    with pytest.raises(RuntimeError, match="notification failed"):
        reef.request_and_wait(
            "client",
            "service",
            {"work": "callback"},
            timeout=1,
            on_notification=fail_notification,
        )

    assert reef.get_channel("main").subscribers.get("client", []) == []
    assert reef._response_waiters == {}


@pytest.mark.asyncio
async def test_arequest_and_wait_supports_async_notifications_and_cancellation(reef):
    notification_seen = asyncio.Event()

    def service(request):
        reef.notify_request(request, {"progress": 50})

    async def on_notification(spore):
        assert spore.knowledge == {"progress": 50}
        notification_seen.set()

    reef.subscribe("service", service)
    task = asyncio.create_task(
        reef.arequest_and_wait(
            "client",
            "service",
            {"work": "cancel"},
            timeout=10,
            on_notification=on_notification,
        )
    )
    await asyncio.wait_for(notification_seen.wait(), timeout=1)
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task

    assert reef.get_channel("main").subscribers.get("client", []) == []
    assert reef._response_waiters == {}


@pytest.mark.asyncio
async def test_sync_request_and_wait_rejects_running_event_loop(reef):
    with pytest.raises(RuntimeError, match="arequest_and_wait"):
        reef.request_and_wait("client", "service", {"question": "ready"})


def test_reply_notification_and_forward_helpers_derive_lifecycle(reef):
    expires_at = datetime.now() + timedelta(seconds=30)
    request = Spore(
        id="request-1",
        spore_type=SporeType.REQUEST,
        from_agent="client",
        to_agent="gateway",
        knowledge={"question": "ready"},
        created_at=datetime.now(),
        expires_at=expires_at,
        priority=8,
        metadata={"tenant": "reef"},
        knowledge_references=["memory://request/1"],
        data_references=["filesystem://request/1"],
        schema_version="2.0",
        correlation_id="correlation-1",
        causation_id="parent-1",
        trace_id="trace-1",
        run_id="run-1",
        idempotency_key="idempotency-1",
    )

    reply_id = reef.reply_to_request(request, {"answer": "yes"})
    notification_id = reef.notify_request(request, {"progress": 50})
    forward_id = reef.forward_request(request, "worker")

    reply, notification, forwarded = list(reef.get_channel("main").spores)
    assert reply.id == reply_id
    assert reply.spore_type is SporeType.RESPONSE
    assert notification.id == notification_id
    assert notification.spore_type is SporeType.NOTIFICATION
    for response in (reply, notification):
        assert response.from_agent == "gateway"
        assert response.to_agent == "client"
        assert response.reply_to == request.id
        assert response.causation_id == request.id
        assert response.correlation_id == request.correlation_id
        assert response.trace_id == request.trace_id
        assert response.run_id == request.run_id
        assert response.idempotency_key == request.idempotency_key
        assert response.expires_at == request.expires_at

    assert forwarded.id == forward_id
    assert forwarded.id != request.id
    assert forwarded.spore_type is SporeType.REQUEST
    assert forwarded.from_agent == "gateway"
    assert forwarded.to_agent == "worker"
    assert forwarded.reply_to is None
    assert forwarded.causation_id == request.id
    assert forwarded.correlation_id == request.correlation_id
    assert forwarded.knowledge_references == request.knowledge_references
    assert forwarded.data_references == request.data_references
    assert forwarded.expires_at == request.expires_at


def test_expired_and_late_responses_cannot_complete_inactive_request(reef):
    captured = []
    reef.subscribe("service", captured.append)

    with pytest.raises(TimeoutError):
        reef.request_and_wait(
            "client",
            "service",
            {"work": "expire"},
            expires_in_seconds=0.02,
            timeout=1,
        )

    request = captured[0]
    reef.reply(
        "service",
        "client",
        {"answer": "late"},
        request.id,
    )
    assert reef.get_channel("main").subscribers.get("client", []) == []
    assert reef._response_waiters == {}


def test_shutdown_wakes_waiter_and_removes_temporary_state(reef):
    reef.subscribe("service", lambda request: None)
    errors = []

    def wait_for_response():
        try:
            reef.request_and_wait("client", "service", {"work": "shutdown"}, timeout=10)
        except BaseException as exc:
            errors.append(exc)

    thread = threading.Thread(target=wait_for_response)
    thread.start()
    deadline = time.monotonic() + 1
    while not reef._response_waiters and time.monotonic() < deadline:
        time.sleep(0.001)

    reef.shutdown(wait=False)
    thread.join(timeout=1)

    assert not thread.is_alive()
    assert len(errors) == 1
    assert isinstance(errors[0], ReefLifecycleError)
    assert reef._response_waiters == {}


def test_reset_reef_wakes_waiter_and_replaces_clean_global_instance():
    instance = get_reef()
    instance.subscribe("service", lambda request: None)
    errors = []

    def wait_for_response():
        try:
            instance.request_and_wait(
                "client", "service", {"work": "reset"}, timeout=10
            )
        except BaseException as exc:
            errors.append(exc)

    thread = threading.Thread(target=wait_for_response)
    thread.start()
    deadline = time.monotonic() + 1
    while not instance._response_waiters and time.monotonic() < deadline:
        time.sleep(0.001)

    reset_reef()
    thread.join(timeout=1)

    assert isinstance(errors[0], ReefLifecycleError)
    assert get_reef() is not instance
    assert get_reef().get_channel("main") is not None


def test_distributed_wait_subscribes_to_requester_routing_key_before_send():
    events = []
    backend = SimpleNamespace()
    backend.get_stats = lambda: {}

    async def subscribe_handler(channel, handler):
        events.append(("subscribe", channel))
        backend.handler = handler
        return "consumer-1"

    async def send(spore, channel):
        events.append(("send", channel))
        backend.handler(
            Spore(
                id="response-1",
                spore_type=SporeType.RESPONSE,
                from_agent=spore.to_agent,
                to_agent=spore.from_agent,
                knowledge={"answer": "ready"},
                created_at=datetime.now(),
                reply_to=spore.id,
                causation_id=spore.id,
            )
        )

    async def unsubscribe_handler(handle):
        events.append(("unsubscribe", handle))

    backend.subscribe_handler = subscribe_handler
    backend.unsubscribe_handler = unsubscribe_handler
    backend.send = send
    backend.shutdown = AsyncMock()
    instance = Reef(backend=backend)
    instance._backend_initialized = True
    try:
        response = instance.request_and_wait(
            "client", "service", {"question": "ready"}, timeout=1
        )
    finally:
        instance._backend_initialized = False
        instance.shutdown(wait=False)

    assert response.knowledge == {"answer": "ready"}
    assert events == [
        ("subscribe", "agent.client"),
        ("send", "main"),
        ("unsubscribe", "consumer-1"),
    ]


def test_distributed_wait_fails_without_precise_subscription_capability():
    backend = SimpleNamespace(
        get_stats=lambda: {},
        send=AsyncMock(),
        shutdown=AsyncMock(),
    )
    instance = Reef(backend=backend)
    instance._backend_initialized = True
    try:
        with pytest.raises(RuntimeError, match="precise response subscriptions"):
            instance.request_and_wait(
                "client", "service", {"question": "ready"}, timeout=1
            )
        assert instance._response_waiters == {}
    finally:
        instance._backend_initialized = False
        instance.shutdown(wait=False)
