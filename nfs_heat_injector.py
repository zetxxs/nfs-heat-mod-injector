#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
 NFS HEAT MOD INJECTOR  -  Inyector atomizado de mods Frosty para Frostbite
================================================================================
 Juego   : Need for Speed Heat (Steam AppID 1222680)
 Autor   : Herramienta generada para entorno Steam + EA App
 Python  : 3.8+  (solo biblioteca estandar; 'psutil' es OPCIONAL)
 Plataforma: Windows unicamente (usa Win32 API via ctypes)

--------------------------------------------------------------------------------
 POR QUE ESTE SCRIPT NO ES UN "COPIADOR RECURSIVO" GENERICO
--------------------------------------------------------------------------------
 Frosty Mod Manager NO genera una copia completa del juego en ModData\\Default.
 Genera un "arbol espejo" compuesto por:

   * ENLACES SIMBOLICOS (reparse points) que apuntan de vuelta a los archivos
     VANILLA del juego  -> representan contenido NO modificado.
   * ARCHIVOS REALES    -> el payload verdadero del mod (normalmente pocos MB).
   * Carpetas que son a su vez enlaces simbolicos a carpetas del juego
     (p.ej. ModData\\Default\\Data -> <juego>\\Data).

 Un script que recorra ModData\\Default con shutil/os.walk SIGUIENDO enlaces
 entrara en la carpeta Data REAL del juego y creera que son "archivos del mod".
 Al hacer backup por MOVIMIENTO, dejara al juego SIN esos archivos vanilla.
 Ese es exactamente el fallo que corrompe la instalacion y produce los
 "UnauthorizedAccessException" a mitad de proceso (deja todo a medias, sin
 rollback).

 REGLA DE ORO IMPLEMENTADA AQUI:
   1) NUNCA se desciende dentro de un reparse point.
   2) NUNCA se inyecta un archivo cuyo destino sea fisicamente el mismo inodo.
   3) El backup se hace por COPIA VERIFICADA POR HASH, jamas por movimiento.
   4) Toda la operacion es TRANSACCIONAL: si algo falla, se revierte.
