# Selection notes

## Por qué este set

He priorizado un kit pequeño, reconocible y coherente para un plataformas 2D básico:

- un único personaje con 4 sprites claros para idle/run/jump
- un tileset mínimo de suelo/plataformas
- un coleccionable simple
- un hazard simple
- 4 SFX placeholder muy cortos

## Qué valida del motor

### Tilemap / authoring

Los `grass*` permiten construir un nivel corto con bloques sólidos y plataformas sin meter un pack masivo.

### Animación

`alienBlue_stand`, `alienBlue_walk1`, `alienBlue_walk2` y `alienBlue_jump` cubren exactamente el mínimo que pediste para el slice base.

### Física 2D

El personaje y los tiles elegidos fuerzan a validar movimiento horizontal, salto y colisión con suelo/plataformas.

### Interacción de gameplay

`coinGold.png` valida trigger/colección.
`spikes.png` valida daño o derrota simple.

### Audio runtime

Los WAV generados bastan para probar disparo de eventos de audio sin meter dependencia extra en packs de sonido mayores.

## Qué se ha evitado a propósito

- enemigos complejos
- navegación como dependencia del slice base
- UI elaborada
- packs gigantes con ruido visual
- assets de licencia ambigua
