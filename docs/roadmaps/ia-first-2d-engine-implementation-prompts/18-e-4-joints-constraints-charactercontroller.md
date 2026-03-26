# Prompt E.4

## Titulo
E.4 â€” â€œJoints/constraints + CharacterController data-drivenâ€

## Instrucciones

```text
Antes de cambiar nada:
1) Revisa si hay lÃ³gica ad-hoc de â€œpersonajeâ€ (gravedad, suelo) y cÃ³mo se implementa.
2) Revisa si el motor ya distingue entre rigidbody y controlador de personaje.

Objetivo:
- Implementar el â€œCharacterController2Dâ€ como componente data-driven:
  - move_and_collide / move_and_slide semantics (si aplican) o equivalente documentado.
- Implementar joints mÃ­nimos (fixed + distance o equivalente) si el backend lo soporta.

Restricciones:
- PROHIBIDO mezclar lÃ³gica de personaje dentro del editor.
- Todo debe ser serializable y ejecutable en headless.

ValidaciÃ³n:
- 2 escenas: (a) plataforma con personaje, (b) pÃ©ndulo con joint.
- Debug overlay muestra shapes y joints.
```