================================================================================
"""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import re
import struct
import subprocess
import sys
import time
import traceback
from ctypes import wintypes
from datetime import datetime
from typing import Dict, Iterator, List, Optional, Tuple

# ==============================================================================
# SECCION 1 - CONFIGURACION
# ==============================================================================

RUTA_JUEGO = r"E:\SteamLibrary\steamapps\common\Need for Speed Heat"
PERFIL_FROSTY = "Default"
STEAM_APPID = "1222680"
EJECUTABLE_JUEGO = "NeedForSpeedHeat.exe"

# Frosty instala un PROXY: renombra el juego real a 'NeedForSpeedHeat.orig.exe' y
# deja un stub de ~117 KB como 'NeedForSpeedHeat.exe'. Si solo se vigila el nombre
# original, el inyector cree que el juego esta cerrado cuando en realidad corre
# bajo el nombre .orig. Hay que contemplar todos los nombres posibles.
EJECUTABLES_JUEGO = [
    "NeedForSpeedHeat.exe",
    "NeedForSpeedHeat.orig.exe",
    "NeedForSpeedHeatTrial.exe",
]

# Modo de inyeccion:
#   "copia"    -> Copia fisica del archivo. MAS SEGURO (aislado de ModData). [DEFECTO]
#   "hardlink" -> Enlace duro NTFS. Instantaneo y 0 bytes en disco, pero el archivo
#                 del juego y el de ModData comparten inodo: si Frosty reescribe
#                 ModData mas tarde, el juego puede quedar con contenido obsoleto.
#   "junction" -> Reemplazo a nivel de CARPETA mediante junction NTFS. Solo valido
#                 si la carpeta origen NO es un reparse point (se valida).
MODO_INYECCION = "copia"

# Procesos que mantienen handles abiertos sobre Data\ y Patch\
PROCESOS_A_CERRAR = [
    "NeedForSpeedHeat.exe",
    "NeedForSpeedHeat.orig.exe",   # proxy de Frosty: el juego real corre con este nombre
    "NeedForSpeedHeatTrial.exe",
    "EADesktop.exe",
    "EABackgroundService.exe",
    "EAAncillaryService.exe",
    "EALocalHostSvc.exe",
    "EAConnect_microsoft.exe",
    "EACefSubProcess.exe",
    "EAGSHelper.exe",
    "Origin.exe",
    "OriginClientService.exe",
    "OriginWebHelperService.exe",
    "FrostyModManager.exe",
    "FrostyEditor.exe",
    "steamwebhelper.exe",
    "steam.exe",
]

# Servicios de Windows que reabren handles aunque se maten los procesos
SERVICIOS_A_DETENER = [
    "EABackgroundService",
    "EAAntiCheatService",
    "Origin Client Service",
    "Steam Client Service",
]

# Nombres de directorios dentro de ModData que NO son contenido de mod
CARPETAS_INTERNAS = {"_VanillaBackup", "_InjectorState", "_Backup_Originals"}

TIEMPO_ESPERA_DESBLOQUEO = 30      # segundos maximos esperando liberacion de un archivo
TAMANO_BLOQUE_HASH = 1024 * 1024   # 1 MiB

# Si es True, toda pregunta si/no se responde afirmativamente sin preguntar.
# Lo activa el flag --si para permitir ejecucion desatendida (CI, scripts, .bat).
ASUMIR_SI = False


# ==============================================================================
# SECCION 2 - CAPA WIN32 (ctypes). Todo aqui es a prueba de idioma del sistema.
# ==============================================================================

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
shell32 = ctypes.WinDLL("shell32", use_last_error=True)

INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
INVALID_FILE_ATTRIBUTES = 0xFFFFFFFF

FILE_ATTRIBUTE_READONLY = 0x00000001
FILE_ATTRIBUTE_HIDDEN = 0x00000002
FILE_ATTRIBUTE_SYSTEM = 0x00000004
FILE_ATTRIBUTE_DIRECTORY = 0x00000010
FILE_ATTRIBUTE_NORMAL = 0x00000080
FILE_ATTRIBUTE_REPARSE_POINT = 0x00000400

GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
FILE_SHARE_READ = 0x00000001
FILE_SHARE_WRITE = 0x00000002
FILE_SHARE_DELETE = 0x00000004
OPEN_EXISTING = 3
FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
FILE_FLAG_OPEN_REPARSE_POINT = 0x00200000

ERROR_ACCESS_DENIED = 5
ERROR_SHARING_VIOLATION = 32
ERROR_LOCK_VIOLATION = 33

FSCTL_SET_REPARSE_POINT = 0x000900A4
IO_REPARSE_TAG_MOUNT_POINT = 0xA0000003

TH32CS_SNAPPROCESS = 0x00000002
PROCESS_TERMINATE = 0x0001
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
SYNCHRONIZE = 0x00100000

TOKEN_ADJUST_PRIVILEGES = 0x0020
TOKEN_QUERY = 0x0008
SE_PRIVILEGE_ENABLED = 0x00000002

# --- Prototipos ---------------------------------------------------------------
kernel32.GetFileAttributesW.argtypes = [wintypes.LPCWSTR]
kernel32.GetFileAttributesW.restype = wintypes.DWORD

kernel32.SetFileAttributesW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD]
kernel32.SetFileAttributesW.restype = wintypes.BOOL

kernel32.CreateFileW.argtypes = [
    wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
    wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE,
]
kernel32.CreateFileW.restype = wintypes.HANDLE

kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.CloseHandle.restype = wintypes.BOOL

kernel32.CreateHardLinkW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.LPVOID]
kernel32.CreateHardLinkW.restype = wintypes.BOOL

kernel32.DeviceIoControl.argtypes = [
    wintypes.HANDLE, wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD,
    wintypes.LPVOID, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID,
]
kernel32.DeviceIoControl.restype = wintypes.BOOL

kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.OpenProcess.restype = wintypes.HANDLE

kernel32.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
kernel32.TerminateProcess.restype = wintypes.BOOL

kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
kernel32.WaitForSingleObject.restype = wintypes.DWORD


class BY_HANDLE_FILE_INFORMATION(ctypes.Structure):
    """Identidad fisica de un archivo en NTFS (volumen + indice MFT)."""
    _fields_ = [
        ("dwFileAttributes", wintypes.DWORD),
        ("ftCreationTime", wintypes.FILETIME),
        ("ftLastAccessTime", wintypes.FILETIME),
        ("ftLastWriteTime", wintypes.FILETIME),
        ("dwVolumeSerialNumber", wintypes.DWORD),
        ("nFileSizeHigh", wintypes.DWORD),
        ("nFileSizeLow", wintypes.DWORD),
        ("nNumberOfLinks", wintypes.DWORD),
        ("nFileIndexHigh", wintypes.DWORD),
        ("nFileIndexLow", wintypes.DWORD),
    ]


kernel32.GetFileInformationByHandle.argtypes = [
    wintypes.HANDLE, ctypes.POINTER(BY_HANDLE_FILE_INFORMATION)
]
kernel32.GetFileInformationByHandle.restype = wintypes.BOOL


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", wintypes.WCHAR * 260),
    ]


class LUID(ctypes.Structure):
    _fields_ = [("LowPart", wintypes.DWORD), ("HighPart", wintypes.LONG)]


class LUID_AND_ATTRIBUTES(ctypes.Structure):
    _fields_ = [("Luid", LUID), ("Attributes", wintypes.DWORD)]


class TOKEN_PRIVILEGES(ctypes.Structure):
    _fields_ = [("PrivilegeCount", wintypes.DWORD), ("Privileges", LUID_AND_ATTRIBUTES * 1)]


def ruta_larga(ruta: str) -> str:
    """Prefija con \\\\?\\ para superar el limite MAX_PATH de 260 caracteres."""
    ruta = os.path.abspath(ruta)
    if ruta.startswith("\\\\?\\"):
        return ruta
    if ruta.startswith("\\\\"):
        return "\\\\?\\UNC\\" + ruta[2:]
    return "\\\\?\\" + ruta


def obtener_atributos(ruta: str) -> int:
    """Devuelve los atributos Win32 o INVALID_FILE_ATTRIBUTES si no existe."""
    return kernel32.GetFileAttributesW(ruta_larga(ruta))


def es_reparse_point(ruta: str) -> bool:
    """
    CLAVE DE SEGURIDAD: detecta enlaces simbolicos y junctions SIN seguirlos.
    Si esto devuelve True, jamas se debe descender ni tratar como contenido real.
    """
    attr = obtener_atributos(ruta)
    if attr == INVALID_FILE_ATTRIBUTES:
        return False
    return bool(attr & FILE_ATTRIBUTE_REPARSE_POINT)


def quitar_solo_lectura(ruta: str) -> bool:
    """Elimina los atributos Solo-Lectura / Oculto / Sistema de un archivo."""
    attr = obtener_atributos(ruta)
    if attr == INVALID_FILE_ATTRIBUTES:
        return False
    limpio = attr & ~(FILE_ATTRIBUTE_READONLY | FILE_ATTRIBUTE_HIDDEN | FILE_ATTRIBUTE_SYSTEM)
    if limpio == attr:
        return True
    if limpio == 0:
        limpio = FILE_ATTRIBUTE_NORMAL
    return bool(kernel32.SetFileAttributesW(ruta_larga(ruta), limpio))


def identidad_archivo(ruta: str) -> Optional[Tuple[int, int]]:
    """
    Devuelve (numero_serie_volumen, indice_MFT) siguiendo enlaces.

    Permite detectar que ModData\\...\\x.sb y <juego>\\...\\x.sb son EL MISMO
    archivo fisico (caso de los symlinks/hardlinks que crea Frosty). Si lo son,
    inyectar seria una operacion destructiva y sin sentido.
    """
    h = kernel32.CreateFileW(
        ruta_larga(ruta), 0,
        FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
        None, OPEN_EXISTING, FILE_FLAG_BACKUP_SEMANTICS, None,
    )
    if h == INVALID_HANDLE_VALUE:
        return None
    try:
        info = BY_HANDLE_FILE_INFORMATION()
        if not kernel32.GetFileInformationByHandle(h, ctypes.byref(info)):
            return None
        return (info.dwVolumeSerialNumber,
                (info.nFileIndexHigh << 32) | info.nFileIndexLow)
    finally:
        kernel32.CloseHandle(h)


def estado_bloqueo(ruta: str) -> Tuple[bool, int]:
    """
    Intenta abrir el archivo en modo EXCLUSIVO (dwShareMode = 0).
    Es la unica forma fiable de saber si otro proceso mantiene un handle.
    Devuelve (esta_bloqueado, codigo_error_win32).
    """
    if not os.path.exists(ruta):
        return (False, 0)
    h = kernel32.CreateFileW(
        ruta_larga(ruta), GENERIC_READ | GENERIC_WRITE, 0,
        None, OPEN_EXISTING, FILE_FLAG_BACKUP_SEMANTICS, None,
    )
    if h == INVALID_HANDLE_VALUE:
        return (True, ctypes.get_last_error())
    kernel32.CloseHandle(h)
    return (False, 0)


def crear_hardlink(enlace: str, destino: str) -> None:
    """Crea un enlace duro NTFS. Requiere mismo volumen. Lanza OSError si falla."""
    if not kernel32.CreateHardLinkW(ruta_larga(enlace), ruta_larga(destino), None):
        err = ctypes.get_last_error()
        raise OSError(err, f"CreateHardLinkW fallo (Win32 error {err})", enlace)


def crear_junction(enlace: str, destino: str) -> None:
    """
    Crea un JUNCTION NTFS (reparse point de tipo mount point) sin depender de
    'mklink', evitando problemas de idioma y de parseo de salida de consola.
    """
    destino = os.path.abspath(destino)
    if not os.path.isdir(destino):
        raise NotADirectoryError(f"El destino del junction no es una carpeta: {destino}")
    os.makedirs(enlace, exist_ok=True)

    nombre_sustituto = ("\\??\\" + destino).encode("utf-16-le")
    nombre_impreso = destino.encode("utf-16-le")
    # PathBuffer = sustituto + NUL(2b) + impreso + NUL(2b)
    path_buffer = nombre_sustituto + b"\x00\x00" + nombre_impreso + b"\x00\x00"
    datos = struct.pack(
        "<HHHH",
        0,                              # SubstituteNameOffset
        len(nombre_sustituto),          # SubstituteNameLength
        len(nombre_sustituto) + 2,      # PrintNameOffset
        len(nombre_impreso),            # PrintNameLength
    ) + path_buffer
    buffer = struct.pack("<IHH", IO_REPARSE_TAG_MOUNT_POINT, len(datos), 0) + datos

    h = kernel32.CreateFileW(
        ruta_larga(enlace), GENERIC_READ | GENERIC_WRITE, 0, None, OPEN_EXISTING,
        FILE_FLAG_BACKUP_SEMANTICS | FILE_FLAG_OPEN_REPARSE_POINT, None,
    )
    if h == INVALID_HANDLE_VALUE:
        err = ctypes.get_last_error()
        raise OSError(err, f"No se pudo abrir la carpeta para el junction (error {err})", enlace)
    try:
        devueltos = wintypes.DWORD(0)
        ok = kernel32.DeviceIoControl(
            h, FSCTL_SET_REPARSE_POINT, buffer, len(buffer),
            None, 0, ctypes.byref(devueltos), None,
        )
        if not ok:
            err = ctypes.get_last_error()
            raise OSError(err, f"FSCTL_SET_REPARSE_POINT fallo (error {err})", enlace)
    finally:
        kernel32.CloseHandle(h)


def enumerar_procesos() -> List[Tuple[int, str]]:
    """
    Enumera procesos con Toolhelp32 en lugar de parsear 'tasklist'.
    Motivo: la salida de tasklist esta localizada y su formato cambia.
    """
    resultado: List[Tuple[int, str]] = []
    snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snap == INVALID_HANDLE_VALUE:
        return resultado
    try:
        entrada = PROCESSENTRY32W()
        entrada.dwSize = ctypes.sizeof(PROCESSENTRY32W)
        if not kernel32.Process32FirstW(snap, ctypes.byref(entrada)):
            return resultado
        while True:
            resultado.append((entrada.th32ProcessID, entrada.szExeFile))
            if not kernel32.Process32NextW(snap, ctypes.byref(entrada)):
                break
    finally:
        kernel32.CloseHandle(snap)
    return resultado


def matar_pid(pid: int, espera_ms: int = 5000) -> bool:
    """Termina un proceso por PID y espera a que el kernel lo libere."""
    h = kernel32.OpenProcess(PROCESS_TERMINATE | SYNCHRONIZE, False, pid)
    if not h:
        return False
    try:
        if not kernel32.TerminateProcess(h, 1):
            return False
        kernel32.WaitForSingleObject(h, espera_ms)
        return True
    finally:
        kernel32.CloseHandle(h)


def habilitar_privilegio(nombre: str) -> bool:
    """
    Activa un privilegio en el token del proceso (p.ej. SeDebugPrivilege),
    necesario para terminar procesos de servicios de EA.
    """
    h_token = wintypes.HANDLE()
    if not advapi32.OpenProcessToken(
        kernel32.GetCurrentProcess(),
        TOKEN_ADJUST_PRIVILEGES | TOKEN_QUERY,
        ctypes.byref(h_token),
    ):
        return False
    try:
        luid = LUID()
        if not advapi32.LookupPrivilegeValueW(None, nombre, ctypes.byref(luid)):
            return False
        tp = TOKEN_PRIVILEGES()
        tp.PrivilegeCount = 1
        tp.Privileges[0].Luid = luid
        tp.Privileges[0].Attributes = SE_PRIVILEGE_ENABLED
        if not advapi32.AdjustTokenPrivileges(
            h_token, False, ctypes.byref(tp), 0, None, None
        ):
            return False
        return ctypes.get_last_error() == 0
    finally:
        kernel32.CloseHandle(h_token)


# ==============================================================================
# SECCION 3 - CONSOLA (colores ANSI + UTF-8 para acentos)
# ==============================================================================

class C:
    RESET = "\033[0m"
    NEGRITA = "\033[1m"
    GRIS = "\033[90m"
    ROJO = "\033[91m"
    VERDE = "\033[92m"
    AMBAR = "\033[93m"
    AZUL = "\033[94m"
    CIAN = "\033[96m"


def preparar_consola() -> None:
    """Habilita secuencias VT (colores) y UTF-8 para que los acentos no se rompan."""
    try:
        kernel32.SetConsoleOutputCP(65001)
        kernel32.SetConsoleCP(65001)
    except Exception:
        pass
    try:
        h = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
        modo = wintypes.DWORD()
        if kernel32.GetConsoleMode(h, ctypes.byref(modo)):
            kernel32.SetConsoleMode(h, modo.value | 0x0004)  # ENABLE_VIRTUAL_TERMINAL_PROCESSING
    except Exception:
        pass
    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


_ARCHIVO_LOG: Optional[str] = None

# Ganchos para incrustar el motor en otra interfaz (la GUI de nfs_heat_gui.py).
# Si estan a None el comportamiento es el de siempre: consola y input().
#   _SUMIDERO_LOG(nivel, texto) -> recibe cada linea de log ya sin color
#   _HOOK_CONFIRMAR(pregunta)   -> devuelve True/False en lugar de preguntar por consola
_SUMIDERO_LOG = None
_HOOK_CONFIRMAR = None


def log(mensaje: str, color: str = "", prefijo: str = "") -> None:
    """Imprime en consola con color y persiste una copia sin color en el log."""
    marca = datetime.now().strftime("%H:%M:%S")
    texto = f"{prefijo}{mensaje}" if prefijo else mensaje
    if _SUMIDERO_LOG is not None:
        try:
            _SUMIDERO_LOG(prefijo.strip("[] ").lower(), f"[{marca}] {texto}")
        except Exception:
            pass
    print(f"{C.GRIS}[{marca}]{C.RESET} {color}{texto}{C.RESET}")
    if _ARCHIVO_LOG:
        try:
            with open(_ARCHIVO_LOG, "a", encoding="utf-8") as fh:
                fh.write(f"[{datetime.now().isoformat(timespec='seconds')}] {texto}\n")
        except OSError:
            pass


def ok(m: str) -> None:      log(m, C.VERDE, "[ OK ]  ")
def info(m: str) -> None:    log(m, C.CIAN,  "[INFO]  ")
def aviso(m: str) -> None:   log(m, C.AMBAR, "[AVISO] ")
def error(m: str) -> None:   log(m, C.ROJO,  "[ERROR] ")
def paso(m: str) -> None:    log(m, C.AZUL,  "[PASO]  ")


def titulo(texto: str) -> None:
    linea = "=" * 78
    print(f"\n{C.NEGRITA}{C.AZUL}{linea}\n {texto}\n{linea}{C.RESET}")


def confirmar(pregunta: str) -> bool:
    """
    Pregunta si/no. Respeta ASUMIR_SI (--si) y tolera stdin cerrado (EOF),
    caso habitual al invocar el script desde otro proceso o una tarea programada.
    """
    if _HOOK_CONFIRMAR is not None:
        return bool(_HOOK_CONFIRMAR(pregunta))
    if ASUMIR_SI:
        info(f"{pregunta} -> SI (asumido por --si)")
        return True
    try:
        return input(f"   {C.NEGRITA}{pregunta} (s/n): {C.RESET}").strip().lower() in ("s", "si", "y", "yes")
    except EOFError:
        aviso("Sin entrada interactiva disponible; se asume NO. Usa --si para confirmar.")
        return False


# ==============================================================================
# SECCION 4 - ELEVACION DE PRIVILEGIOS (UAC)
# ==============================================================================

def es_administrador() -> bool:
    """Comprueba si el proceso actual tiene token de administrador."""
    try:
        return bool(shell32.IsUserAnAdmin())
    except Exception:
        return False


def reejecutar_elevado() -> None:
    """
    Relanza este mismo script solicitando elevacion UAC y termina el proceso
    actual. Los argumentos originales se conservan.
    """
    parametros = " ".join(f'"{a}"' for a in [os.path.abspath(sys.argv[0])] + sys.argv[1:])
    aviso("Se requieren privilegios de Administrador. Solicitando elevacion (UAC)...")
    try:
        rc = shell32.ShellExecuteW(None, "runas", sys.executable, parametros, None, 1)
    except Exception as exc:
        error(f"No se pudo invocar ShellExecuteW: {exc}")
        sys.exit(1)
    if rc <= 32:
        error(f"Elevacion rechazada o fallida (codigo {rc}).")
        error("Ejecuta el script manualmente desde una consola como Administrador.")
        sys.exit(1)
    sys.exit(0)


# ==============================================================================
# SECCION 5 - UTILIDADES DE ARCHIVO
# ==============================================================================

def sha256(ruta: str) -> str:
    """Hash SHA-256 por bloques (soporta archivos de varios GB sin cargar en RAM)."""
    h = hashlib.sha256()
    with open(ruta_larga(ruta), "rb") as fh:
        while True:
            bloque = fh.read(TAMANO_BLOQUE_HASH)
            if not bloque:
                break
            h.update(bloque)
    return h.hexdigest()


def tamano_legible(n: int) -> str:
    for unidad in ("B", "KB", "MB", "GB"):
        if n < 1024 or unidad == "GB":
            return f"{n:.1f} {unidad}" if unidad != "B" else f"{n} B"
        n /= 1024.0
    return f"{n:.1f} GB"


def copiar_verificado(origen: str, destino: str) -> str:
    """
    Copia un archivo y VERIFICA por hash que el destino sea identico.
    Devuelve el hash. Si la verificacion falla, borra el destino y lanza IOError.
    """
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    hash_origen = sha256(origen)
    with open(ruta_larga(origen), "rb") as fo, open(ruta_larga(destino), "wb") as fd:
        while True:
            bloque = fo.read(TAMANO_BLOQUE_HASH)
            if not bloque:
                break
            fd.write(bloque)
        fd.flush()
        os.fsync(fd.fileno())
    hash_destino = sha256(destino)
    if hash_origen != hash_destino:
        try:
            os.remove(ruta_larga(destino))
        except OSError:
            pass
        raise IOError(f"Verificacion de copia fallida: {origen} -> {destino}")
    return hash_destino


def borrar_seguro(ruta: str) -> None:
    """
    Borra un archivo o un enlace de carpeta. NUNCA usa rmtree sobre un reparse
    point (eso borraria el contenido real apuntado por el enlace).
    """
    if not os.path.lexists(ruta_larga(ruta)) and not os.path.lexists(ruta):
        return
    quitar_solo_lectura(ruta)
    attr = obtener_atributos(ruta)
    es_dir = attr != INVALID_FILE_ATTRIBUTES and bool(attr & FILE_ATTRIBUTE_DIRECTORY)
    if es_dir:
        os.rmdir(ruta_larga(ruta))  # valido para junctions y symlinks de carpeta
    else:
        os.remove(ruta_larga(ruta))


def esperar_desbloqueo(ruta: str, segundos: int = TIEMPO_ESPERA_DESBLOQUEO) -> bool:
    """
    Espera activamente (con backoff) hasta que el archivo pueda abrirse en modo
    exclusivo. Devuelve False si se agota el tiempo.
    """
    limite = time.time() + segundos
    intervalo = 0.25
    primer_aviso = True
    while time.time() < limite:
        bloqueado, cod = estado_bloqueo(ruta)
        if not bloqueado:
            return True
        if primer_aviso:
            nombre = os.path.basename(ruta)
            aviso(f"'{nombre}' esta bloqueado (Win32 error {cod}). Esperando liberacion...")
            primer_aviso = False
        time.sleep(intervalo)
        intervalo = min(intervalo * 1.5, 2.0)
    return False


def diagnosticar_bloqueo(ruta: str) -> List[str]:
    """
    Intenta identificar QUE procesos tienen abierto el archivo.
    Usa psutil si esta disponible; si no, informa que no puede determinarlo.
    """
    try:
        import psutil  # type: ignore
    except ImportError:
        return []
    objetivo = os.path.normcase(os.path.abspath(ruta))
    culpables: List[str] = []
    for proc in psutil.process_iter(["pid", "name"]):
        try:
            for abierto in proc.open_files():
                if os.path.normcase(abierto.path) == objetivo:
                    culpables.append(f"{proc.info['name']} (PID {proc.info['pid']})")
                    break
        except (psutil.AccessDenied, psutil.NoSuchProcess, OSError):
            continue
    return culpables


# ==============================================================================
# SECCION 5.5 - AUTODETECCION DE RUTAS Y ESTADO DE LA CACHE DE FROSTY
# ==============================================================================
#
# El objetivo es que el script funcione recien clonado, sin editar constantes.
# Y sobre todo: detectar que la cache de Frosty quedo OBSOLETA respecto a los
# datos del juego. Esa es la causa mas dificil de diagnosticar de todas, porque
# el sintoma es un crash que parece culpa del mod.

CARPETAS_FROSTY = ["FrostyModManager", "Frosty Mod Manager", "Frosty"]


def _valor_registro(hive_nombre: str, clave: str, valor: str) -> Optional[str]:
    """Lee un valor del registro devolviendo None en vez de lanzar."""
    try:
        import winreg
    except ImportError:
        return None
    hives = {"HKCU": winreg.HKEY_CURRENT_USER, "HKLM": winreg.HKEY_LOCAL_MACHINE}
    try:
        with winreg.OpenKey(hives[hive_nombre], clave) as k:
            dato = winreg.QueryValueEx(k, valor)[0]
        return str(dato) if dato else None
    except (OSError, KeyError):
        return None


def _juego_por_registro_desinstalacion() -> Optional[str]:
    """
    Busca el juego en las claves de desinstalacion de Windows.
    Es la via mas fiable porque cubre tanto la version de Steam como la de EA App.
    """
    try:
        import winreg
    except ImportError:
        return None
    ramas = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
    ]
    for hive, rama in ramas:
        try:
            with winreg.OpenKey(hive, rama) as raiz:
                for i in range(winreg.QueryInfoKey(raiz)[0]):
                    try:
                        sub = winreg.EnumKey(raiz, i)
                        with winreg.OpenKey(raiz, sub) as k:
                            nombre = str(winreg.QueryValueEx(k, "DisplayName")[0])
                            if "need for speed" not in nombre.lower() or "heat" not in nombre.lower():
                                continue
                            ruta = str(winreg.QueryValueEx(k, "InstallLocation")[0])
                            if ruta and os.path.isdir(ruta):
                                return os.path.normpath(ruta)
                    except OSError:
                        continue
        except OSError:
            continue
    return None


def _bibliotecas_steam() -> List[str]:
    """Devuelve las rutas de todas las bibliotecas de Steam segun libraryfolders.vdf."""
    base = (_valor_registro("HKCU", r"Software\Valve\Steam", "SteamPath")
            or _valor_registro("HKLM", r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath"))
    if not base:
        return []
    base = os.path.normpath(base.replace("/", "\\"))
    vdf = os.path.join(base, "steamapps", "libraryfolders.vdf")
    rutas = [base]
    try:
        with open(vdf, "r", encoding="utf-8", errors="replace") as fh:
            contenido = fh.read()
        # Las rutas vienen escapadas al estilo C: "E:\\SteamLibrary"
        for encontrada in re.findall(r'"path"\s+"([^"]+)"', contenido):
            rutas.append(os.path.normpath(encontrada.replace("\\\\", "\\")))
    except OSError:
        pass
    # Deduplicado insensible a mayusculas: el registro devuelve 'd:/steam' y el
    # vdf 'D:\Steam', que en Windows son la misma carpeta.
    unicas: Dict[str, str] = {}
    for r in rutas:
        if os.path.isdir(r):
            unicas.setdefault(os.path.normcase(r), r)
    return list(unicas.values())


def _juego_por_steam() -> Optional[str]:
    """Localiza el juego recorriendo las bibliotecas de Steam y su appmanifest."""
    for biblioteca in _bibliotecas_steam():
        manifiesto = os.path.join(biblioteca, "steamapps", f"appmanifest_{STEAM_APPID}.acf")
        if not os.path.isfile(manifiesto):
            continue
        try:
            with open(manifiesto, "r", encoding="utf-8", errors="replace") as fh:
                contenido = fh.read()
        except OSError:
            continue
        m = re.search(r'"installdir"\s+"([^"]+)"', contenido)
        if not m:
            continue
        ruta = os.path.join(biblioteca, "steamapps", "common", m.group(1))
        if os.path.isdir(ruta):
            return os.path.normpath(ruta)
    return None


def _unidades_fijas() -> List[str]:
    """Letras de unidad existentes, para los escaneos de ultimo recurso."""
    return [f"{c}:\\" for c in "CDEFGHIJKLMNOPQRSTUVWXYZ" if os.path.isdir(f"{c}:\\")]


def localizar_juego(preferida: Optional[str] = None) -> Optional[str]:
    """
    Encuentra la carpeta del juego. Orden: ruta indicada -> registro de
    desinstalacion -> bibliotecas de Steam -> escaneo de unidades.
    """
    if preferida and os.path.isdir(preferida):
        return os.path.normpath(preferida)
    for buscador in (_juego_por_registro_desinstalacion, _juego_por_steam):
        ruta = buscador()
        if ruta and os.path.isfile(os.path.join(ruta, EJECUTABLE_JUEGO)):
            return ruta
        if ruta:
            return ruta
    for unidad in _unidades_fijas():
        candidata = os.path.join(unidad, "SteamLibrary", "steamapps", "common", "Need for Speed Heat")
        if os.path.isdir(candidata):
            return candidata
    return None


def localizar_frosty(raiz_juego: Optional[str] = None) -> Optional[str]:
    """
    Encuentra la carpeta de Frosty Mod Manager. No se registra en el registro,
    asi que se busca por nombre en los sitios habituales: la unidad del juego
    primero (la gente suele instalarlo junto a los juegos), luego el resto.
    """
    candidatas: List[str] = []
    if raiz_juego:
        unidad_juego = os.path.splitdrive(raiz_juego)[0] + "\\"
        candidatas += [os.path.join(unidad_juego, n) for n in CARPETAS_FROSTY]
    for unidad in _unidades_fijas():
        candidatas += [os.path.join(unidad, n) for n in CARPETAS_FROSTY]
    for base in (os.environ.get("ProgramFiles", ""), os.environ.get("ProgramFiles(x86)", ""),
                 os.environ.get("LOCALAPPDATA", ""), os.path.expanduser("~\\Desktop")):
        if base:
            candidatas += [os.path.join(base, n) for n in CARPETAS_FROSTY]

    for c in dict.fromkeys(candidatas):
        if os.path.isfile(os.path.join(c, "FrostyModManager.exe")):
            return os.path.normpath(c)

    # Ultimo recurso: un nivel de profundidad en cada unidad
    for unidad in _unidades_fijas():
        try:
            for entrada in os.scandir(unidad):
                if not entrada.is_dir(follow_symlinks=False):
                    continue
                if "frosty" not in entrada.name.lower():
                    continue
                if os.path.isfile(os.path.join(entrada.path, "FrostyModManager.exe")):
                    return os.path.normpath(entrada.path)
        except OSError:
            continue
    return None


def ruta_cache_frosty(dir_frosty: str) -> Optional[str]:
    """Devuelve la ruta del archivo de cache de NFS Heat, exista o no."""
    if not dir_frosty:
        return None
    return os.path.join(dir_frosty, "Caches", "NFSHEAT.cache")


def fecha_datos_juego(raiz_juego: str) -> float:
    """
    Marca de tiempo del archivo mas reciente en Data\\ y Patch\\, sin seguir
    enlaces. Representa "cuando cambiaron por ultima vez los datos del juego".
    """
    ultima = 0.0
    for sub in ("Data", "Patch"):
        base = os.path.join(raiz_juego, sub)
        if not os.path.isdir(base):
            continue
        for actual, dirs, archivos in os.walk(base):
            dirs[:] = [d for d in dirs if not es_reparse_point(os.path.join(actual, d))]
            for nombre in archivos:
                try:
                    ultima = max(ultima, os.path.getmtime(os.path.join(actual, nombre)))
                except OSError:
                    continue
    return ultima


def estado_cache_frosty(dir_frosty: Optional[str], raiz_juego: str) -> Dict:
    """
    Decide si la cache de Frosty esta obsoleta comparandola con los datos del
    juego. Si el juego se actualizo o se reparo despues de que Frosty indexara,
    los mods compilados referenciaran assets que ya no encajan.
    """
    resultado: Dict = {"frosty": dir_frosty, "ruta": None, "existe": False,
                       "fecha_cache": None, "fecha_datos": None, "obsoleta": False}
    ruta = ruta_cache_frosty(dir_frosty) if dir_frosty else None
    resultado["ruta"] = ruta
    if not ruta or not os.path.isfile(ruta):
        return resultado
    resultado["existe"] = True
    try:
        resultado["fecha_cache"] = os.path.getmtime(ruta)
    except OSError:
        return resultado
    resultado["fecha_datos"] = fecha_datos_juego(raiz_juego)
    # Margen de 60s para no marcar obsoleta por diferencias de reloj o de FS.
    resultado["obsoleta"] = resultado["fecha_datos"] > resultado["fecha_cache"] + 60
    return resultado


def invalidar_cache_frosty(dir_frosty: str) -> Optional[str]:
    """
    Renombra la cache en vez de borrarla, para que la operacion sea reversible.
    Devuelve la ruta del respaldo, o None si no habia cache.
    """
    ruta = ruta_cache_frosty(dir_frosty)
    if not ruta or not os.path.isfile(ruta):
        aviso("No hay cache de Frosty que invalidar.")
        return None
    marca = datetime.now().strftime("%Y%m%d_%H%M%S")
    destino = f"{ruta}.bak_{marca}"
    try:
        quitar_solo_lectura(ruta)
        os.replace(ruta, destino)
    except OSError as exc:
        error(f"No se pudo renombrar la cache: {exc}")
        return None
    ok(f"Cache renombrada -> {os.path.basename(destino)}")
    info("Al abrir Frosty reconstruira el indice. Tarda varios minutos.")
    return destino


# ==============================================================================
# SECCION 6 - LIBERADOR: cierre de procesos, servicios y toma de propiedad
# ==============================================================================

class Liberador:
    """Responsable de dejar los archivos del juego libres y escribibles."""

    def __init__(self, raiz_juego: str):
        self.raiz = raiz_juego

    # -- Procesos --------------------------------------------------------------
    def cerrar_steam_ordenadamente(self) -> None:
        """Pide a Steam que se cierre solo (evita corromper su estado)."""
        exe = self._localizar_steam()
        if not exe:
            return
        if not any(n.lower() == "steam.exe" for _p, n in enumerar_procesos()):
            return
        try:
            info(f"Solicitando cierre ordenado de Steam: {exe}")
            subprocess.run([exe, "-shutdown"], timeout=10,
                           creationflags=0x08000000, check=False)
        except (subprocess.SubprocessError, OSError) as exc:
            aviso(f"No se pudo invocar el cierre de Steam: {exc}")
            return

        # Espera activa a que Steam termine por si mismo. Un TerminateProcess
        # brusco sobre Steam puede corromper una descarga o actualizacion en
        # curso, asi que se le concede tiempo real en vez de un sleep fijo.
        limite = time.time() + 25
        while time.time() < limite:
            if not any(n.lower() == "steam.exe" for _p, n in enumerar_procesos()):
                ok("Steam se cerro ordenadamente.")
                return
            time.sleep(1)
        aviso("Steam sigue activo tras 25s; se forzara su terminacion.")

    def _localizar_steam(self) -> Optional[str]:
        """Busca steam.exe en el registro y en rutas habituales."""
        try:
            import winreg
            for hive, clave in (
                (winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam"),
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam"),
            ):
                try:
                    with winreg.OpenKey(hive, clave) as k:
                        for valor in ("SteamExe", "InstallPath"):
                            try:
                                dato = winreg.QueryValueEx(k, valor)[0]
                            except OSError:
                                continue
                            ruta = dato if dato.lower().endswith(".exe") \
                                else os.path.join(dato, "steam.exe")
                            if os.path.isfile(ruta):
                                return ruta
                except OSError:
                    continue
        except ImportError:
            pass
        for candidata in (
            r"C:\Program Files (x86)\Steam\steam.exe",
            r"C:\Program Files\Steam\steam.exe",
        ):
            if os.path.isfile(candidata):
                return candidata
        return None

    def terminar_procesos(self, incluir_steam: bool = True) -> int:
        """Termina todos los procesos configurados. Devuelve cuantos mato."""
        paso("Terminando procesos que retienen handles sobre el juego...")
        habilitar_privilegio("SeDebugPrivilege")

        objetivos = {p.lower() for p in PROCESOS_A_CERRAR}
        if not incluir_steam:
            objetivos -= {"steam.exe", "steamwebhelper.exe"}
        else:
            self.cerrar_steam_ordenadamente()

        muertos = 0
        for pid, nombre in enumerar_procesos():
            if nombre.lower() not in objetivos:
                continue
            if pid == os.getpid():
                continue
            if matar_pid(pid):
                muertos += 1
                info(f"  terminado: {nombre} (PID {pid})")
            else:
                aviso(f"  no se pudo terminar: {nombre} (PID {pid})")
        if muertos:
            ok(f"{muertos} proceso(s) terminado(s). Esperando liberacion del kernel...")
            time.sleep(2)
        else:
            ok("No habia procesos conflictivos en ejecucion.")
        return muertos

    # -- Servicios -------------------------------------------------------------
    def detener_servicios(self) -> None:
        """
        Detiene los servicios de EA/Steam. Se apoya en sc.exe pero evalua el
        CODIGO DE SALIDA, no el texto (que esta localizado).
          1060 = el servicio no existe
          1062 = el servicio no estaba iniciado
        """
        paso("Deteniendo servicios en segundo plano (EA / Steam)...")
        for servicio in SERVICIOS_A_DETENER:
            try:
                r = subprocess.run(
                    ["sc.exe", "stop", servicio],
                    capture_output=True, timeout=20,
                    creationflags=0x08000000, check=False,
                )
                if r.returncode == 0:
                    info(f"  detenido: {servicio}")
                elif r.returncode in (1060, 1062):
                    pass  # inexistente o ya detenido: no es un problema
                else:
                    aviso(f"  '{servicio}' devolvio codigo {r.returncode}")
            except (subprocess.SubprocessError, OSError) as exc:
                aviso(f"  no se pudo detener '{servicio}': {exc}")
        time.sleep(1)
        ok("Servicios procesados.")

    # -- Atributos y ACL -------------------------------------------------------
    def limpiar_atributos(self, rutas: List[str]) -> None:
        """Quita Solo-Lectura de una lista concreta de rutas."""
        cambiados = 0
        for r in rutas:
            if os.path.exists(r) and quitar_solo_lectura(r):
                cambiados += 1
        ok(f"Atributos de solo-lectura normalizados en {cambiados} ruta(s).")

    def limpiar_atributos_recursivo(self, carpeta: str) -> None:
        """
        Quita Solo-Lectura de forma recursiva SIN entrar en reparse points.
        Se usa solo bajo demanda: en un juego de decenas de GB es costoso.
        """
        paso(f"Normalizando atributos en: {carpeta}")
        contador = 0
        for actual, dirs, archivos in os.walk(carpeta):
            dirs[:] = [d for d in dirs if not es_reparse_point(os.path.join(actual, d))]
            for nombre in archivos:
                if quitar_solo_lectura(os.path.join(actual, nombre)):
                    contador += 1
        ok(f"{contador} archivo(s) normalizado(s).")

    def tomar_propiedad(self, rutas: List[str]) -> None:
        """
        takeown + icacls sobre rutas concretas.

        Se usa el SID '*S-1-1-0' (Todos/Everyone) en lugar del nombre textual,
        porque el nombre del grupo esta traducido segun el idioma de Windows y
        'Todos' fallaria en un sistema en ingles (y viceversa).
        """
        paso("Tomando propiedad y concediendo permisos completos...")
        procesadas = 0
        for r in rutas:
            if not os.path.exists(r):
                continue
            try:
                # /A asigna la propiedad al grupo Administradores (mas robusto que al usuario)
                subprocess.run(["takeown.exe", "/F", r, "/A"],
                               capture_output=True, timeout=30,
                               creationflags=0x08000000, check=False)
                subprocess.run(["icacls.exe", r, "/grant", "*S-1-1-0:(F)", "/C", "/Q"],
                               capture_output=True, timeout=30,
                               creationflags=0x08000000, check=False)
                procesadas += 1
            except (subprocess.SubprocessError, OSError) as exc:
                aviso(f"  fallo takeown/icacls en '{r}': {exc}")
        ok(f"Permisos aplicados sobre {procesadas} ruta(s).")

    def tomar_propiedad_recursiva(self, carpeta: str) -> None:
        """
        Version recursiva para carpetas completas. takeown /D requiere la letra
        de confirmacion LOCALIZADA ('Y' en ingles, 'S' en espanol): se intentan
        ambas para ser independiente del idioma del sistema.
        """
        paso(f"Tomando propiedad recursiva de: {carpeta}")
        exito = False
        for letra in ("Y", "S"):
            try:
                r = subprocess.run(
                    ["takeown.exe", "/F", carpeta, "/R", "/A", "/D", letra],
                    capture_output=True, timeout=600,
                    creationflags=0x08000000, check=False,
                )
                if r.returncode == 0:
                    exito = True
                    break
            except (subprocess.SubprocessError, OSError):
                continue
        if not exito:
            aviso("takeown recursivo no confirmo exito; se continua igualmente.")
        try:
            subprocess.run(
                ["icacls.exe", carpeta, "/grant", "*S-1-1-0:(OI)(CI)F", "/T", "/C", "/Q"],
                capture_output=True, timeout=600,
                creationflags=0x08000000, check=False,
            )
        except (subprocess.SubprocessError, OSError) as exc:
            aviso(f"icacls recursivo fallo: {exc}")
        ok("Propiedad y ACL recursivas aplicadas.")

    # -- Windows Defender ------------------------------------------------------
    def estado_defender(self) -> Dict[str, str]:
        """Consulta si el Acceso Controlado a Carpetas puede estar bloqueando."""
        consulta = (
            "$p = Get-MpPreference; "
            "\"CFA=$($p.EnableControlledFolderAccess)\"; "
            "\"RT=$((Get-MpComputerStatus).RealTimeProtectionEnabled)\"; "
            "\"EXCL=$($p.ExclusionPath -join '|')\""
        )
        try:
            r = subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", consulta],
                capture_output=True, text=True, timeout=60,
                creationflags=0x08000000, check=False,
            )
            datos: Dict[str, str] = {}
            for linea in (r.stdout or "").splitlines():
                if "=" in linea:
                    k, _, v = linea.partition("=")
                    datos[k.strip()] = v.strip()
            return datos
        except (subprocess.SubprocessError, OSError):
            return {}

    def anadir_exclusion_defender(self) -> bool:
        """
        Anade la carpeta del juego a las exclusiones de Windows Defender.
        ACCION EXPLICITA DEL USUARIO: reduce la proteccion sobre esa ruta.
        """
        comando = (
            f"Add-MpPreference -ExclusionPath '{self.raiz}' -ErrorAction Stop; "
            f"Add-MpPreference -ExclusionProcess '{EJECUTABLE_JUEGO}' -ErrorAction Stop"
        )
        try:
            r = subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", comando],
                capture_output=True, text=True, timeout=90,
                creationflags=0x08000000, check=False,
            )
            if r.returncode == 0:
                ok(f"Exclusion de Defender anadida para: {self.raiz}")
                return True
            error(f"Defender rechazo la exclusion: {(r.stderr or '').strip()[:300]}")
            return False
        except (subprocess.SubprocessError, OSError) as exc:
            error(f"No se pudo contactar con Defender: {exc}")
            return False

    # -- Secuencia completa ----------------------------------------------------
    def preparar_para_escritura(self, rutas_objetivo: List[str]) -> None:
        """Secuencia completa de liberacion, acotada a las rutas que se tocaran."""
        titulo("FASE 1 - LIBERACION DE ARCHIVOS")
        self.terminar_procesos(incluir_steam=True)
        self.detener_servicios()
        self.limpiar_atributos(rutas_objetivo)
        self.tomar_propiedad(rutas_objetivo)

        estado = self.estado_defender()
        if estado.get("CFA") in ("1", "2", "True"):
            aviso("El Acceso Controlado a Carpetas de Defender esta ACTIVO.")
            aviso("Si la inyeccion falla con acceso denegado, usa la opcion [6] del menu.")


# ==============================================================================
# SECCION 7 - MANIFIESTO DE ESTADO (persistencia transaccional)
# ==============================================================================

class Manifiesto:
    """
    Registra en JSON cada operacion realizada para que la restauracion sea
    exacta e idempotente. Sin esto, una segunda inyeccion sobrescribiria los
    backups vanilla con archivos ya modificados (bug clasico e irreversible).
    """

    VERSION = 2

    def __init__(self, ruta: str):
        self.ruta = ruta
        self.datos: Dict = {
            "version": self.VERSION,
            "estado": "vanilla",          # vanilla | inyectado
            "perfil": PERFIL_FROSTY,
            "fecha_inyeccion": None,
            "modo": MODO_INYECCION,
            "entradas": [],               # lista de operaciones
        }
        self.cargar()

    def cargar(self) -> None:
        if not os.path.isfile(self.ruta):
            return
        try:
            with open(self.ruta, "r", encoding="utf-8") as fh:
                cargado = json.load(fh)
            if isinstance(cargado, dict) and "entradas" in cargado:
                self.datos = cargado
        except (OSError, json.JSONDecodeError) as exc:
            aviso(f"Manifiesto ilegible ({exc}). Se parte de estado limpio.")

    def guardar(self) -> None:
        os.makedirs(os.path.dirname(self.ruta), exist_ok=True)
        temporal = self.ruta + ".tmp"
        with open(temporal, "w", encoding="utf-8") as fh:
            json.dump(self.datos, fh, indent=2, ensure_ascii=False)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(temporal, self.ruta)   # escritura atomica

    @property
    def inyectado(self) -> bool:
        return self.datos.get("estado") == "inyectado"

    def registrar(self, entrada: Dict) -> None:
        self.datos["entradas"].append(entrada)

    def marcar_inyectado(self) -> None:
        self.datos["estado"] = "inyectado"
        self.datos["fecha_inyeccion"] = datetime.now().isoformat(timespec="seconds")
        self.datos["modo"] = MODO_INYECCION
        self.guardar()

    def marcar_vanilla(self) -> None:
        self.datos["estado"] = "vanilla"
        self.datos["fecha_inyeccion"] = None
        self.datos["entradas"] = []
        self.guardar()


# ==============================================================================
# SECCION 8 - ESCANER: construccion del plan de inyeccion
# ==============================================================================

# Clasificacion de cada archivo encontrado en ModData
NUEVO = "nuevo"              # no existe en el juego -> crear y borrar al restaurar
REEMPLAZAR = "reemplazar"    # existe y difiere -> backup + sustituir
YA_INYECTADO = "ya_inyectado"
MISMO_FISICO = "mismo_fisico"  # symlink/hardlink de Frosty al archivo vanilla


class Escaner:
    """Recorre ModData\\<perfil> y decide que hacer con cada archivo."""

    def __init__(self, raiz_juego: str, raiz_mods: str):
        self.raiz_juego = raiz_juego
        self.raiz_mods = raiz_mods
        self.enlaces_omitidos = 0
        self.dirs_enlace_omitidos: List[str] = []

    def _recorrer(self, carpeta: str) -> Iterator[str]:
        """
        Recorrido en profundidad que NUNCA desciende en un reparse point.
        Esta es la salvaguarda central del script.
        """
        pila = [carpeta]
        while pila:
            actual = pila.pop()
            try:
                entradas = list(os.scandir(actual))
            except OSError as exc:
                aviso(f"No se pudo leer '{actual}': {exc}")
                continue
            for e in entradas:
                if e.name in CARPETAS_INTERNAS:
                    continue
                if es_reparse_point(e.path):
                    # Enlace de Frosty a contenido vanilla: se ignora por completo.
                    self.enlaces_omitidos += 1
                    if e.is_dir(follow_symlinks=False):
                        self.dirs_enlace_omitidos.append(e.path)
                    continue
                if e.is_dir(follow_symlinks=False):
                    pila.append(e.path)
                else:
                    yield e.path

    def construir_plan(self) -> List[Dict]:
        """Devuelve la lista de operaciones a ejecutar, ya clasificadas."""
        plan: List[Dict] = []
        for origen in self._recorrer(self.raiz_mods):
            rel = os.path.relpath(origen, self.raiz_mods)
            destino = os.path.join(self.raiz_juego, rel)

            item: Dict = {
                "rel": rel,
                "origen": origen,
                "destino": destino,
                "tamano": os.path.getsize(origen),
            }

            if not os.path.exists(destino):
                item["accion"] = NUEVO
                plan.append(item)
                continue

            # Deteccion de identidad fisica: cubre hardlinks y symlinks resueltos.
            id_origen = identidad_archivo(origen)
            id_destino = identidad_archivo(destino)
            if id_origen is not None and id_origen == id_destino:
                item["accion"] = MISMO_FISICO
                plan.append(item)
                continue

            try:
                h_origen = sha256(origen)
                h_destino = sha256(destino)
            except OSError as exc:
                aviso(f"No se pudo hashear '{rel}': {exc}. Se tratara como reemplazo.")
                item["accion"] = REEMPLAZAR
                plan.append(item)
                continue

            item["hash_mod"] = h_origen
            item["hash_juego"] = h_destino
            item["accion"] = YA_INYECTADO if h_origen == h_destino else REEMPLAZAR
            plan.append(item)

        plan.sort(key=lambda x: x["rel"].lower())
        return plan


# ==============================================================================
# SECCION 9 - MOTOR DE INYECCION (transaccional, con rollback)
# ==============================================================================

class MotorInyeccion:
    def __init__(self, raiz_juego: str, perfil: str = PERFIL_FROSTY):
        self.raiz_juego = os.path.abspath(raiz_juego)
        self.raiz_moddata = os.path.join(self.raiz_juego, "ModData")
        self.raiz_perfil = os.path.join(self.raiz_moddata, perfil)
        self.dir_estado = os.path.join(self.raiz_moddata, "_InjectorState")
        self.dir_backup = os.path.join(self.raiz_moddata, "_VanillaBackup")
        self.manifiesto = Manifiesto(os.path.join(self.dir_estado, "manifiesto.json"))
        self.liberador = Liberador(self.raiz_juego)
        self.dir_frosty = localizar_frosty(self.raiz_juego)

    def revisar_cache_frosty(self) -> Dict:
        """
        Comprueba si la cache de Frosty quedo obsoleta y avisa. Un indice
        construido antes de la ultima actualizacion o reparacion del juego
        produce mods que crashean con un desreferenciado nulo.
        """
        est = estado_cache_frosty(self.dir_frosty, self.raiz_juego)
        if not est["existe"]:
            return est
        if est["obsoleta"]:
            f_cache = datetime.fromtimestamp(est["fecha_cache"]).strftime("%d-%m-%Y %H:%M")
            f_datos = datetime.fromtimestamp(est["fecha_datos"]).strftime("%d-%m-%Y %H:%M")
            aviso("La cache de Frosty es ANTERIOR a los datos del juego:")
            aviso(f"   cache indexada : {f_cache}")
            aviso(f"   datos del juego: {f_datos}")
            aviso("Los mods compilados con este indice pueden crashear el juego.")
            aviso("Invalidala con la opcion [9] del menu o --invalidar-cache.")
        return est

    # -- Validaciones ----------------------------------------------------------
    def validar_entorno(self) -> bool:
        if not os.path.isdir(self.raiz_juego):
            error(f"No existe la carpeta del juego: {self.raiz_juego}")
            return False
        if not os.path.isfile(os.path.join(self.raiz_juego, EJECUTABLE_JUEGO)):
            aviso(f"No se encontro {EJECUTABLE_JUEGO} en la raiz del juego.")
        if not os.path.isdir(self.raiz_perfil):
            error(f"No existe el perfil de Frosty: {self.raiz_perfil}")
            error("Compila los mods con Frosty Mod Manager antes de inyectar.")
            return False
        return True

    def _ruta_backup(self, rel: str) -> str:
        """Ubicacion del respaldo .bak, replicando la estructura de carpetas."""
        return os.path.join(self.dir_backup, rel + ".bak")

    # -- Inyeccion -------------------------------------------------------------
    def inyectar(self, forzar: bool = False) -> bool:
        titulo("MOTOR DE INYECCION ATOMIZADA")

        if not self.validar_entorno():
            return False

        # Aviso temprano: una cache obsoleta produce mods que crashean, y el
        # sintoma parece culpa del mod. Mejor decirlo antes de tocar archivos.
        self.revisar_cache_frosty()

        if self.manifiesto.inyectado and not forzar:
            aviso("El manifiesto indica que los mods YA estan inyectados.")
            aviso(f"Inyectado el: {self.manifiesto.datos.get('fecha_inyeccion')}")
            aviso("Restaura primero con la opcion [2] para evitar corromper los backups.")
            return False

        # --- Analisis previo (sin tocar nada) ---
        paso("Analizando ModData (sin seguir enlaces simbolicos)...")
        escaner = Escaner(self.raiz_juego, self.raiz_perfil)
        plan = escaner.construir_plan()

        if escaner.dirs_enlace_omitidos:
            for d in escaner.dirs_enlace_omitidos:
                info(f"  carpeta-enlace omitida (contenido vanilla): {os.path.basename(d)}")

        trabajo = [p for p in plan if p["accion"] in (NUEVO, REEMPLAZAR)]
        ya = [p for p in plan if p["accion"] == YA_INYECTADO]
        fisicos = [p for p in plan if p["accion"] == MISMO_FISICO]

        ok(f"Enlaces simbolicos omitidos : {escaner.enlaces_omitidos}")
        ok(f"Archivos ya inyectados      : {len(ya)}")
        ok(f"Archivos identicos (inodo)  : {len(fisicos)}")
        ok(f"Archivos a inyectar         : {len(trabajo)}")

        if not trabajo:
            ok("No hay nada que hacer: el juego ya tiene el payload aplicado.")
            if not self.manifiesto.inyectado:
                self.manifiesto.marcar_inyectado()
            return True

        total = sum(p["tamano"] for p in trabajo)
        print()
        for p in trabajo:
            etiqueta = "NUEVO     " if p["accion"] == NUEVO else "REEMPLAZAR"
            print(f"   {C.AMBAR}{etiqueta}{C.RESET} {tamano_legible(p['tamano']):>10}  {p['rel']}")
        print(f"\n   {C.NEGRITA}Total a escribir: {tamano_legible(total)}{C.RESET}\n")

        # --- Liberacion acotada a los archivos implicados ---
        rutas = [p["destino"] for p in trabajo] + [p["origen"] for p in trabajo]
        self.liberador.preparar_para_escritura(rutas)

        # --- Ejecucion transaccional ---
        titulo("FASE 2 - INYECCION")
        completadas: List[Dict] = []
        try:
            for indice, p in enumerate(trabajo, 1):
                self._inyectar_uno(p, indice, len(trabajo))
                completadas.append(p)
                self.manifiesto.registrar({
                    "rel": p["rel"],
                    "accion": p["accion"],
                    "backup": p.get("backup"),
                    "hash_vanilla": p.get("hash_vanilla"),
                    "hash_mod": p.get("hash_mod"),
                    "modo": MODO_INYECCION,
                })
                self.manifiesto.guardar()   # persistencia incremental

            self.manifiesto.marcar_inyectado()
            ok(f"Inyeccion completada: {len(completadas)} archivo(s).")
            return True

        except Exception as exc:
            error(f"FALLO durante la inyeccion: {exc}")
            error("Iniciando ROLLBACK automatico para no dejar el juego a medias...")
            self._rollback(completadas)
            error("Rollback finalizado. El juego ha quedado como estaba antes.")
            log(traceback.format_exc(), C.GRIS)
            return False

    def _inyectar_uno(self, p: Dict, indice: int, total: int) -> None:
        """Inyecta un unico archivo: backup verificado + sustitucion."""
        rel, origen, destino = p["rel"], p["origen"], p["destino"]
        print(f"   {C.CIAN}[{indice}/{total}]{C.RESET} {rel}")

        # 1) Backup por COPIA (nunca por movimiento: si falla, el juego sigue intacto)
        if p["accion"] == REEMPLAZAR:
            backup = self._ruta_backup(rel)
            if os.path.exists(backup):
                # Ya hay un backup previo: se conserva el ORIGINAL, no se pisa.
                info(f"      backup preexistente conservado: {os.path.basename(backup)}")
                p["backup"] = backup
                p["hash_vanilla"] = sha256(backup)
            else:
                if not esperar_desbloqueo(destino):
                    culpables = diagnosticar_bloqueo(destino)
                    detalle = f" Procesos: {', '.join(culpables)}" if culpables else ""
                    raise PermissionError(
                        f"'{rel}' sigue bloqueado tras {TIEMPO_ESPERA_DESBLOQUEO}s.{detalle}"
                    )
                p["hash_vanilla"] = copiar_verificado(destino, backup)
                p["backup"] = backup
                info(f"      backup verificado -> {os.path.relpath(backup, self.raiz_juego)}")

        # 2) Sustitucion
        quitar_solo_lectura(destino)
        if not esperar_desbloqueo(destino):
            culpables = diagnosticar_bloqueo(destino)
            detalle = f" Procesos: {', '.join(culpables)}" if culpables else ""
            raise PermissionError(f"'{rel}' bloqueado al sustituir.{detalle}")

        if os.path.lexists(destino):
            borrar_seguro(destino)
        os.makedirs(os.path.dirname(destino), exist_ok=True)

        if MODO_INYECCION == "hardlink":
            crear_hardlink(destino, origen)
            p["hash_mod"] = sha256(origen)
            info("      enlace duro NTFS creado (0 bytes en disco)")
        elif MODO_INYECCION == "junction":
            # Los junctions operan sobre carpetas; a nivel de archivo se degrada a copia.
            p["hash_mod"] = copiar_verificado(origen, destino)
            info("      copia verificada (junction no aplicable a archivos)")
        else:
            p["hash_mod"] = copiar_verificado(origen, destino)
            info("      copia verificada")

    def _rollback(self, completadas: List[Dict]) -> None:
        """Deshace en orden inverso todas las operaciones ya aplicadas."""
        for p in reversed(completadas):
            try:
                if p["accion"] == NUEVO:
                    if os.path.lexists(p["destino"]):
                        borrar_seguro(p["destino"])
                        info(f"  revertido (borrado): {p['rel']}")
                elif p.get("backup") and os.path.isfile(p["backup"]):
                    if os.path.lexists(p["destino"]):
                        borrar_seguro(p["destino"])
                    copiar_verificado(p["backup"], p["destino"])
                    info(f"  revertido (restaurado): {p['rel']}")
            except Exception as exc:
                error(f"  ROLLBACK FALLIDO en '{p['rel']}': {exc}")
                error(f"  Recupera manualmente desde: {p.get('backup')}")

    def asegurar_inyectado(self, forzar: bool = False) -> bool:
        """
        Garantiza que el payload este aplicado, sin exigir una reinyeccion.

        Lanzar el juego no debe fallar solo porque el manifiesto ya diga
        'inyectado'. Si ese es el caso, se REVALIDA por hash: si todo sigue en
        su sitio se procede; si algo se perdio (p.ej. Steam verifico integridad
        por detras), se avisa y se ofrece reinyectar.
        """
        if forzar or not self.manifiesto.inyectado:
            return self.inyectar(forzar=forzar)

        if not self.validar_entorno():
            return False

        paso("El manifiesto indica INYECTADO. Revalidando el payload por hash...")
        escaner = Escaner(self.raiz_juego, self.raiz_perfil)
        pendientes = [p for p in escaner.construir_plan()
                      if p["accion"] in (NUEVO, REEMPLAZAR)]

        if not pendientes:
            ok("Payload integro. Se procede al lanzamiento.")
            return True

        aviso(f"{len(pendientes)} archivo(s) del mod ya NO estan aplicados:")
        for p in pendientes:
            print(f"      {C.AMBAR}pendiente{C.RESET} {p['rel']}")
        if not confirmar("Reinyectarlos antes de lanzar?"):
            aviso("Se lanzara con el payload INCOMPLETO.")
            return True
        return self.inyectar(forzar=True)

    # -- Restauracion ----------------------------------------------------------
    def restaurar(self) -> bool:
        titulo("RESTAURACION A ESTADO VANILLA")

        entradas = self.manifiesto.datos.get("entradas", [])
        if not entradas:
            aviso("El manifiesto no contiene operaciones registradas.")
            return self._restaurar_por_barrido()

        rutas = []
        for e in entradas:
            rutas.append(os.path.join(self.raiz_juego, e["rel"]))
        self.liberador.preparar_para_escritura(rutas)

        titulo("APLICANDO RESTAURACION")
        restaurados = borrados = fallos = 0

        for e in reversed(entradas):
            rel = e["rel"]
            destino = os.path.join(self.raiz_juego, rel)
            try:
                if e["accion"] == NUEVO:
                    # No existia en vanilla: se elimina.
                    if os.path.lexists(destino):
                        quitar_solo_lectura(destino)
                        esperar_desbloqueo(destino)
                        borrar_seguro(destino)
                        borrados += 1
                        print(f"   {C.AMBAR}eliminado{C.RESET}  {rel}")
                    continue

                backup = e.get("backup")
                if not backup or not os.path.isfile(backup):
                    error(f"Backup ausente para '{rel}'. Usa 'Verificar integridad' en Steam.")
                    fallos += 1
                    continue

                # Verificacion de integridad del backup antes de confiar en el
                hash_actual = sha256(backup)
                if e.get("hash_vanilla") and hash_actual != e["hash_vanilla"]:
                    error(f"El backup de '{rel}' NO coincide con su hash registrado.")
                    error("Se omite por seguridad. Restaura ese archivo desde Steam.")
                    fallos += 1
                    continue

                quitar_solo_lectura(destino)
                if not esperar_desbloqueo(destino):
                    raise PermissionError(f"'{rel}' bloqueado.")
                if os.path.lexists(destino):
                    borrar_seguro(destino)
                copiar_verificado(backup, destino)
                restaurados += 1
                print(f"   {C.VERDE}restaurado{C.RESET} {rel}")

            except Exception as exc:
                error(f"Error restaurando '{rel}': {exc}")
                fallos += 1

        print()
        ok(f"Restaurados: {restaurados} | Eliminados: {borrados} | Fallos: {fallos}")
        if fallos == 0:
            self.manifiesto.marcar_vanilla()
            ok("El juego ha vuelto a estado VANILLA.")
            return True
        aviso("Restauracion parcial. El manifiesto se conserva para reintentar.")
        return False

    def _restaurar_por_barrido(self) -> bool:
        """
        Plan B: si no hay manifiesto, busca todos los .bak en _VanillaBackup y
        los devuelve a su sitio deduciendo la ruta relativa.
        """
        if not os.path.isdir(self.dir_backup):
            error("No hay carpeta de respaldos ni manifiesto. Nada que restaurar.")
            info("Usa Steam -> Propiedades -> Archivos locales -> Verificar integridad.")
            return False

        aviso("Restaurando por barrido de la carpeta de respaldos...")
        candidatos: List[Tuple[str, str]] = []
        for actual, _dirs, archivos in os.walk(self.dir_backup):
            for nombre in archivos:
                if not nombre.endswith(".bak"):
                    continue
                origen = os.path.join(actual, nombre)
                rel = os.path.relpath(origen, self.dir_backup)[:-4]  # quita '.bak'
                candidatos.append((origen, os.path.join(self.raiz_juego, rel)))

        if not candidatos:
            error("No se hallaron archivos .bak.")
            return False

        self.liberador.preparar_para_escritura([d for _o, d in candidatos])
        hechos = fallos = 0
        for origen, destino in candidatos:
            try:
                quitar_solo_lectura(destino)
                esperar_desbloqueo(destino)
                if os.path.lexists(destino):
                    borrar_seguro(destino)
                copiar_verificado(origen, destino)
                hechos += 1
                print(f"   {C.VERDE}restaurado{C.RESET} {os.path.relpath(destino, self.raiz_juego)}")
            except Exception as exc:
                error(f"Fallo restaurando '{destino}': {exc}")
                fallos += 1
        ok(f"Barrido finalizado. Restaurados: {hechos} | Fallos: {fallos}")
        return fallos == 0

    # -- Reparacion de instalaciones rotas por herramientas previas -------------
    def reparar_huerfanos(self) -> bool:
        """
        Repara el dano tipico de un inyector defectuoso: archivos VANILLA que
        fueron MOVIDOS a una carpeta de backup y nunca devueltos, dejando al
        juego con archivos ausentes.

        Solo restaura cuando el destino NO EXISTE. Nunca sobrescribe un archivo
        presente, porque un backup tomado despues de una inyeccion previa puede
        contener datos ya modificados (backup contaminado).
        """
        titulo("REPARACION DE ARCHIVOS HUERFANOS")

        origenes = [
            os.path.join(self.raiz_moddata, "_Backup_Originals"),
            self.dir_backup,
        ]
        huerfanos: List[Tuple[str, str]] = []
        contaminados: List[str] = []

        for base in origenes:
            if not os.path.isdir(base):
                continue
            for actual, dirs, archivos in os.walk(base):
                dirs[:] = [d for d in dirs if not es_reparse_point(os.path.join(actual, d))]
                for nombre in archivos:
                    origen = os.path.join(actual, nombre)
                    rel = os.path.relpath(origen, base)
                    if rel.endswith(".bak"):
                        rel = rel[:-4]
                    destino = os.path.join(self.raiz_juego, rel)
                    if os.path.lexists(destino):
                        contaminados.append(rel)
                    else:
                        huerfanos.append((origen, destino))

        if contaminados:
            aviso(f"{len(contaminados)} respaldo(s) cuyo destino YA existe: se omiten.")
            aviso("No se sobrescriben: podrian ser copias de archivos ya modificados.")
            for r in contaminados[:10]:
                print(f"      {C.GRIS}omitido{C.RESET} {r}")
            if len(contaminados) > 10:
                print(f"      {C.GRIS}... y {len(contaminados) - 10} mas{C.RESET}")

        if not huerfanos:
            ok("No se detectaron archivos huerfanos. La instalacion esta completa.")
            return True

        print()
        error(f"DETECTADOS {len(huerfanos)} ARCHIVO(S) VANILLA AUSENTES DEL JUEGO:")
        for _o, d in huerfanos:
            print(f"      {C.ROJO}falta{C.RESET} {os.path.relpath(d, self.raiz_juego)}")
        print()

        if not confirmar("Restaurarlos a su ubicacion original?"):
            info("Operacion cancelada por el usuario.")
            return False

        # Preparacion LIGERA a proposito: todos los destinos estan AUSENTES, asi que
        # ningun proceso puede mantener un handle sobre ellos. Cerrar Steam y EA App
        # aqui seria disruptivo y no aportaria nada. Basta con asegurar que las
        # carpetas contenedoras sean escribibles.
        carpetas = sorted({os.path.dirname(d) for _o, d in huerfanos})
        for c in carpetas:
            os.makedirs(c, exist_ok=True)
        self.liberador.limpiar_atributos(carpetas)
        self.liberador.tomar_propiedad(carpetas)

        # El juego SI debe estar cerrado: podria estar leyendo la carpeta Data.
        objetivos = {e.lower() for e in EJECUTABLES_JUEGO}
        if any(n.lower() in objetivos for _p, n in enumerar_procesos()):
            aviso("El juego esta en ejecucion. Cerrandolo antes de reparar...")
            for pid, nombre in enumerar_procesos():
                if nombre.lower() in objetivos:
                    matar_pid(pid)
            time.sleep(2)

        hechos = fallos = 0
        for origen, destino in huerfanos:
            try:
                os.makedirs(os.path.dirname(destino), exist_ok=True)
                copiar_verificado(origen, destino)
                hechos += 1
                print(f"   {C.VERDE}restaurado{C.RESET} {os.path.relpath(destino, self.raiz_juego)}")
            except Exception as exc:
                error(f"Fallo restaurando '{destino}': {exc}")
                fallos += 1

        print()
        ok(f"Reparacion finalizada. Restaurados: {hechos} | Fallos: {fallos}")
        if hechos:
            aviso("Recomendado: Steam -> Verificar integridad, para confirmar el resto.")
        return fallos == 0

    # -- Diagnostico -----------------------------------------------------------
    def diagnostico(self) -> None:
        titulo("DIAGNOSTICO DEL ENTORNO")

        print(f"   Juego           : {self.raiz_juego}")
        print(f"   Perfil Frosty   : {self.raiz_perfil}")
        print(f"   Estado manifiesto: "
              f"{C.AMBAR if self.manifiesto.inyectado else C.VERDE}"
              f"{self.manifiesto.datos.get('estado', '?').upper()}{C.RESET}")
        print(f"   Administrador   : "
              f"{C.VERDE + 'SI' if es_administrador() else C.ROJO + 'NO'}{C.RESET}")
        print(f"   Modo inyeccion  : {MODO_INYECCION}")

        # Frosty y su cache
        print(f"\n   {C.NEGRITA}Frosty Mod Manager:{C.RESET}")
        if not self.dir_frosty:
            print(f"      {C.AMBAR}no localizado{C.RESET} "
                  f"(se busco en las unidades y en Archivos de programa)")
        else:
            print(f"      Carpeta : {self.dir_frosty}")
            est = estado_cache_frosty(self.dir_frosty, self.raiz_juego)
            if not est["existe"]:
                print(f"      Cache   : {C.GRIS}no existe — Frosty la creara al abrirse{C.RESET}")
            else:
                f_cache = datetime.fromtimestamp(est["fecha_cache"]).strftime("%d-%m-%Y %H:%M")
                f_datos = datetime.fromtimestamp(est["fecha_datos"]).strftime("%d-%m-%Y %H:%M")
                print(f"      Indexada: {f_cache}")
                print(f"      Datos   : {f_datos}")
                if est["obsoleta"]:
                    print(f"      Estado  : {C.ROJO}{C.NEGRITA}OBSOLETA{C.RESET} "
                          f"{C.ROJO}— reindexa antes de compilar (opcion [9]){C.RESET}")
                else:
                    print(f"      Estado  : {C.VERDE}al dia{C.RESET}")

        # Procesos conflictivos
        print(f"\n   {C.NEGRITA}Procesos conflictivos activos:{C.RESET}")
        objetivos = {p.lower() for p in PROCESOS_A_CERRAR}
        activos = [(pid, n) for pid, n in enumerar_procesos() if n.lower() in objetivos]
        if activos:
            for pid, n in activos:
                print(f"      {C.AMBAR}activo{C.RESET} {n} (PID {pid})")
        else:
            print(f"      {C.VERDE}ninguno{C.RESET}")

        # Defender
        est = self.liberador.estado_defender()
        if est:
            cfa = est.get("CFA", "?")
            excluido = self.raiz_juego.lower() in est.get("EXCL", "").lower()
            print(f"\n   {C.NEGRITA}Windows Defender:{C.RESET}")
            print(f"      Proteccion en tiempo real : {est.get('RT', '?')}")
            print(f"      Acceso Controlado Carpetas: "
                  f"{C.AMBAR + cfa if cfa not in ('0', 'False') else C.VERDE + cfa}{C.RESET}")
            print(f"      Carpeta excluida          : "
                  f"{C.VERDE + 'SI' if excluido else C.GRIS + 'NO'}{C.RESET}")

        # Plan
        if not os.path.isdir(self.raiz_perfil):
            error(f"\n   No existe el perfil: {self.raiz_perfil}")
            return

        print(f"\n   {C.NEGRITA}Analisis de ModData\\{PERFIL_FROSTY}:{C.RESET}")
        escaner = Escaner(self.raiz_juego, self.raiz_perfil)
        plan = escaner.construir_plan()
        conteo = {NUEVO: 0, REEMPLAZAR: 0, YA_INYECTADO: 0, MISMO_FISICO: 0}
        for p in plan:
            conteo[p["accion"]] += 1
        print(f"      Enlaces omitidos (vanilla): {escaner.enlaces_omitidos}")
        print(f"      Archivos reales del mod   : {len(plan)}")
        print(f"        - pendientes de inyectar: "
              f"{C.AMBAR}{conteo[NUEVO] + conteo[REEMPLAZAR]}{C.RESET}")
        print(f"        - ya inyectados         : {C.VERDE}{conteo[YA_INYECTADO]}{C.RESET}")
        print(f"        - mismo inodo (omitir)  : {conteo[MISMO_FISICO]}")

        if plan:
            print(f"\n   {C.NEGRITA}Detalle del payload:{C.RESET}")
            for p in plan:
                colores = {
                    NUEVO: C.AMBAR, REEMPLAZAR: C.AMBAR,
                    YA_INYECTADO: C.VERDE, MISMO_FISICO: C.GRIS,
                }
                col = colores[p["accion"]]
                print(f"      {col}{p['accion']:<13}{C.RESET} "
                      f"{tamano_legible(p['tamano']):>10}  {p['rel']}")

        # Integridad: huerfanos
        print(f"\n   {C.NEGRITA}Integridad de la instalacion:{C.RESET}")
        huerfanos = 0
        for base in (os.path.join(self.raiz_moddata, "_Backup_Originals"), self.dir_backup):
            if not os.path.isdir(base):
                continue
            for actual, dirs, archivos in os.walk(base):
                dirs[:] = [d for d in dirs if not es_reparse_point(os.path.join(actual, d))]
                for nombre in archivos:
                    rel = os.path.relpath(os.path.join(actual, nombre), base)
                    if rel.endswith(".bak"):
                        rel = rel[:-4]
                    if not os.path.lexists(os.path.join(self.raiz_juego, rel)):
                        if huerfanos == 0:
                            print(f"      {C.ROJO}ARCHIVOS VANILLA AUSENTES DEL JUEGO:{C.RESET}")
                        print(f"        {C.ROJO}falta{C.RESET} {rel}")
                        huerfanos += 1
        if huerfanos:
            print(f"\n      {C.ROJO}{C.NEGRITA}Instalacion INCOMPLETA: "
                  f"{huerfanos} archivo(s). Usa la opcion [5].{C.RESET}")
        else:
            print(f"      {C.VERDE}Sin archivos huerfanos detectados.{C.RESET}")


# ==============================================================================
# SECCION 10 - LANZADOR
# ==============================================================================

class Lanzador:
    def __init__(self, raiz_juego: str):
        self.raiz = raiz_juego

    def lanzar_por_steam(self) -> bool:
        """Lanza mediante el protocolo steam:// para que se apliquen DRM y EA App."""
        url = f"steam://rungameid/{STEAM_APPID}"
        paso(f"Lanzando el juego: {url}")
        try:
            os.startfile(url)  # type: ignore[attr-defined]
            ok("Peticion enviada a Steam.")
            info("Steam y EA App tardaran unos segundos en inicializarse.")
            return True
        except OSError as exc:
            error(f"No se pudo invocar el protocolo steam://: {exc}")
            return self.lanzar_directo()

    def lanzar_directo(self) -> bool:
        """Alternativa: ejecutar el binario (Steam se reenganchara por DRM)."""
        exe = os.path.join(self.raiz, EJECUTABLE_JUEGO)
        if not os.path.isfile(exe):
            error(f"No se encontro el ejecutable: {exe}")
            return False
        try:
            subprocess.Popen([exe], cwd=self.raiz, close_fds=True)
            ok("Ejecutable lanzado directamente.")
            return True
        except OSError as exc:
            error(f"No se pudo lanzar el ejecutable: {exc}")
            return False

    @staticmethod
    def esperar_cierre(timeout_arranque: int = 180) -> bool:
        """
        Espera a que el proceso del juego aparezca y despues termine.
        Util para encadenar una restauracion automatica.
        """
        objetivos = {e.lower() for e in EJECUTABLES_JUEGO}
        paso("Esperando a que arranque el juego...")
        limite = time.time() + timeout_arranque
        arrancado = False
        while time.time() < limite:
            if any(n.lower() in objetivos for _p, n in enumerar_procesos()):
                arrancado = True
                break
            time.sleep(2)
        if not arrancado:
            aviso(f"El juego no arranco en {timeout_arranque}s. Se deja de esperar.")
            return False
        ok("Juego en ejecucion. Esperando a que lo cierres...")
        while any(n.lower() in objetivos for _p, n in enumerar_procesos()):
            time.sleep(5)
        ok("El juego se ha cerrado.")
        return True


