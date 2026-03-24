---
description: Replay one logged episode and verify the report
agent: build
---

Run the custom tool `dataset_replay_episode` with:

- `episodes_jsonl`: `$1`
- `episode_id`: `$2`
- `out`: `artifacts/opencode/episodes/replay_$2.json`

What this validates:
- replay of one logged episode from the dataset
- replay report generation for a concrete episode id

Where artifacts are written:
- `artifacts/opencode/episodes/replay_$2.json`

Requirements:
- do not use raw bash for this flow
- summarize whether the replay matched and where the report was written
- if `$1` or `$2` is missing, ask for the missing argument before proceeding
