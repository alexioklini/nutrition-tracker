#!/usr/bin/env python3.12
"""Weekly Nutrition Report Generator - HTML email report from nutrition.db"""

import argparse
import json
import sqlite3
import sys
import os
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'nutrition.db')

TARGETS = {'calories': 2000, 'protein_g': 90, 'sugar_g': 25}


def get_daily_data(days=7):
    """Query daily aggregated nutrition data for the last N days."""
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    end = datetime.now().strftime('%Y-%m-%d')
    start = (datetime.now() - timedelta(days=days - 1)).strftime('%Y-%m-%d')

    rows = db.execute('''
        SELECT date,
               SUM(calories) as calories,
               SUM(protein_g) as protein_g,
               SUM(fat_g) as fat_g,
               SUM(carbs_g) as carbs_g,
               SUM(sugar_g) as sugar_g,
               SUM(fiber_g) as fiber_g,
               COUNT(*) as meal_count
        FROM meals
        WHERE date >= ? AND date <= ?
        GROUP BY date
        ORDER BY date
    ''', (start, end)).fetchall()
    db.close()
    return [dict(r) for r in rows]


def compute_report(days=7):
    """Compute all report data as a dict."""
    daily = get_daily_data(days)
    if not daily:
        return {'error': 'Keine Daten vorhanden', 'days_with_data': 0}

    n = len(daily)
    total_cal = sum(d['calories'] for d in daily)
    avg_cal = total_cal / n
    avg_protein = sum(d['protein_g'] for d in daily) / n
    avg_fat = sum(d['fat_g'] for d in daily) / n
    avg_carbs = sum(d['carbs_g'] for d in daily) / n
    avg_sugar = sum(d['sugar_g'] for d in daily) / n

    low_protein_days = [d['date'] for d in daily if d['protein_g'] < 80]
    high_sugar_days = [d['date'] for d in daily if d['sugar_g'] > TARGETS['sugar_g']]

    # Targets
    cal_diff = avg_cal - TARGETS['calories']
    protein_diff = avg_protein - TARGETS['protein_g']
    sugar_diff = avg_sugar - TARGETS['sugar_g']

    # Tip
    tip = _generate_tip(avg_protein, avg_sugar, avg_cal, low_protein_days, high_sugar_days, n)

    return {
        'period_start': daily[0]['date'],
        'period_end': daily[-1]['date'],
        'days_with_data': n,
        'total_calories': round(total_cal, 1),
        'avg_daily_calories': round(avg_cal, 1),
        'avg_protein_g': round(avg_protein, 1),
        'avg_fat_g': round(avg_fat, 1),
        'avg_carbs_g': round(avg_carbs, 1),
        'avg_sugar_g': round(avg_sugar, 1),
        'daily': daily,
        'low_protein_days': low_protein_days,
        'high_sugar_days': high_sugar_days,
        'targets': TARGETS,
        'target_diffs': {
            'calories': round(cal_diff, 1),
            'protein_g': round(protein_diff, 1),
            'sugar_g': round(sugar_diff, 1),
        },
        'tip': tip,
    }


def _generate_tip(avg_protein, avg_sugar, avg_cal, low_protein_days, high_sugar_days, n):
    if len(low_protein_days) > n / 2 and avg_sugar > 30:
        return "Proteinquellen wie Skyr, Hühnerbrust oder Linsen statt zuckerreicher Snacks einbauen – das hebt Protein und senkt Zucker gleichzeitig."
    if len(low_protein_days) > n / 2:
        return "An den meisten Tagen fehlt Protein. Versuche, zu jeder Mahlzeit eine Proteinquelle einzuplanen (Eier, Quark, Fisch, Hülsenfrüchte)."
    if avg_sugar > 40:
        return "Der Zuckerkonsum ist deutlich zu hoch. Ersetze Fruchtsäfte und Süßigkeiten durch Wasser und Nüsse."
    if avg_sugar > 25:
        return "Zucker liegt über dem Ziel. Achte auf versteckten Zucker in Müsli, Joghurt und Saucen."
    if avg_cal > 2200:
        return "Die Kalorienzufuhr liegt über dem Ziel. Kleinere Portionen beim Abendessen können helfen."
    if avg_cal < 1600:
        return "Die Kalorienzufuhr ist niedrig – achte darauf, genug zu essen, besonders an Trainingstagen."
    return "Gute Woche! Weiter so – Konsistenz ist der Schlüssel. 💪"


