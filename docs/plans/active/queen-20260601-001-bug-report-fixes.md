# Authority: operational-plan

**Task ID:** queen-20260601-001
**Created:** 2026-06-01
**Status:** partial
**Max cycles:** 5
**Current cycle:** 5

---

## Objective

Fix all failures reported in `docs/bug_report.md`. Full coverage across 15 bugs
in 3 categories: user-reported criticals (2), RPG development issues (6),
code audit findings (7).

---

## Scope

### In scope

| ID | Title | Severity | Subsystem |
|----|-------|----------|-----------|
| 1.1 | Editor sync after API/save changes | Critical | Editor ↔ EngineAPI |
| 1.2 | Hierarchy panel scroll/input mapping | Critical | Editor UI |
| 2.1 | Sprite supports `source_slice` | High | Render |
| 2.2 | `motor runtime step` accepts InputMap + ScriptBehaviour | High | CLI / Runtime |
| 2.3 | Do NOT serialize `InputMap.last_state`; document runtime-only | Medium | Components / Docs |
| 2.4 | Animator supports string parameters/conditions for directional anim | Medium | Animator |
| 2.5 | `EngineAPI.create_entity` accepts `tag`/`layer`/`active` | Low | API |
| 2.6 | `get_active_scene` supports `include_entities=True` | Low | API |
| 3.1 | Planned capabilities not exposed as implemented to AI; filter | Medium | CLI / Registry |
| 3.2 | Reduce unjustified skipped tests; keep optional-dependency skips | Medium | Testing |
| 3.3 | No false BUG/TODO markers; docs policy + real markers only | Medium | Governance |
| 3.4 | `PrefabManager.save_prefab` logs via project logging, keeps public return contract | Low | Prefabs |
| 3.5 | Prefab instantiate name race prevented with minimal lock/atomic naming | Low | Prefabs |
| 3.6 | Scene save verifies post-write load/integrity | Low | Scenes |
| 3.7 | Sprite is not ignored when Animator exists; layered/fallback render | Low | Render |

### Out of scope

- Engine internals beyond explicitly allowed critical files.
- New public components not already registered.
- Box2D backend installation (only mock-aware test coverage).
- `component_registry.py` changes unless tests prove needed.

---

## Critical Files (touch only with explicit justification)

- `engine/scenes/scene_manager.py` — needed for 1.1 and 3.6 only.
- `engine/systems/render_system.py` — needed for 2.1 and 3.7 only.
- `engine/inspector/inspector_system.py` — needed for 1.2 only.
- `engine/levels/component_registry.py` — do NOT touch unless tests prove needed; `source_slice` is a field of existing `Sprite`.

### Cycle 1 DoD (partial — cycle-level)

- `focused_tests_pass`: true
- `review_must_fix_count`: 0
- `ai_friendliness_score`: 94
- `no_scope_creep`: true

---

## Decisions (Queen critiques applied)

1. **No false BUG markers** (C1): Only add `# BUG(id): description` for real accepted remaining limitations. Never add markers for already-fixed bugs. Add docs policy (3.3) for governance, not code markers aspirationales.
2. **No `save_prefab` signature break** (C2): Fix logging internally (`log_err` instead of `print`) but keep public return contract `-> bool`. Do not change return type.
3. **`motor/cli_core` for runtime step** (C3): Expand `runtime step` detection in `motor/cli_core.py` to accept `InputMap + ScriptBehaviour`, not only `PlayerController2D`.
4. **Schema-safe capability filtering** (C4): For 3.1, filter planned capabilities from `motor ai start` output rather than inventing unsupported JSON fields. Verify registry/CLI first; fix only if needed.
5. **Optional deps stay optional** (C5): For 3.2, add fixtures/mocks where safe but never convert optional-dependency skips into hard requirements. Keep clear skip messages.
6. **No `component_registry` for `source_slice`** (C6): `source_slice` is a new field of existing `Sprite` component — not a new component. Do not touch `component_registry.py`.
7. **Phases bounded to 5 cycles** (C7): Exactly 5 phases matching `max_cycles=5`. Each phase has clear acceptance checks; if a phase fails validation, it blocks the cycle.

