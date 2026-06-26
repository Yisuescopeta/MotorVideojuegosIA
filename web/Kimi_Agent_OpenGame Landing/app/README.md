# OpenGame Landing Page

Landing page estatica profesional para OpenGame (OpenGame), construida con Astro y preparada para desplegarse en GitHub Pages.

## Tecnologia

- **Astro** — Framework web estatico
- **Tipografia pixel** — "Press Start 2P" para titulos, "Inter" para cuerpo, "JetBrains Mono" para codigo
- **Sin dependencias externas** — Todo el estilo es CSS puro, las animaciones usan Intersection Observer nativo

## Desarrollo local

```bash
# Instalar dependencias
npm install

# Servidor de desarrollo
npm run dev

# Build de produccion
npm run build

# Preview del build
npm run preview
```

El servidor de desarrollo se iniciara en `http://localhost:4321`.

## Estructura del proyecto

```
/
├── .github/workflows/deploy.yml  # Workflow de GitHub Actions
├── public/
│   └── favicon.svg               # Logo pixel M
├── src/
│   ├── layouts/
│   │   └── Layout.astro          # Layout base con meta, fonts, scripts
│   ├── sections/                 # Secciones de la landing
│   │   ├── Hero.astro
│   │   ├── Introduccion.astro
│   │   ├── Arquitectura.astro
│   │   ├── IaFirst.astro
│   │   ├── Cli.astro
│   │   ├── Exportacion.astro
│   │   ├── Modulos.astro
│   │   ├── QuickStart.astro
│   │   └── Cta.astro
│   ├── components/
│   │   ├── Navbar.astro
│   │   ├── PixelCard.astro
│   │   ├── TerminalBlock.astro
│   │   └── SectionWrapper.astro
│   ├── styles/
│   │   └── global.css             # Variables CSS, resets, utilidades
│   └── pages/
│       └── index.astro            # Pagina principal
├── astro.config.mjs               # Configuracion Astro (base path para GitHub Pages)
├── package.json
└── tsconfig.json
```

## Despliegue en GitHub Pages

### Opcion 1: GitHub Actions (recomendada)

1. Copia todo el contenido de esta carpeta a la raiz de tu repositorio `OpenGame`
2. En GitHub, ve a **Settings → Pages**
3. En "Source", selecciona **GitHub Actions**
4. Haz push a la rama `main`. El workflow `.github/workflows/deploy.yml` se ejecutara automaticamente

### Opcion 2: Deploy manual

```bash
npm run build
# Sube el contenido de la carpeta dist/ a la rama gh-pages
```

### URL de despliegue

La landing estara disponible en:
```
https://yisuescopeta.github.io/OpenGame/
```

## Configuracion importante

El archivo `astro.config.mjs` tiene la siguiente configuracion:

```js
base: '/OpenGame'
```

Esto es necesario para que GitHub Pages sirva correctamente los assets desde la subruta del repositorio. Si cambias el nombre del repositorio, actualiza este valor.

## Secciones incluidas

1. **Hero** — Titulo, descripcion, botones y diagrama Scene → World → Runtime
2. **Introduccion** — Explicacion del proyecto con nota experimental
3. **Arquitectura** — Tarjetas de Scene, World, SceneManager, EngineAPI + diagrama
4. **IA-first** — Descripcion del enfoque IA + bloque de codigo Python
5. **CLI oficial** — Comandos de terminal + tarjetas de comandos
6. **Exportacion** — Pipeline visual + plataformas soportadas
7. **Modulos** — Tres columnas: Core, Oficiales opcionales, Experimental
8. **Quick Start** — Comandos de instalacion
9. **CTA final** — Llamada a la accion + footer