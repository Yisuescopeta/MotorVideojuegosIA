# Analisis Actual del Proyecto

> Nota: este documento es una lectura complementaria. El contrato tecnico
> vigente del repo vive en `README.md`, `docs/architecture.md`,
> `docs/TECHNICAL.md` y `docs/schema_serialization.md`.

## 1. Resumen Ejecutivo

Este proyecto es un motor/editor 2D experimental en Python orientado a ser controlado y extendido por una IA. No es solo un "runtime" de juego: combina un motor ECS, un editor visual estilo Unity, carga y guardado de escenas JSON, un modo headless para automatizacion y una API programatica para que un agente externo pueda inspeccionar y modificar el estado del juego.

El objetivo practico del repositorio hoy es permitir crear escenas 2D simples, ejecutarlas en modo PLAY sin perder el estado de edicion, editar entidades visualmente, automatizar pruebas o flujos por script y exponer una interfaz suficientemente explicita para que una IA pueda operar sobre el proyecto sin depender de comportamientos opacos.

## 2. De Que Trata el Proyecto

La app implementa un flujo de trabajo parecido a un mini-editor de videojuegos 2D:

- Se carga una escena desde JSON.
- Esa escena se convierte en un `World` editable.
- El usuario puede seleccionar entidades, ver sus componentes, moverlas y modificar propiedades.
- Al entrar en PLAY, el motor crea una copia temporal del mundo para simular fisica, colisiones y animaciones.
- Al detener la ejecucion, la escena editable se restaura, evitando que la simulacion destruya el estado original.

En paralelo, el proyecto incluye capacidades pensadas para IA y automatizacion:

- API formal en Python para cargar niveles, inspeccionar entidades y editar componentes.
- Modo CLI/headless para ejecutar simulaciones sin interfaz.
- Scripts JSON de automatizacion para reproducir acciones.
- Hot-reload de scripts Python.
- Herramientas auxiliares para introspeccion y generacion de boilerplate.

## 3. Arquitectura General

La base del sistema es una arquitectura ECS:

- `Entity`: contenedor con ID y nombre.
- `Component`: datos puros serializables.
- `System`: logica que procesa entidades con determinados componentes.
- `World`: conjunto de entidades activas.

Encima del ECS hay varias capas:

- `Scene` y `SceneManager`: gestionan la escena editable y el mundo de runtime.
- `Game`: coordina ventana, loop principal, entrada, render y estados.
- `EditorLayout` y paneles: construyen la UI del editor.
- `EventBus` y `RuleSystem`: permiten reaccionar a eventos con reglas declarativas.
- `EngineAPI` y `CLIRunner`: exponen el motor a uso programatico y automatizado.

## 4. Funcionamiento de la Aplicacion

### 4.1 Modos de ejecucion

La app tiene dos modos principales:

- GUI: abre ventana Raylib, muestra editor visual y permite interaccion directa.
- Headless/CLI: ejecuta logica sin abrir ventana, util para tests, scripts y agentes.

### 4.2 Estados del motor

El motor trabaja con estados bien definidos:

- `EDIT`: modo de autoria. Permite editar escena y ver preview lento de animaciones.
- `PLAY`: ejecuta simulacion real sobre una copia temporal del mundo.
- `PAUSED`: congela la simulacion.
- `STEPPING`: avanza exactamente un frame y vuelve a pausado.

### 4.3 Flujo Scene vs RuntimeWorld

Este es el concepto central del proyecto actual:

- La escena JSON es la fuente de verdad.
- En `EDIT` se usa un `World` editable derivado de esa escena.
- En `PLAY` se crea un `RuntimeWorld` clonado.
- Al salir de `PLAY`, el editor reconstruye el mundo original desde la escena.

Esto permite probar gameplay sin contaminar el estado de edicion.

## 5. Funcionalidades Actuales

### 5.1 Carga de niveles desde JSON

Actualmente se pueden cargar escenas JSON desde archivo. El nivel incluido `levels/demo_level.json` define entidades, componentes y metadatos de escena.

Capacidades actuales:

- Cargar escena al iniciar.
- Recargar la escena con `R`.
- Crear una escena nueva desde la UI.
- Guardar la escena actual a disco.
- Abrir una escena desde selector de archivos.
- Guardado automatico periodico en `autosave.json`.

### 5.2 Sistema ECS operativo

El motor tiene un ECS funcional con estas capacidades:

- Crear entidades por nombre.
- Anadir y quitar componentes.
- Buscar entidades por ID o nombre.
- Filtrar entidades por tipos de componente.
- Clonar el `World`.
- Serializar el mundo para guardado.

