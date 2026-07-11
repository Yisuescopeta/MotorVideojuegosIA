# Task 1 — Migracion Codex Reina

Read `docs/plans/active/queen-20260710-001-codex-queen-migration.md` first; it is the approved requirements source.

Implement Phases 1-3 completely. Create `.agents/skills/queen/` using the official skill-creator `init_skill.py`, then customize it. Create `.codex/config.toml`, 20 standalone `.codex/agents/*.toml`, canonical machine-readable contracts, `validate_result.py`, tests, and docs.

Critical constraints:

- Do not touch `engine/**`, `cli/**`, `main.py`, `START_HERE_AI.md`, `docs/archive/**`, `.opencode/**`, or `opencode.json`.
- Keep OpenCode behavior and existing tests intact.
- Codex root session is Queen; do not create `queen.toml`.
- Use `agents.max_depth=1`, `agents.max_threads=3`.
- Read-only roles use `sandbox_mode="read-only"`; writers use `workspace-write`.
- Fast: `gpt-5.6-terra` low; standard: `gpt-5.6` high; deep: `gpt-5.6` xhigh. Fixed roles choose least capable sufficient configuration.
- Every mandatory result type including committer has JSON schema and validator coverage.
- Codex names use underscores; maintain explicit mapping to OpenCode hyphen names.
- Preserve full role contracts by referencing and requiring complete reads of corresponding `.opencode/agents/*.md`; add Codex-specific responsibility, input/output, blocking and scope rules in TOML.
- Godot roles must integrate `.agents/skills/godot-feature-adapter/SKILL.md`.
- Add tests without relaxing existing assertions.
- Separate technical sandbox guarantees from instruction/test-enforced operational guarantees.
- Update required `docs/refactor/` baseline files and create `docs/refactor/phase_codex_queen_migration_result.md`.

Focused checks:

`py -m unittest tests.test_codex_queen_contract tests.test_queen_agent_contract -v`

`py -m unittest tests.test_repository_governance tests.test_motor_cli_contract tests.test_start_here_ai_coherence -v`

`git diff --check`

Write full report to `.superpowers/sdd/task-1-report.md`. Return JSON status, files changed, commands, failures and risks.
