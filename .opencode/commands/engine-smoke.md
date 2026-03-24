---
description: Run the engine smoke flow for a scene
agent: build
---

Run the custom tool `engine_smoke` with:

- `scene`: `$1`
- `frames`: `$2` if provided, otherwise `5`
- `seed`: `$3` if provided, otherwise `123`
- `out_dir`: `artifacts/opencode/engine_smoke`

What this validates:
- scene validation
- asset validation
- migration to a reproducible artifact
- build-assets
- short headless run
- short profile run

Where artifacts are written:
- `artifacts/opencode/engine_smoke/`

Requirements:
- do not write outside `artifacts/` or `.motor/`
- summarize the generated smoke artifacts and whether the run passed
- if `$1` is missing, ask for the scene path before proceeding
