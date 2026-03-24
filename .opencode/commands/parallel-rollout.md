---
description: Run the parallel rollout runner for a scene
agent: build
---

Run the custom tool `runner_parallel_rollout` with:

- `scene`: `$1`
- `workers`: `$2` if provided, otherwise `2`
- `episodes`: `$3` if provided, otherwise `8`
- `max_steps`: `$4` if provided, otherwise `120`
- `seed`: `$5` if provided, otherwise `123`
- `out_dir`: `artifacts/opencode/parallel_rollout`

What this validates:
- subprocess-based parallel rollout execution
- shard outputs and consolidated throughput report

Where artifacts are written:
- `artifacts/opencode/parallel_rollout/`

Requirements:
- do not write outside `artifacts/` or `.motor/`
- summarize worker count, total episodes, failures if any, and the report path
- if `$1` is missing, ask for the scene path before proceeding