# ==============================================================================
# SECCION 11 - MENU E INTERFAZ
# ==============================================================================

BANNER = r"""
   _  _ ___ ___   _  _ ___   _ _____   ___ _  _ _ ___ ___ _____ ___  ___
  | \| | __/ __| | || | __| /_\_   _| |_ _| \| | | __/ __|_   _/ _ \| _ \
  | .` | _|\__ \ | __ | _| / _ \| |    | || .` | | _| (__  | || (_) |   /
  |_|\_|_| |___/ |_||_|___/_/ \_\_|   |___|_|\_| |___\___| |_| \___/|_|_\
"""


def mostrar_menu(motor: MotorInyeccion) -> None:
    estado = motor.manifiesto.datos.get("estado", "?").upper()
    color_estado = C.AMBAR if motor.manifiesto.inyectado else C.VERDE
    print(f"\n{C.CIAN}{BANNER}{C.RESET}")
    print(f"   Juego  : {C.GRIS}{motor.raiz_juego}{C.RESET}")
    print(f"   Perfil : {C.GRIS}{PERFIL_FROSTY}{C.RESET}   "
          f"Estado: {color_estado}{estado}{C.RESET}   "
          f"Admin: {C.VERDE + 'SI' if es_administrador() else C.ROJO + 'NO'}{C.RESET}")
    print(f"\n   {C.NEGRITA}ACCIONES PRINCIPALES{C.RESET}")
    print(f"     {C.NEGRITA}[1]{C.RESET} Inyectar Mods y Lanzar Juego (Steam Protocol)")
    print(f"     {C.NEGRITA}[2]{C.RESET} Restaurar Archivos Originales (Vanilla)")
    print(f"     {C.NEGRITA}[3]{C.RESET} Salir")
    print(f"\n   {C.NEGRITA}HERRAMIENTAS{C.RESET}")
    print(f"     {C.NEGRITA}[4]{C.RESET} Diagnostico completo del estado")
    print(f"     {C.NEGRITA}[5]{C.RESET} Reparar instalacion (archivos vanilla ausentes)")
    print(f"     {C.NEGRITA}[6]{C.RESET} Anadir exclusion de Windows Defender")
    print(f"     {C.NEGRITA}[7]{C.RESET} Solo liberar archivos (matar procesos y permisos)")
    print(f"     {C.NEGRITA}[8]{C.RESET} Inyectar sin lanzar el juego")
    print(f"     {C.NEGRITA}[9]{C.RESET} Invalidar la cache de Frosty (forzar reindexado)")
    print()


