from __future__ import annotations

import re
import sys
from pathlib import Path


NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def _read_frontmatter(skill_path: Path) -> dict[str, str]:
    text = skill_path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ValueError(f"{skill_path.as_posix()}: missing YAML frontmatter")
    end = text.find("\n---\n", 4)
    if end == -1:
        raise ValueError(f"{skill_path.as_posix()}: unterminated YAML frontmatter")
    block = text[4:end]
    result: dict[str, str] = {}
    for raw_line in block.splitlines():
        line = raw_line.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        if line.startswith(" ") or line.startswith("\t"):
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        result[key.strip()] = value.strip().strip('"').strip("'")
    return result


def validate_skill_dir(skill_dir: Path) -> list[str]:
    errors: list[str] = []
    folder_name = skill_dir.name
    skill_md = skill_dir / "SKILL.md"

    if not NAME_RE.fullmatch(folder_name) or not (1 <= len(folder_name) <= 64):
        errors.append(f"{skill_dir.as_posix()}: invalid folder name '{folder_name}'")
        return errors

    if not skill_md.exists():
        errors.append(f"{skill_dir.as_posix()}: missing SKILL.md")
        return errors

    try:
        frontmatter = _read_frontmatter(skill_md)
    except ValueError as exc:
        errors.append(str(exc))
        return errors

    name = frontmatter.get("name", "")
    description = frontmatter.get("description", "")

    if not name:
        errors.append(f"{skill_md.as_posix()}: missing frontmatter field 'name'")
    elif name != folder_name:
        errors.append(f"{skill_md.as_posix()}: frontmatter name '{name}' must match folder '{folder_name}'")
    elif not NAME_RE.fullmatch(name) or not (1 <= len(name) <= 64):
        errors.append(f"{skill_md.as_posix()}: invalid skill name '{name}'")

    if not description:
        errors.append(f"{skill_md.as_posix()}: missing frontmatter field 'description'")

    return errors


def main() -> int:
    root = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else (Path.cwd() / ".agents" / "skills").resolve()
    if not root.exists():
        print(f"[ERROR] skills path not found: {root.as_posix()}")
        return 1

    if root.is_dir() and (root / "SKILL.md").exists():
        errors = validate_skill_dir(root)
        if errors:
            for item in errors:
                print(f"[ERROR] {item}")
            return 1
        print(f"[OK] validated skill: {root.as_posix()}")
        return 0

    errors: list[str] = []
    validated = 0
    for child in sorted(root.iterdir()):
        if not child.is_dir():
            continue
        validated += 1
        errors.extend(validate_skill_dir(child))

    if errors:
        for item in errors:
            print(f"[ERROR] {item}")
        return 1

    print(f"[OK] validated {validated} skill directories: {root.as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
