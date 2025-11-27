from flask import Flask, render_template, request, redirect, url_for, jsonify, flash
import os
import json
import datetime
import uuid
from flask import send_file, abort
from collections import Counter
from typing import Optional, Iterable, List, Tuple
from markupsafe import Markup, escape
from admin import admin_bp

app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = os.getenv("SECRET_KEY", "dev-secret")  # đổi trên production
app.register_blueprint(admin_bp, url_prefix="/admin")
DATA_FILE = "data.json"
HOUR_FILE = "hour.json"


BOXES = {
    "cowboy_win": ("🤠 Cowboy", "x2", "default"),
    "draw": ("Hòa", "x20", "orange"),
    "bull_win": ("🐮 Bull", "x2", "default"),

    "suited_combo": ("Dây / Đồng chất / Dây đồng chất", "x1.66", "default"),
    "pair_any": ("Đôi", "x8.5", "default"),
    "aa": ("AA", "x100", "default"),

    "high_onepair": ("Bài cao / Một đôi", "x2.2", "default"),
    "two_pair": ("Hai đôi", "x3.1", "default"),
    "trips": ("Bộ ba", "x4.7", "default"),
    "full_house": ("Cù lũ", "x20", "orange"),
    "four_kind": ("Tứ quý", "x248", "red"),
}

RANKS = "23456789TJQKA"
SUITS = ['h', 'd', 'c', 's']

# -----------------------
# Data helpers
# -----------------------
def all_cards() -> List[str]:
    return [r + s for r in RANKS for s in SUITS]

def card_label(c: Optional[str]) -> Optional[str]:
    if not c or len(c) < 2:
        return c
    rank = c[0].upper()
    suit = c[1].lower()
    if rank == "T":
        rank = "10"
    map_s = {'s': '♠', 'h': '♥', 'd': '♦', 'c': '♣'}
    symbol = map_s.get(suit, suit)

    # Màu cố định
    red = '#c92a2a'        # hearts & diamonds
    dark = '#222222'       # spades & clubs

    if suit in ('h', 'd'):
        # trả về HTML với style inline màu đỏ
        return Markup(f'{escape(rank)}<span style="color:{red};font-weight:600;margin-left:4px">{escape(symbol)}</span>')
    else:
        return Markup(f'{escape(rank)}<span style="color:{dark};font-weight:600;margin-left:4px">{escape(symbol)}</span>')

def ensure_data_file() -> None:
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump([], f)

def load_data() -> List[dict]:
    ensure_data_file()
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []

def save_data(arr: List[dict]) -> None:
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(arr, f, ensure_ascii=False, indent=2)

# -----------------------
# Hour file helpers (slot -> list of cards)
# -----------------------
def ensure_hour_file() -> None:
    if not os.path.exists(HOUR_FILE):
        with open(HOUR_FILE, "w", encoding="utf-8") as f:
            json.dump({"aa": {}, "four_kind": {}}, f)

