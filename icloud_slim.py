"""icloud-slim: shrink videos, photos, screen recordings and screenshots in Apple Photos (iCloud)
while keeping date, location, albums, favorites, keywords and people's names.

Not run directly: use ./icloud-slim <command> (it runs this file through `osxphotos run`).

Each original is replaced: the compressed copy goes into the same albums, the original moves to
Recently Deleted (macOS asks to confirm) and a copy of it is kept in BACKUP_DIR under its own name.
Originals are deleted in small batches so iCloud never has to hold both versions of everything.
Every compressed file carries an XMP marker (tool, date, original, before/after) so it's never redone.
"""
import argparse, contextlib, datetime as dt, fcntl, hashlib, json, logging, os, random, re, shutil, signal, sqlite3, subprocess, sys, tempfile, threading, time, types
from collections import defaultdict, deque
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from pathlib import Path

import osxphotos, photoscript
with contextlib.suppress(ImportError):  # photoscript kills Photos on any 2-min AppleScript timeout: we handle timeouts
    from photoscript.script_loader import configure_run_script
    configure_run_script(retry_enabled=False)
from osxphotos import ExportOptions, PhotoExporter
from rich.cells import cell_len  # rich ships with osxphotos
from rich.console import Console, Group
from rich.live import Live
from rich.markdown import Markdown
from rich.align import Align
from rich.panel import Panel
from rich.progress_bar import ProgressBar
from rich.table import Table
from rich.text import Text

sys.path.insert(0, str(Path(__file__).resolve().parent))  # `osxphotos run` doesn't add this folder: our modules live here
import i18n
from i18n import t as tr  # not `t`: that name is used for item types and times all over

