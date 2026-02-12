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
        {"date": "2026-02-11", "month": "2026-01"},
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
    today_str = today.strftime("%Y-%m-%d")
    for event_type, schedule in SCHEDULE_2026.items():
        for event in schedule:
            # 今日以降のイベントのみ表示
            if event["date"] >= today_str:
                events.append({
                    "type": event_type.upper(),
                    "date": event["date"],
                    **event
                })

    events.sort(key=lambda x: x["date"])
    # 直近10件に制限
    events = events[:10]

    # 次回NFPの予測シグナルを取得
    next_prediction = None
    if next_nfp:
        scenarios = load_json('nfp_scenarios.json')
        scenario = scenarios.get(next_nfp["month"])
        if scenario and "prediction" in scenario:
            next_prediction = scenario["prediction"]

    return render_template('index.html',
                         today=today.strftime("%Y-%m-%d"),
                         next_nfp=next_nfp,
                         next_prediction=next_prediction,
                         events=events)


@app.route('/nfp')
@app.route('/nfp/<month>')
def nfp_page(month=None):
    """雇用統計ページ"""
    nfp_data = load_json('nfp_history.json')
    fed_speeches = load_json('fed_speeches.json')
    scenarios = load_json('nfp_scenarios.json')

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

    # シナリオ分析（あれば）
    scenario = scenarios.get(month)

    # 全NFPリスト
    all_nfp = SCHEDULE_2026["nfp"]

    return render_template('nfp.html',
                         month=month,
                         schedule=nfp_schedule,
                         data=month_data,
                         speeches=related_speeches,
                         scenario=scenario,
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


@app.route('/vip-quotes')
def vip_quotes_page():
    """要人発言ページ"""
    # サンプルデータ（後でJSONファイル化可能）
    investor_quotes = [
        {
            "name": "ラリー・フィンク",
            "title": "ブラックロック CEO",
            "emoji": "🏛️",
            "date": "2026-01-23",
            "event": "ダボス会議",
            "quote": "インフラと民間市場への投資機会は拡大している。長期投資家にとって好機だ。",
            "stance": "bullish",
            "market_impact": "BLK +1.5%",
            "color": "pop-blue",
            "color2": "pop-purple"
        },
        {
            "name": "ジェイミー・ダイモン",
            "title": "JPモルガン CEO",
            "emoji": "🏦",
            "date": "2026-01-23",
            "event": "ダボス会議",
            "quote": "地政学的リスクは過小評価されている。企業は備えが必要だ。",
            "stance": "cautious",
            "market_impact": None,
            "color": "pop-red",
            "color2": "pop-pink"
        },
        {
            "name": "レイ・ダリオ",
            "title": "ブリッジウォーター創業者",
            "emoji": "📊",
            "date": "2026-01-24",
            "event": "CNBC インタビュー",
            "quote": "債務サイクルの終盤にいる。現金と金に分散投資すべき時期だ。",
            "stance": "bearish",
            "market_impact": "金価格 +1.2%",
            "color": "pop-yellow",
            "color2": "pop-orange"
        },
        {
            "name": "キャシー・ウッド",
            "title": "ARK Invest CEO",
            "emoji": "🚀",
            "date": "2026-01-22",
            "event": "Bloomberg TV",
            "quote": "AI革命はまだ始まったばかり。我々は引き続きディスラプティブ・イノベーションに投資する。",
            "stance": "bullish",
            "market_impact": "ARKK +2.3%",
            "color": "pop-green",
            "color2": "pop-cyan"
        }
    ]

    # ペロシ銘柄（STOCK Act開示情報 - 2026/1/23開示分）
    pelosi_trades = [
        {
            "politician": "ナンシー・ペロシ（夫 ポール）",
            "emoji": "👩‍⚖️",
            "date": "2026-01-16",
            "action": "buy",
            "ticker": "AB",
            "company": "アライアンス・バーンスタイン",
            "amount": "25,000株（新規）"
        },
        {
            "politician": "ナンシー・ペロシ（夫 ポール）",
            "emoji": "👩‍⚖️",
            "date": "2026-01-16",
            "action": "buy",
            "ticker": "VST",
            "company": "Vistra Corp",
            "amount": "5,000株（オプション行使）"
        },
        {
            "politician": "ナンシー・ペロシ（夫 ポール）",
            "emoji": "👩‍⚖️",
            "date": "2026-01",
            "action": "buy",
            "ticker": "NVDA",
            "company": "エヌビディア",
            "amount": "コールオプション（2027年1月期限）"
        },
        {
            "politician": "ナンシー・ペロシ（夫 ポール）",
            "emoji": "👩‍⚖️",
            "date": "2026-01",
            "action": "buy",
            "ticker": "GOOGL",
            "company": "アルファベット",
            "amount": "5,000株（オプション行使）+ 新規コールOP"
        },
        {
            "politician": "ナンシー・ペロシ（夫 ポール）",
            "emoji": "👩‍⚖️",
            "date": "2026-01",
            "action": "buy",
            "ticker": "AMZN",
            "company": "アマゾン",
            "amount": "5,000株（オプション行使）+ 新規コールOP"
        },
        {
            "politician": "ナンシー・ペロシ（夫 ポール）",
            "emoji": "👩‍⚖️",
            "date": "2025-12〜2026-01",
            "action": "sell",
            "ticker": "AAPL",
            "company": "アップル",
            "amount": "約45,000株を売却・寄付"
        },
    ]

    davos_quotes = [
        {
            "name": "クリスティーヌ・ラガルド",
            "title": "ECB総裁",
            "emoji": "🇪🇺",
            "date": "2026-01-23",
            "quote": "インフレは低下傾向にあるが、利下げを急ぐ理由はない。",
            "topic": "金融政策"
        },
        {
            "name": "ジャネット・イエレン",
            "title": "米財務長官",
            "emoji": "🇺🇸",
            "date": "2026-01-22",
            "quote": "米国経済はソフトランディングを達成しつつある。",
            "topic": "米経済"
        },
        {
            "name": "李強",
            "title": "中国首相",
            "emoji": "🇨🇳",
            "date": "2026-01-21",
            "quote": "中国は外国投資を歓迎し、市場開放を継続する。",
            "topic": "中国経済"
        }
    ]

    # 機関投資家データ（実際の13Fファイリングに基づく）
    hedge_funds = [
        {
            "name": "バークシャー・ハサウェイ",
            "aum": "$2,673億（株式のみ）",
            "return_2025": 10.9,
            "top_holdings": "AAPL, AXP, BAC, OXY",
            "recent_move": "現金$3,816億で過去最高。バフェット引退（2026/1/1）、グレッグ・アベルがCEO就任。OxyChem買収$97億"
        },
        {
            "name": "ブリッジウォーター",
            "aum": "$1,500億",
            "return_2025": 8.2,
            "top_holdings": "SPY, GLD, TLT",
            "recent_move": "金ETFへの配分を増加"
        },
        {
            "name": "シタデル",
            "aum": "$600億",
            "return_2025": 15.3,
            "top_holdings": "テック株中心",
            "recent_move": None
        },
        {
            "name": "ルネサンス・テクノロジーズ",
            "aum": "$1,300億",
            "return_2025": 22.1,
            "top_holdings": "非公開（クオンツ戦略）",
            "recent_move": "メダリオンファンド好調"
        }
    ]

    # バフェット銘柄（13Fファイリング公開情報）
    buffett_analysis = {
        "cash_position": "$3,816億",
        "cash_trend": "2026/1/1にCEO引退。グレッグ・アベルが後任。会長職は継続",
        "apple_sold": "Apple・BofA・VeriSignを売却。退任前に6銘柄$64億購入",
        "new_position": "OxyChem（オキシデンタル石化部門）を$97億で買収"
    }

    return render_template('vip_quotes.html',
                         investor_quotes=investor_quotes,
                         pelosi_trades=pelosi_trades,
                         davos_quotes=davos_quotes,
                         hedge_funds=hedge_funds,
                         buffett_analysis=buffett_analysis)


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
