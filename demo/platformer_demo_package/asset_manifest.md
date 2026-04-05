# Asset manifest

## Assets visuales elegidos

### Player sprites

Fuente elegida: mirror público del pack de plataformas de Kenney en `Barney241/Jump2D`.

- `assets/sprites/alienBlue_stand.png`
  - uso previsto: idle del jugador
  - fuente: `Sprites/PNG/Players/128x256/Blue/alienBlue_stand.png`
  - licencia esperada: CC0 / Kenney Platformer Pack
- `assets/sprites/alienBlue_walk1.png`
  - uso previsto: run frame 1
  - fuente: `Sprites/PNG/Players/128x256/Blue/alienBlue_walk1.png`
  - licencia esperada: CC0 / Kenney Platformer Pack
- `assets/sprites/alienBlue_walk2.png`
  - uso previsto: run frame 2
  - fuente: `Sprites/PNG/Players/128x256/Blue/alienBlue_walk2.png`
  - licencia esperada: CC0 / Kenney Platformer Pack
- `assets/sprites/alienBlue_jump.png`
  - uso previsto: jump / fall
  - fuente: `Sprites/PNG/Players/128x256/Blue/alienBlue_jump.png`
  - licencia esperada: CC0 / Kenney Platformer Pack

### Tileset

- `assets/tilesets/grassCenter.png`
  - uso previsto: bloque sólido base
  - fuente: `Sprites/PNG/Ground/Grass/grassCenter.png`
- `assets/tilesets/grassMid.png`
  - uso previsto: suelo/plataforma central
  - fuente: `Sprites/PNG/Ground/Grass/grassMid.png`
- `assets/tilesets/grassLeft.png`
  - uso previsto: borde izquierdo de plataforma
  - fuente: `Sprites/PNG/Ground/Grass/grassLeft.png`
- `assets/tilesets/grassRight.png`
  - uso previsto: borde derecho de plataforma
  - fuente: `Sprites/PNG/Ground/Grass/grassRight.png`

### Interactivos

- `assets/sprites/coinGold.png`
  - uso previsto: coleccionable
  - fuente: `Sprites/PNG/Items/coinGold.png`
- `assets/sprites/spikes.png`
  - uso previsto: hazard simple
  - fuente: `Sprites/PNG/Tiles/spikes.png`

## Audio del prototipo

- `assets/audio/jump.wav`
- `assets/audio/collect.wav`
- `assets/audio/victory.wav`
- `assets/audio/defeat.wav`

Estos cuatro sonidos se generan mediante `fetch_selected_assets.py` como placeholders libres para el prototipo. No dependen de terceros y están pensados para smoke test del runtime de audio.

## Script de descarga/poblado

El script `fetch_selected_assets.py` descarga los assets visuales seleccionados a partir de URLs raw concretas y genera el audio placeholder dentro de la rama actual.
