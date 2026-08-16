# Diagnóstico: por qué los mods de Frosty no funcionaban en NFS Heat (Steam)

Registro completo de la investigación que produjo esta herramienta. Documentado
porque las tres causas reales no eran ninguna de las que se sospechaban al empezar,
y porque cada una escondía a la siguiente.

**Entorno:** Need for Speed Heat, Steam AppID `1222680`, con EA App. Frosty Mod
Manager en `E:\FrostyModManager`. Windows 11.

---

## La hipótesis inicial, y por qué era falsa

El síntoma reportado era que la EA App y Windows Defender bloqueaban
`Data\initfs_Win32` con `UnauthorizedAccessException`, impidiendo reemplazar
archivos o crear junctions.

Lo primero que hizo la investigación fue mirar el disco en vez de asumirlo. Y
`Data\initfs_Win32` **no era el archivo relevante**: en NFS Heat el initfs que
cargan los mods vive en `Patch\initfs_win32`, y en ese momento ya estaba inyectado
correctamente. El bloqueo era un síntoma, no la causa.

---

## Causa 1 — Un inyector previo siguió los enlaces simbólicos de Frosty

Frosty **no genera una copia completa** del juego en `ModData\Default`. Genera un
árbol espejo:

| Elemento | Qué es realmente |
|---|---|
| `ModData\Default\Data` | **Enlace simbólico** → `<juego>\Data` |
| `ModData\Default\Update` | Enlace simbólico **roto** (no existe `<juego>\Update`) |
| `ModData\Default\patch\win32\*` | 74 de 76 entradas son **enlaces** al contenido vanilla |
| Payload real del mod | **6 archivos** de ~24 MB |

Una herramienta anterior recorrió `ModData\Default` **siguiendo los enlaces**. Al
entrar por `ModData\Default\Data` aterrizó dentro de la carpeta `Data` **real** del
juego y trató sus archivos vanilla como si fueran payload del mod. Hizo backup
**moviéndolos**, y se detuvo en seco al chocar con un archivo bloqueado
(`chunks2.toc`). Sin rollback.

Resultado encontrado en disco:

```
Data\Win32\  →  faltaban chunks0.sb, chunks0.toc, chunks1.sb, chunks1.toc, chunks2.sb
                (solo sobrevivía chunks2.toc, justo donde murió el proceso)
```

Los 5 archivos estaban en `ModData\_Backup_Originals\Data\Win32\` y nunca volvieron.

### Backups contaminados

Peor: `_Backup_Originals\patch\initfs_win32`, `layout.toc` y `mods.json` tenían
**SHA-256 idéntico** a las versiones modificadas. Y `mods.json` es un artefacto que
Frosty genera — **no existe en vanilla**. Prueba de que ese backup se tomó *después*
de una inyección: la herramienta se ejecutó dos veces y la segunda pisó los backups
buenos con archivos ya modificados.

**Lección:** el respaldo por movimiento sin rollback convierte un fallo parcial en
una instalación rota. Este inyector respalda por **copia verificada por hash**, y un
manifiesto con estado impide que una segunda ejecución pise los backups.

---

## Causa 2 — La caché de Frosty, construida sobre una instalación incompleta

Con los archivos reparados y el mod inyectado, el juego **crasheaba** al cargar la
partida en el mundo. NFS Heat no usa Windows Error Reporting, así que el Visor de
eventos aparecía vacío. Los volcados estaban en
`Documentos\Need for Speed Heat\CrashDumps\*.mdmp`.

Se escribió un parser de minidumps ([`tools/leer_minidump.py`](tools/leer_minidump.py))
para leerlos sin depender de un depurador. Los dos volcados eran idénticos:

```
Excepción : 0xC0000005 ACCESS_VIOLATION
Operación : LECTURA sobre 0x00000000000000A7
Módulo    : NeedForSpeedHeat.exe + 0x590051
```

Leer en `0xA7` es un **desreferenciado de puntero nulo**: el motor pidió un objeto,
recibió `NULL` y accedió a un campo 167 bytes dentro sin comprobar. Firma típica de
un asset que el mod modificó y el motor no pudo resolver.

### La pista que lo resolvió

El usuario señaló que **esos mismos mods funcionaban en una cuenta de EA App**. Eso
descartaba que el mod estuviera roto. La cronología reveló el resto:

```
12-08  19:33   Frosty construye NFSHEAT.cache (137 MB)
   ...
