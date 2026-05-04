"""Tests for audio bus system and MIDI input (Batch 1, Ola 8)."""

from __future__ import annotations

import pytest

from engine.audio.audio_bus import (
    AudioBus,
    AudioBusLayout,
    AudioEffect,
    DelayEffect,
    EQEffect,
    ReverbEffect,
)
from engine.audio.contracts import AudioPlaybackRequest
from engine.audio.runtime import AudioRuntime
from engine.components.inputmap import InputMap
from engine.input.midi_input import MIDIInput


# ------------------------------------------------------------------ #
# AudioBus tests
# ------------------------------------------------------------------ #

class TestAudioBus:
    def test_linear_volume_zero_db(self) -> None:
        bus = AudioBus(name="master", volume_db=0.0)
        assert bus.linear_volume == pytest.approx(1.0)

    def test_linear_volume_negative_db(self) -> None:
        bus = AudioBus(name="sfx", volume_db=-6.0)
        assert bus.linear_volume == pytest.approx(0.5, rel=0.01)

    def test_linear_volume_positive_db(self) -> None:
        bus = AudioBus(name="sfx", volume_db=6.0)
        assert bus.linear_volume == pytest.approx(2.0, rel=0.01)

    def test_mute_silence(self) -> None:
        bus = AudioBus(name="sfx", volume_db=0.0, mute=True)
        layout = AudioBusLayout()
        layout.buses["sfx"] = bus
        assert layout.get_linear_volume("sfx") == 0.0

    def test_bypass_ignores_mute(self) -> None:
        bus = AudioBus(name="sfx", volume_db=0.0, mute=True, bypass=True)
        layout = AudioBusLayout()
        layout.buses["sfx"] = bus
        assert layout.get_linear_volume("sfx") == 1.0

    def test_solo_only_solo_bus_plays(self) -> None:
        layout = AudioBusLayout()
        layout.add_bus("sfx")
        layout.add_bus("music")
        layout.buses["sfx"].solo = True
        assert layout.get_linear_volume("sfx") == 1.0
        assert layout.get_linear_volume("music") == 0.0
        assert layout.get_linear_volume("master") == 0.0

    def test_no_solo_all_play(self) -> None:
        layout = AudioBusLayout()
        layout.add_bus("sfx")
        layout.add_bus("music")
        assert layout.get_linear_volume("sfx") == 1.0
        assert layout.get_linear_volume("music") == 1.0
        assert layout.get_linear_volume("master") == 1.0

    def test_serialize_deserialize(self) -> None:
        bus = AudioBus(name="sfx", volume_db=-3.0, mute=True)
        bus.effects.append(ReverbEffect(room_size=0.8))
        bus.effects.append(EQEffect(low_gain=2.0))

        data = bus.to_dict()
        restored = AudioBus.from_dict(data)

        assert restored.name == "sfx"
        assert restored.volume_db == -3.0
        assert restored.mute is True
        assert len(restored.effects) == 2
        assert isinstance(restored.effects[0], ReverbEffect)
        assert restored.effects[0].room_size == 0.8
        assert isinstance(restored.effects[1], EQEffect)
        assert restored.effects[1].low_gain == 2.0

    def test_delay_effect_defaults(self) -> None:
        delay = DelayEffect(name="echo")
        assert delay.delay_ms == 250.0
        assert delay.feedback == 0.3
        assert delay.wet_level == 0.5
        assert delay.enabled is True


