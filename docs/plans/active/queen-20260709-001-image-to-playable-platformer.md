# Queen Execution Plan: Image-to-Playable Platformer

Status: active
Authority: operational-plan
Task ID: queen-20260709-001
Created at: 2026-07-09T00:00:00
Updated at: 2026-07-11T00:00:00
Mode: long-task-plan

## Objective

Experimental pipeline reference image -> deterministic vision analysis -> GameSpec2D -> OpenGame Scene -> deterministic visible semantic representation -> real off-screen render capture -> playtest smoke -> bounded hardening -> documentation sync -> explicit exit decision.

## Non-goals

- No commercial cloning/assets.
- No arbitrary Python generation.
- No direct Scene JSON mutation when API/CLI exists.
- No SceneManager/EngineAPI/serialization/runtime/editor/physics changes in early phases.
- No mandatory OpenCV/supervision.
- No test relaxation.
- No automated reference-vs-render visual comparison in this MVP closure.
- No pixel-match, RGB-error, block-similarity, occupancy-similarity, or visual-similarity scores in Phase 8B.

## Current phase

- Name: Phase 8A.2 — Deterministic off-screen scene capture
- phase_status: blocked
- task_status: partial
- Decision: block before implementation because required planner result is missing
- Allowed files: `engine/vision/render_capture.py`, `engine/vision/__init__.py`, `motor/cli.py`, `motor/cli_core.py`, `engine/ai/registry_builder.py`, focused vision/CLI tests and fixtures, required canonical discoverability docs, this active plan
- Forbidden files: protected game/render/EngineAPI/Scene/serialization/runtime/editor/physics surfaces, component registry, HeadlessGame, Pyray shim/stub, archive docs
- Test contract: test-contract-queen-20260709-001-phase-8a2-render-capture
- Verdict: sufficient
- Next phase: resume Phase 8A.2 planning only after a valid structured `planner_deep` result is available

## Authorized Phase 8 decision

Authorize a vision-local off-screen render capture contract using a hidden
Raylib graphics context and a dedicated RenderTexture.

The capture is not guaranteed to be displayless on every operating system.
When a real graphics backend or context is unavailable, the command must fail
with a structured actionable error.

The Pyray stub must never produce a successful capture.

Automated visual comparison is deferred because the current deterministic
semantic representation is not visually comparable enough to the reference
image for meaningful similarity metrics.

## Blocked conditions

Stop the plan immediately if any of these are true. These are machine-checkable blockers.

- `required_subagent_result_missing`: any required subagent result is missing, empty, truncated, or not valid JSON/parseable.
- `test_contract_missing_or_insufficient`: TEST CONTRACT is absent, contradicts the plan, or omits required minimum commands/tests for the active phase.
- `protected_module_write_required_outside_explicit_critical_phase`: a protected module write becomes necessary while the current phase is not explicitly marked `critical-write-allowed=true`.
- `dependency_becomes_mandatory`: progress requires OpenCV, supervision, or native tooling instead of an optional/fallback path.
- `validator_failure_or_minimum_commands_unavailable`: validator fails, or any minimum required command cannot run successfully in the current environment.
- `code_reviewer_must_fix`: code-reviewer returns any `must_fix` item.
- `ai_friendliness_below_threshold`: applicable AI-friendliness score is `< 90`, or `must_fix` is non-empty.
- `direct_scene_json_mutation_required`: the implementation requires direct Scene JSON mutation instead of a public API/CLI route.
- `cli_json_mode_noisy_or_unparseable`: a CLI JSON command emits noisy output, mixed streams, or output that cannot be parsed as JSON.
- `contract_or_regression_failure`: official contract, serialization, Scene v2, EngineAPI, or regression tests fail.
- `commercial_or_uncleared_asset_required`: a commercial asset or any uncleared asset/license would be needed to proceed.

Blocked response rule: keep `phase_status` unchanged for the current phase, keep `task_status: partial`, record the blocker, and do not advance.

## Model route

task_complexity complex; risk_level high; reasoning_required high; selected_agents test-strategist-deep/planner-deep/builder-deep/code-reviewer-deep; fixed_agents context-recon/validator/documenter/ai-friendliness/committer; reason multi-phase experimental IA/CLI/docs pipeline with protected-contract risk.