---

## Phases

### Phase 1 — Foundation + API/CLI (docs-light)

**Status:** approved
**Cycle:** 1
**Covers:** 2.2, 2.5, 2.6, 2.3 (docs), 3.1 (verification/filter)

**Allowed files:**
- `motor/cli_core.py`
- `engine/api/_authoring_api.py`
- `engine/api/_scene_workspace_api.py`
- `engine/api/_runtime_api.py`
- `docs/api.md`
- `docs/cli.md` (if runtime step docs change)
- `tests/test_motor_cli_contract.py` (or dedicated test file)

**Forbidden files:**
- `engine/scenes/scene_manager.py`
- `engine/systems/render_system.py`
- `engine/inspector/inspector_system.py`
- `engine/components/animator.py`
- `engine/components/sprite.py`

**Acceptance checks:**
- `motor runtime step --input "right"` succeeds with `InputMap + ScriptBehaviour` entity.
- `api.create_entity("X", tag="T", layer="L", active=True)` works.
- `api.get_active_scene(include_entities=True)` returns entities list; default `False` preserves summary.
- `InputMap.last_state` is documented as runtime-only in `docs/api.md` with pointer to `RuntimeAPI.get_input_state()`.
- `motor ai start --json` does NOT list `asset:find`, `asset:metadata:get`, `asset:refresh`, `introspect:status`, `project:editor_state`, `project:open` as available (if they remain unimplemented).

**Tests:**
- `test_runtime_step_with_script_behaviour`
- `test_create_entity_with_tag_layer_active`
- `test_get_active_scene_include_entities`
- `test_inputmap_last_state_not_in_to_dict`
- `test_planned_capabilities_filtered_from_ai_start`

**Docs expected:**
- `docs/api.md`: document `include_entities`, `tag`/`layer`/`active` params, `last_state` runtime-only note.
- `docs/cli.md`: update `runtime step` description if detection logic changes.

**Risks:**
- `motor/cli_core.py` change may affect existing runtime step contract — verify `--json` output backward-compatible.
- `include_entities` default must be `False` to not break existing callers expecting summary.

---

### Phase 2 — Render / Components / Animator

**Status:** approved
**Cycle:** 2
**Covers:** 2.1, 2.4, 3.7

**Allowed files:**
- `engine/components/sprite.py`
- `engine/components/animator.py`
- `engine/systems/render_system.py`
- `docs/TECHNICAL.md`
- `tests/` (dedicated test file)

**Forbidden files:**
- `engine/scenes/scene_manager.py`
- `engine/inspector/inspector_system.py`
- `engine/levels/component_registry.py`
- `motor/cli_core.py`

**Acceptance checks:**
- `Sprite(source_slice="grass_0")` resolves tile rect via `AssetService.get_slice_rect()` and renders only that tile.
- `Animator` with `AnimationCondition(parameter="facing", operator="==", value="up")` triggers correct state.
- Entity with both `Sprite` and `Animator` renders Sprite first, then Animator on top (layered fallback).
- Entity with only one component preserves existing render behavior.

**Tests:**
- `test_sprite_source_slice_renders_tile`
- `test_animator_string_parameter_condition`
- `test_dual_sprite_animator_layered_render`
- `test_sprite_only_preserves_behavior`
- `test_animator_only_preserves_behavior`

**Docs expected:**
- `docs/TECHNICAL.md`: note `source_slice` field on Sprite, string parameters on Animator.
- `docs/api.md`: if any new API surface added.

**Risks:**
- `AssetService.get_slice_rect()` call may have different signature than `_draw_animated_sprite` usage — verify.
- Layered render may need render order guarantee — ensure Sprite drawn before Animator.
- String condition evaluation must not break existing numeric conditions.

---

### Phase 3 — Persistence / Prefab

**Status:** approved
**Cycle:** 3
**Covers:** 3.4, 3.5, 3.6

**Allowed files:**
- `engine/assets/prefab.py`
- `engine/scenes/scene_manager.py`
- `tests/` (dedicated test file)

**Forbidden files:**
- `engine/systems/render_system.py`
- `engine/inspector/inspector_system.py`
- `engine/components/animator.py`

