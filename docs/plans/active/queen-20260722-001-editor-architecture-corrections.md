# Reina — editor architecture corrections

- `task_id`: `queen-20260722-001`
- `classification`: `critical`
- `max_cycles`: `5`
- `task_status`: `partial`
- `current_phase`: `plan_critique`
- `phase_status`: `completed` (`execution_planning`)
- `model_route`: `context_recon` + `test_strategist_deep` -> `planner_deep` -> `builder_deep` -> `validator` -> `code_reviewer_deep`
- `authoritative_plan`: `docs/editor_in_engine_migration_plan_v4.md`
- `initial_sha`: `bc33bd8de26f028462f4a45dcd8f1d4f73ab83b3`
- `remote_sha`: `b2bb2d97ee14b762e3e1165b7e9856e5c1fe2467`
- `stable_predecessor`: `b2bb2d97ee14b762e3e1165b7e9856e5c1fe2467`
- `branch`: `feat/EditorArchitectureUnification`
- `working_tree`: `clean`
- `commit.authorized`: `true`
- `push.performed`: `false`

## Objective

Correct inherited architectural violations in G0.5, G1, G2, and G3 through the ordered Blocks 1–9: fail-closed protected actions, one persistent `Scene` authority, one preview lifecycle authority, PLAY projected from `Scene`, composition outside `Game`, authoritative `EditorSession` selection, GUID-first cross-scene references, truly ID-first APIs, and exact `Scene.revision` invariants. Finish with the validation methodology required by the authoritative plan.

## Non-goals

- No RectTransform, Camera, Collider, Tilemap, G4, or later packages.
- No merge, rebase, reset, clean, force-push, branch change, or push.
- No generic command bus, service locator, new architecture contracts based on `Any`/`hasattr`, or semantic fallbacks.
- No unrelated CLI, inspector, scaffolding, sample-project, or UI work unless proved to be a direct consumer.

## Reconciliation evidence

- `git fetch --all --prune`: passed; remote refs refreshed.
- Current branch exactly `feat/EditorArchitectureUnification`.
- Local `HEAD`: `bc33bd8de26f028462f4a45dcd8f1d4f73ab83b3`.
- Remote branch: `b2bb2d97ee14b762e3e1165b7e9856e5c1fe2467`.
- Divergence `HEAD...origin`: 2 local / 0 remote commits.
- Working tree: clean; no uncommitted inherited changes.
- `git diff --check`: passed.
- First sandboxed Git attempt failed with `detected dubious ownership`; all later read-only Git commands use per-command `-c safe.directory=...`, without changing user config.

## Commits after `b2bb2d9`

1. `9e1baa8 Refactor editor authority: session, previews, and GUID-first refs`
2. `bc33bd8 Update recent project history`

Inherited diff: 64 files, 3,143 insertions, 582 deletions. Includes architecture/product/tests plus `.codex-test-global/recent_projects.json`; classification pending read-only RECON. Preserve both commits; no history rewrite or amend.

## Acceptance criteria

1. Protected save/autosave/PLAY/switch/close/reload/export operations never import `World -> Scene`; open legacy lease or failed preview cancellation blocks without changing `Scene` or disk.
2. One application-owned `PreviewLeaseRegistry`, keyed by `OpenDocumentId`; `EditorPreviewCoordinator` is lifecycle authority; zero leases after successful cancellation; document isolation holds.
3. PLAY is projected canonically from `Scene`, excludes transient editor state, shares no mutable state with `EditWorld`, and STOP discards runtime.
4. Transform preview is atomic/conflict-aware, releases leases on every path, restores projection on failure, creates no history for no-op, and creates exactly one semantic entry for commit.
5. `Game` neither builds editor preview capabilities nor uses `SceneManager` private state; application/composition root owns wiring and exposes narrow capabilities.
6. `EditorSession.selection` is sole productive selection authority; `World.selected_entity_name` is one-way visual projection; rename/rekey retain identity; incompatible scene change clears selection.
7. Schema v3 persists GUID-first cross-scene references; reader accepts v2/v3; writer is canonical v3; unresolved migration blocks without invented IDs and produces backup/report.
8. ID-first APIs never resolve back to names; rename followed by mutation through the same ref targets the same entity; AST fitness prevents regression.
9. Each semantic commit increments `Scene.revision` exactly once; no-op, preview update, error, and rollback do not; preview commit increments once.
10. Final suite, focused suites, fitness, import graph, Ruff, configured type checker, `py_compile`, and required benchmarks execute with exact evidence before ledger update.

## RECON result

`context_recon` returned a valid read-only result (`status: completed`). Classification of inherited work:

