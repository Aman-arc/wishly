import os
import sqlite3
import uuid
import json
from flask import Flask, request, jsonify, send_from_directory, g
from flask_cors import CORS
from werkzeug.utils import secure_filename

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
DB_PATH = os.path.join(BASE_DIR, "wishes.db")

ALLOWED_IMAGE_EXT = {"png", "jpg", "jpeg", "gif", "webp"}
ALLOWED_VIDEO_EXT = {"mp4", "webm", "mov", "ogg"}

os.makedirs(UPLOAD_DIR, exist_ok=True)

app = Flask(__name__)

# In production set ALLOWED_ORIGINS to your deployed frontend URL, e.g.
# ALLOWED_ORIGINS=https://your-app.vercel.app
allowed_origins = os.environ.get("ALLOWED_ORIGINS", "*")
CORS(app, origins=allowed_origins.split(",") if allowed_origins != "*" else "*")

app.config["MAX_CONTENT_LENGTH"] = 150 * 1024 * 1024  # 150 MB total upload limit

# ---------------------------------------------------------------------------
# Default generic messages used when the user leaves the message blank
# ---------------------------------------------------------------------------
DEFAULT_MESSAGES = {
    "birthday": "Wishing you a fantastic birthday filled with love, laughter, and all your favorite things. May this year bring you closer to every dream you're chasing!",
    "anniversary": "Happy Anniversary! Here's to the love you share and the beautiful memories you continue to create together.",
    "congratulations": "Congratulations on this well-deserved achievement! Your hard work and dedication truly paid off.",
    "wedding": "Wishing you a lifetime of love, laughter, and happily ever after. Congratulations on your wedding!",
    "graduation": "Congratulations, Graduate! This is just the beginning of an amazing journey ahead.",
    "farewell": "Wishing you the very best in this new chapter. You'll be missed, but never forgotten!",
    "getwellsoon": "Sending you warm wishes for a speedy recovery. Take care and feel better soon!",
    "newborn": "Congratulations on your bundle of joy! Wishing your family endless love and happiness.",
    "other": "Sending you warm wishes today and always. Hope your day is as special as you are!",
}

DEFAULT_TITLES = {
    "birthday": "Happy Birthday!",
    "anniversary": "Happy Anniversary!",
    "congratulations": "Congratulations!",
    "wedding": "Congratulations on Your Wedding!",
    "graduation": "Congratulations, Graduate!",
    "farewell": "Wishing You Well!",
    "getwellsoon": "Get Well Soon!",
    "newborn": "Welcome, Little One!",
    "other": "A Special Wish For You",
}


# ---------------------------------------------------------------------------
# SQLite helpers
# ---------------------------------------------------------------------------
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS wishes (
            id TEXT PRIMARY KEY,
            occasion TEXT NOT NULL,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            sender TEXT,
            recipient TEXT,
            theme_color TEXT,
            photos TEXT NOT NULL DEFAULT '[]',
            videos TEXT NOT NULL DEFAULT '[]',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.commit()
    conn.close()


init_db()


def allowed_file(filename, allowed_ext):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed_ext


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route("/api/wishes", methods=["POST"])
def create_wish():
    occasion = request.form.get("occasion", "other").lower().strip()
    if occasion not in DEFAULT_MESSAGES:
        occasion = "other"

    title = request.form.get("title", "").strip()
    message = request.form.get("message", "").strip()
    sender = request.form.get("sender", "").strip()
    recipient = request.form.get("recipient", "").strip()
    theme_color = request.form.get("themeColor", "").strip()

    if not message:
        message = DEFAULT_MESSAGES.get(occasion, DEFAULT_MESSAGES["other"])
    if not title:
        title = DEFAULT_TITLES.get(occasion, DEFAULT_TITLES["other"])

    wish_id = uuid.uuid4().hex[:10]
    wish_folder = os.path.join(UPLOAD_DIR, wish_id)
    os.makedirs(wish_folder, exist_ok=True)

    photos, videos = [], []

    for file in request.files.getlist("photos"):
        if file and file.filename and allowed_file(file.filename, ALLOWED_IMAGE_EXT):
            fname = secure_filename(file.filename)
            unique_name = f"{uuid.uuid4().hex[:6]}_{fname}"
            file.save(os.path.join(wish_folder, unique_name))
            photos.append(unique_name)

    for file in request.files.getlist("videos"):
        if file and file.filename and allowed_file(file.filename, ALLOWED_VIDEO_EXT):
            fname = secure_filename(file.filename)
            unique_name = f"{uuid.uuid4().hex[:6]}_{fname}"
            file.save(os.path.join(wish_folder, unique_name))
            videos.append(unique_name)

    db = get_db()
    db.execute(
        """
        INSERT INTO wishes (id, occasion, title, message, sender, recipient, theme_color, photos, videos)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            wish_id,
            occasion,
            title,
            message,
            sender,
            recipient,
            theme_color,
            json.dumps(photos),
            json.dumps(videos),
        ),
    )
    db.commit()

    return jsonify({"id": wish_id}), 201


@app.route("/api/wishes/<wish_id>", methods=["GET"])
def get_wish(wish_id):
    db = get_db()
    row = db.execute("SELECT * FROM wishes WHERE id = ?", (wish_id,)).fetchone()
    if not row:
        return jsonify({"error": "Wish not found"}), 404

    photos = json.loads(row["photos"])
    videos = json.loads(row["videos"])

    return jsonify(
        {
            "occasion": row["occasion"],
            "title": row["title"],
            "message": row["message"],
            "sender": row["sender"],
            "recipient": row["recipient"],
            "themeColor": row["theme_color"],
            "photos": [f"/uploads/{wish_id}/{p}" for p in photos],
            "videos": [f"/uploads/{wish_id}/{v}" for v in videos],
        }
    )


@app.route("/uploads/<wish_id>/<filename>")
def serve_upload(wish_id, filename):
    return send_from_directory(os.path.join(UPLOAD_DIR, wish_id), filename)


@app.route("/")
def health():
    return jsonify({"status": "ok", "message": "Wish App API is running"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=os.environ.get("FLASK_DEBUG", "0") == "1", host="0.0.0.0", port=port)