class TestAudioBusLayout:
    def test_creates_master_by_default(self) -> None:
        layout = AudioBusLayout()
        assert "master" in layout.buses
        assert layout.buses["master"].name == "master"

    def test_add_bus(self) -> None:
        layout = AudioBusLayout()
        bus = layout.add_bus("sfx", parent="master")
        assert bus.name == "sfx"
        assert bus.send_to == "master"
        assert "sfx" in layout.buses

    def test_add_bus_idempotent(self) -> None:
        layout = AudioBusLayout()
        b1 = layout.add_bus("sfx")
        b2 = layout.add_bus("sfx")
        assert b1 is b2

    def test_remove_bus(self) -> None:
        layout = AudioBusLayout()
        layout.add_bus("sfx")
        layout.remove_bus("sfx")
        assert "sfx" not in layout.buses

    def test_get_bus(self) -> None:
        layout = AudioBusLayout()
        bus = layout.get_bus("master")
        assert bus is not None
        assert bus.name == "master"
        assert layout.get_bus("nonexistent") is None

    def test_serialize_deserialize(self) -> None:
        layout = AudioBusLayout()
        layout.add_bus("sfx")
        sfx = layout.get_bus("sfx")
        assert sfx is not None
        sfx.volume_db = -6.0
        sfx.effects.append(ReverbEffect())

        data = layout.to_dict()
        restored = AudioBusLayout.from_dict(data)

        assert "master" in restored.buses
        assert "sfx" in restored.buses
        assert restored.buses["sfx"].volume_db == -6.0
        assert len(restored.buses["sfx"].effects) == 1
        assert isinstance(restored.buses["sfx"].effects[0], ReverbEffect)

    def test_from_dict_missing_master(self) -> None:
        layout = AudioBusLayout.from_dict({"buses": {}})
        assert "master" in layout.buses


class TestAudioEffect:
    def test_base_effect_defaults(self) -> None:
        fx = AudioEffect()
        assert fx.name == ""
        assert fx.enabled is True

    def test_reverb_defaults(self) -> None:
        fx = ReverbEffect()
        assert fx.room_size == 0.5
        assert fx.damping == 0.5
        assert fx.wet_level == 0.3
        assert fx.dry_level == 0.7

    def test_eq_defaults(self) -> None:
        fx = EQEffect()
        assert fx.low_gain == 0.0
        assert fx.mid_gain == 0.0
        assert fx.high_gain == 0.0


# ------------------------------------------------------------------ #
# AudioRuntime + bus integration tests
# ------------------------------------------------------------------ #

class TestAudioRuntimeWithBus:
    def test_bus_layout_default(self) -> None:
        runtime = AudioRuntime()
        assert runtime.bus_layout is not None
        assert "master" in runtime.bus_layout.buses

    def test_play_applies_bus_volume(self) -> None:
        runtime = AudioRuntime()
        runtime.bus_layout.buses["master"].volume_db = -6.0  # 0.5x

        request = AudioPlaybackRequest(
            entity_name="test",
            asset_path="test.wav",
            bus_id="master",
            volume=1.0,
        )
        voice = runtime.play(request)
        assert voice.volume == pytest.approx(0.5, rel=0.01)

    def test_play_muted_bus_zero_volume(self) -> None:
        runtime = AudioRuntime()
        runtime.bus_layout.buses["master"].mute = True

        request = AudioPlaybackRequest(
            entity_name="test",
            asset_path="test.wav",
            bus_id="master",
            volume=1.0,
        )
        voice = runtime.play(request)
        assert voice.volume == 0.0

    def test_play_nonexistent_bus_defaults_to_master(self) -> None:
        runtime = AudioRuntime()
        sfx_bus = runtime.bus_layout.add_bus("sfx", parent="master")
        sfx_bus.volume_db = 0.0

        request = AudioPlaybackRequest(
            entity_name="test",
            asset_path="test.wav",
            bus_id="nonexistent",
            volume=1.0,
        )
        voice = runtime.play(request)
        # Nonexistent bus → get_linear_volume returns 1.0 (default)
        assert voice.volume == 1.0

    def test_play_custom_bus_volume(self) -> None:
        runtime = AudioRuntime()
        sfx = runtime.bus_layout.add_bus("sfx")
        sfx.volume_db = -12.0  # ~0.25x

        request = AudioPlaybackRequest(
            entity_name="test",
            asset_path="test.wav",
            bus_id="sfx",
            volume=0.8,
        )
        voice = runtime.play(request)
        expected = 0.8 * (10.0 ** (-12.0 / 20.0))
        assert voice.volume == pytest.approx(expected, rel=0.01)