- Block 1 incomplete: explicit adapter/lease foundation exists, but public `sync_from_edit_world` and `mark_edit_world_dirty` remain; productive calls remain in `editor_interaction_controller.py` and `game.py`.
- Block 2 incomplete: `EditorApplication` creates a coordinator, but `SceneManager.create_preview_lease_registry()` still permits parallel lifecycle authorities.
- Block 3 partially correct: PLAY projection from `Scene` exists and a test excludes selection; complete protected lifecycle evidence is missing.
- Block 4 incomplete: typed Transform handles exist, but transient preview paths still call legacy dirty marking.
- Block 5 contradictory: `Game` still owns broad wiring and reaches through `_scene_manager`; composition fitness is too narrow.
- Block 6 contradictory: `EditorSession` exists beside productive `EditorSelectionState`, workspace selection, and `World.selected_entity_name` authorities.
- Block 7 incomplete: GUID-first schema pieces exist, but name/path-first cross-scene consumers remain in scene-flow and inspector paths.
- Block 8 contradictory: hierarchy and other productive paths still resolve `EntityRef`/IDs through names.
- Block 9 incomplete: revision tests exist, but legacy import/preview paths and all mutation families lack exact executed proof.
- Out of scope inherited state: `.codex-test-global/recent_projects.json`; preserve but exclude from architecture commits.

Key remaining inventories from RECON:

- `sync_from_edit_world`: public coordinator/manager surfaces remain.
- `mark_edit_world_dirty`: public coordinator/manager surfaces plus productive callers in interaction controller and `Game` remain.
- Legacy leases: explicit adapter exists; no proven productive acquire caller or complete retirement metadata.
- `Game` private/wiring access: broad `_scene_manager` use and editor capability construction remain.
- Selection authorities: `EditorSession`, `EditorSelectionState`, workspace-entry state, and `World.selected_entity_name` remain productive.
- Cross-scene legacy: `target_path`, `target_scene_path`, `target_entity_name`, and name-first scene-flow/inspector paths remain.

## TEST CONTRACT

`test_strategist_deep` returned a valid result after one contract-only reformat (`verdict: sufficient`, `status: completed`). No tests were run by the strategist.

Authority coverage:

- Block 1: projection/integrity, save/persistence, edit-sync, legacy adapter, workspace and architecture correction tests.
- Block 2: architecture corrections, Transform preview contract, workspace isolation.
- Block 3: workspace, runtime controller, scene projection, projection integrity.
- Block 4: Transform/gizmo, history atomicity, mutation rollback.
- Block 5: editor composition fitness and scene architecture.
- Block 6: editor session, project workspace, hierarchy, inspector, gizmo.
- Block 7: GUID-first, v3 migration, scene refs, schema, flow, persistence.
- Block 8: ID-first fitness plus entity/component/serializable/structural authoring and manager contracts.
- Block 9: revision invariants, Transform preview, history, rollback, serializable mutation.

Required strengthened authority tests:

1. Parametric protected-action matrix for save/autosave/PLAY/switch/close/project/reload/export, asserting typed failure and unchanged `Scene`, revision, disk, active document, runtime, and adapter count.
2. Registry/coordinator identity, two-document isolation, same-document conflict, cancel failure, and zero-lease success.
3. Canonical Scene-derived PlayWorld with no editor state or shared mutables; STOP destroys runtime.
4. Transform success/no-op/conflict/target loss/Err/exception/restore failure/pointer/undo/save/PLAY/switch paths, asserting payload, revision, dirty, history, fingerprint, and leases.
5. AST-qualified composition rules and narrow-capability behavior tests.
6. Session-only productive selection plus AST prohibition of productive `World.selected_entity_name` reads.
7. v3 round trips and migration diagnostics for all cross-scene families; no invented IDs/GUIDs.
8. AST/control-flow ID-first rules plus rename-then-mutate through the same ref for every mutation family.
9. Parametric exact revision tests across success/no-op/error/history/projection/rollback paths.
10. Deterministic benchmark fixtures Small=100x4, Medium=1000x5, Large=5000x5, XL=10000x4; fingerprint/save/projection all sizes, hierarchy when available, Transform commit Medium; warmups 5, repeats 20, p50/p95/max/mean/relative deviation and comparable baseline.

Tests that must be replaced, never weakened, when legacy behavior is removed:

- `test_prepare_for_save_syncs_unmarked_world_version_change`: replace automatic promotion expectation with rejection plus unchanged Scene/revision/disk.
- Manager contract tests that expect ID wrappers to resolve the current name: replace with direct-ID and zero-name-lookup authority.
- Workspace/World selection-authority tests: replace only after stronger `EditorSession` and one-way projection coverage exists.

