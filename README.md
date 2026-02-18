# 🥗 Nutrition Tracker

Flask-basierter Ernährungs-Tracker mit SQLite, Bootstrap 5 Dark Mode Dashboard.

## Start
```bash
./run.sh
# oder
python3.12 app.py
```

App läuft auf **http://localhost:5003**

## Features
- Mahlzeiten CRUD (Frühstück/Mittag/Abend/Snack)
- Kalorien-Fortschrittsbalken (Ziel: 2000 kcal)
- Makro-Donut-Chart (Protein/Fett/KH)
- Wochentrend-Balkendiagramm
- Tages- und Wochenzusammenfassungen

## API
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/meals` | GET | Alle Mahlzeiten (?date=, ?from=&to=) |
| `/api/meals` | POST | Neue Mahlzeit |
| `/api/meals/<id>` | PUT | Update |
| `/api/meals/<id>` | DELETE | Löschen |
| `/api/summary/YYYY-MM-DD` | GET | Tageszusammenfassung |
| `/api/summary/week/YYYY-MM-DD` | GET | Wochenzusammenfassung |

## Tech
Python 3.12, Flask, Flask-CORS, SQLite
