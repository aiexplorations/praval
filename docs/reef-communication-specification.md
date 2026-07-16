# Reef and Spores

Reef is Praval's agent-to-agent delivery substrate. It supports in-process
delivery and an optional RabbitMQ distributed backend. Agents exchange
structured messages called Spores.

```python
from praval import agent, broadcast, start_agents, get_reef

@agent("researcher", provider="ollama", responds_to=["query"])
def researcher(spore):
    broadcast({"type": "finding", "text": "answer"})

start_agents(researcher, initial_data={"type": "query"})
get_reef().wait_for_completion()
get_reef().shutdown()
```

`Spore.knowledge` is preserved for compatibility. V2 payload fields can be used
alongside it where available, but handlers should continue to tolerate legacy
spores.

Redis is not a Reef backend; it belongs to the storage system. AMQP, MQTT, and
STOMP adapters belong to the optional secure transport layer. Applications are
responsible for correlation, idempotency, bounded retry policy, terminal
results, and shutdown.
