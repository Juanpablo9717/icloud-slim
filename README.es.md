# icloud-slim

[English](README.md)

Libera espacio en **Fotos de iCloud** recomprimiendo los videos, fotos, grabaciones de pantalla y capturas que ocupan mucho más de lo necesario. Conserva la **fecha, el orden, el lugar, los álbumes, los favoritos y las personas**, y la pérdida de calidad no se nota al verlos normalmente.

Todo corre en tu Mac. Nada se sube a ningún lado, salvo de vuelta a tu propia fototeca de iCloud.

**Resultado real:** 61 videos de iPhone y Android pasaron de 51,5 GB a 12,8 GB (−75 %), con un VMAF promedio de 97,7. VMAF es un puntaje de calidad visual de 0 a 100; sobre 93 se ve igual al original.

Los comandos, opciones y mensajes del programa están en inglés.

---

## Contenido

- [Qué hace](#qué-hace)
- [Instalación paso a paso](#instalación-paso-a-paso)
- [Uso](#uso)
- [Cortar y retomar](#cortar-y-retomar)
- [Configuración](#configuración)
- [Ayuda y problemas comunes](#ayuda-y-problemas-comunes)
- [Detalles técnicos](#detalles-técnicos)
- [Desinstalar](#desinstalar)

---

## Qué hace

El teléfono graba en tiempo real, así que guarda el video de una forma muy poco eficiente: un minuto de 4K del iPhone puede pesar 400 MB. icloud-slim toma cada video pesado y lo vuelve a empaquetar con calma, de forma eficiente. Es como volver a doblar la ropa de una maleta: la misma ropa en menos espacio.

Con cada ítem:

1. **descarga** el original desde iCloud,
2. lo **comprime** con el chip de video del Mac y revisa el resultado (la duración, la fecha y el lugar tienen que coincidir con el original),
3. **guarda** la copia comprimida en Fotos, en los mismos álbumes y con la misma fecha, lugar, favorito y palabras clave,
4. **guarda una copia del original** en tu Mac, en `~/icloud-slim/originals-backup/<año>/<mes>/`, con su nombre original,
5. **mueve el original a Eliminados recientemente** en tandas de unos 20 GB. macOS te pide confirmar cada tanda y el proceso sigue mientras la ventana espera.

Lo que está en Eliminados recientemente [no cuenta para el espacio de iCloud](https://support.apple.com/es-es/108922), así que el espacio se libera apenas confirmas. Los originales se pueden recuperar ahí durante 30 días, y el respaldo local queda para que decidas si lo guardas o lo borras.

**Lo que NO cambia**

| | |
|---|---|
| Resolución, fluidez, sonido | Iguales (4K sigue en 4K; el audio se copia tal cual) |
| HDR | Se mantiene (HLG de 10 bits) |
| Fecha, hora y orden en la galería | Iguales |
| Lugar | Igual: aparece en el mapa y en la búsqueda por lugar |
| Álbumes, favorito, título, descripción, palabras clave | Se copian |
| Personas y mascotas | Su nombre se agrega como palabra clave, así que la búsqueda por nombre funciona de inmediato. Fotos además vuelve a reconocer las caras sola después de un tiempo |

**Lo que SÍ cambia**

- **Menos detalle fino** en escenas muy cargadas (hojas, agua, confeti, escenas oscuras). Solo se nota si pausas y haces zoom.
- **Dolby Vision pasa a HDR estándar (HLG).** En pantallas Dolby Vision, el brillo de los reflejos puede verse un poco distinto.
- **Las ediciones y los recuerdos** del original no pasan a la copia.
- Los videos en **modo Cine** pierden la opción de cambiar el enfoque después.
- **Las capturas** pasan de PNG/JPEG a HEIC, el formato moderno de Apple. Se ven igual y pesan más o menos la mitad.
- **Las fotos JPEG pesadas** (de una cámara, un Android, un iPhone antiguo…) también pasan a HEIC, con más calidad que las capturas. Cada una se compara con su original y, si se vería peor, se deja como estaba. Las livianas, como las de WhatsApp, no se tocan: ya vienen comprimidas y rehacerlas solo les quitaría calidad.

**Lo que nunca toca:** fotos que ya son HEIC (lo que sacan hoy los iPhone), Live Photos, fotos en movimiento de Android, ráfagas, RAW, fotos editadas en Fotos, videos en cámara lenta, ítems ocultos, álbumes compartidos, la biblioteca compartida de iCloud y todo lo que ya es liviano.

---

## Instalación paso a paso

**Necesitas:** un Mac con chip Apple (M1 o posterior), [Homebrew](https://brew.sh) y Fotos de iCloud activado en la app Fotos. Probado en un M1 Max con macOS 15 Sequoia.

### 1. Descárgalo y abre una terminal en la carpeta

Usa **Terminal** o **iTerm2**. Los avisos de permisos de macOS solo aparecen ahí; las terminales dentro de otras apps (VS Code, la app de Claude, …) no los reciben.

```bash
git clone https://github.com/Juanpablo9717/icloud-slim.git
cd icloud-slim
```

### 2. Instala las herramientas (una vez)

```bash
./icloud-slim install
```

Instala ffmpeg, exiftool y osxphotos, todas gratuitas y de código abierto. Tarda unos minutos.

### 3. Da los permisos (una vez)

```bash
./icloud-slim permissions
```

macOS mostrará dos avisos. Acepta los dos:

| Aviso | Elige |
|---|---|
| **"Terminal" quiere acceder a tus Fotos** | **Permitir acceso completo** (no "Limitar acceso") |
| **"Terminal" quiere controlar "Fotos"** | **Permitir** / **Aceptar** |

Muestra una lista de 3 pasos con qué hacer en cada uno (las ventanas de macOS pueden abrirse detrás de otras). Al final tiene que haber ✓ en los tres y "Todo listo". Si un paso falla, se detiene y te dice cómo arreglarlo.

**Si no aparece ningún aviso, o dice FAILED:**

1. Abre **Configuración del Sistema → Privacidad y seguridad → Fotos** y pon tu terminal en **Acceso completo**.
2. Abre **Configuración del Sistema → Privacidad y seguridad → Automatización**, busca tu terminal y activa **Fotos**.
3. Si tu terminal no aparece en la lista, reinicia el permiso y prueba otra vez:
   ```bash
   tccutil reset Photos com.apple.Terminal        # Terminal
   tccutil reset Photos com.googlecode.iterm2     # iTerm2
   ```
   Después cierra la terminal por completo (⌘Q), ábrela de nuevo y vuelve a correr `./icloud-slim permissions`.

### 4. Mientras corre

- **Deja el Mac enchufado y con la tapa abierta** (o con una pantalla externa). icloud-slim evita que el Mac se duerma solo, pero cerrar la tapa igual lo duerme.
- **No toques Fotos.** Puede abrirse sola; es normal.
- **Atento a la ventana de borrado** cada ~20 GB. Confírmala para liberar el espacio en iCloud.

---

## Uso

### El menú (lo más fácil)

```bash
./icloud-slim
```

Abre un menú estilo arcade: eliges con ↑↓, Enter para entrar, Esc para volver y q para salir.

| Opción | Qué hace |
|---|---|
| VIDEOS, PHOTOS, SCREEN RECORDINGS, SCREENSHOTS, EVERYTHING | Muestra cuántos quedan y cuánto ahorrarías; luego START, START WITH ONLY THE 10 BIGGEST o SHOW THE LIST (simulación) |
| ANALYZE LIBRARY · STATS & ERRORS · DEMO | Los comandos `analyze`, `status` y `demo` |
| SETUP | Una lista de chequeo (herramientas, acceso a Fotos, control de Fotos, terminal correcta). Enter sobre cualquier ✗ lo arregla |
| SETTINGS | Idioma (English/Español) y las opciones de abajo, guardadas para la próxima vez |
| HOW IT WORKS | Pestañas: en resumen (qué ganas y qué cambia), videos, fotos, red de seguridad, detalles técnicos, problemas y teclas |

Con el idioma en Español, el menú muestra estas opciones en español. El HI-SCORE es el espacio ahorrado hasta ahora. Las corridas quedan en gris hasta que SETUP esté todo en ✓.

### Comandos

Todo lo del menú también funciona como comando, útil para scripts:

```bash
./icloud-slim --help        # todos los comandos
./icloud-slim <comando> --help
```

### 1. Mira cuánto ahorrarías (no cambia nada)

```bash
./icloud-slim analyze
```

Muestra qué ocupa espacio (por tipo, origen, resolución y año), qué se puede comprimir, el ahorro estimado y los 15 videos más pesados. El reporte se guarda en `~/icloud-slim/reports/`.

### 2. Prueba con unos pocos

```bash
./icloud-slim process --batch 3
```

Procesa los 3 videos más pesados. Abre Fotos y compáralos: calidad, fecha, lugar, álbum.

### 3. Procesa todo

```bash
./icloud-slim process                       # todos los videos
./icloud-slim process --type photos         # fotos JPEG pesadas → HEIC
./icloud-slim process --type recordings     # grabaciones de pantalla
./icloud-slim process --type screenshots    # capturas de pantalla
./icloud-slim process --type all            # todo
./icloud-slim process --dry-run             # lista lo que procesaría, sin tocar nada
```

Siempre empieza por lo que más ahorra. Mientras corre verás un panel en vivo con:

- el progreso total y el tiempo restante,
- el espacio ahorrado en iCloud, separado en lo ya liberado y lo que se libera en el próximo borrado,
- los ítems en curso (hasta 2 comprimiéndose y 1 descargándose a la vez),
- la velocidad de red,
- los fallidos, que quedan fijos para que no se pierdan con el scroll,
- los recientes, cada uno con su hora, resultado, duración y hace cuánto terminó.

El panel se adapta al tamaño de la ventana. Para verlo sin tocar tu fototeca, corre `./icloud-slim demo`.

### 4. Revisa los resultados

```bash
./icloud-slim status
```

Muestra el espacio ahorrado, el tiempo usado, el estado de cada ítem y los errores. También se guarda en `~/icloud-slim/metrics.md`.

---

## Cortar y retomar

Presiona **Ctrl+C** cuando quieras y luego vuelve a correr **el mismo comando** para seguir donde quedó.

- Cada paso de cada ítem queda anotado apenas termina, así que nada se descarga, comprime ni importa dos veces.
- El ítem que se estaba descargando cuando cortaste se vuelve a descargar desde cero. Si ya estaba descargado, se reutiliza.
- Los fallidos se reintentan solos en la siguiente ejecución, hasta 3 veces. Después de eso, usa `--retry`.
- Las copias comprimidas llevan una marca invisible (metadatos XMP), así que nunca se vuelven a comprimir, ni siquiera desde otro Mac.

---

## Configuración

La pantalla **SETTINGS** del menú cambia estos valores y los guarda en `~/icloud-slim/settings.json`: idioma (inglés por defecto, o español), videos comprimiéndose a la vez, tamaño de cada tanda de borrado, respaldo, VMAF y animación. Las opciones de comando los reemplazan solo para esa corrida.

### Opciones del comando (`process`)

| Opción | Por defecto | Qué hace |
|---|---|---|
| `--type videos\|photos\|recordings\|screenshots\|all` | `videos` | Qué procesar |
| `--batch N` | todo | Solo los N ítems más pesados |
| `--uuid ID …` | | Solo estos ítems |
| `--dry-run` | | Lista lo que procesaría, sin cambiar nada |
| `--parallel N` | `2` | Videos comprimiéndose a la vez. Usa `1` en un Mac antiguo o si lo estás usando para otra cosa. Más de 2 rara vez ayuda: la mayoría de los Mac tiene 1 o 2 codificadores de video |
| `--delete-every GB` | `20` | Pide borrar originales cada tantos GB (también cada 500 ítems) |
| `--no-backup` | | No guarda copia local de los originales |
| `--vmaf` | | Mide la calidad visual de cada video (mucho más lento) |
| `--retry` | | Reintenta los ítems que ya fallaron 3 veces |
| `--no-fun` | | Panel simple, sin la animación espacial |

### Carpeta de trabajo

Todo vive en `~/icloud-slim`. Para usar otra ubicación, por ejemplo un disco externo, define `ICLOUD_SLIM_DIR`:

```bash
ICLOUD_SLIM_DIR=/Volumes/Respaldo/icloud-slim ./icloud-slim process
```

| Ruta | Qué es |
|---|---|
| `originals-backup/<año>/<mes>/` | **Tus originales.** Bórralos cuando estés conforme con el resultado |
| `state.db` | El avance de cada ítem (SQLite). No lo borres mientras sigas procesando |
| `settings.json` | Tus ajustes de SETTINGS del menú |
| `logs/` | El detalle de cada ejecución |
| `reports/`, `metrics.md` | Lo que generan `analyze` y `status` |
| `originals/`, `compressed/` | Temporales; se limpian después de cada ítem |

### Calidad (en `icloud_slim.py`)

| Constante | Por defecto | Significado |
|---|---|---|
| `BITRATE` | 4K → 20 Mbps, 1080p → 8 Mbps, menor → 4 Mbps | Bitrate objetivo según el lado largo del video. Súbelo para más calidad y menos ahorro |
| `MARGIN` | `1.2` | Solo comprime videos al menos 20 % sobre su objetivo |
| `HEIC_QUALITY` | `80` | Calidad de las capturas (0–100) |
| `PHOTO_QUALITY` | `90` | Calidad de las fotos (0–100) |
| `PHOTO_BPP` | `1.2` | Bits por píxel esperados de una foto a `PHOTO_QUALITY`. Un JPEG es candidato si supera `MARGIN` × este valor |
| `PHOTO_MIN_VMAF` | `93` | Una foto con menos puntaje se deja como estaba |
| `DELETE_EVERY_GB`, `DELETE_EVERY_ITEMS` | `20`, `500` | Tamaño de cada tanda de borrado |
| `MAX_ATTEMPTS` | `3` | Reintentos automáticos por ítem |

---

## Ayuda y problemas comunes

**`permissions` dice FAILED o no aparece ningún aviso.** Mira el paso 3 de la [instalación](#3-da-los-permisos-una-vez). Asegúrate de estar en Terminal o iTerm2, no en una terminal dentro de otra app.

**"iCloud download failed … Could not get video for asset".** iCloud no entregó ese original en ese momento (el mensaje muestra el motivo real y cuánto lo intentó). Cuando pasa, icloud-slim reintenta solo a través de la app Fotos, que normalmente sí lo logra. Si igual falla, suele ser temporal, o el ítem todavía se está sincronizando desde otro dispositivo. Se reintenta en la siguiente ejecución. Si uno falla siempre, ábrelo en Fotos y dale play una vez; eso fuerza la descarga. Las VPN pueden hacer mucho más lento a iCloud.

**"Fotos no está lista" o "Se detuvo: fallaron 3 seguidos".** En un Mac donde Fotos es nueva, puede quedarse detrás de una ventana de bienvenida o pasar horas sincronizando con iCloud; mientras tanto no se puede descargar ni importar nada. icloud-slim revisa Fotos antes de empezar, y se detiene si fallan 3 seguidos en vez de fallar toda la noche. Fotos no necesita estar abierta (icloud-slim la abre), pero sí libre: cierra cualquier ventana que muestre y espera a que abajo en Fotos > Biblioteca diga "Actualizado". Luego vuelve a correrlo; no se pierde nada.

**Aparecen muchas ventanas "No se puede importar 1 elemento … Error desconocido" en Fotos.** Fotos se traba después de unos miles de importaciones seguidas y empieza a rechazar todo, incluso archivos sanos. icloud-slim reinicia Fotos solo cada 1.000 importaciones, y de inmediato si rechaza 3 archivos seguidos (eso también cierra esas ventanas). Si sigue rechazando tras reiniciarla, la corrida se detiene en vez de fallar todo. No se pierde nada: el original solo se borra cuando su versión comprimida ya quedó guardada, y lo pendiente se importa en la próxima corrida sin volver a descargarlo.

**Toqué "No permitir" en la ventana de borrado.** No se pierde nada: esos originales siguen en tu fototeca y se te vuelve a preguntar en la siguiente tanda o en la próxima ejecución.

**Veo un ítem dos veces en Fotos.** Seguramente tu fototeca ya tenía un duplicado, y cada copia se procesa por separado. Revisa el álbum **Duplicados** de Fotos (barra lateral → Utilidades) para unirlos.

**"already compressed · skipped".** Ese archivo ya lo hizo icloud-slim (tiene la marca). Solo pasa si se borró `state.db` o si lo corres en otro Mac.

**"skipped: saves less than 10 %".** Ese video ya era eficiente, así que se deja como está.

**¿Eliminados recientemente ocupa mi espacio de iCloud?** No. Según Apple, no cuenta para el espacio de iCloud. Sí ocupa espacio en tu Mac y tu iPhone hasta que lo vacíes o pasen los 30 días.

**¿Puedo usar el Mac mientras corre?** Sí. Si lo notas lento, córtalo y vuelve a correrlo con `--parallel 1`.

**¿Dónde está el log detallado?** En `~/icloud-slim/logs/`. La ruta del log actual se muestra al empezar y al terminar.

---

## Detalles técnicos

### Flujo

```
iCloud ──export PhotoKit (proceso hijo)──▶ originals/<uuid>/           una descarga a la vez, un ítem adelantado
  ──ffmpeg (VideoToolbox) / sips → HEIC──▶ compressed/<uuid>/          hasta --parallel a la vez
  ──exiftool: copia metadatos + marca XMP──▶ verificación
  ──import photoscript + álbumes/keywords/favorito──▶ Fotos            hilo principal
  ──original a originals-backup/──▶ borrado PhotoKit por tandas         proceso hijo, no bloquea
```

Estados en `state.db`: `pending → exported → compressed → imported → replaced → done`, más `skipped`. `imported` se escribe justo después del import, junto con el id del ítem nuevo, así que un ítem nunca se importa dos veces. Los hilos de trabajo descargan y comprimen, cada uno con su propia conexión SQLite. El hilo principal importa, porque AppleScript y el panel en vivo corren ahí. Ctrl+C activa una señal de parada, así que lo interrumpido no cuenta como fallo.

### Selección

| Tipo | Regla |
|---|---|
| `videos` | Bitrate real (`tamaño × 8 / duración`) > `MARGIN` × objetivo |
| `recordings` | La misma regla, para grabaciones de pantalla |
| `photos` | JPEG con bits por píxel (`tamaño × 8 / (ancho × alto)`) > `MARGIN` × `PHOTO_BPP`. Omite Live Photos, ráfagas, pares RAW y fotos editadas (solo se exporta el original, así que las ediciones se perderían) |
| `screenshots` | Capturas en PNG o JPEG |

Las fotos se eligen según cuán comprimidas están, no según de dónde vienen, así que la misma regla sirve para cualquier biblioteca. Después de descargarlo, un JPEG con un MP4 adentro (fotos en movimiento de Android: `MVIMG_`, `PXL_…MP`, Samsung) se omite: en HEIC se perdería el video.

Las capturas se detectan con las marcas `screenshot`/`screen_recording` de osxphotos más la columna `ZASSET.ZISDETECTEDSCREENSHOT` de la base de datos de Fotos. Esa columna también detecta las capturas de Android y WhatsApp, que osxphotos no expone.

### Codificación de video

```
ffmpeg -hwaccel videotoolbox -hwaccel_output_format videotoolbox_vld -i in
       -map 0:v:0 -map 0:a? -c:v hevc_videotoolbox -b:v T -maxrate 1.5T -bufsize 2T [-profile:v main10]
       -c:a copy -tag:v hvc1 -map_metadata 0 -movflags use_metadata_tags+faststart out
```

- Tanto la decodificación como la codificación corren en el motor de medios del chip Apple. Un clip 4K de 30 segundos usa ~1 s de CPU en vez de ~200 s, y por eso vale la pena correr varias compresiones a la vez.
- Si la decodificación por hardware falla, se usa la de software. Si el contenedor no acepta el audio tal cual (algunos códecs de Android), el audio se recodifica a AAC de 192 kbps.
- `hvc1` es necesario para que Fotos, QuickTime e iOS lo reproduzcan. Las fuentes de 10 bits mantienen Main 10 con su color HLG/BT.2020.
- **Lo que se pierde:** el RPU de Dolby Vision (el resultado sigue siendo HDR, como HLG) y las pistas de metadatos temporales de Apple (`mebx`: estabilización y datos del modo Cine).

### Metadatos y verificación

- `exiftool -tagsFromFile original -all:all`, más `Keys:CreationDate` (con zona horaria), `Keys:GPSCoordinates`, `QuickTime:CreateDate` y `FileModifyDate` de forma explícita, con `-api QuickTimeUTC`.
- **Se revisa antes de importar:** la duración (±0,5 s), las mismas dimensiones en las fotos y capturas, que las etiquetas de fecha y GPS sean idénticas (incluido el GPS EXIF), VMAF ≥ `PHOTO_MIN_VMAF` en las fotos (se mide siempre: más o menos un segundo cada una; el HEIC se decodifica antes con `sips` porque ffmpeg solo lee su primer mosaico), y que pese al menos 10 % menos.
- **Se aplica después de importar:** los álbumes, el favorito, el título y la descripción del original, más palabras clave con las del original y los nombres de las personas. También la fecha y el lugar, si Fotos no los tomó del archivo.
- **Marca XMP:** `xmp:CreatorTool=icloud-slim 1.0`, `xmpMM:PreservedFileName`, `xmpMM:DerivedFromDocumentID` (el id del original) y una entrada `xmpMM:History` con parámetros en JSON (antes/después, ajustes, SHA-1 del original, VMAF). Es invisible en Fotos; se lee con `exiftool -XMP:all archivo`.

### Borrado

Los originales reemplazados se borran con `PHAssetChangeRequest.deleteAssets` en un proceso hijo, cuando se juntan 20 GB o 500 ítems. macOS siempre muestra su propia confirmación y no hay API que la salte. La ejecución sigue procesando mientras la ventana está abierta y solo espera la última al final.

### Dependencias

[osxphotos](https://github.com/RhetTbull/osxphotos) (incluye photoscript y rich), [ffmpeg](https://ffmpeg.org) y [exiftool](https://exiftool.org), además de `sips`, `caffeinate` y `nettop`, que vienen con macOS. El script corre dentro del entorno de osxphotos (`osxphotos run`).

### Limitaciones conocidas

- Exporta el **original sin edición**, así que las ediciones hechas en Fotos no pasan.
- Las caras no se pueden asignar desde fuera de Fotos. Fotos las vuelve a detectar en segundo plano y, mientras tanto, los nombres quedan como palabras clave.
- Si el proceso muere en los milisegundos entre un import y la escritura del estado, ese ítem podría importarse dos veces. Lo verías como un duplicado.

---

## Desinstalar

```bash
pipx uninstall osxphotos && brew uninstall ffmpeg exiftool
rm -rf ~/icloud-slim        # ⚠️ también borra originals-backup: mueve antes lo que quieras conservar
```

## Licencia

MIT. Ver [LICENSE](LICENSE).