i18n.STRINGS.update({
    # item types and the reasons evaluate() gives (stored in English, translated when shown)
    "type.videos": {"en": "videos", "es": "videos"},
    "type.recordings": {"en": "recordings", "es": "grabaciones"},
    "type.screenshots": {"en": "screenshots", "es": "capturas"},
    "type.photos": {"en": "photos", "es": "fotos"},
    "reason.not applicable": {"en": "not applicable", "es": "no aplica"},
    "reason.in trash": {"en": "in trash", "es": "en la papelera"},
    "reason.hidden": {"en": "hidden", "es": "oculto"},
    "reason.shared album": {"en": "shared album", "es": "álbum compartido"},
    "reason.shared library": {"en": "shared library", "es": "biblioteca compartida"},
    "reason.slow motion": {"en": "slow motion", "es": "cámara lenta"},
    "reason.already compressed": {"en": "already compressed", "es": "ya comprimido"},
    "reason.already HEIC or other format": {"en": "already HEIC or other format", "es": "ya es HEIC u otro formato"},
    "reason.no duration": {"en": "no duration", "es": "sin duración"},
    "reason.already light": {"en": "already light", "es": "ya es liviano"},
    "reason.live photo": {"en": "Live Photo", "es": "Live Photo"},
    "reason.burst": {"en": "burst", "es": "ráfaga"},
    "reason.RAW": {"en": "RAW", "es": "RAW"},
    "reason.edited": {"en": "edited in Photos", "es": "editada en Fotos"},
    # errors users see (failed list, status)
    "err.download": {"en": "iCloud download failed after {m}:{s:02d}: {why} (will retry)",
                     "es": "la descarga de iCloud falló tras {m}:{s:02d}: {why} (se reintentará)"},
    "err.timeout": {"en": "timed out after {m} min", "es": "se agotó el tiempo tras {m} min"},
    "err.no_file": {"en": "no file", "es": "sin archivo"},
    "err.duration": {"en": "verification: duration mismatch", "es": "verificación: la duración no coincide"},
    "err.dimensions": {"en": "verification: dimensions mismatch", "es": "verificación: las dimensiones no coinciden"},
    "err.metadata": {"en": "original kept: the compressed copy would lose or change its date/location {a} → {b}",
                     "es": "se dejó el original: la copia comprimida perdería o cambiaría su fecha/lugar {a} → {b}"},
    "err.marker": {"en": "already compressed by {tool}", "es": "ya comprimido por {tool}"},
    "err.no_shrink": {"en": "saves less than 10 %", "es": "ahorra menos del 10 %"},
    "log.photos_restart": {"en": "Restarting Photos (it gets slow after many imports)…",
                           "es": "Reiniciando Fotos (se pone lenta tras muchas importaciones)…"},
    "err.import_timeout": {"en": "Photos didn't finish saving it in {m} min; retried on the next run",
                           "es": "Fotos no terminó de guardarlo en {m} min; se reintenta en la próxima corrida"},
    "err.import_canceled": {"en": "Photos canceled the import (it was closed, or busy with a window); retried on the next run",
                            "es": "Fotos canceló la importación (se cerró o estaba ocupada con una ventana); se reintenta en la próxima corrida"},
    "err.import": {"en": "Photos did not accept the file", "es": "Fotos no aceptó el archivo"},
    "err.photos_stuck": {"en": "Photos stopped accepting files: stopping. Quit and reopen Photos, then run again "
                               "(everything resumes where it stopped).",
                         "es": "Fotos dejó de aceptar archivos: se detiene. Cierra y abre Fotos y vuelve a correrlo "
                               "(todo sigue donde quedó)."},
    "err.motion": {"en": "motion photo (has a short video inside)", "es": "foto en movimiento (trae un video corto adentro)"},
    "err.quality": {"en": "would look worse (VMAF {score})", "es": "se vería peor (VMAF {score})"},
    # live panel
    "panel.progress": {"en": "Progress", "es": "Progreso"},
    "panel.count": {"en": "{done} of {n} {title}", "es": "{done} de {n} {title}"},
    "panel.bytes": {"en": " · {done} of {total} · biggest first", "es": " · {done} de {total} · primero los más pesados"},
    "panel.time_left": {"en": "Time left ", "es": "Tiempo restante "},
    "panel.elapsed": {"en": " · elapsed {t}", "es": " · transcurrido {t}"},
    "panel.saved": {"en": "iCloud space saved  ", "es": "Espacio ahorrado en iCloud  "},
    "panel.freed": {"en": " already freed", "es": " ya liberado"},
    "panel.more_after": {"en": " more after the next deletion", "es": " más tras el próximo borrado"},
    "panel.now": {"en": "Now", "es": "Ahora"},
    "step.download": {"en": "Download", "es": "Descargar"},
    "step.compress": {"en": "Compress", "es": "Comprimir"},
    "step.save": {"en": "Save to Photos", "es": "Guardar en Fotos"},
    "panel.waiting_compress": {"en": "waiting to compress", "es": "esperando para comprimir"},
    "panel.between": {"en": "between items…", "es": "entre un ítem y otro…"},
    "panel.network": {"en": "Network  ", "es": "Red  "},
    "panel.measuring": {"en": "measuring…", "es": "midiendo…"},
    "panel.idle": {"en": "   (idle while compressing)", "es": "   (inactiva mientras comprime)"},
    "panel.done": {"en": "{n} done   ", "es": "{n} listos   "},
    "panel.done.one": {"en": "{n} done   ", "es": "{n} listo   "},
    "panel.skipped": {"en": "{n} skipped   ", "es": "{n} omitidos   "},
    "panel.skipped.one": {"en": "{n} skipped   ", "es": "{n} omitido   "},
    "panel.failed": {"en": "{n} failed", "es": "{n} fallidos"},
    "panel.failed.one": {"en": "{n} failed", "es": "{n} fallido"},
    "panel.retried": {"en": " (retried on the next run)", "es": " (se reintentan en la próxima corrida)"},
    "panel.ask_at": {"en": "deletion asked at {gb} GB", "es": "se pide borrar al llegar a {gb} GB"},
    "panel.pending": {"en": "{n} originals ({size}) still in iCloud", "es": "{n} originales ({size}) aún en iCloud"},
    "panel.pending.one": {"en": "{n} original ({size}) still in iCloud", "es": "{n} original ({size}) aún en iCloud"},
    "panel.confirm": {"en": "⏳ macOS is asking you to confirm deleting ", "es": "⏳ macOS te pide confirmar el borrado de "},
    "panel.originals": {"en": "{n} originals", "es": "{n} originales"},
    "panel.originals.one": {"en": "{n} original", "es": "{n} original"},
    "panel.continues": {"en": " · processing continues", "es": " · el procesamiento sigue"},
    "panel.more_failed": {"en": "  … and {n} more failed (see status)", "es": "  … y {n} fallidos más (ver status)"},
    "panel.more_failed.one": {"en": "  … and {n} more failed (see status)", "es": "  … y {n} fallido más (ver status)"},
    "panel.recent": {"en": "Recent", "es": "Recientes"},
    "panel.already": {"en": "already compressed · skipped", "es": "ya comprimido · omitido"},
    "panel.skipped_reason": {"en": "skipped: {error}", "es": "omitido: {error}"},
    "ago.now": {"en": "just now", "es": "ahora mismo"},
    "ago.sec": {"en": "{n} sec ago", "es": "hace {n} segundo"},
    "ago.secs": {"en": "{n} secs ago", "es": "hace {n} segundos"},
    "ago.min": {"en": "{n} min ago", "es": "hace {n} minuto"},
    "ago.mins": {"en": "{n} mins ago", "es": "hace {n} minutos"},
    "ago.hour": {"en": "{n} hour ago", "es": "hace {n} hora"},
    "ago.hours": {"en": "{n} hours ago", "es": "hace {n} horas"},
    "ago.day": {"en": "{n} day ago", "es": "hace {n} día"},
    "ago.days": {"en": "{n} days ago", "es": "hace {n} días"},
    "note.deleted": {"en": "🗑  {n} originals moved to Recently Deleted (iCloud space freed)",
                     "es": "🗑  {n} originales movidos a Eliminados recientemente (espacio de iCloud liberado)"},
    "note.deleted.one": {"en": "🗑  {n} original moved to Recently Deleted (iCloud space freed)",
                         "es": "🗑  {n} original movido a Eliminados recientemente (espacio de iCloud liberado)"},
    "note.not_deleted": {"en": "Originals NOT deleted ({out}); you'll be asked again",
                         "es": "Los originales NO se borraron ({out}); se te volverá a preguntar"},
    "note.confirm_last": {"en": "Done processing — confirm the last deletion in the macOS dialog",
                          "es": "Procesamiento terminado: confirma el último borrado en la ventana de macOS"},
    "note.systemic": {"en": "Stopped: {n} in a row failed. See below what to check.",
                      "es": "Se detuvo: fallaron {n} seguidos. Abajo ves qué revisar."},
    "proc.systemic": {"en": "[bold red]Stopped: {n} items in a row failed[/] (nothing was lost; they're retried next time).\n"
                            "This usually means Photos isn't ready or iCloud is too slow right now:\n"
                            "  1. Open Photos and close any window it shows (welcome, iCloud, updates).\n"
                            "  2. Wait until it finishes syncing: at the bottom of Photos > Library it says \"Updated\".\n"
                            "  3. Check the internet connection (VPN off, close to the router or on a cable).\n"
                            "  4. Run it again.",
                      "es": "[bold red]Se detuvo: fallaron {n} seguidos[/] (no se perdió nada; se reintentan la próxima vez).\n"
                            "Casi siempre es porque Fotos no está lista o iCloud está muy lento ahora:\n"
                            "  1. Abre Fotos y cierra cualquier ventana que muestre (bienvenida, iCloud, actualizaciones).\n"
                            "  2. Espera a que termine de sincronizar: abajo en Fotos > Biblioteca dice \"Actualizado\".\n"
                            "  3. Revisa la conexión a internet (sin VPN, cerca del router o por cable).\n"
                            "  4. Vuelve a correrlo."},
    "proc.photos_check": {"en": "Checking that Photos is ready…", "es": "Revisando que Fotos esté lista…"},
    "proc.photos_not_ready": {"en": "[bold red]Photos isn't ready[/] ({why}). Nothing was changed.\n"
                                    "  1. Open Photos and close any window it shows (welcome, iCloud, updates).\n"
                                    "  2. Wait until it finishes syncing: at the bottom of Photos > Library it says \"Updated\".\n"
                                    "  3. Run it again. If it keeps failing: ./icloud-slim permissions",
                              "es": "[bold red]Fotos no está lista[/] ({why}). No se cambió nada.\n"
                                    "  1. Abre Fotos y cierra cualquier ventana que muestre (bienvenida, iCloud, actualizaciones).\n"
                                    "  2. Espera a que termine de sincronizar: abajo en Fotos > Biblioteca dice \"Actualizado\".\n"
                                    "  3. Vuelve a correrlo. Si sigue fallando: ./icloud-slim permissions"},
    "why.no_answer": {"en": "it didn't answer in 2 min", "es": "no respondió en 2 min"},
    "why.not_found": {"en": "it can't find the photos of its own library yet", "es": "todavía no encuentra las fotos de su propia fototeca"},
    "err.not_found": {"en": "Photos can't find this item yet (still syncing, or busy with a window)",
                      "es": "Fotos todavía no encuentra este ítem (sigue sincronizando o está ocupada con una ventana)"},
    "note.finished": {"en": "Finished", "es": "Terminado"},
    "demo.title": {"en": "videos (demo)", "es": "videos (demo)"},
    "demo.finished": {"en": "Demo finished", "es": "Demo terminada"},
    "demo.err_download": {"en": "iCloud download failed or timed out after 149 min (will retry)",
                          "es": "la descarga de iCloud falló o se agotó el tiempo tras 149 min (se reintentará)"},
    # permissions
    "perm.title": {"en": "iCloud Slim · permissions", "es": "iCloud Slim · permisos"},
    "perm.intro": {"en": "macOS will ask for access in one or two windows. Accept them all.",
                   "es": "macOS pedirá acceso en una o dos ventanas. Acéptalas todas."},
    "perm.s1": {"en": "Reading your photo library", "es": "Leyendo tu fototeca"},
    "perm.s1.hint": {"en": "the first time can take a minute", "es": "la primera vez puede tardar un minuto"},
    "perm.s1.ok": {"en": "{n} items", "es": "{n} ítems"},
    "perm.s2": {"en": "Access to your photos", "es": "Acceso a tus fotos"},
    "perm.s2.hint": {"en": "macOS window → \"Allow Full Access\" (it may be behind other windows)",
                     "es": "ventana de macOS → \"Permitir acceso completo\" (puede estar detrás de otras ventanas)"},
    "perm.s2.fix": {"en": "Open System Settings > Privacy & Security > Photos, set your terminal to Full Access, "
                          "quit the terminal (⌘Q), reopen it and run this again.",
                    "es": "Abre Ajustes del Sistema > Privacidad y seguridad > Fotos, pon tu terminal en Acceso completo, "
                          "cierra la terminal (⌘Q), ábrela de nuevo y vuelve a correr esto."},
    "perm.s3": {"en": "Control of the Photos app", "es": "Control de la app Fotos"},
    "perm.s3.hint": {"en": "Photos opens: close its welcome screen if it shows one · macOS window → \"OK\"",
                     "es": "se abre Fotos: cierra su pantalla de bienvenida si aparece · ventana de macOS → \"OK\""},
    "perm.s3.fix": {"en": "Open Photos and close any welcome window. Then check System Settings > Privacy & Security > "
                          "Automation > your terminal > Photos (on), and run this again.",
                    "es": "Abre Fotos y cierra cualquier ventana de bienvenida. Luego revisa Ajustes del Sistema > "
                          "Privacidad y seguridad > Automatización > tu terminal > Fotos (activado), y vuelve a correr esto."},
    "perm.timeout": {"en": "no answer after {m} min", "es": "sin respuesta tras {m} min"},
    "perm.done": {"en": "All set. Next: ./icloud-slim (opens the menu)", "es": "Todo listo. Siguiente: ./icloud-slim (abre el menú)"},
    # reports: table columns
    "col.items": {"en": "Items", "es": "Ítems"},
    "col.size": {"en": "Size", "es": "Tamaño"},
    "col.source": {"en": "Source", "es": "Origen"},
    "col.videos": {"en": "Videos", "es": "Videos"},
    "col.photos": {"en": "Photos", "es": "Fotos"},
    "col.avg_bitrate": {"en": "Avg bitrate", "es": "Bitrate medio"},
    "col.resolution": {"en": "Resolution", "es": "Resolución"},
    "col.hours": {"en": "Hours", "es": "Horas"},
    "col.type": {"en": "Type", "es": "Tipo"},
    "col.candidates": {"en": "Candidates", "es": "Candidatos"},
    "col.size_now": {"en": "Size now", "es": "Tamaño actual"},
    "col.est_size": {"en": "Estimated size", "es": "Tamaño estimado"},
    "col.est_savings": {"en": "Estimated savings", "es": "Ahorro estimado"},
    "col.not_touched": {"en": "Not touched because…", "es": "No se toca porque…"},
    "col.what": {"en": "What", "es": "Qué"},
    "col.year": {"en": "Year", "es": "Año"},
    "col.of_videos": {"en": "Of which videos", "es": "De eso, videos"},
    "col.file": {"en": "File", "es": "Archivo"},
    "col.date": {"en": "Date", "es": "Fecha"},
    "col.minutes": {"en": "Minutes", "es": "Minutos"},
    "saved_to": {"en": "Saved to {path}", "es": "Guardado en {path}"},
    # analyze
    "an.title": {"en": "# Photos analysis — {date}", "es": "# Análisis de Fotos — {date}"},
    "an.summary": {"en": "## Summary", "es": "## Resumen"},
    "an.total": {"en": "Total", "es": "Total"},
    "an.by_source": {"en": "## Videos by source", "es": "## Videos por origen"},
    "src.screen": {"en": "Screen recording", "es": "Grabación de pantalla"},
    "src.other": {"en": "Other camera ({make})", "es": "Otra cámara ({make})"},
    "src.none": {"en": "No camera data (Android, WhatsApp, downloads…)", "es": "Sin datos de cámara (Android, WhatsApp, descargas…)"},
    "an.by_res": {"en": "## Videos by resolution", "es": "## Videos por resolución"},
    "res.below": {"en": "below 1080p", "es": "menos de 1080p"},
    "an.can": {"en": "## What can be compressed", "es": "## Qué se puede comprimir"},
    "an.total_savings": {"en": "**Total estimated savings: {saved}** (from {total} to {after}).",
                         "es": "**Ahorro estimado total: {saved}** (de {total} a {after})."},
    "an.review": {"en": "## To review and delete by hand", "es": "## Para revisar y borrar a mano"},
    "an.screenshots": {"en": "Screenshots", "es": "Capturas de pantalla"},
    "an.recordings": {"en": "Screen recordings", "es": "Grabaciones de pantalla"},
    "an.trash": {"en": "Recently Deleted (freed when emptied)", "es": "Eliminados recientemente (se libera al vaciar)"},
    "an.by_year": {"en": "## Size by year", "es": "## Tamaño por año"},
    "an.largest": {"en": "## 15 largest videos", "es": "## Los 15 videos más pesados"},
    # process / status
    "proc.locked": {"en": "[yellow]Another run is already in progress (in another tab or window).[/] Wait for it to finish, or stop it with Ctrl+C there.",
                    "es": "[yellow]Ya hay otra corrida en curso (en otra pestaña o ventana).[/] Espera a que termine o detenla con Ctrl+C allá."},
    "proc.to_process": {"en": "[bold]To process:[/] {n} items, {before} → ~{after} (estimated)",
                        "es": "[bold]Por procesar:[/] {n} ítems, {before} → ~{after} (estimado)"},
    "proc.log": {"en": "[dim]Detailed log: {path}[/]", "es": "[dim]Log detallado: {path}[/]"},
    "proc.stopped": {"en": "[yellow]Stopped.[/] Run the same command again to resume where it left off.",
                     "es": "[yellow]Detenido.[/] Vuelve a correr el mismo comando para seguir donde quedó."},
    "st.title": {"en": "# icloud-slim metrics — {date}", "es": "# Métricas de icloud-slim — {date}"},
    "st.header": {"en": "| Type | Done | Before | After | Saved | % | Avg VMAF | Time |",
                  "es": "| Tipo | Listos | Antes | Después | Ahorro | % | VMAF medio | Tiempo |"},
    "st.status_header": {"en": "| Status | Items |", "es": "| Estado | Ítems |"},
    "st.pending": {"en": "{n} originals replaced but not yet deleted from Photos (deleted on the next run).",
                   "es": "{n} originales reemplazados pero aún no borrados de Fotos (se borran en la próxima corrida)."},
    "st.pending.one": {"en": "{n} original replaced but not yet deleted from Photos (deleted on the next run).",
                       "es": "{n} original reemplazado pero aún no borrado de Fotos (se borra en la próxima corrida)."},
    "st.errors": {"en": "## Errors (retried automatically on the next run; after {n} attempts use --retry)",
                  "es": "## Errores (se reintentan solos en la próxima corrida; tras {n} intentos usa --retry)"},
    "st.error_row": {"en": "- {name} (stuck at: {status}, attempts {attempts}): {error}",
                     "es": "- {name} (detenido en: {status}, intentos {attempts}): {error}"},
    # command-line help
    "help.main": {"en": """Shrink videos, photos, screen recordings and screenshots in iCloud Photos without visible quality loss.
Keeps date, location, albums, favorites and people. Originals go to Recently Deleted (you confirm
each batch) and a copy stays on this Mac in ~/icloud-slim/originals-backup.

Easiest: ./icloud-slim                   opens the menu (setup, runs, settings, help)

First time:
  ./icloud-slim install                   install ffmpeg, exiftool and osxphotos (Homebrew)
  ./icloud-slim permissions               grant Photos access (run it from Terminal or iTerm2)

Typical use:
  ./icloud-slim analyze                   what can be saved; changes nothing
  ./icloud-slim process --batch 3         try it on the 3 biggest videos
  ./icloud-slim process                   all videos (stop with Ctrl+C, run again to resume)
  ./icloud-slim process --type photos     JPEG photos with room to shrink → HEIC
  ./icloud-slim process --type recordings
  ./icloud-slim process --type screenshots
  ./icloud-slim status                    savings so far and errors

Help for one command: ./icloud-slim <command> --help        Full guide: README.md""",
                  "es": """Reduce videos, fotos, grabaciones de pantalla y capturas en Fotos de iCloud sin pérdida de calidad visible.
Conserva fecha, lugar, álbumes, favoritos y personas. Los originales van a Eliminados recientemente
(confirmas cada tanda) y queda una copia en este Mac en ~/icloud-slim/originals-backup.

Lo más fácil: ./icloud-slim              abre el menú (setup, corridas, ajustes, ayuda)

La primera vez:
  ./icloud-slim install                   instala ffmpeg, exiftool y osxphotos (Homebrew)
  ./icloud-slim permissions               da acceso a Fotos (córrelo desde Terminal o iTerm2)

Uso típico:
  ./icloud-slim analyze                   cuánto se puede ahorrar; no cambia nada
  ./icloud-slim process --batch 3         pruébalo con los 3 videos más pesados
  ./icloud-slim process                   todos los videos (detén con Ctrl+C, vuelve a correrlo para seguir)
  ./icloud-slim process --type photos     fotos JPEG con margen para achicarse → HEIC
  ./icloud-slim process --type recordings
  ./icloud-slim process --type screenshots
  ./icloud-slim status                    ahorro hasta ahora y errores

Ayuda de un comando: ./icloud-slim <comando> --help        Guía completa: README.es.md"""},
    "help.commands": {"en": "commands", "es": "comandos"},
    "help.usage": {"en": "usage: ", "es": "uso: "},
    "help.options": {"en": "options", "es": "opciones"},
    "help.h": {"en": "show this help message and exit", "es": "muestra esta ayuda y sale"},
    "help.command": {"en": "<command>", "es": "<comando>"},
    "help.permissions": {"en": "ask macOS for Photos access (once)", "es": "pide a macOS acceso a Fotos (una vez)"},
    "help.permissions_desc": {"en": "Downloads one small photo and talks to the Photos app so macOS shows its two permission prompts.\n"
                                    "Allow both. If no prompt shows up, see 'Setup' in README.md.",
                              "es": "Descarga una foto chica y habla con la app Fotos para que macOS muestre sus dos avisos de permiso.\n"
                                    "Acepta ambos. Si no aparece ningún aviso, mira 'Instalación paso a paso' en README.es.md."},
    "help.analyze": {"en": "library stats and estimated savings (changes nothing)",
                     "es": "estadísticas de la biblioteca y ahorro estimado (no cambia nada)"},
    "help.report_at": {"en": "Report saved to {path}.", "es": "El informe se guarda en {path}."},
    "help.process": {"en": "compress and replace; safe to stop and resume", "es": "comprime y reemplaza; puedes detenerlo y seguir después"},
    "help.process_desc": {"en": "Biggest savings first. Each item: download from iCloud → compress → verify → save to Photos\n"
                                "(same albums, date, place) → back up the original → move it to Recently Deleted in batches.\n"
                                "Stop any time with Ctrl+C; the same command resumes without redoing anything.",
                          "es": "Primero lo que más ahorra. Cada ítem: descarga de iCloud → comprime → verifica → guarda en Fotos\n"
                                "(mismos álbumes, fecha y lugar) → respalda el original → lo mueve a Eliminados recientemente por tandas.\n"
                                "Detén cuando quieras con Ctrl+C; el mismo comando sigue sin rehacer nada."},
    "help.examples": {"en": "examples:", "es": "ejemplos:"},
    "help.type": {"en": "what to process (default videos)", "es": "qué procesar (por defecto videos)"},
    "help.batch": {"en": "process only the N largest items", "es": "procesa solo los N ítems más pesados"},
    "help.uuid": {"en": "process only these items", "es": "procesa solo estos ítems"},
    "help.dry_run": {"en": "only list what would be processed", "es": "solo lista lo que se procesaría"},
    "help.vmaf": {"en": "measure perceived quality vs the original (slower)", "es": "mide la calidad percibida frente al original (más lento)"},
    "help.no_backup": {"en": "don't keep originals in {path}", "es": "no guarda los originales en {path}"},
    "help.retry": {"en": "retry items that already failed {n} times", "es": "reintenta los ítems que ya fallaron {n} veces"},
    "help.delete_every": {"en": "ask to delete replaced originals every this many GB (default {n})",
                          "es": "pide borrar los originales reemplazados cada esta cantidad de GB (por defecto {n})"},
    "help.parallel": {"en": "videos compressing at once (default 2; use 1 on older or busy Macs)",
                      "es": "videos comprimiéndose a la vez (por defecto 2; usa 1 en Macs antiguos u ocupados)"},
    "help.parallel_demo": {"en": "videos compressing at once (default 2)", "es": "videos comprimiéndose a la vez (por defecto 2)"},
    "help.no_fun": {"en": "plain panel, no space animation", "es": "panel simple, sin animación espacial"},
    "help.status": {"en": "savings so far, item states and errors", "es": "ahorro hasta ahora, estado de los ítems y errores"},
    "help.status_desc": {"en": "Also saved to {path}.", "es": "También se guarda en {path}."},
    "help.demo": {"en": "preview the live panel with fake data (touches nothing)", "es": "muestra el panel en vivo con datos falsos (no toca nada)"},
    "help.items": {"en": "how many fake videos (default 40)", "es": "cuántos videos falsos (por defecto 40)"},
    "help.speed": {"en": "time multiplier, e.g. 3 = three times faster", "es": "multiplicador de tiempo, p. ej. 3 = tres veces más rápido"},
    "help.seed": {"en": "change it to get a different fake library", "es": "cámbialo para obtener otra biblioteca falsa"},
    "help.help": {"en": "show this help", "es": "muestra esta ayuda"},
})


