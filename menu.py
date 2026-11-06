"""Arcade-style start menu, shown when icloud-slim runs with no command.

icloud_slim.main() calls run(api) with the few functions the menu needs (see fake_api() for the shape).
Full screen with rich: a starfield drifts behind the content, ↑↓ select, ⏎ enter, esc/← back, q quit.
Commands run outside the menu's screen (api.run) and come back to it afterwards.
Self-check without a terminal: python menu.py
"""
import io, os, select, shutil, sqlite3, subprocess, sys, termios, textwrap, threading, time, tty, types
from collections import namedtuple

from rich.cells import cell_len
from rich.console import Console, Group
from rich.live import Live
from rich.text import Text

import i18n
from i18n import t

try:
    import logo
except ImportError:
    logo = None

LOGO_TEXT = "iCLOUD SLIM"
LOGO_PALETTE = "ice"
FPS = 12
TERMINALS = {"Apple_Terminal": ("Terminal", "com.apple.Terminal"), "iTerm.app": ("iTerm2", "com.googlecode.iterm2")}

S = {  # key: (English, Spanish)
    "tagline": ("free your iCloud · keep your memories", "libera tu iCloud · conserva tus recuerdos"),
    "hiscore": ("HI-SCORE", "RÉCORD"),
    "saved": ("SAVED", "AHORRADOS"),
    "keys": ("↑↓ select   ⏎ enter   esc back   q quit", "↑↓ elegir   ⏎ entrar   esc volver   q salir"),
    "keys.side": ("↑↓ select   ←→ change   esc back   q quit", "↑↓ elegir   ←→ cambiar   esc volver   q salir"),
    "keys.page": ("←→ page   ↑↓ scroll   esc back   q quit", "←→ página   ↑↓ desplazar   esc volver   q salir"),
    "more": ("↓ more below", "↓ hay más abajo"),
    "keys.any": ("press any key", "presiona cualquier tecla"),
    "back_to_menu": ("Press any key to return to the menu", "Presiona cualquier tecla para volver al menú"),
    "stopped": ("Stopped.", "Detenido."),
    "waiting_library": ("Waiting for the Photos library to finish loading…", "Esperando a que termine de cargar la biblioteca de Fotos…"),
    "bye": ("See you! Space saved so far: {saved}", "¡Nos vemos! Espacio ahorrado hasta ahora: {saved}"),
    "counting": ("counting", "contando"),
    "left": ("{n} left · ~{gb} to save", "quedan {n} · ~{gb} a ahorrar"),
    "left.short": ("{n} · ~{gb}", "{n} · ~{gb}"),
    "all_done": ("all done ✓", "todo listo ✓"),
    "unknown": ("couldn't count", "no se pudo contar"),
    "videos": ("VIDEOS", "VIDEOS"),
    "photos": ("PHOTOS", "FOTOS"),
    "recordings": ("SCREEN RECORDINGS", "GRABACIONES DE PANTALLA"),
    "screenshots": ("SCREENSHOTS", "CAPTURAS DE PANTALLA"),
    "all": ("EVERYTHING", "TODO"),
    "analyze": ("ANALYZE LIBRARY", "ANALIZAR BIBLIOTECA"),
    "stats": ("STATS & ERRORS", "ESTADÍSTICAS Y ERRORES"),
    "demo": ("DEMO", "DEMO"),
    "setup": ("SETUP", "PREPARACIÓN"),
    "settings": ("SETTINGS", "AJUSTES"),
    "help": ("HOW IT WORKS", "CÓMO FUNCIONA"),
    "exit": ("EXIT", "SALIR"),
    "ready": ("✓ ready", "✓ listo"),
    "attention": ("✗ needs attention", "✗ revisar"),
    "checking": ("checking…", "revisando…"),
    "hint.videos": ("Shrink camera videos: the biggest savings", "Achica los videos de la cámara: el mayor ahorro"),
    "hint.photos": ("Turn heavy JPEG photos into HEIC. Light ones are left alone", "Pasa las fotos JPEG pesadas a HEIC. Las livianas no se tocan"),
    "hint.recordings": ("Shrink screen recordings", "Achica las grabaciones de pantalla"),
    "hint.screenshots": ("Turn screenshots into HEIC, about half the size", "Pasa las capturas a HEIC, pesan la mitad"),
    "hint.all": ("All of the above, biggest first", "Todo lo anterior, primero lo más pesado"),
    "hint.analyze": ("See how much you could save. Changes nothing", "Mira cuánto podrías ahorrar. No cambia nada"),
    "hint.stats": ("Space saved so far, and anything that failed", "Espacio ahorrado hasta ahora y lo que falló"),
    "hint.demo": ("Watch a pretend run. Touches nothing", "Mira una corrida de mentira. No toca nada"),
    "hint.setup": ("Install the tools and give permissions (first time)", "Instala las herramientas y da permisos (la primera vez)"),
    "hint.settings": ("Language, speed, backups…", "Idioma, velocidad, respaldos…"),
    "hint.help": ("What it does to your photos and videos: what you gain, what changes, how it stays safe", "Qué les hace a tus fotos y videos: qué ganas, qué cambia y cómo se mantiene seguro"),
    "hint.exit": ("See you next time!", "¡Hasta la próxima!"),
    "hint.disabled": ("Finish SETUP first", "Primero completa la PREPARACIÓN"),
    # prep
    "prep.summary": ("{n} to process · {before} → ~{after} · biggest first", "{n} por procesar · {before} → ~{after} · primero los más pesados"),
    "prep.nothing": ("Nothing left to do here", "Aquí no queda nada por hacer"),
    "prep.counting": ("Counting what's left…", "Contando lo que falta…"),
    "start": ("START", "EMPEZAR"),
    "start10": ("START WITH ONLY THE 10 BIGGEST", "EMPEZAR SOLO CON LOS 10 MÁS PESADOS"),
    "list": ("SHOW THE LIST", "VER LA LISTA"),
    "back": ("BACK", "VOLVER"),
    "hint.start": ("Stop anytime with Ctrl+C; run it again to continue", "Detén cuando quieras con Ctrl+C; vuelve a correrlo para seguir"),
    "hint.start10": ("A good way to try it first", "Una buena forma de probar primero"),
    "hint.list": ("Only shows what would be done. Changes nothing", "Solo muestra lo que se haría. No cambia nada"),
    "hint.back": ("Back to the previous screen", "Volver a la pantalla anterior"),
    # setup
    "chk.brew": ("Homebrew", "Homebrew"),
    "chk.ffmpeg": ("ffmpeg", "ffmpeg"),
    "chk.exiftool": ("exiftool", "exiftool"),
    "chk.osxphotos": ("osxphotos", "osxphotos"),
    "chk.photos": ("Photos access", "Acceso a Fotos"),
    "chk.automation": ("Control of the Photos app", "Control de la app Fotos"),
    "chk.terminal": ("Running in Terminal or iTerm2", "Corriendo en Terminal o iTerm2"),
    "photos.3": ("Full Access", "Acceso total"),
    "photos.4": ("Limited: needs Full Access", "Limitado: necesita acceso total"),
    "photos.2": ("Denied", "Denegado"),
    "photos.1": ("Restricted", "Restringido"),
    "photos.0": ("Not asked yet", "Aún no se pidió"),
    "hint.chk.ok": ("All good", "Todo bien"),
    "hint.chk.brew": ("⏎ shows how to install Homebrew", "⏎ muestra cómo instalar Homebrew"),
    "hint.chk.tool": ("⏎ installs ffmpeg and exiftool with Homebrew", "⏎ instala ffmpeg y exiftool con Homebrew"),
    "hint.chk.photos": ("⏎ asks macOS for access (choose Full Access)", "⏎ le pide acceso a macOS (elige Acceso total)"),
    "hint.chk.photos_fix": ("⏎ shows how to fix it", "⏎ muestra cómo arreglarlo"),
    "hint.chk.automation": ("Can't be checked silently: ⏎ asks macOS (choose OK)", "No se puede revisar en silencio: ⏎ le pregunta a macOS (elige OK)"),
    "hint.chk.terminal": ("⏎ shows what to do", "⏎ muestra qué hacer"),
    "msg.brew.title": ("INSTALL HOMEBREW", "INSTALA HOMEBREW"),
    "msg.brew": ("Homebrew installs the free tools icloud-slim uses.\nOpen brew.sh in your browser, copy the install command and paste it in this terminal.\nThen come back to SETUP.",
                 "Homebrew instala las herramientas gratuitas que usa icloud-slim.\nAbre brew.sh en el navegador, copia el comando de instalación y pégalo en esta terminal.\nLuego vuelve a PREPARACIÓN."),
    "msg.perm.title": ("GIVE PHOTOS ACCESS", "DA ACCESO A FOTOS"),
    "msg.perm": ("1. Open System Settings → Privacy & Security → Photos and set {term} to Full Access.\n"
                 "2. In Privacy & Security → Automation, find {term} and turn on Photos.\n"
                 "3. Not in the list? Run: tccutil reset Photos {bundle}\n"
                 "4. Quit {term} completely (⌘Q), open it again and come back to SETUP.",
                 "1. Abre Ajustes del Sistema → Privacidad y seguridad → Fotos y dale Acceso total a {term}.\n"
                 "2. En Privacidad y seguridad → Automatización, busca {term} y activa Fotos.\n"
                 "3. ¿No aparece? Ejecuta: tccutil reset Photos {bundle}\n"
                 "4. Cierra {term} del todo (⌘Q), ábrelo de nuevo y vuelve a PREPARACIÓN."),
    "msg.term.title": ("USE TERMINAL OR iTERM2", "USA TERMINAL O iTERM2"),
    "msg.term": ("macOS only asks for Photos permission in Terminal or iTerm2, not in terminals inside other apps.\nOpen Terminal or iTerm2, go to the icloud-slim folder and run ./icloud-slim",
                 "macOS solo pide permiso de Fotos en Terminal o iTerm2, no en terminales dentro de otras apps.\nAbre Terminal o iTerm2, ve a la carpeta de icloud-slim y ejecuta ./icloud-slim"),
    # settings
    "set.lang": ("Language", "Idioma"),
    "set.parallel": ("Videos compressing at once", "Videos comprimiéndose a la vez"),
    "set.delete_every": ("Ask to delete originals every", "Pedir borrar originales cada"),
    "set.backup": ("Keep a backup of originals", "Guardar respaldo de originales"),
    "set.vmaf": ("Measure quality (VMAF)", "Medir calidad (VMAF)"),
    "set.fun": ("Animation", "Animación"),
    "set.workdir": ("Work folder", "Carpeta de trabajo"),
    "on": ("ON", "SÍ"),
    "off": ("OFF", "NO"),
    "hint.set.lang": ("Applies right away", "Se aplica al instante"),
    "hint.set.parallel": ("Your {chip} has {enc} video encoder(s): {rec} is best. Lower it if you use the Mac meanwhile",
                          "Tu {chip} tiene {enc} codificador(es) de video: lo ideal es {rec}. Bájalo si usas el Mac mientras tanto"),
    "hint.set.parallel_more": ("More than {rec} won't be faster on your {chip}", "Más de {rec} no será más rápido en tu {chip}"),
    "recommended": ("recommended", "recomendado"),
    "hint.set.delete_every": ("One macOS confirmation each time", "Una confirmación de macOS cada vez"),
    "hint.set.backup": ("A copy of each original stays on this Mac", "Una copia de cada original queda en este Mac"),
    "hint.set.vmaf": ("Slower", "Más lento"),
    "hint.set.fun": ("Space animation here and while it runs", "Animación espacial aquí y durante la corrida"),
    "hint.set.workdir": ("Backups, logs and progress live here", "Aquí quedan los respaldos, registros y el avance"),
    # how it works. Markup: "## " heading, "+ " stays or gained, "~ " changes, "- " neutral, "> " technical
    "help.1.tab": ("IN SHORT", "EN RESUMEN"),
    "help.1.title": ("WHAT IT DOES, IN ONE MINUTE", "QUÉ HACE, EN UN MINUTO"),
    "help.1": ("""Phones save photos and videos with a lot of room to spare, just in case. icloud-slim saves them again in a modern format that only keeps what your eyes can see. They look the same and take much less space.
## What you gain
+ Videos take about 70 % less space. Heavy photos, 50 to 80 % less
+ Same resolution, same smoothness, same sound
+ Date, place, albums, favorites and people stay in place
## What changes
~ Very fine detail in busy scenes, only visible if you pause and zoom in
~ Edits made to a video, and Memories, don't carry over
~ Photos and screenshots become HEIC, the format iPhones use today
## Nothing is lost for good
+ Each original waits 30 days in Recently Deleted
+ And a copy stays on this Mac, with its original name""",
               """Los celulares guardan fotos y videos con mucho espacio de sobra, por si acaso. icloud-slim los vuelve a guardar en un formato moderno que solo conserva lo que tus ojos ven. Se ven igual y ocupan mucho menos.
## Qué ganas
+ Los videos ocupan cerca de 70 % menos. Las fotos pesadas, entre 50 y 80 % menos
+ La misma resolución, la misma fluidez, el mismo sonido
+ La fecha, el lugar, los álbumes, los favoritos y las personas se mantienen
## Qué cambia
~ El detalle muy fino en escenas cargadas, solo visible si pausas y haces zoom
~ Las ediciones hechas a un video y los Recuerdos no pasan a la copia
~ Las fotos y capturas pasan a HEIC, el formato que usan hoy los iPhone
## Nada se pierde para siempre
+ Cada original espera 30 días en Eliminados recientemente
+ Y una copia queda en este Mac, con su nombre original"""),
    "help.record": ("On your library so far: {n} items, {before} → {after} (−{pct} %)",
                    "En tu biblioteca hasta ahora: {n} ítems, {before} → {after} (−{pct} %)"),
    "help.2.tab": ("VIDEOS", "VIDEOS"),
    "help.2.title": ("WHAT HAPPENS TO YOUR VIDEOS", "QUÉ LES PASA A TUS VIDEOS"),
    "help.2": ("""Each video is saved again with the same format your iPhone uses (HEVC), but sized for what the eye can actually see. The extra data recorded "just in case" is what goes away.
## Stays exactly the same
+ Resolution: 4K stays 4K
+ Smoothness: same frames per second
+ Sound: copied untouched
+ HDR, colors, length, date and place
## Changes
~ A little less fine detail in very busy scenes: leaves, water, confetti, night shots
~ Dolby Vision becomes standard HDR. It still looks bright and colorful
~ Cinematic-mode videos can no longer change focus afterwards
## Never touched
- Slow motion, hidden videos, shared albums
- Videos that are already light: there's nothing to gain""",
               """Cada video se vuelve a guardar con el mismo formato que usa tu iPhone (HEVC), pero ajustado a lo que el ojo realmente ve. Lo que se va son los datos extra grabados "por si acaso".
## Queda exactamente igual
+ La resolución: un 4K sigue siendo 4K
+ La fluidez: los mismos cuadros por segundo
+ El sonido: se copia sin tocarlo
+ El HDR, los colores, la duración, la fecha y el lugar
## Cambia
~ Un poco menos de detalle fino en escenas muy cargadas: hojas, agua, confeti, de noche
~ Dolby Vision pasa a HDR estándar. Se sigue viendo brillante y con color
~ Los videos en modo Cine ya no permiten cambiar el enfoque después
## Nunca se toca
- Cámara lenta, videos ocultos, álbumes compartidos
- Videos que ya son livianos: no hay nada que ganar"""),
    "help.3.tab": ("PHOTOS", "FOTOS"),
    "help.3.title": ("WHAT HAPPENS TO YOUR PHOTOS", "QUÉ LES PASA A TUS FOTOS"),
    "help.3": ("""Heavy JPEG photos (from a camera, an Android phone, an older iPhone) are saved again as HEIC, the format iPhones use today. Same picture, usually half the size or less.
## Stays exactly the same
+ Resolution: every pixel is kept, nothing is resized or cropped
+ Date, place, orientation, camera details, albums, favorites, people
## How we make sure it doesn't look worse
+ Each new photo is compared with its original and gets a score from 0 to 100
+ 93 or more means you can't tell them apart. Below that, the original stays as it was
+ Light photos, like WhatsApp ones, are never touched: redoing them would only lose quality
## Never touched
- Photos already in HEIC: the ones your iPhone takes
- Live Photos, bursts, RAW, and photos you edited in Photos
- Android motion photos: they hide a short video inside
## Screenshots
- Also become HEIC, at a slightly lower quality. Text stays sharp""",
               """Las fotos JPEG pesadas (de una cámara, un Android, un iPhone antiguo) se vuelven a guardar en HEIC, el formato que usan hoy los iPhone. La misma imagen, normalmente con la mitad del peso o menos.
## Queda exactamente igual
+ La resolución: se conserva cada píxel, nada se achica ni se recorta
+ La fecha, el lugar, la orientación, los datos de la cámara, los álbumes, los favoritos, las personas
## Cómo nos aseguramos de que no se vea peor
+ Cada foto nueva se compara con su original y recibe un puntaje de 0 a 100
+ 93 o más significa que no se distinguen. Si queda por debajo, el original se deja como estaba
+ Las fotos livianas, como las de WhatsApp, no se tocan: rehacerlas solo les quitaría calidad
## Nunca se toca
- Fotos que ya son HEIC: las que saca tu iPhone
- Live Photos, ráfagas, RAW y fotos que editaste en Fotos
- Fotos en movimiento de Android: esconden un video corto adentro
## Capturas de pantalla
- También pasan a HEIC, con una calidad un poco menor. El texto se sigue viendo nítido"""),
    "help.4.tab": ("SAFETY", "SEGURIDAD"),
    "help.4.title": ("YOUR SAFETY NET", "TU RED DE SEGURIDAD"),
    "help.4": ("""Nothing is replaced until it passes every check. If anything fails, the original stays exactly as it was.
## 1. Checked before saving
+ Same length (videos) or same size in pixels (photos)
+ Same date and same place
+ At least 10 % smaller, or it's not worth replacing
## 2. Never done twice
+ Each new copy carries an invisible mark. If it comes back, it's skipped
## 3. The original is kept twice
+ 30 days in Recently Deleted, where it no longer uses iCloud space
+ A copy on this Mac, in the work folder, sorted by year and month
## 4. You're in control
+ macOS asks you before each batch of originals is deleted
+ Stop anytime with Ctrl+C. Nothing breaks: it continues next time
+ ANALYZE and SHOW THE LIST change nothing. Try them first
+ START WITH ONLY THE 10 BIGGEST is a good first test""",
               """Nada se reemplaza hasta pasar todas las revisiones. Si algo falla, el original queda exactamente como estaba.
## 1. Se revisa antes de guardar
+ La misma duración (videos) o el mismo tamaño en píxeles (fotos)
+ La misma fecha y el mismo lugar
+ Al menos 10 % más liviano, o no vale la pena reemplazarlo
## 2. Nunca se hace dos veces
+ Cada copia nueva lleva una marca invisible. Si vuelve a aparecer, se salta
## 3. El original se guarda dos veces
+ 30 días en Eliminados recientemente, donde ya no ocupa espacio de iCloud
+ Una copia en este Mac, en la carpeta de trabajo, ordenada por año y mes
## 4. Tú tienes el control
+ macOS te pregunta antes de borrar cada tanda de originales
+ Detén cuando quieras con Ctrl+C. No se rompe nada: sigue la próxima vez
+ ANALIZAR y VER LA LISTA no cambian nada. Pruébalos primero
+ EMPEZAR SOLO CON LOS 10 MÁS PESADOS es una buena primera prueba"""),
    "help.5.tab": ("TECHNICAL", "TÉCNICO"),
    "help.5.title": ("FOR THE TECHNICALLY CURIOUS", "PARA LOS CURIOSOS DE LO TÉCNICO"),
    "help.5": ("""## Videos
> HEVC (H.265) on the Mac's hardware encoder (VideoToolbox), tagged hvc1 so Photos and iOS play it
> Target 20 Mbps at 4K, 8 Mbps at 1080p, 4 Mbps below. iPhones record 4K at about 50 to 100 Mbps
> Only re-encoded if it's at least 20 % above its target. Resolution and frame rate untouched
> 10-bit HDR kept as Main 10 (HLG, BT.2020). Audio stream-copied, AAC 192k only as a fallback
> Lost: the Dolby Vision layer and Apple's timed metadata (Cinematic focus, stabilization data)
## Photos and screenshots
> JPEG or PNG → HEIC with macOS sips: quality 90 for photos, 80 for screenshots
> A photo is a candidate above 1.44 bits per pixel. Lighter ones are skipped as already compressed
> VMAF against the original at 1080p, minimum 93. Same width and height required
> A JPEG with an MP4 inside (motion photo) is detected after download and skipped
## Metadata
> exiftool copies EXIF, GPS, QuickTime and Apple Keys tags. Date and GPS are compared before import
> Albums, favorite, title, caption and keywords re-applied through the Photos app. People's names are added as keywords; Photos re-detects faces on its own
## Safety
> Each item's progress lives in state.db: pending → exported → compressed → imported → replaced → done
> XMP marker: CreatorTool, DerivedFromDocumentID and a History entry with the original's SHA-1
> Originals deleted through PhotoKit in batches of about 20 GB or 500 items""",
               """## Videos
> HEVC (H.265) con el codificador por hardware del Mac (VideoToolbox), etiqueta hvc1 para que Fotos e iOS lo reproduzcan
> Objetivo de 20 Mbps en 4K, 8 Mbps en 1080p y 4 Mbps por debajo. Los iPhone graban 4K a unos 50 a 100 Mbps
> Solo se recodifica si está al menos 20 % sobre su objetivo. Resolución y cuadros por segundo intactos
> El HDR de 10 bits se mantiene como Main 10 (HLG, BT.2020). Audio copiado tal cual; AAC 192k solo como respaldo
> Se pierde: la capa Dolby Vision y los metadatos temporales de Apple (enfoque del modo Cine, datos de estabilización)
## Fotos y capturas
> JPEG o PNG → HEIC con sips de macOS: calidad 90 en fotos, 80 en capturas
> Una foto es candidata sobre 1,44 bits por píxel. Las más livianas se saltan por estar ya comprimidas
> VMAF contra el original a 1080p, mínimo 93. Se exige el mismo ancho y alto
> Un JPEG con un MP4 adentro (foto en movimiento) se detecta después de descargarlo y se salta
## Metadatos
> exiftool copia las etiquetas EXIF, GPS, QuickTime y Keys de Apple. La fecha y el GPS se comparan antes de importar
> Los álbumes, el favorito, el título, la descripción y las palabras clave se aplican con la app Fotos. Los nombres de las personas se agregan como palabras clave; Fotos vuelve a detectar las caras por su cuenta
## Seguridad
> El avance de cada ítem queda en state.db: pending → exported → compressed → imported → replaced → done
> Marca XMP: CreatorTool, DerivedFromDocumentID y una entrada History con el SHA-1 del original
> Los originales se borran con PhotoKit en tandas de unos 20 GB o 500 ítems"""),
    "help.6.tab": ("PROBLEMS", "PROBLEMAS"),
    "help.6.title": ("IF SOMETHING FAILS", "SI ALGO FALLA"),
    "help.6": ("""## No permission prompt, or it says FAILED
- Open SETUP. Use Terminal or iTerm2, not a terminal inside another app
## "Could not get video for asset"
- iCloud didn't hand over that video right now. It's retried on the next run. Playing it once in Photos helps
## You clicked "Don't Allow" on the delete dialog
- Nothing is lost. You'll be asked again with the next batch
## Something shows up twice
- It was probably duplicated before. Check the Duplicates album in Photos
## Want to undo one?
- Find the original in Recently Deleted and recover it, or import its backup from the work folder""",
               """## No aparece el aviso de permisos, o dice FAILED
- Abre PREPARACIÓN. Usa Terminal o iTerm2, no una terminal dentro de otra app
## "Could not get video for asset"
- iCloud no entregó ese video en este momento. Se reintenta en la próxima corrida. Reproducirlo una vez en Fotos ayuda
## Le diste "No permitir" al aviso de borrado
- No se pierde nada. Se vuelve a pedir con la próxima tanda
## Algo aparece dos veces
- Seguramente ya estaba duplicado. Revisa el álbum Duplicados en Fotos
## ¿Quieres deshacer uno?
- Busca el original en Eliminados recientemente y recupéralo, o importa su respaldo desde la carpeta de trabajo"""),
    "help.7.tab": ("KEYS", "TECLAS"),
    "help.7.title": ("KEYS", "TECLAS"),
    "help.7": ("""- ↑ ↓   move, or scroll a long page
- ⏎   choose
- ← →   change a setting, or go to the next page here
- esc   go back
- q   quit
- Ctrl+C during a run stops it safely. Run it again to continue""",
               """- ↑ ↓   moverse, o desplazar una página larga
- ⏎   elegir
- ← →   cambiar un ajuste, o pasar de página aquí
- esc   volver
- q   salir
- Ctrl+C durante una corrida la detiene sin riesgo. Vuelve a correrla para seguir"""),
}
i18n.STRINGS.update({f"menu.{k}": {"en": en, "es": es} for k, (en, es) in S.items()})
tr = lambda key, **kw: t(f"menu.{key}", **kw)

