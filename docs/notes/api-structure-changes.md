# API Structure Changes (Planned)

This note documents likely API structure changes and potential regressions for the rearchitecture phase.

## Likely API Changes
- **ReefCore**: core transport implementation separated from `Reef` facade (public API preserved).
- **Reef split**: introduce a core transport layer and a facade API. The public `get_reef()` API should remain, but internal classes may move.
- **Decorator simplification**: `@agent` may be decomposed into smaller decorators (e.g., `@responds_to`, `@with_memory`, `@with_tools`).
- **Spore immutability**: `Spore` may become immutable to prevent cross-handler mutation.

## Potential Regressions
- **Spore mutation**: any code that mutates `spore.knowledge` in-place will break if `Spore` becomes immutable.
- **Decorator behavior**: if `@agent` responsibilities are split, callers relying on side effects (auto tool discovery, memory wiring) may need to opt in explicitly.
- **Imports/paths**: internal refactors may change import paths for advanced users referencing internal classes.

## Mitigation Strategy
- Preserve `get_reef()`, `start_agents()`, and `@agent` as compatibility shims during transition.
- Provide deprecation warnings and migration examples before removal.
- Add docstring warnings and update examples when changes land.

## Decision
- Spore will be immutable; handlers must treat spores as read-only.

## Decorator Decision
- The `@agent` decorator remains the primary simple interface and will not be split.