## Recon summary

- Initial continuation recon id: `recon-queen-20260709-001`; status completed; 18/18 required findings confirmed.
- Current branch: `fix/ciclosReina`; starting continuation HEAD: `9db99afe71d917eca9106578ba067447d3aaae87`; worktree clean.
- Commits after Phase 7: `cd3da76` and `99fa389` are unrelated migration/revert with net zero; `9db99af` is an attributed but incomplete Codex Queen migration, unrelated to vision, preserved without reset.
- `HeadlessGame.run()` is unbounded logic-only execution and is forbidden for capture.
- `RenderSystem.render()` returns before drawing without a ready window and exposes the required public `viewport_size` / `allow_render_targets=False` route.
- Public existing route is sufficient: `EngineAPI.load_level`, `EngineAPI.game.world`, `EngineAPI.game.render_system`, and public `RenderSystem.render()`.
- Semantic `Sprite` payloads have empty textures; solid cells have no visual component; `Polygon2D` is registered, serializable, and rendered without assets.
- Real installed Pyray backend exposes `FLAG_WINDOW_HIDDEN` and required texture/image functions; local stub advertises `_IS_STUB=True`, simulates image functions, and must be rejected explicitly.
- No protected module modification is required.
- Real hidden-context initialization, foreground capture, and cleanup remain unproven until Phase 8A.2 smoke.
- Preexisting Queen migration defect: `.codex` role config/tests reference missing `result_schemas.json` and `validate_result.py`; outside vision scope.

## TEST CONTRACT

- Contract id: test-contract-queen-20260709-001
- Verdict: sufficient
- Phase 0 minimum commands:
  - `git diff --`
  - `git diff --cached --`
  - `git remote show origin`
  - `git branch -r --sort=-committerdate`
  - `git status --short --branch`
  - `py -m motor doctor --project . --json`
- Phase 1 required tests:
  - `py -m unittest discover -s tests`
  - targeted tests for any new experimental GameSpec2D surface
  - governance checks if docs/plans or prompts change

### Phase 8A.1 TEST CONTRACT

- Contract id: `test-contract-queen-20260709-001-phase-8a1-semantic-visuals`
- Task type: experimental tooling
- Verdict: sufficient
- Authority: `tests/test_vision_gamespec_to_scene.py`, `tests/test_vision_gamespec2d.py`, `tests/test_polygon2d.py`, `tests/test_official_contract_regression.py`, `tests/test_repository_governance.py`
- Required changes: assert centered `polygon_payload`; explicit stable RGBA palette for all ten semantic types; every semantic prefab keeps `Sprite` and gains `Polygon2D`; solid cells gain centered `Polygon2D`; `REGISTERED_COMPONENTS_USED` includes `Polygon2D`; public save/load round-trip preserves polygon payload; deterministic ordering remains unchanged.
- Tests that must not be relaxed: existing GameSpec projection/load/determinism/public-route tests, GameSpec2D allowed-type/round-trip tests, Polygon2D serialization tests, official contract regression, repository governance.
- Minimum commands:
  - `py -m unittest tests.test_vision_gamespec_to_scene tests.test_vision_gamespec2d -v`
  - `py -m unittest tests.test_polygon2d -v`
  - `py -m unittest tests.test_official_contract_regression tests.test_repository_governance -v`
  - `git diff --check`
  - protected normal/staged diff audits covering component registry, render core, EngineAPI, Scene/serialization/runtime/editor/physics, Pyray shim/stub, and archive docs
- Recommended regression: `py -m unittest tests.test_render_graph -v`; full suite at final task validation.
- Manual smoke: not required for 8A.1; public scene round-trip is automated.
- Acceptance: deterministic asset-free semantic geometry; valid RGBA; Sprite preserved; solid cells visible; serialization survives; no protected changes; validator pass; reviewer approved with no must-fix; AI audit score >= 90 with no must-fix.
- Risks: collider/geometry dimension drift, component/entity ordering drift, palette drift, omitted semantic type or solid cell, insufficient mock-only round-trip, protected scope bleed.
- Strategy evidence: all required unittest modules exist; current only local change is attributed Queen plan sync; no tests executed by strategist.

### Phase 8A.2 TEST CONTRACT

