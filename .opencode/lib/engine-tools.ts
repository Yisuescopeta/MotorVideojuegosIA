import path from "path"
import { mkdir } from "fs/promises"

export type ToolResult = {
  ok: boolean
  summary: string
  command: string[]
  cwd: string
  exitCode: number
  stdout: string
  stderr: string
  outputPath?: string
  outputDir?: string
  data?: unknown
}

export function worktreeRoot(context: { worktree?: string; directory?: string }) {
  return path.resolve(context.worktree ?? context.directory ?? process.cwd())
}

export function resolveInsideWorktree(context: { worktree?: string; directory?: string }, inputPath: string) {
  const root = worktreeRoot(context)
  const candidate = path.resolve(root, inputPath)
  if (!isInside(root, candidate)) {
    throw new Error(`Path must stay inside the repo: ${inputPath}`)
  }
  return candidate
}

export function ensureOutputPathAllowed(
  context: { worktree?: string; directory?: string },
  inputPath: string,
) {
  const root = worktreeRoot(context)
  const candidate = path.resolve(root, inputPath)
  const artifactsRoot = path.resolve(root, "artifacts")
  const motorRoot = path.resolve(root, ".motor")
  if (!isInside(artifactsRoot, candidate) && !isInside(motorRoot, candidate)) {
    throw new Error(`Outputs must stay under artifacts/ or .motor/: ${inputPath}`)
  }
  return candidate
}

export function ensureOutputDirAllowed(
  context: { worktree?: string; directory?: string },
  inputPath: string,
) {
  return ensureOutputPathAllowed(context, inputPath)
}

export async function ensureParentDir(filePath: string) {
  await mkdir(path.dirname(filePath), { recursive: true })
}

export async function ensureDir(dirPath: string) {
  await mkdir(dirPath, { recursive: true })
}

export function repoRelative(context: { worktree?: string; directory?: string }, absPath: string) {
  return path.relative(worktreeRoot(context), absPath).replaceAll("\\", "/")
}

export async function runCommand(
  command: string[],
  cwd: string,
): Promise<{ exitCode: number; stdout: string; stderr: string }> {
  const proc = Bun.spawn(command, {
    cwd,
    stdout: "pipe",
    stderr: "pipe",
  })
  const [stdout, stderr, exitCode] = await Promise.all([
    new Response(proc.stdout).text(),
    new Response(proc.stderr).text(),
    proc.exited,
  ])
  return {
    exitCode,
    stdout: stdout.trim(),
    stderr: stderr.trim(),
  }
}

export function pythonExecutable() {
  return process.platform === "win32" ? ["py", "-3"] : ["python3"]
}

export function buildPythonCommand(scriptPath: string, args: Array<string | number>) {
  return [...pythonExecutable(), scriptPath, ...args.map((item) => String(item))]
}

export async function readJsonIfExists(filePath?: string) {
  if (!filePath) return undefined
  try {
    return await Bun.file(filePath).json()
  } catch {
    return undefined
  }
}

export function isInside(parent: string, child: string) {
  const relative = path.relative(parent, child)
  return relative === "" || (!relative.startsWith("..") && !path.isAbsolute(relative))
}

export function successSummary(label: string, detail: string) {
  return `${label} completed: ${detail}`
}

export function failureSummary(label: string, exitCode: number) {
  return `${label} failed with exit code ${exitCode}`
}
