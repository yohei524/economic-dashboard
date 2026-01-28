#!/usr/bin/env python3
"""
経済指標トレードダッシュボード
- カレンダー表示
- 雇用統計ページ（月別）
- FRB発言一覧
- トレード履歴
"""

from flask import Flask, render_template, jsonify, request
import json
import os
from datetime import datetime, timedelta

app = Flask(__name__)

DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')


def load_json(filename):
    """JSONファイルを読み込み"""
    filepath = os.path.join(DATA_DIR, filename)
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_json(filename, data):
    """JSONファイルに保存"""
    filepath = os.path.join(DATA_DIR, filename)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# 2026年のスケジュール（固定）
SCHEDULE_2026 = {
    "fomc": [
        {"date": "2026-01-28", "sep": False},
        {"date": "2026-03-18", "sep": True},
        {"date": "2026-04-29", "sep": False},
        {"date": "2026-06-17", "sep": True},
        {"date": "2026-07-29", "sep": False},
        {"date": "2026-09-16", "sep": True},
        {"date": "2026-10-28", "sep": False},
        {"date": "2026-12-09", "sep": True},
    ],
    "boj": [
        {"date": "2026-01-23", "outlook": True},
        {"date": "2026-03-19", "outlook": False},
        {"date": "2026-04-28", "outlook": True},
        {"date": "2026-06-16", "outlook": False},
        {"date": "2026-07-31", "outlook": True},
        {"date": "2026-09-18", "outlook": False},
        {"date": "2026-10-30", "outlook": True},
        {"date": "2026-12-18", "outlook": False},
    ],
    "nfp": [
        {"date": "2026-01-09", "month": "2025-12"},
        {"date": "2026-02-06", "month": "2026-01"},
        {"date": "2026-03-06", "month": "2026-02"},
        {"date": "2026-04-03", "month": "2026-03"},
        {"date": "2026-05-01", "month": "2026-04"},
        {"date": "2026-06-05", "month": "2026-05"},
        {"date": "2026-07-02", "month": "2026-06"},
        {"date": "2026-08-07", "month": "2026-07"},
        {"date": "2026-09-04", "month": "2026-08"},
        {"date": "2026-10-02", "month": "2026-09"},
        {"date": "2026-11-06", "month": "2026-10"},
        {"date": "2026-12-04", "month": "2026-11"},
    ],
    "cpi": [
        {"date": "2026-01-14", "month": "2025-12"},
        {"date": "2026-02-12", "month": "2026-01"},
        {"date": "2026-03-11", "month": "2026-02"},
        {"date": "2026-04-14", "month": "2026-03"},
        {"date": "2026-05-13", "month": "2026-04"},
        {"date": "2026-06-10", "month": "2026-05"},
        {"date": "2026-07-15", "month": "2026-06"},
        {"date": "2026-08-12", "month": "2026-07"},
        {"date": "2026-09-16", "month": "2026-08"},
        {"date": "2026-10-13", "month": "2026-09"},
        {"date": "2026-11-12", "month": "2026-10"},
        {"date": "2026-12-10", "month": "2026-11"},
    ]
}


@app.route('/')
def index():
    """トップページ - カレンダー"""
    today = datetime.now()

    # 次回NFPを探す
    next_nfp = None
    for nfp in SCHEDULE_2026["nfp"]:
        nfp_date = datetime.strptime(nfp["date"], "%Y-%m-%d")
        if nfp_date >= today:
            next_nfp = nfp
            days_until = (nfp_date - today).days
            next_nfp["days_until"] = days_until
            break

    # 今月・来月のイベントを取得
    current_month = today.strftime("%Y-%m")
    next_month = (today.replace(day=1) + timedelta(days=32)).strftime("%Y-%m")

    events = []
    for event_type, schedule in SCHEDULE_2026.items():
        for event in schedule:
            event_month = event["date"][:7]
            if event_month in [current_month, next_month]:
                events.append({
                    "type": event_type.upper(),
                    "date": event["date"],
                    **event
                })

    events.sort(key=lambda x: x["date"])

    return render_template('index.html',
                         today=today.strftime("%Y-%m-%d"),
                         next_nfp=next_nfp,
                         events=events)


