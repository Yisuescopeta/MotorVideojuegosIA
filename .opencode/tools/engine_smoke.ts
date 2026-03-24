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
  description: "Run the unified engine smoke command against a scene and export artifacts under artifacts/ or .motor/.",
  args: {
    scene: tool.schema.string().describe("Scene JSON path inside the repo, for example levels/demo_level.json"),
    frames: tool.schema.number().int().positive().default(5).describe("Frames to simulate"),
    seed: tool.schema.number().int().default(123).describe("Deterministic seed"),
    out_dir: tool.schema.string().describe("Output directory under artifacts/ or .motor/"),
  },
  async execute(args, context) {
    const cwd = worktreeRoot(context)
    const scenePath = resolveInsideWorktree(context, args.scene)
    const outDir = ensureOutputDirAllowed(context, args.out_dir)
    await ensureDir(outDir)

    const script = path.join(cwd, "tools", "engine_cli.py")
    const command = buildPythonCommand(script, [
      "smoke",
      "--scene",
      repoRelative(context, scenePath),
      "--frames",
      args.frames,
      "--seed",
      args.seed,
      "--out-dir",
      repoRelative(context, outDir),
    ])
    const result = await runCommand(command, cwd)

    const profilePath = path.join(outDir, "smoke_profile.json")
    const debugDumpPath = path.join(outDir, "smoke_debug_dump.json")
    const migratedScenePath = path.join(outDir, "smoke_migrated_scene.json")

    return {
      ok: result.exitCode === 0,
      summary:
        result.exitCode === 0
          ? successSummary("engine_smoke", repoRelative(context, outDir))
          : failureSummary("engine_smoke", result.exitCode),
      command,
      cwd,
      exitCode: result.exitCode,
      stdout: result.stdout,
      stderr: result.stderr,
      outputDir: repoRelative(context, outDir),
      data: {
        scene: repoRelative(context, scenePath),
        artifacts: {
          migrated_scene: repoRelative(context, migratedScenePath),
          debug_dump: repoRelative(context, debugDumpPath),
          profile: repoRelative(context, profilePath),
        },
        profile: await readJsonIfExists(profilePath),
        debug_dump: await readJsonIfExists(debugDumpPath),
      },
    }
  },
})
