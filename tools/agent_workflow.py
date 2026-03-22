"""
tools/agent_workflow.py - Utilidades operativas para orquestacion multiagente

PROPOSITO:
    Ayuda al Agente Orquestador a preparar trabajo con contratos claros y
    validacion consistente sobre el motor 2D IA-First.

FUNCIONALIDAD:
    - Generar un Task Brief en Markdown
    - Recomendar agentes implicados
    - Sugerir validaciones segun subsistemas afectados
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict, List, Sequence, Set


PRIORITY_ORDER = [
    "core-stability",
    "test-automation",
    "api-consistency",
    "editor-ui",
    "unity-2d-core-gap",
]

IA_FIRST_RULE = (
    "La fuente de verdad debe vivir en codigo y datos serializables; "
    "la UI solo traduce ese modelo y toda accion del usuario debe existir "
    "tambien por API o datos accesibles por IA."
)

UNITY_2D_CORE_MATRIX = [
    {"feature": "entity-activation", "status": "ya existe", "priority": "unity-2d-core-gap", "depends_on": []},
    {"feature": "component-enabling", "status": "ya existe", "priority": "unity-2d-core-gap", "depends_on": ["entity-activation"]},
    {"feature": "tags-and-layers", "status": "ya existe", "priority": "unity-2d-core-gap", "depends_on": ["entity-activation"]},
    {"feature": "camera-2d", "status": "ya existe", "priority": "unity-2d-core-gap", "depends_on": ["tags-and-layers"]},
    {"feature": "input-actions", "status": "ya existe", "priority": "unity-2d-core-gap", "depends_on": ["component-enabling"]},
    {"feature": "audio-basic", "status": "ya existe", "priority": "unity-2d-core-gap", "depends_on": ["component-enabling"]},
]

AGENT_RULES: Dict[str, Set[str]] = {
    "Core Architect": {"core", "ecs", "scenes", "systems", "api", "serialization"},
    "Core Implementer": {
        "core",
        "ecs",
        "scenes",
        "systems",
        "api",
        "serialization",
        "editor",
        "cli",
        "tests",
        "tools",
    },
    "QA & Regression": {
        "core",
        "ecs",
        "scenes",
        "systems",
        "api",
        "serialization",
        "editor",
        "cli",
        "tests",
        "tools",
    },
    "Debugger": {
        "core",
        "ecs",
        "scenes",
        "systems",
        "api",
        "serialization",
        "editor",
        "cli",
        "tests",
        "tools",
    },
    "Docs & Contracts": {
        "core",
        "ecs",
        "scenes",
        "systems",
        "api",
        "serialization",
        "editor",
        "cli",
        "tests",
        "tools",
        "docs",
    },
}

VALIDATION_RULES: Dict[str, List[str]] = {
    "api": ["python tests/test_api_usage.py"],
    "scenes": ["python verify_scene_manager.py"],
    "serialization": ["python verify_serialization.py"],
    "prefabs": ["python verify_prefabs.py"],
    "editor": [
        "python verify_inspector.py",
        "python verify_hierarchy_actions.py",
        "python verify_gizmo_logic.py",
    ],
    "core": ["python main.py --headless --frames 5 --level levels/demo_level.json"],
    "cli": ["python main.py --headless --frames 5 --level levels/demo_level.json"],
    "tests": ["python tests/test_api_usage.py"],
}

DEFAULT_VALIDATIONS = [
    "python tests/test_api_usage.py",
]


def normalize_subsystems(values: Sequence[str]) -> List[str]:
    """Normaliza subsistemas y elimina duplicados conservando orden."""
    normalized: List[str] = []
    seen: Set[str] = set()
    for value in values:
        key = value.strip().lower()
        if not key or key in seen:
            continue
        normalized.append(key)
        seen.add(key)
    return normalized


def recommend_agents(subsystems: Sequence[str], has_failure: bool = False) -> List[str]:
    """Calcula agentes sugeridos para una tarea."""
    normalized = normalize_subsystems(subsystems)
    selected: List[str] = ["Agente Orquestador", "Feature Scout"]

    if any(item in {"core", "ecs", "scenes", "systems", "api", "serialization"} for item in normalized):
        selected.append("Core Architect")

    selected.append("Core Implementer")
    selected.append("QA & Regression")

    if has_failure:
        selected.append("Debugger")

    selected.append("Docs & Contracts")
    return selected


def recommend_validations(subsystems: Sequence[str]) -> List[str]:
    """Genera una lista de validaciones no visuales recomendadas."""
    normalized = normalize_subsystems(subsystems)
    commands: List[str] = []
    seen: Set[str] = set()

    for subsystem in normalized:
        for command in VALIDATION_RULES.get(subsystem, []):
            if command not in seen:
                commands.append(command)
                seen.add(command)

    if not commands:
        commands = list(DEFAULT_VALIDATIONS)

    return commands


def infer_execution_mode(subsystems: Sequence[str]) -> str:
    """Decide el modo de ejecucion recomendado."""
    normalized = set(normalize_subsystems(subsystems))
    critical = {"core", "ecs", "scenes", "systems", "api", "serialization"}
    if normalized & critical:
        return "sequential"
    return "parallel"


def build_task_brief(
    title: str,
    goal: str,
    subsystems: Sequence[str],
    files: Sequence[str],
    priority: str,
    has_failure: bool = False,
) -> str:
    """Construye el Task Brief inicial en Markdown."""
    normalized = normalize_subsystems(subsystems)
    agents = recommend_agents(normalized, has_failure=has_failure)
    validations = recommend_validations(normalized)
    execution_mode = infer_execution_mode(normalized)

    affected_files = ", ".join(files) if files else "Por determinar"
    subsystem_list = ", ".join(normalized) if normalized else "Por determinar"
    validation_lines = "\n".join(f"- {command}" for command in validations)
    agent_list = ", ".join(agents)

    return f"""# Task Brief