Row = namedtuple("Row", "id label info enabled hint", defaults=("", True, ""))
SEP = Row(None, "")
HELP_PAGES = 7
SETTINGS = {"lang": list(i18n.LANGS), "parallel": [1, 2, 3, 4], "delete_every": [5, 10, 20, 30, 50],
            "backup": [True, False], "vmaf": [False, True], "fun": [True, False]}
# cold palette, no italics or dim text: easy to read on dark terminals
# how-it-works markup → (bullet, bullet style, text style)
MARKS = {"+ ": ("✓ ", "bold #5fe3a1", "#d8f3ff"), "~ ": ("≈ ", "bold #ffcf6b", "#d8f3ff"),
         "- ": ("• ", "#9cc4e0", "#d8f3ff"), "> ": ("› ", "bold #7fdbff", "#b4d2ea")}
STYLE = {"row": "bold #d8f3ff", "sel": "bold #0b1a2a on #7fdbff", "off": "#5c6f80", "info": "#9cc4e0",
         "mark": "bold #7fdbff", "title": "bold #7fdbff", "hint": "#b4d2ea", "keys": "#8aa6bf"}


# ---------- keyboard ----------

ARROWS = {"A": "up", "B": "down", "C": "right", "D": "left"}


def parse_keys(data):
    """Bytes read from the terminal → key names: up/down/left/right/enter/esc/quit/ctrl-c or the character."""
    keys, i = [], 0
    while i < len(data):
        b = data[i:i + 1]
        if b == b"\x1b":
            if data[i + 1:i + 2] in (b"[", b"O") and i + 2 < len(data):
                j = i + 2  # CSI/SS3: skip parameters up to the final byte
                while j < len(data) and not 0x40 <= data[j] <= 0x7E:
                    j += 1
                final = chr(data[j]) if j < len(data) else ""
                keys.append(ARROWS.get(final, "?"))
                i = j + 1
                continue
            keys.append("esc")
        elif b in (b"\r", b"\n", b" "):
            keys.append("enter")
        elif b == b"\x03":
            keys.append("ctrl-c")
        elif b == b"\x7f":
            keys.append("esc")
        elif b in (b"q", b"Q"):
            keys.append("quit")
        else:
            keys.append(b.decode("latin-1"))
        i += 1
    return [k for k in keys if k != "?"]


