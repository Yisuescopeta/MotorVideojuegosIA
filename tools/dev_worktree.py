from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from tools._tooling_common import (
    ExitCode,
    branch_exists,
    current_branch,
    format_command,
    head_sha,
    is_dirty,
    make_response,
    normalize_path,
    parse_worktree_porcelain,
    print_json,
    resolve_git_root,
    run_git,
    slugify_branch_name,
)


def get_repo_status(repo_path: str | Path) -> dict[str, Any]:
    requested_path = normalize_path(repo_path)
    repo_root = resolve_git_root(requested_path)
    if repo_root is None:
        return {
            "requested_path": requested_path.as_posix(),
            "cwd": Path.cwd().resolve().as_posix(),
            "is_git_repo": False,
            "repo_root": None,
            "branch": None,
            "detached_head": False,
            "dirty": False,
            "head": None,
        }

    branch_name = current_branch(repo_root)
    return {
        "requested_path": requested_path.as_posix(),
        "cwd": Path.cwd().resolve().as_posix(),
        "is_git_repo": True,
        "repo_root": repo_root.as_posix(),
        "branch": branch_name,
        "detached_head": branch_name is None,
        "dirty": is_dirty(repo_root),
        "head": head_sha(repo_root),
    }


def list_worktrees(repo_path: str | Path) -> dict[str, Any]:
    status = get_repo_status(repo_path)
    if not status["is_git_repo"]:
        return status | {"worktrees": []}

    result = run_git(["worktree", "list", "--porcelain"], cwd=status["repo_root"])
    worktrees = parse_worktree_porcelain(result.stdout) if result.returncode == 0 else []
    return status | {
        "worktrees": worktrees,
        "git_returncode": result.returncode,
        "git_stderr": result.stderr,
    }


def validate_worktree(
    repo_path: str | Path,
    *,
    expected_branch: str = "",
    allow_detached: bool = False,
    require_clean: bool = False,
) -> dict[str, Any]:
    status = get_repo_status(repo_path)
    issues: list[str] = []

    if not status["is_git_repo"]:
        issues.append("Path is not inside a git repository")
    else:
        if status["detached_head"] and not allow_detached:
            issues.append("Detached HEAD is not allowed")
        if expected_branch and status["branch"] != expected_branch:
            issues.append(
                f"Expected branch '{expected_branch}' but found '{status['branch'] or 'DETACHED'}'"
            )
        if require_clean and status["dirty"]:
            issues.append("Working tree is not clean")

    return status | {
        "expected_branch": expected_branch or None,
        "allow_detached": allow_detached,
        "require_clean": require_clean,
        "valid": not issues,
        "issues": issues,
    }


def plan_worktree(
    repo_path: str | Path,
    *,
    branch: str,
    base_dir: str = "",
    dest: str = "",
) -> dict[str, Any]:
    status = get_repo_status(repo_path)
    if not status["is_git_repo"]:
        return status | {
            "valid": False,
            "issues": ["Path is not inside a git repository"],
        }

    repo_root = Path(status["repo_root"])
    if dest:
        destination = normalize_path(dest)
    else:
        base = normalize_path(base_dir) if base_dir else repo_root.parent
        destination = (base / f"{repo_root.name}-{slugify_branch_name(branch)}").resolve()

    exists_locally = branch_exists(repo_root, branch)
    command: list[str] = ["git", "worktree", "add"]
    if exists_locally:
        command.extend([destination.as_posix(), branch])
    else:
        command.extend(["-b", branch, destination.as_posix()])

    return status | {
        "valid": True,
        "branch": branch,
        "branch_exists_locally": exists_locally,
        "destination": destination.as_posix(),
        "command": command,
        "command_text": format_command(command),
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read-only helper for git branch and worktree diagnostics.")
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repo root or any path inside the target repository.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    status_parser = subparsers.add_parser("status", help="Report current branch, dirty state, and detached HEAD.")
    status_parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON output.")

    list_parser = subparsers.add_parser("list", help="List worktrees via git worktree list --porcelain.")
    list_parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON output.")

    validate_parser = subparsers.add_parser("validate", help="Validate branch, detached HEAD policy, and clean state.")
    validate_parser.add_argument("--expected-branch", default="", help="Expected current branch name.")
    validate_parser.add_argument("--allow-detached", action="store_true", help="Allow detached HEAD.")
    validate_parser.add_argument("--require-clean", action="store_true", help="Require a clean working tree.")
    validate_parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON output.")

    plan_parser = subparsers.add_parser("plan", help="Recommend a git worktree add command without executing it.")
    plan_group = plan_parser.add_mutually_exclusive_group()
    plan_group.add_argument("--base-dir", default="", help="Base directory used to derive the destination path.")
    plan_group.add_argument("--dest", default="", help="Explicit destination path for the planned worktree.")
    plan_parser.add_argument("--branch", required=True, help="Target branch name for the planned worktree.")
    plan_parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON output.")

    return parser


def _render_text(payload: dict[str, Any]) -> str:
    data = payload["data"]
    if "worktrees" in data:
        lines = [payload["message"]]
        for worktree in data["worktrees"]:
            branch_name = worktree["branch"] or "DETACHED"
            lines.append(f"- {worktree['path']} [{branch_name}]")
        return "\n".join(lines)

    if "command_text" in data:
        return "\n".join(
            [
                payload["message"],
                f"Destination: {data['destination']}",
                f"Command: {data['command_text']}",
            ]
        )

    if "valid" in data and "issues" in data:
        lines = [payload["message"]]
        if data["issues"]:
            lines.extend(f"- {issue}" for issue in data["issues"])
        return "\n".join(lines)

    return "\n".join(
        [
            payload["message"],
            f"Repo root: {data['repo_root']}",
            f"Branch: {data['branch'] or 'DETACHED'}",
            f"Dirty: {data['dirty']}",
            f"Detached: {data['detached_head']}",
        ]
    )


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    if args.command == "status":
        data = get_repo_status(args.repo_root)
        success = bool(data["is_git_repo"])
        payload = make_response(success, "Repository status loaded" if success else "Repository not found", data)
    elif args.command == "list":
        data = list_worktrees(args.repo_root)
        success = bool(data["is_git_repo"]) and data.get("git_returncode", 0) == 0
        payload = make_response(success, "Worktrees listed" if success else "Unable to list worktrees", data)
    elif args.command == "validate":
        data = validate_worktree(
            args.repo_root,
            expected_branch=args.expected_branch,
            allow_detached=args.allow_detached,
            require_clean=args.require_clean,
        )
        payload = make_response(data["valid"], "Worktree validation passed" if data["valid"] else "Worktree validation failed", data)
    else:
        data = plan_worktree(
            args.repo_root,
            branch=args.branch,
            base_dir=args.base_dir,
            dest=args.dest,
        )
        payload = make_response(data["valid"], "Worktree plan generated" if data["valid"] else "Worktree plan failed", data)

    if getattr(args, "json", False):
        print_json(payload)
    else:
        print(_render_text(payload))

    return int(ExitCode.OK if payload["success"] else ExitCode.FAILED)


if __name__ == "__main__":
    raise SystemExit(main())
