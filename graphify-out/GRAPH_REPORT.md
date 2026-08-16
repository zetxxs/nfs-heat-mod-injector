# Graph Report - nfs-heat-injector  (2026-08-16)

## Corpus Check
- Corpus is ~12,142 words - fits in a single context window. You may not need a graph.

## Summary
- 190 nodes · 437 edges · 9 communities
- Extraction: 91% EXTRACTED · 9% INFERRED · 0% AMBIGUOUS · INFERRED: 41 edges (avg confidence: 0.9)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- Console and Menu Actions
- Path Discovery and Win32 Tokens
- Reparse-Safe File Operations
- Injection Engine
- Process and Service Release
- State Manifest and Save Safety
- Stale Cache and Crash Diagnosis
- Symlink Mirror Scanning
- File Lock Detection

## God Nodes (most connected - your core abstractions)
1. `aviso()` - 26 edges
2. `ok()` - 21 edges
3. `MotorInyeccion` - 19 edges
4. `error()` - 17 edges
5. `info()` - 16 edges
6. `Liberador` - 15 edges
7. `accion_invalidar_cache()` - 14 edges
8. `ruta_larga()` - 13 edges
9. `es_reparse_point()` - 13 edges
10. `main()` - 13 edges

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

## Communities (9 total, 0 thin omitted)

### Community 0 - "Console and Menu Actions"
Cohesion: 0.13
Nodes (27): accion_invalidar_cache(), accion_inyectar_y_lanzar(), aviso(), bucle_principal(), confirmar(), error(), info(), invalidar_cache_frosty() (+19 more)

### Community 1 - "Path Discovery and Win32 Tokens"
Cohesion: 0.09
Nodes (30): _bibliotecas_steam(), C, enumerar_procesos(), es_administrador(), habilitar_privilegio(), _juego_por_registro_desinstalacion(), _juego_por_steam(), localizar_frosty() (+22 more)

### Community 2 - "Reparse-Safe File Operations"
Cohesion: 0.11
Nodes (25): Reparse Point Trap, borrar_arbol_moddata(), borrar_seguro(), crear_hardlink(), crear_junction(), es_reparse_point(), obtener_atributos(), quitar_solo_lectura() (+17 more)

### Community 3 - "Injection Engine"
Cohesion: 0.12
Nodes (17): Backup by Move Without Rollback, copiar_verificado(), diagnosticar_bloqueo(), MotorInyeccion, paso(), Comprueba si la cache de Frosty quedo obsoleta y avisa. Un indice construido…, Ubicacion del respaldo .bak, replicando la estructura de carpetas., Inyecta un unico archivo: backup verificado + sustitucion. (+9 more)

### Community 4 - "Process and Service Release"
Cohesion: 0.12
Nodes (12): Liberador, matar_pid(), Quita Solo-Lectura de una lista concreta de rutas., takeown + icacls sobre rutas concretas. Se usa el SID '*S-1-1-0'…, Version recursiva para carpetas completas. takeown /D requiere la letra de…, Consulta si el Acceso Controlado a Carpetas puede estar bloqueando., Secuencia completa de liberacion, acotada a las rutas que se tocaran., Termina un proceso por PID y espera a que el kernel lo libere. (+4 more)

### Community 5 - "State Manifest and Save Safety"
Cohesion: 0.16
Nodes (9): Contaminated Backups, Reward Multiplier Overflow, Frosty Launch Does Not Apply Mods, Restore Compile Inject Launch, NeedForSpeedHeat.orig.exe Proxy, Save Game Backup, Manifiesto, Registra en JSON cada operacion realizada para que la restauracion sea exacta e… (+1 more)

### Community 6 - "Stale Cache and Crash Diagnosis"
Cohesion: 0.16
Nodes (13): Stale Frosty Asset Cache, Null Dereference Crash at 0xA7, Incomplete Game Install, NFS Heat Bypasses Windows Error Reporting, estado_cache_frosty(), fecha_datos_juego(), Devuelve la ruta del archivo de cache de NFS Heat, exista o no., Marca de tiempo del archivo mas reciente en Data\\ y Patch\\, sin seguir… (+5 more)

### Community 7 - "Symlink Mirror Scanning"
Cohesion: 0.18
Nodes (10): Frosty Symlink Mirror, BY_HANDLE_FILE_INFORMATION, Escaner, identidad_archivo(), Recorre ModData\\<perfil> y decide que hacer con cada archivo., Recorrido en profundidad que NUNCA desciende en un reparse point. Esta es la…, Devuelve la lista de operaciones a ejecutar, ya clasificadas., Identidad fisica de un archivo en NTFS (volumen + indice MFT). (+2 more)

### Community 8 - "File Lock Detection"
Cohesion: 0.40
Nodes (5): esperar_desbloqueo(), estado_bloqueo(), Intenta abrir el archivo en modo EXCLUSIVO (dwShareMode = 0). Es la unica forma…, Espera activamente (con backoff) hasta que el archivo pueda abrirse en modo…, Exclusive-Open Lock Detection

## Knowledge Gaps
- **3 isolated node(s):** `LUID_AND_ATTRIBUTES`, `C`, `NFS Heat Mod Injector`
  These have ≤1 connection - possible missing edges or undocumented components.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `aviso()` connect `Console and Menu Actions` to `Path Discovery and Win32 Tokens`, `Injection Engine`, `Process and Service Release`, `State Manifest and Save Safety`, `Symlink Mirror Scanning`, `File Lock Detection`?**
  _High betweenness centrality (0.113) - this node is a cross-community bridge._
- **Why does `Manifiesto` connect `State Manifest and Save Safety` to `Path Discovery and Win32 Tokens`?**
  _High betweenness centrality (0.089) - this node is a cross-community bridge._
- **Why does `Liberador` connect `Process and Service Release` to `Console and Menu Actions`, `Path Discovery and Win32 Tokens`, `Reparse-Safe File Operations`?**
  _High betweenness centrality (0.078) - this node is a cross-community bridge._
- **What connects `LUID_AND_ATTRIBUTES`, `C`, `NFS Heat Mod Injector` to the rest of the system?**
  _3 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Console and Menu Actions` be split into smaller, more focused modules?**
  _Cohesion score 0.12612612612612611 - nodes in this community are weakly interconnected._
- **Should `Path Discovery and Win32 Tokens` be split into smaller, more focused modules?**
  _Cohesion score 0.08901515151515152 - nodes in this community are weakly interconnected._
- **Should `Reparse-Safe File Operations` be split into smaller, more focused modules?**
  _Cohesion score 0.11396011396011396 - nodes in this community are weakly interconnected._