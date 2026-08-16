# Graph Report - nfs-heat-injector  (2026-08-16)

## Corpus Check
- Corpus is ~10,259 words - fits in a single context window. You may not need a graph.

## Summary
- 159 nodes · 355 edges · 8 communities (7 shown, 1 thin omitted)
- Extraction: 93% EXTRACTED · 7% INFERRED · 0% AMBIGUOUS · INFERRED: 25 edges (avg confidence: 0.92)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- Atomic File Swap
- Launch and Privileges
- CLI Entry Point
- Process and Service Release
- Reparse Safety and Crash Diagnosis
- Symlink Mirror Scanning
- State Manifest
- Mod Reward Conflicts

## God Nodes (most connected - your core abstractions)
1. `aviso()` - 23 edges
2. `ok()` - 19 edges
3. `MotorInyeccion` - 17 edges
4. `Liberador` - 15 edges
5. `error()` - 14 edges
6. `info()` - 13 edges
7. `ruta_larga()` - 12 edges
8. `es_reparse_point()` - 11 edges
9. `paso()` - 11 edges
10. `copiar_verificado()` - 11 edges

## Surprising Connections (you probably didn't know these)
- `Never Descends Into Reparse Point` --references--> `es_reparse_point()`  [INFERRED]
  README.md → nfs_heat_injector.py
- `Physical Identity Detection` --references--> `identidad_archivo()`  [INFERRED]
  README.md → nfs_heat_injector.py
- `Copy Mode Default Over Hardlink` --rationale_for--> `crear_hardlink()`  [INFERRED]
  README.md → nfs_heat_injector.py
- `Hash-Verified Copy Backup` --references--> `copiar_verificado()`  [INFERRED]
  README.md → nfs_heat_injector.py
- `Exclusive-Open Lock Detection` --references--> `esperar_desbloqueo()`  [INFERRED]
  README.md → nfs_heat_injector.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Three Chained Root Causes** — diagnostico_trampa_reparse_point, diagnostico_cache_obsoleta_frosty, diagnostico_launch_enganoso [EXTRACTED 1.00]
- **Injector Safety Guarantees** — readme_garantia_reparse, readme_identidad_fisica, readme_backup_hash_verificado, readme_transaccional_rollback, readme_manifiesto_atomico [EXTRACTED 1.00]
- **Crash Diagnosis Toolchain** — diagnostico_sin_wer, diagnostico_crash_null_0xa7, tools_leer_minidump_leer, diagnostico_cache_obsoleta_frosty [INFERRED 0.85]

## Communities (8 total, 1 thin omitted)

### Community 0 - "Atomic File Swap"
Cohesion: 0.08
Nodes (30): Backup by Move Without Rollback, borrar_seguro(), copiar_verificado(), crear_hardlink(), crear_junction(), diagnosticar_bloqueo(), esperar_desbloqueo(), estado_bloqueo() (+22 more)

### Community 1 - "Launch and Privileges"
Cohesion: 0.13
Nodes (20): aviso(), confirmar(), error(), info(), log(), ok(), paso(), Garantiza que el payload este aplicado, sin exigir una reinyeccion. Lanzar el… (+12 more)

### Community 2 - "CLI Entry Point"
Cohesion: 0.14
Nodes (23): accion_inyectar_y_lanzar(), bucle_principal(), C, enumerar_procesos(), es_administrador(), habilitar_privilegio(), Lanzador, LUID (+15 more)

### Community 3 - "Process and Service Release"
Cohesion: 0.10
Nodes (15): Frosty Launch Does Not Apply Mods, Restore Compile Inject Launch, NeedForSpeedHeat.orig.exe Proxy, Liberador, matar_pid(), Termina un proceso por PID y espera a que el kernel lo libere., Responsable de dejar los archivos del juego libres y escribibles., Pide a Steam que se cierre solo (evita corromper su estado). (+7 more)

### Community 4 - "Reparse Safety and Crash Diagnosis"
Cohesion: 0.15
Nodes (15): Stale Frosty Asset Cache, Null Dereference Crash at 0xA7, Incomplete Game Install, NFS Heat Bypasses Windows Error Reporting, Reparse Point Trap, es_reparse_point(), CLAVE DE SEGURIDAD: detecta enlaces simbolicos y junctions SIN seguirlos. Si…, Never Descends Into Reparse Point (+7 more)

### Community 5 - "Symlink Mirror Scanning"
Cohesion: 0.18
Nodes (10): Frosty Symlink Mirror, BY_HANDLE_FILE_INFORMATION, Escaner, identidad_archivo(), Recorre ModData\\<perfil> y decide que hacer con cada archivo., Recorrido en profundidad que NUNCA desciende en un reparse point. Esta es la…, Devuelve la lista de operaciones a ejecutar, ya clasificadas., Identidad fisica de un archivo en NTFS (volumen + indice MFT). (+2 more)

### Community 6 - "State Manifest"
Cohesion: 0.25
Nodes (4): Contaminated Backups, Manifiesto, Registra en JSON cada operacion realizada para que la restauracion sea exacta e…, Atomic State Manifest

## Knowledge Gaps
- **4 isolated node(s):** `LUID_AND_ATTRIBUTES`, `C`, `Reward Multiplier Overflow`, `NFS Heat Mod Injector`
  These have ≤1 connection - possible missing edges or undocumented components.
- **1 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `es_reparse_point()` connect `Reparse Safety and Crash Diagnosis` to `Atomic File Swap`, `Launch and Privileges`, `CLI Entry Point`, `Process and Service Release`, `Symlink Mirror Scanning`?**
  _High betweenness centrality (0.114) - this node is a cross-community bridge._
- **Why does `aviso()` connect `Launch and Privileges` to `Atomic File Swap`, `CLI Entry Point`, `Process and Service Release`, `Symlink Mirror Scanning`, `State Manifest`?**
  _High betweenness centrality (0.113) - this node is a cross-community bridge._
- **Why does `Manifiesto` connect `State Manifest` to `CLI Entry Point`, `Process and Service Release`?**
  _High betweenness centrality (0.106) - this node is a cross-community bridge._
- **What connects `LUID_AND_ATTRIBUTES`, `C`, `Reward Multiplier Overflow` to the rest of the system?**
  _4 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Atomic File Swap` be split into smaller, more focused modules?**
  _Cohesion score 0.08143939393939394 - nodes in this community are weakly interconnected._
- **Should `Launch and Privileges` be split into smaller, more focused modules?**
  _Cohesion score 0.13446969696969696 - nodes in this community are weakly interconnected._
- **Should `CLI Entry Point` be split into smaller, more focused modules?**
  _Cohesion score 0.13538461538461538 - nodes in this community are weakly interconnected._