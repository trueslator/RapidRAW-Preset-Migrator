# RapidRAW Preset Migrator

**Adobe-Lightroom-Presets nach RapidRAW unter Windows und Linux migrieren.**

Der RapidRAW Preset Migrator konvertiert ältere **`.lrtemplate`**- und moderne **`.xmp`**-Presets aus Adobe Lightroom in native RapidRAW-Presets, verwaltet auch große Preset-Sammlungen in einer lokalen Browser-Oberfläche und kann optional kreative Bestandteile aus eigenen **DNG Camera Profiles (`.dcp`)** weiterverwenden.

> **Wichtig:** Dieses Projekt führt eine **bestmögliche Look-Migration** durch, keine pixelgenaue 1:1-Reproduktion von Adobe Lightroom. Lightroom und RapidRAW verwenden unterschiedliche RAW-Engines, Farb-Pipelines, Tonwertverarbeitung und Regler-Interpretationen.

[![Latest Release](https://img.shields.io/github/v/release/trueslator/RapidRAW-Preset-Migrator?label=Download)](https://github.com/trueslator/RapidRAW-Preset-Migrator/releases/latest)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Windows](https://img.shields.io/badge/Windows-supported-blue)](#windows)
[![Linux](https://img.shields.io/badge/Linux-supported-green)](#linux--nobara--flatpak)

**[Aktuelle Version herunterladen](https://github.com/trueslator/RapidRAW-Preset-Migrator/releases/latest)**  
**[English README](README.md)**

---

## Warum dieses Projekt entstanden ist

RapidRAW ist ein schneller, quelloffener RAW-Editor für Windows, macOS und Linux.

Für Fotografen, die Lightroom verlassen möchten, kann aber ein Punkt überraschend schwierig werden: Über Jahre angesammelte Presets bestehen oft aus deutlich mehr als ein paar Reglerwerten. Sie können eigene Kurven, HSL-Einstellungen, Körnung, Split Toning, Schwarzweiß-Mixer, Weißabgleichsänderungen und Verweise auf Camera Profiles enthalten.

Der RapidRAW Preset Migrator wurde entwickelt, um beim Wechsel zu RapidRAW möglichst viel von dieser **kreativen Absicht und dem visuellen Charakter** zu erhalten.

Entstanden ist das Projekt aus einer persönlichen Migration eines über viele Jahre gewachsenen Foto-Workflows von **Windows 11 und Adobe Lightroom zu Nobara Linux und RapidRAW**.

---

## Funktionen

- ältere Lightroom-Presets im Format **`.lrtemplate`** konvertieren
- moderne Lightroom-/Adobe-Camera-Raw-Presets im Format **`.xmp`** konvertieren
- einzelne Dateien, Ordner oder ZIP-Archive verarbeiten
- Ordnerstrukturen übernehmen
- native RapidRAW-Dateien im Format **`.rrpreset`** erzeugen
- Farb- und Schwarzweiß-Presets erkennen
- viele häufig verwendete Lightroom-Einstellungen übertragen
- Lightroom-Weißabgleichsverschiebungen berücksichtigen, wenn im XMP verwertbare `AsShot`-Werte vorhanden sind
- HSL, Punktkurven, parametrische Kurven, Grain, Split Toning / Color Grading und weitere Einstellungen unterstützen
- nicht sicher übertragbare Einstellungen im Report dokumentieren
- hunderte Presets über eine lokale HTML-Oberfläche verwalten
- Favoriten markieren
- migrierte Presets mit **`[MIG]`** kennzeichnen
- alle migrierten Presets entfernen, ohne native RapidRAW-Presets anzufassen
- vor Änderungen automatisch ein Backup der RapidRAW-`presets.json` erzeugen
- Windows, natives Linux und RapidRAW-Flatpak-Installationen automatisch erkennen
- optional Companion-LUTs aus **eigenen** DCP-Camera-Profiles erzeugen
- Camera-Profile-Library mit Dropdown-Auswahl passender Profile
- erzeugte LUTs cachen und wiederverwenden
- keine zusätzlichen Python-Pakete erforderlich

---

## Unterstützte Lightroom-Presetformate

| Format | Unterstützung |
|---|---|
| `.lrtemplate` | ✅ Unterstützt |
| `.xmp` | ✅ Unterstützt |
| gemischte Ordner / ZIP-Archive | ✅ Unterstützt |
| DNG Camera Profiles `.dcp` | ✅ Optional, vom Benutzer bereitgestellt |
| AI-/Adaptive-Masken | ⚠️ Nicht reproduzierbar |
| lokale Masken | ⚠️ Nicht reproduzierbar |
| Lightroom-Funktionen ohne RapidRAW-Gegenstück | ⚠️ Werden gemeldet, nicht stillschweigend verworfen |

---

## Hinweis zur Genauigkeit

Das Ziel ist eine **Migration des Looks**, nicht die Emulation der Lightroom-Rendering-Engine.

Ein Preset kann Werte enthalten, die auf dem Papier identisch aussehen, sich in einem anderen RAW-Konverter aber anders auswirken. Zum Beispiel:

- Lightroom und RapidRAW können Lichter und Schatten unterschiedlich interpretieren
- Camera Calibration ist zwischen den Engines nicht direkt äquivalent
- Tonkurven können an unterschiedlichen Stellen der Verarbeitungskette angewendet werden
- Camera Profiles können sensorspezifische Kalibrierungsdaten enthalten
- Objektivkorrekturen und Vignettierungsparameter haben nicht immer direkte Gegenstücke
- moderne XMP-Presets können Masken oder adaptive Funktionen enthalten, die RapidRAW nicht unterstützt

Der Converter verwendet deshalb eine Kombination aus:

1. direkter Übertragung, wenn die Semantik ausreichend ähnlich ist,
2. skalierter oder angenäherter Übertragung, wenn Tests gezeigt haben, dass dies sinnvoller ist,
3. ausdrücklichen Warnungen, wenn eine zuverlässige Übersetzung nicht möglich ist.

**Wichtige migrierte Presets sollten immer visuell mit dem Lightroom-Original verglichen werden, bevor sie produktiv eingesetzt werden.**

---

# Schnellstart

## 1. Download

Die aktuelle Version herunterladen:

**https://github.com/trueslator/RapidRAW-Preset-Migrator/releases/latest**

ZIP-Datei in einen normalen Ordner entpacken.

Benötigt wird **Python 3.10 oder neuer**.

Zusätzliche Python-Pakete sind nicht erforderlich.

---

## Windows

Starten:

```text
Start_Converter_Windows.bat
```

Anschließend ein Lightroom-Preset, einen Ordner oder ein ZIP-Archiv auswählen.

Nach der Konvertierung den erzeugten Ausgabeordner öffnen und dort starten:

```text
Start_Preset_Manager_Windows.bat
```

Vor dem Schreiben der Presets nach RapidRAW bitte **RapidRAW vollständig schließen**.

> Der Preset Manager benötigt die bei der Konvertierung erzeugte `migration_catalog.json` und wird deshalb aus dem jeweiligen **Ausgabeordner** gestartet.

---

## Linux / Nobara / Flatpak

Die Starter einmalig ausführbar machen:

```bash
chmod +x Start_Converter_Linux.sh Start_Preset_Manager_Linux.sh
```

Converter starten:

```bash
./Start_Converter_Linux.sh
```

Nach der Konvertierung im erzeugten Ausgabeordner:

```bash
./Start_Preset_Manager_Linux.sh
```

Der Manager erkennt typische RapidRAW-Pfade automatisch, einschließlich Flatpak-Installationen.

Bei einer RapidRAW-Flatpak-Installation liegen die Programmdaten typischerweise unter:

```text
~/.var/app/io.github.CyberTimon.RapidRAW/
```

---

# Preset Manager

Der Converter erzeugt einen lokalen HTML-basierten Preset Manager.

Damit lassen sich unter anderem:

- Presets durchsuchen
- nach Quellordnern filtern
- `.lrtemplate` und `.xmp` filtern
- nur tatsächlich gewünschte Presets auswählen
- Favoriten markieren
- kompatible DCP-Varianten auswählen
- ausgewählte Presets mit RapidRAW synchronisieren
- migrierte Presets wieder entfernen

Alle vom Manager geschriebenen Presets erhalten den Präfix:

```text
[MIG]
```

Dadurch kann der Manager zwischen migrierten Presets und direkt in RapidRAW erstellten Presets unterscheiden.

Favoriten werden zusätzlich in einer eigenen Gruppe gespiegelt:

```text
[MIG] Favoriten
```

Auswahl und Favoritenstatus speichert der Manager separat. Das Entfernen aller `[MIG]`-Presets aus RapidRAW löscht deshalb nicht automatisch die gespeicherten Favoriten.

---

# Camera Profile Library

Einige Lightroom-Presets verweisen auf ein DNG Camera Profile (`.dcp`).

Der Migrator enthält **keine** Camera Profiles von Adobe, VSCO oder anderen Drittanbietern.

Wer rechtmäßig eigene kompatible `.dcp`-Dateien besitzt, kann diese in folgenden Ordner kopieren:

```text
CameraProfiles/
```

Unterordner sind erlaubt.

Der Preset Manager scannt die Bibliothek. Verweist ein Preset auf ein passendes Camera Profile, werden kompatible Varianten in einem Dropdown angezeigt.

Beispiel:

```text
Kodak Portra 800 v2C
├── Canon EOS 5D Mark II
├── Canon EOS 5D Mark III
├── Canon EOS 6D
└── ...
```

Existieren mehrere kameraspezifische Profile, entscheidet das Tool bewusst **nicht automatisch**, welches davon verwendet werden soll.

Wird eine DCP-Variante ausgewählt, kann der Migrator den nutzbaren **kreativen Look-Anteil** extrahieren und eine Companion-LUT im Format `.cube` erzeugen.

Sensorspezifische Camera-Calibration-Matrizen werden **nicht blind auf andere Kameras übertragen**.

Erzeugte LUTs werden gecacht und bei späterer Verwendung wiederverwendet.

---

## Was passiert ohne DCP?

Nichts Kritisches.

Das normal konvertierte RapidRAW-Preset bleibt als Fallback verfügbar.

DCP-Dateien können auch später noch in `CameraProfiles/` ergänzt werden. Nur weil später weitere Camera Profiles gefunden werden, müssen die ursprünglichen Lightroom-Presets nicht erneut konvertiert werden.

---

# Was wird migriert?

Typische Zuordnungen umfassen unter anderem:

- Belichtung
- Kontrast
- Lichter
- Schatten
- Weiß
- Schwarz
- Texture / Structure
- Klarheit
- Dehaze
- Dynamik
- Sättigung
- HSL
- Luma-/RGB-Punktkurven
- parametrische Kurven, sofern sinnvoll
- Körnung
- Split Toning / Color Grading
- Schwarzweiß-Mixer als Annäherung
- Weißabgleichsverschiebungen bei unterstützten XMP-Fällen
- ausgewählte Camera-Calibration-Werte als Annäherung

Details zur Umsetzung und zu bekannten Grenzen stehen in:

**[MAPPING.md](MAPPING.md)**

---

# Konvertierungsberichte

Die Ausgabe kann Reports enthalten, die dokumentieren, was bei der Migration passiert ist.

Je nach Eingabe können dort beispielsweise stehen:

- Quellformat
- referenziertes Camera Profile
- Process Version
- Farb-/Schwarzweiß-Erkennung
- direkt übertragene Parameter
- angenäherte Parameter
- nicht unterstützte Einstellungen
- Warnungen

Das ist bewusst so: Einstellungen, die sich nicht sicher darstellen lassen, sollen **sichtbar** sein und nicht unbemerkt verschwinden.

---

# Sicherheit

Der Preset Manager arbeitet bewusst konservativ.

Vor Änderungen an RapidRAW:

- wird ein Backup von `presets.json` erzeugt
- verweigert der Manager das Schreiben, solange RapidRAW läuft
- verwaltet er nur Einträge mit `[MIG]`
- bleiben native RapidRAW-Presets unangetastet

Trotzdem handelt es sich um ein unabhängiges Community-Tool.

Von wichtigen Lightroom-Presets, Camera Profiles und RapidRAW-Konfigurationsdaten sollten weiterhin Backups vorhanden sein.

---

# Datenschutz

Die Preset-Konvertierung erfolgt lokal auf dem eigenen Rechner.

Lightroom-Presets oder Camera Profiles müssen für die Verwendung des Tools nirgendwo hochgeladen werden.

---

# Presets und Camera Profiles von Drittanbietern

Dieses Repository enthält **keine**:

- kommerziellen Lightroom-Presets
- VSCO-Profile
- Adobe Camera Profiles
- DCP-Dateien von Drittanbietern
- aus fremden Profilen erzeugten LUTs

Jeder Benutzer ist selbst dafür verantwortlich, dass die von ihm verwendeten Presets oder Camera Profiles rechtmäßig genutzt werden dürfen.

Die persönliche Konvertierung eines Presets oder Profils bedeutet nicht automatisch, dass das Original oder daraus erzeugte Daten weiterverbreitet werden dürfen.

Siehe:

- [DISCLAIMER.md](DISCLAIMER.md)
- [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)

---

# Projektdateien

```text
RapidRAW-Preset-Migrator/
├── rapidraw_preset_migrator.py
├── lrtemplate_converter.py
├── dcp_support.py
├── preset_manager.py
├── Start_Converter_Windows.bat
├── Start_Converter_Linux.sh
├── Start_Preset_Manager_Windows.bat
├── Start_Preset_Manager_Linux.sh
├── README.md
├── README_DE.md
├── MAPPING.md
├── DISCLAIMER.md
├── THIRD_PARTY_NOTICES.md
├── CONTRIBUTING.md
├── CHANGELOG.md
├── RELEASE_NOTES.md
├── LICENSE
└── tests/
```

---

# Tests

Das Projekt enthält automatisierte Smoke- und Sicherheitstests für wichtige Migrationspfade, unter anderem:

- `.lrtemplate`
- `.xmp`
- Schwarzweiß-Presets
- Tonkurven
- Camera-Profile-Matching
- Sicherheitsverhalten des Preset Managers
- Erhalt nativer RapidRAW-Presets

Zusätzlich wurde der Workflow mit einer realen Lightroom-Sammlung aus hunderten älteren Presets und hunderten DCP-Profilen getestet.

---

# RapidRAW

RapidRAW selbst ist ein separates Open-Source-Projekt von CyberTimon.

RapidRAW:

**https://github.com/CyberTimon/RapidRAW**

Flathub:

**https://flathub.org/apps/io.github.CyberTimon.RapidRAW**

Dieses Projekt ist **weder mit Adobe noch mit dem RapidRAW-Projekt verbunden oder von diesen offiziell unterstützt**.

Adobe, Lightroom und Camera Raw sind Marken ihrer jeweiligen Rechteinhaber.

---

# Mitmachen

Fehlerberichte, Test-Presets zur Aufdeckung von Mapping-Problemen, Verbesserungen der Dokumentation und Pull Requests sind willkommen.

Bitte **keine kommerziellen Presets oder proprietären Camera Profiles** an öffentliche Issues anhängen, sofern keine Rechte zur Weitergabe bestehen.

Siehe:

**[CONTRIBUTING.md](CONTRIBUTING.md)**

---

# Lizenz

RapidRAW Preset Migrator steht unter der **MIT-Lizenz**.

Siehe [LICENSE](LICENSE).

---

## Abschließender Hinweis

> **Ein migriertes Preset ist eine Annäherung an den ursprünglichen Lightroom-Look und keine garantierte 1:1-Reproduktion.**

Wenn die migrierte Version den kreativen Charakter erhält und in RapidRAW einen brauchbaren Ausgangspunkt liefert, hat die Migration ihr Ziel erreicht.
