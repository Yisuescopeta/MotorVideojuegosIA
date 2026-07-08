# Solitario Espanol

MVP jugable de Solitario Espanol para demostrar escenas 2D, sprites, input, estado, reglas, reinicio y victoria en OpenGame sin tocar el motor.

## Reglas implementadas

- Baraja espanola de 40 cartas: oros, copas, espadas, bastos; valores 1, 2, 3, 4, 5, 6, 7, 10, 11, 12.
- Reparto tipo Klondike: 7 columnas con tamanos 1 a 7; solo la ultima carta de cada columna queda boca arriba.
- Stock de 12 cartas, robo de 1 carta y descarte boca arriba.
- Reciclado ilimitado del descarte al agotarse el stock.
- Bases por palo en orden ascendente: 1, 2, 3, 4, 5, 6, 7, 10, 11, 12.
- Columnas en orden descendente con color alterno: oros/copas rojo, espadas/bastos negro.
- Columna vacia solo acepta Rey, valor 12.
- Auto-volteo de la carta superior cuando se libera una carta boca abajo.
- Victoria cuando las 40 cartas llegan a las bases.

## Controles

- Click en mazo: robar carta o reciclar descarte si el mazo esta vacio.
- Click en carta boca arriba de columna: seleccionar carta o secuencia valida.
- Click en carta superior del descarte: seleccionar carta.
- Click en columna o base: intentar mover seleccion.
- Tecla `R`: reiniciar partida.
- Boton `Reiniciar`: recarga la escena.

## Assets

Ruta del proyecto:

```text
projects/Opengame cartas/assets/spanish_deck
```

La carpeta contiene `1.PNG` a `40.PNG` y `back.PNG`, cartas RGBA de 73x113. El mapeo usado es:

- `1-10`: oros.
- `11-20`: copas.
- `21-30`: espadas.
- `31-40`: bastos.

## Ejecutar

Desde `projects/Opengame cartas`:

```powershell
$env:PYTHONPATH="..\.."
py -m engine.runtime.exported_game
```

Modo headless:

```powershell
$env:PYTHONPATH="..\.."
py -m engine.runtime.exported_game --headless --frames 5
```

## Testear

Desde la raiz del repo:

```powershell
py -m pytest tests/test_solitario_espanol.py
py -m motor doctor --project "projects\Opengame cartas" --json
py -m motor ai compliance --project "projects\Opengame cartas" --json
```

## Limitaciones conocidas

- Interaccion por seleccion/click; drag and drop queda fuera del MVP.
- Foundations son destino final; no se permite sacar cartas de las bases.
- Sin undo, pistas, guardado, sonido ni animaciones avanzadas.

## Mejoras futuras

- Drag and drop.
- Undo limitado.
- Pistas.
- Animaciones de movimiento.
- Sonidos.
- Guardado/carga de partida.
- Estadisticas persistentes.
