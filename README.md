# NFS Heat Mod Injector

**English** · [**Español → LEEME.md**](LEEME.md)

Make Frosty mods actually load in **Need for Speed Heat** on Steam + EA App.

Frosty Mod Manager compiles your mods into `ModData\Default`, but on many Steam
installs its **Launch button starts the game without applying them**. The game boots
fine, so it looks like it worked — and you spend an evening wondering why your mod
does nothing. This tool closes that gap: it swaps Frosty's compiled payload into the
files the game actually reads, with verified backups and a one-command way back.

> Single-player game modding on your own installation. Nothing here touches
> anti-cheat, DRM, or online play.

---

## Why not just copy the files yourself

Because `ModData\Default` is not a folder of files. It is a **mirror built out of
symlinks**:

| Entry | What it really is |
|---|---|
| `ModData\Default\Data` | **Symlink** → `<game>\Data` |
| `ModData\Default\Update` | **Broken symlink** (no `Update` folder exists) |
| `ModData\Default\patch\win32\*` | 74 of 76 entries are **links** to vanilla content |
| The actual mod payload | **6 real files**, ~24 MB |

Copy that tree with `xcopy`, `robocopy`, `shutil.copytree` or `Remove-Item -Recurse`
and you follow the `Data` symlink straight into your real game folder. A previous
tool did exactly that on the install this was built for, moved five vanilla files out
of `Data\Win32`, hit a locked file, and died with no rollback — leaving a broken
install that *looked* like a permissions problem.

**This tool never descends into a reparse point.** That is the whole point.

---

## Download (no Python needed)