Interpreter and base validation commands:

- Python: `C:/Users/usuario/AppData/Local/Programs/Python/Python311/python.exe` (`3.11.1`); `py`, `python`, and `python3` are unusable here.
- Focused commands are the `python.exe -m unittest` module groups listed per Block 1–9 in the strategist result; planner must keep them phase-local.
- Shared fitness: `python.exe -m unittest tests.test_editor_migration_fitness tests.test_id_first_fitness tests.test_editor_composition_fitness tests.test_scene_architecture`.
- Final: `unittest discover -s tests`, Ruff production/tests, configured mypy, compileall/`py_compile`, inventory/import graph, fitness, Git scope checks, expanded benchmarks, and manual smoke when GUI environment is available.
- If a command cannot run: record exact command/exit/error, classify cause, keep gate open, and never report pass.

## Ordered phases, dependencies, and write sets

| Phase | Dependency | Exclusive write set summary | Status |
|---|---|---|---|
| 0. Reconcile, RECON, TEST CONTRACT, plan | none | Queen plan only | completed; critique pending |
| 1. Fail-closed + legacy adapter | 0 | edit sync, legacy adapter, manager/lifecycle, direct callers, authority tests | pending |
| 2. One preview lifecycle authority | 1 | preview coordinator, editor application, manager/lifecycle, tests | pending |
| 3. PLAY from `Scene` | 1–2 | runtime controller, manager/lifecycle, minimal `Game`, tests | pending |
| 4. Atomic Transform preview | 2–3 | Transform/coordinator/gizmo/controller/authoring, tests | pending |
| 5. Wiring outside `Game` | 2–4 | composition root, `Game`, editor application/factory/manager, fitness tests | pending |
| 6. `EditorSession` selection authority | 5 | session/legacy selection, application/controllers, hierarchy/gizmo/inspector/world projection, tests | pending |
| 7. GUID-first cross-scene | 1, 6 | schema/refs/persistence/flow/transitions/prefabs/components/direct consumers, tests | pending |
| 8. ID-first without name fallback | 6–7 | Scene/authoring/manager/API, AST fitness and mutation tests | pending |
| 9. Revision invariants | 1–8 | Scene/mutation families/Transform and exact invariant tests | pending |
| 10. Final validation + ledger | 1–9 | Queen plan plus authoritative ledger only | pending |

`planner_deep` result: valid (`status: completed`). Candidate plan is executable but remains gated by independent critique. Phase locks are exclusive; repeated critical files are released only after the prior phase is validated, reviewed, and committed. Same single `builder_deep` is reused serially.

### Candidate phase gates

Each Block 1–9 runs:

`LOAD PLAN -> PLAN SYNC -> TEST CONTRACT SYNC -> authority baseline -> builder_deep -> focused tests -> shared regression when applicable -> py_compile -> validator -> code_reviewer_deep -> AI audit if applicable -> must_fix correction cycle -> committer -> plan sync`.

Common commit exclusion: this Queen plan and `.codex-test-global/recent_projects.json` are never staged in functional commits. Existing `9e1baa8` and `bc33bd8` are never amended or rewritten.

Phase-specific locks and proposed commits:

1. Block 1 locks `engine/scenes/edit_sync.py`, `legacy_world_authoring_adapter.py`, `scene_manager.py`, `workspace_lifecycle.py`, direct productive callers proven by baseline, and fail-closed/adapter/integrity tests. Commit: `fix(g05): make protected actions fail closed`.
2. Block 2 locks `editor_preview_coordinator.py`, `editor_application.py`, registry/manager/lifecycle wiring, and preview identity/isolation tests. Commit: `fix(g05): centralize preview lease lifecycle`.
3. Block 3 locks runtime controller plus manager/lifecycle and minimal host caller changes, with projection/runtime/STOP tests. Commit: `fix(g05): build play world from canonical scene`.
4. Block 4 locks Transform preview/coordinator/gizmo/controller and its exact authoring/test paths. No RectTransform/Camera/Collider/Tilemap. Commit: `fix(g30): make transform preview cancellation atomic`.
5. Block 5 locks composition root, editor application, `Game`, runtime-system factory/manager only where direct wiring requires, plus AST/behavior fitness. Commit: `fix(g20): move preview wiring to editor application`.
6. Block 6 locks session/selection and direct hierarchy/gizmo/inspector/workspace consumers plus one-way `World` projection and tests. Commit: `fix(g20): make editor session selection authoritative`.
7. Block 7 locks schema/refs/persistence/flow/transitions/prefabs/direct consumers and migration tests. Mandatory AI audit. Commit: `fix(g10): complete guid-first cross-scene references`.
8. Block 8 locks Scene authoring families, manager, public authoring API and AST/behavior tests. Mandatory AI audit. Commit: `fix(g10): remove name fallback from id-first APIs`.
9. Block 9 locks Scene revision owner, mutation coordinators, Transform commit, and exact parametrized tests. Commit: `fix(scene): enforce revision invariants`.
10. Final phase has no product builder. Validator, final review and AI-audit closure run first; then documenter may update the authoritative ledger from executed evidence. Separate commit: `test(migration): complete gate validation` or documentation-only equivalent matching actual diff.

