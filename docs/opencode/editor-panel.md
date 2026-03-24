# OpenCode Editor Panel

## Objetivo

La ventana principal del rail derecho actua como cliente del backend real de OpenCode. El editor ya no intenta resolver salud, sesiones y prompts con estado de UI disperso: todo pasa por `OpenCodeBridge`, `OpenCodeBackendManager` y `OpenCodeSessionController`. No escribe ni modifica el repo por su cuenta, y el mismo flujo existe en CLI.

## Que hace

- Detecta si ya existe un backend accesible en el `host:port` configurado.
- Si al abrir el panel no hay backend accesible, intenta abrir OpenCode automaticamente una vez para este proyecto.
- Permite `Connect`, `Reconnect` y `Start`.
- `Start` abre OpenCode visible en una nueva terminal para este proyecto. Si ya hay backend en el endpoint configurado, abre `opencode attach <url>`; si no, abre `opencode <project> --hostname ... --port ...` y espera a que el backend responda.
- Lista sesiones reales del backend, permite crear una y cambiar entre sesiones.
- Muestra mensajes reales de la sesión activa y permite enviar prompts.
- Hace polling del estado de la sesión activa cuando hay una sesión seleccionada.
- Mantiene diff, approvals y artifacts como datos secundarios de la sesión.
- Conserva la pestaña inferior `OpenCode` solo como vista secundaria/resumen.

## Significado de las acciones

- `Connect`: intenta conectar al backend ya configurado o ya arrancado en el endpoint actual. No arranca procesos.
- `Reconnect`: vuelve a intentar la conexión y refresca el estado visible del backend.
- `Start`: abre OpenCode visible. El editor espera a que el backend quede accesible y, si conecta, carga sesiones reales.
- `New`: crea una sesión real en el backend y la selecciona como sesión activa.
- `Refresh`: refresca conexión, sesiones y la vista de la sesión activa.

## Relación con el terminal

- El editor y la CLI usan la misma fachada `OpenCodeBridge`.
- El botón `Start` del editor intenta reproducir el flujo natural de terminal: abrir OpenCode visible y conectar el panel al backend real.
- Si el backend ya responde en el endpoint configurado, el editor abre `opencode attach <url>` en vez de levantar otra ruta paralela.
- El panel no implementa una TUI paralela ni reimplementa OpenCode.
- La CLI `py -3 tools/engine_cli.py opencode start` sigue significando "arrancar backend HTTP en background" porque es más útil para scripting y automatización.

## Demo Manual

1. Abre el editor y usa el panel `OpenCode` del rail derecho.
2. Si no hay backend:
   - el panel intentara abrir OpenCode automaticamente una vez
   - si aun no conecta, pulsa `Connect` para comprobar si ya existe uno
   - o pulsa `Start` para volver a abrir OpenCode en una terminal nueva
3. Si el backend conecta, revisa el endpoint visible y el estado `connected`.
4. Crea una sesión con `New` o selecciona una existente de la lista.
5. Escribe un prompt en el composer inferior y envíalo con `Send` o `Enter`.
6. Revisa el estado visible del panel:
   - `disconnected`
   - `starting`
   - `connected`
   - `waiting approval`
   - `error`
7. Si hay permisos pendientes:
   - selecciónalos en el panel
   - usa `Allow` o `Deny`
   - equivalente CLI:
     - `py -3 tools/engine_cli.py opencode approvals --session <session_id>`
     - `py -3 tools/engine_cli.py opencode approvals --session <session_id> --permission-id <perm_id> --response allow`
8. Para exportar artifacts desde el panel:
   - `Diff out`
   - `Transcript`
   - equivalente CLI:
     - `py -3 tools/engine_cli.py opencode diff --session <session_id>`
     - `py -3 tools/engine_cli.py opencode messages --session <session_id> --out artifacts/opencode/manual_messages`

## Equivalencias CLI

- Listar sesiones:
  - `py -3 tools/engine_cli.py opencode sessions`
- Comprobar conexión/backend:
  - `py -3 tools/engine_cli.py opencode status`
- Arrancar backend local:
  - `py -3 tools/engine_cli.py opencode start`
- Crear sesión:
  - `py -3 tools/engine_cli.py opencode new-session --title "Editor Demo"`
- Enviar prompt:
  - `py -3 tools/engine_cli.py opencode ask --session <session_id> --agent plan --prompt "Analiza el estado actual del proyecto"`
- Ver mensajes:
  - `py -3 tools/engine_cli.py opencode messages --session <session_id> --limit 100`
- Exportar transcript:
  - `py -3 tools/engine_cli.py opencode messages --session <session_id> --out artifacts/opencode/manual_messages`
- Exportar diff:
  - `py -3 tools/engine_cli.py opencode diff --session <session_id> --out artifacts/opencode/manual_diff`
- Aprobar o denegar:
  - `py -3 tools/engine_cli.py opencode approvals --session <session_id> --permission-id <perm_id> --response allow`

## Restricciones

- El panel no aplica parches ni edita archivos del repo.
- El panel solo consume Bridge + backend real + artifacts.
- La pestaña inferior `OpenCode` ya no es la UI principal; sirve como resumen y recordatorio del nuevo punto de entrada.
- Si el backend no está disponible, el editor sigue funcionando; el panel queda en estado desconectado o error con detalle técnico y acción sugerida.