# ------------------------------------------------------------------ #
# MIDI input tests
# ------------------------------------------------------------------ #

class TestMIDIInput:
    def test_list_devices_no_rtmidi(self) -> None:
        midi = MIDIInput()
        devices = midi.list_devices()
        # Without rtmidi installed, returns empty list
        assert isinstance(devices, list)

    def test_open_device_fails_without_rtmidi(self) -> None:
        midi = MIDIInput()
        result = midi.open_device(0)
        assert result is False

    def test_poll_events_empty_without_rtmidi(self) -> None:
        midi = MIDIInput()
        events = midi.poll_events()
        assert events == []

    def test_close_safe_when_not_open(self) -> None:
        midi = MIDIInput()
        midi.close()  # Should not raise

    def test_midi_event_creation(self) -> None:
        event = MIDIInput.MIDIEvent(
            channel=1,
            message_type="note_on",
            note=60,
            velocity=100,
            value=100,
        )
        assert event.channel == 1
        assert event.message_type == "note_on"
        assert event.note == 60
        assert event.velocity == 100

    def test_parse_note_on(self) -> None:
        event = MIDIInput._parse_message((0x90, 60, 100), 0.0)
        assert event is not None
        assert event.message_type == "note_on"
        assert event.note == 60
        assert event.velocity == 100
        assert event.channel == 1

    def test_parse_note_off(self) -> None:
        event = MIDIInput._parse_message((0x80, 60, 0), 0.0)
        assert event is not None
        assert event.message_type == "note_off"
        assert event.note == 60

    def test_parse_note_on_zero_velocity_is_off(self) -> None:
        event = MIDIInput._parse_message((0x90, 60, 0), 0.0)
        assert event is not None
        assert event.message_type == "note_off"

    def test_parse_cc(self) -> None:
        event = MIDIInput._parse_message((0xB0, 7, 100), 0.0)
        assert event is not None
        assert event.message_type == "cc"
        assert event.note == 7  # CC number
        assert event.value == 100

    def test_parse_program_change(self) -> None:
        event = MIDIInput._parse_message((0xC0, 5, 0), 0.0)
        assert event is not None
        assert event.message_type == "program_change"
        assert event.value == 5

    def test_parse_pitch_bend(self) -> None:
        event = MIDIInput._parse_message((0xE0, 0x40, 0x40), 0.0)
        assert event is not None
        assert event.message_type == "pitch_bend"
        # LSB=0x40 (64) | MSB=0x40<<7 (8192) = 8256, roughly center
        assert event.value == 8256

    def test_parse_short_message_returns_none(self) -> None:
        event = MIDIInput._parse_message((0x90, 60), 0.0)
        assert event is None


# ------------------------------------------------------------------ #
# InputMap MIDI fields tests
# ------------------------------------------------------------------ #

class TestInputMapMIDI:
    def test_default_midi_disabled(self) -> None:
        im = InputMap()
        assert im.midi_enabled is False

    def test_default_midi_action_map_empty(self) -> None:
        im = InputMap()
        assert im.midi_action_map == {}

    def test_serialize_midi_fields(self) -> None:
        im = InputMap()
        im.midi_enabled = True
        im.midi_action_map = {60: "action_1", 62: "action_2"}

        data = im.to_dict()
        assert data["midi_enabled"] is True
        assert data["midi_action_map"] == {60: "action_1", 62: "action_2"}

    def test_deserialize_midi_fields(self) -> None:
        data = {
            "midi_enabled": True,
            "midi_action_map": {36: "jump", 60: "action_1"},
        }
        im = InputMap.from_dict(data)
        assert im.midi_enabled is True
        assert im.midi_action_map == {36: "jump", 60: "action_1"}
