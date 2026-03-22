from __future__ import annotations

import json
from pathlib import Path
from typing import List

from engine.ai.types import PlanQuestion, SkillManifest


class SkillRegistry:
    def __init__(self, root: Path | None = None) -> None:
        self._root = root or Path(__file__).resolve().parent / "skill_manifests"
        self._skills = self._load_all()

    def _load_all(self) -> List[SkillManifest]:
        manifests: List[SkillManifest] = []
        for file_path in sorted(self._root.glob("*.json")):
            with file_path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
            manifests.append(
                SkillManifest(
                    id=str(data["id"]),
                    version=int(data["version"]),
                    domain=str(data["domain"]),
                    summary=str(data["summary"]),
                    trigger_keywords=[str(item) for item in data.get("trigger_keywords", [])],
                    capabilities=[str(item) for item in data.get("capabilities", [])],
                    planning_questions=[
                        PlanQuestion(
                            id=str(question["id"]),
                            text=str(question["text"]),
                            rationale=str(question.get("rationale", "")),
                            choices=[str(choice) for choice in question.get("choices", [])],
                            required=bool(question.get("required", True)),
                        )
                        for question in data.get("planning_questions", [])
                    ],
                    allowed_operations=[str(item) for item in data.get("allowed_operations", [])],
                    validations=[str(item) for item in data.get("validations", [])],
                )
            )
        return manifests

    def list_skills(self) -> List[SkillManifest]:
        return list(self._skills)

    def match(self, prompt: str) -> List[SkillManifest]:
        lower = prompt.lower()
        matched: List[SkillManifest] = []
        for skill in self._skills:
            if any(keyword.lower() in lower for keyword in skill.trigger_keywords):
                matched.append(skill)
        if matched:
            return matched
        core = [skill for skill in self._skills if skill.domain == "core"]
        return core or list(self._skills)