### 5.3 Componentes implementados

Los componentes fuente realmente disponibles en el repositorio son:

- `Transform`: posicion, rotacion, escala y relaciones padre-hijo.
- `Sprite`: textura, tamano, origen, flip y tinte.
- `Collider`: colision AABB con soporte para trigger.
- `RigidBody`: velocidad, gravedad e indicador de suelo.
- `Animator`: animaciones por sprite sheet con estados, fps, loop y transiciones por `on_complete`.

### 5.4 Render 2D

El motor renderiza entidades con `Transform` usando tres estrategias:

- `Animator`, si existe sprite sheet animado.
- `Sprite`, si existe textura estatica.
- Placeholder rectangular si la entidad no tiene recurso visual.

Ademas muestra:

- Colliders en modo debug.
- Resaltado de entidad seleccionada.
- Nombre de la entidad seleccionada.

### 5.5 Fisica y backends

La fisica actual ya no es solo una base monolitica minima:

- existe un contrato comun de backends fisicos
- `legacy_aabb` sigue siendo la base obligatoria del core
- `box2d` puede activarse de forma opcional cuando la dependencia esta
  disponible
- hay queries publicas y seleccion efectiva de backend con fallback explicito

El limite real sigue siendo de producto, no de contrato: el core garantiza una
superficie comun y comparable, pero no documenta `box2d` como dependencia
obligatoria ni promete determinismo cross-platform fuerte.

### 5.6 Colisiones AABB

El sistema de colision detecta intersecciones AABB entre entidades con `Transform` y `Collider`.

Funcionalidades:

- Deteccion de colisiones entre pares de entidades.
- Distincion entre colision normal y trigger.
- Emision de eventos `on_collision`.
- Emision de eventos `on_trigger_enter`.
- Consulta de colisiones actuales desde el sistema.

### 5.7 Animaciones por estados

El sistema de animacion soporta:

- Multiples estados por entidad.
- Listas de frames.
- Velocidad por animacion.
- Loop o animacion finita.
- Cambio automatico a otro estado al terminar una animacion.
- Evento `on_animation_end`.

En modo `EDIT` las animaciones pueden previsualizarse a velocidad reducida.

### 5.8 EventBus y reglas declarativas

La app incluye un mecanismo de gameplay data-driven:

- Sistemas emiten eventos.
- `RuleSystem` escucha eventos concretos.
- Las reglas se definen en JSON.
- Si se cumplen condiciones `when`, se ejecutan acciones `do`.

Acciones implementadas:

- `set_animation`
- `set_position`
- `destroy_entity`
- `emit_event`
- `log_message`

Esto permite definir parte del comportamiento del juego sin escribir codigo Python adicional.

### 5.9 Editor visual estilo Unity

La ventana principal esta organizada como un editor:

- Panel izquierdo: jerarquia.
- Centro: vista `Scene` y vista `Game`.
- Panel derecho: inspector.
- Panel inferior: `Project` y `Console`.
- Barra superior con herramientas y controles.

Tambien soporta:

- Splitters para redimensionar paneles.
- Camara de editor con pan y zoom.
- Grid de escena.
- Cambio entre pestañas `Scene` y `Game`.
- Botones `Play`, `Pause` y `Step`.
- Botones `New`, `Open` y `Save`.

### 5.10 Seleccion de entidades

La seleccion en escena permite:

- Hacer click sobre entidades para seleccionarlas.
- Detectar bounds usando prioridad `Collider > Sprite > Animator > placeholder`.
- Deseleccionar al hacer click en vacio.
- Reflejar la seleccion en el render y en el inspector.

### 5.11 Gizmos de transformacion

El editor tiene gizmos visuales para manipular entidades seleccionadas:

- Mover en eje X.
- Mover en eje Y.
- Rotar.
- Escalar en X.
- Escalar en Y.
- Escalado uniforme.

La toolbar refleja herramientas tipo `Hand`, `Move`, `Rotate`, `Scale` y `Rect`, aunque la implementacion mas directa hoy esta en mover/rotar/escalar.

### 5.12 Inspector editable

El inspector actual soporta bastante interaccion:

- Visualizacion de la entidad seleccionada.
- Lista de componentes.
- Cabeceras colapsables por componente.
- Edicion de campos numericos.
- Ajuste por arrastre horizontal sobre la etiqueta.
- Edicion textual de valores numericos.
- Checkboxes para booleanos.
- Eliminacion de componentes.
- Menu para agregar componentes disponibles.