def accion_inyectar_y_lanzar(motor: MotorInyeccion, lanzar: bool = True) -> None:
    # Para lanzar basta con asegurar el payload; para la opcion "solo inyectar"
    # se usa la ruta estricta, que si rechaza una doble inyeccion.
    aplicado = motor.asegurar_inyectado() if lanzar else motor.inyectar()
    if not aplicado:
        return
    if not lanzar:
        return
    lanzador = Lanzador(motor.raiz_juego)
    if not lanzador.lanzar_por_steam():
        return
    print()
    if confirmar("Restaurar automaticamente al cerrar el juego?"):
        if Lanzador.esperar_cierre():
            motor.restaurar()


def accion_invalidar_cache(motor: MotorInyeccion) -> bool:
    """
    Renombra la cache de Frosty para forzar un reindexado contra la instalacion
    actual. Es el remedio cuando el juego se actualizo o se reparo despues de
    que Frosty construyera su indice.
    """
    titulo("INVALIDAR LA CACHE DE FROSTY")
    if not motor.dir_frosty:
        error("No se encontro la carpeta de Frosty Mod Manager.")
        info("Pasa la ruta con --frosty, o renombra a mano <Frosty>\\Caches\\NFSHEAT.cache")
        return False

    est = estado_cache_frosty(motor.dir_frosty, motor.raiz_juego)
    print(f"   Frosty : {motor.dir_frosty}")
    if not est["existe"]:
        ok("No hay cache: Frosty la construira la proxima vez que se abra.")
        return True
    f_cache = datetime.fromtimestamp(est["fecha_cache"]).strftime("%d-%m-%Y %H:%M")
    f_datos = datetime.fromtimestamp(est["fecha_datos"]).strftime("%d-%m-%Y %H:%M")
    print(f"   Cache indexada : {f_cache}")
    print(f"   Datos del juego: {f_datos}")
    print(f"   Estado         : "
          f"{C.ROJO + 'OBSOLETA' if est['obsoleta'] else C.VERDE + 'al dia'}{C.RESET}\n")

    if not est["obsoleta"]:
        aviso("La cache parece al dia. Invalidarla solo cuesta un reindexado.")
    if not confirmar("Renombrar la cache para forzar el reindexado?"):
        info("Operacion cancelada.")
        return False

    if invalidar_cache_frosty(motor.dir_frosty) is None:
        return False

    # ModData debe irse tambien: si sobrevive, Frosty lo reutiliza y se salta
    # la recompilacion, dejando el build viejo hecho con la cache defectuosa.
    if os.path.isdir(motor.raiz_perfil):
        print()
        aviso(f"Existe {os.path.relpath(motor.raiz_perfil, motor.raiz_juego)}.")
        aviso("Si no se borra, Frosty lo reutilizara y no recompilara.")
        if confirmar("Borrarlo tambien? (borrado seguro, no sigue enlaces)"):
            try:
                borrar_arbol_moddata(motor.raiz_perfil)
                ok("Perfil de ModData borrado. Frosty compilara de cero.")
            except OSError as exc:
                error(f"No se pudo borrar el perfil: {exc}")
                return False

    print()
    info("Ahora abre Frosty (reconstruira el indice), aplica tus mods y pulsa Launch.")
    info("Cierra el juego cuando abra, y vuelve aqui para inyectar.")
    return True


