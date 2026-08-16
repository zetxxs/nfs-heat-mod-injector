# Contributing

*Español más abajo.*

## Reporting a bug

The single most useful thing you can attach is the diagnostic output. It is read-only
and safe to run at any time:

```bash
python nfs_heat_injector.py --diagnostico
```

Also useful:

| File | Where |
|---|---|
| Injector log | `<game>\ModData\_InjectorState\injector.log` |
| State manifest | `<game>\ModData\_InjectorState\manifiesto.json` |
| Compiled mod list | `<game>\ModData\Default\patch\mods.json` |

**If the game crashed**, NFS Heat does not use Windows Error Reporting, so Event Viewer
will be empty. The dumps are in `Documents\Need for Speed Heat\CrashDumps\`. Decode one:

```bash
python tools/leer_minidump.py "path\to\CrashDump_....mdmp"
```

Paste the exception code and faulting module. An `ACCESS_VIOLATION` reading a tiny
address like `0x00000000000000A7` is a null dereference — usually a stale Frosty cache
rather than a broken mod.

**Before reporting "the mod does nothing"**, check `mods.json` actually lists the mod you
expect. Frosty only compiles what is in its applied list, and having one mod in the
folder and a different one compiled is the most common cause by far.

## Working on the code

No build step, no dependencies. `nfs_heat_injector.py` is the engine and works
standalone; `nfs_heat_gui.py` is a tkinter wrapper around it. `psutil` is optional and
only adds "which process holds this file".

```bash
python -m py_compile nfs_heat_injector.py nfs_heat_gui.py
python nfs_heat_injector.py --diagnostico --sin-elevar
```

Building the exe:

```bash
pyinstaller --onefile --windowed --uac-admin --name NFSHeatModInjector \
  --hidden-import nfs_heat_injector nfs_heat_gui.py
```

### Rules that are not style preferences

These come from a real incident that broke an install. Read
[DIAGNOSTICO.md](DIAGNOSTICO.md) for the full story.

1. **Never descend into a reparse point.** `ModData\Default\Data` is a symlink to the
   real game folder. Any recursive walk must check `es_reparse_point()` and treat links
   as leaves. `shutil.rmtree`, `Remove-Item -Recurse` and `os.walk` with `followlinks`
   are all unsafe here.
2. **Never back up by moving.** Copy, verify the hash, then replace. A move that fails
   halfway leaves the game missing files — that is exactly how the original break
   happened, with no rollback.
3. **Never judge staleness by timestamps.** Steam re-downloading the same build rewrites
   every file and bumps every `mtime` without changing a byte. Compare content.
4. **Keep it locale-independent.** No parsing `tasklist` output, no `"Everyone"` string
   (use the SID `*S-1-1-0`), judge services by exit code. Contributors and users run
   Windows in many languages.
5. **Say "unknown" when it is unknown.** The cache check has three verdicts, not two, on
   purpose. Flagging red without evidence is worse than admitting ignorance.

Comments in the code are in Spanish, matching the existing style. Explain *why*, not
*what* — the non-obvious Win32 behaviour is worth a sentence; a `for` loop is not.

---

# Contribuir

## Reportar un fallo

Lo más útil que puedes adjuntar es la salida del diagnóstico. Es de solo lectura y se
puede ejecutar en cualquier momento:

```bash
python nfs_heat_injector.py --diagnostico
```

También sirven el log en `<juego>\ModData\_InjectorState\injector.log`, el manifiesto de
estado en la misma carpeta, y el `mods.json` de `ModData\Default\patch\`.

**Si el juego crasheó**, NFS Heat no usa el sistema de errores de Windows y el Visor de
eventos sale vacío. Los volcados están en `Documentos\Need for Speed Heat\CrashDumps\`:

```bash
python tools/leer_minidump.py "ruta\al\CrashDump_....mdmp"
```

**Antes de reportar "el mod no hace nada"**, comprueba que `mods.json` lista el mod que
esperas. Frosty solo compila lo que está en su lista de aplicados, y tener uno en la
carpeta y otro distinto compilado es con diferencia la causa más común.

## Tocar el código

Sin compilación ni dependencias. `nfs_heat_injector.py` es el motor y funciona solo;
`nfs_heat_gui.py` es una envoltura en tkinter. `psutil` es opcional.

### Reglas que no son cuestión de estilo

Salen de un incidente real que rompió una instalación. La historia completa está en
[DIAGNOSTICO.md](DIAGNOSTICO.md).

1. **Nunca desciendas en un reparse point.** `ModData\Default\Data` es un enlace a la
   carpeta real del juego. Todo recorrido debe comprobar `es_reparse_point()` y tratar
   los enlaces como hojas.
2. **Nunca respaldes moviendo.** Copia, verifica el hash y reemplaza. Un movimiento que
   falla a mitad deja al juego sin archivos.
3. **Nunca juzgues por fechas.** Steam redescargando la misma build cambia todos los
   `mtime` sin cambiar un byte. Compara contenido.
4. **Independiente del idioma.** Nada de parsear `tasklist` ni usar la cadena `"Todos"`
   (usa el SID `*S-1-1-0`); juzga los servicios por código de salida.
5. **Di "no se sabe" cuando no se sabe.** La comprobación de caché tiene tres veredictos
   a propósito. Marcar rojo sin pruebas es peor que admitir ignorancia.

Los comentarios del código están en español. Explica el *porqué*, no el *qué*.