- Contract id: `test-contract-queen-20260709-001-phase-8a2-render-capture`
- Task type: experimental tooling
- Verdict: sufficient
- Authority: focused vision projection/capture/CLI tests; motor CLI and registry contracts; render target/graph/pipeline/safety tests; official/parser/registry/governance/AI coherence regressions.
- Limits: width and height must be non-bool positive integers, each <= 4096; total pixels <= 4,194,304; default background `(24, 24, 32, 255)`.
- Backend: reject `_IS_STUB=True` before EngineAPI/context/resources/files; use real symbolic `FLAG_WINDOW_HIDDEN`; preserve existing windows; verify created context becomes ready.
- Capture: public `EngineAPI.load_level`, `game.world`, `game.render_system`; dedicated RenderTexture; exact viewport; `allow_render_targets=False`; balanced texture mode; vertical flip before pixel extraction.
- Pixel contract: verify image dimensions; support sized sequences and real indexable CFFI pointers whose `len()` raises; read exactly expected count; encode direct deterministic PPM P6 and discard alpha only in output.
- File contract: same-directory temporary, validate before publication, atomic no-clobber publication, no overwrite or partials, cleanup every failure path.
- Resource contract: unload colors, Image, RenderTexture, close only owned window, shutdown EngineAPI; cleanup failures cannot stop later cleanup or hide primary errors.
- CLI/registry: `motor vision render-scene`; JSON-only stdout, nonzero errors, structured error/report, `vision:render-scene` implemented with experimental tag and honest hidden-context/backend notes.
- Required tests: new `tests/test_vision_render_capture.py`; extend vision CLI/motor CLI and controlled GameSpec fixture coverage; fake-real API, stub, window ownership, init/render/read/write/cleanup failures, PPM/determinism/foreground, dimension limits, atomic race, capability metadata.
- Minimum commands: all focused commands specified by user for vision capture/projection, CLI, render core regressions, official/parser/registry/governance/AI coherence, doctor, Ruff, mypy, diff check, and protected audit from commit `6b2a1b0`.
- Real smoke: mandatory against real backend at 256x144; require JSON parse, PPM exact payload, foreground, >1 color, cleanup, no artifacts. Report `contract_tests` and `real_backend_smoke` separately.
- Completion: Phase 8A.2 can be completed only with real smoke passed; if implementation/contracts pass but backend unavailable, remain partial; fake/stub/mock/overlay never count.
- Risks: OS/session context failure, CFFI pointer handling, unbalanced texture mode, cleanup masking errors, publication race, stdout contamination, background-only false positive, protected scope bleed.

## Continuation baseline

- `py -m unittest discover -s tests`: failed; 3602 tests, 20 failures, 1 error, 8 skipped; all classified `preexisting_failure`; zero demonstrated new regressions.
- `ruff check engine motor cli tests`: executable unavailable in PATH; equivalent `py -m ruff check engine motor cli tests` ran and failed with 25 preexisting findings (I001=23, W293=1, F401=1).
- `mypy engine motor cli`: executable unavailable in PATH; equivalent `py -m mypy engine motor cli` ran and failed with 16 preexisting errors in 5 files.
- `py -m motor doctor --project . --json`: passed; healthy, no issues or warnings.
- Queen tooling error: missing `.agents/skills/queen/references/agent_mapping.json`; preexisting from `9db99af`, unrelated to vision.
- Merge gate: closed until global CI failures are repaired in a separate task/PR and this branch is updated.
- Phase rule: focused validation must prove no new regression relative to this baseline; preexisting failures are recorded, not ignored or repaired in vision commits.

## Phase 8A.1 implementation plan

- Plan id: `plan-queen-20260709-001-phase-8a1-semantic-visuals`
- Route: one `builder_deep`; root owns only this operational plan; validator/reviewer/AI audit are read-only; committer stages explicit paths only.
- TDD red: add focused tests for exact centered geometry, full payload, literal ten-type RGBA palette, Sprite preservation, solid-cell Polygon2D, deterministic order/build, and public save/load round-trip.
- Green: add one explicit semantic palette and `polygon_payload` in `semantic_prefabs.py`; add Polygon2D to all semantic prefabs and `REGISTERED_COMPONENTS_USED`; add Polygon2D to sorted solid cells in `gamespec_to_scene.py`; preserve report representation and authoring behavior.
- Document: describe asset-free semantic geometry and limits in experimental vision pipeline; do not claim render capture or visual comparison validated.
- Validate: TEST CONTRACT minimum commands plus focused Ruff/mypy, render-graph regression, protected normal/staged diff audits.
- Rollback: revert only 8A.1 code/tests/docs; preserve Phase 7, plan history, protected modules, registry, and render core.
- Terminal: validator pass for focused contract, reviewer approved with no must-fix, AI audit score >= 90 with no must-fix, plan updated, exclusive authorized commit, clean worktree.

