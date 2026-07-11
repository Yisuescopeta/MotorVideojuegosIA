# Model Router

Clasificar despues de RECON y antes de TEST CONTRACT. Evaluar `risk_level`,
`reasoning_required`, `subsystem`, `critical_files`, `public_contract_changes`,
`serialization_changes`, `runtime_authoring_risk` y `previous_failed_cycles`.

- `simple`: `test_strategist_fast`, `planner_fast`, `builder_fast`, `code_reviewer_fast`.
- `normal`: `test_strategist`, `planner`, `builder`, `code_reviewer`.
- `complex`: `test_strategist_deep`, `planner_deep`, `builder_deep`, `code_reviewer_deep`.
- `critical`: `test_strategist_deep`, `planner_deep`, `builder_deep`, `code_reviewer_deep`.

Tratar como critical: contrato publico, serializacion, migracion, Scene,
World.clone, runtime/authoring, EngineAPI, SceneManager, fisica, legacy_aabb,
export pipeline, component registry, relajacion potencial de tests, segundo
ciclo tras fallo importante o cambio arquitectonico multiarchivo.

Un fallo no trivial de validator eleva planner y reviewer a deep. Un `must_fix`
activa reviewer deep. Builder no deep que detecte complejidad critica bloquea y
pide replanificacion deep. Recalcular route al inicio de cada fase larga.

Modelos Codex configurados: fast `gpt-5.6-terra`/low; standard
`gpt-5.6`/high; deep `gpt-5.6`/xhigh. No reutilizar IDs OpenCode.
