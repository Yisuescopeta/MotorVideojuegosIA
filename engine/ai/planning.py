from __future__ import annotations

import unicodedata
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

        execution_intent = self._detect_general_execution_intent(prompt)
        if execution_intent == "attach_player_movement_script":
            return self._build_character_movement_plan(prompt, answers, matched_skills, context)

        return PlanningSession(
            session_type="general_plan",
            summary="Puedo analizar esta petición y, en Build, intentar implementarla generando cambios sobre escena y scripts del proyecto con rollback si algo falla.",
            assumptions=["Se usará authoring sobre EngineAPI y datos serializables como flujo principal."],
            questions=[],
            milestones=[
                "Inspeccionar el proyecto actual y localizar el sistema afectado",
                "Definir el cambio jugable y los archivos o entidades implicadas",
                "Traducirlo a cambios serializables y scripts editables dentro del proyecto",
            ],
            gaps=[],
            selected_skills=matched_skills,
            execution_intent=execution_intent,
            metadata={"genre": genre, "prompt": prompt, "answers": dict(answers), "generic_build_candidate": True, "can_build_now": True},
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

    def _build_character_movement_plan(
        self,
        prompt: str,
        answers: Dict[str, Any],
        matched_skills: List[str],
        context: Dict[str, Any],
    ) -> PlanningSession:
        target_entity = self._resolve_target_entity(prompt, answers, context)
        if not target_entity:
            return PlanningSession(
                session_type="intent_plan",
                summary="He detectado una peticion de movimiento. Solo necesito saber que entidad debe moverse.",
                assumptions=[
                    "Preparare una propuesta revisable con InputMap, RigidBody y ScriptBehaviour.",
                    "No se aplicaran cambios sin confirmacion explicita.",
                ],
                questions=[
                    PlanQuestion(
                        id="target_entity",
                        text="No detecto la entidad objetivo. Escribe el nombre exacto de la entidad o selecciona una en el editor.",
                        rationale="Necesito una entidad concreta para preparar el script y los componentes de movimiento.",
                        choices=self._entity_choices(context),
                    )
                ],
                milestones=[
                    "Identificar la entidad objetivo",
                    "Preparar componentes base de movimiento",
                    "Generar una propuesta revisable antes del apply",
                ],
                gaps=[],
                selected_skills=matched_skills,
                execution_intent="attach_player_movement_script",
                metadata={"prompt": prompt, "movement_profile": "platformer_2d"},
            )

        return PlanningSession(
            session_type="intent_plan",
            summary=f"Plan de movimiento listo para {target_entity}. Preparare una propuesta revisable sin preguntas genericas.",
            assumptions=[
                f"Entidad objetivo: {target_entity}",
                "Perfil por defecto: lateral 2D con salto.",
            ],
            questions=[],
            milestones=[
                "Asegurar InputMap y RigidBody en la entidad objetivo",
                "Adjuntar ScriptBehaviour con parametros editables",
                "Validar PLAY/STOP antes de aplicar",
            ],
            gaps=[],
            selected_skills=matched_skills,
            execution_intent="attach_player_movement_script",
            metadata={"prompt": prompt, "target_entity": target_entity, "movement_profile": "platformer_2d"},
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

    def _detect_genre(self, prompt: str) -> str:
        lower = self._normalized_text(prompt)
        if "plataforma" in lower or "platformer" in lower:
            return "platformer"
        if "top down" in lower or "top-down" in lower:
            return "top_down"
        if "puzzle" in lower:
            return "puzzle"
        return "general"

    def _detect_general_execution_intent(self, prompt: str) -> str | None:
        lower = self._normalized_text(prompt)
        mentions_actor = any(token in lower for token in ("player", "jugador", "personaje", "character", "heroe", "hero"))
        mentions_motion = any(
            token in lower
            for token in ("movimiento", "movilidad", "desplazamiento", "movement", "mover", "move", "caminar", "andar")
        )
        mentions_script_or_add = any(token in lower for token in ("script", "scriptbehaviour", "comportamiento", "anade", "agrega", "ponle", "implementa", "add", "anademe"))
        if mentions_actor and mentions_motion and (mentions_script_or_add or "movilidad al" in lower or "movimiento al" in lower):
            return "attach_player_movement_script"
        return None

    def _resolve_target_entity(self, prompt: str, answers: Dict[str, Any], context: Dict[str, Any]) -> str:
        answered = str(answers.get("target_entity", "") or "").strip()
        if answered:
            return answered

        selected_entity = str(context.get("scene", {}).get("selected_entity", "") or "").strip()
        if selected_entity:
            return selected_entity

        prompt_lower = self._normalized_text(prompt)
        entities = [str(item.get("name", "") or "").strip() for item in context.get("scene", {}).get("entities", []) if isinstance(item, dict)]
        for entity_name in entities:
            if entity_name and self._normalized_text(entity_name) in prompt_lower:
                return entity_name

        for preferred in ("Player", "Jugador", "Character"):
            if preferred in entities:
                return preferred

        if any(token in prompt_lower for token in ("player", "jugador")):
            return "Player"
        return ""

    def _entity_choices(self, context: Dict[str, Any]) -> List[str]:
        entities = [str(item.get("name", "") or "").strip() for item in context.get("scene", {}).get("entities", []) if isinstance(item, dict)]
        return [entity for entity in entities[:3] if entity]

    def _normalized_text(self, value: str) -> str:
        text = unicodedata.normalize("NFKD", str(value or ""))
        ascii_text = text.encode("ascii", "ignore").decode("ascii")
        return ascii_text.lower()

    def _has_answer(self, answers: Dict[str, Any], key: str) -> bool:
        value = answers.get(key)
        if value is None:
            return False
        if isinstance(value, str):
            return bool(value.strip())
        return True
