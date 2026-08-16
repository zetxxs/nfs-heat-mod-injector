# -*- coding: utf-8 -*-
"""Parser minimo de minidumps (.mdmp) para extraer la excepcion y el modulo culpable."""
import struct
import sys

TIPO_MODULOS = 4
TIPO_EXCEPCION = 6
TIPO_SYSINFO = 7

CODIGOS = {
    0xC0000005: "ACCESS_VIOLATION (lectura/escritura en memoria invalida)",
    0xC000001D: "ILLEGAL_INSTRUCTION",
    0xC0000094: "INTEGER_DIVIDE_BY_ZERO",
    0xC0000096: "PRIVILEGED_INSTRUCTION",
    0xC00000FD: "STACK_OVERFLOW",
    0xC0000409: "STACK_BUFFER_OVERRUN / __fastfail",
    0xC0000374: "HEAP_CORRUPTION",
    0x80000003: "BREAKPOINT (int 3)",
    0xE06D7363: "Excepcion C++ no capturada",
    0xC0000006: "IN_PAGE_ERROR (fallo al leer datos de disco)",
}


def leer(ruta):
    with open(ruta, "rb") as fh:
        datos = fh.read()

    firma, version, n_streams, dir_rva = struct.unpack_from("<IIII", datos, 0)
    if firma != 0x504D444D:
        print(f"  No es un minidump valido (firma {firma:#x})")
        return

    streams = {}
    for i in range(n_streams):
        off = dir_rva + i * 12
        tipo, tam, rva = struct.unpack_from("<III", datos, off)
        streams[tipo] = (tam, rva)

    # ---- Lista de modulos (para localizar la direccion del fallo) ----
    modulos = []
    if TIPO_MODULOS in streams:
        _tam, rva = streams[TIPO_MODULOS]
        (n_mod,) = struct.unpack_from("<I", datos, rva)
        for i in range(n_mod):
            off = rva + 4 + i * 108
            base, tam_img = struct.unpack_from("<QI", datos, off)
            # MINIDUMP_MODULE: Base(8) Size(4) CheckSum(4) TimeDateStamp(4) NameRva(4)
            (nombre_rva,) = struct.unpack_from("<I", datos, off + 20)
            (long_bytes,) = struct.unpack_from("<I", datos, nombre_rva)
            nombre = datos[nombre_rva + 4: nombre_rva + 4 + long_bytes].decode("utf-16-le", "replace")
            modulos.append((base, tam_img, nombre))

    # ---- Excepcion ----
    if TIPO_EXCEPCION not in streams:
        print("  El volcado no contiene stream de excepcion.")
        return
    _tam, rva = streams[TIPO_EXCEPCION]
    hilo = struct.unpack_from("<I", datos, rva)[0]
    codigo, flags = struct.unpack_from("<II", datos, rva + 8)
    _rec, direccion = struct.unpack_from("<QQ", datos, rva + 16)
    n_params = struct.unpack_from("<I", datos, rva + 32)[0]
    params = struct.unpack_from("<15Q", datos, rva + 40)

    print(f"  Hilo culpable     : {hilo}")
    print(f"  Codigo excepcion  : {codigo:#010x}  {CODIGOS.get(codigo, 'desconocido')}")
    print(f"  Direccion del fallo: {direccion:#018x}")

    if codigo == 0xC0000005 and n_params >= 2:
        modo = {0: "LECTURA", 1: "ESCRITURA", 8: "EJECUCION (DEP)"}.get(params[0], f"modo {params[0]}")
        print(f"  Operacion         : {modo} sobre la direccion {params[1]:#018x}")

    culpable = None
    for base, tam_img, nombre in modulos:
        if base <= direccion < base + tam_img:
            culpable = (base, nombre)
            break
    if culpable:
        base, nombre = culpable
        print(f"  MODULO CULPABLE   : {nombre}")
        print(f"  Offset en el modulo: {direccion - base:#x}")
    else:
        print("  MODULO CULPABLE   : ninguno (direccion fuera de todo modulo cargado)")

    print(f"  Modulos cargados  : {len(modulos)}")


for ruta in sys.argv[1:]:
    print(f"\n=== {ruta.split(chr(92))[-1]} ===")
    try:
        leer(ruta)
    except Exception as exc:
        print(f"  Error al parsear: {exc}")
