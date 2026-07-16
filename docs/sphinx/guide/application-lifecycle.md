# Application lifecycle

`PravalApp` gives an application one place to retain agents and shut down its
owned Reef.

```python
from praval import PravalApp

with PravalApp() as app:
    assistant = app.create_agent("assistant", provider="openai")
    print(assistant.chat("Say hello in one sentence."))
```

On exit, the app closes registered agents and shuts down its Reef. Calling
`close()` more than once is safe.

## Ownership boundary in 0.8

`PravalApp` is a lifecycle owner, not an isolated dependency container. In
particular:

- `create_agent()` retains the new agent for cleanup.
- `register_agent()` retains an existing agent for cleanup.
- the process-wide provider registry is still used by `Agent` construction.
- agent Reef convenience methods still use Praval's global Reef helpers.

Do not use multiple `PravalApp` instances as a security or tenant-isolation
boundary. True provider and Reef dependency injection is deferred.

## Errors

Creating or registering an agent after the app has closed raises
`RuntimeError`. Cleanup deliberately ignores Reef shutdown errors so all owned
agents still receive their close call.
