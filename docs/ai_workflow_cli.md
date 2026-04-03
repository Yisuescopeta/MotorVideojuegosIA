# AI Workflow CLI

The AI-assisted workflow CLI is a thin automation surface for coding agents and scripted environments. It does not add a new agent, prompt parser, skill system, or UI automation layer. It only wires the existing workflow services into stable command-line entry points.

## Intended Sequence

1. Generate a context pack:

```bash
py -3 -m tools.engine_cli ai-context --project-root .
```

2. Run a structured workflow sequence from JSON:

```bash
py -3 -m tools.engine_cli ai-workflow --spec artifacts/workflow.json --out artifacts/workflow_report.json
```

3. Run validation directly when needed:

```bash
py -3 -m tools.engine_cli ai-validate --target scene-file --path levels/demo_level.json
py -3 -m tools.engine_cli ai-validate --target project
```

4. Run headless verification from a saved scenario:

```bash
py -3 -m tools.engine_cli ai-verify --scenario artifacts/verify_scene.json --out artifacts/verify_report.json
```

## JSON Inputs

`ai-verify` expects a JSON object matching `HeadlessVerificationScenario`.

Example:

```json
{
  "scenario_id": "verify-demo",
  "project_root": ".",
  "scene_path": "levels/demo_level.json",
  "play": true,
  "step_frames": 5,
  "assertions": [
    {
      "assertion_id": "scene-selected",
      "kind": "selected_scene_is",
      "expected_scene_path": "levels/demo_level.json"
    }
  ]
}
```

`ai-workflow` expects a JSON object with optional `context`, `authoring_request`, `validation`, and `verification` sections.

Example:

```json
{
  "project_root": ".",
  "context": {
    "enabled": true
  },
  "authoring_request": {
    "request_id": "workflow-demo",
    "label": "create-scene",
    "operations": [
      {
        "operation_id": "create-scene",
        "kind": "create_scene",
        "scene_name": "Workflow Scene"
      },
      {
        "operation_id": "save-scene",
        "kind": "save_scene",
        "scene_ref": "levels/workflow_scene.json"
      }
    ]
  },
  "validation": {
    "target": "active-scene"
  },
  "verification": {
    "scenario_id": "verify-demo",
    "scene_path": "levels/workflow_scene.json",
    "assertions": [
      {
        "assertion_id": "scene-selected",
        "kind": "selected_scene_is",
        "expected_scene_path": "levels/workflow_scene.json"
      }
    ]
  }
}
```

## Notes

- `ai-workflow` stays thin. It delegates to the context pack generator, structured authoring executor, validation service, and headless verification harness.
- Structured authoring requests must not mix workspace operations (`create_scene`, `open_scene`, `activate_scene`, `save_scene`) with transactional scene edits in the same execution request. Run those as two separate requests so the transaction boundary and rollback behavior stay predictable.
- Verification runs against saved project content. If the workflow edits a scene and verification must observe the change, the workflow spec must include a save operation before verification.
- AI workflow CLI commands use project-local automation state under `.motor/ai_assist_state` so repeated runs stay isolated from user-global editor state.
- Use `--json` when the caller needs machine-friendly stdout.
- Use `--out` on `ai-verify` and `ai-workflow` when the caller wants a JSON report artifact on disk.

## Out Of Scope

- Conversational command flows
- LLM integration
- Skills
- UI click automation
- A broad test framework inside the engine
