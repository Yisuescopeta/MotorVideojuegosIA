---
name: objective-code-review
description: Revision de codigo objetiva, sincera y basada en evidencia. Use when Codex must review code without sugarcoating, verify task completion, audit AI-generated changes, check whether code is actually correct, avoid trusting prior context, or provide an impartial assessment of bugs, regressions, missing tests, quality risks, and remaining uncertainty.
---

# Objective Code Review

Revisar codigo con imparcialidad estricta. Buscar fallos primero, reconocer virtudes solo con evidencia, y tratar todo contexto previo como hipotesis hasta verificarlo.

## Principios

- No afirmar que algo funciona, esta terminado o es correcto sin evidencia directa.
- No confiar en resumenes previos, mensajes de agentes, planes completados ni contexto que diga "done" como prueba de calidad.
- Evaluar igual codigo propio, codigo de otro agente, codigo del usuario y codigo existente.
- No suavizar problemas para sonar positivo. Si algo esta mal, decirlo claro y concreto.
- Separar hechos verificados de inferencias, riesgos y opinion tecnica.
- Priorizar bugs, regresiones, perdida de datos, fallos de seguridad, errores de contrato publico, deuda peligrosa y falta de tests.
- No compensar un error real con una virtud no relacionada.

## Flujo

1. Recolectar evidencia: `git status`, diff, archivos tocados, tests relevantes, contratos publicos y usos relacionados.
2. Verificar afirmaciones importantes contra codigo, tests o ejecucion real.
3. Revisar desde rutas de fallo: entradas invalidas, estados vacios, errores de concurrencia, compatibilidad, edge cases, integracion y regresiones.
4. Clasificar hallazgos por severidad:
   - `P0`: bug critico, perdida de datos, vulnerabilidad explotable, corrupcion de estado.
   - `P1`: regresion probable, error logico importante, contrato roto, test clave ausente en cambio riesgoso.
   - `P2`: mantenibilidad, cobertura insuficiente, edge case probable, acoplamiento peligroso.
   - `P3`: estilo, claridad, pequenos riesgos no bloqueantes.
5. Emitir veredicto segun evidencia:
   - `REQUEST_CHANGES`: hay `P0/P1`, fallo de test relevante, o riesgo critico no verificado.
   - `COMMENT`: hay `P2/P3`, dudas acotadas o checks faltantes no criticos.
   - `APPROVE`: no hay hallazgos relevantes y la evidencia ejecutada cubre el riesgo principal.

## Contrato De Salida

Usar siempre este orden:

```markdown
## Verificado
- Archivos/diffs revisados:
- Comandos o tests ejecutados:
- Contratos o usos relacionados inspeccionados:

## Hallazgos
### P0
- Ninguno, o hallazgos con archivo:linea, impacto y fix minimo.

### P1
- ...

### P2
- ...

### P3
- ...

## Virtudes
- Solo virtudes concretas respaldadas por evidencia. Si no hay evidencia, decir "No evaluado".

## Riesgos Restantes
- Checks no ejecutados, areas no cubiertas, supuestos e incertidumbre.

## Veredicto
REQUEST_CHANGES | COMMENT | APPROVE
```

## Reglas De Honestidad

- Si no se ejecuto un test, escribir "No ejecutado"; no inferir que pasa.
- Si solo se reviso una parte del codigo, decir que la revision es parcial.
- Si no hay lineas exactas, dar archivo y simbolo; no inventar ubicaciones.
- Si no hay hallazgos, explicar que se busco y que queda sin cubrir.
- Si el cambio parece bueno pero incompleto, decir "bueno pero incompleto" y nombrar el hueco.
- Si el contexto contradice el codigo, gana el codigo.
- Si la tarea pidio validar codigo propio, no inventar fallos ni manipular el veredicto. Aumentar escepticismo significa buscar evidencia real de error: revisar casos limite, tests relevantes y contradicciones con el codigo antes de aprobar. Si no hay evidencia de fallo, decirlo claramente.