### Phase 8A.1 plan critique

- Verdict: approved.
- Ten types: exact key equality with `ALLOWED_ENTITY_TYPES` and literal expected RGBA values required.
- Palette: single explicit source in implementation; tests retain independent literals to detect drift.
- Geometry: exact ordered points at `±width/2`, `±height/2`; color changes cannot affect points.
- Solid cells: loaded entities must contain Transform, Collider, and Polygon2D sized from tile size.
- Round-trip: assert persisted payload after public EngineAPI load, not mocks only.
- Sprite: additive Polygon2D only; existing Sprite payload retained.
- Determinism: preserve sorted cells, entity names/order, semantic mapping, and `representation="collider_blocks"`.
- Protected scope: normal and staged audits must be empty.
- Ownership: builder cannot edit active plan; root cannot edit functional code/tests/docs.

## Phase transition rules

- `completed`: mark the phase block as `phase_status: completed` only when its acceptance checks pass and no blocked condition is active; the task still stays `task_status: partial` until the full plan finishes.
- `blocked`: stop at the current phase, do not start the next phase, and keep `task_status: partial` unless the task itself is being abandoned.
- `failed`: treat as an execution failure for the current phase; do not advance; preserve prior completed phases; keep `task_status: partial`.
- `skipped`: use only when the phase is explicitly inapplicable; document why; do not infer completion; keep `task_status: partial`.
- `not_applicable`: use only when the phase cannot apply to the current scope; document the reason and leave the task incomplete.
- `phase completed != task completed`: a completed phase never means the whole task is done; only the final exit decision can close the task.
- Never rewrite the canonical current-phase status to imply task completion.

## Plan summary

Phase 1 writes only internal GameSpec2D surfaces and the approved experiment docs; no protected module writes.
Phase 2 — Convert GameSpec2D to Scene through existing public authoring paths; tests/docs only; no protected module writes.

## Allowed / forbidden files

### Phase 0

- Allowed: `docs/plans/active/queen-20260709-001-image-to-playable-platformer.md`
- Forbidden: all code, tests, canonical docs, archive docs, `pyproject.toml`, `requirements.txt`, protected modules

### Phase 1

- Allowed: `engine/vision/**`, focused tests, `docs/vision/gamespec2d.md`, `docs/module_taxonomy.md`
- Forbidden: protected modules, canonical CLI/API docs, serialization/runtime/editor/physics changes, direct Scene JSON mutation paths

## Phases

### Phase 1 — Introduce GameSpec2D as internal experimental contract

Status: completed
Goal: define the internal experimental GameSpec2D contract and minimal tests.
Allowed files: `engine/vision/**`, focused tests, experiment docs
Forbidden files: protected modules, canonical docs, direct Scene JSON mutation
Acceptance checks: scaffold exists, tests cover shape/schema basics, no contract drift
Docs affected: experimental docs only
Risks: scope bleed into protected APIs

### Phase 2 — Convert GameSpec2D to Scene through existing public authoring paths

Status: completed
Goal: convert GameSpec2D to Scene through existing public authoring paths.
Allowed files: `engine/vision/**`, focused tests, experiment docs
Forbidden files: protected modules, canonical docs
Acceptance checks: Scene projection uses supported public authoring paths, no direct Scene JSON mutation, and the conversion remains deterministic and testable
Docs affected: experimental docs only
Risks: internal helper only, no dedicated EngineAPI wrapper/CLI yet, future discoverability docs/CLI needed, richer tilemap projection deferred

### Phase 3 — Add experimental CLI for GameSpec workflows

