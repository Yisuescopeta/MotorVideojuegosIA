"""MIDI input device reading with cross-platform abstraction."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional


class MIDIInput:
    """MIDI input device reading (cross-platform abstraction).

    Uses python-rtmidi if available. Graceful fallback if not installed.
    """

    @dataclass
    class MIDIEvent:
        device: int = 0
        channel: int = 0
        message_type: str = ""  # note_on, note_off, cc, program_change, pitch_bend
        note: int = 0
        velocity: int = 0
        value: int = 0
        timestamp: float = 0.0

    def __init__(self) -> None:
        self._devices: list = []
        self._active_device: int = -1
        self._events: List[MIDIInput.MIDIEvent] = []
        self._midi_in: Optional[object] = None
        self._has_rtmidi: bool = False

    def list_devices(self) -> list:
        """List available MIDI input devices. Returns list of {id, name} dicts."""
        try:
            import rtmidi  # type: ignore
            midi_in = rtmidi.MidiIn()
            ports = midi_in.get_ports()
            del midi_in
            return [{"id": i, "name": name} for i, name in enumerate(ports)]
        except ImportError:
            return []

    def open_device(self, device_id: int) -> bool:
        """Open a MIDI input device. Returns True on success."""
        try:
            import rtmidi  # type: ignore
            if self._midi_in is not None:
                self.close()
            self._midi_in = rtmidi.MidiIn()
            ports = self._midi_in.get_ports()
            if device_id < 0 or device_id >= len(ports):
                return False
            self._midi_in.open_port(device_id)
            self._midi_in.ignore_types(False, False, False)
            self._active_device = device_id
            self._has_rtmidi = True
            return True
        except ImportError:
            return False
        except Exception:
            return False

    def poll_events(self) -> List[MIDIEvent]:
        """Poll for new MIDI events. Returns list of MIDIEvent."""
        self._events.clear()
        if not self._has_rtmidi or self._midi_in is None:
            return []

        try:
            msg = self._midi_in.get_message()  # type: ignore
            while msg is not None:
                message, timestamp = msg
                if len(message) >= 3:
                    event = self._parse_message(message, timestamp)
                    if event is not None:
                        self._events.append(event)
                msg = self._midi_in.get_message()  # type: ignore
        except Exception:
            pass

        return self._events

    def close(self) -> None:
        """Close the MIDI device."""
        if self._midi_in is not None:
            try:
                self._midi_in.close_port()  # type: ignore
                del self._midi_in
            except Exception:
                pass
            self._midi_in = None
        self._active_device = -1
        self._has_rtmidi = False

    def __del__(self) -> None:
        self.close()

    @staticmethod
    def _parse_message(message: tuple, timestamp: float) -> Optional[MIDIEvent]:
        """Parse a raw MIDI message into a MIDIEvent."""
        if len(message) < 3:
            return None

        status_byte = message[0]
        channel = (status_byte & 0x0F) + 1
        msg_type = status_byte & 0xF0

        if msg_type == 0x90 and message[2] > 0:  # Note On
            return MIDIInput.MIDIEvent(
                channel=channel,
                message_type="note_on",
                note=message[1],
                velocity=message[2],
                value=message[2],
                timestamp=timestamp,
            )
        elif msg_type == 0x80 or (msg_type == 0x90 and message[2] == 0):  # Note Off
            return MIDIInput.MIDIEvent(
                channel=channel,
                message_type="note_off",
                note=message[1],
                velocity=0,
                value=0,
                timestamp=timestamp,
            )
        elif msg_type == 0xB0:  # Control Change (CC)
            return MIDIInput.MIDIEvent(
                channel=channel,
                message_type="cc",
                note=message[1],
                value=message[2],
                timestamp=timestamp,
            )
        elif msg_type == 0xE0:  # Pitch Bend
            value = message[1] | (message[2] << 7)
            return MIDIInput.MIDIEvent(
                channel=channel,
                message_type="pitch_bend",
                value=value,
                timestamp=timestamp,
            )
        elif msg_type == 0xC0:  # Program Change
            return MIDIInput.MIDIEvent(
                channel=channel,
                message_type="program_change",
                value=message[1],
                timestamp=timestamp,
            )

        return None
