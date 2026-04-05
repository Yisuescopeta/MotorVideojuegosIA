from __future__ import annotations

import math
import struct
import urllib.request
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / 'assets'
SPRITES = ASSETS / 'sprites'
TILESETS = ASSETS / 'tilesets'
AUDIO = ASSETS / 'audio'
OPTIONAL = ASSETS / 'optional'

VISUAL_ASSETS = {
    SPRITES / 'alienBlue_stand.png': 'https://raw.githubusercontent.com/Barney241/Jump2D/273586c43969071d430b5671f02933c1bd3e9ab7/Sprites/PNG/Players/128x256/Blue/alienBlue_stand.png',
    SPRITES / 'alienBlue_walk1.png': 'https://raw.githubusercontent.com/Barney241/Jump2D/273586c43969071d430b5671f02933c1bd3e9ab7/Sprites/PNG/Players/128x256/Blue/alienBlue_walk1.png',
    SPRITES / 'alienBlue_walk2.png': 'https://raw.githubusercontent.com/Barney241/Jump2D/273586c43969071d430b5671f02933c1bd3e9ab7/Sprites/PNG/Players/128x256/Blue/alienBlue_walk2.png',
    SPRITES / 'alienBlue_jump.png': 'https://raw.githubusercontent.com/Barney241/Jump2D/273586c43969071d430b5671f02933c1bd3e9ab7/Sprites/PNG/Players/128x256/Blue/alienBlue_jump.png',
    TILESETS / 'grassCenter.png': 'https://raw.githubusercontent.com/Barney241/Jump2D/273586c43969071d430b5671f02933c1bd3e9ab7/Sprites/PNG/Ground/Grass/grassCenter.png',
    TILESETS / 'grassMid.png': 'https://raw.githubusercontent.com/Barney241/Jump2D/273586c43969071d430b5671f02933c1bd3e9ab7/Sprites/PNG/Ground/Grass/grassMid.png',
    TILESETS / 'grassLeft.png': 'https://raw.githubusercontent.com/Barney241/Jump2D/273586c43969071d430b5671f02933c1bd3e9ab7/Sprites/PNG/Ground/Grass/grassLeft.png',
    TILESETS / 'grassRight.png': 'https://raw.githubusercontent.com/Barney241/Jump2D/273586c43969071d430b5671f02933c1bd3e9ab7/Sprites/PNG/Ground/Grass/grassRight.png',
    SPRITES / 'coinGold.png': 'https://raw.githubusercontent.com/Barney241/Jump2D/273586c43969071d430b5671f02933c1bd3e9ab7/Sprites/PNG/Items/coinGold.png',
    SPRITES / 'spikes.png': 'https://raw.githubusercontent.com/Barney241/Jump2D/273586c43969071d430b5671f02933c1bd3e9ab7/Sprites/PNG/Tiles/spikes.png',
}


def ensure_dirs() -> None:
    for path in [SPRITES, TILESETS, AUDIO, OPTIONAL]:
        path.mkdir(parents=True, exist_ok=True)


def download_visual_assets() -> None:
    for dest, url in VISUAL_ASSETS.items():
        if dest.exists():
            continue
        print(f'Downloading {dest.name}...')
        with urllib.request.urlopen(url) as response:
            dest.write_bytes(response.read())


def _make_tone(path: Path, *, notes: list[float], duration: float) -> None:
    sample_rate = 22050
    samples: list[int] = []
    note_len = duration / len(notes)
    for i in range(int(sample_rate * duration)):
        t = i / sample_rate
        note_index = min(int(t / note_len), len(notes) - 1)
        freq = notes[note_index]
        amp = max(0.2, 1 - (t / duration))
        value = int(32767 * 0.35 * amp * math.sin(2 * math.pi * freq * t))
        samples.append(value)
    with wave.open(str(path), 'wb') as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(b''.join(struct.pack('<h', s) for s in samples))


def generate_audio() -> None:
    audio_map = {
        AUDIO / 'jump.wav': ([440.0, 660.0], 0.35),
        AUDIO / 'collect.wav': ([880.0, 1320.0], 0.35),
        AUDIO / 'victory.wav': ([523.25, 659.25, 783.99], 0.6),
        AUDIO / 'defeat.wav': ([220.0, 164.81], 0.35),
    }
    for path, (notes, duration) in audio_map.items():
        if path.exists():
            continue
        print(f'Generating {path.name}...')
        _make_tone(path, notes=notes, duration=duration)


if __name__ == '__main__':
    ensure_dirs()
    download_visual_assets()
    generate_audio()
    print('Done.')
