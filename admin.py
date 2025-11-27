# admin.py
import os
import json
import tempfile
from functools import wraps
from typing import Any, Dict, List, Optional
from flask import (
    Blueprint,
    request,
    render_template,
    redirect,
    url_for,
    send_file,
    current_app,
    abort,
)

# Blueprint độc lập (template_folder trỏ tới thư mục templates của project)
admin_bp = Blueprint("admin_bp", __name__, template_folder="templates")

# Cấu hình file (có thể override bằng env vars)
DATA_FILE = os.getenv("DATA_FILE", "data.json")
HOUR_FILE = os.getenv("HOUR_FILE", "hour.json")
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN")  # set this in environment for production

# -----------------------
# Helpers: IO an toàn
# -----------------------
def ensure_file(path: str, default: Any) -> None:
    """
    Tạo file nếu chưa tồn tại, ghi default (JSON) vào file.
    """
    if not os.path.exists(path):
        try:
            dirn = os.path.dirname(path) or "."
            os.makedirs(dirn, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(default, f, ensure_ascii=False, indent=2)
        except Exception:
            current_app.logger.exception("Failed to create file %s", path)

def atomic_write_json(path: str, obj: Any) -> None:
    """
    Ghi JSON một cách atomic: ghi vào temp file rồi replace.
    """
    dirn = os.path.dirname(path) or "."
    os.makedirs(dirn, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=dirn)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except Exception:
                pass

def load_data_file(path: str = DATA_FILE) -> List[Dict]:
    """
    Trả về list rounds; nếu file không hợp lệ trả [].
    """
    ensure_file(path, [])
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
    except Exception:
        current_app.logger.exception("Failed to load data file %s", path)
    return []

def load_hour_file(path: str = HOUR_FILE) -> Dict[str, Any]:
    """
    Trả về dict hour data; nếu file không hợp lệ trả default structure.
    """
    default = {"aa": {}, "four_kind": {}}
    ensure_file(path, default)
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                # nhẹ nhàng migrate nếu cần
                for k in ("aa", "four_kind"):
                    if k not in data:
                        data[k] = {}
                return data
    except Exception:
        current_app.logger.exception("Failed to load hour file %s", path)
    return default

# -----------------------
# Auth decorator
# -----------------------
def require_admin(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        # ưu tiên header X-Admin-Token
        token = (
            request.headers.get("X-Admin-Token")
            or request.form.get("admin_token")
            or request.args.get("admin_token")
        )
        if ADMIN_TOKEN:
            if token == ADMIN_TOKEN:
                return fn(*args, **kwargs)
            # không hợp lệ -> 403
            return abort(403)
        # Nếu ADMIN_TOKEN chưa set (dev), cho phép nhưng log cảnh báo
        current_app.logger.warning("ADMIN_TOKEN not set; allowing admin access (development mode).")
        return fn(*args, **kwargs)
    return wrapper

# -----------------------
# Admin routes
# -----------------------
@admin_bp.route("/", methods=["GET"])
@require_admin
def index():
    """
    Dashboard: hiển thị stats và preview recent rounds.
    """
    data = load_data_file()
    hour_data = load_hour_file()
    stats = {
        "rounds": len(data),
        "hour_slots_aa": len(hour_data.get("aa", {})),
        "hour_slots_fk": len(hour_data.get("four_kind", {})),
    }
    preview = data[-50:][::-1] if isinstance(data, list) else []
    return render_template("admin/index.html", stats=stats, preview=preview)

@admin_bp.route("/delete_round", methods=["POST"])
@require_admin
def delete_round():
    """
    Xóa 1 round theo round_id (form POST).
    """
    rid = request.form.get("round_id")
    if not rid:
        return redirect(url_for("admin_bp.index"))
    data = load_data_file()
    new = [r for r in data if r.get("round_id") != rid]
    try:
        atomic_write_json(DATA_FILE, new)
        current_app.logger.info("admin deleted round %s", rid)
    except Exception:
        current_app.logger.exception("Failed to delete round %s", rid)
    return redirect(url_for("admin_bp.index"))

@admin_bp.route("/clear_all", methods=["POST"])
@require_admin
def clear_all():
    """
    Xóa toàn bộ data.json và hour.json (ghi lại default).
    """
    try:
        atomic_write_json(DATA_FILE, [])
        atomic_write_json(HOUR_FILE, {"aa": {}, "four_kind": {}})
        current_app.logger.info("admin cleared all data")
    except Exception:
        current_app.logger.exception("Failed to clear all data")
    return redirect(url_for("admin_bp.index"))

@admin_bp.route("/export/<which>", methods=["GET"])
@require_admin
def export(which: str):
    """
    Tải về data.json hoặc hour.json.
    """
    if which == "data":
        path = DATA_FILE
        name = "data.json"
    elif which == "hour":
        path = HOUR_FILE
        name = "hour.json"
    else:
        return abort(404)
    if not os.path.exists(path):
        return abort(404)
    # send_file sẽ stream file hiện có
    try:
        return send_file(path, as_attachment=True, download_name=name)
    except TypeError:
        # fallback cho Flask cũ
        return send_file(path, as_attachment=True)

@admin_bp.route("/slot_delete", methods=["POST"])
@require_admin
def slot_delete():
    """
    Xóa một slot trong hour.json (form POST: box='aa'|'four_kind', slot='HH:MM').
    """
    box = request.form.get("box")
    slot = request.form.get("slot")
    if not box or not slot:
        return redirect(url_for("admin_bp.index"))
    hour_data = load_hour_file()
    if box in hour_data and slot in hour_data[box]:
        try:
            del hour_data[box][slot]
            atomic_write_json(HOUR_FILE, hour_data)
            current_app.logger.info("admin removed slot %s from %s", slot, box)
        except Exception:
            current_app.logger.exception("Failed to remove slot %s from %s", slot, box)
    return redirect(url_for("admin_bp.index"))

@admin_bp.route("/health", methods=["GET"])
def health():
    """
    Health check: trả 200 nếu có thể đọc file data/hour.
    """
    try:
        _ = load_data_file()
        _ = load_hour_file()
        return ("ok", 200)
    except Exception:
        return ("error", 500)