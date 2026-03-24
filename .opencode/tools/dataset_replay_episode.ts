import path from "path"
import { tool } from "@opencode-ai/plugin"
import {
  buildPythonCommand,
  ensureOutputPathAllowed,
  ensureParentDir,
  failureSummary,
  readJsonIfExists,
  repoRelative,
  resolveInsideWorktree,
  runCommand,
  successSummary,
  worktreeRoot,
} from "../lib/engine-tools"

export default tool({
  description: "Replay one logged episode using scenario_dataset_cli.py and return the replay report JSON.",
  args: {
    episodes_jsonl: tool.schema.string().describe("Dataset JSONL path inside the repo, usually under artifacts/"),
    episode_id: tool.schema.string().describe("Episode identifier, for example episode_0000"),
    out: tool.schema.string().describe("Replay JSON path under artifacts/ or .motor/"),
  },
  async execute(args, context) {
    const cwd = worktreeRoot(context)
    const datasetPath = resolveInsideWorktree(context, args.episodes_jsonl)
    const outPath = ensureOutputPathAllowed(context, args.out)
    await ensureParentDir(outPath)

    const script = path.join(cwd, "tools", "scenario_dataset_cli.py")
    const command = buildPythonCommand(script, [
      "replay-episode",
      repoRelative(context, datasetPath),
      "--episode-id",
      args.episode_id,
      "--out",
      repoRelative(context, outPath),
    ])
    const result = await runCommand(command, cwd)
    const replayReport = await readJsonIfExists(outPath)

    return {
      ok: result.exitCode === 0,
      summary:
        result.exitCode === 0
          ? successSummary("dataset_replay_episode", repoRelative(context, outPath))
          : failureSummary("dataset_replay_episode", result.exitCode),
      command,
      cwd,
      exitCode: result.exitCode,
      stdout: result.stdout,
      stderr: result.stderr,
      outputPath: repoRelative(context, outPath),
      data: {
        dataset_path: repoRelative(context, datasetPath),
        episode_id: args.episode_id,
        replay_path: repoRelative(context, outPath),
        replay: replayReport,
      },
    }
  },
})
