# Blocksmith

[English](../README.md) · [Español](README.es.md) · [Français](README.fr.md) · **Deutsch** · [Русский](README.ru.md)

Erstelle bearbeitbare Levelprototypen in **Blender 5+** und exportiere sie nach **Godot**. Version **0.8.7**, lizenziert unter **GPL-3.0-or-later**.

Blocksmith ist eine eigenständige Umsetzung, die sich an öffentlich beschriebenen Arbeitsabläufen von BlockD orientiert. Nicht alle Funktionen von BlockD sind enthalten. Die Oberfläche unterstützt Englisch, Spanisch, Französisch, Deutsch und Russisch. Wähle die Sprache unter **Edit → Preferences → Interface → Translation** und aktiviere **Interface** und **Tooltips**. Blocksmith folgt der Sprache von Blender; Namen vorhandener Objekte bleiben erhalten.

## Funktionen

- Zeichne Wände, Böden, Räume, Treppen und Rampen direkt in der 3D-Ansicht; 32 Vorlagen mit Vorschau stehen bereit.
- Ändere Abmessungen im Seitenbereich oder über Griffe in der Ansicht. Türen, Fenster, Bögen, Dächer, Geländer und gekrümmte Wände werden unterstützt.
- Raste am Raster sowie an sichtbaren Punkten und Kanten ein, einschließlich ausgewerteter Boolean- und Array-Geometrie. Verbinde gerade Wände auf Gehrung, stumpf oder als T-Verbindung.
- Zeichne nichtdestruktive Öffnungen in geschlossene Meshes und wiederhole Objekte oder Öffnungen mit dem Reihenwerkzeug.
- Verbinde zwei Höhen mit einer geraden Treppe oder Rampe. Nutze Spielerreferenzen und Hinweise zu Stufen, Durchgängen, Deckung und Neigung.
- Verwende die mitgelieferten Kenney-Prototyptexturen, vergebe Gameplay-Tags und exportiere GLB oder FBX.
- Markiere einzelne Meshes für **freie Platzierung**, um die Geometriebeschränkungen von Blocksmith aufzuheben.
- Erzeuge Level aus validiertem JSON über eine Python-Befehlszeile, ohne das Add-on in deiner persönlichen Blender-Sitzung zu installieren.


Deaktiviere **Blocksmith in dieser Datei aktivieren** oben in der Seitenleiste, um frei zu modellieren oder zu formen. Die Einstellung wird in der `.blend` gespeichert und gilt für alle Szenen der Datei. Werkzeuge, Tastenkürzel, Maßanzeigen, automatische Aktualisierungen und Geometrie-Rücksetzungen werden pausiert; das Add-on bleibt in Blender aktiviert. Aktiviere dieselbe Einstellung zum Fortsetzen, ohne alte Geometrie wiederherzustellen. Die nativen Einrasteinstellungen von Blender bleiben unverändert.

## Installation

