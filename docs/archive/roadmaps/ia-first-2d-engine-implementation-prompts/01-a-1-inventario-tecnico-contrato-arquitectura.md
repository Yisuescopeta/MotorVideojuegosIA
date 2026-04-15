# Prompt A.1

## Titulo
A.1 â€” â€œInventario tÃ©cnico + contrato de arquitectura verificableâ€

## Instrucciones

```text
ActÃºa como arquitecto de software. Antes de cambiar nada:
1) Explora el repositorio y produce un inventario preciso: mÃ³dulos principales, carpetas, runtime vs editor, serializaciÃ³n de escenas/prefabs, ECS, timeline/snapshots, CLI/headless y API programÃ¡tica para IA.
2) Identifica explÃ­citamente dÃ³nde vive la â€œfuente de verdadâ€ de los datos hoy (archivos JSON, objetos en memoria, etc.). No asumas: cita rutas/archivos concretos.

Objetivo:
- Crear un documento ARCHITECTURE.md (o /docs/architecture.md) que fije el contrato: â€œla UI traduce el modelo; el modelo serializable es la fuente de verdadâ€, definiendo invariantes testables.

Restricciones:
- PROHIBIDO reimplementar sistemas ya existentes (ECS, escenas JSON, timeline, etc.) sin justificar con evidencia del repo.
- No aÃ±adir dependencias pesadas.
- No introducir estado persistente que exista solo en UI.

Entrega:
- Documento de arquitectura con:
  - invariantes (ej. load->edit->save->load roundtrip)
  - responsabilidades (runtime/editor/API/serializaciÃ³n/tooling)
  - lista de â€œpuntos de integraciÃ³nâ€ para futuras fases.
- Una propuesta de â€œtest matrixâ€ (quÃ© se testea, cÃ³mo, dÃ³nde).

ValidaciÃ³n:
- El documento debe permitir a otro dev entender cÃ³mo aÃ±adir features sin violar el contrato de datos.
```

