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
  description: "Run episodes with scenario_dataset_cli.py and export the JSONL dataset plus optional summary JSON.",
  args: {
    scene: tool.schema.string().describe("Scene path inside the repo"),
    episodes: tool.schema.number().int().positive().default(100).describe("Number of episodes"),
    max_steps: tool.schema.number().int().positive().default(120).describe("Max steps per episode"),
    seed: tool.schema.number().int().default(123).describe("Deterministic seed"),
    out: tool.schema.string().describe("JSONL output path under artifacts/ or .motor/"),
    summary_out: tool.schema.string().describe("Summary JSON path under artifacts/ or .motor/"),
  },
  async execute(args, context) {
    const cwd = worktreeRoot(context)
    const scenePath = resolveInsideWorktree(context, args.scene)
    const outPath = ensureOutputPathAllowed(context, args.out)
    const summaryPath = ensureOutputPathAllowed(context, args.summary_out)
    await ensureParentDir(outPath)
    await ensureParentDir(summaryPath)

    const script = path.join(cwd, "tools", "scenario_dataset_cli.py")
    const command = buildPythonCommand(script, [
      "run-episodes",
      repoRelative(context, scenePath),
      "--episodes",
      args.episodes,
      "--max-steps",
      args.max_steps,
      "--seed",
      args.seed,
      "--out",
      repoRelative(context, outPath),
      "--summary-out",
      repoRelative(context, summaryPath),
    ])
    const result = await runCommand(command, cwd)

    return {
      ok: result.exitCode === 0,
      summary:
        result.exitCode === 0
          ? successSummary("dataset_run_episodes", repoRelative(context, summaryPath))
          : failureSummary("dataset_run_episodes", result.exitCode),
      command,
      cwd,
      exitCode: result.exitCode,
      stdout: result.stdout,
      stderr: result.stderr,
      outputPath: repoRelative(context, outPath),
      data: {
        scene: repoRelative(context, scenePath),
        dataset_path: repoRelative(context, outPath),
        summary_path: repoRelative(context, summaryPath),
        summary: await readJsonIfExists(summaryPath),
      },
    }
  },
})
