#!/usr/bin/env python3.12
"""Nutrition Tracker - Flask App"""

import sqlite3
import os
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, g, send_from_directory
from flask_cors import CORS

app = Flask(__name__, static_folder='static')
CORS(app)

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'nutrition.db')

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.execute('PRAGMA foreign_keys = ON')
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(exc):
    db = g.pop('db', None)
    if db: db.close()

def init_db():
    db = sqlite3.connect(DB_PATH)
    db.execute('PRAGMA foreign_keys = ON')
    db.execute('''CREATE TABLE IF NOT EXISTS meals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        meal_type TEXT NOT NULL CHECK(meal_type IN ('breakfast','lunch','dinner','snack')),
        description TEXT NOT NULL,
        calories REAL DEFAULT 0,
        protein_g REAL DEFAULT 0,
        fat_g REAL DEFAULT 0,
        carbs_g REAL DEFAULT 0,
        fiber_g REAL DEFAULT 0,
        sugar_g REAL DEFAULT 0,
        notes TEXT DEFAULT '',
        source TEXT DEFAULT 'manual' CHECK(source IN ('text','photo','manual')),
        created_at TEXT DEFAULT (datetime('now'))
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS meal_components (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        meal_id INTEGER NOT NULL REFERENCES meals(id) ON DELETE CASCADE,
        description TEXT NOT NULL,
        calories REAL DEFAULT 0,
        protein_g REAL DEFAULT 0,
        fat_g REAL DEFAULT 0,
        carbs_g REAL DEFAULT 0,
        fiber_g REAL DEFAULT 0,
        sugar_g REAL DEFAULT 0,
        sort_order INTEGER DEFAULT 0
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS supplements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        dose_per_day INTEGER NOT NULL,
        unit TEXT DEFAULT 'Kapseln',
        key_ingredients TEXT DEFAULT '',
        category TEXT DEFAULT 'general',
        prostate_relevant INTEGER DEFAULT 0,
        notes TEXT DEFAULT '',
        active INTEGER DEFAULT 1,
        dose_morning INTEGER DEFAULT 1,
        dose_noon INTEGER DEFAULT 1,
        dose_evening INTEGER DEFAULT 1
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS supplement_intake (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        supplement_id INTEGER NOT NULL REFERENCES supplements(id),
        taken INTEGER DEFAULT 0,
        taken_at TEXT DEFAULT NULL,
        dose_slot TEXT DEFAULT 'morning'
    )''')
    db.execute('''CREATE UNIQUE INDEX IF NOT EXISTS idx_supplement_intake_unique
        ON supplement_intake(date, supplement_id, dose_slot)''')
    # Pre-fill supplements if empty
    if db.execute('SELECT COUNT(*) FROM supplements').fetchone()[0] == 0:
        supps = [
            ("Vitals Männerformel Pro Prostata", 2, "Kapseln", "Kürbiskern Go-Less® 500mg · Sägepalme 320mg · Beta-Sitosterol 130mg · Pygeum 100mg", "prostata", 1),
            ("Legalon 140mg", 2, "Kapseln", "Silymarin 280mg/Tag (Mariendistel)", "leber", 0),
            ("curcumin-Loges plus Boswellia", 2, "Kapseln", "Curcumin (Mizellen, 185× Bioverfügb.) · Boswelliasäuren · Vitamin D", "entzündung", 1),
            ("Apremia Omega-3", 1, "Kapsel", "Fischöl 1000mg (EPA/DHA)", "herz", 1),
            ("MiraCHOL 3.0 Gold", 1, "Kapsel", "Ubiquinol CoQ10 · Boswellia · Monacolin K", "herz", 0),
            ("Pure Encapsulations Zink 30", 1, "Kapsel", "Zinkpicolinat 30mg", "prostata", 1),
            ("Selamin Selen", 1, "Tablette", "Natriumselenit", "prostata", 1),
            ("Vitals Grüner Tee-PS", 2, "Kapseln", "Catechine 120mg/Kapsel · EGCG 75mg/Kapsel", "antioxidans", 1),
        ]
        db.executemany('INSERT INTO supplements (name, dose_per_day, unit, key_ingredients, category, prostate_relevant) VALUES (?,?,?,?,?,?)', supps)
        db.commit()
    # Insert initial data if empty
    if db.execute('SELECT COUNT(*) FROM meals').fetchone()[0] == 0:
        meals = [
            ('2026-02-18','breakfast','125g Himbeeren',40,1,0.5,8,4,5,'','manual'),
            ('2026-02-18','breakfast','100g Vollkorn-Müsli',370,10,6,60,8,10,'','manual'),
            ('2026-02-18','breakfast','30g Erdbeer-Crunchy-Müsli',135,2,5,20,1.5,8,'','manual'),
            ('2026-02-18','breakfast','Sojamilch ohne Zucker (~200ml)',70,7,3.5,2,0,0,'','manual'),
            ('2026-02-18','breakfast','1 Tasse Kaffee mit Hafermilch (~50ml)',20,0.3,0.5,3,0,0,'','manual'),
            ('2026-02-18','breakfast','1 Glas Granatapfelsaft (~200ml)',130,1,0,30,0,28,'','manual'),
            ('2026-02-18','lunch','Gemischter Salat mit Lachspuffer',550,35,28,30,4,0,'Restaurant Jonathan & Sieglinde Wien, Aschermittwoch-Salat','manual'),
            ('2026-02-18','lunch','2 Kaffee mit Milch',60,3,2,6,0,0,'Restaurant Jonathan & Sieglinde Wien','manual'),
            ('2026-02-18','snack','3 Äpfel (~150g each)',230,1,0.5,55,8,44,'','manual'),
        ]
        db.executemany('INSERT INTO meals (date,meal_type,description,calories,protein_g,fat_g,carbs_g,fiber_g,sugar_g,notes,source) VALUES (?,?,?,?,?,?,?,?,?,?,?)', meals)
        db.commit()
    # Migration: add dose_morning/dose_noon/dose_evening columns if missing
    cols = [row[1] for row in db.execute('PRAGMA table_info(supplements)').fetchall()]
    if 'dose_morning' not in cols:
        db.execute('ALTER TABLE supplements ADD COLUMN dose_morning INTEGER DEFAULT 1')
        db.execute('ALTER TABLE supplements ADD COLUMN dose_noon INTEGER DEFAULT 1')
        db.execute('ALTER TABLE supplements ADD COLUMN dose_evening INTEGER DEFAULT 1')
        db.commit()
    # Ensure Grüner Tee-PS (id=8) has correct split-dose: 3 caps/day (2 morning + 1 evening)
    row8 = db.execute('SELECT dose_per_day, dose_morning, dose_evening FROM supplements WHERE id=8').fetchone()
    if row8 and (row8[0] != 3 or row8[1] != 2 or row8[2] != 1):
        db.execute('UPDATE supplements SET dose_per_day=3, dose_morning=2, dose_evening=1 WHERE id=8')
        db.commit()
    # Migration: combine breakfast components for 2026-02-17 and 2026-02-18
    migrate_breakfast_components(db)
    db.close()

