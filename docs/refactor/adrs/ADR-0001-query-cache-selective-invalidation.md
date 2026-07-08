# ADR-0001 - ECS query cache selective invalidation

## Estado

Accepted

## Contexto

`World.get_entities_with()` cached component-query results, but component add/remove paths previously cleared the whole component-query cache. This made unrelated cached queries cold after every component membership change.

Protected constraints apply because `engine/ecs/world.py` is a critical ECS file. The change must stay internal, keep public behavior, and remain Python-only.

## Decision

Invalidate only cached query keys that include the component type whose membership changed. Keep a full cache clear for full index rebuild paths. Add internal hit, miss, and invalidation counters for measurement only.

## Consecuencias

- Unrelated component-query cache entries survive membership changes.
- Public `World` API remains unchanged.
- Tests now cover selective invalidation and unrelated cache preservation.
- Internal counters must not be treated as public API.

## Alternativas consideradas

- Keep global invalidation: lower risk, but leaves measured cache churn unresolved.
- Move query cache to Rust: rejected because this is an algorithmic Python issue and Rust is forbidden before stronger benchmarks and equivalence gates.
