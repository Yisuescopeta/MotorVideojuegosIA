from __future__ import annotations

from typing import Any, Dict, List

from engine.ai.capabilities import detect_capability_gaps
from engine.ai.types import PlanQuestion, PlanningSession


class PlanningEngine:
    def build_plan(self, prompt: str, answers: Dict[str, Any], context: Dict[str, Any]) -> PlanningSession:
        gaps = detect_capability_gaps(prompt)
        matched_skills = context["summary"].get("matched_skill_ids", [])
        if gaps:
            return PlanningSession(
                session_type="gap_analysis",
                summary="La petición requiere capacidades que el motor todavía no expone de forma serializable.",
                assumptions=[],
                questions=[],
                milestones=[
                    "Confirmar el hueco técnico con una capability gap formal",
                    "Diseñar la extensión del motor en hitos",
                    "Implementar la capacidad faltante antes de continuar con el juego",
                ],
                gaps=gaps,
                selected_skills=matched_skills,
                execution_intent=None,
                metadata={"genre": self._detect_genre(prompt)},
            )

        genre = self._detect_genre(prompt)
        if genre == "platformer":
            return self._build_platformer_plan(prompt, answers, matched_skills, context)

        default_questions = self._default_questions()
        missing_questions = [question for question in default_questions if not self._has_answer(answers, question.id)]
        execution_intent = self._detect_general_execution_intent(prompt)

        if missing_questions:
            return PlanningSession(
                session_type="general_plan",
                summary="La petición se puede atender con el motor actual, pero necesita concretar el diseño del juego antes de ejecutar cambios.",
                assumptions=["Se usará authoring sobre EngineAPI y datos serializables como flujo principal."],
                questions=missing_questions,
                milestones=[
                    "Definir el objetivo jugable",
                    "Concretar escena, input, cámara y feedback",
                    "Traducirlo a acciones sobre el proyecto",
                ],
                gaps=[],
                selected_skills=matched_skills,
                execution_intent=execution_intent,
                metadata={"genre": genre, "prompt": prompt},
            )

        return PlanningSession(
            session_type="general_plan",
            summary="Plan general listo para pasar a propuesta de ejecución.",
            assumptions=[
                f"Objetivo: {answers.get('goal', '')}",
                f"Alcance: {answers.get('scope', '')}",
            ],
            questions=[],
            milestones=[
                "Traducir el objetivo y alcance confirmados a acciones del proyecto",
                "Generar una propuesta aplicable con validación",
            ],
            gaps=[],
            selected_skills=matched_skills,
            execution_intent=execution_intent,
            metadata={"genre": genre, "prompt": prompt, "answers": dict(answers)},
        )

    def _build_platformer_plan(self, prompt: str, answers: Dict[str, Any], matched_skills: List[str], context: Dict[str, Any]) -> PlanningSession:
        missing_questions = [question for question in self._platformer_questions() if not self._has_answer(answers, question.id)]
        requires_python = "python" in prompt.lower() or "script" in prompt.lower() or bool(answers.get("custom_script"))
        if missing_questions:
            return PlanningSession(
                session_type="genre_plan",
                summary="Se ha detectado un plataformas. Faltan decisiones para crear un slice jugable sin inventar requisitos.",
                assumptions=[
                    "Se priorizará una escena base jugable antes que contenido final.",
                    "Se reutilizarán assets del proyecto o placeholders según respuesta del usuario.",
                ],
                questions=missing_questions,
                milestones=[
                    "Definir el alcance del plataformas",
                    "Preparar escena base, jugador, cámara y colisiones",
                    "Añadir enemigos y HUD según respuestas confirmadas",
                ],
                gaps=[],
                selected_skills=matched_skills,
                execution_intent=None,
                metadata={"genre": "platformer", "requires_python": requires_python},
            )

        milestones = [
            "Crear escena base con suelo, jugador y cámara serializables",
            "Configurar input y control lateral con salto",
            "Añadir enemigos y obstáculos placeholders si se solicitaron",
            "Añadir HUD básico si se solicitó",
            "Validar la escena en headless sin romper el flujo EDIT/PLAY/STOP",
        ]
        assumptions = [
            f"Estrategia de assets: {answers.get('asset_strategy')}",
            f"Cámara: {answers.get('camera_style')}",
            f"HUD: {answers.get('hud')}",
        ]
        return PlanningSession(
            session_type="genre_plan",
            summary="Plan de plataformas listo para pasar a propuesta de ejecución.",
            assumptions=assumptions,
            questions=[],
            milestones=milestones,
            gaps=[],
            selected_skills=matched_skills,
            execution_intent="create_platformer_slice",
            metadata={
                "genre": "platformer",
                "answers": dict(answers),
                "scene_entities": context["scene"]["entity_count"],
                "requires_python": requires_python,
            },
        )

    def _platformer_questions(self) -> List[PlanQuestion]:
        return [
            PlanQuestion(
                id="enemies",
                text="¿Quieres enemigos desde el primer slice? Si sí, indica cuántos o de qué tipo.",
                rationale="Determina si el primer slice debe incluir lógica hostil y colisiones adicionales.",
                choices=["none", "single_melee_enemy", "two_basic_enemies"],
            ),
            PlanQuestion(
                id="obstacles",
                text="¿Qué obstáculos quieres en esta primera versión? Por ejemplo pinchos, plataformas elevadas o fosos.",
                rationale="Permite crear el layout inicial y las colisiones adecuadas.",
                choices=["none", "spikes", "moving_platforms"],
            ),
            PlanQuestion(
                id="asset_strategy",
                text="¿Usamos placeholders/cubos o assets existentes del proyecto para el primer slice?",
                rationale="Define si la IA debe apoyarse en recursos del proyecto o generar una escena gris jugable.",
                choices=["placeholders", "project_assets", "mixed"],
            ),
            PlanQuestion(
                id="camera_style",
                text="¿Quieres cámara siguiendo al jugador tipo plataformas o una cámara fija en este primer slice?",
                rationale="Impacta la configuración de Camera2D y framing.",
                choices=["follow_platformer", "fixed", "room_by_room"],
            ),
            PlanQuestion(
                id="hud",
                text="¿Quieres HUD básico desde el principio? Por ejemplo texto de vidas o monedas.",
                rationale="Define si se crea Canvas/UI en el slice inicial.",
                choices=["none", "basic_hud", "hud_with_coins"],
            ),
        ]

    def _default_questions(self) -> List[PlanQuestion]:
        return [
            PlanQuestion(
                id="goal",
                text="¿Cuál es el objetivo jugable principal del juego o cambio solicitado?",
                rationale="Define el vertical slice que se debe construir o modificar.",
                choices=["prototipo_jugable", "vertical_slice", "editar_proyecto_existente"],
            ),
            PlanQuestion(
                id="scope",
                text="¿Quieres crear un prototipo nuevo o modificar una escena/proyecto existente?",
                rationale="Define si el flujo entra por creación o edición.",
                choices=["nuevo_prototipo", "escena_existente", "sistema_existente"],
            ),
        ]

    def _detect_genre(self, prompt: str) -> str:
        lower = prompt.lower()
        if "plataforma" in lower or "platformer" in lower:
            return "platformer"
        if "top down" in lower or "top-down" in lower:
            return "top_down"
        if "puzzle" in lower:
            return "puzzle"
        return "general"

    def _detect_general_execution_intent(self, prompt: str) -> str | None:
        lower = prompt.lower()
        mentions_actor = any(token in lower for token in ("player", "jugador"))
        mentions_motion = any(token in lower for token in ("movimiento", "movement", "mover", "move"))
        mentions_script_or_add = any(token in lower for token in ("script", "scriptbehaviour", "comportamiento", "añade", "anade", "agrega", "add"))
        if mentions_actor and mentions_motion and mentions_script_or_add:
            return "attach_player_movement_script"
        return None

    def _has_answer(self, answers: Dict[str, Any], key: str) -> bool:
        value = answers.get(key)
        if value is None:
            return False
        if isinstance(value, str):
            return bool(value.strip())
        return True
