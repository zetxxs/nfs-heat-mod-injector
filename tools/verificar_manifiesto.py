# -*- coding: utf-8 -*-
"""
Compara Support/mnfst.txt (el manifiesto oficial de archivos del juego) contra
lo que hay realmente en disco.

Sirve para detectar una instalacion incompleta: archivos de datos que el juego
espera y no estan, o archivos presentes que no pertenecen al juego (residuos de
mods). Una instalacion incompleta hace que Frosty construya un indice de assets
erroneo, y eso produce crashes que parecen culpa del mod.

Uso:
    python verificar_manifiesto.py [ruta_del_juego]
"""
import os
import sys

RUTA_POR_DEFECTO = r"E:\SteamLibrary\steamapps\common\Need for Speed Heat"


def main(raiz: str) -> int:
    mnfst = os.path.join(raiz, "Support", "mnfst.txt")
    if not os.path.isfile(mnfst):
        print(f"No se encontro el manifiesto: {mnfst}")
        return 1

    with open(mnfst, "r", encoding="utf-8", errors="replace") as fh:
        entradas = [l.strip().strip('"') for l in fh if l.strip()]

    faltan, presentes = [], 0
    for rel in entradas:
        if os.path.exists(os.path.join(raiz, rel.replace("/", os.sep))):
            presentes += 1
        else:
            faltan.append(rel)

    print(f"Entradas en el manifiesto : {len(entradas)}")
    print(f"Presentes en disco        : {presentes}")
    print(f"AUSENTES                  : {len(faltan)}")

    # Los archivos de idioma no seleccionados no se descargan: eso es normal.
    idiomas = [f for f in faltan if "/loc/" in f]
    datos = [f for f in faltan
             if f.startswith(("Data/", "Patch/", "Core/")) and "/loc/" not in f]
    resto = [f for f in faltan if f not in idiomas and f not in datos]

    if datos:
        print(f"\n*** {len(datos)} ARCHIVO(S) DE DATOS AUSENTES - instalacion incompleta ***")
        for f in datos:
            print(f"   FALTA  {f}")
        print("\n   Repara con: Steam -> Propiedades -> Archivos locales -> Verificar integridad")
    else:
        print("\nSin archivos de datos ausentes.")

    if idiomas:
        print(f"({len(idiomas)} archivos de idioma no instalados: normal si no los seleccionaste)")
    if resto:
        print(f"({len(resto)} ausencias no criticas: instalador, EULAs, redistribuibles)")

    # Archivos presentes que el manifiesto no reconoce = residuos de mods
    print("\n=== Archivos presentes que NO figuran en el manifiesto ===")
    conocidos = {e.replace("/", os.sep).lower() for e in entradas}
    extras = []
    for base in ("Data", "Patch"):
        carpeta = os.path.join(raiz, base)
        if not os.path.isdir(carpeta):
            continue
        for actual, _dirs, archivos in os.walk(carpeta):
            for n in archivos:
                rel = os.path.relpath(os.path.join(actual, n), raiz)
                if rel.lower() not in conocidos:
                    extras.append((rel, os.path.getsize(os.path.join(actual, n))))
    for rel, tam in sorted(extras):
        print(f"   EXTRA  {tam:>12} B  {rel}")
    if not extras:
        print("   ninguno")

    return 0 if not datos else 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else RUTA_POR_DEFECTO))