16-08  00:38   Data\ solo contiene Win32   ← sin initfs_Win32, layout.toc ni chunkmanifest
16-08  01:01   se reparan los 5 chunks de Data\Win32
16-08  01:05   Steam (verificar integridad) repone initfs_Win32, layout.toc, chunkmanifest
```

**Frosty indexó el juego cuando a `Data\` le faltaban los archivos base.** Esos tres
no estaban en `_Backup_Originals` ni los tocó la herramienta rota: llevaban ausentes
desde antes, probablemente desde la instalación. Un índice de assets construido sobre
una instalación incompleta produce `.toc`/`.sb` que referencian algo inexistente.

No era una diferencia entre las builds de Steam y EA. Era la caché.

### La solución

1. Renombrar `E:\FrostyModManager\Caches\NFSHEAT.cache` → Frosty reindexa de cero.
2. Borrar `ModData\Default` con [`tools/borrar_moddata.py`](tools/borrar_moddata.py),
   porque si no Frosty reutiliza el build viejo y se salta la recompilación.
3. Recompilar en Frosty e inyectar.

Resultado: de crashear a los 2 minutos con 2.2 GB de RAM, a correr estable con 4.4 GB.

---

## Causa 3 — El botón Launch de Frosty engaña

Tres rondas se perdieron creyendo que el mod estaba probado cuando no lo estaba.
El botón **Launch** de Frosty hace dos cosas:

1. **Compila** `ModData` ← esto sí se necesita
2. **Lanza el juego** ← y ese arranque **no aplica los mods**

Como el juego arranca sin errores, parece que funcionó. Pero el mod se queda en
`ModData` y nunca llega a los archivos que el juego lee. Verificado con el juego
en marcha: sin `-dataPath`, sin DLL inyectada, y archivos de datos vanilla en disco.

### El proxy `NeedForSpeedHeat.orig.exe`

Al pulsar Launch, Frosty renombra el juego real a `NeedForSpeedHeat.orig.exe`
(336 MB) e instala un stub de 117 KB como `NeedForSpeedHeat.exe`. Al cerrarse
revierte el cambio y aparca el stub como `NeedForSpeedHeat.old`.

Esto destapó un **bug en el propio inyector**: su lista de procesos solo conocía
`NeedForSpeedHeat.exe`, así que con el juego corriendo bajo el nombre `.orig` lo
daba por cerrado y habría escrito sobre archivos en uso. Corregido con la lista
`EJECUTABLES_JUEGO`.

---

## El procedimiento que funciona

```
1. --restaurar                       deja el juego vanilla y los backups limpios
2. Frosty: configurar mods → Launch  SOLO para compilar; cierra el juego al abrir
3. --inyectar
4. --lanzar                          por Steam, NUNCA desde Frosty
```

## Verificado funcionando (16-08-2026)

| Mod | Resultado |
|---|---|
| `10000x Rep & Cash` (Colezane) | estable 4 min / 4.4 GB tras reindexar la caché |
| `base money changer` | estable 4 min / 4.3 GB |

---

## Cosas que se descartaron por el camino

- **`Core\` y `__overlay\`** — solo DLLs de activación y el overlay de Steam. Inertes.
- **Los 74 enlaces de ModData** — todos apuntaban correctamente al `patch` del juego.
- **Windows Defender** — Acceso Controlado a Carpetas estaba desactivado. Nunca fue el problema.
- **48 archivos "ausentes" del manifiesto** — todos paquetes de idioma no instalados. Normal.
- **Permisos** — las carpetas siempre fueron escribibles por el usuario. `takeown`/`icacls`
  nunca hicieron falta. La única parte de la maquinaria de liberación que sí se ejercitó
  fue el fallback de servicios, cuando `TerminateProcess` no pudo con `EABackgroundService`
  sin elevación y `sc.exe stop` sí.

## Conflictos entre mods

Las rutas de assets se pueden extraer del `.fbmod` como cadenas legibles:

| Mod | Assets que toca |
|---|---|
| `10000x Rep & Cash` | `cash_globalawardmultiplier`, `rep_globalawardmultiplier`, `heat_globalawardmultiplier` |
| `base money changer` | `levelbasedbankrewardtable`, `collectibles_bankrewardmultiplier` |

No se solapan, así que Frosty los compila sin conflicto. Pero **apilarlos es mala
idea**: uno multiplica ×10000 lo que el otro infla, y el desbordamiento de entero
resultante deja el saldo en negativo — daño que se escribe en la partida y que
restaurar archivos no arregla. Respalda `Documentos\Need for Speed Heat\SaveGame\savegame\1`
antes de cada prueba.
