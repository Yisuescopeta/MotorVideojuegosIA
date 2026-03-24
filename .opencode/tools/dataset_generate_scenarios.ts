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
  description: "Generate scenario datasets using the existing scenario_dataset_cli.py command.",
  args: {
    scene: tool.schema.string().describe("Template scene path inside the repo"),
    count: tool.schema.number().int().positive().default(100).describe("Number of scenarios"),
    seed: tool.schema.number().int().default(123).describe("Deterministic seed"),
    out_dir: tool.schema.string().describe("Output directory under artifacts/ or .motor/"),
  },
  async execute(args, context) {
    const cwd = worktreeRoot(context)
    const scenePath = resolveInsideWorktree(context, args.scene)
    const outDir = ensureOutputDirAllowed(context, args.out_dir)
    await ensureDir(outDir)

    const script = path.join(cwd, "tools", "scenario_dataset_cli.py")
    const command = buildPythonCommand(script, [
      "generate-scenarios",
      repoRelative(context, scenePath),
      "--count",
      args.count,
      "--seed",
      args.seed,
      "--out-dir",
      repoRelative(context, outDir),
    ])
    const result = await runCommand(command, cwd)
    const manifestPath = path.join(outDir, "manifest.json")

    return {
      ok: result.exitCode === 0,
      summary:
        result.exitCode === 0
          ? successSummary("dataset_generate_scenarios", repoRelative(context, manifestPath))
          : failureSummary("dataset_generate_scenarios", result.exitCode),
      command,
      cwd,
      exitCode: result.exitCode,
      stdout: result.stdout,
      stderr: result.stderr,
      outputDir: repoRelative(context, outDir),
      data: {
        scene: repoRelative(context, scenePath),
        manifest_path: repoRelative(context, manifestPath),
        manifest: await readJsonIfExists(manifestPath),
      },
    }
  },
})
