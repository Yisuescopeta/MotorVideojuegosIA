# AI-Assisted Workflows Foundation

Status: `experimental/tooling`.

## Scope

This document defines a small foundation layer for AI-assisted workflows in the
engine. The layer is intended for existing coding agents and automation callers
that need typed workflow state, explicit validation, and reproducible
verification. It is not a new autonomous subsystem.

The implementation lives under `engine/workflows/ai_assist/` and provides:

- typed context snapshots for the active project and scene workspace
- typed authoring requests and explicit authoring plans
- typed validation and verification reports
- a small workflow summary helper that composes those phases

## Non-goals

This foundation does not add:

- a new autonomous agent runtime
- natural-language parsing
- LLM or provider integration
- a skill system
- editor UI changes
- duplicate scene or prefab mutation logic

## Public API Boundary

Scene, prefab, script, and asset-content workflows must treat
`engine.api.EngineAPI` as the mutation boundary. This layer may read project and
runtime facts from existing public surfaces such as:

- project manifest and project-relative paths
- active scene summary and open scene list
- project asset, prefab, and script listings
- runtime status and headless verification hooks

It must not bypass `EngineAPI` to mutate scene state, and it must not re-create
transaction, undo/redo, prefab, or schema logic that already exists in
`SceneManager`, authoring APIs, or serialization helpers.

## Phase Separation

The foundation keeps four workflow phases explicit and separate:

1. Context
   - Capture a typed snapshot of project facts, scene workspace facts, feature
     metadata, and inventory summaries.
   - Keep the snapshot serializable and stable enough for tests and automation.

2. Authoring
   - Represent intended work as a structured request and an explicit ordered
     plan.
   - Do not parse free-form instructions in this layer.
   - Keep workspace scene lifecycle operations separate from transactional
     scene edits. Mixed requests are intentionally rejected so rollback,
     active-scene targeting, and persistence behavior remain explicit.

3. Validation
   - Reuse existing schema migration and validation helpers for scene/prefab
     payloads.
   - Add workflow-level checks such as missing targets, empty plans, or paths
     outside the active project.

4. Verification
   - Reuse existing headless runtime capture and script execution
     infrastructure.
   - Keep verification evidence distinct from validation so a caller can reason
     separately about structural correctness versus runtime evidence.

## Why This Fits The Repo

This design matches the current repo shape:

- `EngineAPI` already exposes a stable public facade over runtime, authoring,
  scene workspace, assets/project, and UI concerns.
- scene and prefab schema migration and validation already live in
  `engine.serialization.schema`.
- headless runtime capture and script execution already exist for reproducible
  verification.

The result is intentionally small and conservative: composition over framework,
typed reports over hidden orchestration, and reuse of existing public seams over
new engine abstractions.

Automation-owned runs should also stay self-contained. The AI-assisted workflow
CLI and headless verification paths use project-local state under
`.motor/ai_assist_state` instead of user-global editor state so repeated runs
remain deterministic and isolated.

`engine/agent/` is a separate experimental layer for clean-room agent sessions,
the fake provider, runtime loop, tools and permissions. It consumes this
foundation for context, structured authoring and verification; it does not
replace these workflow contracts. Agent v2 keeps online providers, MCP, web,
remote execution and subagents out of scope until the core turn/tool runtime is
stable.
