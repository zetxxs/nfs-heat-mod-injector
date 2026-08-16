# NFS Heat Mod Injector

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

## Quick start

Requires Windows 10/11, Python 3.8+, and Administrator (it self-elevates via UAC).
`psutil` is optional — it only adds "which process is holding this file".

```bash
git clone https://github.com/zetxxs/nfs-heat-mod-injector.git
cd nfs-heat-mod-injector
python nfs_heat_injector.py --diagnostico --juego "E:\SteamLibrary\steamapps\common\Need for Speed Heat"
```

Edit `RUTA_JUEGO` at the top of the script to your install path, or pass `--juego`
every time.

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
```

| Flag | What it does |
|---|---|
| `--diagnostico` | State report — read-only, safe to run anytime |
| `--inyectar` | Inject the payload and exit |
| `--lanzar` | Inject if needed, then launch via Steam |
| `--restaurar` | Roll back to vanilla from the manifest |
| `--reparar` | Restore vanilla files a broken tool left orphaned |
| `--juego <ruta>` | Game root path |
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
