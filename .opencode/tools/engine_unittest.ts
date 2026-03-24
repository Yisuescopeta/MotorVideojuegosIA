import { tool } from "@opencode-ai/plugin"
import {
  buildPythonCommand,
  failureSummary,
  runCommand,
  successSummary,
  worktreeRoot,
} from "../lib/engine-tools"

export default tool({
  description: "Run the repo unittest discover suite with a safe fixed command.",
  args: {},
  async execute(_args, context) {
    const cwd = worktreeRoot(context)
    const command = [...buildPythonCommand("-m", ["unittest", "discover", "-s", "tests", "-p", "test_*.py"])]
    const result = await runCommand(command, cwd)

    return {
      ok: result.exitCode === 0,
      summary:
        result.exitCode === 0
          ? successSummary("engine_unittest", "unittest discover finished successfully")
          : failureSummary("engine_unittest", result.exitCode),
      command,
      cwd,
      exitCode: result.exitCode,
      stdout: result.stdout,
      stderr: result.stderr,
      data: {
        runner: "python -m unittest discover",
        suite: "tests/test_*.py",
      },
    }
  },
})
