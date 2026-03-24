---
description: Generate scenario datasets from a scene template
agent: build
---

Run the custom tool `dataset_generate_scenarios` with:

- `scene`: `$1`
- `count`: `$2` if provided, otherwise `100`
- `seed`: `$3` if provided, otherwise `123`
- `out_dir`: `artifacts/opencode/generated_scenarios`

What this validates:
- scenario generation from an existing template scene
- manifest emission and reproducible dataset layout

Where artifacts are written:
- `artifacts/opencode/generated_scenarios/`

Requirements:
- do not use raw bash for this flow
- summarize the manifest path and the number of scenarios generated
- if `$1` is missing, ask for the scene path before proceeding