**Acceptance checks:**
- `save_prefab` uses `log_err()` for errors, returns `False` on failure (no signature change).
- `save_prefab` distinguishes `IOError`, `PermissionError`, `JSONEncodeError` in log messages.
- `instantiate_prefab` uses `threading.Lock` or `itertools.count()` for atomic naming.
- Concurrent instantiation test: 100 threads, no name collision.
- `save_scene` reads back file after write, validates `json.load()` + `migrate_scene_data()`, compares `entity_count`.

**Tests:**
- `test_save_prefab_logs_errors_not_print`
- `test_save_prefab_permission_error_returns_false`
- `test_instantiate_prefab_atomic_naming`
- `test_concurrent_instantiate_no_name_race`
- `test_save_scene_post_write_integrity_check`

**Docs expected:**
- `docs/schema_serialization.md`: note scene save integrity check.
- `docs/TECHNICAL.md`: note atomic naming for prefab instantiate.

**Risks:**
- `save_scene` integrity check adds overhead — keep minimal (JSON parse + entity count compare only).
- Lock on `instantiate_prefab` must not deadlock with other scene operations.
- `log_err` may require importing project logging infrastructure — verify availability.

---

### Phase 4 — Editor Criticals

**Status:** approved
**Cycle:** 4
**Covers:** 1.1, 1.2

**Allowed files:**
- `engine/scenes/scene_manager.py`
- `engine/editor/` (only where wiring exists for scene_changed event)
- `engine/inspector/inspector_system.py`
- `tests/` (dedicated test file)

**Forbidden files:**
- `engine/systems/render_system.py`
- `engine/components/sprite.py`
- `engine/components/animator.py`
- `engine/assets/prefab.py`

**Acceptance checks:**
- `SceneManager.on_scene_saved` event emitted after `save_scene`.
- Editor subscribes to `on_scene_saved`, shows loading screen, rebuilds World projection from serialized Scene.
- After `build_scene.py` modifies `main_scene.json`, editor viewport reflects changes without restart.
- Hierarchy panel supports vertical scroll with `_entity_list_scroll_offset` + `rl.begin_scissor_mode`.
- Mouse hit coordinates account for scroll offset.
- Entity rename/reorder operations apply correctly within scrolled view.

**Tests:**
- `test_scene_manager_emits_on_scene_saved`
- `test_editor_reloads_after_api_mutation`
- `test_hierarchy_panel_scroll_draws_entities`
- `test_hierarchy_panel_scroll_mouse_hits`
- `test_hierarchy_panel_rename_entity`

**Docs expected:**
- `docs/architecture.md`: note `on_scene_saved` event and editor subscription.
- `docs/TECHNICAL.md`: note hierarchy panel scroll implementation.

**Risks:**
- `SceneManager` change is in critical file list — minimal event emission only.
- Editor reload on every `save_scene` may be expensive for batch mutations — consider `batch_save` or debounce.
- `rl.begin_scissor_mode` availability depends on raylib version — verify.
- Hierarchy panel (~4000 lines) is complex — keep scroll offset changes minimal.
- This phase has highest risk; may need to be split into sub-steps if blocked.

---

### Phase 5 — Skips / Governance / Docs / Final Cleanup

**Status:** approved/complete
**Cycle:** 5
**Covers:** 3.2, 3.3, docs, validation fixes only

**Allowed files:**
- `tests/` (add fixtures/mocks, improve skip messages)
- `docs/bug_report.md` (update status)
- `docs/documentation_governance.md`
- `docs/README.md`
- No engine code unless fixing a real bug found during validation.

**Forbidden files:**
- All `engine/` files (unless validation finds a real bug).
- All `motor/` files (unless validation finds a real bug).

**Acceptance checks:**
- Unjustified `@unittest.skipIf` reduced: at least 5 previously-skipped tests now run via fixtures/mocks.
- Optional-dependency skips have clear messages explaining what to install.
- No false BUG/TODO markers added to engine code (only real accepted limitations).
- Docs policy for markers added to `docs/documentation_governance.md`.
- All 5 phases pass their respective tests.
- `py -m unittest discover -s tests` passes (existing failures are pre-existing debt, not new).
- `py -m motor doctor --project . --json` clean.