class Keys:
    """`with keys:` puts the terminal in cbreak mode (no echo, keys one by one; Ctrl+C still interrupts)."""

    def __init__(self):
        self.fd = sys.stdin.fileno() if sys.stdin.isatty() else None
        self.saved = None

    def __enter__(self):
        if self.fd is not None:
            self.saved = termios.tcgetattr(self.fd)
            tty.setcbreak(self.fd)
            termios.tcflush(self.fd, termios.TCIFLUSH)  # forget keys typed while a command was running
        return self

    def __exit__(self, *exc):
        if self.saved:
            termios.tcsetattr(self.fd, termios.TCSADRAIN, self.saved)
            self.saved = None

    def read(self, timeout):
        if self.fd is None:
            time.sleep(timeout)
            return []
        if not select.select([self.fd], [], [], timeout)[0]:
            return []
        data = os.read(self.fd, 64)
        if data == b"\x1b" and select.select([self.fd], [], [], 0.05)[0]:  # Esc alone, or the start of an arrow
            data += os.read(self.fd, 64)
        return parse_keys(data)


# ---------- background ----------

class Starfield:
    """Stars drifting across the whole screen, 🌍 🌕 passing by, the ship flying to 🪐 and a comet 💫 now and then.
    Positions are a pure function of time. Nothing is drawn over the content box."""
    BODY, FLAMES = "≡▶", ("-=", "=-", "~=", "=~")

    def __init__(self, scene=None):
        import random
        rnd = random.Random(7)
        self.stars = [(rnd.random(), rnd.random(), rnd.choice("··..*✦+"), rnd.choice((1.5, 3, 5))) for _ in range(400)]
        self.BODY, self.FLAMES = getattr(scene, "BODY", self.BODY), getattr(scene, "FLAMES", self.FLAMES)

    def render(self, w, h, now, box, fun=True):
        bx, by, bw, bh = box
        cells = [[(" ", None)] * w for _ in range(h)]

        def free(x, y):
            return 0 <= x < w and 0 <= y < h and not (by <= y < by + bh and bx <= x < bx + bw)

        def put(y, x, s, style=None):
            x, n = int(x), cell_len(s)
            if all(free(x + i, y) and cells[y][x + i][0] in " ·.*✦+" for i in range(n)):
                cells[y][x:x + n] = [(s, style)] + [("", None)] * (n - 1)  # "" = 2nd half of a wide emoji

        if not fun:
            now = 0
        for xf, yf, ch, speed in self.stars[:min(len(self.stars), w * h // 30)]:
            style = {"✦": "bright_white", "*": "#7fdbff", "+": "#7b6bff"}.get(ch, "grey50")
            put(int(yf * h), (xf * w - speed * now) % w, ch, style)
        span = w + 16
        for x0, yf, emoji, speed in ((30.0, 0.12, "🌍", 0.7), (120.0, 0.88, "🌕", 0.4)):
            put(int(yf * h), (x0 - speed * now) % span - 8, emoji)
        top, bottom = by, h - by - bh
        lane = top // 2 if top >= 1 else by + bh + bottom // 2 if bottom >= 1 else None
        if lane is not None:
            put(lane, w - 4, "🪐")
            ship_x = (now % 20) / 20 * max(w - 12, 1) if fun else w // 3
            flame = self.FLAMES[int(now * 8) % len(self.FLAMES)]
            for i, (ch, st) in enumerate(zip(flame + self.BODY, ("yellow", "yellow", "bold cyan", "bold cyan"))):
                put(lane, ship_x + i, ch, st)
        if fun and (phase := now % 14) < 2 and top >= 3:  # a comet crosses the top every ~14 s
            put(top // 4, w - phase / 2 * (w + 4), "💫")
        return cells


# ---------- the menu ----------

def fit_line(text, width):
    if text.cell_len > width:
        text = text.copy()
        text.truncate(width)
    return text


class Menu:
    def __init__(self, api):
        self.api = api
        self.mac = getattr(api, "mac", ("Mac", 1, 2))  # (chip, video encoders, recommended parallel)
        self.settings = api.load_settings()
        self.stack = [("main", None)]
        self.sel = {}
        self.page = 0
        self.scroll = 0
        self.record = None  # (items, bytes before, bytes after) replaced so far
        self.action = None  # set by a key handler: "quit" or a function to run outside the menu
        self.checks = None  # {name: True/False/None}
        self.photos_status = None
        self.automation_ok = None
        self.queue = None  # None = not counted, "counting", "error" or [(type, bytes, estimated bytes)]
        self.hiscore = 0
        self.worker = None
        self.stars = Starfield(getattr(api, "scene", None))
        self.logos = {}
        self.t0 = time.monotonic()

    # ----- background work: setup checks, saved space, what's left per type

    def refresh(self):
        if self.worker and self.worker.is_alive():
            return  # ponytail: a refresh asked while one runs is dropped; counts only change after a run
        self.worker = threading.Thread(target=self._refresh, daemon=True)
        self.worker.start()

    def _refresh(self):
        try:
            db = self.api.state().db
            self.record = db.execute("select count(*), coalesce(sum(bytes_before), 0), coalesce(sum(bytes_after), 0) "
                                     "from items where status in ('done','replaced')").fetchone()
            self.hiscore = self.record[1] - self.record[2]
        except (sqlite3.Error, OSError):
            pass
        self.checks = self.check_setup()
        if self.checks["photos"] is False:
            self.queue = None
            return
        self.queue = "counting"
        try:
            q = self.api.build_queue(tuple(self.api.tool_types))
            self.queue = [(typ, p.original_filesize or 0, self.api.estimate(p)) for p, typ in q]
        except Exception:
            self.queue = "error"

    def check_setup(self):
        try:
            import Photos  # pyobjc; asking the status never shows a prompt
            self.photos_status = int(Photos.PHPhotoLibrary.authorizationStatusForAccessLevel_(2))
        except Exception:
            self.photos_status = None
        has = lambda tool: shutil.which(tool) is not None
        return {"brew": has("brew"), "ffmpeg": has("ffmpeg"), "exiftool": has("exiftool"), "osxphotos": True,
                "photos": None if self.photos_status is None else self.photos_status == 3,
                "automation": self.automation_ok, "terminal": os.environ.get("TERM_PROGRAM") in TERMINALS}

    @property
    def ready(self):
        return self.checks is not None and False not in self.checks.values()

    def wait_for_library(self):
        if self.worker and self.worker.is_alive():
            self.api.console.print(f"[dim]{tr('waiting_library')}[/]")
            self.worker.join()

    # ----- numbers

    def left(self, types):
        """(count, bytes, estimated bytes after) still to do for these types, or None if unknown."""
        if not isinstance(self.queue, list):
            return None
        q = [x for x in self.queue if x[0] in types]
        return len(q), sum(x[1] for x in q), sum(x[2] for x in q)

    def types_for(self, key):
        return tuple(self.api.tool_types) if key == "all" else (key,)

    def count_info(self, key, now, w):
        if not self.ready:
            return ""
        if self.queue == "counting":
            return tr("counting") + "." * (int(now * 3) % 4) + " " * (3 - int(now * 3) % 4)
        if self.queue == "error":
            return tr("unknown")
        left = self.left(self.types_for(key))
        if not left:
            return ""
        n, before, after = left
        if not n:
            return tr("all_done")
        n = f"{n / 1000:.1f}K" if n >= 10_000 else f"{n:,}"
        return tr("left" if w >= 72 else "left.short", n=n, gb=self.api.fmt(before - after))

    # ----- screens: each returns (lines above the rows, rows, lines below, footer key)

    def screen_main(self, arg, now, w):
        hi = Text.assemble((tr("hiscore") + "   ", "bold #7fdbff"),
                           (f"{self.api.fmt(self.hiscore)} {tr('saved')}", "bold #e8fbff"))
        setup_info = tr("checking") if self.checks is None else tr("ready") if self.ready else tr("attention")
        run = lambda key: Row(key, tr(key), self.count_info(key, now, w), self.ready, tr(f"hint.{key}"))
        rows = [*(run(k) for k in (*self.api.tool_types, "all")), SEP,
                Row("analyze", tr("analyze"), "", self.ready, tr("hint.analyze")),
                Row("stats", tr("stats"), "", True, tr("hint.stats")),
                Row("demo", tr("demo"), "", True, tr("hint.demo")), SEP,
                Row("setup", tr("setup"), setup_info, True, tr("hint.setup")),
                *(Row(k, tr(k), "", True, tr(f"hint.{k}")) for k in ("settings", "help", "exit"))]
        return [(Text(tr("tagline"), "#9ff0ff"), 2), (hi, 1), (Text(), 3)], rows, [], "keys"

    def screen_prep(self, key, now, w):
        head = [(Text(tr(key), STYLE["title"]), 0)]
        left = self.left(self.types_for(key))
        if left is None:
            head.append((Text(tr("prep.counting"), STYLE["info"]), 0))
        elif left[0] == 0:
            head.append((Text(tr("prep.nothing"), "bold bright_green"), 0))
        else:
            n, before, after = left
            head.append((Text(tr("prep.summary", n=n, before=self.api.fmt(before), after=self.api.fmt(after)),
                              STYLE["info"]), 0))
        top10 = ""
        if left and left[0] > 10:
            q = [x for x in self.queue if x[0] in self.types_for(key)][:10]
            top10 = f"{self.api.fmt(sum(x[1] for x in q))} → ~{self.api.fmt(sum(x[2] for x in q))}"
        can = left is None or left[0] > 0
        rows = [Row("start", tr("start"), "", can, tr("hint.start")),
                Row("start10", tr("start10"), top10 if w >= 72 else "", can, tr("hint.start10")),
                Row("list", tr("list"), "", True, tr("hint.list")),
                Row("back", tr("back"), "", True, tr("hint.back"))]
        return head + [(Text(), 2)], rows, [], "keys"

    def screen_setup(self, arg, now, w):
        c = self.checks or {}
        rows = []
        for name in ("brew", "ffmpeg", "exiftool", "osxphotos", "photos", "automation", "terminal"):
            ok = c.get(name)
            mark = "…" if self.checks is None else "✓" if ok else "?" if ok is None else "✗"
            info = mark
            if name == "photos" and self.photos_status is not None:
                info = f"{tr(f'photos.{self.photos_status}')}  {mark}"
            hint = "chk.ok" if ok else {
                "brew": "chk.brew", "ffmpeg": "chk.tool", "exiftool": "chk.tool",
                "photos": "chk.photos" if self.photos_status in (0, None) else "chk.photos_fix",
                "automation": "chk.automation", "terminal": "chk.terminal"}.get(name, "chk.ok")
            rows.append(Row(name, tr(f"chk.{name}"), info, True, tr(f"hint.{hint}")))
        rows += [SEP, Row("back", tr("back"), "", True, tr("hint.back"))]
        return [(Text(tr("setup"), STYLE["title"]), 0), (Text(), 2)], rows, [], "keys"

    def setting_value(self, key):
        v = self.settings.get(key)
        if key == "lang":
            return i18n.LANGS.get(v, v)
        if key == "parallel":
            return f"{v} · {tr('recommended')}" if v == self.mac[2] else str(v)
        if key == "delete_every":
            return f"{v:g} GB"
        return tr("on") if v else tr("off")

    def screen_settings(self, arg, now, w):
        chip, enc, rec = self.mac
        hint = lambda k: (tr("hint.set.parallel_more" if self.settings["parallel"] > rec else "hint.set.parallel",
                             chip=chip, enc=enc, rec=rec) if k == "parallel" else tr(f"hint.set.{k}"))
        rows = [Row(k, tr(f"set.{k}"), self.setting_value(k), True, hint(k)) for k in SETTINGS]
        path = str(self.api.workdir).replace(os.path.expanduser("~"), "~", 1)
        room = max(w - 50, 8)
        if cell_len(path) > room:
            path = "…" + path[-(room - 1):]
        rows += [Row("workdir", tr("set.workdir"), path, False, tr("hint.set.workdir")), SEP,
                 Row("back", tr("back"), "", True, tr("hint.back"))]
        return [(Text(tr("settings"), STYLE["title"]), 0), (Text(), 2)], rows, [], "keys.side"

    def paragraphs(self, text, w):
        width = max(min(w - 8, 72), 20)
        lines = []
        for i, para in enumerate(text.split("\n")):
            lines += [(Text(x, "bright_white"), 0) for x in textwrap.wrap(para, width)] or [(Text(), 2)]
        return lines

    def guide(self, text, w):
        """How-it-works markup → left-aligned lines (all the same width, so centering the box keeps them aligned)."""
        width = max(min(w - 8, 78), 20)
        lines = []
        for raw in text.split("\n"):
            if raw.startswith("## "):
                if lines:
                    lines.append((Text(), 2))
                lines.append((Text(raw[3:].upper(), "bold #7fdbff"), 0))
                continue
            bullet, b_style, style = MARKS.get(raw[:2], ("", "", "#e8fbff"))
            body = raw[2:] if bullet else raw
            for i, part in enumerate(textwrap.wrap(body, width - len(bullet)) or [""]):
                lines.append((Text.assemble((bullet if i == 0 else " " * len(bullet), b_style), (part, style)), 0))
        for line, _ in lines:
            line.append(" " * max(width - line.cell_len, 0))
        return lines

    def screen_help(self, arg, now, w):
        n = self.page % HELP_PAGES + 1
        tabs = Text()
        for i in range(1, HELP_PAGES + 1):
            tabs.append(f" {tr(f'help.{i}.tab')} ", STYLE["sel"] if i == n else STYLE["info"])
            tabs.append(" ")
        if tabs.cell_len > w - 4:  # narrow terminal: just the current one
            tabs = Text.assemble(("‹ ", STYLE["mark"]), (f" {tr(f'help.{n}.tab')} ", STYLE["sel"]),
                                 (f" › {n}/{HELP_PAGES}", STYLE["mark"]))
        body = self.guide(tr(f"help.{n}"), w)
        if n == 1 and self.record and self.record[0]:
            k, before, after = self.record
            body += [(Text(), 2), (Text(tr("help.record", n=f"{k:,}", before=self.api.fmt(before), after=self.api.fmt(after),
                                           pct=int(100 - after * 100 // max(before, 1))), "bold #5fe3a1"), 0)]
        head = [(tabs, 0), (Text(), 2), (Text(tr(f"help.{n}.title"), "bold #e8fbff"), 0), (Text(), 2)]
        return head, [], body, "keys.page"

    def screen_message(self, msg, now, w):
        title, body = msg
        lines = [(Text(title, STYLE["title"]), 0), (Text(), 2)]
        for line in self.paragraphs(body, w):
            lines += [line, (Text(), 3)]
        return lines, [], [], "keys.any"

    # ----- drawing

    def logo_variants(self, w):
        if w not in self.logos:
            variants = []
            if logo:
                try:
                    variants.append(logo.fit(LOGO_TEXT, w - 4)[1])
                    variants.append(logo.render(LOGO_TEXT, style="small"))
                except Exception:
                    pass
            out = []
            for lines in variants:
                if lines and max(map(cell_len, lines)) <= w:
                    try:
                        out.append(logo.gradient(lines, palette=LOGO_PALETTE).split("\n"))
                    except Exception:
                        out.append([Text(x, STYLE["title"]) for x in lines])
            spaced = " ".join(LOGO_TEXT)
            out.append([Text(spaced if len(spaced) <= w else LOGO_TEXT, STYLE["title"])])
            self.logos[w] = out
        return self.logos[w]

    def content(self, now, w, h):
        """Lines of the centered box for the current screen, already fitted to h."""
        name, arg = self.stack[-1]
        head, rows, below, keys = getattr(self, f"screen_{name}")(arg, now, w)
        lines = list(head)
        sel_line = None
        if rows:
            sel = self.selected(rows)
            lw = max(cell_len(r.label) for r in rows)
            iw = max(cell_len(r.info) for r in rows)
            blink = int(now * 2.5) % 2 == 0
            for i, r in enumerate(rows):
                if r.id is None:
                    lines.append((Text("  " + "─" * (lw + iw + 4 + (4 if name == "settings" else 0)) + "  ", "grey35"), 1))
                    continue
                is_sel = i == sel
                mark = "▶ " if is_sel and blink else "  "
                label = r.label + " " * (lw - cell_len(r.label))
                info = r.info and " " * (iw - cell_len(r.info)) + r.info
                style = STYLE["sel"] if is_sel and r.enabled else STYLE["row"] if r.enabled else STYLE["off"]
                if name == "settings" and is_sel and r.enabled:
                    info = f"‹ {r.info} ›"
                    info = " " * max(iw + 4 - cell_len(info), 0) + info
                line = Text.assemble((mark, STYLE["mark"]), (f" {label} ", style),
                                     ("  " + info.ljust(iw + (4 if name == "settings" else 0)), STYLE["info"]),
                                     (" ◀" if is_sel and blink else "  ", STYLE["mark"]))
                if is_sel:
                    sel_line = len(lines)
                lines.append((line, 0))
                if i + 1 < len(rows) and rows[i + 1].id is not None:
                    lines.append((Text(), 3))  # air between items when the screen is tall enough
            lines.append((Text(), 2))
            r = rows[sel]
            lines.append((Text(r.hint if r.enabled or r.id == "workdir" else tr("hint.disabled"), STYLE["hint"]), 1))
        lines += below
        lines += [(Text(), 3), (Text(tr(keys), STYLE["keys"]), 1)]
        body_h = len(lines)
        for variant in self.logo_variants(w):
            if len(variant) + 1 + body_h <= h:
                break
        lines = [(x, 0) for x in variant] + [(Text(), 3)] + lines
        if sel_line is not None:
            sel_line += len(variant) + 1
        for prio in (3, 2, 1):  # too tall: drop blank lines, then the tagline, then hints
            if len(lines) <= h:
                break
            keep = [(i, x) for i, x in enumerate(lines) if x[1] < prio]
            if sel_line is not None:
                sel_line = next((n for n, (i, _) in enumerate(keep) if i == sel_line), 0)
            lines = [x for _, x in keep]
        lines = [x for x, _ in lines]
        if len(lines) > h:  # still too tall: a window that keeps the selected row visible (or scrolls, in help)
            if name == "help":
                start = self.scroll = min(self.scroll, len(lines) - h)
            else:
                start = max(0, min((sel_line or 0) - h // 2, len(lines) - h))
            more = start + h < len(lines)
            lines = lines[start:start + h]
            if name == "help" and more:
                lines[-1] = Text(tr("more"), STYLE["mark"])
        return [fit_line(x, w) for x in lines]

    def frame(self, now, w, h):
        lines = self.content(now, w, h)
        bh, bw = len(lines), min(w, max((x.cell_len for x in lines), default=0) + 6)
        bx, by = (w - bw) // 2, (h - bh) // 2
        cells = self.stars.render(w, h, now, (bx, by, bw, bh), self.settings.get("fun", True))
        out = []
        for y, row in enumerate(cells):
            t = Text(no_wrap=True, overflow="crop")
            add = lambda part: [t.append(ch, st) for ch, st in part if ch]
            if by <= y < by + bh:
                line = lines[y - by]
                pad = (bw - line.cell_len) // 2
                add(row[:bx])
                t.append(" " * pad)
                t.append_text(line)
                t.append(" " * (bw - pad - line.cell_len))
                add(row[bx + bw:])
            else:
                add(row)
            out.append(t)
        return Group(*out)

    # ----- keys

    def selected(self, rows):
        name = self.stack[-1][0]
        ids = [i for i, r in enumerate(rows) if r.id is not None]
        i = self.sel.get(name, ids[0])
        return i if i in ids else ids[0]

    def current_rows(self):
        name, arg = self.stack[-1]
        return getattr(self, f"screen_{name}")(arg, 0, 100)[1]

    def handle(self, key):
        name, arg = self.stack[-1]
        if key in ("quit", "ctrl-c"):
            self.action = "quit"
            return
        if name == "message":
            self.stack.pop()
            return
        if name == "help" and key in ("left", "right", "enter"):
            self.page += -1 if key == "left" else 1
            self.scroll = 0
            return
        if name == "help" and key in ("up", "down"):
            self.scroll = max(0, self.scroll + (3 if key == "down" else -3))  # content() caps it at the end
            return
        rows = self.current_rows()
        if key in ("up", "down") and rows:
            ids = [i for i, r in enumerate(rows) if r.id is not None]
            pos = ids.index(self.selected(rows))
            self.sel[name] = ids[(pos + (1 if key == "down" else -1)) % len(ids)]
            return
        row = rows[self.selected(rows)] if rows else None
        if name == "settings" and row and row.id in SETTINGS and key in ("left", "right", "enter"):
            return self.change_setting(row.id, -1 if key == "left" else 1)
        if key in ("esc", "left"):
            if len(self.stack) > 1:
                self.stack.pop()
            return
        if key == "enter" and row and row.enabled:
            self.choose(name, arg, row.id)

    def change_setting(self, key, step):
        values = SETTINGS[key]
        cur = self.settings.get(key)
        i = min(range(len(values)), key=lambda n: abs(values[n] - cur) if key in ("parallel", "delete_every")
                else values[n] != cur)
        self.settings[key] = values[(i + step) % len(values)]
        self.api.save_settings(self.settings)

    def outside(self, argv=None, fn=None, library=False):
        """Ask the loop to leave the menu screen and run a command (argv) or a function there."""
        def go():
            if library:
                self.wait_for_library()
            return self.api.run(argv) if argv else fn()
        self.action = go

    def choose(self, name, arg, row):
        push = lambda *s: self.stack.append(s)
        if row == "back":
            self.stack.pop()
        elif name == "main":
            if row in (*self.api.tool_types, "all"):
                push("prep", row)
            elif row in ("setup", "settings", "help"):
                if row == "setup":
                    self.refresh()
                self.page = self.scroll = 0
                push(row, None)
            elif row == "exit":
                self.action = "quit"
            else:
                self.outside({"analyze": ["analyze"], "stats": ["status"], "demo": ["demo"]}[row],
                             library=row == "analyze")
        elif name == "prep":
            argv = ["process", "--type", arg]
            argv += {"start": [], "start10": ["--batch", "10"], "list": ["--dry-run"]}[row]
            self.outside(argv, library=True)
        elif name == "setup":
            self.fix(row)

    def fix(self, row):
        if (self.checks or {}).get(row):
            return
        term, bundle = TERMINALS.get(os.environ.get("TERM_PROGRAM"), ("Terminal / iTerm2", "com.apple.Terminal"))
        message = lambda key, **kw: self.stack.append(("message", (tr(f"msg.{key}.title"), tr(f"msg.{key}", **kw))))
        if row == "brew":
            message("brew")
        elif row in ("ffmpeg", "exiftool"):
            if not (self.checks or {}).get("brew"):
                return message("brew")
            self.outside(fn=lambda: subprocess.run(["brew", "install", "ffmpeg", "exiftool"]))
        elif row == "terminal":
            message("term")
        elif row == "photos" and self.photos_status not in (0, None):
            message("perm", term=term, bundle=bundle)
        elif row in ("photos", "automation"):
            def ask():
                self.api.run(["permissions"])
                self.automation_ok = True  # the command raises if macOS refused control of Photos
            self.outside(fn=ask, library=True)

    # ----- main loop

    def loop(self):
        console = self.api.console
        self.refresh()
        while True:
            with Keys() as keys, Live(console=console, screen=True, auto_refresh=False, transient=True) as live:
                while self.action is None:
                    live.update(self.frame(time.monotonic() - self.t0, console.width, console.height), refresh=True)
                    for k in keys.read(1 / FPS):
                        self.handle(k)
            action, self.action = self.action, None
            if action == "quit":
                return
            self.api.hard_clear()
            try:
                action()
            except KeyboardInterrupt:
                console.print(f"\n[yellow]{tr('stopped')}[/]")
            except SystemExit:
                pass
            except Exception as e:
                console.print(f"\n[red]{type(e).__name__}: {e}[/]")
            console.print(f"\n[bold #7fdbff]{tr('back_to_menu')}[/]")
            with Keys() as keys:
                try:
                    while not keys.read(1):
                        pass
                except KeyboardInterrupt:
                    pass
            self.refresh()  # recount: the run changed what's left


def run(api):
    menu = Menu(api)
    try:
        menu.loop()
    except KeyboardInterrupt:
        pass
    api.hard_clear()
    api.console.show_cursor(True)
    api.console.print(f"[bold #7fdbff]{tr('bye', saved=api.fmt(menu.hiscore))}[/]")


# ---------- self-check (no terminal needed) ----------

def fake_api(log=None):
    """Same shape as the api icloud_slim.main() passes, with fake data. Touches nothing."""
    import random
    rnd = random.Random(3)
    photos = [(types.SimpleNamespace(original_filesize=int(rnd.paretovariate(1.5) * {"videos": 30e6, "photos": 2e6, "recordings": 25e6, "screenshots": 0.4e6}[typ])), typ)
              for typ, n in (("videos", 568), ("photos", 7_200), ("recordings", 31), ("screenshots", 14_700)) for _ in range(n)]
    photos.sort(key=lambda x: -x[0].original_filesize)
    db = sqlite3.connect(":memory:", check_same_thread=False)
    db.execute("create table items(status text, bytes_before int, bytes_after int)")
    db.execute("insert into items values('done', 60000000000, 7600000000)")
    settings = {"lang": "en", "parallel": 2, "delete_every": 20, "backup": True, "vmaf": False, "fun": True}

    def load_settings():
        i18n.LANG = settings["lang"]
        return dict(settings)

    def save_settings(s):
        settings.update(s)
        i18n.LANG = s["lang"]

    def build_queue(tps):
        time.sleep(0.3)
        return [x for x in photos if x[1] in tps]

    def run_cmd(argv):
        (log if log is not None else []).append(argv)
        print("(fake) would run:", " ".join(argv))

    fmt = lambda b: f"{(b or 0) / 1e9:,.1f} GB" if (b or 0) >= 1e9 else f"{(b or 0) / 1e6:,.0f} MB"
    return types.SimpleNamespace(
        run=run_cmd, load_settings=load_settings, save_settings=save_settings, build_queue=build_queue,
        estimate=lambda p: p.original_filesize * 0.3, fmt=fmt, console=Console(), scene=None,
        workdir="/Users/someone/icloud-slim", version="1.0", tool_types=("videos", "photos", "recordings", "screenshots"),
        state=lambda: types.SimpleNamespace(db=db), hard_clear=lambda: None)


def self_check():
    assert parse_keys(b"\x1b[A\x1b[B\x1bOC\x1bOD") == ["up", "down", "right", "left"]
    assert parse_keys(b"\r\n q\x1b\x03") == ["enter", "enter", "enter", "quit", "esc", "ctrl-c"]
    assert parse_keys(b"\x1b[1;5A") == ["up"] and parse_keys(b"\x1b[5~x") == ["x"]
    calls = []
    api = fake_api(calls)
    m = Menu(api)
    m._refresh()
    m.checks = dict.fromkeys(m.checks, True)
    assert m.left(("videos",))[0] == 568 and m.hiscore == 60_000_000_000 - 7_600_000_000
    screens = [("main", None), ("prep", "videos"), ("prep", "all"), ("setup", None), ("settings", None),
               *[("help", None)] * HELP_PAGES, ("message", ("TITLE", tr("msg.perm", term="Terminal", bundle="x")))]
    for lang in ("en", "es"):
        i18n.LANG = lang
        for w, h in ((160, 50), (100, 40), (60, 24), (50, 20)):
            m.logos.clear()
            for i, screen in enumerate(screens):
                m.stack = [("main", None), screen]
                for now in (0, 0.5, 7.3, 13.1):
                    m.page, m.scroll = i, int(now) * 5  # every help page, scrolled too
                    con = Console(width=w, height=h, record=True, file=io.StringIO(), color_system="truecolor")
                    con.print(m.frame(now, w, h))
                    out = con.export_text().rstrip("\n").split("\n")
                    assert len(out) == h, (screen, w, h, len(out))
                    assert all(cell_len(x) <= w for x in out), (screen, w, h)
    # navigation: down to SCREEN RECORDINGS, open it, list it (dry run), back; settings change language
    i18n.LANG = "en"
    m.stack, m.sel = [("main", None)], {}
    for k in ("down", "down", "enter"):
        m.handle(k)
    assert m.stack[-1] == ("prep", "recordings")
    for k in ("down", "down", "enter"):
        m.handle(k)
    m.action()
    assert calls[-1] == ["process", "--type", "recordings", "--dry-run"]
    m.action = None
    m.handle("esc")
    m.stack = [("main", None), ("settings", None)]
    m.handle("right")
    assert i18n.LANG == "es" and api.load_settings()["lang"] == "es"
    m.handle("left")
    m.handle("quit")
    assert m.action == "quit"
    print("menu self-check OK")


def snapshot(w=100, h=40, lang="en"):
    m = Menu(fake_api())
    m._refresh()
    m.checks = dict.fromkeys(m.checks, True)
    i18n.LANG = lang
    con = Console(width=w, height=h, record=True, file=io.StringIO())
    con.print(m.frame(1.0, w, h))
    return con.export_text()


if __name__ == "__main__":
    self_check()
    print(snapshot())
