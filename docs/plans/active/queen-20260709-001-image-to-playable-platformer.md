# Queen Execution Plan: Image-to-Playable Platformer

Status: active
Authority: operational-plan
Task ID: queen-20260709-001
Created at: 2026-07-09T00:00:00
Updated at: 2026-07-09T00:00:00
Mode: long-task-plan

## Objective

Experimental pipeline reference image -> vision analysis -> GameSpec2D -> OpenGame Scene -> validation -> debug overlay -> render comparison -> playtest smoke.

## Non-goals

- No commercial cloning/assets.
- No arbitrary Python generation.
- No direct Scene JSON mutation when API/CLI exists.
- No SceneManager/EngineAPI/serialization/runtime/editor/physics changes in early phases.
- No mandatory OpenCV/supervision.
- No test relaxation.

## Current phase

- Name: Phase 4 — Implement simple tile-grid and tilemap extraction without ML
- phase_status: completed
- task_status: partial
- Decision: continue_next_phase
- Allowed files: `engine/vision/**`, focused tests, `docs/vision/image_to_platformer_pipeline.md` if needed, this active plan
- Forbidden files: protected modules, canonical CLI/API docs, serialization/runtime/editor/physics changes, direct Scene JSON mutation
- Test contract: test-contract-queen-20260709-001-phase-4-tile-grid
- Verdict: sufficient
- Correction test contract: test-contract-queen-20260709-001-correction-phase3-vision-registry-metadata
- Correction verdict: sufficient
- Validator checks passed:
  - `py -m unittest tests.test_vision_tile_grid_detector tests.test_vision_tilemap_reconstructor tests.test_vision_gamespec2d -v`
  - `py -m unittest tests.test_vision_cli_contract tests.test_vision_gamespec_to_scene -v`
  - `py -m unittest tests.test_capability_registry_audit tests.test_capability_registry_semantic_audit -v`
  - `py -m unittest tests.test_parser_registry_alignment tests.test_motor_registry_consistency tests.test_start_here_ai_coherence -v`
  - `py -m unittest tests.test_repository_governance tests.test_start_here_ai_coherence -v`
  - `py -m motor doctor --project . --json`
- Review: approved, must_fix 0, should_fix 2 (PPM size guard / more malformed PPM tests for future hardening)
- AI audit: approved/pass, score 95, must_fix 0
- Known limitations: controlled PPM/PixelImage only; no image CLI yet; no arbitrary screenshots; no ML/CV; no max-size guard yet; helper discoverability lower than CLI/API
- Acceptance checks: tile-grid extraction stays deterministic, bounded, and ML-free; no protected contract drift; outputs remain testable and reproducible
- Docs affected: experimental docs only, plus active plan when gated
- Risks: scope bleed into protected APIs, overfitting to a single fixture image, tilemap extraction complexity, broad `py -m unittest discover -s tests` still fails unrelated editor/RPG regressions (validator addendum final_verdict pass for Phase 4; related_to_phase4=false)
- Next phase: Phase 5 — Add `vision build-platformer` MVP without object detection ML

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

- No engine/vision exists.
- CLI motor/cli.py exists.
- EngineAPI/tilemap helpers exist but are protected.
- Dependency system: pyproject + requirements; no vision extra.
- Render headless exists, but there is no image compare pipeline.
- Current branch: fix/ciclosReina.
- Remote default: origin/main.
- No task_id collision found.

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

Status: pending
Goal: add a `vision build-platformer` MVP that turns the validated image/tilemap pipeline into a playable platformer without object detection ML.
Allowed files: `engine/vision/**`, focused tests, `docs/vision/image_to_platformer_pipeline.md`, this active plan
Forbidden files: protected modules, canonical CLI/API docs, serialization/runtime/editor/physics changes, direct Scene JSON mutation
Acceptance checks: build flow stays deterministic, ML-free, and routed through supported public surfaces when available
Docs affected: experimental docs only
Risks: accidental contract bypass, scope creep into protected surfaces, image-to-game overfitting

### Phase 6 — Validation pass

Status: pending
Goal: validate projected scene against internal constraints.
Allowed files: `engine/vision/**`, focused tests, experiment docs
Forbidden files: protected modules, canonical docs
Acceptance checks: validation failures are explicit and actionable
Docs affected: experimental docs only
Risks: weak validation semantics

### Phase 7 — Debug overlay

Status: pending
Goal: expose analysis and projection state in an overlay.
Allowed files: `engine/vision/**`, focused tests, experiment docs
Forbidden files: protected modules, canonical docs
Acceptance checks: overlay is optional and non-invasive
Docs affected: experimental docs only
Risks: UI bleed into core contracts

### Phase 8 — Render comparison

Status: pending
Goal: compare expected image cues with rendered output.
Allowed files: `engine/vision/**`, focused tests, experiment docs
Forbidden files: protected modules, canonical docs
Acceptance checks: comparison is reproducible and headless-capable
Docs affected: experimental docs only
Risks: false confidence from noisy comparisons

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
- Phase 6 rollback summary: remove validation additions only; keep projection and earlier phase artifacts.
- Phase 7 rollback summary: remove debug overlay code and its tests/docs; keep validation outputs unchanged.
- Phase 8 rollback summary: remove render comparison tooling and baselines; keep the overlay and validation layers.
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
