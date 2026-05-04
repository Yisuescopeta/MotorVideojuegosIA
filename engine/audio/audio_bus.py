"""Audio bus system — per-bus volume, mute/solo/bypass, effects chain."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class AudioEffect:
    """Base class for audio effects on a bus."""

    name: str = ""
    enabled: bool = True


@dataclass
class ReverbEffect(AudioEffect):
    room_size: float = 0.5
    damping: float = 0.5
    wet_level: float = 0.3
    dry_level: float = 0.7


@dataclass
class EQEffect(AudioEffect):
    low_gain: float = 0.0
    mid_gain: float = 0.0
    high_gain: float = 0.0


@dataclass
class DelayEffect(AudioEffect):
    delay_ms: float = 250.0
    feedback: float = 0.3
    wet_level: float = 0.5


_EFFECT_TYPE_MAP: Dict[str, type] = {
    "reverb": ReverbEffect,
    "eq": EQEffect,
    "delay": DelayEffect,
    "audio_effect": AudioEffect,
}


def _effect_to_dict(effect: AudioEffect) -> dict:
    data = {"__type__": type(effect).__name__.replace("Effect", "").lower()}
    for field_name in ("name", "enabled"):
        if field_name in effect.__dataclass_fields__:
            data[field_name] = getattr(effect, field_name)
    for field_name in effect.__dataclass_fields__:
        if field_name in ("name", "enabled"):
            continue
        data[field_name] = getattr(effect, field_name)
    return data


def _effect_from_dict(data: dict) -> AudioEffect:
    type_name = data.get("__type__", "audio_effect")
    cls = _EFFECT_TYPE_MAP.get(type_name, AudioEffect)
    kwargs = {k: v for k, v in data.items() if k != "__type__"}
    return cls(**kwargs)


@dataclass
class AudioBus:
    """Single audio bus with volume, mute/solo/bypass, and effects chain."""

    name: str = "master"
    volume_db: float = 0.0  # decibels
    mute: bool = False
    solo: bool = False
    bypass: bool = False
    effects: List[AudioEffect] = field(default_factory=list)
    send_to: str = ""  # target bus name

    @property
    def linear_volume(self) -> float:
        """Convert dB to linear multiplier."""
        return 10.0 ** (self.volume_db / 20.0)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "volume_db": self.volume_db,
            "mute": self.mute,
            "solo": self.solo,
            "bypass": self.bypass,
            "effects": [_effect_to_dict(e) for e in self.effects],
            "send_to": self.send_to,
        }

    @classmethod
    def from_dict(cls, data: dict) -> AudioBus:
        return cls(
            name=data.get("name", "master"),
            volume_db=data.get("volume_db", 0.0),
            mute=data.get("mute", False),
            solo=data.get("solo", False),
            bypass=data.get("bypass", False),
            effects=[_effect_from_dict(e) for e in data.get("effects", [])],
            send_to=data.get("send_to", ""),
        )


@dataclass
class AudioBusLayout:
    """Collection of audio buses."""

    buses: Dict[str, AudioBus] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if "master" not in self.buses:
            self.buses["master"] = AudioBus(name="master")

    def add_bus(self, name: str, parent: str = "") -> AudioBus:
        if name in self.buses:
            return self.buses[name]
        bus = AudioBus(name=name, send_to=parent)
        self.buses[name] = bus
        return bus

    def remove_bus(self, name: str) -> None:
        self.buses.pop(name, None)

    def get_bus(self, name: str) -> Optional[AudioBus]:
        return self.buses.get(name)

    def get_linear_volume(self, bus_name: str) -> float:
        """Get effective linear volume for a bus, accounting for mute/solo/bypass."""
        bus = self.buses.get(bus_name)
        if bus is None:
            return 1.0
        return self._effective_volume(bus)

    def _effective_volume(self, bus: AudioBus) -> float:
        if bus.bypass:
            return 1.0
        if bus.mute:
            return 0.0
        # Solo: if any bus has solo=True, only solo buses play
        any_solo = any(b.solo for b in self.buses.values())
        if any_solo and not bus.solo:
            return 0.0
        return bus.linear_volume

    def to_dict(self) -> dict:
        return {"buses": {name: bus.to_dict() for name, bus in self.buses.items()}}

    @classmethod
    def from_dict(cls, data: dict) -> AudioBusLayout:
        buses_data = data.get("buses", {})
        layout = cls()
        for name, bus_data in buses_data.items():
            layout.buses[name] = AudioBus.from_dict(bus_data)
        if "master" not in layout.buses:
            layout.buses["master"] = AudioBus(name="master")
        return layout