**Tests:**
- `test_skipped_tests_have_clear_messages`
- `test_no_false_bug_markers_in_engine`
- `test_docs_bug_marker_policy_exists`

**Docs expected:**
- `docs/documentation_governance.md`: add policy for TODO/FIXME/BUG/LIMITATION markers.
- `docs/bug_report.md`: update status of each resolved bug.
- `docs/README.md`: if new docs files created.

**Risks:**
- Some skips may be truly unsolvable (DPAPI, Box2D binary) — document clearly.
- Markers policy is governance, not code change — ensure it doesn't demand retroactive markers.
- Validation-only phase means no engine changes; if a bug surfaces during validation, scope-creep risk.

---

## Progress Log

| Timestamp | Event | Details |
|-----------|-------|---------|
| 2026-06-01 | Plan persisted | 15 bugs scoped across 5 phases. Status: in_progress, cycle 0. |
| 2026-06-01 | Cycle 1 implemented | Bugs 2.2, 2.5, 2.6, 2.3, 3.1 resolved. New tests: `test_runtime_step_script_behaviour.py` (CLI), `test_api_authoring_workspace.py` (API). Docs: `docs/api.md`, `docs/cli.md`. Phase 1 status: implemented (preliminary validation). |
| 2026-06-01 | Cycle 1 validated | Validator: focused/unit/contract tests passed, motor doctor healthy, ruff/mypy global fail only pre-existing debt. Reviewer: approved, must_fix=0. AI audit: score 94, must_fix=0. DoD partial: focused_tests_pass=true, review_must_fix=0, ai_score=94, no_scope_creep=true. Phase 1 approved. |
| 2026-06-01 | Cycle 2 implemented | Bug 2.1 fixed: `Sprite.source_slice` in `engine/components/sprite.py`; `_draw_sprite` uses AssetService slice rect with fallback in `engine/systems/render_system.py`; tests updated/added. Bug 2.4 fixed: Animator supports string parameter type and string conditions with numeric comparisons safely false; tests updated. Bug 3.7 fixed: `RenderSystem._render_entity` renders Sprite and Animator layered instead of ignoring Sprite; tests added. Docs updated: `docs/TECHNICAL.md`. Builder checks: sprite/render 67 OK; animator 42+24 OK; docs contract/governance subsets OK; motor doctor healthy. Phase 2 status: implemented/pending validation. |
| 2026-06-01 | Cycle 2 validated | Validator: focused/regression tests pass (sprite/render 67 OK, animator 66 OK, docs/contract/governance subsets OK). motor doctor healthy. ruff/mypy global fail only pre-existing unrelated debt after animator correction (1 warning: `animator.py` line 578 type inference issue, not in animator source — pre-existing in pyray stubs). Reviewer: approved, must_fix=0. AI audit: applicable, score 95, must_fix=0. Recommendation: mention new features in `docs/agents.md` later (Phase 5 docs pass). Cycle 2 DoD: focused_tests_pass=true, review_must_fix=0, ai_score=95, no_scope_creep=true. Phase 2 approved/complete. |
| 2026-06-01 | Cycle 3 implemented | Bug 3.4 fixed in `engine/assets/prefab.py`: save_prefab logs write/serialization errors with project logging (`log_err`) and keeps bool contract (returns False on failure, distinguishes IOError/PermissionError/JSONEncodeError in log messages). Tests in `tests/test_prefab_persistence.py`. Bug 3.5 fixed: atomic name selection via itertools.count + root entity creation under `threading.Lock` in `instantiate_prefab`; real concurrency regression tests pass (100 threads, no name collision). Bug 3.6 fixed in critical `engine/scenes/scene_manager.py`: `save_scene` does post-write readback → json.load/migrate/validate/entity-count check. Tests in `tests/test_scene_save_integrity.py`. Docs updated: `docs/schema_serialization.md` (scene save integrity check), `docs/TECHNICAL.md` (atomic naming for prefab instantiate). Builder checks: prefab tests 10 OK + governance subset OK; scene tests/regressions 196 OK; docs governance subset OK; motor doctor healthy. Phase 3 status: implemented/pending validation. |
| 2026-06-01 | Cycle 3 validated | Validator: 262 focused/regression tests pass (prefab 10 OK, scene 196 OK, governance/contract subsets OK). motor doctor healthy. ruff/mypy global fail only pre-existing unrelated debt. Reviewer: approved, must_fix=0. AI audit: applicable, score 90, must_fix=0. Recommendations: document prefab CLI/API flows later (Phase 5). Cycle 3 DoD: focused_tests_pass=true, review_must_fix=0, ai_score=90, no_scope_creep=true. Phase 3 approved/complete. |
| 2026-06-01 | Cycle 4 implemented | Bug 1.1 fixed in critical `engine/scenes/scene_manager.py`: scene save callback registry, callback errors logged/non-fatal, active scene file mtime tracking and safe stale refresh in editor-facing edit_world path when not dirty; tests in `tests/test_editor_scene_sync.py`. Bug 1.2 fixed in `engine/editor/hierarchy_panel.py`: wheel scroll offset, clamp, viewport scrollbar, scrolled hit-tests verified; tests in `tests/test_hierarchy_panel_scroll.py`. Docs updated: `docs/architecture.md`, `docs/TECHNICAL.md`. Builder checks: scene sync/editor tests 138 pass; hierarchy/editor scroll tests 123 pass; docs contract/governance subsets pass; motor doctor healthy. Phase 4 status: implemented/pending validation. |
| 2026-06-01 | Cycle 4 corrected and approved | Validator: 296 tests pass after API exposure; motor doctor healthy; ruff/mypy only pre-existing unrelated debt. Reviewer: approved, must_fix=0 after path-resolution correction; remaining findings non-blocking. AI audit: applicable, score 95 after EngineAPI/docs exposure, must_fix=0; CLI refresh recommendation non-blocking. Bug 1.1 and 1.2 complete. Cycle 4 DoD: focused_tests_pass=true, review_must_fix=0, ai_score=95, no_scope_creep=true. Phase 4 approved/complete. |
| 2026-06-01 | Cycle 5 implemented | Bug 3.2 fixed: unjustified START_HERE/examples skip guards removed/replaced by assertions; legitimate Box2D/Prueva1/DPAPI skips keep optional behavior with actionable messages. New tests in `tests/test_bug_report_governance.py`. Bug 3.3 fixed: marker policy added to `docs/documentation_governance.md`; governance tests assert policy and no false BUG markers. Docs gaps closed: `docs/agents.md` documents Sprite.source_slice, Animator string, layered render, prefabs; `docs/cli.md` documents prefab commands; `docs/bug_report.md` statuses updated. Builder checks: bug_report_governance 6 OK; contract/coherence 81 OK; physics 38 OK; repository/start_here 29 OK. Phase 5 status: implemented/pending validation. |
| 2026-06-01 | Cycle 5 validated | Validator: 215 tests pass; `motor ai start --json` passes; `motor doctor` healthy; ruff/mypy only pre-existing unrelated debt. Reviewer: approved after docs correction, must_fix=0; all 15 bug_report items have explicit resolved status. AI audit: applicable, score 100, must_fix=0. Cycle 5 DoD: focused_tests_pass=true, review_must_fix=0, ai_score=100, no_scope_creep=true. Phase 5 approved/complete. All 5 phases complete. Awaiting documenter/committer finalization. |
| 2026-06-01 | TASK CLOSED | **Status: partial.** Reason: strict Queen DoD cannot be fully satisfied due to pre-existing global failures (full unittest discover has 2 failures + 1 error, ruff has 6 pre-existing issues, mypy has 52 pre-existing issues). No commit created because user did not explicitly request one and strict DoD is not met. User-requested scope is fully complete: all 15 bug_report items resolved, all 5 phases approved, final review approved (must_fix=0), AI audit score 100. No scope creep (root `0` file removed, `settings/project_settings.json` reverted). 307 targeted tests pass, `motor ai start` and `motor doctor` healthy. Risks remaining: pre-existing global test/lint/type debt only. Final report: `.motor/queen_state/reports/queen-20260601-001.json`. |