def trn(key, n, **kw):
    """tr() with a singular variant: "key.one" is used when n == 1 and registered."""
    return tr(key + ".one" if n == 1 and key + ".one" in i18n.STRINGS else key, n=n, **kw)


# Skips by our XMP marker, in every language (state.db may hold errors written in another one): see end_item()
MARKER_PREFIXES = tuple(s.split("{")[0] for s in i18n.STRINGS["err.marker"].values())

VERSION = "1.0"
TOOL = f"icloud-slim {VERSION}"
WORKDIR = Path(os.environ.get("ICLOUD_SLIM_DIR", Path.home() / "icloud-slim"))
BACKUP_DIR = WORKDIR / "originals-backup"   # <year>/<month>/<original filename>
# Ask to delete replaced originals once this many GB pile up (--delete-every). Recently Deleted doesn't count
# toward iCloud storage, so meanwhile iCloud only holds the extra compressed copies (~30 % of this).
# Each request is one macOS confirmation dialog; processing keeps going while it waits.
DELETE_EVERY_GB, DELETE_EVERY_ITEMS = 20, 500
# ponytail: fixed bitrate by the video's long side; raise it here if quality isn't good enough
BITRATE = [(3840, 20_000_000), (1920, 8_000_000), (0, 4_000_000)]
MARGIN = 1.2        # only compress if the original exceeds the target by 20 %
HEIC_QUALITY = 80
# estimated size ratio of a screenshot after converting to HEIC, by source format
HEIC_RATIO = {"public.png": 0.35, "public.jpeg": 0.6}
# Photos (JPEG → HEIC): higher quality than screenshots, they're memories. Measured on real libraries: quality 90
# gives ~1.2 bits per pixel and VMAF 95-97. Like videos, a JPEG is only a candidate if it's MARGIN heavier than that,
# whatever its source: heavily compressed ones (WhatsApp…) are skipped as "already light".
PHOTO_QUALITY, PHOTO_BPP, PHOTO_MIN_VMAF = 90, 1.2, 93
MAX_ATTEMPTS = 3
TYPES = ("videos", "photos", "recordings", "screenshots")
FINAL = ("done", "skipped")
# status flow: pending → exported → compressed → imported → replaced (original backed up) → done (original deleted)

log = logging.getLogger("icloud-slim")
SCREENSHOTS = set()  # uuids Photos detects as screenshots (includes Android, WhatsApp…)
OURS = set()         # uuids of compressed copies this tool imported (never re-process them)
fmt = lambda b: f"{(b or 0) / 1e9:,.1f} GB" if (b or 0) >= 1e9 else f"{(b or 0) / 1e6:,.0f} MB"
hm = lambda s: f"{int(s // 3600)}h{int(s % 3600 // 60):02d}m" if s is not None else "…"
console = Console()
ui = None  # live Dashboard while `process` runs

def mac_chip():
    """(chip name, video encoders, recommended --parallel). Apple's Max chips have 2 hardware video encoders and
    Ultra 4; the rest 1, where 2 at once still helps a bit (the steps around the encoder overlap). Intel: 1."""
    try:
        chip = subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"], capture_output=True, text=True).stdout.strip()
    except OSError:
        chip = ""
    encoders = 4 if "Ultra" in chip else 2 if "Max" in chip else 1
    return chip or "Mac", encoders, (4 if encoders == 4 else 2) if chip.startswith("Apple") else 1


# Preferences chosen in the menu (Settings); command-line flags override them for one run
SETTINGS_FILE = WORKDIR / "settings.json"
DEFAULTS = {"lang": "en", "parallel": mac_chip()[2], "delete_every": DELETE_EVERY_GB, "backup": True, "vmaf": False, "fun": True}


def load_settings():
    try:
        saved = json.loads(SETTINGS_FILE.read_text())
    except (OSError, ValueError):
        saved = {}
    s = {**DEFAULTS, **{k: v for k, v in saved.items() if k in DEFAULTS}}
    i18n.LANG = s["lang"] if s["lang"] in i18n.LANGS else "en"
    return s


def save_settings(s):
    WORKDIR.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(json.dumps(s, indent=2))
    i18n.LANG = s["lang"]


def hard_clear():
    """Like Cmd+K: clear the screen and the scrollback, so only this run's panel is left."""
    if console.is_terminal:
        print("\033[H\033[2J\033[3J", end="", flush=True)


def step(msg, style="cyan"):
    log.info(msg)
    if ui:
        ui.step(msg, style)


# ---------- selection ----------

def target_bitrate(w, h):
    long_side = max(w or 0, h or 0)
    return next(b for side, b in BITRATE if long_side >= side)


def duration(p):
    return (p.exif_info.duration if p.exif_info else None) or None


_library, _library_lock = None, threading.Lock()  # the menu counts in a background thread


def load_library():
    """Open the library (once per session: it's slow) and read which items Photos detected as screenshots
    (osxphotos doesn't expose it) and which ones are our own compressed copies."""
    global _library
    with _library_lock:
        db = _library = _library or osxphotos.PhotosDB()
    con = sqlite3.connect(f"file:{db._tmp_db}?mode=ro", uri=True)
    SCREENSHOTS.update(u for (u,) in con.execute("select ZUUID from ZASSET where ZISDETECTEDSCREENSHOT=1"))
    OURS.update(u for (u,) in State().db.execute("select new_uuid from items where new_uuid is not null"))
    return db


def is_screen_capture(p):
    return p.screenshot or p.screen_recording or p.uuid in SCREENSHOTS


def item_type(p):
    if p.ismovie:
        return "recordings" if is_screen_capture(p) else "videos"
    return "screenshots" if is_screen_capture(p) else "photos"


def evaluate(p):
    """(type, reason it is NOT processed, or None if it's a candidate)."""
    t = item_type(p)
    if not t:
        return None, "not applicable"
    for cond, reason in [(p.intrash, "in trash"), (p.hidden, "hidden"),
                         (p.shared, "shared album"), (getattr(p, "shared_library", False), "shared library"),
                         (p.slow_mo, "slow motion"), (p.uuid in OURS, "already compressed")]:
        if cond:
            return t, reason
    if t == "screenshots":
        return t, None if p.uti in HEIC_RATIO else "already HEIC or other format"
    if t == "photos":
        # a Live Photo, burst or RAW+JPEG pair would lose its other half; edits would be lost (only originals are exported)
        for cond, reason in [(p.live_photo, "live photo"), (p.burst, "burst"), (p.has_raw or p.israw, "RAW"),
                             (p.hasadjustments, "edited"), (p.uti != "public.jpeg", "already HEIC or other format")]:
            if cond:
                return t, reason
        pixels = (p.width or 0) * (p.height or 0)
        return t, None if pixels and p.original_filesize * 8 / pixels > PHOTO_BPP * MARGIN else "already light"
    d = duration(p)
    if not d:
        return t, "no duration"
    if p.original_filesize * 8 / d < target_bitrate(p.width, p.height) * MARGIN:
        return t, "already light"
    return t, None


def estimate(p):
    """Estimated size after compression."""
    if p.isphoto and not is_screen_capture(p):
        return min(p.original_filesize, p.width * p.height * PHOTO_BPP / 8)
    if p.isphoto:
        return p.original_filesize * HEIC_RATIO[p.uti]
    d = duration(p) or 0
    return min(p.original_filesize, d * target_bitrate(p.width, p.height) / 8)


# ---------- state (for resuming) ----------

class State:
    def __init__(self):
        WORKDIR.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(WORKDIR / "state.db")
        self.db.row_factory = sqlite3.Row
        self.db.execute("""create table if not exists items(
            uuid text primary key, type text, name text, date text,
            bytes_before int, bytes_after int, status text, new_uuid text,
            error text, attempts int default 0, seconds real default 0, updated text)""")
        for col in ("vmaf real", "sha1 text", "backup text"):  # added in 1.0
            try:
                self.db.execute(f"alter table items add column {col}")
            except sqlite3.OperationalError:
                pass

    def get(self, uuid):
        return self.db.execute("select * from items where uuid=?", (uuid,)).fetchone()

    def add(self, p, t):
        self.db.execute("insert or ignore into items(uuid,type,name,date,bytes_before,status) values(?,?,?,?,?,?)",
                        (p.uuid, t, p.original_filename, p.date.isoformat(), p.original_filesize, "pending"))
        self.db.commit()
        return self.get(p.uuid)

    def set(self, uuid, **kv):
        kv["updated"] = dt.datetime.now().isoformat(timespec="seconds")
        self.db.execute(f"update items set {', '.join(k + '=?' for k in kv)} where uuid=?", (*kv.values(), uuid))
        self.db.commit()


# ---------- steps ----------

def run(cmd, stderr=False):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(f"{Path(cmd[0]).name}: {(r.stderr or r.stdout).strip()[-400:]}")
    return r.stderr if stderr else r.stdout


