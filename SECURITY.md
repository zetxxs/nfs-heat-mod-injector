# Security

*Español más abajo.*

## What this tool does that looks alarming

Be suspicious of it. Everything below is real, and it is why an antivirus may flag the
binary:

- **Terminates processes** — `EADesktop`, `EABackgroundService`, `Steam`,
  `FrostyModManager`, the game itself. Necessary because EA App keeps file handles open
  on the game data that must be replaced.
- **Stops Windows services** — `EABackgroundService`, `Origin Client Service`. Same
  reason: they reopen those handles.
- **Takes file ownership** — `takeown` and `icacls` on the specific files it replaces.
- **Rewrites game data** — that is the entire point of the tool.
- **Requests administrator** — it cannot release EA App's locks otherwise.

If Windows Defender flags the release binary, that is not a silly false positive. That
behaviour profile is exactly what heuristics are built to catch. The difference is that
it acts on your own game, on your machine, when you press the button.

## Verifying what you run

The exe is **not code-signed**. If you would rather not trust a stranger's binary — a
reasonable position — run it from source instead. It is plain Python with no
dependencies, and you can read every line:

```bash
python nfs_heat_gui.py
```

To verify a downloaded binary, compare its hash against the one published in the
[release notes](https://github.com/zetxxs/nfs-heat-mod-injector/releases):

```powershell
Get-FileHash NFSHeatModInjector.exe -Algorithm SHA256
```

## What it does not do

- No network access of any kind. It never phones home, checks for updates, or sends
  telemetry.
- No writes outside the game folder, except reading Steam's registry keys and
  `libraryfolders.vdf` to locate the install, and reading crash dumps under `Documents`
  when you ask it to.
- No anti-cheat, DRM or online-play interference. This is single-player file swapping.
- It never deletes without a backup, except for files that did not exist in vanilla
  (Frosty's `mods.json` and its generated `cas_NN.cas`), which are recorded in the
  manifest and removed on restore.

## Reporting a problem

Open an issue. If it is a security concern you would rather not post publicly, use
GitHub's private vulnerability reporting on the Security tab.

Useful to include:

- Output of `python nfs_heat_injector.py --diagnostico`
- `ModData\_InjectorState\injector.log`
- If the game crashed, the output of
  `python tools/leer_minidump.py "<dump>.mdmp"`

---

# Seguridad

## Lo que hace esta herramienta y parece alarmante

Desconfía de ella. Todo lo que sigue es real, y es la razón de que un antivirus pueda
marcar el ejecutable:

- **Mata procesos** — `EADesktop`, `EABackgroundService`, `Steam`, `FrostyModManager` y
  el propio juego. Hace falta porque EA App mantiene abiertos los archivos que hay que
  reemplazar.
- **Detiene servicios de Windows** — por el mismo motivo: vuelven a abrirlos.
- **Toma propiedad de archivos** — `takeown` e `icacls` sobre los que va a sustituir.
- **Reescribe datos del juego** — que es exactamente para lo que sirve.
- **Pide administrador** — sin eso no puede soltar los bloqueos de EA App.

Si Defender marca el binario, **no es un falso positivo tonto**. Ese perfil de
comportamiento es justo el que las heurísticas buscan. La diferencia es que actúa sobre
tu juego, en tu máquina, cuando tú pulsas el botón.

## Verificar lo que ejecutas

El exe **no está firmado**. Si prefieres no fiarte del binario de un desconocido, y
haces bien en dudar, ejecútalo desde el código: es Python plano, sin dependencias, y
puedes leer cada línea.

```bash
python nfs_heat_gui.py
```

Para comprobar un binario descargado, compara su hash con el publicado en las notas de
la release:

```powershell
Get-FileHash NFSHeatModInjector.exe -Algorithm SHA256
```

## Lo que NO hace

- Ningún acceso a red. No llama a casa, no busca actualizaciones, no envía telemetría.
- No escribe fuera de la carpeta del juego, más allá de leer el registro de Steam y
  `libraryfolders.vdf` para localizar la instalación, y leer los volcados de fallo en
  `Documentos` cuando se lo pides.
- No toca anti-cheat, DRM ni juego en línea. Es intercambio de archivos en un juego de
  un jugador.
- Nunca borra sin respaldo, salvo archivos que no existen en vanilla (el `mods.json` de
  Frosty y los `cas_NN.cas` que genera), que quedan anotados en el manifiesto y se
  eliminan al restaurar.

## Reportar un problema

Abre una issue. Si es algo de seguridad que prefieres no publicar, usa el reporte
privado de vulnerabilidades en la pestaña Security.

Conviene adjuntar la salida de `--diagnostico`, el archivo
`ModData\_InjectorState\injector.log`, y si el juego crasheó, la salida de
`tools/leer_minidump.py`.
