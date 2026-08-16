#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
 NFS HEAT MOD INJECTOR  -  Interfaz grafica
================================================================================
 Envoltorio visual sobre nfs_heat_injector.py para quien no quiera tocar la
 consola. Toda la logica vive en el motor; aqui solo hay presentacion.

 Detalles de diseno que importan:
  - Las operaciones corren en un HILO APARTE. Si se ejecutaran en el hilo de
    Tk, la ventana se congelaria durante los minutos que tarda una inyeccion.
  - El motor escribe con print() y pregunta con input(). Ambos se redirigen:
    stdout va a un widget de texto, y confirmar() se convierte en un dialogo.
  - Los dialogos SOLO pueden crearse desde el hilo principal de Tk. El hilo
    trabajador encola la pregunta y se bloquea hasta que la UI le responde.
================================================================================
"""

from __future__ import annotations

import os
import queue
import re
import sys
import threading
import traceback
from datetime import datetime
from typing import Callable, Optional

import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext

# El motor vive junto a este archivo (o dentro del exe empaquetado)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nfs_heat_injector as motor_mod  # noqa: E402


# ==============================================================================
# PALETA
# ==============================================================================

FONDO = "#14161b"
PANEL = "#1c1f27"
PANEL2 = "#22262f"
BORDE = "#2e333d"
TEXTO = "#e7e9ee"
TENUE = "#8b93a1"
ROSA = "#ff2d78"       # acento principal, guino a la paleta de Heat
CIAN = "#22d3ee"
VERDE = "#3ddc84"
AMBAR = "#ffb020"
ROJO = "#ff4d4f"

FUENTE = ("Segoe UI", 10)
FUENTE_B = ("Segoe UI Semibold", 10)
FUENTE_TIT = ("Segoe UI Semibold", 17)
FUENTE_MONO = ("Consolas", 9)

ANSI = re.compile(r"\x1b\[[0-9;]*m")


# ==============================================================================
# CAPTURA DE SALIDA
# ==============================================================================

class CapturaSalida:
    """
    Sustituye a sys.stdout. Quita los codigos de color ANSI que el motor emite
    para consola y encola las lineas para que la UI las pinte.

    Ojo: en un exe compilado con --windowed, sys.stdout es None y cualquier
    print() reventaria. Por eso se instala de forma permanente, no solo durante
    las operaciones.
    """

    def __init__(self, cola: queue.Queue):
        self.cola = cola
        self._resto = ""

    def write(self, texto: str) -> int:
        if not texto:
            return 0
        limpio = ANSI.sub("", texto)
        self._resto += limpio
        while "\n" in self._resto:
            linea, self._resto = self._resto.split("\n", 1)
            self.cola.put(("log", linea))
        return len(texto)

    def flush(self) -> None:
        if self._resto:
            self.cola.put(("log", self._resto))
            self._resto = ""

    def isatty(self) -> bool:
        return False


# ==============================================================================
# WIDGETS AUXILIARES
# ==============================================================================

class Boton(tk.Frame):
    """Boton plano con estados de hover y deshabilitado, sin depender de ttk."""

    def __init__(self, padre, texto, orden, color=ROSA, principal=False, **kw):
        super().__init__(padre, bg=color if principal else PANEL2,
                         highlightthickness=1,
                         highlightbackground=color if principal else BORDE,
                         highlightcolor=color if principal else BORDE, **kw)
        self.orden = orden
        self.color = color
        self.principal = principal
        self.activo = True
        self.etiqueta = tk.Label(
            self, text=texto, bg=self["bg"],
            fg="#ffffff" if principal else TEXTO,
            font=FUENTE_B if principal else FUENTE,
            padx=16, pady=9, cursor="hand2",
        )
        self.etiqueta.pack(fill="both", expand=True)
        for w in (self, self.etiqueta):
            w.bind("<Button-1>", self._click)
            w.bind("<Enter>", self._entrar)
            w.bind("<Leave>", self._salir)

    def _click(self, _e=None):
        if self.activo:
            self.orden()

    def _entrar(self, _e=None):
        if not self.activo:
            return
        nuevo = self._aclarar(self.color) if self.principal else BORDE
        self.configure(bg=nuevo)
        self.etiqueta.configure(bg=nuevo, fg="#ffffff")

    def _salir(self, _e=None):
        if not self.activo:
            return
        base = self.color if self.principal else PANEL2
        self.configure(bg=base)
        self.etiqueta.configure(bg=base, fg="#ffffff" if self.principal else TEXTO)

    @staticmethod
    def _aclarar(hexcol: str, f: float = 0.18) -> str:
        r, g, b = (int(hexcol[i:i + 2], 16) for i in (1, 3, 5))
        r, g, b = (min(255, int(c + (255 - c) * f)) for c in (r, g, b))
        return f"#{r:02x}{g:02x}{b:02x}"

    def habilitar(self, si: bool) -> None:
        self.activo = si
        if si:
            self._salir()
            self.etiqueta.configure(cursor="hand2")
        else:
            self.configure(bg=PANEL)
            self.etiqueta.configure(bg=PANEL, fg=TENUE, cursor="arrow")


class FilaEstado(tk.Frame):
    """Una linea del panel de estado: punto de color + etiqueta + valor."""

    def __init__(self, padre, titulo):
        super().__init__(padre, bg=PANEL)
        self.punto = tk.Label(self, text="●", bg=PANEL, fg=TENUE, font=("Segoe UI", 11))
        self.punto.pack(side="left", padx=(0, 8))
        tk.Label(self, text=titulo, bg=PANEL, fg=TENUE, font=FUENTE,
                 width=9, anchor="w").pack(side="left")
        self.valor = tk.Label(self, text="comprobando…", bg=PANEL, fg=TEXTO,
                              font=FUENTE, anchor="w", justify="left")
        self.valor.pack(side="left", fill="x", expand=True)

    def poner(self, texto: str, color: str) -> None:
        self.valor.configure(text=texto, fg=TEXTO if color != TENUE else TENUE)
        self.punto.configure(fg=color)


# ==============================================================================
# VENTANA PRINCIPAL
# ==============================================================================

class Aplicacion(tk.Tk):

    def __init__(self):
        super().__init__()
        self.title("NFS Heat Mod Injector")
        self.configure(bg=FONDO)
        self.geometry("880x680")
        self.minsize(760, 560)

        self.cola: queue.Queue = queue.Queue()
        self.motor: Optional[motor_mod.MotorInyeccion] = None
        self.trabajando = False
        self._respuesta = None
        self._evento_respuesta = threading.Event()

        # stdout permanente: en modo --windowed sys.stdout es None
        captura = CapturaSalida(self.cola)
        sys.stdout = captura
        sys.stderr = captura
        motor_mod._SUMIDERO_LOG = lambda nivel, texto: None  # el print ya llega por stdout
        motor_mod._HOOK_CONFIRMAR = self._confirmar_desde_hilo

        self._construir()
        self.after(60, self._bombear_cola)
        self.after(120, lambda: self._en_hilo(self._tarea_refrescar, "Detectando instalacion"))

    # -- Construccion de la interfaz -------------------------------------------
    def _construir(self) -> None:
        cab = tk.Frame(self, bg=FONDO)
        cab.pack(fill="x", padx=22, pady=(18, 10))
        tk.Label(cab, text="NFS Heat Mod Injector", bg=FONDO, fg=TEXTO,
                 font=FUENTE_TIT).pack(side="left")
        tk.Label(cab, text="  mods de Frosty que si se cargan", bg=FONDO, fg=ROSA,
                 font=FUENTE).pack(side="left", padx=(2, 0))
        self.lbl_admin = tk.Label(cab, text="", bg=FONDO, fg=TENUE, font=FUENTE)
        self.lbl_admin.pack(side="right")

        # Panel de estado
        caja = tk.Frame(self, bg=PANEL, highlightthickness=1,
                        highlightbackground=BORDE, highlightcolor=BORDE)
        caja.pack(fill="x", padx=22, pady=(0, 14))
        interior = tk.Frame(caja, bg=PANEL)
        interior.pack(fill="x", padx=16, pady=14)
        self.f_juego = FilaEstado(interior, "Juego")
        self.f_frosty = FilaEstado(interior, "Frosty")
        self.f_cache = FilaEstado(interior, "Cache")
        self.f_estado = FilaEstado(interior, "Estado")
        for f in (self.f_juego, self.f_frosty, self.f_cache, self.f_estado):
            f.pack(fill="x", pady=2)

        # Botones principales
        b1 = tk.Frame(self, bg=FONDO)
        b1.pack(fill="x", padx=22)
        self.b_jugar = Boton(b1, "▶  Inyectar mods y jugar",
                             lambda: self._en_hilo(self._tarea_inyectar_lanzar,
                                                   "Inyectando y lanzando"),
                             color=ROSA, principal=True)
        self.b_jugar.pack(side="left", padx=(0, 10))
        self.b_restaurar = Boton(b1, "↺  Restaurar original",
                                 lambda: self._en_hilo(self._tarea_restaurar, "Restaurando"))
        self.b_restaurar.pack(side="left", padx=(0, 10))
        self.b_inyectar = Boton(b1, "Solo inyectar",
                                lambda: self._en_hilo(self._tarea_inyectar, "Inyectando"))
        self.b_inyectar.pack(side="left")

        # Botones secundarios
        b2 = tk.Frame(self, bg=FONDO)
        b2.pack(fill="x", padx=22, pady=(10, 14))
        self.b_diag = Boton(b2, "Diagnostico",
                            lambda: self._en_hilo(self._tarea_diagnostico, "Diagnosticando"))
        self.b_diag.pack(side="left", padx=(0, 8))
        self.b_cache = Boton(b2, "Invalidar cache de Frosty",
                             lambda: self._en_hilo(self._tarea_invalidar, "Invalidando cache"),
                             color=AMBAR)
        self.b_cache.pack(side="left", padx=(0, 8))
        self.b_reparar = Boton(b2, "Reparar instalacion",
                               lambda: self._en_hilo(self._tarea_reparar, "Reparando"))
        self.b_reparar.pack(side="left", padx=(0, 8))
        self.b_ruta = Boton(b2, "Cambiar ruta…", self._elegir_ruta)
        self.b_ruta.pack(side="left")

        # Registro
        marco_log = tk.Frame(self, bg=PANEL, highlightthickness=1,
                             highlightbackground=BORDE, highlightcolor=BORDE)
        marco_log.pack(fill="both", expand=True, padx=22, pady=(0, 12))
        self.txt = scrolledtext.ScrolledText(
            marco_log, bg="#0f1116", fg="#c9cfda", font=FUENTE_MONO,
            insertbackground=TEXTO, relief="flat", wrap="word",
            padx=12, pady=10, state="disabled", height=14,
        )
        self.txt.pack(fill="both", expand=True, padx=1, pady=1)
        for nombre, color in (("ok", VERDE), ("aviso", AMBAR), ("error", ROJO),
                              ("info", CIAN), ("paso", ROSA), ("tenue", TENUE)):
            self.txt.tag_configure(nombre, foreground=color)

        # Barra inferior
        pie = tk.Frame(self, bg=FONDO)
        pie.pack(fill="x", padx=22, pady=(0, 14))
        self.lbl_estado = tk.Label(pie, text="Listo", bg=FONDO, fg=TENUE, font=FUENTE)
        self.lbl_estado.pack(side="left")
        tk.Label(pie, text="Lanza siempre por Steam, nunca desde Frosty",
                 bg=FONDO, fg=TENUE, font=("Segoe UI", 9)).pack(side="right")

    # -- Registro ---------------------------------------------------------------
    def _escribir(self, linea: str) -> None:
        etiqueta = "tenue"
        for clave, tag in (("[ OK ]", "ok"), ("[AVISO]", "aviso"), ("[ERROR]", "error"),
                           ("[INFO]", "info"), ("[PASO]", "paso")):
            if clave in linea:
                etiqueta = tag
                break
        if linea.startswith("===") or linea.startswith("---"):
            etiqueta = "paso"
        self.txt.configure(state="normal")
        self.txt.insert("end", linea + "\n", etiqueta)
        self.txt.see("end")
        self.txt.configure(state="disabled")

    def _bombear_cola(self) -> None:
        """Vacia la cola del hilo trabajador. Solo el hilo de Tk toca widgets."""
        try:
            while True:
                tipo, dato = self.cola.get_nowait()
                if tipo == "log":
                    self._escribir(dato)
                elif tipo == "estado":
                    self.lbl_estado.configure(text=dato)
                elif tipo == "refrescar":
                    self._pintar_estado(dato)
                elif tipo == "fin":
                    self._bloquear(False)
                elif tipo == "preguntar":
                    self._responder(dato)
        except queue.Empty:
            pass
        self.after(60, self._bombear_cola)

    # -- Confirmaciones desde el hilo trabajador --------------------------------
    def _confirmar_desde_hilo(self, pregunta: str) -> bool:
        """
        Llamado por el motor DESDE EL HILO TRABAJADOR. Encola la pregunta y se
        bloquea hasta que el hilo de Tk muestre el dialogo y conteste.
        """
        if threading.current_thread() is threading.main_thread():
            return messagebox.askyesno("Confirmar", pregunta, parent=self)
        self._evento_respuesta.clear()
        self.cola.put(("preguntar", pregunta))
        self._evento_respuesta.wait()
        return bool(self._respuesta)

    def _responder(self, pregunta: str) -> None:
        self._respuesta = messagebox.askyesno("Confirmar", pregunta, parent=self)
        self._evento_respuesta.set()

    # -- Hilos ------------------------------------------------------------------
    def _bloquear(self, si: bool) -> None:
        self.trabajando = si
        for b in (self.b_jugar, self.b_restaurar, self.b_inyectar, self.b_diag,
                  self.b_cache, self.b_reparar, self.b_ruta):
            b.habilitar(not si)
        if not si:
            self.lbl_estado.configure(text="Listo")

    def _en_hilo(self, tarea: Callable, titulo: str) -> None:
        if self.trabajando:
            return
        self._bloquear(True)
        self.lbl_estado.configure(text=titulo + "…")

        def envoltura():
            try:
                tarea()
            except Exception as exc:
                self.cola.put(("log", f"[ERROR] Excepcion no controlada: {exc}"))
                for l in traceback.format_exc().splitlines():
                    self.cola.put(("log", "   " + l))
            finally:
                self.cola.put(("fin", None))

        threading.Thread(target=envoltura, daemon=True).start()

    # -- Estado ------------------------------------------------------------------
    def _pintar_estado(self, d: dict) -> None:
        self.lbl_admin.configure(
            text="Administrador" if d["admin"] else "Sin privilegios de administrador",
            fg=VERDE if d["admin"] else AMBAR)

        if d["juego"]:
            self.f_juego.poner(d["juego"], VERDE)
        else:
            self.f_juego.poner("no encontrado — usa «Cambiar ruta»", ROJO)

        if d["frosty"]:
            self.f_frosty.poner(d["frosty"], VERDE)
        else:
            self.f_frosty.poner("no encontrado", AMBAR)

        c = d["cache"]
        if not c.get("existe"):
            self.f_cache.poner("sin construir — Frosty la creara al abrirse", TENUE)
        elif c.get("obsoleta"):
            self.f_cache.poner(
                f"OBSOLETA — indexada {c['f_cache']}, datos del juego {c['f_datos']}", ROJO)
        else:
            self.f_cache.poner(f"al dia (indexada {c['f_cache']})", VERDE)

        if d["estado"] == "inyectado":
            self.f_estado.poner("MODS INYECTADOS", AMBAR)
        else:
            self.f_estado.poner("original (vanilla)", VERDE)

    def _recoger_estado(self) -> dict:
        m = self.motor
        c: dict = {}
        if m:
            est = motor_mod.estado_cache_frosty(m.dir_frosty, m.raiz_juego)
            c["existe"] = est["existe"]
            c["obsoleta"] = est["obsoleta"]
            if est["existe"]:
                fmt = lambda t: datetime.fromtimestamp(t).strftime("%d/%m %H:%M")
                c["f_cache"] = fmt(est["fecha_cache"])
                c["f_datos"] = fmt(est["fecha_datos"]) if est["fecha_datos"] else "?"
        return {
            "admin": motor_mod.es_administrador(),
            "juego": m.raiz_juego if m else None,
            "frosty": m.dir_frosty if m else None,
            "cache": c,
            "estado": (m.manifiesto.datos.get("estado") if m else "?"),
        }

    def _refrescar(self) -> None:
        if self.motor:
            self.motor.manifiesto.cargar()
        self.cola.put(("refrescar", self._recoger_estado()))

    # -- Tareas -------------------------------------------------------------------
    def _crear_motor(self, ruta: Optional[str] = None) -> bool:
        destino = motor_mod.localizar_juego(ruta or motor_mod.RUTA_JUEGO)
        if not destino:
            print("[ERROR] No se encontro Need for Speed Heat.")
            print("        Pulsa «Cambiar ruta…» e indica la carpeta del juego.")
            self.motor = None
            return False
        dir_estado = os.path.join(destino, "ModData", "_InjectorState")
        try:
            os.makedirs(dir_estado, exist_ok=True)
            motor_mod._ARCHIVO_LOG = os.path.join(dir_estado, "injector.log")
        except OSError:
            pass
        self.motor = motor_mod.MotorInyeccion(destino)
        print(f"[ OK ]  Juego: {destino}")
        print(f"[ OK ]  Frosty: {self.motor.dir_frosty or 'no encontrado'}")
        return True

    def _tarea_refrescar(self) -> None:
        if not motor_mod.es_administrador():
            print("[AVISO] Sin privilegios de administrador. Si una operacion falla")
            print("        por acceso denegado, cierra y abre como administrador.")
        self._crear_motor()
        self._refrescar()

    def _tarea_diagnostico(self) -> None:
        if not self.motor and not self._crear_motor():
            return
        self.motor.diagnostico()
        self._refrescar()

    def _tarea_inyectar(self) -> None:
        if not self.motor and not self._crear_motor():
            return
        self.motor.inyectar()
        self._refrescar()

    def _tarea_inyectar_lanzar(self) -> None:
        if not self.motor and not self._crear_motor():
            return
        if self.motor.asegurar_inyectado():
            motor_mod.Lanzador(self.motor.raiz_juego).lanzar_por_steam()
        self._refrescar()

    def _tarea_restaurar(self) -> None:
        if not self.motor and not self._crear_motor():
            return
        self.motor.restaurar()
        self._refrescar()

    def _tarea_reparar(self) -> None:
        if not self.motor and not self._crear_motor():
            return
        self.motor.reparar_huerfanos()
        self._refrescar()

    def _tarea_invalidar(self) -> None:
        if not self.motor and not self._crear_motor():
            return
        motor_mod.accion_invalidar_cache(self.motor)
        self._refrescar()

    def _elegir_ruta(self) -> None:
        if self.trabajando:
            return
        carpeta = filedialog.askdirectory(
            title="Selecciona la carpeta de Need for Speed Heat", parent=self)
        if not carpeta:
            return
        carpeta = os.path.normpath(carpeta)
        if not os.path.isfile(os.path.join(carpeta, motor_mod.EJECUTABLE_JUEGO)):
            if not messagebox.askyesno(
                    "Carpeta dudosa",
                    f"No se encontro {motor_mod.EJECUTABLE_JUEGO} ahi dentro.\n\n"
                    "Puede que el juego se este actualizando.\n¿Usarla igualmente?",
                    parent=self):
                return
        self._en_hilo(lambda: (self._crear_motor(carpeta), self._refrescar()),
                      "Cambiando ruta")


# ==============================================================================
# ARRANQUE
# ==============================================================================

def main() -> int:
    if os.name != "nt":
        print("Esta herramienta solo funciona en Windows.")
        return 1
    # El exe se compila con manifiesto uac-admin, asi que normalmente ya llega
    # elevado. Si se ejecuta el .py suelto puede no estarlo: se avisa y se sigue,
    # porque el diagnostico y buena parte de las operaciones funcionan igual.
    app = Aplicacion()
    app.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
