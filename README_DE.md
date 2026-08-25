# RapidRAW Preset Migrator 1.0 — Deutsche Kurzanleitung

Der **RapidRAW Preset Migrator** ist ein inoffizielles Community-Tool, das alte Lightroom-`.lrtemplate`-Presets in RapidRAW-`.rrpreset`-Presets überträgt und anschließend über einen lokalen HTML-Manager verwaltet.

## Das Besondere an Version 1.0: Camera Profile Library

Nach der Konvertierung gibt es im Ausgabeordner:

```text
CameraProfiles/
```

Dort legst du einfach deine **eigenen `.dcp`-Kameraprofile** ab. Unterordner sind erlaubt. Der Preset-Manager überwacht/scant diesen Ordner und zeigt bei jedem Preset im Dropdown nur DCPs an, deren interner Profilname **exakt** zu dem `CameraProfile` passt, das im alten Lightroom-Preset gespeichert ist.

Beispiel:

```text
Lightroom erwartet: Kodak Portra 800 v2C

Dropdown:
Standard / ohne DCP
Canon EOS 5D — Kodak Portra 800 v2C
Canon EOS 5D Mark II — Kodak Portra 800 v2C
Canon EOS 5D Mark III — Kodak Portra 800 v2C
...
```

Damit entscheidet der Nutzer selbst, welche Kamera-Variante verwendet werden soll. Das Tool rät nicht.

**Neue DCPs können jederzeit später in `CameraProfiles/` kopiert werden. Die `.lrtemplate` müssen dafür nicht erneut konvertiert werden.**

## Windows

1. ZIP entpacken.
2. `Start_Converter_Windows.bat` starten.
3. Preset-ZIP/Ordner auswählen und konvertieren.
4. Eigene `.dcp`-Profile in den erzeugten Ordner `CameraProfiles/` kopieren.
5. RapidRAW vollständig schließen.
6. Im erzeugten Ausgabeordner `Start_Preset_Manager_Windows.bat` starten.
7. Presets anhaken, optional CameraProfile im Dropdown wählen und auf **START** klicken.

## Linux / Nobara / Flatpak

Einmalig:

```bash
chmod +x Start_Converter_Linux.sh Start_Preset_Manager_Linux.sh
```

Konverter starten:

```bash
./Start_Converter_Linux.sh
```

Danach im erzeugten Ausgabeordner:

```bash
./Start_Preset_Manager_Linux.sh
```

Der Manager erkennt Windows, natives Linux und die RapidRAW-Flatpak-Installation automatisch. Über `RAPIDRAW_PRESETS_JSON` kann ein Pfad manuell vorgegeben werden.

## `[MIG]`-Prinzip

Alle vom Manager in RapidRAW angelegten Einträge beginnen mit `[MIG]`. Dadurch kann der Manager migrierte Presets gezielt ersetzen oder löschen, ohne in RapidRAW selbst erstellte Presets anzufassen.

- Vor jeder Änderung wird `presets.json` gesichert.
- Während RapidRAW läuft, schreibt der Manager absichtlich nicht.
- Favoriten bleiben im Manager gespeichert und werden zusätzlich nach `[MIG] Favoriten` gespiegelt.
- Gewählte CameraProfiles bleiben ebenfalls gespeichert, auch wenn alle `[MIG]`-Presets aus RapidRAW gelöscht werden.

## DCP/LUT-Verarbeitung

Eine Companion-LUT wird **erst dann erzeugt**, wenn du ein DCP im Dropdown auswählst und das Preset übernimmst. Die LUT wird gecacht und bei unverändertem Profil wiederverwendet.

Die kameraabhängigen Input-Matrizen des DCP werden nicht auf andere Kameras übertragen. RapidRAW entwickelt weiterhin das RAW der tatsächlichen Kamera; der Migrator nutzt den kreativen Profilanteil als Begleit-Look.

## Wichtig

Das Tool enthält **keine** Lightroom-Presets, DCP-Profile oder kommerziellen Filmlooks. Diese Dateien müssen vom Nutzer selbst bereitgestellt werden. Bitte nur Dateien verwenden und weitergeben, für die entsprechende Nutzungsrechte bestehen.

Lightroom und RapidRAW verwenden unterschiedliche RAW-Engines. Die Migration ist deshalb keine mathematische 1:1-Kopie. Ziel ist, den beabsichtigten Look alter Presets möglichst gut zu erhalten.