def export(p, folder):
    folder.mkdir(parents=True, exist_ok=True)
    existing = [f for f in folder.iterdir() if not f.name.startswith(".")]
    if existing:
        return existing[0]
    # osxphotos' PhotoKit gives up after 300 s; allow for slow links (VPN, WiFi): ~0.5 MB/s, at least 10 min
    wait = max(600, (p.original_filesize or 0) // 500_000)
    # Run the download in a child process: PhotoKit blocks this one while waiting, freezing the live panel
    t0, why = time.time(), None
    try:
        r = subprocess.run([osxphotos_bin(), "run", __file__, "_export", p.uuid, str(folder)], capture_output=True, text=True,
                           env={**os.environ, "OSXPHOTOS_PHOTOKIT_TIMEOUT": str(wait)}, timeout=wait + 120,
                           cwd=WORKDIR / "logs")  # osxphotos drops crash logs in the cwd: keep them with our logs
        log.info(f"  export child: rc={r.returncode} {(r.stdout + r.stderr).strip()[-300:]}")
        # PhotoKit's own reason, e.g. "Could not get video for asset" when iCloud won't hand the original over
        why = ([l.strip() for l in (r.stdout + r.stderr).splitlines() if l.strip() and not l.startswith(
            ("Something went wrong", "Crash log", "Please file"))] or [None])[-1]
    except subprocess.TimeoutExpired:
        why = tr("err.timeout", m=wait // 60)
    files = [f for f in folder.iterdir() if not f.name.startswith(".")]
    if not files:
        took = int(time.time() - t0)
        raise RuntimeError(tr("err.download", m=took // 60, s=took % 60, why=why or tr("err.no_file")))
    return files[0]


def exif(f, *tags):
    d = json.loads(run(["exiftool", "-j", "-api", "QuickTimeUTC", *tags, str(f)]))[0]
    d.pop("SourceFile")
    return d


def metadata(f):
    """What verification requires to be identical between original and compressed."""
    return exif(f, "-Keys:CreationDate", "-QuickTime:CreateDate", "-Keys:GPSCoordinates", "-EXIF:DateTimeOriginal",
                "-EXIF:GPSLatitude", "-EXIF:GPSLongitude")


def marker(f):
    """Our XMP marker if this file was already produced by icloud-slim, else None."""
    tool = exif(f, "-XMP-xmp:CreatorTool").get("CreatorTool", "")
    return tool if str(tool).startswith("icloud-slim") else None  # exiftool turns a numeric tool like "15.4" into a float


def has_video_inside(f):
    """Android motion photos (MVIMG_, PXL_…MP, Samsung) append an MP4 to the JPEG; HEIC would drop it."""
    data = f.read_bytes()
    return any(sig in data for sig in (b"ftypmp4", b"ftypisom", b"ftypmp42"))


def copy_metadata(src, dst):
    # ffmpeg alone isn't enough: Photos reads date (with timezone) and GPS from Apple's Keys tags
    run(["exiftool", "-q", "-m", "-overwrite_original", "-api", "QuickTimeUTC", "-tagsFromFile", str(src), "-all:all",
         "-Keys:CreationDate<Keys:CreationDate", "-Keys:GPSCoordinates<Keys:GPSCoordinates",
         "-QuickTime:CreateDate<QuickTime:CreateDate", "-FileModifyDate<FileModifyDate", str(dst)])


def ffprobe(f, fields):
    return json.loads(run(["ffprobe", "-v", "error", "-of", "json", *fields, str(f)]))


def describe(f):
    """One-line technical summary, e.g. '157 MB hevc 3840x2160 10-bit 53 Mbps'."""
    size = fmt(f.stat().st_size)
    if f.suffix.lower() in (".heic", ".png", ".jpg", ".jpeg"):
        w, h = run(["sips", "-g", "pixelWidth", "-g", "pixelHeight", str(f)]).split()[-3::2]
        return f"{size} {f.suffix[1:].upper()} {w}x{h}"
    v = ffprobe(f, ["-select_streams", "v:0", "-show_entries", "stream=codec_name,width,height,pix_fmt,bit_rate"])["streams"][0]
    bits = "10-bit" if "10" in v.get("pix_fmt", "") else "8-bit"
    return f"{size} {v['codec_name']} {max(v['width'], v['height'])}x{min(v['width'], v['height'])} {bits} {int(v.get('bit_rate', 0)) / 1e6:.0f} Mbps"


def vmaf(src, dst):
    """Perceived quality of dst vs src (0-100, >93 is visually indistinguishable). Compared at 1080p."""
    scale = "scale=1920:1080:force_original_aspect_ratio=decrease:flags=bicubic,format=yuv420p,setsar=1"
    if dst.suffix.lower() == ".heic":  # ffmpeg reads only the first 512x512 tile of a HEIC: decode it with sips
        png = dst.with_name(".vmaf.png")
        run(["sips", "-s", "format", "png", str(dst), "--out", str(png)])
        try:
            return vmaf(src, png)
        finally:
            png.unlink(missing_ok=True)
    out = run(["ffmpeg", "-nostdin", "-hide_banner", "-i", str(dst), "-i", str(src), "-lavfi",
               f"[0:v]{scale}[d];[1:v]{scale}[r];[d][r]libvmaf=n_threads={os.cpu_count()}", "-f", "null", "-"], stderr=True)
    m = re.search(r"VMAF score: ([\d.]+)", out)
    return round(float(m.group(1)), 1) if m else None


def compress_video(src, dst):
    v = ffprobe(src, ["-select_streams", "v:0", "-show_entries", "stream=width,height,pix_fmt"])["streams"][0]
    rate = target_bitrate(v["width"], v["height"])
    ten_bit = "10" in v.get("pix_fmt", "")  # iPhone HDR: keep 10-bit
    enc = ["-map", "0:v:0", "-map", "0:a?", "-c:v", "hevc_videotoolbox", "-b:v", str(rate),
           "-maxrate", str(rate * 3 // 2), "-bufsize", str(rate * 2)] + (["-profile:v", "main10"] if ten_bit else [])
    tail = ["-tag:v", "hvc1", "-map_metadata", "0", "-movflags", "use_metadata_tags+faststart", str(dst)]
    # Hardware decoding keeps frames on the GPU (~1 s of CPU per 30 s of 4K instead of ~200 s), which is what lets
    # several videos compress at once; software decoding is the fallback for codecs the hardware can't read.
    decoders = [(["-hwaccel", "videotoolbox", "-hwaccel_output_format", "videotoolbox_vld"], []),
                ([], ["-pix_fmt", "p010le"] if ten_bit else [])]
    # audio the container won't take as-is (some Android): re-encode to AAC
    audios = [["-c:a", "copy"], ["-c:a", "aac", "-b:a", "192k"]]
    for i, ((dec, fmt_), audio) in enumerate((d, a) for d in decoders for a in audios):
        try:
            run(["ffmpeg", "-nostdin", "-v", "error", "-y", *dec, "-i", str(src), *enc, *fmt_, *audio, *tail])
            break
        except RuntimeError:
            if i == len(decoders) * len(audios) - 1:
                raise
    copy_metadata(src, dst)
    dur = lambda f: float(ffprobe(f, ["-show_entries", "format=duration"])["format"]["duration"])
    if abs(dur(src) - dur(dst)) > 0.5:
        raise RuntimeError(tr("err.duration"))
    return f"target {rate // 1_000_000} Mbps"


def compress_image(src, dst, quality=HEIC_QUALITY):
    run(["sips", "-s", "format", "heic", "-s", "formatOptions", str(quality), str(src), "--out", str(dst)])
    copy_metadata(src, dst)
    dims = lambda f: run(["sips", "-g", "pixelWidth", "-g", "pixelHeight", str(f)]).split()[-4:]
    if dims(src) != dims(dst):
        raise RuntimeError(tr("err.dimensions"))
    return f"HEIC quality {quality}"


def sha1(f):
    h = hashlib.sha1()
    with open(f, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def compress(p, t, src, folder, with_vmaf):
    """Compress, verify and stamp the XMP marker. Returns (dst, extra state fields)."""
    folder.mkdir(parents=True, exist_ok=True)
    dst = folder / (src.name if t in ("videos", "recordings") else src.stem + ".heic")
    settings = {"screenshots": lambda: compress_image(src, dst), "photos": lambda: compress_image(src, dst, PHOTO_QUALITY)
                }.get(t, lambda: compress_video(src, dst))()
    a, b = metadata(src), metadata(dst)
    # extra tags are fine (a PNG's XMP date also lands in EXIF); a missing or changed one is not
    if lost := {k: v for k, v in a.items() if b.get(k) != v}:
        raise RuntimeError(tr("err.metadata", a=lost, b={k: b.get(k) for k in lost}))
    # photos are always measured (a second or two each): one that would look worse is left as it was
    score = vmaf(src, dst) if t == "photos" or with_vmaf and t != "screenshots" else None
    digest = sha1(src)
    details = {"from": describe(src), "to": describe(dst), "settings": settings, "original_sha1": digest}
    if score is not None:
        details["vmaf"] = score
    # Standard XMP media-management fields: invisible in Photos, readable with exiftool
    run(["exiftool", "-q", "-m", "-overwrite_original", f"-XMP-xmp:CreatorTool={TOOL}",
         f"-XMP-xmpMM:PreservedFileName={src.name}", f"-XMP-xmpMM:DerivedFromDocumentID={p.uuid}",
         "-XMP-xmpMM:HistoryAction=converted", f"-XMP-xmpMM:HistorySoftwareAgent={TOOL}",
         f"-XMP-xmpMM:HistoryWhen={dt.datetime.now().astimezone():%Y:%m:%d %H:%M:%S%z}",
         f"-XMP-xmpMM:HistoryParameters={json.dumps(details)}", str(dst)])
    return dst, {"vmaf": score, "sha1": digest}


def album(lib, name):
    return lib.album(name, top_level=False) or lib.create_album(name)


def finish(p, new_uuid, lib):
    """What Photos doesn't take from the file: albums, favorite, keywords, title."""
    n = photoscript.Photo(new_uuid)
    people = {x for x in p.persons if x != "_UNKNOWN_"}
    n.keywords = sorted(set(n.keywords) | set(p.keywords) | people)
    if p.title:
        n.title = p.title
    if p.description:
        n.description = p.description
    if p.favorite:
        n.favorite = True
    if p.latitude is not None and n.location[0] is None:
        n.location = (p.latitude, p.longitude)
    date = p.date.astimezone().replace(tzinfo=None)
    if abs((n.date - date).total_seconds()) > 2:
        n.date = date
    for name in p.albums:
        album(lib, name).add([n])


def backup_path(p, name):
    folder = BACKUP_DIR / f"{p.date:%Y}" / f"{p.date:%m}"
    folder.mkdir(parents=True, exist_ok=True)
    dst, n = folder / name, 2
    while dst.exists():
        dst, n = folder / f"{Path(name).stem} ({n}){Path(name).suffix}", n + 1
    return dst


def osxphotos_bin():
    return os.environ.get("OSXPHOTOS") or shutil.which("osxphotos") or str(Path.home() / ".local/bin/osxphotos")


class Deleter:
    """Moves replaced originals to Recently Deleted in batches, in a child process: macOS asks the user to
    confirm, and processing keeps going while that dialog waits. State changes only in the main thread."""

    def __init__(self, state, every_gb):
        self.state, self.every, self.proc, self.uuids = state, every_gb * 1e9, None, []

    def pending(self):
        """Originals replaced but still in iCloud: (count, bytes, space freed once deleted)."""
        return tuple(self.state.db.execute("select count(*), coalesce(sum(bytes_before), 0), "
                                           "coalesce(sum(bytes_before - bytes_after), 0) from items where status='replaced'").fetchone())

    def poll(self):
        if not self.proc or self.proc.poll() is None:
            return
        out = self.proc.communicate()[0].strip()
        if self.proc.returncode == 0:
            for u in self.uuids:
                self.state.set(u, status="done")
            step(trn("note.deleted", len(self.uuids)), "green")
        else:
            step(tr("note.not_deleted", out=out[-120:]), "red")
        self.proc, self.uuids = None, []

    def request(self, force=False):
        self.poll()
        if self.proc:  # one dialog at a time
            return
        rows = self.state.db.execute("select uuid, bytes_before from items where status='replaced'").fetchall()
        if not rows or not force and len(rows) < DELETE_EVERY_ITEMS and sum(r[1] for r in rows) < self.every:
            return
        self.uuids = [r[0] for r in rows]
        self.proc = subprocess.Popen([osxphotos_bin(), "run", __file__, "_delete", *self.uuids], cwd=WORKDIR / "logs",
                                     stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        log.info(f"Asked to delete {len(self.uuids)} originals ({fmt(sum(r[1] for r in rows))})")

    def waiting(self):
        return bool(self.proc) and self.proc.poll() is None

    def finish(self):
        """End of run: ask for whatever is left and wait for the answer."""
        self.request(force=True)
        if self.proc:
            self.proc.wait()
        self.poll()


# ---------- pipeline: download the next item while others compress ----------
# Worker threads download (one at a time) and compress (up to --parallel at once); the main thread imports into
# Photos as items finish, since AppleScript and the live panel live there. Each thread has its own sqlite connection.
DOWNLOAD = threading.Semaphore(1)
COMPRESS = threading.Semaphore(2)  # resized by run_pipeline
IMPORTS = {"fails": 0, "ok": 0}    # imports rejected by Photos in a row / accepted since its last restart
RESTART_EVERY = 1000               # Photos starts rejecting every file after a few thousand imports in one session
STOP = threading.Event()           # set on Ctrl+C: interrupted work is left to resume, not counted as a failure
_local = threading.local()


def thread_state():
    if not hasattr(_local, "state"):
        _local.state = State()
    return _local.state


def show_step(p, i, waiting=False):
    if ui:
        ui.set_step(p, i, waiting)


def prepare_item(p, t, a):
    """Worker thread: pending/exported → compressed (or skipped). Returns when it started, for timing."""
    state, u, start = thread_state(), p.uuid, time.time()
    row = state.get(u) or state.add(p, t)
    if row["status"] not in ("pending", "exported"):
        return start  # already compressed by an earlier run: straight to importing
    d_orig, d_comp = WORKDIR / "originals" / u, WORKDIR / "compressed" / u
    try:
        # already downloaded by an interrupted run: don't wait behind another item's download
        with DOWNLOAD if row["status"] == "pending" else contextlib.nullcontext():
            if STOP.is_set():
                return start
            if row["status"] == "pending":
                shutil.rmtree(d_orig, True)  # never reuse a half-finished download from an interrupted run
            show_step(p, 1)
            log.info(f"↓ Downloading {p.original_filename}")
            src = export(p, d_orig)
        state.set(u, status="exported")
        if (tool := marker(src)):  # already one of ours (state.db lost, other Mac…): don't redo it
            state.set(u, status="skipped", error=tr("err.marker", tool=tool))
            shutil.rmtree(d_orig, True)
            log.info(f"  skipped (already compressed by {tool}): {p.original_filename}")
            return start
        if t == "photos" and has_video_inside(src):
            state.set(u, status="skipped", error=tr("err.motion"))
            shutil.rmtree(d_orig, True)
            log.info(f"  skipped (motion photo): {p.original_filename}")
            return start
        show_step(p, 2, waiting=True)
        with COMPRESS:
            if STOP.is_set():
                return start
            show_step(p, 2)
            log.info(f"⚙ Compressing {p.original_filename}" + (" + measuring quality (VMAF)" if a.vmaf else ""))
            dst, extra = compress(p, t, src, d_comp, a.vmaf)
        too_low = t == "photos" and (extra["vmaf"] or 0) < PHOTO_MIN_VMAF
        if too_low or dst.stat().st_size >= src.stat().st_size * 0.9:
            state.set(u, status="skipped", error=tr("err.quality", score=extra["vmaf"]) if too_low else tr("err.no_shrink"))
            shutil.rmtree(d_orig, True), shutil.rmtree(d_comp, True)
            log.info(f"  skipped ({state.get(u)['error']}): {p.original_filename}")
            return start
        state.set(u, status="compressed", bytes_after=dst.stat().st_size,
                  seconds=(row["seconds"] or 0) + time.time() - start, **extra)
    except Exception as e:
        # ponytail: Ctrl+C also kills our ffmpeg/download children; give the main thread 1 s to flag it as a stop
        if STOP.is_set() or STOP.wait(1):
            if state.get(u)["status"] == "pending":
                shutil.rmtree(d_orig, True)  # no half downloads left behind
            return start
        state.set(u, error=str(e), attempts=(row["attempts"] or 0) + 1)
        log.error(f"  ERROR on {p.original_filename} (step {state.get(u)['status']}): {e}")
    return start


def restart_photos():
    """Quit Photos (forced if its error sheets block quitting) and reopen it in the background; wait until it answers.
    Also closes the pile of "can't import" windows a stuck Photos leaves behind."""
    # ponytail: blocks the main thread (panel frozen ~10-30 s); workers keep downloading/compressing meanwhile
    log.info(tr("log.photos_restart"))
    with contextlib.suppress(subprocess.TimeoutExpired):
        subprocess.run(["osascript", "-e", 'quit app "Photos"'], capture_output=True, timeout=20)
    for i in range(25):
        if subprocess.run(["pgrep", "-x", "Photos"], capture_output=True).returncode:
            break
        if i == 15:
            subprocess.run(["killall", "Photos"], capture_output=True)
        time.sleep(1)
    subprocess.run(["open", "-g", "-a", "Photos"])
    for _ in range(30):
        with contextlib.suppress(subprocess.TimeoutExpired):
            if not subprocess.run(["osascript", "-e", 'tell app "Photos" to count of media items'],
                                  capture_output=True, timeout=60).returncode:
                break
        time.sleep(2)
    IMPORTS["ok"] = 0


def photos_import(f):
    """Import one file into Photos; returns the new item (with .uuid) or None if Photos rejected it.
    Own AppleScript instead of photoscript's: that one gives up after AppleScript's default 2 min, and a big video
    on a busy Mac takes longer. Waits ~1 min per 100 MB (at least 10 min)."""
    wait = max(600, f.stat().st_size // 1_600_000)
    script = f"""on run argv
        with timeout of {wait} seconds
            tell application "Photos"
                set r to import {{POSIX file (item 1 of argv)}} skip check duplicates true
                if r is missing value or r is {{}} then return ""
                return id of item 1 of r
            end tell
        end timeout
    end run"""
    try:
        r = subprocess.run(["osascript", "-e", script, str(f)], capture_output=True, text=True, timeout=wait + 60)
    except subprocess.TimeoutExpired:
        raise RuntimeError(tr("err.import_timeout", m=wait // 60))
    if r.returncode:
        if "-1712" in r.stderr:  # AppleScript's own timeout
            raise RuntimeError(tr("err.import_timeout", m=wait // 60))
        raise RuntimeError(r.stderr.strip()[-200:] or "osascript failed")
    new = r.stdout.strip()
    return types.SimpleNamespace(uuid=new.split("/")[0]) if new else None


def import_file(lib, f):
    """Import into Photos. Restart Photos every RESTART_EVERY imports, and when it rejects 3 files in a row
    (stuck, not a bad file): then retry this one once. 5 in a row stops the run (complete_item)."""
    if IMPORTS["ok"] >= RESTART_EVERY:
        restart_photos()
    why = tr("err.import")
    for retry in (False, True):
        try:
            new = photos_import(f)
        except Exception as e:  # AppleScript error: -128 = Photos canceled it (closed, or busy with a window)
            new, why = None, tr("err.import_canceled") if "-128" in str(e) else str(e)
        if new:
            IMPORTS["fails"], IMPORTS["ok"] = 0, IMPORTS["ok"] + 1
            return new
        IMPORTS["fails"] += 1
        if retry or IMPORTS["fails"] != 3:
            break
        restart_photos()
    raise RuntimeError(why)


def complete_item(p, state, lib, a, _queued_at):
    """Main thread: compressed → imported → replaced (original backed up, waiting to be deleted)."""
    u, start = p.uuid, time.time()  # own clock: waiting in line for the main thread is not work
    row = state.get(u)
    if row["status"] not in ("compressed", "imported") or STOP.is_set() and row["status"] == "compressed":
        return  # skipped, failed or interrupted (a compressed one is imported on the next run)
    d_orig, d_comp = WORKDIR / "originals" / u, WORKDIR / "compressed" / u
    try:
        if row["status"] == "compressed":
            dst = next(d_comp.iterdir())
            show_step(p, 3)
            log.info(f"↑ Importing {p.original_filename} into Photos")
            new = import_file(lib, dst)
            state.set(u, status="imported", new_uuid=new.uuid)  # from here on it's never imported again
            row = state.get(u)
        finish(p, row["new_uuid"], lib)
        backup = None
        if a.backup and d_orig.exists():
            src = next(d_orig.iterdir())
            backup = backup_path(p, src.name)
            shutil.move(str(src), backup)
        shutil.rmtree(d_orig, True), shutil.rmtree(d_comp, True)
        state.set(u, status="replaced", error=None, backup=str(backup) if backup else None,
                  seconds=(row["seconds"] or 0) + time.time() - start)
        row = state.get(u)
        saved = 100 - row["bytes_after"] * 100 // row["bytes_before"]
        q = f", VMAF {row['vmaf']}" if row["vmaf"] else ""
        log.info(f"  done: {p.original_filename} {fmt(row['bytes_before'])} -> {fmt(row['bytes_after'])} (-{saved} %{q})")
    except Exception as e:
        state.set(u, error=str(e), attempts=(row["attempts"] or 0) + 1)
        log.error(f"  ERROR on {p.original_filename} (step {state.get(u)['status']}): {e}")
        if row["status"] == "compressed":
            if IMPORTS["fails"] >= 5 and not STOP.is_set():  # Photos stuck: stop instead of failing the whole queue
                log.error(tr("err.photos_stuck"))
                STOP.set()


def run_pipeline(queue, prepare, complete, parallel, tick):
    """prepare(p, t) runs in parallel + 1 worker threads (parallel compressing, one downloading ahead);
    complete(p, t, result) and tick() run here, in the main thread."""
    global COMPRESS
    parallel = max(1, parallel)
    COMPRESS = threading.Semaphore(parallel)
    STOP.clear()
    pool = ThreadPoolExecutor(parallel + 1)
    # Ctrl+C also kills our ffmpeg/download children: flag the stop before their threads notice, so a thread
    # waiting for a free compressor doesn't start a new one
    signal.signal(signal.SIGINT, lambda *x: (STOP.set(), signal.default_int_handler(*x)))
    futures = {pool.submit(prepare, p, t): (p, t) for p, t in queue}
    try:
        while futures:
            for f in wait(futures, timeout=0.25, return_when=FIRST_COMPLETED)[0]:
                p, t = futures.pop(f)
                complete(p, t, f.result())
            tick()
    finally:
        if futures:
            STOP.set()
        pool.shutdown(wait=False, cancel_futures=True)
        signal.signal(signal.SIGINT, signal.default_int_handler)


# ---------- live terminal panel ----------

class SpaceScene:
    """Decorative 3-row starfield: the ship flies toward 🪐 as data gets done (off with --no-fun)."""
    BODY, FLAMES = "≡▶", ("-=", "=-", "~=", "=~")

    def __init__(self):
        rnd = random.Random(7)
        # (start x, row, char, speed in cells/s) — positions are a pure function of time, no state to update
        self.stars = [(rnd.uniform(0, 200), rnd.randrange(3), rnd.choice("··.*✦"), rnd.choice((1.5, 3, 5)))
                      for _ in range(40)]  # render() uses one per 4 columns: same density at any width
        self.bodies = [(30.0, 0, "🌍", 0.7), (120.0, 2, "🌕", 0.4)]  # rows 0/2 only: row 1 is the ship's lane

    def render(self, width, progress, paused, now):
        cells = [[(" ", None)] * width for _ in range(3)]

        def put(row, x, s, style=None):
            x, w = int(x), cell_len(s)
            if 0 <= x and x + w <= width and all(c[0] in " ·.*✦" for c in cells[row][x:x + w]):
                cells[row][x:x + w] = [(s, style)] + [("", None)] * (w - 1)  # "" = 2nd half of a wide emoji

        for x0, row, ch, speed in self.stars[:width // 4]:
            put(row, (x0 - speed * now) % width, ch, "bright_white" if ch == "✦" else "grey50")
        span = width + 16
        for x0, row, emoji, speed in self.bodies:
            put(row, (x0 - speed * now) % span - 8, emoji)
        if (phase := now % 14) < 2:  # a comet (💫) crosses the top row every ~14 s
            put(0, width - phase / 2 * (width + 4), "💫")
        put(1, width - 3, "🪐")
        ship_x = int(min(progress, 1) * (width - 3 - len(self.BODY) - 4))
        if not paused or int(now * 2) % 2:  # blinks while waiting for the user
            flame = self.FLAMES[int(now * 8) % len(self.FLAMES)]
            for i, (ch, st) in enumerate([(flame[0], "yellow"), (flame[1], "yellow"), (self.BODY[0], "bold cyan"),
                                          (self.BODY[1], "bold cyan")]):
                cells[1][ship_x + i] = (ch, st)
        lines = []
        for row in cells:
            t = Text(no_wrap=True)
            for ch, st in row:
                if ch:
                    t.append(ch, st)
            lines.append(t)
        return Group(*lines)


class Dashboard:
    """Panel redrawn in place while `process` runs; the detailed log goes to a file per run."""
    MAX_WIDTH, COMPACT_BELOW = 160, 64  # follows the terminal size live; narrow/short terminals get a compact layout
    STEPS = (("↓", "step.download"), ("⚙", "step.compress"), ("↑", "step.save"))  # labels are i18n keys
    MAX_FAILED_SHOWN = 3

    def __init__(self, title, n_items, total_bytes, fun=True, sample_network=True):
        self.title, self.n, self.total = title, n_items, total_bytes
        self.scene = SpaceScene() if fun else None
        self.deleter = None
        self.done = self.skipped = self.done_bytes = self.saved = self.failed_bytes = 0
        self.pending = (0, 0, 0)  # originals still in iCloud waiting for deletion: (count, bytes, saving once deleted)
        self.t0 = time.time()
        self.active = {}  # uuid -> [item, step 1-3, step start time, waiting for a free compressor]
        self.note = None  # (text, style, time) for one-off messages such as deletion results
        self.recent = deque(maxlen=15)  # successes and skips, newest first: (finished at, seconds taken, sym, …)
        self.failed = {}  # name -> (error, time); kept apart so failures never scroll out of view
        self.fullscreen = True
        self.started = {}  # uuid -> when its download began, for the duration shown in the history
        self.down = self.up = None  # live iCloud speeds (bytes/s)
        if sample_network:
            threading.Thread(target=self._sample_network, daemon=True).start()

    def _sample_network(self):
        """Live iCloud speeds: bytes macOS' cloudd receives (downloads) and sends (Photos uploading our copies)."""
        last = None
        while True:
            try:
                out = subprocess.run(["nettop", "-P", "-L", "1", "-n", "-x", "-J", "bytes_in,bytes_out"],
                                     capture_output=True, text=True, timeout=10).stdout
                rows = [l.split(",") for l in out.splitlines() if l.startswith("cloudd.")]
                b_in, b_out, now = sum(int(r[1]) for r in rows), sum(int(r[2]) for r in rows), time.time()
                if last:
                    dt_ = now - last[2]
                    self.down, self.up = max(0, (b_in - last[0]) / dt_), max(0, (b_out - last[1]) / dt_)
                last = (b_in, b_out, now)
            except Exception:
                pass
            time.sleep(2)

    def step(self, msg, style="cyan"):
        self.note = (msg, style, time.time())

    def set_step(self, p, i, waiting=False):  # called from worker threads too
        self.active[p.uuid] = [p, i, time.time(), waiting]
        self.started.setdefault(p.uuid, time.time())

    def end_item(self, p, row, pending):
        name, b, a = p.original_filename, row["bytes_before"] or 0, row["bytes_after"] or 0
        now, start = time.time(), self.started.pop(p.uuid, None)
        took = now - start if start else None
        if row["error"] and row["status"] not in FINAL:
            if name not in self.failed:
                self.failed_bytes += b
            self.failed[name] = (row["error"], now)
        elif row["status"] == "skipped":
            self.skipped += 1
            self.done_bytes += b
            if row["error"].startswith(MARKER_PREFIXES):  # found our XMP marker: nothing to do, not a problem
                self.recent.appendleft((now, took, "↷", "blue", name, tr("panel.already"), "blue"))
            else:
                self.recent.appendleft((now, took, "↷", "yellow", name, tr("panel.skipped_reason", error=row["error"]), "yellow"))
        else:
            self.failed.pop(name, None)
            self.done += 1
            self.done_bytes += b
            self.saved += b - a
            vmaf = f"  VMAF {row['vmaf']}" if row["vmaf"] else ""
            self.recent.appendleft((now, took, "✓", "bold green", name, f"{fmt(b):>7} → {fmt(a):>7}   "
                                    f"−{int(100 - a * 100 // max(b, 1))} %{vmaf}", "green"))
        self.active.pop(p.uuid, None)
        self.pending = pending

    def __rich__(self):
        now = time.time()
        # terminal size is re-read every frame, so it adapts live when the window is resized
        width = min(console.width, self.MAX_WIDTH)
        compact = width < self.COMPACT_BELOW
        inner = width - (4 if compact else 6)  # border + padding
        name_w = max(10, min(48, inner * 2 // 5))
        line = lambda *parts: Text.assemble(*parts, no_wrap=True, overflow="ellipsis")
        fit = lambda s, n: s.ljust(n) if len(s) <= n else s[:n - 1] + "…"
        today = dt.date.today()
        clock = lambda t: (f"{dt.datetime.fromtimestamp(t):%H:%M}" if dt.date.fromtimestamp(t) == today
                           else f"{dt.datetime.fromtimestamp(t):%b %d %H:%M}") + "  "
        hms = lambda s: f"{int(s // 3600)}:{int(s % 3600 // 60):02d}:{int(s % 60):02d}" if s >= 3600 else f"{int(s // 60)}:{int(s % 60):02d}"
        plural = lambda n, unit: tr(f"ago.{unit}{'s' if n > 1 else ''}", n=n)
        ago = lambda s: (tr("ago.now") if s < 10 else plural(int(s), "sec") if s < 60 else plural(int(s // 60), "min")
                         if s < 3600 else plural(int(s // 3600), "hour") if s < 86400 else plural(int(s // 86400), "day"))
        elapsed = now - self.t0
        processed = self.done_bytes + self.failed_bytes  # failures count as processed, but not toward the speed
        rate = self.done_bytes / elapsed if self.done_bytes else 0
        eta = (self.total - processed) / rate if rate else None
        finished = self.done + self.skipped + len(self.failed)
        pct = processed * 100 / max(self.total, 1)
        n_pend, pend_bytes, pend_saving = self.pending
        waiting = bool(self.deleter and self.deleter.waiting())
        failed = list(self.failed.items())[:self.MAX_FAILED_SHOWN]

        # height budget: the core always shows; failures next; then the scene (4 lines) and history if they fit
        core = 16 + max(1, len(self.active)) + (1 if waiting else 0) + (1 if self.note else 0) + (len(failed) + 1 if failed else 0)
        spare = console.height - core - (0 if compact else 2)
        show_scene = self.scene and not compact and spare >= 8
        n_recent = max(0, min(len(self.recent), spare - (4 if show_scene else 0) - 2))  # - blank and title lines
        shown = list(self.recent)[:n_recent]
        # name column only as wide as the names on screen, so the numbers sit close to them
        name_w = min(name_w, max([len(r[4]) for r in shown] + [len(n) for n, _ in failed] + [10]))

        parts = []
        if show_scene:
            parts += [self.scene.render(inner, pct / 100, waiting, now), Text()]

        label = tr("panel.progress")  # label widths follow the language, so the lines under it stay aligned
        bar = Table.grid(padding=(0, 2))
        bar.add_column(style="bold", width=cell_len(label)), bar.add_column(ratio=1), bar.add_column(justify="right", width=7)
        bar.add_row(label, ProgressBar(total=100, completed=pct), f"{pct:5.1f} %")
        indent = "" if compact else " " * (cell_len(label) + 2)
        parts += [bar,
                  line(indent, (tr("panel.count", done=finished, n=self.n, title=self.title), "bold"),
                       (tr("panel.bytes", done=fmt(processed), total=fmt(self.total)), "dim")),
                  line(indent, (tr("panel.time_left"), "dim"), (f"~{hm(eta)}", "bold"), (tr("panel.elapsed", t=hm(elapsed)), "dim")),
                  Text()]

        freed = max(0, self.saved - pend_saving)
        parts += [line(tr("panel.saved"), (fmt(self.saved), "bold green")),
                  line(indent, (fmt(freed), "green"), (tr("panel.freed"), "dim"),
                       *(((" · ", "dim"), (fmt(pend_saving), "yellow"), (tr("panel.more_after"), "dim"))
                         if pend_saving else ())),
                  Text()]

        active = list(self.active.values())  # several at once: one downloading ahead, others compressing
        spin = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"[int(now * 10) % 10]  # drawn by hand so the line never wraps
        now_label = tr("panel.now") + "  "
        gap = " " * cell_len(now_label)
        queued_text = tr("panel.waiting_compress")
        # status column as wide as its longest possible text in this language ("1/3 ⠋ ↓ " + label + " 0:00")
        status_w = max([len(queued_text) + 6] + [len(tr(k)) + 13 for _, k in self.STEPS]) + 3
        for n, (p, i, t, queued) in enumerate(active):
            icon, key = self.STEPS[i - 1]
            secs = int(now - t)
            status = ((f"{i}/3 · {queued_text}", "grey50") if queued else
                      (f"{i}/3 {spin} {icon} {tr(key)} {secs // 60}:{secs % 60:02d}", "bold cyan"))
            parts.append(line((now_label if n == 0 else gap, "bold"), (status[0].ljust(status_w), status[1]),
                              (p.original_filename, "bold"), (f" · {fmt(p.original_filesize)} · {p.date.date()}", "dim")))
        if not active:
            parts.append(line((now_label, "bold"), (tr("panel.between"), "dim")))
        net = (tr("panel.measuring") if self.down is None else
               f"↓ {self.down / 1e6:.1f} MB/s   ↑ {self.up / 1e6:.1f} MB/s")
        downloading = any(i == 1 for _, i, _, _ in active)
        idle = tr("panel.idle") if active and not downloading and (self.down or 0) < 1e5 else ""
        parts += [line(gap, (tr("panel.network"), "dim"), net, (idle, "dim"))]
        if self.note:
            text, style, t = self.note
            if now - t < 30:
                parts.append(line(gap, (text, style)))
        parts.append(Text())

        parts.append(line(("✓ ", "green"), trn("panel.done", self.done), ("↷ ", "yellow"), trn("panel.skipped", self.skipped),
                          ("✗ ", "red"), trn("panel.failed", len(self.failed)), (tr("panel.retried") if self.failed else "", "dim")))
        if n_pend:
            ask_at = tr("panel.ask_at", gb=f"{self.deleter.every / 1e9:.0f}") if self.deleter else ""
            parts.append(line(("⌫ ", "yellow"), trn("panel.pending", n_pend, size=fmt(pend_bytes)),
                              (f" · {ask_at}" if ask_at and not waiting else "", "dim")))
        if waiting:
            parts.append(line((tr("panel.confirm"), "bold yellow"),
                              (trn("panel.originals", len(self.deleter.uuids)), "bold yellow"), (tr("panel.continues"), "yellow")))
        if failed:
            parts.append(Text())
            parts += [line((clock(t), "dim"), ("✗ ", "bold red"), (fit(name, name_w), "bold"), "  ", (err, "red"))
                      for name, (err, t) in failed]
            if len(self.failed) > len(failed):
                parts.append(line((trn("panel.more_failed", len(self.failed) - len(failed)), "red")))
        if shown:
            parts += [Text(), line((tr("panel.recent"), "bold"))]
            for n, (t, took, sym, sym_style, name, detail, detail_style) in enumerate(shown):
                parts.append(line((clock(t), "dim"), (sym + " ", sym_style), (fit(name, name_w), "bold" if n == 0 else ""),
                                  "  ", (fit(detail, 36), detail_style), (f"  {hms(took) if took else '':>7}", "dim"), (f"   {ago(now - t)}", "dim")))
        panel = Panel(Group(*parts), title=f"[bold]icloud-slim[/] · {self.title}", border_style="blue",
                      padding=(0, 1) if compact or spare < 2 else (1, 2), width=width)
        # full screen: centered both ways on wide/tall terminals; the copy printed on exit only horizontally
        return Align.center(panel, vertical="middle", height=console.height) if self.fullscreen else Align.center(panel)


# ---------- commands ----------

def run_steps(steps):
    """Checklist with a live spinner: steps = [(label, hint, fix, fn)]; fn() runs in a thread and returns a short
    detail, or raises. Stops at the first failure and shows how to fix it. Returns True if all passed."""
    from rich.padding import Padding
    from rich.spinner import Spinner
    from rich.table import Table
    from rich.text import Text
    con, n = Console(), len(steps)
    done = []  # (ok, label, detail)
    con.print(f"\n  [bold #7fdbff]{tr('perm.title')}[/]\n  [dim]{tr('perm.intro')}[/]\n")

    lw = max(cell_len(label) for label, *_ in steps) + 5

    def grid(rows):
        g = Table.grid(padding=(0, 2))
        g.add_column(width=1), g.add_column(width=lw), g.add_column()
        for r in rows:
            g.add_row(*r)
        return Padding(g, (0, 0, 0, 2))

    def view(i, spinner, t0):
        rows, hint = [], None
        for j, (label, h, _, _) in enumerate(steps):
            num = f"[dim]{j + 1}/{n}[/]  "
            if j < len(done):
                ok, _, detail = done[j]
                rows.append(("[green]✓[/]" if ok else "[red]✗[/]", num + label, f"[dim]{detail}[/]"))
            elif j == i:
                rows.append((spinner, f"{num}[bold]{label}[/]", f"[dim]{int(time.time() - t0)} s[/]"))
                hint = len(rows)
            else:
                rows.append(("[dim]·[/]", f"[dim]{num}{label}[/]", ""))
        if hint is None:
            return grid(rows)
        tip = Padding(Text(f"→ {steps[i][1]}", style="yellow"), (0, 2, 0, 11))  # under the label
        return Group(grid(rows[:hint]), tip, grid(rows[hint:]))

    with Live(console=con, refresh_per_second=10, transient=False) as live:
        for i, (label, hint, fix, fn) in enumerate(steps):
            out, t0, spinner = {}, time.time(), Spinner("dots", style="cyan")
            def work():
                try:
                    out["r"] = fn()
                except Exception as e:  # shown to the user, with the fix below
                    out["e"] = str(e) or type(e).__name__
            th = threading.Thread(target=work, daemon=True)
            th.start()
            while th.is_alive():
                live.update(view(i, spinner, t0))
                th.join(0.1)
            secs = f"{time.time() - t0:.0f} s"
            done.append(("e" not in out, label, f"{out['r']} · {secs}" if "e" not in out else out["e"]))
            live.update(view(i + 1, spinner, t0))
            if "e" in out:
                break
    if len(done) == n and done[-1][0]:
        con.print(Padding(Text(tr("perm.done"), style="green"), (1, 2, 1, 2)))
        return True
    con.print(Padding(Text(steps[len(done) - 1][2], style="yellow"), (1, 2, 1, 5)))  # aligned with the labels
    return False


def cmd_permissions(a):
    lib = {}

    def read():
        lib["db"] = load_library()
        return tr("perm.s1.ok", n=f"{len(lib['db'].photos()):,}")

    def access():
        db = lib["db"]
        p = min((x for x in db.photos(images=True, movies=False) if x.original_filesize), key=lambda x: x.original_filesize)
        with tempfile.TemporaryDirectory() as d:
            if not PhotoExporter(p).export(d, options=ExportOptions(use_photokit=True, download_missing=True)).exported:
                raise RuntimeError(tr("perm.s2.fix").split(".")[0])
        return "OK"

    def control():
        # osascript instead of photoscript: it can be timed out. A first launch of Photos (welcome screen, library
        # choice) or a hidden permission window would otherwise hang here forever.
        subprocess.run(["open", "-a", "Photos"])
        try:
            r = subprocess.run(["osascript", "-e", 'tell application "Photos" to get version'],
                               capture_output=True, text=True, timeout=300)
        except subprocess.TimeoutExpired:
            raise RuntimeError(tr("perm.timeout", m=5))
        if r.returncode:
            raise RuntimeError(r.stderr.strip()[-120:] or "osascript failed")
        return f"Photos {r.stdout.strip()}"

    ok = run_steps([(tr("perm.s1"), tr("perm.s1.hint"), tr("perm.s2.fix"), read),
                    (tr("perm.s2"), tr("perm.s2.hint"), tr("perm.s2.fix"), access),
                    (tr("perm.s3"), tr("perm.s3.hint"), tr("perm.s3.fix"), control)])
    if not ok:
        sys.exit(1)  # the menu's Setup reads this as "not granted"


def cmd_analyze(a):
    db = load_library()
    everything = db.photos()
    trash = db.photos(intrash=True)
    L = [tr("an.title", date=dt.date.today()), ""]
    table = lambda head, rows: L.extend(["| " + " | ".join(head) + " |", "|" + "---|" * len(head),
                                         *["| " + " | ".join(map(str, r)) + " |" for r in rows], ""])
    photos = [p for p in everything if p.isphoto]
    videos = [p for p in everything if p.ismovie]
    size = lambda xs: sum(p.original_filesize or 0 for p in xs)
    total = size(everything)
    L += [tr("an.summary"), ""]
    table(["", tr("col.items"), tr("col.size"), "%"], [(n, len(xs), fmt(size(xs)), f"{size(xs) * 100 // max(total, 1)} %")
                                        for n, xs in [(tr("an.total"), everything), (tr("col.photos"), photos), (tr("col.videos"), videos)]])

    L += [tr("an.by_source"), ""]
    source = defaultdict(list)
    for p in videos:
        make = (p.exif_info.camera_make if p.exif_info else None) or ""
        source[tr("src.screen") if is_screen_capture(p) else "iPhone/Apple" if make == "Apple"
               else tr("src.other", make=make) if make else tr("src.none")].append(p)
    bitrate = lambda xs: f"{size(xs) * 8 / max(sum(duration(p) or 0 for p in xs), 1) / 1e6:.0f} Mbps"
    table([tr("col.source"), tr("col.videos"), tr("col.size"), tr("col.avg_bitrate")],
          [(k, len(xs), fmt(size(xs)), bitrate(xs)) for k, xs in sorted(source.items(), key=lambda kv: -size(kv[1]))])

    L += [tr("an.by_res"), ""]
    res = defaultdict(list)
    for p in videos:
        long_side = max(p.width or 0, p.height or 0)
        res["4K" if long_side >= 3840 else "1080p" if long_side >= 1920 else tr("res.below")].append(p)
    table([tr("col.resolution"), tr("col.videos"), tr("col.size"), tr("col.hours")],
          [(k, len(xs), fmt(size(xs)), f"{sum(duration(p) or 0 for p in xs) / 3600:.1f}") for k, xs in res.items()])

    L += [tr("an.can"), ""]
    cand, excl = defaultdict(list), defaultdict(list)
    for p in everything:
        t, reason = evaluate(p)
        if t:
            (excl[(t, reason)] if reason else cand[t]).append(p)
    rows, total_saved = [], 0
    for t in TYPES:
        before, after = size(cand[t]), sum(estimate(p) for p in cand[t])
        total_saved += before - after
        rows.append((tr("type." + t), len(cand[t]), fmt(before), fmt(after), fmt(before - after)))
    table([tr("col.type"), tr("col.candidates"), tr("col.size_now"), tr("col.est_size"), tr("col.est_savings")], rows)
    L += [tr("an.total_savings", saved=fmt(total_saved), total=fmt(total), after=fmt(total - total_saved)), ""]
    table([tr("col.type"), tr("col.not_touched"), tr("col.items"), tr("col.size")],
          [(tr("type." + t), tr("reason." + r), len(xs), fmt(size(xs))) for (t, r), xs in sorted(excl.items(), key=lambda kv: -size(kv[1]))])

    L += [tr("an.review"), ""]
    shots = [p for p in everything if p.isphoto and is_screen_capture(p)]
    recs = [p for p in everything if p.ismovie and is_screen_capture(p)]
    table([tr("col.what"), tr("col.items"), tr("col.size")], [(tr("an.screenshots"), len(shots), fmt(size(shots))),
                                      (tr("an.recordings"), len(recs), fmt(size(recs))),
                                      (tr("an.trash"), len(trash), fmt(size(trash)))])

    L += [tr("an.by_year"), ""]
    by_year = defaultdict(list)
    for p in everything:
        by_year[p.date.year].append(p)
    table([tr("col.year"), tr("col.photos"), tr("col.videos"), tr("col.size"), tr("col.of_videos")],
          [(y, sum(p.isphoto for p in xs), sum(p.ismovie for p in xs), fmt(size(xs)), fmt(size([p for p in xs if p.ismovie])))
           for y, xs in sorted(by_year.items())])

    L += [tr("an.largest"), ""]
    table([tr("col.file"), tr("col.date"), tr("col.size"), tr("col.minutes"), tr("col.resolution")],
          [(p.original_filename, p.date.date(), fmt(p.original_filesize), f"{(duration(p) or 0) / 60:.1f}",
            f"{p.width}x{p.height}") for p in sorted(videos, key=lambda p: -(p.original_filesize or 0))[:15]])

    out = WORKDIR / "reports" / f"analysis-{dt.date.today()}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(L))
    console.print(Markdown("\n".join(L)))
    console.print(f"\n[dim]{tr('saved_to', path=out)}[/]")


def build_queue(types, retry=False, uuids=None):
    """[(photo, type)] still to process, biggest first. Also what the menu counts."""
    db, state = load_library(), State()
    queue, ready, failed = [], set(), set()
    for p in db.photos(uuid=uuids) if uuids else db.photos():
        typ, reason = evaluate(p)
        row = state.get(p.uuid)
        if row and row["status"] in ("compressed", "imported"):
            ready.add(p.uuid)
        elif row and row["attempts"]:
            failed.add(p.uuid)
        if row and row["status"] not in FINAL and row["status"] != "pending":
            reason = None  # left halfway: resume it
        if typ in types and not reason and not (row and (row["status"] in FINAL + ("replaced",)
                                                         or row["attempts"] >= MAX_ATTEMPTS and not retry)):
            queue.append((p, typ))
    # already compressed first (seconds each, nothing to download), then biggest savings first; ones that already
    # failed go last, so a video iCloud keeps refusing doesn't hold up the downloads for hours
    queue.sort(key=lambda x: (x[0].uuid not in ready, x[0].uuid in failed, -(x[0].original_filesize or 0)))
    return queue


_run_lock = None


def single_run(take=True):
    """Only one `process` at a time (another tab, or the menu): both would pick the same items."""
    global _run_lock
    if not take:
        if _run_lock:
            _run_lock.close()  # closing releases the lock
        _run_lock = None
        return True
    if _run_lock is None:
        _run_lock = open(WORKDIR / "process.lock", "w")
        try:
            fcntl.flock(_run_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            _run_lock.close()
            _run_lock = None
    return _run_lock is not None


FAILS_TO_STOP = 3  # items in a row that fail at any step, with no success in between


def fails_in_row(n, row):
    """Running count of failed items; an interrupted one (no error, not finished) leaves it as it was."""
    if row and row["status"] in FINAL + ("replaced",):
        return 0
    return n + 1 if row and row["error"] else n


def photos_not_ready(p):
    """Why Photos can't be used right now, or None. Photos must answer AppleScript and find a library item:
    on a new Mac it can sit behind a welcome window or still be syncing, and then every item fails."""
    try:
        with console.status(tr("proc.photos_check")):
            r = subprocess.run(["osascript", "-e", f'tell application "Photos" to exists media item id "{p.uuid}/L0/001"'],
                               capture_output=True, text=True, timeout=120)
    except subprocess.TimeoutExpired:
        return tr("why.no_answer")
    if r.returncode:
        return r.stderr.strip()[-150:] or "osascript failed"
    return None if r.stdout.strip() == "true" else tr("why.not_found")


def cmd_process(a):
    types = TYPES if a.type == "all" else (a.type,)
    state = State()
    if not a.dry_run and not single_run():
        return console.print(tr("proc.locked"))
    queue = build_queue(types, a.retry, a.uuid)
    if a.batch:
        queue = queue[:a.batch]
    before = sum(p.original_filesize for p, _ in queue)
    if not a.dry_run:
        hard_clear()
    console.print(tr("proc.to_process", n=len(queue), before=fmt(before), after=fmt(sum(estimate(p) for p, _ in queue))))
    if a.dry_run:
        table = Table(tr("col.type"), tr("col.date"), tr("col.size"), tr("col.file"), box=None, header_style="bold dim")
        for p, t in queue:
            table.add_row(tr("type." + t), str(p.date.date()), fmt(p.original_filesize), p.original_filename)
        return console.print(table)
    logfile = WORKDIR / "logs" / f"{dt.datetime.now():%Y%m%d-%H%M%S}.log"
    logfile.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(force=True, level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S",
                        handlers=[logging.FileHandler(logfile)])
    log.info(f"Start: {len(queue)} items")
    console.print(tr("proc.log", path=logfile))
    if queue and (why := photos_not_ready(queue[0][0])):
        log.error(f"Photos not ready: {why}")
        single_run(take=False)
        return console.print(tr("proc.photos_not_ready", why=why))
    lib = photoscript.PhotosLibrary()
    deleter = Deleter(state, a.delete_every)
    pending = deleter.pending
    global ui
    ui = Dashboard(", ".join(tr("type." + t) for t in types), len(queue), before, fun=a.fun)
    ui.deleter, ui.pending = deleter, pending()
    stopped, in_row = False, [0]
    try:
        with Live(get_renderable=lambda: ui, console=console, refresh_per_second=8, screen=True):
            deleter.request(force=True)  # anything a previous run replaced but couldn't delete
            ui.pending = pending()
            count = iter(range(1, len(queue) + 1))

            def complete(p, t, start):
                complete_item(p, state, lib, a, start)
                row = state.get(p.uuid)
                ui.end_item(p, row, pending())
                # n failures in a row with nothing working = Photos or iCloud trouble, not bad files: stop, explain
                in_row[0] = fails_in_row(in_row[0], row)
                if in_row[0] >= FAILS_TO_STOP and not STOP.is_set():
                    log.error(f"Stopping: {in_row[0]} failed in a row")
                    ui.step(tr("note.systemic", n=in_row[0]), "bold red")
                    STOP.set()
                log.info(f"[{next(count)}/{len(queue)}] {t}: {p.original_filename} ({fmt(p.original_filesize)}, {p.date.date()})")
                deleter.request()
                ui.pending = pending()

            def tick():
                deleter.poll()
                ui.pending = pending()  # a deletion confirmed mid-item shows up right away

            run_pipeline(queue, lambda p, t: prepare_item(p, t, a), complete, a.parallel, tick)
            if deleter.waiting() or pending():
                ui.step(tr("note.confirm_last"), "bold yellow")
            deleter.finish()
            ui.pending = pending()
            ui.step(tr("note.finished"), "bold green")
    except KeyboardInterrupt:
        stopped = True
    # iTerm2 can push full-screen frames into the scrollback (e.g. on resize): wipe them, keep only the final panel
    hard_clear()
    ui.fullscreen = False
    console.print(ui)  # the full-screen panel vanishes on exit: leave its last state in the terminal
    console.print(tr("proc.log", path=logfile))
    if stopped:
        log.info("Stopped by user")
        console.print(tr("proc.stopped"))
    elif in_row[0] >= FAILS_TO_STOP:
        console.print(tr("proc.systemic", n=in_row[0]))
    ui = None
    single_run(take=False)
    cmd_status(a)


def cmd__export(a):
    """Child process: download one original from iCloud into dest (see export())."""
    from osxphotos.photokit import PHOTOS_VERSION_ORIGINAL, PhotoLibrary
    t0 = time.time()
    took = lambda: f"{int(time.time() - t0) // 60} min"
    try:
        files = PhotoLibrary().fetch_uuid(a.uuid).export(a.dest, version=PHOTOS_VERSION_ORIGINAL)
    except Exception as e:
        # PhotoKit sometimes can't get an original ("Could not get video for asset") that the Photos app itself
        # exports fine. Export into a hidden folder first, so a half-written file is never taken as the download.
        print(f"PhotoKit: {e} ({took()}); retrying through the Photos app", file=sys.stderr)
        e, t0 = f"{e} ({took()})", time.time()
        tmp = Path(a.dest) / ".photos-app"
        shutil.rmtree(tmp, True)
        tmp.mkdir(parents=True)
        wait = int(os.environ.get("OSXPHOTOS_PHOTOKIT_TIMEOUT", 600))
        try:
            files = [Path(shutil.move(f, a.dest)) for f in
                     photoscript.Photo(a.uuid).export(str(tmp), original=True, timeout=wait)]
            if not files:
                raise RuntimeError(tr("err.no_file"))
        except Exception as e2:  # the last stderr line is what the panel shows: both reasons, in plain words
            print(f"PhotoKit: {e} · " + (tr("err.not_found") if "Invalid photo id" in str(e2) else f"Photos: {e2}")
                  + f" ({took()})", file=sys.stderr)
            sys.exit(1)
        shutil.rmtree(tmp, True)
    print(json.dumps([str(f) for f in files]))


def cmd__delete(a):
    """Child process: move these originals to Recently Deleted; macOS shows the confirmation dialog."""
    import Photos
    assets = Photos.PHAsset.fetchAssetsWithLocalIdentifiers_options_([f"{u}/L0/001" for u in a.uuids], None)
    if assets.count():
        ok, err = Photos.PHPhotoLibrary.sharedPhotoLibrary().performChangesAndWait_error_(
            lambda: Photos.PHAssetChangeRequest.deleteAssets_(assets), None)
        if not ok:
            sys.exit(f"not deleted: {err}")


def cmd_demo(a):
    """Fake run with realistic data to preview the live panel. Touches nothing: no Photos, no iCloud, no files."""
    import types
    rnd = random.Random(a.seed)
    items = []
    for i in range(a.items):
        kind = rnd.random()
        name = (f"LMC_XHT2023022{rnd.randint(0, 9)}_18{rnd.randint(1000, 5959)}_lmc_8.4.mp4" if kind < 0.15
                else f"IMG_{rnd.randint(1000, 9999)}.MOV")
        size = int(rnd.lognormvariate(19.8, 0.9))  # ~400 MB median, a few multi-GB
        date = dt.datetime(rnd.randint(2021, 2026), rnd.randint(1, 12), rnd.randint(1, 28))
        items.append(types.SimpleNamespace(uuid=str(i), original_filename=name, original_filesize=size, date=date))
    items.sort(key=lambda p: -p.original_filesize)  # biggest first, like the real run
    for p in items:
        p.r = rnd.random()  # outcome: < 0.06 fails, < 0.09 already compressed, < 0.12 doesn't shrink, else done
    if len(items) >= 6:  # every seed shows each outcome at least once
        items[1].r, items[3].r, items[5].r = 0.0, 0.1, 0.07
    global ui
    hard_clear()
    ui = Dashboard(tr("demo.title"), len(items), sum(p.original_filesize for p in items), fun=a.fun, sample_network=False)
    every = min(3e9, sum(p.original_filesize for p in items) / 3)  # at least two deletion dialogs per demo
    deleter = types.SimpleNamespace(state=None, every=every, uuids=[], _wait_until=0)
    deleter.waiting = lambda: time.time() < deleter._wait_until
    ui.deleter = deleter
    pending = [0, 0, 0]

    def confirm_if_due():
        if deleter._wait_until and not deleter.waiting():  # the "user" confirmed the dialog
            deleter._wait_until = 0
            ui.step(trn("note.deleted", len(deleter.uuids)), "green")
            pending[:] = [0, 0, 0]
            ui.pending = tuple(pending)

    def prepare(p, t):  # worker thread, like prepare_item: same locks, so the demo shows the real overlap
        gb, r = p.original_filesize / 1e9, p.r
        with DOWNLOAD:
            if STOP.is_set():
                return None
            show_step(p, 1)
            STOP.wait((0.6 + gb) / a.speed)
        if r < 0.06:
            return {"status": "pending", "bytes_before": p.original_filesize, "bytes_after": 0, "vmaf": None,
                    "error": tr("demo.err_download")}
        if r < 0.09:  # our XMP marker is checked right after downloading
            return {"status": "skipped", "bytes_before": p.original_filesize, "bytes_after": None,
                    "vmaf": None, "error": tr("err.marker", tool=TOOL)}
        show_step(p, 2, waiting=True)
        with COMPRESS:
            if STOP.is_set():
                return None
            show_step(p, 2)
            STOP.wait((0.8 + gb * 1.5) / a.speed)
        if r < 0.12:
            return {"status": "skipped", "bytes_before": p.original_filesize, "bytes_after": None,
                    "vmaf": None, "error": tr("err.no_shrink")}
        return {"status": "compressed"}

    def complete(p, t, row):  # main thread, like complete_item
        if row is None:
            return
        if row["status"] == "compressed":
            show_step(p, 3)
            time.sleep(0.5 / a.speed)
            after = int(p.original_filesize * rnd.uniform(0.07, 0.45))
            row = {"status": "replaced", "bytes_before": p.original_filesize, "bytes_after": after,
                   "error": None, "vmaf": round(rnd.uniform(94, 98.5), 1) if rnd.random() < 0.3 else None}
            pending[0] += 1
            pending[1] += p.original_filesize
            pending[2] += p.original_filesize - after
        ui.end_item(p, row, tuple(pending))
        if pending[1] >= every and not deleter._wait_until:
            deleter.uuids = [None] * pending[0]
            deleter._wait_until = time.time() + 6 / a.speed * 2  # pretend the user takes a moment to confirm

    def tick():
        downloading = any(i == 1 for _, i, _, _ in list(ui.active.values()))
        ui.down = max(0, rnd.gauss(30e6, 6e6)) if downloading else rnd.uniform(0, 4e4)
        ui.up = rnd.uniform(0, 3e6)
        confirm_if_due()

    with Live(get_renderable=lambda: ui, console=console, refresh_per_second=8, screen=True):
        try:
            run_pipeline([(p, "videos") for p in items], prepare, complete, a.parallel, tick)
            while deleter._wait_until:  # like the real run: wait for the last confirmation
                ui.step(tr("note.confirm_last"), "bold yellow")
                confirm_if_due()
                time.sleep(0.25)
            ui.step(tr("demo.finished"), "bold green")
            time.sleep(3)
        except KeyboardInterrupt:
            pass
    hard_clear()
    ui.fullscreen = False
    console.print(ui)
    ui = None


def cmd_status(a):
    state = State()
    q = lambda sql, *x: state.db.execute(sql, x).fetchall()
    L = [tr("st.title", date=f"{dt.datetime.now():%Y-%m-%d %H:%M}"), "",
         tr("st.header"), "|---|---|---|---|---|---|---|---|"]
    tot = [0, 0, 0, 0]
    for r in q("select type, count(*) n, sum(bytes_before) b, sum(bytes_after) a, sum(seconds) s, avg(vmaf) v "
               "from items where status in ('done','replaced') group by type"):
        v = f"{r['v']:.1f}" if r["v"] else "–"
        L.append(f"| {tr('type.' + r['type'])} | {r['n']} | {fmt(r['b'])} | {fmt(r['a'])} | {fmt(r['b'] - r['a'])} | "
                 f"{100 - r['a'] * 100 // r['b']} % | {v} | {r['s'] / 60:.0f} min |")
        tot = [tot[0] + r["n"], tot[1] + r["b"], tot[2] + r["a"], tot[3] + r["s"]]
    if tot[0]:
        L.append(f"| **Total** | {tot[0]} | {fmt(tot[1])} | {fmt(tot[2])} | **{fmt(tot[1] - tot[2])}** | "
                 f"{100 - tot[2] * 100 // tot[1]} % | | {tot[3] / 60:.0f} min |")
    L += ["", tr("st.status_header"), "|---|---|", *[f"| {r[0]} | {r[1]} |" for r in q("select status, count(*) from items group by status")]]
    pending = q("select count(*) from items where status='replaced'")[0][0]
    if pending:
        L += ["", trn("st.pending", pending)]
    errors = q("select name, status, attempts, error from items where error is not null and status not in ('done','replaced','skipped')")
    if errors:
        L += ["", tr("st.errors", n=MAX_ATTEMPTS), ""]
        L += [tr("st.error_row", name=r["name"], status=r["status"], attempts=r["attempts"], error=r["error"]) for r in errors]
    text = "\n".join(L)
    (WORKDIR / "metrics.md").write_text(text)
    console.print(Markdown(text))
    console.print(f"[dim]{tr('saved_to', path=WORKDIR / 'metrics.md')}[/]")


class HelpFormatter(argparse.RawDescriptionHelpFormatter):
    def add_usage(self, usage, actions, groups, prefix=None):
        super().add_usage(usage, actions, groups, tr("help.usage") if prefix is None else prefix)


def build_parser(st):
    fmt_ = HelpFormatter
    ap = argparse.ArgumentParser(prog="icloud-slim", description=tr("help.main"), formatter_class=fmt_)
    sub = ap.add_subparsers(dest="cmd", metavar=tr("help.command"), title=tr("help.commands"))
    sub.add_parser("permissions", help=tr("help.permissions"), description=tr("help.permissions_desc"), formatter_class=fmt_)
    sub.add_parser("analyze", help=tr("help.analyze"), description=tr("help.report_at", path=WORKDIR / "reports"))
    pr = sub.add_parser("process", help=tr("help.process"), formatter_class=fmt_, description=tr("help.process_desc"), epilog=
                        tr("help.examples") + "\n  ./icloud-slim process --dry-run\n  ./icloud-slim process --batch 10\n"
                        "  ./icloud-slim process --type all --parallel 1")
    pr.add_argument("--type", choices=(*TYPES, "all"), default="videos", help=tr("help.type"))
    pr.add_argument("--batch", type=int, metavar="N", help=tr("help.batch"))
    pr.add_argument("--uuid", nargs="+", help=tr("help.uuid"))
    pr.add_argument("--dry-run", action="store_true", help=tr("help.dry_run"))
    pr.add_argument("--vmaf", action="store_true", help=tr("help.vmaf"))
    pr.add_argument("--no-backup", dest="backup", action="store_false", help=tr("help.no_backup", path=BACKUP_DIR))
    pr.add_argument("--retry", action="store_true", help=tr("help.retry", n=MAX_ATTEMPTS))
    pr.add_argument("--delete-every", type=float, default=st["delete_every"], metavar="GB",
                    help=tr("help.delete_every", n=DELETE_EVERY_GB))
    pr.add_argument("--parallel", type=int, default=st["parallel"], metavar="N", help=tr("help.parallel"))
    pr.add_argument("--no-fun", dest="fun", action="store_false", help=tr("help.no_fun"))
    pr.set_defaults(backup=st["backup"], vmaf=st["vmaf"], fun=st["fun"])  # from Settings unless a flag says otherwise
    sub.add_parser("status", help=tr("help.status"), description=tr("help.status_desc", path=WORKDIR / "metrics.md"))
    dm = sub.add_parser("demo", help=tr("help.demo"))
    dm.add_argument("--items", type=int, default=40, help=tr("help.items"))
    dm.add_argument("--speed", type=float, default=1.0, help=tr("help.speed"))
    dm.add_argument("--seed", type=int, default=1, help=tr("help.seed"))
    dm.add_argument("--parallel", type=int, default=st["parallel"], metavar="N", help=tr("help.parallel_demo"))
    dm.add_argument("--no-fun", dest="fun", action="store_false", help=tr("help.no_fun"))
    dm.set_defaults(fun=st["fun"])
    sub.add_parser("help", help=tr("help.help"))
    ex = sub.add_parser("_export")  # internal: one PhotoKit download, run as a child process (no help= → hidden)
    ex.add_argument("uuid"), ex.add_argument("dest")
    de = sub.add_parser("_delete")  # internal: one batch deletion, run as a child process
    de.add_argument("uuids", nargs="+")
    sub._choices_actions = [c for c in sub._choices_actions if not c.dest.startswith("_")]
    for p in (ap, *sub.choices.values()):  # argparse's own words ("usage", "options", -h)
        p.formatter_class, p._optionals.title, p._actions[0].help = fmt_, tr("help.options"), tr("help.h")
    return ap


def run_command(argv):
    """Run one command as if typed, e.g. ["process", "--type", "videos"]. Used by main() and by the menu."""
    ap = build_parser(load_settings())
    a = ap.parse_args(argv)
    if a.cmd in (None, "help"):
        return ap.print_help()
    globals()[f"cmd_{a.cmd}"](a)


def main():
    if sys.argv[1:]:
        return run_command(sys.argv[1:])
    import menu  # no command: the interactive menu
    menu.run(types.SimpleNamespace(
        run=run_command, load_settings=load_settings, save_settings=save_settings, build_queue=build_queue,
        estimate=estimate, fmt=fmt, console=console, scene=SpaceScene, workdir=WORKDIR, version=VERSION,
        tool_types=TYPES, state=State, hard_clear=hard_clear, mac=mac_chip()))


main()
