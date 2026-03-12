"""
engine/systems/audio_system.py - Sistema de audio 2D basico y seguro para headless
"""

from engine.components.audiosource import AudioSource
from engine.ecs.world import World


class AudioSystem:
    """Gestion minima de AudioSource sin introducir estado opaco en la UI."""

    def update(self, world: World) -> None:
        for entity in world.get_entities_with(AudioSource):
            audio_source = entity.get_component(AudioSource)
            if audio_source is None or not audio_source.enabled:
                continue
            if audio_source.play_on_awake and not audio_source.is_playing:
                audio_source.is_playing = True

    def play(self, world: World, entity_name: str) -> bool:
        entity = world.get_entity_by_name(entity_name)
        if entity is None:
            return False
        audio_source = entity.get_component(AudioSource)
        if audio_source is None or not audio_source.enabled:
            return False
        audio_source.is_playing = True
        return True

    def stop(self, world: World, entity_name: str) -> bool:
        entity = world.get_entity_by_name(entity_name)
        if entity is None:
            return False
        audio_source = entity.get_component(AudioSource)
        if audio_source is None:
            return False
        audio_source.is_playing = False
        return True
