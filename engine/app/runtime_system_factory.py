"""Shared runtime system wiring for editor PLAY and exported games."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from engine.events.event_bus import EventBus
from engine.events.rule_system import RuleSystem
from engine.systems.animation_system import AnimationSystem
from engine.systems.audio_system import AudioSystem
from engine.systems.character_controller_system import CharacterControllerSystem
from engine.systems.collision_system import CollisionSystem
from engine.systems.input_system import InputSystem
from engine.systems.light2d_system import Light2DSystem
from engine.systems.parallax_system import ParallaxSystem
from engine.systems.particle_system import ParticleSystem
from engine.systems.physics_system import PhysicsSystem
from engine.systems.player_controller_system import PlayerControllerSystem
from engine.systems.render_system import RenderSystem
from engine.systems.resource_preloader_system import ResourcePreloaderSystem
from engine.systems.script_behaviour_system import ScriptBehaviourSystem
from engine.systems.timer_system import TimerSystem
from engine.systems.tween_system import TweenSystem
from engine.systems.ui_render_system import UIRenderSystem
from engine.systems.ui_system import UISystem
from engine.systems.visible_on_screen_system import VisibleOnScreenSystem

if TYPE_CHECKING:
    from engine.core.game import Game


@dataclass
class RuntimeSystemBundle:
    event_bus: EventBus
    rule_system: RuleSystem
    render_system: RenderSystem
    physics_system: PhysicsSystem
    collision_system: CollisionSystem
    animation_system: AnimationSystem
    audio_system: AudioSystem
    input_system: InputSystem
    character_controller_system: CharacterControllerSystem
    player_controller_system: PlayerControllerSystem
    script_behaviour_system: ScriptBehaviourSystem
    timer_system: TimerSystem
    tween_system: TweenSystem
    visible_on_screen_system: VisibleOnScreenSystem
    parallax_system: ParallaxSystem
    resource_preloader_system: ResourcePreloaderSystem
    ui_system: UISystem
    ui_render_system: UIRenderSystem
    light2d_system: Light2DSystem
    particle_system: ParticleSystem

    def install(
        self,
        game: "Game",
        *,
        project_service: Any | None = None,
        scene_manager: Any | None = None,
    ) -> None:
        if project_service is not None:
            game.set_project_service(project_service)
        if scene_manager is not None:
            game.set_scene_manager(scene_manager)
        game.set_render_system(self.render_system)
        game.set_physics_system(self.physics_system)
        game.set_collision_system(self.collision_system)
        game.set_animation_system(self.animation_system)
        game.set_audio_system(self.audio_system)
        game.set_input_system(self.input_system)
        game.set_character_controller_system(self.character_controller_system)
        game.set_player_controller_system(self.player_controller_system)
        game.set_script_behaviour_system(self.script_behaviour_system)
        game.set_timer_system(self.timer_system)
        game.set_tween_system(self.tween_system)
        game.set_visible_on_screen_system(self.visible_on_screen_system)
        game.set_parallax_system(self.parallax_system)
        game.set_resource_preloader_system(self.resource_preloader_system)
        game.set_event_bus(self.event_bus)
        game.set_rule_system(self.rule_system)
        game.set_ui_system(self.ui_system)
        game.set_ui_render_system(self.ui_render_system)
        game.set_light2d_system(self.light2d_system)
        game.set_particle_system(self.particle_system)


def create_runtime_system_bundle(*, gravity: float = 600.0) -> RuntimeSystemBundle:
    event_bus = EventBus()
    return RuntimeSystemBundle(
        event_bus=event_bus,
        rule_system=RuleSystem(event_bus),
        render_system=RenderSystem(),
        physics_system=PhysicsSystem(gravity=gravity),
        collision_system=CollisionSystem(event_bus),
        animation_system=AnimationSystem(event_bus),
        audio_system=AudioSystem(),
        input_system=InputSystem(),
        character_controller_system=CharacterControllerSystem(),
        player_controller_system=PlayerControllerSystem(),
        script_behaviour_system=ScriptBehaviourSystem(),
        timer_system=TimerSystem(),
        tween_system=TweenSystem(),
        visible_on_screen_system=VisibleOnScreenSystem(),
        parallax_system=ParallaxSystem(),
        resource_preloader_system=ResourcePreloaderSystem(),
        ui_system=UISystem(),
        ui_render_system=UIRenderSystem(),
        light2d_system=Light2DSystem(),
        particle_system=ParticleSystem(event_bus),
    )