Status: completed
Goal: expose GameSpec workflows through the `motor` CLI in a minimal JSON-first way:
- `py -m motor vision spec validate <path> --project . --json`
- `py -m motor vision build-scene <gamespec_path> --out <scene_path> --project . --json`
Allowed files: CLI parser/registry files discovered by recon, `tests/test_vision_cli_contract.py`, `docs/cli.md`, `docs/agents.md`, `docs/vision/image_to_platformer_pipeline.md`, `START_HERE_AI.md`, this active plan
Forbidden files: EngineAPI public changes, `SceneManager`, serialization core, editor UI, physics backend, `pyproject.toml`, requirements, direct scene JSON mutation, unsafe overwrite behavior, protected modules outside the CLI surface
Acceptance checks: both commands support `--json`, fail safely, refuse unsafe overwrite paths, and remain isolated from EngineAPI/SceneManager/serialization/editor/physics changes
Docs affected: `docs/cli.md`, `docs/agents.md`, `docs/vision/image_to_platformer_pipeline.md`, `START_HERE_AI.md`, active plan
Risks: CLI discoverability drift, JSON output noise, accidental scope bleed into protected contracts; known limitations: CLI-first/no EngineAPI wrapper, Any-typed payloads, RAYLIB stderr startup noise but stdout JSON contract passes

### Phase 4 — Implement simple tile-grid and tilemap extraction without ML

Status: completed
Goal: implement deterministic tile-grid and tilemap extraction without ML.
Allowed files: `engine/vision/**`, focused tests, experiment docs
Forbidden files: protected modules, canonical docs
Acceptance checks: extraction is explicit, bounded, reproducible, and testable
Docs affected: experimental docs only
Risks: overfitting to the sample image, grid ambiguity, extraction drift

### Phase 5 — Add `vision build-platformer` MVP without object detection ML

Status: completed
Goal: add a `vision build-platformer` MVP that turns the validated image/tilemap pipeline into a playable platformer without object detection ML.
Allowed files: `engine/vision/**`, `motor/cli.py`, `motor/cli_core.py`, `engine/ai/registry_builder.py`, focused tests, `docs/cli.md`, `docs/agents.md`, `docs/vision/image_to_platformer_pipeline.md`, this active plan
Forbidden files: protected modules, serialization/runtime/editor/physics changes, direct Scene JSON mutation
Acceptance checks: build flow stays deterministic, ML-free, and routed through supported public surfaces when available
Docs affected: `docs/cli.md`, `docs/agents.md`, `docs/vision/image_to_platformer_pipeline.md`, this active plan
Risks: accidental contract bypass, scope creep into protected surfaces, image-to-game overfitting

### Phase 6 — Add optional Supervision adapter

Status: completed
Goal: add an optional Supervision adapter for the experimental pipeline without making it mandatory.
Allowed files: `engine/vision/**`, focused tests, experiment docs
Forbidden files: protected modules, canonical docs
Acceptance checks: the adapter stays optional, the fallback path remains available, and no protected contracts drift
Docs affected: `docs/vision/image_to_platformer_pipeline.md`, this active plan
Risks: dependency creep, optional-path ambiguity, scope bleed into protected contracts

### Phase 7 — Debug overlay

Status: completed
Goal: expose analysis and projection state in a deterministic PPM debug overlay.
Allowed files: `engine/vision/**`, focused tests, `docs/cli.md`, `docs/vision/image_to_platformer_pipeline.md`, `docs/agents.md`, `START_HERE_AI.md`, this active plan
Forbidden files: protected modules, direct Scene JSON mutation, serialization/runtime/editor/physics changes
Acceptance checks: overlay is optional and non-invasive; PPM-only; stdlib-only; no render/editor/runtime/EngineAPI integration; no text rendering; no partial output on failure
Docs affected: `docs/cli.md`, `docs/vision/image_to_platformer_pipeline.md`, `docs/agents.md`, `START_HERE_AI.md`, this active plan
Evidence: implementation landed as stdlib-only PPM debug overlay helper plus CLI `motor vision annotate`, registry `vision:annotate`, tests, and docs; review cycle 1 flagged non-atomic output create and cycle 2 fixed it with exclusive `open("x")`/equivalent and safe cleanup; validator cycle 2 passed focused vision, CLI, regression, governance, registry audits, and `motor doctor`; review cycle 2 approved with no findings; AI audit approved with score 90.
Risks: UI bleed into core contracts; mistaken assumptions about render/runtime integration; PPM-only, no text rendering, diagnostic-only output.

