---
description: Run reproducible logged episodes for a scene
agent: build
---

Run the custom tool `dataset_run_episodes` with:

- `scene`: `$1`
- `episodes`: `$2` if provided, otherwise `100`
- `max_steps`: `$3` if provided, otherwise `120`
- `seed`: `$4` if provided, otherwise `123`
- `out`: `artifacts/opencode/episodes/episodes.jsonl`
- `summary_out`: `artifacts/opencode/episodes/summary.json`

What this validates:
- reproducible episode logging
- JSONL dataset generation
- summary generation for the rollout batch

Where artifacts are written:
- `artifacts/opencode/episodes/episodes.jsonl`
- `artifacts/opencode/episodes/summary.json`

Requirements:
- do not write outside `artifacts/` or `.motor/`
- summarize completed episodes, summary path, and key counters
- if `$1` is missing, ask for the scene path before proceeding
