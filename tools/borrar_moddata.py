# -*- coding: utf-8 -*-
"""
Borra ModData\\<perfil> de forma SEGURA, sin seguir jamas un reparse point.

POR QUE ESTE SCRIPT EXISTE
--------------------------
ModData\\Default contiene un enlace simbolico 'Data' que apunta a la carpeta
Data REAL del juego. Un borrado recursivo normal lo sigue y te vacia los datos
del juego:

    Remove-Item -Recurse    <- PowerShell 5.1 sigue los junctions. NO USAR.
    shutil.rmtree()         <- puede seguirlos segun la plataforma. NO USAR.

Este script trata todo reparse point como una HOJA: borra el enlace, nunca su
destino. Y verifica al final que el conteo de archivos del juego no ha cambiado.

CUANDO USARLO
-------------
Cuando Frosty se niega a recompilar porque cree que ModData ya esta al dia, pero
ese build salio de una cache defectuosa. Sin ModData, Frosty no tiene nada que
reutilizar y compila de cero.

Uso:
    python borrar_moddata.py [ruta_del_juego] [perfil]
"""
import os
import sys

RUTA_POR_DEFECTO = r"E:\SteamLibrary\steamapps\common\Need for Speed Heat"
PERFIL_POR_DEFECTO = "Default"

# El inyector vive un nivel por encima de tools/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import nfs_heat_injector as nfs  # noqa: E402

contadores = {"archivos": 0, "enlaces": 0, "carpetas": 0}


def contar(carpeta: str) -> int:
    """Cuenta archivos reales bajo una carpeta, sin seguir enlaces."""
    if not os.path.isdir(carpeta):
        return 0
    total = 0
    for actual, dirs, archivos in os.walk(carpeta):
        dirs[:] = [d for d in dirs if not nfs.es_reparse_point(os.path.join(actual, d))]
        total += len(archivos)
    return total


def borrar_arbol(raiz: str) -> None:
    """Borrado post-orden que trata los reparse points como hojas."""
    if nfs.es_reparse_point(raiz):
        nfs.borrar_seguro(raiz)          # elimina SOLO el enlace
        contadores["enlaces"] += 1
        return
    for entrada in os.scandir(raiz):
        ruta = entrada.path
        if nfs.es_reparse_point(ruta):
            nfs.borrar_seguro(ruta)      # nunca desciende
            contadores["enlaces"] += 1
        elif entrada.is_dir(follow_symlinks=False):
            borrar_arbol(ruta)
        else:
            nfs.borrar_seguro(ruta)
            contadores["archivos"] += 1
    os.rmdir(nfs.ruta_larga(raiz))
    contadores["carpetas"] += 1


def main(raiz: str, perfil: str) -> int:
    objetivo = os.path.join(raiz, "ModData", perfil)

    # --- Salvaguardas antes de tocar nada ---
    if not os.path.isdir(raiz):
        return print(f"ABORTADO: no existe la carpeta del juego: {raiz}") or 1
    if not os.path.isdir(objetivo):
        return print(f"ABORTADO: no existe {objetivo}") or 1
    if nfs.es_reparse_point(objetivo):
        return print(f"ABORTADO: {objetivo} es un enlace, no una carpeta real") or 1

    antes_data = contar(os.path.join(raiz, "Data"))
    antes_patch = contar(os.path.join(raiz, "Patch"))
    print(f"ANTES   -> Data: {antes_data} archivos | Patch: {antes_patch} archivos")

    borrar_arbol(objetivo)
    print(f"Borrado: {contadores['archivos']} archivos, "
          f"{contadores['enlaces']} enlaces, {contadores['carpetas']} carpetas")

    despues_data = contar(os.path.join(raiz, "Data"))
    despues_patch = contar(os.path.join(raiz, "Patch"))
    print(f"DESPUES -> Data: {despues_data} archivos | Patch: {despues_patch} archivos")

    if despues_data == antes_data and despues_patch == antes_patch:
        print("OK: los datos reales del juego estan INTACTOS (no se siguio ningun enlace)")
        return 0
    print("*** ALERTA: el conteo cambio. Se siguio un enlace. ***")
    return 1


if __name__ == "__main__":
    sys.exit(main(
        sys.argv[1] if len(sys.argv) > 1 else RUTA_POR_DEFECTO,
        sys.argv[2] if len(sys.argv) > 2 else PERFIL_POR_DEFECTO,
    ))