def borrar_arbol_moddata(raiz: str) -> None:
    """
    Borrado recursivo que trata cada reparse point como una hoja.

    ModData contiene un enlace 'Data' que apunta a la carpeta real del juego:
    un rmtree normal lo seguiria y vaciaria la instalacion. Aqui nunca se
    desciende en un enlace, solo se elimina el enlace en si.
    """
    if es_reparse_point(raiz):
        borrar_seguro(raiz)
        return
    for entrada in os.scandir(raiz):
        if es_reparse_point(entrada.path):
            borrar_seguro(entrada.path)
        elif entrada.is_dir(follow_symlinks=False):
            borrar_arbol_moddata(entrada.path)
        else:
            borrar_seguro(entrada.path)
    os.rmdir(ruta_larga(raiz))


def bucle_principal(motor: MotorInyeccion) -> None:
    acciones = {
        "1": lambda: accion_inyectar_y_lanzar(motor, lanzar=True),
        "2": motor.restaurar,
        "4": motor.diagnostico,
        "5": motor.reparar_huerfanos,
        "6": motor.liberador.anadir_exclusion_defender,
        "7": lambda: (motor.liberador.terminar_procesos(),
                      motor.liberador.detener_servicios(),
                      motor.liberador.tomar_propiedad_recursiva(motor.raiz_juego)),
        "8": lambda: accion_inyectar_y_lanzar(motor, lanzar=False),
        "9": lambda: accion_invalidar_cache(motor),
    }
    while True:
        try:
            mostrar_menu(motor)
            opcion = input(f"   {C.NEGRITA}Selecciona una opcion: {C.RESET}").strip()
            if opcion == "3":
                info("Saliendo. Recuerda restaurar a vanilla antes de jugar online.")
                return
            accion = acciones.get(opcion)
            if not accion:
                aviso("Opcion no valida.")
                continue
            accion()
            motor.manifiesto.cargar()
            input(f"\n   {C.GRIS}Pulsa ENTER para volver al menu...{C.RESET}")
        except KeyboardInterrupt:
            print()
            info("Interrumpido por el usuario.")
            return
        except Exception as exc:
            error(f"Excepcion no controlada: {exc}")
            log(traceback.format_exc(), C.GRIS)
            input(f"\n   {C.GRIS}Pulsa ENTER para continuar...{C.RESET}")