def migrate_breakfast_components(db):
    """Combine individual breakfast items into one 'Frühstücksmüsli' with components."""
    db.row_factory = sqlite3.Row
    component_descs = ['125g Himbeeren', '100g Vollkorn-Müsli', '30g Erdbeer-Crunchy-Müsli', 'Sojamilch ohne Zucker (~200ml)']
    for date in ['2026-02-17', '2026-02-18']:
        # Check if already migrated
        existing = db.execute("SELECT id FROM meals WHERE date=? AND description='Frühstücksmüsli'", (date,)).fetchone()
        if existing:
            continue
        # Find the 4 component meals
        placeholders = ','.join('?' * len(component_descs))
        rows = db.execute(f"SELECT * FROM meals WHERE date=? AND meal_type='breakfast' AND description IN ({placeholders})",
                          [date] + component_descs).fetchall()
        if len(rows) < 1:
            continue
        # Sum up
        totals = {k: sum(r[k] for r in rows) for k in ['calories', 'protein_g', 'fat_g', 'carbs_g', 'fiber_g', 'sugar_g']}
        # Create combined meal
        cur = db.execute("INSERT INTO meals (date,meal_type,description,calories,protein_g,fat_g,carbs_g,fiber_g,sugar_g,notes,source) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                         (date, 'breakfast', 'Frühstücksmüsli', totals['calories'], totals['protein_g'], totals['fat_g'], totals['carbs_g'], totals['fiber_g'], totals['sugar_g'], '', 'manual'))
        meal_id = cur.lastrowid
        # Insert components
        for i, r in enumerate(rows):
            db.execute("INSERT INTO meal_components (meal_id,description,calories,protein_g,fat_g,carbs_g,fiber_g,sugar_g,sort_order) VALUES (?,?,?,?,?,?,?,?,?)",
                       (meal_id, r['description'], r['calories'], r['protein_g'], r['fat_g'], r['carbs_g'], r['fiber_g'], r['sugar_g'], i))
        # Delete originals
        ids = [r['id'] for r in rows]
        db.execute(f"DELETE FROM meals WHERE id IN ({','.join('?'*len(ids))})", ids)
        db.commit()

@app.route('/')
def dashboard():
    return send_from_directory('static', 'index.html')

def attach_components(db, meals):
    """Attach components array to each meal dict."""
    if not meals:
        return meals
    ids = [m['id'] for m in meals]
    placeholders = ','.join('?' * len(ids))
    comps = db.execute(f'SELECT * FROM meal_components WHERE meal_id IN ({placeholders}) ORDER BY sort_order, id', ids).fetchall()
    comp_map = {}
    for c in comps:
        comp_map.setdefault(c['meal_id'], []).append(dict(c))
    for m in meals:
        m['components'] = comp_map.get(m['id'], [])
    return meals

@app.route('/api/meals', methods=['GET'])
def get_meals():
    db = get_db()
    date = request.args.get('date')
    date_from = request.args.get('from')
    date_to = request.args.get('to')
    if date:
        rows = db.execute('SELECT * FROM meals WHERE date=? ORDER BY meal_type, id', (date,)).fetchall()
    elif date_from and date_to:
        rows = db.execute('SELECT * FROM meals WHERE date BETWEEN ? AND ? ORDER BY date, meal_type, id', (date_from, date_to)).fetchall()
    else:
        rows = db.execute('SELECT * FROM meals ORDER BY date DESC, meal_type, id').fetchall()
    meals = [dict(r) for r in rows]
    attach_components(db, meals)
    return jsonify(meals)

@app.route('/api/meals', methods=['POST'])
def create_meal():
    d = request.json
    db = get_db()
    cur = db.execute('INSERT INTO meals (date,meal_type,description,calories,protein_g,fat_g,carbs_g,fiber_g,sugar_g,notes,source) VALUES (?,?,?,?,?,?,?,?,?,?,?)',
        (d['date'], d['meal_type'], d['description'], d.get('calories',0), d.get('protein_g',0), d.get('fat_g',0), d.get('carbs_g',0), d.get('fiber_g',0), d.get('sugar_g',0), d.get('notes',''), d.get('source','manual')))
    db.commit()
    row = db.execute('SELECT * FROM meals WHERE id=?', (cur.lastrowid,)).fetchone()
    return jsonify(dict(row)), 201

@app.route('/api/meals/<int:meal_id>', methods=['PUT'])
def update_meal(meal_id):
    d = request.json
    db = get_db()
    fields = ['date','meal_type','description','calories','protein_g','fat_g','carbs_g','fiber_g','sugar_g','notes','source']
    sets = ', '.join(f'{f}=?' for f in fields if f in d)
    vals = [d[f] for f in fields if f in d]
    if not sets:
        return jsonify({'error': 'No fields to update'}), 400
    vals.append(meal_id)
    db.execute(f'UPDATE meals SET {sets} WHERE id=?', vals)
    db.commit()
    row = db.execute('SELECT * FROM meals WHERE id=?', (meal_id,)).fetchone()
    if not row: return jsonify({'error': 'Not found'}), 404
    return jsonify(dict(row))

@app.route('/api/meals/<int:meal_id>', methods=['DELETE'])
def delete_meal(meal_id):
    db = get_db()
    db.execute('DELETE FROM meals WHERE id=?', (meal_id,))
    db.commit()
    return jsonify({'status': 'deleted'})

@app.route('/api/meals/<int:meal_id>/components', methods=['GET'])
def get_components(meal_id):
    db = get_db()
    rows = db.execute('SELECT * FROM meal_components WHERE meal_id=? ORDER BY sort_order, id', (meal_id,)).fetchall()
    return jsonify([dict(r) for r in rows])

@app.route('/api/meals/<int:meal_id>/components', methods=['POST'])
def create_component(meal_id):
    d = request.json
    db = get_db()
    cur = db.execute('INSERT INTO meal_components (meal_id,description,calories,protein_g,fat_g,carbs_g,fiber_g,sugar_g,sort_order) VALUES (?,?,?,?,?,?,?,?,?)',
        (meal_id, d['description'], d.get('calories',0), d.get('protein_g',0), d.get('fat_g',0), d.get('carbs_g',0), d.get('fiber_g',0), d.get('sugar_g',0), d.get('sort_order',0)))
    db.commit()
    row = db.execute('SELECT * FROM meal_components WHERE id=?', (cur.lastrowid,)).fetchone()
    return jsonify(dict(row)), 201

@app.route('/api/meals/<int:meal_id>/components/<int:comp_id>', methods=['DELETE'])
def delete_component(meal_id, comp_id):
    db = get_db()
    db.execute('DELETE FROM meal_components WHERE id=? AND meal_id=?', (comp_id, meal_id))
    db.commit()
    return jsonify({'status': 'deleted'})

@app.route('/api/supplements')
def get_supplements():
    db = get_db()
    rows = db.execute('SELECT * FROM supplements WHERE active=1 ORDER BY id').fetchall()
    return jsonify([dict(r) for r in rows])

def ensure_supplement_records(db, date):
    """Auto-insert supplement_intake records for a date if none exist."""
    count = db.execute('SELECT COUNT(*) FROM supplement_intake WHERE date=?', (date,)).fetchone()[0]
    if count > 0:
        return
    # Dose schedule:
    # IDs 1,2,3,8 (dose_per_day=2): morning 07:00 + evening 19:00
    # ID 4 (Omega-3, dose_per_day=1): noon 12:00
    # IDs 5,6,7 (dose_per_day=1): evening 19:00
    supps = db.execute('SELECT id, dose_per_day FROM supplements WHERE active=1 ORDER BY id').fetchall()
    for s in supps:
        sid = s[0]
        dpd = s[1]
        if dpd == 2:  # IDs 1,2,3,8
            db.execute('INSERT OR IGNORE INTO supplement_intake (date, supplement_id, taken, taken_at, dose_slot) VALUES (?,?,0,?,?)',
                       (date, sid, date + ' 07:00:00', 'morning'))
            db.execute('INSERT OR IGNORE INTO supplement_intake (date, supplement_id, taken, taken_at, dose_slot) VALUES (?,?,0,?,?)',
                       (date, sid, date + ' 19:00:00', 'evening'))
        elif sid == 4:  # Omega-3
            db.execute('INSERT OR IGNORE INTO supplement_intake (date, supplement_id, taken, taken_at, dose_slot) VALUES (?,?,0,?,?)',
                       (date, sid, date + ' 12:00:00', 'noon'))
        else:  # IDs 5,6,7
            db.execute('INSERT OR IGNORE INTO supplement_intake (date, supplement_id, taken, taken_at, dose_slot) VALUES (?,?,0,?,?)',
                       (date, sid, date + ' 19:00:00', 'evening'))
    db.commit()

@app.route('/api/supplement-intake/<date>')
def get_supplement_intake(date):
    db = get_db()
    ensure_supplement_records(db, date)
    # Fetch all intake records grouped by supplement
    supps = db.execute('SELECT * FROM supplements WHERE active=1 ORDER BY id').fetchall()
    result = []
    for s in supps:
        doses = db.execute('''
            SELECT id, dose_slot, taken, taken_at FROM supplement_intake
            WHERE date=? AND supplement_id=? ORDER BY
            CASE dose_slot WHEN 'morning' THEN 1 WHEN 'noon' THEN 2 WHEN 'evening' THEN 3 END
        ''', (date, s['id'])).fetchall()
        result.append({
            'supplement_id': s['id'],
            'name': s['name'],
            'dose_per_day': s['dose_per_day'],
            'unit': s['unit'],
            'key_ingredients': s['key_ingredients'],
            'category': s['category'],
            'prostate_relevant': s['prostate_relevant'],
            'dose_morning': s['dose_morning'] if 'dose_morning' in s.keys() else 1,
            'dose_noon': s['dose_noon'] if 'dose_noon' in s.keys() else 1,
            'dose_evening': s['dose_evening'] if 'dose_evening' in s.keys() else 1,
            'doses': [{'id': d['id'], 'dose_slot': d['dose_slot'], 'taken': d['taken'],
                       'taken_at': d['taken_at'].split(' ')[-1][:5] if d['taken_at'] else None} for d in doses]
        })
    return jsonify(result)

@app.route('/api/supplement-intake', methods=['POST'])
def post_supplement_intake():
    d = request.json
    db = get_db()
    dose_slot = d.get('dose_slot', 'morning')
    taken = d.get('taken', 0)
    # Update existing record by (date, supplement_id, dose_slot)
    existing = db.execute('SELECT id, taken_at FROM supplement_intake WHERE date=? AND supplement_id=? AND dose_slot=?',
                          (d['date'], d['supplement_id'], dose_slot)).fetchone()
    if existing:
        # Keep original scheduled time if unchecking, set current time if checking
        taken_at = datetime.now().strftime(d['date'] + ' %H:%M:%S') if taken else existing['taken_at']
        db.execute('UPDATE supplement_intake SET taken=?, taken_at=? WHERE id=?',
                   (taken, taken_at, existing['id']))
    else:
        taken_at = datetime.now().strftime(d['date'] + ' %H:%M:%S') if taken else None
        db.execute('INSERT INTO supplement_intake (date, supplement_id, taken, taken_at, dose_slot) VALUES (?,?,?,?,?)',
                   (d['date'], d['supplement_id'], taken, taken_at, dose_slot))
    db.commit()
    return jsonify({'status': 'ok'})

@app.route('/api/supplement-intake/week/<date>')
def get_supplement_intake_week(date):
    db = get_db()
    d = datetime.strptime(date, '%Y-%m-%d')
    start = d - timedelta(days=6)
    days = []
    for i in range(7):
        day = (start + timedelta(days=i)).strftime('%Y-%m-%d')
        # Count taken doses vs total expected doses per day (12 total)
        rows = db.execute('''
            SELECT s.id, s.name, si.dose_slot, COALESCE(si.taken, 0) as taken
            FROM supplements s
            LEFT JOIN supplement_intake si ON si.supplement_id = s.id AND si.date = ?
            WHERE s.active = 1
            ORDER BY s.id, si.dose_slot
        ''', (day,)).fetchall()
        days.append({'date': day, 'supplements': [dict(r) for r in rows]})
    return jsonify({'week_ending': date, 'days': days})

BIRTH_YEAR = 1971
HEALTH_API = 'http://localhost:5050'

def get_workout_data(date):
    """Fetch workout + steps data from Health API for a given date."""
    import urllib.request, json as _json
    result = {'active_energy_kj': 0, 'avg_hr': None, 'duration_min': 0, 'steps': 0, 'has_workout': False}
    try:
        with urllib.request.urlopen(f'{HEALTH_API}/api/training/{date}', timeout=2) as r:
            d = _json.loads(r.read())
            if d.get('training') and d['training'].get('done'):
                t = d['training']
                result['has_workout'] = True
                result['duration_min'] = t.get('duration', 0) or 0
                # avg_hr: try multiple field names
                result['avg_hr'] = t.get('avg_hr') or t.get('hr_avg') or None
                # active_energy: Health API stores in kJ (active_energy) or kcal (calories)
                ae_kj = t.get('active_energy', 0) or 0
                ae_kcal = t.get('calories', 0) or 0
                # If active_energy is in kJ (>300 typically means kJ), convert; else use kcal directly
                if ae_kj > 0:
                    result['active_energy_kj'] = ae_kj if ae_kj > 100 else ae_kj * 4.184
                elif ae_kcal > 0:
                    result['active_energy_kj'] = ae_kcal * 4.184
    except Exception:
        pass
    try:
        with urllib.request.urlopen(f'{HEALTH_API}/api/steps/{date}', timeout=2) as r:
            d = _json.loads(r.read())
            result['steps'] = d.get('steps', 0) or 0
    except Exception:
        pass
    return result

def calc_workout_calories(active_energy_kj, avg_hr, duration_min):
    """
    Calculate burned calories and macro split based on heart rate zones.
    HRmax = 220 - age (born 1971, age ~54) = 166 bpm
    Zone 1 (<60% = <100): fat dominant ~70% fat / 30% KH
    Zone 2 (60-70% = 100-116): fat burning ~60% fat / 40% KH
    Zone 3 (70-80% = 116-133): mixed ~50% fat / 50% KH
    Zone 4 (80-90% = 133-149): KH dominant ~25% fat / 75% KH
    Zone 5 (>90% = >149): KH max ~10% fat / 90% KH
    """
    from datetime import date as _date
    age = _date.today().year - BIRTH_YEAR
    hr_max = 220 - age
    kcal_burned = round(active_energy_kj / 4.184) if active_energy_kj else 0

    # Determine zone from avg HR
    fat_pct, kh_pct, zone, zone_label = 0.5, 0.5, 3, 'Mischzone'
    if avg_hr:
        hr_pct = avg_hr / hr_max * 100
        if hr_pct < 60:
            fat_pct, kh_pct, zone, zone_label = 0.70, 0.30, 1, 'Grundlagen (Fettverbrennung)'
        elif hr_pct < 70:
            fat_pct, kh_pct, zone, zone_label = 0.60, 0.40, 2, 'Fettverbrennung'
        elif hr_pct < 80:
            fat_pct, kh_pct, zone, zone_label = 0.50, 0.50, 3, 'Aerob (Mischzone)'
        elif hr_pct < 90:
            fat_pct, kh_pct, zone, zone_label = 0.25, 0.75, 4, 'Anaerob (KH-dominant)'
        else:
            fat_pct, kh_pct, zone, zone_label = 0.10, 0.90, 5, 'Maximalkraft'

    fat_kcal = kcal_burned * fat_pct
    kh_kcal = kcal_burned * kh_pct
    fat_g_burned = round(fat_kcal / 9, 1)
    kh_g_burned = round(kh_kcal / 4, 1)

    return {
        'kcal_burned': kcal_burned,
        'fat_g_burned': fat_g_burned,
        'kh_g_burned': kh_g_burned,
        'fat_pct': round(fat_pct * 100),
        'kh_pct': round(kh_pct * 100),
        'zone': zone,
        'zone_label': zone_label,
        'hr_max': hr_max,
        'avg_hr': avg_hr,
    }

@app.route('/api/summary/<date>')
def daily_summary(date):
    db = get_db()
    row = db.execute('SELECT COALESCE(SUM(calories),0) as calories, COALESCE(SUM(protein_g),0) as protein_g, COALESCE(SUM(fat_g),0) as fat_g, COALESCE(SUM(carbs_g),0) as carbs_g, COALESCE(SUM(fiber_g),0) as fiber_g, COALESCE(SUM(sugar_g),0) as sugar_g, COUNT(*) as meal_count FROM meals WHERE date=?', (date,)).fetchone()
    totals = dict(row)

    # Workout data
    workout = get_workout_data(date)
    workout_calc = calc_workout_calories(
        workout['active_energy_kj'],
        workout['avg_hr'],
        workout['duration_min']
    )

    base_goal = 2000
    cal_goal = base_goal + workout_calc['kcal_burned']
    net_calories = round(totals['calories'] - workout_calc['kcal_burned'])

    # Adjust macro goals: on workout days increase protein slightly, shift fat/KH based on zone
    protein_goal = 90 if workout['has_workout'] else 80
    fat_goal = 65
    carbs_goal = 250
    if workout['has_workout'] and workout_calc['kcal_burned'] > 0:
        # Increase carb goal on high-intensity days (zone 4-5)
        if workout_calc['zone'] >= 4:
            carbs_goal = 280
        elif workout_calc['zone'] <= 2:
            fat_goal = 70  # more fat ok on fat-burning days

    return jsonify({
        'date': date,
        'totals': totals,
        'goals': {'calories': cal_goal, 'protein_g': protein_goal, 'fat_g': fat_goal, 'carbs_g': carbs_goal, 'fiber_g': 30},
        'progress': {'calories': round(totals['calories'] / cal_goal * 100, 1)},
        'workout': {**workout, **workout_calc},
        'net_calories': net_calories,
        'base_goal': base_goal,
    })

@app.route('/api/summary/week/<date>')
def weekly_summary(date):
    db = get_db()
    d = datetime.strptime(date, '%Y-%m-%d')
    start = d - timedelta(days=6)
    days = []
    for i in range(7):
        day = (start + timedelta(days=i)).strftime('%Y-%m-%d')
        row = db.execute('SELECT COALESCE(SUM(calories),0) as calories, COALESCE(SUM(protein_g),0) as protein_g, COALESCE(SUM(fat_g),0) as fat_g, COALESCE(SUM(carbs_g),0) as carbs_g FROM meals WHERE date=?', (day,)).fetchone()
        days.append({'date': day, **dict(row)})
    return jsonify({'week_ending': date, 'days': days})

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5003, debug=True)
