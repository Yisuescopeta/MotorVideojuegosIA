"""
build/build_windows.py - Script de build para Windows

Genera el ejecutable empaquetado y opcionalmente el instalador.

Uso:
    python build/build_windows.py              # Solo ejecutable
    python build/build_windows.py --installer  # Ejecutable + instalador

Requisitos:
    pip install pyinstaller
    Inno Setup 6 (solo para --installer): https://jrsoftware.org/isinfo.php
"""

import argparse
import os
import re
import shutil
import subprocess
import sys


def get_project_root() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def read_engine_version(project_root: str) -> str:
    config_path = os.path.join(project_root, "engine", "config.py")
    with open(config_path, encoding="utf-8") as f:
        content = f.read()
    match = re.search(r'ENGINE_VERSION\s*[:=]\s*["\']([^"\']+)["\']', content)
    if not match:
        print("[ERROR] No se encontro ENGINE_VERSION en engine/config.py")
        sys.exit(1)
    return match.group(1)


def find_iscc() -> str:
    """Busca ISCC.exe de Inno Setup en ubicaciones comunes."""
    candidates = [
        shutil.which("ISCC"),
        os.path.join(os.environ.get("ProgramFiles(x86)", ""), "Inno Setup 6", "ISCC.exe"),
        os.path.join(os.environ.get("ProgramFiles", ""), "Inno Setup 6", "ISCC.exe"),
    ]
    for path in candidates:
        if path and os.path.isfile(path):
            return path
    return ""


def run_pyinstaller(project_root: str) -> None:
    spec_path = os.path.join(project_root, "build", "motorvideojuegos.spec")
    print(f"[BUILD] Ejecutando PyInstaller con spec: {spec_path}")
    subprocess.run(
        [sys.executable, "-m", "PyInstaller", spec_path, "--noconfirm", "--distpath",
         os.path.join(project_root, "dist"), "--workpath", os.path.join(project_root, "build", "pyinstaller_work")],
        cwd=project_root,
        check=True,
    )
    print("[BUILD] Ejecutable generado en dist/MotorVideojuegosIA/")


def run_inno_setup(project_root: str, version: str) -> None:
    iscc = find_iscc()
    if not iscc:
        print("[ERROR] No se encontro ISCC.exe (Inno Setup 6).")
        print("        Instalar desde: https://jrsoftware.org/isinfo.php")
        print("        O agregar ISCC.exe al PATH.")
        sys.exit(1)

    iss_path = os.path.join(project_root, "build", "installer.iss")
    print(f"[BUILD] Generando instalador con Inno Setup: {iss_path}")
    subprocess.run(
        [iscc, f"/DAppVersion={version}", iss_path],
        cwd=project_root,
        check=True,
    )
    installer_name = f"MotorVideojuegosIA-{version}-Setup.exe"
    print(f"[BUILD] Instalador generado: dist/{installer_name}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build MotorVideojuegosIA para Windows")
    parser.add_argument("--installer", action="store_true", help="Generar tambien el instalador (requiere Inno Setup 6)")
    args = parser.parse_args()

    project_root = get_project_root()
    version = read_engine_version(project_root)
    print(f"[BUILD] Version: {version}")
    print(f"[BUILD] Raiz del proyecto: {project_root}")

    # Paso 1: PyInstaller
    run_pyinstaller(project_root)

    # Paso 2: Instalador (opcional)
    if args.installer:
        run_inno_setup(project_root, version)

    print()
    print("=" * 60)
    print(f"  Build completado - v{version}")
    print("=" * 60)
    if args.installer:
        print(f"  Instalador: dist/MotorVideojuegosIA-{version}-Setup.exe")
    else:
        print("  Ejecutable: dist/MotorVideojuegosIA/MotorVideojuegosIA.exe")
        print("  (usar --installer para generar el instalador)")


if __name__ == "__main__":
    main()