Rollback: revert only a new phase commit before dependents, otherwise forward correction. Never restore automatic World-to-Scene sync, duplicate preview authorities, name fallback, distributed composition, or v2 writing. Schema rollback preserves v2/v3 reader, `.bak`, and structured report; no data restoration without explicit verified target and user authority.

### Initial baseline before first builder

- Git status, branch, HEAD and `diff --check` must match recorded state except this Queen plan.
- Run authority baseline covering architecture corrections, both legacy adapter suites, lifecycle/projection integrity, Transform/gizmo, composition, session, GUID-first, ID-first and revision tests.
- Run shared architecture fitness.
- Classify every failure as functional, environment, missing dependency, obsolete contractual test, flaky, import, or platform. No builder begins until baseline failures are mapped to owning phase and recorded.

## Authority tests

Pending TEST CONTRACT reconciliation. Known candidate authority files from inherited diff include:

- `tests/test_architecture_authority_corrections.py`
- `tests/test_legacy_authoring_adapter.py`
- `tests/test_legacy_world_authoring_adapter.py`
- `tests/test_transform_preview_contract.py`
- `tests/test_gizmo_transform_preview.py`
- `tests/test_editor_composition_fitness.py`
- `tests/test_editor_session_authority.py`
- `tests/test_guid_first_cross_scene.py`
- `tests/test_id_first_fitness.py`
- `tests/test_scene_revision_invariants.py`

## Decisions

- Real repository state outranks previous transcript and ledger claims.
- Continue because local commits exist after `b2bb2d9`; do not block as `missing_pushed_changes`.
- Treat remote as not containing inherited correction work.
- Preserve inherited commits and correct forward with new, small, reversible commits.
- Do not update authoritative ledger until final executed evidence exists.
- Native agent roles are available; no OpenCode fallback is eligible while native dispatch succeeds.

## Pending findings

- Classify every inherited change across Blocks 1–9 as correct, incomplete, contradictory, or out of scope.
- Determine whether `bc33bd8` is unrelated/generated state that must remain excluded from future commits.
- Inventory productive legacy consumers, leases, `mark_edit_world_dirty`, `sync_from_edit_world`, `Game` private access, duplicate selection authorities, and unresolved cross-scene references.
- Establish interpreter, focused baselines, configured lint/type tools, import graph command, and benchmark commands.

## Command record

- Required instruction files and authoritative plan read completely.
- Initial Git commands under sandbox: blocked by repository ownership check; no state changed.
- `git -c safe.directory=... status --short`: clean.
- `git -c safe.directory=... branch --show-current`: expected branch.
- `git -c safe.directory=... remote -v`: `origin` points to `Yisuescopeta/OpenGame`.
- `git -c safe.directory=... fetch --all --prune`: passed.
- Required local/remote rev-parse, logs, diff stat/name-only, and `diff --check`: passed; SHAs and diff recorded above.

## Risks

- Inherited product changes span protected contracts and may contradict tests or plan despite appearing complete.
- Remote lacks both local commits; losing local repository would lose inherited correction work.
- `.codex-test-global/recent_projects.json` appears outside architecture scope and must not enter later commits accidentally.
- Shared critical files require strictly serial implementation.
- Final validation/benchmark environment may lack Ruff, type checker, GUI/runtime dependencies, or stable timing; failures must be classified, not hidden.

## Gates

- Closed: instruction load, branch gate, clean-tree inventory, remote reconciliation, inherited-work existence, model-route availability.
- Open: RECON validity, TEST CONTRACT sufficiency, executable plan, plan critique, Blocks 1–9, per-phase validator/review/commit, AI compatibility audit where applicable, final validation, benchmarks, ledger accuracy.

## Next action

Run `context_recon` and `test_strategist_deep` in parallel, read-only. Then obtain `planner_deep`, independent read-only plan critique, and persist approved execution details before any product/test code change.
