# Reef And Spores

The Reef is Praval's in-process communication substrate. Agents exchange
structured messages called spores.

```python
from praval import agent, broadcast, start_agents, get_reef

@agent("researcher", responds_to=["query"])
def researcher(spore):
    broadcast({"type": "finding", "text": "answer"})

start_agents(researcher, initial_data={"type": "query"})
get_reef().wait_for_completion()
get_reef().shutdown()
```

`Spore.knowledge` is preserved for compatibility. V2 payload fields can be used
alongside it where available, but handlers should continue to tolerate legacy
spores.