@app.route('/nfp')
@app.route('/nfp/<month>')
def nfp_page(month=None):
    """雇用統計ページ"""
    nfp_data = load_json('nfp_history.json')
    fed_speeches = load_json('fed_speeches.json')

    if month is None:
        # 次回の雇用統計月を表示
        today = datetime.now()
        for nfp in SCHEDULE_2026["nfp"]:
            nfp_date = datetime.strptime(nfp["date"], "%Y-%m-%d")
            if nfp_date >= today:
                month = nfp["month"]
                break

    # 該当月のNFPスケジュール
    nfp_schedule = None
    prev_nfp_date = None
    for i, nfp in enumerate(SCHEDULE_2026["nfp"]):
        if nfp["month"] == month:
            nfp_schedule = nfp
            if i > 0:
                prev_nfp_date = SCHEDULE_2026["nfp"][i-1]["date"]
            break

    # 該当月のデータ
    month_data = nfp_data.get(month, {
        "forecast": None,
        "actual": None,
        "prev": None,
        "market_reaction": None,
        "notes": ""
    })

    # 関連するFRB発言（前回NFP〜今回NFP）
    related_speeches = []
    if nfp_schedule and prev_nfp_date:
        for speech in fed_speeches:
            if prev_nfp_date <= speech["date"] <= nfp_schedule["date"]:
                related_speeches.append(speech)

    # 全NFPリスト
    all_nfp = SCHEDULE_2026["nfp"]

    return render_template('nfp.html',
                         month=month,
                         schedule=nfp_schedule,
                         data=month_data,
                         speeches=related_speeches,
                         all_nfp=all_nfp,
                         nfp_history=nfp_data)


@app.route('/fed-speeches')
def fed_speeches_page():
    """FRB発言一覧"""
    speeches = load_json('fed_speeches.json')
    speeches.sort(key=lambda x: x["date"], reverse=True)

    # FRB高官情報
    officials = {
        "Powell": {"name": "パウエル議長", "weight": "★★★"},
        "Williams": {"name": "ウィリアムズ（NY連銀）", "weight": "★★☆"},
        "Waller": {"name": "ウォラー理事", "weight": "★★☆"},
        "Bowman": {"name": "ボウマン理事", "weight": "★★☆"},
        "Jefferson": {"name": "ジェファーソン副議長", "weight": "★★☆"},
        "Cook": {"name": "クック理事", "weight": "★☆☆"},
        "Kugler": {"name": "クーグラー理事", "weight": "★☆☆"},
    }

    return render_template('fed_speeches.html',
                         speeches=speeches,
                         officials=officials)


@app.route('/trades')
def trades_page():
    """トレード履歴"""
    trades = load_json('trades.json')

    # 統計計算
    total_pnl = sum(t.get("pnl", 0) for t in trades)
    win_count = len([t for t in trades if t.get("pnl", 0) > 0])
    lose_count = len([t for t in trades if t.get("pnl", 0) < 0])
    total_trades = len(trades)
    win_rate = win_count / total_trades * 100 if total_trades > 0 else 0

    # 累計収支推移
    cumulative = []
    running_total = 0
    for t in sorted(trades, key=lambda x: x["date"]):
        running_total += t.get("pnl", 0)
        cumulative.append({"date": t["date"], "total": running_total})

    return render_template('trades.html',
                         trades=trades,
                         total_pnl=total_pnl,
                         win_count=win_count,
                         lose_count=lose_count,
                         win_rate=win_rate,
                         cumulative=cumulative)


# API エンドポイント（データ更新用）
@app.route('/api/nfp/<month>', methods=['POST'])
def update_nfp(month):
    """NFPデータを更新"""
    nfp_data = load_json('nfp_history.json')
    data = request.json
    nfp_data[month] = {
        "forecast": data.get("forecast"),
        "actual": data.get("actual"),
        "prev": data.get("prev"),
        "market_reaction": data.get("market_reaction"),
        "notes": data.get("notes", "")
    }
    save_json('nfp_history.json', nfp_data)
    return jsonify({"status": "ok"})


@app.route('/api/fed-speech', methods=['POST'])
def add_fed_speech():
    """FRB発言を追加"""
    speeches = load_json('fed_speeches.json')
    data = request.json
    speeches.append({
        "date": data["date"],
        "official": data["official"],
        "summary": data["summary"],
        "stance": data["stance"],
        "market_reaction": data.get("market_reaction", "")
    })
    save_json('fed_speeches.json', speeches)
    return jsonify({"status": "ok"})


@app.route('/api/trade', methods=['POST'])
def add_trade():
    """トレードを追加"""
    trades = load_json('trades.json')
    data = request.json
    trades.append({
        "date": data["date"],
        "indicator": data["indicator"],
        "entry": data["entry"],
        "exit": data["exit"],
        "pnl": data["pnl"],
        "notes": data.get("notes", "")
    })
    save_json('trades.json', trades)
    return jsonify({"status": "ok"})


if __name__ == '__main__':
    app.run(debug=True, port=5000)
