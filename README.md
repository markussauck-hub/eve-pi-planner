# EVE PI Planner

LincolnSoft-Tool für Planetary Interaction in EVE Online: welche PI-Ketten sich lohnen,
welche Planetentypen und wie viele Fabriken man dafür braucht – und wann die Extraktoren
der eigenen Kolonien ablaufen. Look & Feel wie [Price Checker](https://github.com/markussauck-hub/eve-price-checker)
und [Invention Helper](https://github.com/markussauck-hub/eve-invention-helper).

## Bereiche

| Bereich | Was er kann |
|---|---|
| **Ketten-Ranking** | Alle P1–P4 als Tabelle: Gewinn/Tag einer Fabrik auf einem *Fabrikplaneten* (Inputs eine Stufe darunter gekauft) und *selbst extrahiert* (ganze Kette ab P0, Gewinn je Extraktionsplanet). Filter nach Stufe und eigenen Planetentypen, sortierbar, Klick öffnet den Planer. |
| **Produktionsplaner** | Zielprodukt + Anzahl End-Fabriken → komplette Kette bis P0 mit Bedarf/h, Fabriken je Stufe (exakt und aufgerundet), P0-Bedarf, Anzahl Extraktionsplaneten, kleinste Planetentyp-Kombinationen. Pro Zwischenprodukt **bauen oder kaufen**, Einkaufsliste als Multibuy, Gewinnrechnung inkl. Steuern und Vergleich „eigenes P1 direkt verkaufen“. Dazu ein **Fitting-Check** für einen Planeten (CPU/PG nach Command-Center-Stufe). |
| **Systeme** | Umkreissuche (Sprünge über Stargates) um ein Startsystem oder Suche über alle Systeme: welche Systeme haben die benötigten Planetentypen, Filter Highsec/Lowsec/Nullsec/J-Space. |
| **Kolonien** | Optional mit EVE-Login, **mehrere Charaktere**: alle Kolonien mit Extraktoren, Köpfen, Ertrag und Ablauf-Countdown, Fabriken je Planet. Export der Ablaufzeiten als **.ics** (Kalender mit Erinnerung 1 h vorher) und Browser-Benachrichtigung, solange der Tab offen ist. |

Einstellungen (Hub, Preisbasis, Gebühren, Customs-Steuer, P0-Ertrag je Planet) gelten für Ranking und Planer
und werden im Browser gespeichert (`lincolnsoft.pi.*`). Musik/Sounds teilen sich die Einstellung mit den anderen
Tools (`lincolnsoft.snd.*`). Direktlinks: `#ranking`, `#plan/<TypeID>`, `#systems`, `#colonies`.

## Rechenmodell (wichtig zum Verstehen der Zahlen)

- **Rezepte** aus der SDE: P0→P1 3000 → 20 je 30 min, P1→P2 40+40 → 5 je h, P2→P3 10+10(+10) → 3 je h,
  P3→P4 6+6+6 (bzw. 40 P1) → 1 je h. Fabriken pro Stufe = Bedarf ÷ Leistung einer Fabrik.
- **P0-Ertrag ist eine Eingabe**, keine Rechnung: der Ertrag eines Extraktors hängt von der Ressourcen-Karte
  des einzelnen Planeten ab, die weder in der SDE noch öffentlich per ESI steht. Default 6.000 P0/h je Planet.
- **Customs-Steuer**: Export = Basiswert × Steuersatz, Import = 50 % davon. Basiswerte je Stufe aus
  `invTypes.basePrice`, sonst Rückfall P0 5 · P1 400 · P2 7.200 · P3 60.000 · P4 1.200.000 ISK.
  *Die Rückfallwerte bitte einmal im Spiel gegenprüfen* (Export-Fenster eines Customs Office).
- **P1-Transport**: Haken im Planer = eigenes P1 wird vom Extraktions- zum Fabrikplaneten verschifft
  (Export + Import versteuert). P2+ wird auf dem Fabrikplaneten weiterverarbeitet.
- **Eigenes P0 kostet nichts** – Zeit, Klicks und Command-Center-Kosten sind nicht eingerechnet.
- **Fitting**: Gebäudewerte aus der SDE (dgm-Attribute), sonst Konstanten; Command Center je Stufe als Tabelle.
  Links kosten je nach Länge CPU/PG → als Reserve in % geschätzt.

## Aufbau

| Datei | Zweck |
|---|---|
| `index.html` | Die komplette Seite (HTML/CSS/JS, keine externen Abhängigkeiten) |
| `build_data.py` | Lädt den Fuzzwork-SDE-Dump, erzeugt `pi.json` (Rezepte, Stufen, Planeten→P0, Gebäude) und `universe.json` (Systeme, Planetentypen, Gates) |
| `tests/make_fixture.py` | Mini-SDE im Fuzzwork-Format (echte Rezepte, ausgedachtes Universum) zum Offline-Testen |
| `fonts/` | Chakra Petch, Martian Mono, Orbitron (lokal, OFL) |
| `.github/workflows/pages.yml` | Testet mit der Mini-SDE, baut die Daten, veröffentlicht auf GitHub Pages und aktualisiert den Branch `deploy` – bei jedem Push, dienstags und manuell |

`pi.json` und `universe.json` werden **nicht** eingecheckt. `build_data.py` bricht mit klarer Meldung ab,
wenn die SDE anders aussieht als erwartet (fehlende Spalten, zu wenige Rezepte/Systeme, P0 ohne Planetentyp).

## Lokal testen

```bash
python build_data.py                     # echte SDE (Internet nötig)
# oder offline:
python tests/make_fixture.py /tmp/sde && python build_data.py --local /tmp/sde
python -m http.server 8000               # dann http://localhost:8000 öffnen
```

## Einrichtung

1. Repo `markussauck-hub/eve-pi-planner` (öffentlich) mit diesen Dateien befüllen.
2. **Settings → Pages → Source: „GitHub Actions“**.
3. Actions → „Build & Deploy“ → *Run workflow*. Danach erreichbar unter
   `https://markussauck-hub.github.io/eve-pi-planner/`.
4. **Lincolnsoft Server**: den Branch `deploy` nach `~/server/site/pi-planner/` spiegeln – in `sync-tool.sh`
   den Eintrag für `pi-planner` ergänzen (wie bei `price-checker` und `invention-helper`).
5. **Homestation**: Kachel „PI Planner“ → `/pi-planner/`.

### EVE-Login (nur für den Kolonie-Monitor)

Zwei Apps auf [developers.eveonline.com](https://developers.eveonline.com/) anlegen – eine je Host:

| App | Callback-URL | Scopes |
|---|---|---|
| PI Planner (GitHub) | `https://markussauck-hub.github.io/eve-pi-planner/` | `esi-planets.manage_planets.v1`, `esi-skills.read_skills.v1` |
| PI Planner (LincolnSoft) | `https://lincolnsoft.de/pi-planner/` | dieselben |

Die beiden Client-IDs in `index.html` im Abschnitt „EVE SSO“ eintragen (`CLIENT_ID_GITHUB`, `CLIENT_ID_LINCOLNSOFT`).
Ohne Client-ID zeigt die Seite beim Login einen Hinweis, alles andere funktioniert.

## Datenschutz & Sicherheit

- Kein Tracking, keine externen Schriften oder CDNs. Der Browser spricht nur mit `esi.evetech.net`,
  `images.evetech.net` und (beim Login) `login.eveonline.com`.
- Login per OAuth2 + PKCE ohne Client-Secret direkt bei CCP. Tokens, Kolonie-Daten und Planetennamen
  bleiben im `localStorage` dieses Browsers (`lincolnsoft.pi.*`).
- `esi-planets.manage_planets.v1` klingt nach Schreibrechten, ESI bietet dafür aber nur Lese-Abfragen an.
- **Entfernen** beim Charakter löscht das Token und widerruft es bei CCP.

## Datenquelle

[Fuzzwork SDE-Dump](https://www.fuzzwork.co.uk/dump/latest/csv/) (CSV), Preise live über ESI.
EVE Online und alle zugehörigen Inhalte © CCP hf.
