# Prompt E.1

## Titulo
E.1 â€” â€œAPI de fÃ­sica estable y backend pluggableâ€

## Instrucciones

```text
Antes de cambiar nada:
1) Inspecciona el sistema actual de colisiones AABB + rigidbody simple.
2) Identifica cÃ³mo se reportan colisiones (eventos, reglas declarativas).

Objetivo:
- Definir una interfaz PhysicsBackend:
  - create_body, destroy_body
  - create_shape/collider
  - step(dt)
  - query_ray / query_aabb / (opcional) query_shape
  - contact events
- Implementar un backend â€œLegacyAABBâ€ que adapte lo existente a la interfaz (sin reescribirlo).

Restricciones:
- PROHIBIDO romper el gameplay existente.
- Los cuerpos/colisionadores deben ser parte del modelo serializable (componentes).

ValidaciÃ³n:
- El runtime puede alternar backend (config) y los tests base siguen pasando.
- Contact events alimentan el sistema de reglas existente.
```

