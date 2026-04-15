# Como ejecutar demos

La guia antigua del vertical slice se archivo en
[docs/archive/demos/COMO_EJECUTAR.md](docs/archive/demos/COMO_EJECUTAR.md).

Para la documentacion vigente usa:

- [README.md](README.md) para inicio rapido del repo
- [docs/README.md](docs/README.md) para el indice documental maestro
- [docs/cli.md](docs/cli.md) para la CLI oficial `motor`
- [docs/building.md](docs/building.md) para build y distribucion

Comandos actuales de referencia:

```bash
py main.py
py main.py --level levels/platformer_vertical_slice.json
py main.py --level levels/platformer_vertical_slice.json --headless --frames 120
py -m motor doctor --project . --json
```
