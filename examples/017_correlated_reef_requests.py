"""Offline correlation-safe Reef requests with progress and forwarding."""

from __future__ import annotations

import json
import threading
from typing import Dict, List

from praval.core.reef import Reef, Spore, SporeType


def main() -> None:
    reef = Reef()
    originals: Dict[str, Spore] = {}
    progress: Dict[str, List[int]] = {}
    results: Dict[str, str] = {}
    state_lock = threading.Lock()

    def gateway(spore: Spore) -> None:
        if spore.spore_type is SporeType.REQUEST:
            correlation_id = spore.correlation_id
            assert correlation_id is not None
            with state_lock:
                originals[correlation_id] = spore
            reef.notify_request(spore, {"progress": 20})
            reef.forward_request(spore, "worker")
            return

        if spore.spore_type is SporeType.RESPONSE:
            correlation_id = spore.correlation_id
            assert correlation_id is not None
            with state_lock:
                original = originals.pop(correlation_id)
            reef.notify_request(original, {"progress": 80})
            reef.reply_to_request(original, spore.knowledge)

    def worker(spore: Spore) -> None:
        reef.reply_to_request(
            spore,
            {"answer": f"processed-{spore.knowledge['token']}"},
        )

    reef.subscribe("gateway", gateway)
    reef.subscribe("worker", worker)

    def request_work(token: str) -> None:
        notifications: List[int] = []
        response = reef.request_and_wait(
            "client",
            "gateway",
            {"token": token},
            timeout=2,
            correlation_id=f"demo-{token}",
            trace_id="offline-demo",
            on_notification=lambda spore: notifications.append(
                spore.knowledge["progress"]
            ),
        )
        with state_lock:
            progress[token] = notifications
            results[token] = response.knowledge["answer"]

    threads = [
        threading.Thread(target=request_work, args=(token,))
        for token in ("alpha", "beta")
    ]
    try:
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=3)

        assert not any(thread.is_alive() for thread in threads)
        assert results == {
            "alpha": "processed-alpha",
            "beta": "processed-beta",
        }
        assert progress == {"alpha": [20, 80], "beta": [20, 80]}
        assert reef._response_waiters == {}
        assert reef.get_channel("main").subscribers.get("client", []) == []
        print(json.dumps({"progress": progress, "results": results}, sort_keys=True))
    finally:
        reef.shutdown(wait=False)


if __name__ == "__main__":
    main()