# ==============================================================================
# SECCION 12 - PUNTO DE ENTRADA
# ==============================================================================

def main() -> int:
    global _ARCHIVO_LOG, MODO_INYECCION, ASUMIR_SI

    if os.name != "nt":
        print("Este script funciona unicamente en Windows.")
        return 1

    preparar_consola()

    parser = argparse.ArgumentParser(
        description="Inyector de mods Frosty para Need for Speed Heat.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--juego", default=None,
                        help="Ruta raiz del juego. Si se omite, se autodetecta.")
    parser.add_argument("--frosty", default=None,
                        help="Carpeta de Frosty Mod Manager. Si se omite, se autodetecta.")
    parser.add_argument("--invalidar-cache", dest="invalidar_cache", action="store_true",
                        help="Renombra la cache de Frosty para forzar el reindexado y sale.")
    parser.add_argument("--perfil", default=PERFIL_FROSTY, help="Perfil de Frosty (ModData\\<perfil>).")
    parser.add_argument("--modo", choices=["copia", "hardlink", "junction"],
                        default=MODO_INYECCION, help="Estrategia de inyeccion.")
    parser.add_argument("--inyectar", action="store_true", help="Inyecta y sale.")
    parser.add_argument("--lanzar", action="store_true", help="Inyecta, lanza y sale.")
    parser.add_argument("--restaurar", action="store_true", help="Restaura vanilla y sale.")
    parser.add_argument("--reparar", action="store_true", help="Repara huerfanos y sale.")
    parser.add_argument("--diagnostico", action="store_true", help="Muestra el diagnostico y sale.")
    parser.add_argument("--forzar", action="store_true",
                        help="Inyecta aunque el manifiesto diga que ya esta inyectado.")
    parser.add_argument("--si", "--yes", dest="si", action="store_true",
                        help="Responde SI a todas las confirmaciones (ejecucion desatendida).")
    parser.add_argument("--sin-elevar", action="store_true",
                        help="No solicitar UAC (para depuracion; muchas acciones fallaran).")
    args = parser.parse_args()

    MODO_INYECCION = args.modo
    ASUMIR_SI = args.si

    # --- Elevacion automatica -------------------------------------------------
    if not es_administrador():
        if args.sin_elevar:
            aviso("Ejecutando SIN privilegios de administrador (--sin-elevar).")
            aviso("Los bloqueos de EA App y Defender NO podran resolverse.")
        else:
            reejecutar_elevado()
            return 0

    # --- Localizacion del juego -----------------------------------------------
    # Se prueba la ruta indicada, luego la constante, y si ninguna sirve se
    # autodetecta. Asi el script funciona recien clonado y sin editar nada.
    ruta_juego = localizar_juego(args.juego or RUTA_JUEGO)
    if not ruta_juego:
        error("No se encontro Need for Speed Heat.")
        error("Indica la ruta con --juego \"X:\\...\\Need for Speed Heat\"")
        return 1
    if not (args.juego or os.path.isdir(RUTA_JUEGO)):
        ok(f"Juego autodetectado: {ruta_juego}")
    args.juego = ruta_juego

    # --- Log ------------------------------------------------------------------
    dir_estado = os.path.join(args.juego, "ModData", "_InjectorState")
    try:
        os.makedirs(dir_estado, exist_ok=True)
        _ARCHIVO_LOG = os.path.join(dir_estado, "injector.log")
    except OSError:
        _ARCHIVO_LOG = None

    if es_administrador():
        ok(f"Ejecutando como Administrador. Log: {_ARCHIVO_LOG or 'deshabilitado'}")
    else:
        aviso(f"Ejecutando SIN elevacion. Log: {_ARCHIVO_LOG or 'deshabilitado'}")

    motor = MotorInyeccion(args.juego, args.perfil)
    if args.frosty:
        motor.dir_frosty = args.frosty if os.path.isdir(args.frosty) else motor.dir_frosty
    if motor.dir_frosty and not args.frosty:
        info(f"Frosty autodetectado: {motor.dir_frosty}")

    # --- Modo no interactivo --------------------------------------------------
    if args.invalidar_cache:
        return 0 if accion_invalidar_cache(motor) else 1
    if args.diagnostico:
        motor.diagnostico()
        return 0
    if args.reparar:
        return 0 if motor.reparar_huerfanos() else 1
    if args.restaurar:
        return 0 if motor.restaurar() else 1
    if args.inyectar:
        return 0 if motor.inyectar(forzar=args.forzar) else 1
    if args.lanzar:
        if not motor.asegurar_inyectado(forzar=args.forzar):
            return 1
        return 0 if Lanzador(motor.raiz_juego).lanzar_por_steam() else 1

    # --- Modo interactivo -----------------------------------------------------
    motor.diagnostico()
    bucle_principal(motor)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nInterrumpido.")
        sys.exit(130)
    except Exception:
        traceback.print_exc()
        input("\nSe produjo un error inesperado. Pulsa ENTER para cerrar...")
        sys.exit(1)