1. Lade `blocksmith-0.8.7.zip` unter [Releases](https://github.com/hlophlopgaming/Blocksmith/releases) herunter oder erstelle das Archiv im Hauptverzeichnis des Repositories:

   ```sh
   python3 tools/package.py
   ```

2. Öffne in Blender **Edit → Preferences → Get Extensions → Menü oben rechts → Install from Disk**. Wähle das heruntergeladene ZIP oder `dist/blocksmith-0.8.7.zip` und aktiviere die Erweiterung.
3. Drücke in der 3D-Ansicht **N** und öffne den Reiter **Blocksmith**.

Zum Erstellen des Archivs wird Python 3.10+ benötigt; zusätzliche Python-Pakete sind nicht erforderlich. Die automatischen **Source code**-Archive von GitHub enthalten den Quellcode und sind keine installierbaren Erweiterungsarchive.

## Einstieg

1. Klicke auf **Konstruktionen zeichnen** oder drücke **Umschalt+Alt+D**.
2. Wähle eine Form in der oberen Reihe oder unter **Nächste Konstruktion**. **Vorlagenkatalog** öffnet den Vorlagenkatalog.
3. Ziehe mit der linken Maustaste und lasse sie los, um die Konstruktion zu erstellen. Wähle sie aus, um Abmessungen zu ändern oder die orangefarbenen Griffe zu verwenden.
4. Aktiviere **Wiederholen**, um weitere Teile zu zeichnen. **Esc / rechte Maustaste** bricht die aktuelle Geste ab oder kehrt zur Auswahl zurück.

Beim gewöhnlichen Zeichnen deaktiviert **Strg** vorübergehend das Einrasten. **Umschalt** begrenzt die Richtung auf 45°-Schritte oder erzeugt eine quadratische Grundfläche, **H** ändert die Höhe und **F** kehrt Treppen oder Rampen um. Zwischen den Gesten bleiben Navigation und Seitenbereich bedienbar.

Ziehe für gerade Treppen und Rampen vom unteren Boden zur Kante der oberen Plattform; die umgekehrte Richtung funktioniert ebenfalls. Zeichne für Türen, Fenster und Bögen ein Rechteck auf ein geschlossenes Mesh: Jede Öffnung fügt einen nichtdestruktiven Boolean-Ausschnitt hinzu. Gekrümmte Wände entstehen aus Punkten, einer Freihandlinie oder einem Dreipunktbogen. Die [ausführliche russische Anleitung](manual.ru.md) beschreibt die Bedienung der erweiterten Werkzeuge.

## Freie Platzierung

Wähle ein Mesh aus und aktiviere **N → Blocksmith → Blocksmith-Regeln ignorieren**. Dies ist eine gespeicherte Objekteigenschaft, die im Objekt- und Bearbeitungsmodus verfügbar ist. Für mehrere ausgewählte Meshes nutze **Auf Auswahl anwenden**, nachdem du die Eigenschaft am aktiven Mesh gesetzt hast.

Markierte Meshes dürfen andere Objekte überlappen, verschoben, gedreht und skaliert werden, negative Skalierung erhalten und manuelle Änderungen oder umgedrehte Normalen behalten, ohne dass Blocksmith die Änderungen zurücksetzt. Andere Module dürfen markierte Meshes ebenfalls überlappen. Die Markierung verändert weder Geometrie noch Materialien oder Gameplay-Tags. Sie bleibt beim Duplizieren, Umwandeln in ein Mesh sowie Speichern und Laden einer `.blend`-Datei erhalten. Das Mesh bleibt für Einrasten und Export verfügbar, sofern seine Rolle es nicht bereits ausschließt, etwa als Schneideobjekt oder Referenzfigur.

Das Ausschalten der Eigenschaft stellt den normalen Schutz eines Blocksmith-Moduls wieder her. Verletzt der aktuelle Zustand die Regeln, bleibt der Schutz ausgeschaltet: Mesh und manuelle Änderungen bleiben erhalten. Korrigiere zuerst Überschneidungen, Skalierung oder Normalen. Gewöhnliche Blender-Meshes sind auch ohne diese Markierung unbeschränkt. Die Funktion unterstützt Rückgängig und Wiederholen.

Wähle für Skripte die Meshes aus und verwende:

```python
obj.bs.free_placement = True
bpy.ops.blocksmith.free_placement(enabled=True)
bpy.ops.blocksmith.free_placement(enabled=False)
```

Die Markierung umgeht die Prüfung: Überlappende oder fehlerhafte markierte Geometrie kann im Export landen. Blenders Einrastfunktion und Maßhinweise sind davon unabhängige Einstellungen. Eine Transformation des Elternobjekts kann weiterhin abgelehnt werden, wenn sie ein geschütztes Kindobjekt betrifft.

## Geometrieschutz

Nicht markierte Blocksmith-Module verhindern Überschneidungen, negative oder Nullskalierung, offene Meshes und umgedrehte Normalen. Flächenkontakt ist erlaubt. Geprüft wird die ausgewertete Geometrie, nicht nur der Begrenzungsrahmen. Gewöhnliche oder importierte Meshes, Referenzen, Wasser und aktive Boolean-Schneideobjekte sind von diesen Volumenprüfungen ausgenommen.

Der Schutz gilt für Add-on-Operationen, native Transformationen, Änderungen nach Verlassen des Bearbeitungsmodus sowie Rückgängig/Wiederholen. Beim Export werden geschützte Module erneut geprüft. Vorhandene Szenen werden ohne Löschen von Objekten als Ausgangszustand angenommen; Konflikte geschützter Module müssen vor dem Export behoben werden. Die numerischen Prüfungen können bei komplexen Szenen langsamer sein und stellen keine mathematische Garantie dar.

## Export nach Godot

Öffne **Nach Godot exportieren**, wähle **GLB** oder **FBX**, die zu exportierenden Objekte, den Zielordner und den Dateinamen. Speichere die `.blend`-Datei, bevor du einen relativen Ausgabepfad verwendest.

GLB ist das hauptsächlich getestete Format. Bei aktivierten Kollisionen erhalten geschlossene Meshes das Godot-Suffix `-col`. Wasser wird sichtbar, aber ohne Kollision exportiert. Referenzfiguren, verwendete Schneideobjekte, ausgeblendete Archive ursprünglicher Meshes und temporäre Schutzobjekte werden ausgeschlossen. Gekrümmte Wände werden in Meshes umgewandelt. Vorhandene Exportdateien werden nicht überschrieben: Wähle einen anderen Namen oder Ordner.

## JSON-Befehlszeile

Führe die Befehle im Hauptverzeichnis aus, mit Python 3.10+ und Blender 5+ in `PATH`:

```sh
python3 tools/levelgen.py shapes
python3 tools/levelgen.py presets
python3 tools/levelgen.py schema
python3 tools/levelgen.py validate examples/courtyard.json
python3 tools/levelgen.py generate examples/courtyard.json --out-dir generated/courtyard
```

Erzeugt werden `level.blend`, `level.glb`, `level.spec.json`, `report.json` und `blender.log`. Mit `--blender /pfad/zu/blender` wählst du eine andere ausführbare Datei, mit `--overwrite` ersetzt du frühere Ergebnisse. Blender läuft in einem getrennten Hintergrundprozess. Schlägt die Validierung fehl, bleiben vorherige Exporte erhalten. Die Ausgabe erfolgt als JSON; Fehler werden über stderr und einen Rückgabecode ungleich null gemeldet.

Die Spezifikation verwendet **Meter**, Blender-Koordinaten mit **Z nach oben** und Eulerwinkel in **Grad**. GLB konvertiert zur Y-Hochachse von Godot. Siehe [Schema](../examples/level.schema.json), [Beispiele](../examples/) und den Befehl `schema`. Unbekannte Schlüssel, doppelte Namen, ungültige Zahlen und übermäßige Komplexität werden abgelehnt; JSON führt keinen Python-Code aus. Die Markierung für freie Platzierung ist eine Mesh-Einstellung in Blender und kein Feld des aktuellen CLI-Schemas.

## Entwicklung und Prüfungen

```sh
python3 -m unittest discover -s tests -p 'test_*.py' -v
blender -b -noaudio --factory-startup --python-exit-code 1 --python tests/free_placement_check.py
blender -b -noaudio --factory-startup --python-exit-code 1 --python tests/guard_check.py
python3 tools/package.py
```

Siehe [CONTRIBUTING](../CONTRIBUTING.md), [CHANGELOG](../CHANGELOG.md) und den [Prüfbericht zu 0.8.3](validation-0.8.3.md), derzeit auf Russisch. GitHub Actions ist für Python-Tests, Syntaxprüfung und das Erstellen des ZIPs eingerichtet. Tests der 3D-Ansicht benötigen eine grafische Umgebung. Sicherungen, Build-Artefakte und erzeugte Szenen werden von Git ausgeschlossen.

## Aktuelle Grenzen

Blender 5.0 ist die angegebene Mindestversion, wurde aber nicht separat getestet. Frühere Prüfungen deckten Blender 5.2.3, 5.3.0 und Godot 4.7.2 ab. FBX wurde weniger geprüft als GLB. Wandketten schließen sich nicht automatisch und verschieben beim Bearbeiten einer Wand keine Nachbarwände. Verwende **Umschalt+D** für unabhängig bearbeitbare Kopien; **Alt+D** teilt das Mesh, aber nicht seine Parameter. Apply Scale unterstützt positive gleichmäßige Skalierung auf unveränderten parametrischen Meshes mit nur einem Benutzer. Die Maßhinweise simulieren keinen Spielcontroller. Exportierte Kollisionen sind statische Dreiecksnetze. Für den Produktionseinsatz kann eine Optimierung der Prototypgeometrie nötig sein.

## Lizenz

Blocksmith-Code: **GPL-3.0-or-later**, siehe [LICENSE](../LICENSE). Eine Kopie ist im Installationsarchiv enthalten.

[Kenney Prototype Textures](https://kenney.nl/assets/prototype-textures): **CC0**. Die [Lizenz](../blocksmith/assets/kenney/License.txt) und [Herkunftsinformationen](../blocksmith/assets/kenney/SOURCE.txt) liegen den Ressourcen bei.