### Phase 8A.1 — Deterministic semantic visual representation

Status: completed
Goal: add asset-free deterministic `Polygon2D` geometry to semantic prefabs and directly generated solid cells while preserving existing `Sprite` payloads and authoring semantics.
Allowed files: `engine/vision/semantic_prefabs.py`, `engine/vision/gamespec_to_scene.py`, `engine/vision/__init__.py`, focused vision tests/fixtures, `docs/vision/image_to_platformer_pipeline.md`, this plan
Forbidden files: protected modules, render core, central component registry, EngineAPI, Scene/serialization/runtime/editor/physics, Pyray shim/stub, archive docs
Test contract: `test-contract-queen-20260709-001-phase-8a1-semantic-visuals`
Acceptance checks: deterministic centered geometry and stable RGBA palette; known semantics and solid cells contain `Polygon2D`; `Sprite` compatibility and entity order preserved; scene round-trip passes; protected modules unchanged; validator pass; reviewer `must_fix=[]`; AI friendliness score >= 90
Docs affected: experimental vision pipeline and this plan
Risks: prefab serialization drift; visual geometry diverging from collider dimensions; accidental protected registry/render changes
Evidence: TDD red failed only for absent palette/helper/Polygon2D; builder changed four authorized functional/test/doc files with no write-scope violation; validator passed 114 focused/regression tests and TEST CONTRACT; focused Ruff and isolated mypy passed; normal mypy retained only the 10 baseline errors from unchanged `gamespec2d.py`; protected normal/staged audits empty; independent deep review approved with no findings or must-fix; AI audit approved with score 95 and no must-fix.

### Phase 8A.2 — Deterministic off-screen scene capture

Status: blocked
Goal: capture actual OpenGame `RenderSystem` output to deterministic PPM P6 using a dedicated RenderTexture and off-screen capture using a hidden Raylib context.
Allowed files: `engine/vision/render_capture.py`, `engine/vision/__init__.py`, `motor/cli.py`, `motor/cli_core.py`, `engine/ai/registry_builder.py`, focused vision/CLI tests and fixtures, required canonical discoverability docs, this plan
Forbidden files: `engine/core/game.py`, `cli/headless_game.py`, render core/pipeline, EngineAPI, Scene/SceneManager/serialization, component registry, runtime/editor/physics, Pyray shim/stub, archive docs
Test contract: `test-contract-queen-20260709-001-phase-8a2-render-capture`
Acceptance checks: real backend required and stub rejected; safe hidden-context ownership; existing window preserved; dedicated RenderTexture/Image/colors cleanup; public scene-load/render route; vertical flip and exact deterministic PPM; bounded dimensions; no overwrite/partials; atomic publish; JSON-only stdout; experimental capability; protected modules unchanged; real backend smoke passed
Partial rule: implementation and contract tests may be complete while phase remains `partial` when real backend smoke is unavailable.
Docs affected: vision pipeline, CLI/agent discoverability, `START_HERE_AI.md`, this plan
Risks: OS graphics context unavailable; false positive from stub; resource leaks; stdout contamination; capture not displayless on every OS
Blocker: `missing_subagent_result` — `planner_deep` remained running without a result, was interrupted, and again returned no JSON after the single allowed reformulation request. Queen result-contract rules forbid delegating implementation without this required structured plan.
Implementation status: not started. No Phase 8A.2 code, tests, CLI, registry, or functional documentation changed.
Environment evidence: Windows; real site-packages Pyray available with `_IS_STUB=false`, symbolic `FLAG_WINDOW_HIDDEN`, and required functions; safe real capture remains unexecuted.
Protected files required: none according to recon and TEST CONTRACT.
Rollback boundary: commit `6b2a1b0baf236eea4edb3bec986e399f033eef2a` (completed Phase 8A.1).
Honest alternatives: resume this phase with a functioning `planner_deep` result; or explicitly revise Queen role/result requirements in a separate task before retrying. Do not substitute root implementation, fake backend, stub output, or debug overlay.

### Phase 8B — Automated visual comparison report