def render_html(data):
    """Render the report data as a styled HTML email."""
    if 'error' in data:
        return f"<html><body><p>{data['error']}</p></body></html>"

    daily = data['daily']
    max_cal = max(d['calories'] for d in daily) if daily else 1

    # Bar chart rows
    bars = []
    for d in daily:
        cal = d['calories']
        pct = min(cal / 2500 * 100, 100)
        color = '#4ade80' if cal < 2000 else '#facc15' if cal <= 2200 else '#f87171'
        weekday = datetime.strptime(d['date'], '%Y-%m-%d').strftime('%a')
        short_date = datetime.strptime(d['date'], '%Y-%m-%d').strftime('%d.%m.')
        bars.append(f'''
        <tr>
          <td style="padding:4px 8px 4px 0;font-size:13px;color:#94a3b8;white-space:nowrap;width:70px">{weekday} {short_date}</td>
          <td style="padding:4px 0;width:100%">
            <div style="background:#1e293b;border-radius:4px;overflow:hidden;height:22px">
              <div style="width:{pct:.0f}%;background:{color};height:100%;border-radius:4px;min-width:2px"></div>
            </div>
          </td>
          <td style="padding:4px 0 4px 8px;font-size:13px;color:#e2e8f0;white-space:nowrap;text-align:right;font-weight:600">{cal:.0f}</td>
        </tr>''')
    bars_html = '\n'.join(bars)

    # Protein rows
    protein_rows = []
    for d in daily:
        p = d['protein_g']
        weekday = datetime.strptime(d['date'], '%Y-%m-%d').strftime('%a %d.%m.')
        color = '#f87171' if p < 80 else '#4ade80'
        warn = ' ⚠️' if p < 80 else ''
        protein_rows.append(f'<tr><td style="padding:3px 12px 3px 0;color:#94a3b8;font-size:13px">{weekday}</td>'
                           f'<td style="padding:3px 0;color:{color};font-weight:600;font-size:13px">{p:.1f}g{warn}</td></tr>')
    protein_html = '\n'.join(protein_rows)

    # Sugar rows
    sugar_rows = []
    for d in daily:
        s = d['sugar_g']
        weekday = datetime.strptime(d['date'], '%Y-%m-%d').strftime('%a %d.%m.')
        color = '#f87171' if s > 25 else '#4ade80'
        sugar_rows.append(f'<tr><td style="padding:3px 12px 3px 0;color:#94a3b8;font-size:13px">{weekday}</td>'
                         f'<td style="padding:3px 0;color:{color};font-weight:600;font-size:13px">{s:.1f}g</td></tr>')
    sugar_html = '\n'.join(sugar_rows)

    # Target indicators
    def target_indicator(label, avg, target, unit, lower_is_better=False):
        diff = avg - target
        if lower_is_better:
            color = '#4ade80' if diff <= 0 else '#f87171'
            icon = '✅' if diff <= 0 else '❌'
            sign = '+' if diff > 0 else ''
        else:
            color = '#4ade80' if diff >= 0 else '#f87171'
            icon = '✅' if diff >= 0 else '❌'
            sign = '+' if diff > 0 else ''
        return f'''<div style="display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid #1e293b">
          <span style="color:#cbd5e1">{icon} {label}</span>
          <span style="color:{color};font-weight:600">{avg:.0f}{unit} <span style="font-size:12px;color:#64748b">({sign}{diff:.0f})</span></span>
        </div>'''

    targets_html = (
        target_indicator('Kalorien', data['avg_daily_calories'], 2000, ' kcal', lower_is_better=True) +
        target_indicator('Protein', data['avg_protein_g'], 90, 'g') +
        target_indicator('Zucker', data['avg_sugar_g'], 25, 'g', lower_is_better=True)
    )

    return f'''<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#0f172a;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif">
<div style="max-width:600px;margin:0 auto;background:#0f172a">

  <!-- Header -->
  <div style="background:linear-gradient(135deg,#1a1a2e,#16213e);padding:32px 24px;text-align:center;border-radius:0 0 16px 16px">
    <div style="font-size:36px;margin-bottom:8px">🥗</div>
    <h1 style="color:#e2e8f0;margin:0;font-size:22px;font-weight:700">Wöchentlicher Ernährungsbericht</h1>
    <p style="color:#64748b;margin:8px 0 0;font-size:13px">{data['period_start']} — {data['period_end']} · {data['days_with_data']} Tage</p>
  </div>

  <div style="padding:16px">

    <!-- Wochenüberblick -->
    <div style="background:#1e293b;border-radius:12px;padding:20px;margin-bottom:16px">
      <h2 style="color:#e2e8f0;font-size:16px;margin:0 0 16px">📊 Wochenüberblick</h2>
      <div style="display:flex;flex-wrap:wrap;gap:12px">
        <div style="flex:1;min-width:120px;background:#0f172a;border-radius:8px;padding:12px;text-align:center">
          <div style="color:#64748b;font-size:11px;text-transform:uppercase;letter-spacing:1px">Gesamt kcal</div>
          <div style="color:#e2e8f0;font-size:24px;font-weight:700;margin-top:4px">{data['total_calories']:.0f}</div>
        </div>
        <div style="flex:1;min-width:120px;background:#0f172a;border-radius:8px;padding:12px;text-align:center">
          <div style="color:#64748b;font-size:11px;text-transform:uppercase;letter-spacing:1px">Ø kcal/Tag</div>
          <div style="color:#e2e8f0;font-size:24px;font-weight:700;margin-top:4px">{data['avg_daily_calories']:.0f}</div>
        </div>
      </div>
      <div style="display:flex;flex-wrap:wrap;gap:8px;margin-top:12px">
        <div style="flex:1;min-width:80px;background:#0f172a;border-radius:8px;padding:10px;text-align:center">
          <div style="color:#64748b;font-size:10px">Ø Protein</div>
          <div style="color:#38bdf8;font-size:16px;font-weight:600">{data['avg_protein_g']:.0f}g</div>
        </div>
        <div style="flex:1;min-width:80px;background:#0f172a;border-radius:8px;padding:10px;text-align:center">
          <div style="color:#64748b;font-size:10px">Ø Fett</div>
          <div style="color:#fb923c;font-size:16px;font-weight:600">{data['avg_fat_g']:.0f}g</div>
        </div>
        <div style="flex:1;min-width:80px;background:#0f172a;border-radius:8px;padding:10px;text-align:center">
          <div style="color:#64748b;font-size:10px">Ø Kohlenhydrate</div>
          <div style="color:#a78bfa;font-size:16px;font-weight:600">{data['avg_carbs_g']:.0f}g</div>
        </div>
      </div>
    </div>

    <!-- Tages-Trend -->
    <div style="background:#1e293b;border-radius:12px;padding:20px;margin-bottom:16px">
      <h2 style="color:#e2e8f0;font-size:16px;margin:0 0 12px">📈 Tages-Trend (Kalorien)</h2>
      <div style="font-size:11px;color:#64748b;margin-bottom:8px">
        <span style="color:#4ade80">●</span> &lt;2000 &nbsp;
        <span style="color:#facc15">●</span> 2000–2200 &nbsp;
        <span style="color:#f87171">●</span> &gt;2200
      </div>
      <table style="width:100%;border-collapse:collapse">{bars_html}</table>
    </div>

    <!-- Protein-Analyse -->
    <div style="background:#1e293b;border-radius:12px;padding:20px;margin-bottom:16px">
      <h2 style="color:#e2e8f0;font-size:16px;margin:0 0 4px">🥩 Protein-Analyse</h2>
      <p style="color:#64748b;font-size:12px;margin:0 0 12px">Ziel: ≥90g/Tag · Warnung unter 80g</p>
      <table style="width:100%;border-collapse:collapse">{protein_html}</table>
      <div style="margin-top:10px;padding-top:10px;border-top:1px solid #334155;color:#94a3b8;font-size:13px">
        Ø {data['avg_protein_g']:.1f}g/Tag · {len(data['low_protein_days'])} von {data['days_with_data']} Tagen unter 80g
      </div>
    </div>

    <!-- Zucker-Tracker -->
    <div style="background:#1e293b;border-radius:12px;padding:20px;margin-bottom:16px">
      <h2 style="color:#e2e8f0;font-size:16px;margin:0 0 4px">🍬 Zucker-Tracker</h2>
      <p style="color:#64748b;font-size:12px;margin:0 0 12px">Ziel: &lt;25g/Tag</p>
      <table style="width:100%;border-collapse:collapse">{sugar_html}</table>
      <div style="margin-top:10px;padding-top:10px;border-top:1px solid #334155;color:#94a3b8;font-size:13px">
        Ø {data['avg_sugar_g']:.1f}g/Tag
      </div>
    </div>

    <!-- Zielwerte -->
    <div style="background:#1e293b;border-radius:12px;padding:20px;margin-bottom:16px">
      <h2 style="color:#e2e8f0;font-size:16px;margin:0 0 12px">🎯 Zielwerte (Ø pro Tag)</h2>
      {targets_html}
    </div>

    <!-- Empfehlung -->
    <div style="background:linear-gradient(135deg,#1a1a2e,#16213e);border-radius:12px;padding:20px;margin-bottom:16px;border:1px solid #334155">
      <h2 style="color:#e2e8f0;font-size:16px;margin:0 0 8px">💡 Empfehlung</h2>
      <p style="color:#cbd5e1;font-size:14px;line-height:1.6;margin:0">{data['tip']}</p>
    </div>

  </div>

  <div style="text-align:center;padding:16px;color:#475569;font-size:11px">
    Nutrition Tracker · Generiert am {datetime.now().strftime('%d.%m.%Y %H:%M')}
  </div>

</div>
</body></html>'''


def main():
    parser = argparse.ArgumentParser(description='Weekly Nutrition Report')
    parser.add_argument('--days', type=int, default=7)
    parser.add_argument('--output', type=str, default=None)
    parser.add_argument('--json', action='store_true', help='Output JSON instead of HTML')
    args = parser.parse_args()

    data = compute_report(args.days)

    if args.json:
        out = json.dumps(data, indent=2, ensure_ascii=False)
    else:
        out = render_html(data)

    if args.output:
        with open(args.output, 'w') as f:
            f.write(out)
        print(f"Report written to {args.output}")
    else:
        print(out)


if __name__ == '__main__':
    main()
