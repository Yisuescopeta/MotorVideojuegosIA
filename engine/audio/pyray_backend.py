"""
PyrayAudioBackend — backend de audio real usando raylib/pyray.

Implementa el conrato AudioBackend con reproducción real de sonido.
Soporta carga perezosa de dispositivo, cache de sonidos, looping manual,
y degradación segura si no hay dispositivo de audio disponible.
"""

import pyray as rl
from typing import Dict, Optional
from engine.audio.contracts import AudioPlaybackRequest, AudioVoiceState


class PyrayAudioBackend:
    """Backend de audio usando pyray/raylib. Degrada a no-op si no hay dispositivo."""
    
    def __init__(self):
        self._device_ready: bool = False
        self._sounds: Dict[str, any] = {}  # asset_path -> raylib Sound
        self._looping: Dict[str, bool] = {}  # entity_name -> is_looping
    
    def _ensure_device(self) -> bool:
        """Inicializa el dispositivo de audio si no está listo. Retorna True si OK."""
        if self._device_ready:
            return True
        try:
            rl.InitAudioDevice()
            self._device_ready = True
            return True
        except Exception:
            return False
    
    def start(self, request: AudioPlaybackRequest, voice: AudioVoiceState) -> None:
        """Carga y reproduce un sonido."""
        if not self._ensure_device():
            return
        
        path = request.resolved_asset_path or request.asset_path
        if not path:
            return
        
        # Cache: no recargar sonido ya cargado
        if path not in self._sounds:
            try:
                sound = rl.LoadSound(path)
                self._sounds[path] = sound
            except Exception:
                return
        
        sound = self._sounds[path]
        entity = request.entity_name
        
        # Configurar volumen y pitch
        rl.SetSoundVolume(sound, max(0.0, min(1.0, request.volume)))
        rl.SetSoundPitch(sound, request.pitch)
        
        # Looping manual (rl.SetSoundLooping no existe para Sound en raylib)
        if request.loop:
            self._looping[entity] = True
        else:
            self._looping.pop(entity, None)
        
        rl.PlaySound(sound)
    
    def pause(self, voice: AudioVoiceState) -> None:
        """Pausa la reproducción de un sonido."""
        entity = voice.entity_name
        resolved = getattr(voice, 'resolved_asset_path', '') or voice.asset_path
        if resolved and resolved in self._sounds:
            rl.PauseSound(self._sounds[resolved])
    
    def resume(self, voice: AudioVoiceState) -> None:
        """Reanuda la reproducción."""
        entity = voice.entity_name
        resolved = getattr(voice, 'resolved_asset_path', '') or voice.asset_path
        if resolved and resolved in self._sounds:
            rl.ResumeSound(self._sounds[resolved])
    
    def stop(self, voice: AudioVoiceState) -> None:
        """Detiene la reproducción."""
        entity = voice.entity_name
        resolved = getattr(voice, 'resolved_asset_path', '') or voice.asset_path
        if resolved and resolved in self._sounds:
            rl.StopSound(self._sounds[resolved])
            self._looping.pop(entity, None)
    
    def update(self, voices: Dict[str, AudioVoiceState], game_time: float) -> None:
        """Actualiza estado: reinicia sonidos en loop, detecta finalizados."""
        for entity_name, voice in voices.items():
            resolved = getattr(voice, 'resolved_asset_path', '') or voice.asset_path
            if resolved not in self._sounds:
                continue
            
            sound = self._sounds[resolved]
            if not rl.IsSoundPlaying(sound):
                if self._looping.get(entity_name, False):
                    rl.PlaySound(sound)
                # Si no es looping, el audio terminó — AudioRuntime maneja el evento
    
    def shutdown(self) -> None:
        """Limpia todos los sonidos y cierra el dispositivo de audio."""
        for path, sound in self._sounds.items():
            try:
                rl.UnloadSound(sound)
            except Exception:
                pass
        self._sounds.clear()
        self._looping.clear()
        
        if self._device_ready:
            try:
                rl.CloseAudioDevice()
            except Exception:
                pass
            self._device_ready = False