### 5.13 Jerarquia de entidades

El panel de jerarquia permite:

- Ver entidades de la escena.
- Seleccionar entidad.
- Crear nueva entidad con `Transform`.
- Abrir menu contextual con acciones.
- Eliminar entidad.
- Duplicar subarboles de entidades.
- Guardar entidad como prefab.

Tambien existe soporte consolidado para:

- relaciones padre-hijo serializables
- validacion de padres invalidos o ciclos
- preservacion de jerarquia en save/load
- duplicacion de subarboles y copia entre escenas de workspace

### 5.14 Panel de proyecto y drag and drop

El panel `Project` permite:

- Navegar el arbol de archivos bajo `assets`.
- Ver carpetas y archivos.
- Arrastrar archivos desde el panel a la escena.

Cuando se suelta un archivo en la vista de escena:

- Si es `.prefab`, se instancia un prefab.
- Si es otro archivo, se crea una entidad con `Transform`, `Sprite` y `Collider`.

### 5.15 Sistema de prefabs

La gestion de prefabs esta implementada a nivel de codigo:

- Guardar una entidad como archivo `.prefab`.
- Cargar datos de prefab.
- Instanciar un prefab en el mundo.
- Sobrescribir posicion al instanciar.
- Generar nombres unicos si ya existe una entidad con el mismo nombre.

### 5.16 Consola y logging

El editor contempla consola de mensajes y el codigo usa logging textual para:

- Informacion de carga.
- Guardado y autosave.
- Errores de gameplay.
- Errores de render.
- Hot-reload.
- Operaciones de scene manager.

### 5.17 Hot-reload de scripts Python

Existe un `HotReloadManager` operativo para el directorio `scripts/`:

- Escanea archivos `.py`.
- Detecta cambios por timestamp.
- Recarga modulos con `importlib.reload`.
- Guarda errores sin tirar el motor.
- Ejecuta `on_reload()` si el modulo la define.

### 5.18 Snapshots y timeline

El motor implementa debugging temporal basico:

- Guardar snapshot del `World`.
- Mantener historial en una `Timeline`.
- Restaurar el ultimo snapshot.
- Avanzar un solo frame con `Step`.

Esto sirve como base para debugging reproducible y experimentacion.

### 5.19 Controles de teclado actuales

Controles observables en codigo:

- `SPACE`: entrar/salir de PLAY.
- `P`: pausar o reanudar.
- `ESC`: stop y vuelta a edicion.
- `R`: recargar escena.
- `F10`: avanzar un frame.
- `F5`: guardar snapshot.
- `F6`: restaurar ultimo snapshot.
- `F8`: hot-reload de scripts.
- `F11`: fullscreen.
- `Ctrl+S`: guardar escena actual.

### 5.20 Modo CLI / headless

La app puede ejecutarse sin interfaz grafica mediante argumentos:

- `--headless`
- `--frames`
- `--script`
- `--level`

Casos de uso actuales:

- Simular frames de juego.
- Cargar niveles desde terminal.
- Ejecutar scripts de automatizacion.
- Usar el motor en entornos de test o agentes.

### 5.21 Automatizacion por scripts JSON

Hay un ejecutor de scripts secuenciales para automatizar flujos de prueba y operacion.

Comandos implementados:

- `LOAD_SCENE`
- `SELECT`
- `INSPECT_EDIT`
- `PLAY`
- `STOP`
- `SAVE`
- `WAIT`
- `ASSERT_POS`
- `PARENT`
- `EXIT`

Esto permite construir pruebas funcionales simples sin interactuar manualmente con la UI.

### 5.22 API programatica para IA

La clase `EngineAPI` expone el contrato publico estable para control externo del
motor.

Funciones actuales:

- authoring de entidades, componentes y `feature_metadata`
- runtime (`play`, `stop`, `step`, input y eventos)
- workspace y scene flow
- assets y proyecto
- debug/profiler
- UI serializable

La fachada publica esta delegada internamente por dominios, pero el punto de
entrada sigue siendo unico. La regla vigente es que wrappers, tests y tooling
usen `EngineAPI`, no internals privados del runtime.

El repositorio incluye una prueba de uso centrada precisamente en demostrar ese flujo.

### 5.23 Herramientas auxiliares para IA

El directorio `tools/` aporta utilidades practicas:

- `create_mechanic.py`: genera boilerplate de un nuevo sistema ECS.
- `introspect.py`: inspecciona entidades, mundo, sistemas y tipos de componente.
- `generate_test_spritesheet.py`: genera spritesheet de prueba si falta el asset.

