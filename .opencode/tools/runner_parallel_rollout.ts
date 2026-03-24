import path from "path"
import { tool } from "@opencode-ai/plugin"
import {
  buildPythonCommand,
  ensureDir,
  ensureOutputDirAllowed,
  failureSummary,
  readJsonIfExists,
  repoRelative,
  resolveInsideWorktree,
  runCommand,
  successSummary,
  worktreeRoot,
} from "../lib/engine-tools"

export default tool({
  description: "Run the parallel rollout runner and return the structured parallel report JSON.",
  args: {
    scene: tool.schema.string().describe("Scene path inside the repo"),
    workers: tool.schema.number().int().positive().default(2).describe("Worker subprocess count"),
    episodes: tool.schema.number().int().positive().default(8).describe("Total episodes"),
    max_steps: tool.schema.number().int().positive().default(120).describe("Max steps per episode"),
    seed: tool.schema.number().int().default(123).describe("Deterministic seed"),
    out_dir: tool.schema.string().describe("Output directory under artifacts/ or .motor/"),
  },
  async execute(args, context) {
    const cwd = worktreeRoot(context)
    const scenePath = resolveInsideWorktree(context, args.scene)
    const outDir = ensureOutputDirAllowed(context, args.out_dir)
    await ensureDir(outDir)

    const script = path.join(cwd, "tools", "parallel_rollout_runner.py")
    const command = buildPythonCommand(script, [
      repoRelative(context, scenePath),
      "--workers",
      args.workers,
      "--episodes",
      args.episodes,
      "--max-steps",
      args.max_steps,
      "--seed",
      args.seed,
      "--out-dir",
      repoRelative(context, outDir),
    ])
    const result = await runCommand(command, cwd)
    const reportPath = path.join(outDir, "parallel_report.json")

    return {
      ok: result.exitCode === 0,
      summary:
        result.exitCode === 0
          ? successSummary("runner_parallel_rollout", repoRelative(context, reportPath))
          : failureSummary("runner_parallel_rollout", result.exitCode),
      command,
      cwd,
      exitCode: result.exitCode,
      stdout: result.stdout,
      stderr: result.stderr,
      outputDir: repoRelative(context, outDir),
      data: {
        scene: repoRelative(context, scenePath),
        report_path: repoRelative(context, reportPath),
        report: await readJsonIfExists(reportPath),
      },
    }
  },
})