Grab **`NFSHeatModInjector.exe`** from the [latest release](https://github.com/zetxxs/nfs-heat-mod-injector/releases/latest)
and double-click it. It finds your game, your Frosty install and your cache by itself.

<img alt="GUI" src="docs/gui.png" width="640">

### Windows will warn you. Here's why, honestly.

The exe is **not code-signed** (a certificate costs a few hundred euros a year), so:

- **SmartScreen** shows *"Windows protected your PC"*. Click **More info → Run anyway**.
- **Windows Defender may flag it.** This is not a false positive in the "AV is being
  silly" sense — the tool genuinely terminates processes (`EADesktop`, `Steam`), takes
  ownership of files with `takeown`/`icacls`, and rewrites game data. That is the exact
  behaviour profile of things Defender is built to catch. It just happens to be doing it
  for you, on your own game, at your request.
- It requests **administrator** on launch. It needs it to release the file locks EA App
  holds.

If you would rather not trust a stranger's binary — a reasonable position — **run it from
source instead**. It is one file of plain Python with no dependencies, and you can read
every line of it:

```bash
python nfs_heat_gui.py      # same GUI
python nfs_heat_injector.py # console version
```

Verify the download if you want:

```powershell
Get-FileHash NFSHeatModInjector.exe -Algorithm SHA256
```

The expected hash is published in the release notes.

## Using the app, step by step

*(Guía completa en español: **[LEEME.md](LEEME.md)**)*

Open the exe. It fills in the top panel by itself — you don't type any paths.

### What the status panel tells you

| Row | What it means |
|---|---|
| **Juego** | Where your game is. Green = found. Red = press **Cambiar ruta…** and pick the folder |
| **Frosty** | Where Frosty Mod Manager is. Amber if not found — only matters for the cache check |
| **Cache** | Whether Frosty's asset index still matches your game. See the three verdicts above |
| **Estado** | `original (vanilla)` = clean game. `MODS INYECTADOS` = mods are applied right now |

### What each button does

| Button | What happens |
|---|---|
| **▶ Inyectar mods y jugar** | Copies Frosty's compiled mod files into the game, then launches through Steam. The one you'll use most |
| **↺ Restaurar original** | Puts the original files back from the verified backups. Run this before recompiling in Frosty, and before playing online |
| **Solo inyectar** | Same as the first button but without launching |
| **Diagnostico** | Prints everything it knows: paths, cache state, mod payload, install integrity. Read-only, safe anytime |
| **Invalidar cache de Frosty** | Renames Frosty's index so it rebuilds. Only needed when the game actually changed |
| **Reparar instalacion** | Puts back vanilla files that a broken tool moved out and never returned |
| **Cambiar ruta…** | Point it at the game folder manually |

### The order that works

```
1. Restaurar original          ← leaves a clean base and honest backups
2. Frosty → apply mods → Launch  ← ONLY to compile. Close the game when it opens.
3. Inyectar mods y jugar
```

**Step 2 is where everyone trips.** Frosty's Launch compiles `ModData` *and* starts the
game — but that launch does **not** apply your mods. The game opens fine, so it looks
like it worked. Let it open, close it, then come back and inject.

And once mods are injected, **launch from Steam or from this app — never from Frosty
again.** Frosty reinstalls its proxy exe on launch and can undo the injection.

### Before you play with reward mods

Money and REP multiplier mods write to your save, and an overflow can leave your balance
negative. That damage is in the save file, not in the game files, so restoring won't undo
it. Copy this first:

```
Documents\Need for Speed Heat\SaveGame\savegame\1
```

The game keeps a single save and overwrites it on exit.

## Quick start

Requires Windows 10/11, Python 3.8+, and Administrator (it self-elevates via UAC).
`psutil` is optional — it only adds "which process is holding this file".

```bash
git clone https://github.com/zetxxs/nfs-heat-mod-injector.git
cd nfs-heat-mod-injector
python nfs_heat_injector.py --diagnostico
```

**No configuration needed.** It finds your install by itself:

| What | How it's found |
|---|---|
| The game | Windows uninstall registry (covers Steam *and* EA App) → Steam's `libraryfolders.vdf` + `appmanifest_1222680.acf` → drive scan |
| Frosty Mod Manager | `FrostyModManager.exe` on the game's drive, then other drives and Program Files |
| Frosty's asset cache | `<Frosty>\Caches\NFSHEAT.cache` |

Override either with `--juego "X:\...\Need for Speed Heat"` or `--frosty "X:\FrostyModManager"`.

### The procedure that works

```
1. python nfs_heat_injector.py --restaurar    # clean vanilla baseline
2. Frosty: set your mod list → Launch         # ONLY to compile. Close the game when it opens.
3. python nfs_heat_injector.py --inyectar
4. python nfs_heat_injector.py --lanzar       # via Steam — never from Frosty
```

**Step 2 is the trap.** Frosty's Launch compiles *and* starts the game, but that
launch does not apply the mods. Let it open, close it, then inject.

**Step 4 matters too.** Launching from Frosty afterwards reinstalls its proxy exe and
can undo the injection.

---

## Usage

Interactive menu (self-elevates):

```bash
python nfs_heat_injector.py
```

```
[1] Inject mods and launch (Steam protocol)
[2] Restore original files (vanilla)
[3] Exit
--- Tools ---
[4] Full diagnostic     [5] Repair missing vanilla files
[6] Add Defender exclusion   [7] Release files only   [8] Inject without launching
[9] Invalidate Frosty cache (force reindex)
```

| Flag | What it does |
|---|---|
| `--diagnostico` | State report — read-only, safe to run anytime |
| `--inyectar` | Inject the payload and exit |
| `--lanzar` | Inject if needed, then launch via Steam |
| `--restaurar` | Roll back to vanilla from the manifest |
| `--reparar` | Restore vanilla files a broken tool left orphaned |
| `--invalidar-cache` | Rename Frosty's cache to force a reindex, and offer to delete `ModData` |
| `--juego <ruta>` | Game root path (autodetected if omitted) |
| `--frosty <ruta>` | Frosty folder (autodetected if omitted) |
| `--perfil <nombre>` | Frosty profile (default `Default`) |
| `--modo` | `copia` (default) · `hardlink` · `junction` |
| `--si` | Answer yes to all prompts (unattended) |
| `--forzar` | Re-inject despite the manifest |
| `--sin-elevar` | Skip UAC (debugging) |

Without `--si`, a prompt with closed stdin resolves to **no** — never an implicit yes.

---

## Safety guarantees

- **Never descends into a reparse point** (`FILE_ATTRIBUTE_REPARSE_POINT` via
  `GetFileAttributesW`). The safeguard that prevents the disaster above.
- **Physical identity detection** (`GetFileInformationByHandle` → volume + MFT index):
  if source and destination are the same inode, it skips instead of destroying it.
  This is how it tells Frosty's symlinks apart from real mod files.
- **Backups by hash-verified copy, never by move.** If the copy fails, your game is
  untouched. A move that fails halfway is what breaks installs.
- **Transactional with rollback** — a failure mid-injection reverts what was applied,
  in reverse order.
- **Atomic manifest** (`os.replace`) — stops a second injection from overwriting good
  vanilla backups with already-modded files.
- **Locale-independent** — processes via `CreateToolhelp32Snapshot` (never parses
  `tasklist`), permissions via the SID `*S-1-1-0` (not the localized string
  "Everyone"/"Todos"), services judged by exit code.
- **Real lock detection** — `CreateFileW` with `dwShareMode = 0`, exponential backoff,
  and the culprit process named if `psutil` is installed.

Default mode is **`copia`**, not `hardlink`: a hardlink shares an inode with
`ModData`, so if Frosty recompiles later the game can silently keep stale content.

---

## Troubleshooting

### The game crashes after injecting

NFS Heat does **not** use Windows Error Reporting, so Event Viewer will be empty.
Dumps land in `Documents\Need for Speed Heat\CrashDumps\*.mdmp`.

```bash
python tools/leer_minidump.py "C:\Users\<you>\Documents\Need for Speed Heat\CrashDumps\CrashDump_....mdmp"
```

An `ACCESS_VIOLATION` reading a tiny address like `0x00000000000000A7` is a null
dereference: the engine asked for an asset the mod replaced and got nothing back.
Usually **a stale Frosty cache**, not a broken mod — see below.

### Stale Frosty cache — the one that wastes your evening

Frosty builds an asset index once and reuses it. If the game is **updated, verified or
repaired afterwards**, that index no longer matches the files on disk, and mods compiled
from it reference assets the engine cannot resolve. The game crashes, and it looks like
the mod's fault.

This tool detects it by **content**, not by timestamps. It fingerprints the files that
define the asset index — every `.toc`, `layout.toc`, `initfs_Win32` and `chunkmanifest`
under `Data\` — and compares that fingerprint against the one recorded the last time
Frosty reindexed.

```
Frosty Mod Manager:
   Carpeta : E:\FrostyModManager
   Indexada: 16-08-2026 02:10
   Build   : 10351341
   Estado  : al dia (huella de contenido sin cambios)
```

**Why not just compare timestamps?** Because Steam re-downloading the *same* build
rewrites all 31 GB and bumps every `mtime` without changing a single byte. A
timestamp check calls that stale; it isn't. Verified on exactly that case: after a full
31.5 GB re-download of build `10351341`, every file hashed identical to before.

Three verdicts, and the third one matters:

| Verdict | Meaning |
|---|---|
| `al dia` | Fingerprint unchanged — the cache is valid |
| `OBSOLETA` | Content genuinely changed — reindex before compiling |
| `sin verificar` | First run, no prior reference to compare against |

`sin verificar` exists on purpose. Flagging red without evidence is worse than admitting
the tool doesn't know yet. Only `Data\` is fingerprinted, because the injector never
writes there — including `Patch\` would make the fingerprint change from our own work.

Fix it with:

```bash
python nfs_heat_injector.py --invalidar-cache
```

That renames the cache (reversible — it is never deleted) and offers to remove
`ModData\Default` too, because Frosty reuses an existing build and would otherwise skip
recompiling with the fresh index. Then reopen Frosty, let it reindex, apply mods, Launch.

**Run this after every game update.** Steam patches NFS Heat without warning.

### The mod does nothing / the crash won't go away

Frosty's asset index may have been built against an incomplete install. Check first:

```bash
python tools/verificar_manifiesto.py "E:\SteamLibrary\steamapps\common\Need for Speed Heat"
```

Missing `loc/` files are normal (language packs you didn't install). Missing anything
else under `Data/` or `Patch/` means the install is incomplete — fix it with Steam's
*Verify integrity of game files*, then force Frosty to reindex:

1. Rename `<Frosty>\Caches\NFSHEAT.cache`
2. Delete `ModData\Default` — **with the tool below, never with Explorer**
3. Reopen Frosty (it rebuilds the index), apply mods, Launch

```bash
python tools/borrar_moddata.py "E:\SteamLibrary\steamapps\common\Need for Speed Heat"
```

> Deleting `ModData\Default` with Explorer or `Remove-Item -Recurse` follows the
> `Data` symlink into your real game folder. PowerShell 5.1 has this bug. Use the tool.

### Frosty won't recompile

It reuses `ModData\Default` when it thinks the build is current. Delete it (above) and
it has nothing to reuse.

### `--restaurar` doesn't fully return to vanilla

It restores what it backed up. Files a previous tool modified before this one ran have
no vanilla copy anywhere — only Steam's *Verify integrity* can recover those, and it
won't touch files outside its manifest (`mods.json`, Frosty-added `cas_NN.cas`).

### Back up your save

Reward-multiplier mods write to your save and can overflow the balance into negative.
That damage lives in the save, not in the game files, so restoring won't undo it.

```
Documents\Need for Speed Heat\SaveGame\savegame\1
```

Copy it before each test. The game keeps a single file and overwrites it on exit.

---

## Repo contents

| Path | What |
|---|---|
| `nfs_heat_injector.py` | The injector — single file, stdlib only |
| `tools/leer_minidump.py` | Minidump parser: exception code + faulting module |
| `tools/verificar_manifiesto.py` | Install integrity vs the game's own `mnfst.txt` |
| `tools/borrar_moddata.py` | Symlink-safe `ModData` deletion |
| `DIAGNOSTICO.md` | Full investigation log (Spanish) — the three real causes |

## Compatibility

Built and verified against NFS Heat `1.0.60.7040` (Steam, AppID `1222680`) with EA
App, Frosty Mod Manager, Windows 11, Python 3.14. The Frostbite structure is
game-specific; other titles will need the paths adjusted.

## License

MIT — see [LICENSE](LICENSE).