Status: deferred
Reason: current semantic Polygon2D output is structurally useful but not visually comparable enough to the source image for meaningful automated similarity metrics.
Decision: do not implement comparison code, CLI, capability, fixtures, or metrics in this session.

The generated semantic render is suitable for structural inspection,
debugging and smoke validation, but it is not yet a sufficiently faithful
visual reconstruction of the reference image for meaningful automated
pixel-similarity scoring.

Future work may introduce visual comparison after tile, sprite or texture
reconstruction provides a comparable visual domain.

### Phase 9 — Playtest smoke

Status: pending
Goal: run a minimal playtest smoke over the projected scene.
Allowed files: `engine/vision/**`, focused tests, experiment docs
Forbidden files: protected modules, canonical docs
Acceptance checks: smoke is minimal, deterministic, and non-relaxing
Docs affected: experimental docs only
Risks: hidden runtime dependency coupling

### Phase 10 — Hardening

Status: pending
Goal: tighten failure handling, limits, and rollback points.
Allowed files: `engine/vision/**`, focused tests, experiment docs
Forbidden files: protected modules, canonical docs
Acceptance checks: failures are bounded and reversible
Docs affected: experimental docs only
Risks: accidental expansion of scope

### Phase 11 — Documentation sync

Status: pending
Goal: keep operational docs aligned with experimental reality.
Allowed files: `docs/plans/active/queen-20260709-001-image-to-playable-platformer.md`, experimental docs
Forbidden files: canonical CLI/API docs, archive docs
Acceptance checks: operational docs reflect implemented phase state
Docs affected: experimental docs only
Risks: drift between plan and implementation

### Phase 12 — Exit decision

Status: pending
Goal: decide whether to continue, freeze, archive, or revert the experiment.
Allowed files: `docs/plans/active/queen-20260709-001-image-to-playable-platformer.md`
Forbidden files: protected modules, canonical docs
Acceptance checks: final status is explicit and justified
Docs affected: this plan only
Risks: premature closure

## Rollback

- Default rollback rules for phases 2-12:
  - revert only the files introduced in the active phase;
  - keep earlier completed phases intact;
  - prefer public API/CLI rollbacks over direct JSON/file surgery;
  - if a blocker is triggered, stop before the next phase and document the rollback boundary;
  - if a dependency or asset is no longer acceptable, downgrade to fallback or abort the phase.

- Phase 0 rollback summary: delete/revert this active plan file.
- Phase 1 rollback summary: remove `engine/vision` GameSpec files, tests, and experiment docs.
- Phase 2 rollback summary: remove GameSpec2D-to-Scene builder helpers/tests/docs, `semantic_prefabs/gamespec_to_scene`, `tests/test_vision_gamespec_to_scene.py`, the Phase 2 additions in `docs/vision/image_to_platformer_pipeline.md`, and any `engine/vision/__init__.py` builder export additions; keep the scaffold.
- Phase 3 rollback summary: remove the experimental GameSpec CLI commands, their contract tests, and any docs sync for CLI discoverability; keep prior vision ingestion/spec artifacts intact.
- Phase 4 rollback summary: remove simple tile-grid and tilemap extraction logic and its tests/docs; keep prior analysis inputs.
- Phase 5 rollback summary: remove scene projection code that bypasses supported surfaces; keep the internal spec and validation inputs.
- Phase 6 rollback summary: remove optional Supervision adapter additions only; keep projection and earlier phase artifacts.
- Phase 7 rollback summary: remove debug overlay code and its tests/docs; keep validation outputs unchanged.
- Phase 8A.1 rollback summary: revert only semantic `Polygon2D` fallback payloads/tests/docs; keep Phase 7 and earlier outputs.
- Phase 8A.2 rollback summary: revert only vision-local capture service, CLI/capability/tests/docs; keep Phase 8A.1 semantic geometry.
- Phase 8B rollback summary: remove only its deferred plan decision if scope is re-authorized later; no implementation exists.
- Phase 9 rollback summary: remove playtest smoke harness and fixtures; keep render comparison artifacts.
- Phase 10 rollback summary: remove hardening-only guards, limits, and retry/stop logic; keep the working experiment path.
- Phase 11 rollback summary: remove documentation sync edits for later phases; keep implementation state unchanged.
- Phase 12 rollback summary: revert the exit decision, restore the prior active state, and do not archive or freeze until the decision is re-approved.