def load_hour_data() -> dict:
    ensure_hour_file()
    try:
        with open(HOUR_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        data = {"aa": {}, "four_kind": {}}

    # migrate nhẹ nếu dữ liệu cũ là list các HH:MM strings
    for key in ("aa", "four_kind"):
        if key in data and isinstance(data[key], list):
            new = {}
            for t in data[key]:
                if isinstance(t, str):
                    new.setdefault(t, [])
            data[key] = new
        elif key not in data:
            data[key] = {}

    return data

def save_hour_data(data: dict) -> None:
    with open(HOUR_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# -----------------------
# Time helpers (VN)
# -----------------------
VN_TZ = datetime.timezone(datetime.timedelta(hours=7))

def now_vn() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc).astimezone(VN_TZ)

def format_hhmm(dt: datetime.datetime) -> str:
    return dt.strftime("%H:%M")

def parse_hhmm(s: str) -> Optional[Tuple[int, int]]:
    """
    Chuyển 'HH:MM' -> (h, m). Trả None nếu không phải chuỗi hợp lệ hoặc ngoài phạm vi.
    """
    if not isinstance(s, str):
        return None
    parts = s.split(":")
    if len(parts) != 2:
        return None
    try:
        h = int(parts[0])
        m = int(parts[1])
    except ValueError:
        return None
    if 0 <= h < 24 and 0 <= m < 60:
        return h, m
    return None

def hhmm_to_minutes(hhmm: str) -> Optional[int]:
    """
    Chuyển 'HH:MM' -> số phút từ 00:00, hoặc None nếu input không hợp lệ.
    """
    parsed = parse_hhmm(hhmm)
    if parsed is None:
        return None
    h, m = parsed
    return h * 60 + m

def minutes_to_hhmm(minutes: int) -> str:
    minutes = minutes % (24 * 60)
    h = minutes // 60
    m = minutes % 60
    return f"{h:02d}:{m:02d}"

def next_cycle_slots(history_list: Optional[Iterable[str]], n: int = 3) -> Optional[List[str]]:
    """
    Trả về danh sách n slot 'HH:MM' tiếp theo theo vòng trong ngày dựa trên history_list.
    - history_list có thể là None, list các chuỗi, hoặc dict.keys() (iterable).
    - Nếu không có slot hợp lệ trả về None.
    - Sắp xếp theo phút trong ngày, chọn slot đầu tiên lớn hơn thời điểm hiện tại,
      nếu không có thì quay vòng từ đầu.
    """
    if not history_list:
        return None

    # Chuẩn hoá: lấy các chuỗi hợp lệ 'HH:MM' duy nhất theo thứ tự xuất hiện
    seen = set()
    clean: List[str] = []
    for item in history_list:
        if not isinstance(item, str):
            continue
        if item in seen:
            continue
        if parse_hhmm(item) is None:
            continue
        seen.add(item)
        clean.append(item)

    if not clean:
        return None

    # helper chuyển 'HH:MM' -> phút (đảm bảo int)
    def to_minutes(s: str) -> int:
        val = hhmm_to_minutes(s)
        return int(val) if val is not None else 0

    sorted_day = sorted(clean, key=to_minutes)

    now_minutes = now_vn().hour * 60 + now_vn().minute

    # tìm index bắt đầu: slot đầu tiên có phút > now_minutes
    idx_start = 0
    for i, s in enumerate(sorted_day):
        if to_minutes(s) > now_minutes:
            idx_start = i
            break
    else:
        idx_start = 0

    length = len(sorted_day)
    res = [sorted_day[(idx_start + k) % length] for k in range(n)]
    return res

# -----------------------
# Statistics
# -----------------------
def compute_stats_for_card(card: str) -> dict:
    data = load_data()  # list round objects (schema mới)
    # lọc rounds cho lá được chọn
    rounds = [r for r in data if r.get("first_card") == card]
    total = len(rounds)

    # counts: số rounds chứa mỗi box (inclusive)
    counts = Counter()
    for r in rounds:
        sbs = r.get("selected_boxes") or []
        for sb in sbs:
            counts[sb] += 1

    # percent: tỉ lệ mỗi ô trên tổng rounds (inclusive)
    percent = {k: round((counts.get(k, 0) / total * 100), 2) if total > 0 else 0.0 for k in BOXES.keys()}

    SECTIONS = {
        "top": ["cowboy_win", "draw", "bull_win"],
        "left_group": ["pair_any", "aa"],
        "right": ["high_onepair", "two_pair", "trips", "full_house", "four_kind"]
    }

    percent_by_section = {}

    # top: nội bộ trong section (giữ như trước)
    top_keys = SECTIONS["top"]
    top_total = sum(counts.get(k, 0) for k in top_keys)
    for k in top_keys:
        percent_by_section[k] = round((counts.get(k, 0) / top_total * 100), 2) if top_total > 0 else 0.0

    # left_group và suited_combo: tính theo tổng rounds (inclusive)
    for k in SECTIONS["left_group"]:
        percent_by_section[k] = percent.get(k, 0.0)
    percent_by_section["suited_combo"] = percent.get("suited_combo", 0.0)

    # right: non-four normalized nội bộ; four_kind độc lập theo tổng rounds
    right_non_four = ["high_onepair", "two_pair", "trips", "full_house"]
    non_four_total = sum(counts.get(k, 0) for k in right_non_four)
    for k in right_non_four:
        percent_by_section[k] = round((counts.get(k, 0) / non_four_total * 100), 2) if non_four_total > 0 else 0.0
    percent_by_section["four_kind"] = round((counts.get("four_kind", 0) / total * 100), 2) if total > 0 else 0.0

    return {
        "total": total,
        "counts": dict(counts),
        "percent": percent,
        "percent_by_section": percent_by_section
    }
    
def compute_global_top_cards(limit: int = 12) -> List[tuple]:
    data = load_data()  # mỗi phần tử là 1 round
    c = Counter()
    for r in data:
        card = r.get("first_card")
        if card:
            c[card] += 1
    return c.most_common(limit)
    
# -----------------------
# Helpers for hour.json analysis
# -----------------------
def best_card_for_slot_from_hour(hour_box: dict, slot: str, min_samples: int = 1) -> Optional[dict]:
    if not isinstance(hour_box, dict):
        return None
    cards = hour_box.get(slot, [])
    if not cards:
        return None
    counts = Counter(cards)
    total = len(cards)
    best_card, best_count = counts.most_common(1)[0]
    if best_count < min_samples:
        return None
    return {
        "card": best_card,
        "count": best_count,
        "total": total,
        "rate": round(best_count / total * 100, 2)
    }

def compute_topN_for_box(hour_data: dict, box_key: str, limit: int = 5) -> List[dict]:
    """
    Tính top N lá bài cho một box (ví dụ 'aa' hoặc 'four_kind').
    Trả về list các dict: {card, count, total, rate}
    """
    counts = Counter()
    total = 0
    box_dict = hour_data.get(box_key, {})
    if not isinstance(box_dict, dict):
        return []
    for slot, cards in box_dict.items():
        if isinstance(cards, list):
            for c in cards:
                counts[c] += 1
                total += 1
    top = counts.most_common(limit)
    result = []
    for card, cnt in top:
        result.append({
            "card": card,
            "count": cnt,
            "total": total,
            "rate": round((cnt / total * 100) if total > 0 else 0.0, 2)
        })
    return result

# -----------------------
# Minute stats helper + API
# -----------------------

def minute_counts_for_box(hour_data: dict, box_key: str) -> list:
    """
    Trả về list 1440 số nguyên: counts[0] = số lần nổ phút 00:00,
    counts[1] = phút 00:01, ..., counts[1439] = phút 23:59.
    """
    counts = [0] * (24 * 60)
    box = hour_data.get(box_key, {}) if isinstance(hour_data, dict) else {}
    for slot, cards in box.items():
        parsed = parse_hhmm(slot)
        if parsed is None:
            continue
        h, m = parsed
        idx = h * 60 + m
        if isinstance(cards, list):
            counts[idx] += len(cards)
        elif isinstance(cards, int):
            counts[idx] += cards
    return counts

# -----------------------
# Routes
# -----------------------
@app.route("/api/four_kind_minutes")
def api_four_kind_minutes():
    try:
        agg = int(request.args.get('agg', '1'))
        if agg <= 0:
            agg = 1
    except Exception:
        agg = 1

    hour_data = load_hour_data()
    counts = minute_counts_for_box(hour_data, "four_kind")

    if agg == 1:
        labels = [f"{h:02d}:{m:02d}" for h in range(24) for m in range(60)]
        return jsonify({"labels": labels, "counts": counts})
    else:
        buckets = []
        labels = []
        for start in range(0, 24*60, agg):
            s = sum(counts[start:start+agg])
            buckets.append(s)
            h = start // 60
            m = start % 60
            labels.append(f"{h:02d}:{m:02d}")
        return jsonify({"labels": labels, "counts": buckets, "agg": agg})
@app.route("/api/aa_minutes")
def api_aa_minutes():
    try:
        agg = int(request.args.get('agg', '1'))
        if agg <= 0: agg = 1
    except:
        agg = 1
    hour_data = load_hour_data()
    counts = minute_counts_for_box(hour_data, "aa")
    if agg == 1:
        labels = [f"{h:02d}:{m:02d}" for h in range(24) for m in range(60)]
        return jsonify({"labels": labels, "counts": counts})
    else:
        buckets = []
        labels = []
        for start in range(0, 24*60, agg):
            s = sum(counts[start:start+agg])
            buckets.append(s)
            h = start // 60
            m = start % 60
            labels.append(f"{h:02d}:{m:02d}")
        return jsonify({"labels": labels, "counts": buckets, "agg": agg})
@app.route("/", methods=["GET"])
def index():
    sel = request.args.get("card", "")
    cards = all_cards()
    top_cards = compute_global_top_cards()
    details = compute_stats_for_card(sel) if sel else None

    # aggregate across rounds (schema mới)
    data = load_data()
    agg_counts = Counter()
    total_all = len(data)  # mỗi phần tử là 1 round
    for r in data:
        sbs = r.get("selected_boxes", []) or []
        for sb in sbs:
            agg_counts[sb] += 1
    agg_percent = {k: round((agg_counts.get(k, 0) / total_all * 100) if total_all > 0 else 0.0, 2) for k in BOXES.keys()}

    # load hour data early
    hour_data = load_hour_data()

    # Lấy danh sách slot từ hour_data (keys của dict)
    aa_box = hour_data.get("aa", {})
    fk_box = hour_data.get("four_kind", {})

    aa_slots = list(aa_box.keys()) if isinstance(aa_box, dict) else []
    fk_slots = list(fk_box.keys()) if isinstance(fk_box, dict) else []

    aa_recent = aa_slots[-3:][::-1] if aa_slots else []
    fk_recent = fk_slots[-3:][::-1] if fk_slots else []

    # predictions (theo vòng lặp trong ngày) dựa trên slot list
    aa_pred = next_cycle_slots(aa_slots, 3)
    fk_pred = next_cycle_slots(fk_slots, 3)

    # tổng số bản ghi trong data (dùng khi chưa chọn lá)
    total_all = len(data)

    # nếu có lá được chọn, details đã chứa "total"
    if sel and details:
        count_for_display = details.get("total", 0)
    else:
        count_for_display = total_all

    # Tính lá tốt nhất cho mỗi slot (dựa trên hour.json)
    aa_best: dict = {}
    fk_best: dict = {}
    for t in aa_recent:
        aa_best[t] = best_card_for_slot_from_hour(hour_data.get("aa", {}), t)
    for t in fk_recent:
        fk_best[t] = best_card_for_slot_from_hour(hour_data.get("four_kind", {}), t)
    if aa_pred:
        for t in aa_pred:
            aa_best.setdefault(t, best_card_for_slot_from_hour(hour_data.get("aa", {}), t))
    if fk_pred:
        for t in fk_pred:
            fk_best.setdefault(t, best_card_for_slot_from_hour(hour_data.get("four_kind", {}), t))

    # Tính Top 5 riêng cho AA và Tứ quý
    top5_aa = compute_topN_for_box(hour_data, "aa", limit=5)
    top5_fk = compute_topN_for_box(hour_data, "four_kind", limit=5)

    return render_template("index.html",
        cards=cards, RANKS=RANKS, SUITS=SUITS,
        card_label=card_label, BOXES=BOXES,
        selected_card=sel, details=details,
        top_cards=top_cards, agg_percent=agg_percent,
        aa_recent=aa_recent, fk_recent=fk_recent,
        aa_pred=aa_pred, fk_pred=fk_pred,
        aa_best=aa_best, fk_best=fk_best,
        top5_aa=top5_aa, top5_fk=top5_fk,
        count_for_display=count_for_display
    )

@app.route("/save", methods=["POST"])
def save_round():
    first_card = request.form.get("first_card", "").strip()
    selected_boxes = request.form.getlist("selected_box")

    # Basic check: must have a card
    if not first_card:
        flash("Vui lòng chọn lá bài đầu tiên.", "error")
        return redirect(url_for("index"))

    # Normalize: remove duplicates and keep only known keys
    valid_keys = set(BOXES.keys())
    # preserve order, remove duplicates
    selected_boxes = [k for k in dict.fromkeys(selected_boxes) if k in valid_keys]

    # Define groups
    TOP_KEYS = {"cowboy_win", "draw", "bull_win"}
    RIGHT_KEYS = {"high_onepair", "two_pair", "trips", "full_house", "four_kind"}

    # Compute selections
    top_selected = [b for b in selected_boxes if b in TOP_KEYS]
    right_selected = [b for b in selected_boxes if b in RIGHT_KEYS]
    rights_excl_fk = [b for b in right_selected if b != "four_kind"]

    # Validation rules
    # 1) Top must be exactly 1
    if len(top_selected) == 0:
        flash("Lỗi: phải chọn 1 ô trong TOP (cowboy_win, draw, bull_win).", "error")
        return redirect(url_for("index", card=first_card))
    if len(top_selected) > 1:
        flash("Lỗi: chỉ được chọn đúng 1 ô trong TOP.", "error")
        return redirect(url_for("index", card=first_card))

    # 2) Right must have at least 1
    if len(right_selected) == 0:
        flash("Lỗi: phải chọn ít nhất 1 ô trong RIGHT (high_onepair, two_pair, trips, full_house, four_kind).", "error")
        return redirect(url_for("index", card=first_card))

    # 3) Rights excluding four_kind must be at most 1
    if len(rights_excl_fk) > 1:
        flash("Lỗi: chỉ được chọn tối đa 1 ô trong RIGHT (không tính tứ quý).", "error")
        return redirect(url_for("index", card=first_card))

    # Passed validation -> save
    data = load_data()
    hour_data = load_hour_data()
    now_str = format_hhmm(now_vn())

    rec = {
        "round_id": str(uuid.uuid4()),
        "first_card": first_card,
        "selected_boxes": selected_boxes
    }
    data.append(rec)

    # update hour.json
    slot = now_str
    if "aa" in selected_boxes:
        hour_data.setdefault("aa", {})
        hour_data["aa"].setdefault(slot, [])
        hour_data["aa"][slot].append(first_card)
    if "four_kind" in selected_boxes:
        hour_data.setdefault("four_kind", {})
        hour_data["four_kind"].setdefault(slot, [])
        hour_data["four_kind"][slot].append(first_card)

    save_data(data)
    save_hour_data(hour_data)
    return redirect(url_for("index"))

@app.route("/api/stats/<card>")
def api_stats_card(card: str):
    return jsonify(compute_stats_for_card(card))

@app.route("/api/boxes")
def api_boxes():
    return jsonify([
        {"key": k, "label": v[0], "payout": v[1], "color": v[2]}
        for k, v in BOXES.items()
    ])

@app.route("/admin/clear", methods=["POST"])
def admin_clear():
    save_data([])
    save_hour_data({"aa": {}, "four_kind": {}})
    return redirect(url_for("index"))


ALLOWED_DOWNLOADS = {"data.json", "hour.json"}

@app.route("/download/<filename>")
def download_file(filename: str):
    # bảo vệ: chỉ cho phép tên file trong whitelist
    if filename not in ALLOWED_DOWNLOADS:
        abort(404)
    # đường dẫn tuyệt đối tới file trong repo
    path = os.path.abspath(filename)
    # kiểm tra file nằm trong repo hiện tại (tuỳ chọn)
    if not os.path.exists(path):
        abort(404)
    try:
        return send_file(path, as_attachment=True)
    except Exception:
        abort(500)
if __name__ == "__main__":
    ensure_data_file()
    ensure_hour_file()
    app.run(host="0.0.0.0", port=8080, debug=True)