## 6. Estado Actual del Proyecto

Lo que existe hoy no es una demo vacia: hay una app usable para prototipado de escenas 2D sencillas y para experimentar con control por IA. La combinacion mas madura del repositorio es:

- ECS basico.
- Editor visual.
- Scene/RuntimeWorld.
- Simulacion minima.
- Serializacion JSON.
- Automatizacion headless.
- API programatica.

Ese conjunto ya permite construir un flujo de trabajo completo de autoria, prueba y automatizacion.

## 7. Limitaciones y Puntos Incompletos Detectados

Durante el analisis del codigo se observan varias limitaciones importantes que conviene dejar explicitas:

### 7.1 Fisica todavia simple

- La fisica usa gravedad y suelo temporal.
- No hay resolucion completa de colisiones ni respuesta fisica avanzada.
- `CollisionSystem` detecta, pero no resuelve penetraciones ni rebotes.

### 7.2 Reglas declarativas con alcance acotado

- El `RuleSystem` tiene un conjunto pequeno de acciones.
- Las condiciones son comparaciones directas de igualdad.
- No hay lenguaje de expresiones mas avanzado.

### 7.3 Edicion persistente parcial segun el flujo

- Las rutas principales de authoring ya se recondujeron a `SceneManager` y
  `Scene`.
- `sync_from_edit_world()` sigue existiendo, pero queda acotado a compatibilidad
  legacy explicita; no es el flujo normal recomendado.
- El dirty/save/autosave no deben contaminarse con previews transitorios del
  gizmo.

### 7.4 Jerarquia y workspace: limites reales

- La jerarquia serializable y su roundtrip estan cubiertos por tests.
- La seleccion y el dirty state ya son responsabilidad de `SceneManager` por
  escena de workspace.
- El limite actual no es "no hay jerarquia", sino que el sistema sigue
  dependiendo de nombres unicos y de relaciones padre-hijo validas en datos.

### 7.5 UI y affordances de editor

- Siguen existiendo affordances visuales y controles de toolbar que son UX del
  editor, no contrato de datos.
- Eso no debe confundirse con fuente de verdad: la capa de UI traduce al modelo
  serializable y no debe abrir rutas funcionales paralelas.

### 7.6 Algunas inconsistencias de madurez

El proyecto sigue en consolidacion tecnica y convive con capas de distinta
madurez:

- el core serializable y las rutas compartidas de authoring estan bastante mas
  endurecidos que la UX del editor
- existen restos historicos en documentacion, comentarios y tooling auxiliar
- RL, datasets y runners paralelos existen, pero conviene tratarlos como
  `experimental/tooling`, no como core obligatorio

### 7.7 Inventario de features mayor en binarios que en fuente

En `__pycache__` aparecen nombres de modulos mas avanzados que no estan presentes como fuente `.py` en este estado del repositorio. Por tanto, este analisis se basa solo en funcionalidades verificables desde el codigo fuente disponible, no en artefactos compilados.

## 8. Perfil de Uso Ideal del Proyecto Hoy

En su estado actual, el proyecto encaja especialmente bien para:

- prototipos 2D simples,
- entornos academicos,
- investigacion sobre motores "IA-friendly",
- pruebas de escenas y reglas data-driven,
- automatizacion de flujos de editor y runtime,
- experimentos con agentes que inspeccionan y modifican un motor de juego.

No parece todavia orientado a produccion comercial ni a juegos complejos, pero si a exploracion tecnica muy clara y extensible.

## 9. Conclusion

Este repositorio trata de construir un motor/editor 2D transparente, serializable y controlable por IA. Su valor principal no esta solo en renderizar sprites, sino en ofrecer una arquitectura comprensible para que tanto personas como agentes automaticos puedan cargar escenas, inspeccionar entidades, editar componentes, ejecutar simulacion y automatizar pruebas.

Actualmente ya incorpora un conjunto funcional coherente:

- editor visual,
- ECS,
- escenas JSON,
- simulacion basica,
- animacion,
- colisiones,
- prefabs,
- hot-reload,
- snapshots,
- CLI headless,
- API para IA,
- herramientas auxiliares de introspeccion y generacion.

En resumen: hoy el proyecto es un mini motor/editor 2D experimental, ya usable para prototipado y automatizacion, con una orientacion muy clara hacia integracion con IA y con varias bases tecnicas bien asentadas, aunque aun con zonas parciales y varias piezas pendientes de endurecer.