## Metadata

- `task_id`: TBD
- `created_by`: Agente Orquestador
- `priority`: {priority}
- `execution_mode`: {execution_mode}
- `requested_agents`: {agent_list}
- `status`: ready

## Objective

{goal}

## Scope

- In scope: {title}
- Out of scope: cualquier refactor no necesario para cumplir el objetivo
- Affected subsystems: {subsystem_list}
- Candidate files: {affected_files}

## Constraints

- IA-first rule: {IA_FIRST_RULE}
- Mantener contratos compatibles con `EngineAPI`, modo `headless` y flujo de escenas salvo orden explicita en contra.
- Cualquier cambio de runtime requiere evidencia no visual reproducible.
- El cierre necesita `Result Bundle` con evidencia y riesgos.

## Acceptance Criteria

- [ ] El objetivo queda implementado o investigado con alcance acotado.
- [ ] Los subsistemas afectados mantienen un contrato coherente.
- [ ] La validacion no visual requerida se puede reproducir.
- [ ] Riesgos y siguientes pasos quedan documentados.

## Validation Plan

{validation_lines}

## Handoff Notes

- Dependencies: por concretar segun implementacion
- Known risks: runtime, serializacion y regresiones del subsistema afectado
- Recommended next agent: Core Architect
"""


def parse_args() -> argparse.Namespace:
    """Parsea argumentos CLI."""
    parser = argparse.ArgumentParser(description="Asistente de orquestacion multiagente")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create_brief = subparsers.add_parser("create-brief", help="Genera un Task Brief en Markdown")
    create_brief.add_argument("--title", required=True, help="Titulo corto de la tarea")
    create_brief.add_argument("--goal", required=True, help="Objetivo concreto de la tarea")
    create_brief.add_argument("--subsystems", nargs="+", default=[], help="Subsistemas afectados")
    create_brief.add_argument("--files", nargs="*", default=[], help="Archivos candidatos")
    create_brief.add_argument(
        "--priority",
        default="core-stability",
        choices=PRIORITY_ORDER,
        help="Prioridad de backlog",
    )
    create_brief.add_argument(
        "--has-failure",
        action="store_true",
        help="Incluye al Debugger en el flujo recomendado",
    )
    create_brief.add_argument("--output", help="Ruta opcional de salida")

    recommend = subparsers.add_parser("recommend-validation", help="Lista validaciones recomendadas")
    recommend.add_argument("--subsystems", nargs="+", default=[], help="Subsistemas afectados")

    list_gaps = subparsers.add_parser("list-gaps", help="Lista gaps de Unity 2D core pendientes")
    list_gaps.add_argument(
        "--status",
        default="parcial",
        choices=["ya existe", "parcial", "falta", "bloqueado"],
        help="Filtra por estado de la matriz",
    )

    return parser.parse_args()


def main() -> int:
    """Punto de entrada CLI."""
    args = parse_args()

    if args.command == "create-brief":
        content = build_task_brief(
            title=args.title,
            goal=args.goal,
            subsystems=args.subsystems,
            files=args.files,
            priority=args.priority,
            has_failure=args.has_failure,
        )
        if args.output:
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(content, encoding="utf-8")
            print(f"[OK] Task Brief generado en {output_path}")
        else:
            print(content)
        return 0

    if args.command == "recommend-validation":
        for command in recommend_validations(args.subsystems):
            print(command)
        return 0

    if args.command == "list-gaps":
        for item in UNITY_2D_CORE_MATRIX:
            if item["status"] == args.status:
                deps = ",".join(item["depends_on"]) if item["depends_on"] else "-"
                print(f'{item["feature"]}|{item["status"]}|{item["priority"]}|{deps}')
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