## Update log

- 2026-07-09: Phase 0 documentation created; validation/review/AI audit pending.
- 2026-07-09: Phase 0 AI audit must_fix items resolved in plan text; added blockers, transition rules, and rollback coverage for future phases.
- 2026-07-09: Phase 0 gate closed after validator, code-reviewer-deep, and ai-friendliness approval; decision set to continue_next_phase.
- 2026-07-09: Phase 1 gate closed after validator, code-reviewer-deep, and AI audit approval; decision set to continue_next_phase.
- 2026-07-09: Phase 2 gate closed after validator, code-reviewer-deep, and AI audit approval; decision set to continue_next_phase.
- 2026-07-09: PLAN SYNC — corrected Phase 3 label/details from vision analysis adapter to experimental CLI for GameSpec workflows; completed Phase 0/1/2 gate results unchanged.
- 2026-07-09: Phase 3 gate closed after validator, code-reviewer-deep, and AI audit approval; decision set to continue_next_phase; phase 4 advanced to deterministic tile-grid/tilemap extraction without ML.
- 2026-07-10: Phase 4 gate closed after validator, review, and AI audit approval; decision set to continue_next_phase; phase 5 advanced to `vision build-platformer` MVP without object detection ML.
- 2026-07-10: Phase 5 gate closed after validator, review, and AI audit approval; decision set to continue_next_phase; phase 6 advanced to optional Supervision adapter.
- 2026-07-10: Phase 6 gate closed after validator, review, and AI audit approval; decision set to continue_next_phase; phase 7 advanced to debug overlay generation.
- 2026-07-10: Phase 7 gate closed after validator, review cycle 2, and AI audit approval; decision set to continue_next_phase; phase 8 remains render comparison.
- 2026-07-10: Phase 8 RECON blocked; decision set to block; unblock requires scope clarification or a headless render-capture contract/fixture.
- 2026-07-11: Continuation preflight accepted current clean HEAD `9db99af`; post-Phase-7 commits classified and preserved; no reset performed.
- 2026-07-11: PLAN SYNC — user authorized Phase 8A.1 semantic visuals and Phase 8A.2 off-screen capture using a hidden Raylib context; Phase 8B deferred; phases 9-12 retain numbering.
- 2026-07-11: CONTEXT RECON `recon-queen-20260709-001` completed with all 18 required findings confirmed and no protected change required; Phase 8A.1 awaits sufficient TEST CONTRACT.
- 2026-07-11: TEST CONTRACT `test-contract-queen-20260709-001-phase-8a1-semantic-visuals` returned `sufficient`; implementation remains blocked pending plan and critique.
- 2026-07-11: Baseline completed: full unittest/Ruff/mypy red with documented preexisting failures; doctor green; zero new regressions; merge gate remains closed.
- 2026-07-11: Deep plan `plan-queen-20260709-001-phase-8a1-semantic-visuals` approved by root critique; Phase 8A.1 may enter TDD implementation with one builder.
- 2026-07-11: Phase 8A.1 builder completed TDD implementation in authorized write set; red evidence captured; 114 focused/regression tests passed; no new regressions.
- 2026-07-11: Phase 8A.1 validator passed with `test_contract_satisfied=true`; deep reviewer approved with `must_fix=[]`; AI audit approved with score 95 and `must_fix=[]`.
- 2026-07-11: Phase 8A.1 marked completed and authorized for exclusive commit `feat(vision): agregar representacion visual determinista`; task remains partial.
- 2026-07-11: Phase 8A.1 committed as `6b2a1b0baf236eea4edb3bec986e399f033eef2a`; worktree verified clean; no push performed.
- 2026-07-11: PLAN SYNC — current phase advanced to 8A.2; implementation remains blocked pending sufficient TEST CONTRACT.
- 2026-07-11: TEST CONTRACT `test-contract-queen-20260709-001-phase-8a2-render-capture` returned `sufficient`; confirmed CFFI color pointer behavior, concrete limits, lifecycle/error/CLI/registry coverage, and mandatory real-backend smoke.
- 2026-07-11: Phase 8A.2 blocked before implementation: `planner_deep` produced no structured result after initial run, interruption, and the single allowed reformulation; no builder was delegated and phases 9-12 were not started.
