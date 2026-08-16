# Guía de uso — NFS Heat Mod Injector

Para quien quiere que sus mods de Frosty funcionen en **Need for Speed Heat** y no le
apetece pelearse con la consola.

*(English documentation: **[README.md](README.md)**)*

---

## El problema, en una frase

Frosty compila tus mods en `ModData\Default`, pero en muchas instalaciones de Steam
**el botón Launch arranca el juego sin aplicarlos**. El juego abre bien, así que parece
que funcionó — y te pasas la tarde preguntándote por qué tu mod no hace nada.

Esta herramienta cierra ese hueco: mete los archivos compilados por Frosty en el sitio
que el juego realmente lee.

---

## Instalación

No hay instalación. Baja `NFSHeatModInjector.exe` de la
[última release](https://github.com/zetxxs/nfs-heat-mod-injector/releases/latest),
guárdalo donde quieras y doble clic.

### Windows te va a avisar

El programa **no está firmado digitalmente** (un certificado cuesta cientos de euros al
año), así que verás avisos. No los ignores sin entenderlos:

- **SmartScreen**: *"Windows protegió su PC"* → **Más información** → **Ejecutar de
  todas formas**.
- **Windows Defender puede marcarlo.** Y no es una tontería del antivirus: el programa
  mata procesos (`EADesktop`, `Steam`), toma propiedad de archivos con `takeown` e
  `icacls`, y reescribe datos del juego. Ese es exactamente el comportamiento que un
  antivirus busca. La diferencia es que lo hace sobre tu juego y porque tú se lo pides.
- **Pide permisos de administrador** al abrirse. Los necesita para soltar los bloqueos
  de archivo que mantiene EA App.

Si no te fías de un ejecutable de un desconocido — y haces bien en dudar —, ejecútalo
desde el código, que es Python plano y sin dependencias:

```
python nfs_heat_gui.py
```

---

## La ventana

Al abrirse encuentra tu juego y tu Frosty solo. No tienes que escribir ninguna ruta.

![Interfaz](docs/gui.png)

### El panel de arriba

| Fila | Qué significa |
|---|---|
| **Juego** | Dónde está tu juego. Verde = encontrado. Rojo = pulsa **Cambiar ruta…** y señala la carpeta |
| **Frosty** | Dónde está Frosty Mod Manager. Ámbar si no lo encuentra; solo afecta al aviso de caché |
| **Cache** | Si el índice de Frosty sigue coincidiendo con tu juego |
| **Estado** | `original (vanilla)` = juego limpio. `MODS INYECTADOS` = los mods están puestos |

### Los tres estados de la caché

| Estado | Qué significa | Qué hacer |
|---|---|---|
| 🟢 **al día** | El contenido del juego no ha cambiado desde que Frosty indexó | Nada |
| 🔴 **OBSOLETA** | El juego cambió de verdad (parche o reparación) | Pulsa **Invalidar caché de Frosty** |
| 🟡 **sin verificar** | Primera vez que se ejecuta; no hay referencia con la que comparar | Nada, salvo que vengas de un parche |

El estado se decide comparando el **contenido** de los archivos, no las fechas. Una
redescarga de Steam de la misma versión reescribe los 31 GB y cambia todas las fechas
sin cambiar un solo byte: eso **no** deja la caché obsoleta.

### Los botones

| Botón | Qué hace |
|---|---|
| **▶ Inyectar mods y jugar** | Copia los archivos compilados por Frosty al juego y lo lanza por Steam. El que más vas a usar |
| **↺ Restaurar original** | Devuelve los archivos originales desde los respaldos verificados |
| **Solo inyectar** | Lo mismo que el primero pero sin lanzar el juego |
| **Diagnostico** | Enseña todo lo que sabe: rutas, caché, mods detectados, integridad. Solo lee, no toca nada |
| **Invalidar cache de Frosty** | Renombra el índice de Frosty para que lo reconstruya |
| **Reparar instalacion** | Devuelve archivos originales que una herramienta rota se llevó y nunca repuso |
| **Cambiar ruta…** | Señalar la carpeta del juego a mano |

---

## Cómo usarlo, paso a paso

### 1. Deja el juego limpio

Pulsa **Restaurar original**. Si ya estaba limpio, no hace nada. Esto garantiza que los
respaldos que se creen después sean de archivos originales de verdad.

### 2. Compila en Frosty

Abre **Frosty Mod Manager**, arrastra tus mods a la lista de aplicados y pulsa
**Launch**.

> ⚠️ **Aquí es donde falla todo el mundo.** El botón Launch hace dos cosas: compila
> `ModData` **y** arranca el juego. Pero ese arranque **no aplica los mods**. Como el
> juego abre sin errores, parece que ha funcionado.
>
> Deja que abra, **ciérralo enseguida**, y vuelve aquí.

### 3. Inyecta y juega

Pulsa **▶ Inyectar mods y jugar**. La herramienta:

1. Cierra Steam ordenadamente y detiene los servicios de EA
2. Copia los archivos del mod, guardando respaldo verificado de los originales
3. Lanza el juego por Steam

### 4. Cuando termines

Pulsa **↺ Restaurar original**. Hazlo siempre antes de:

- Recompilar en Frosty con otros mods
- Jugar en línea
- Dejar el juego parado una temporada

---

## Reglas que ahorran horas

**Lanza por Steam o desde esta herramienta, nunca desde Frosty** una vez inyectado.
Frosty reinstala su ejecutable proxy al lanzar y puede deshacer la inyección.

**Restaura antes de recompilar.** Si inyectas sobre archivos ya inyectados, los
respaldos dejan de ser originales y pierdes la vuelta atrás.

**Respalda tu partida antes de probar mods de dinero o REP.** Un multiplicador puede
desbordar el saldo y dejarlo en negativo. Ese daño está en la partida, no en los
archivos, así que restaurar **no** lo arregla:

```
Documentos\Need for Speed Heat\SaveGame\savegame\1
```

El juego guarda un solo archivo y lo sobrescribe al salir.

---

## Si algo va mal

### El juego crashea al entrar

NFS Heat no usa el sistema de errores de Windows, así que el Visor de eventos sale
vacío. Los volcados están en:

```
Documentos\Need for Speed Heat\CrashDumps\
```

Léelos con la herramienta incluida:

```
python tools/leer_minidump.py "ruta\al\CrashDump_....mdmp"
```

Si sale `ACCESS_VIOLATION` leyendo una dirección diminuta como `0x00000000000000A7`, es
un puntero nulo: el motor pidió un asset que el mod cambió y no lo encontró. Casi
siempre es **la caché de Frosty desfasada**, no un mod roto. Pulsa **Invalidar caché de
Frosty** y recompila.

### El mod no hace nada

Comprueba en **Diagnostico** que aparece el mod que esperas. Frosty solo mete en
`ModData` los mods de su lista de aplicados: es muy fácil tener uno en la carpeta y
otro distinto compilado.

Y recuerda que muchos mods de recompensa son **multiplicadores**: cambian lo que ganas
por carrera, no tu saldo actual. Tienes que correr una carrera para verlo. Las carreras
de noche pagan REP y las de día pagan dinero.

### Falta algún archivo del juego

Pulsa **Reparar instalacion**, o comprueba la instalación entera contra el manifiesto
del propio juego:

```
python tools/verificar_manifiesto.py
```

Los archivos de idioma que no instalaste salen como ausentes: es normal. Cualquier otra
ausencia bajo `Data\` o `Patch\` significa instalación incompleta — arréglala con
*Verificar integridad* en Steam.

### Restaurar no me devuelve todo a original

Restaura lo que él respaldó. Los archivos que otra herramienta modificó **antes** de
usar esta no tienen copia original en ninguna parte. Para esos, la única vía es
*Verificar integridad* de Steam, y ni eso cubre los archivos que Frosty añade y que no
están en el manifiesto de Steam.

---

## Para entender por qué pasa todo esto

**[DIAGNOSTICO.md](DIAGNOSTICO.md)** cuenta la investigación completa: las tres causas
encadenadas por las que los mods no cargaban, cada una escondiendo a la siguiente.
Merece la pena si quieres saber qué hace la herramienta y por qué.
