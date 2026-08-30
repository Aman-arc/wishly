import os
import uuid
import json
from urllib.parse import urlparse
from flask import Flask, request, jsonify, send_from_directory, g
from flask_cors import CORS
from werkzeug.utils import secure_filename

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOCAL_UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
LOCAL_DB_PATH = os.path.join(BASE_DIR, "wishes.db")

ALLOWED_IMAGE_EXT = {"png", "jpg", "jpeg", "gif", "webp"}
ALLOWED_VIDEO_EXT = {"mp4", "webm", "mov", "ogg"}

os.makedirs(LOCAL_UPLOAD_DIR, exist_ok=True)

app = Flask(__name__)

allowed_origins = os.environ.get("ALLOWED_ORIGINS", "*")
CORS(app, origins=allowed_origins.split(",") if allowed_origins != "*" else "*")

app.config["MAX_CONTENT_LENGTH"] = 150 * 1024 * 1024  # 150 MB total upload limit

# ---------------------------------------------------------------------------
# Storage mode detection
#   - DATABASE_URL set   -> use Postgres (Render's managed database)
#   - not set            -> use local SQLite file (good for local dev)
#   - R2 env vars set    -> upload media to Cloudflare R2 (durable, survives redeploys)
#   - not set            -> save media to local disk (good for local dev)
# ---------------------------------------------------------------------------
DATABASE_URL = os.environ.get("DATABASE_URL")
USE_POSTGRES = bool(DATABASE_URL)

R2_ACCOUNT_ID = os.environ.get("R2_ACCOUNT_ID")
R2_ACCESS_KEY_ID = os.environ.get("R2_ACCESS_KEY_ID")
R2_SECRET_ACCESS_KEY = os.environ.get("R2_SECRET_ACCESS_KEY")
R2_BUCKET_NAME = os.environ.get("R2_BUCKET_NAME")
R2_PUBLIC_URL = os.environ.get("R2_PUBLIC_URL")  # e.g. https://media.yourdomain.com or the r2.dev URL
USE_R2 = all([R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET_NAME, R2_PUBLIC_URL])

if USE_POSTGRES:
    import psycopg2
    import psycopg2.extras

if USE_R2:
    import boto3
    from botocore.config import Config

    r2_client = boto3.client(
        "s3",
        endpoint_url=f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
        aws_access_key_id=R2_ACCESS_KEY_ID,
        aws_secret_access_key=R2_SECRET_ACCESS_KEY,
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )

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


def allowed_file(filename, allowed_ext):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed_ext


# ---------------------------------------------------------------------------
# Database layer — Postgres in production, SQLite for local dev.
# Both are accessed through the same small set of functions below so the
# rest of the app doesn't need to care which one is active.
# ---------------------------------------------------------------------------
def get_db():
    if "db" not in g:
        if USE_POSTGRES:
            g.db = psycopg2.connect(DATABASE_URL, sslmode="require")
        else:
            import sqlite3

            g.db = sqlite3.connect(LOCAL_DB_PATH)
            g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    if USE_POSTGRES:
        conn = psycopg2.connect(DATABASE_URL, sslmode="require")
        cur = conn.cursor()
        cur.execute(
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
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()
        cur.close()
        conn.close()
    else:
        import sqlite3

        conn = sqlite3.connect(LOCAL_DB_PATH)
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


def insert_wish(wish_id, occasion, title, message, sender, recipient, theme_color, photos, videos):
    db = get_db()
    placeholder = "%s" if USE_POSTGRES else "?"
    query = f"""
        INSERT INTO wishes (id, occasion, title, message, sender, recipient, theme_color, photos, videos)
        VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder})
    """
    cur = db.cursor()
    cur.execute(
        query,
        (wish_id, occasion, title, message, sender, recipient, theme_color, json.dumps(photos), json.dumps(videos)),
    )
    db.commit()
    cur.close()


def fetch_wish(wish_id):
    db = get_db()
    placeholder = "%s" if USE_POSTGRES else "?"
    cur = db.cursor()
    cur.execute(f"SELECT * FROM wishes WHERE id = {placeholder}", (wish_id,))
    row = cur.fetchone()
    cur.close()
    if row is None:
        return None
    if USE_POSTGRES:
        cols = ["id", "occasion", "title", "message", "sender", "recipient", "theme_color", "photos", "videos", "created_at"]
        return dict(zip(cols, row))
    else:
        return dict(row)


# ---------------------------------------------------------------------------
# Media storage layer — Cloudflare R2 in production, local disk for dev.
# ---------------------------------------------------------------------------
def save_media_file(file, wish_id, unique_name):
    """Saves a file either to R2 (returns a full public URL) or locally
    (returns a relative path served by /uploads/...)."""
    if USE_R2:
        key = f"{wish_id}/{unique_name}"
        r2_client.upload_fileobj(file, R2_BUCKET_NAME, key)
        return f"{R2_PUBLIC_URL.rstrip('/')}/{key}"
    else:
        wish_folder = os.path.join(LOCAL_UPLOAD_DIR, wish_id)
        os.makedirs(wish_folder, exist_ok=True)
        file.save(os.path.join(wish_folder, unique_name))
        return f"/uploads/{wish_id}/{unique_name}"


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

    photos, videos = [], []

    for file in request.files.getlist("photos"):
        if file and file.filename and allowed_file(file.filename, ALLOWED_IMAGE_EXT):
            fname = secure_filename(file.filename)
            unique_name = f"{uuid.uuid4().hex[:6]}_{fname}"
            url = save_media_file(file, wish_id, unique_name)
            photos.append(url)

    for file in request.files.getlist("videos"):
        if file and file.filename and allowed_file(file.filename, ALLOWED_VIDEO_EXT):
            fname = secure_filename(file.filename)
            unique_name = f"{uuid.uuid4().hex[:6]}_{fname}"
            url = save_media_file(file, wish_id, unique_name)
            videos.append(url)

    insert_wish(wish_id, occasion, title, message, sender, recipient, theme_color, photos, videos)

    return jsonify({"id": wish_id}), 201


@app.route("/api/wishes/<wish_id>", methods=["GET"])
def get_wish(wish_id):
    row = fetch_wish(wish_id)
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
            # Stored values are already full URLs when using R2, or relative
            # paths (starting with /uploads/...) when using local disk.
            "photos": photos,
            "videos": videos,
        }
    )


@app.route("/uploads/<wish_id>/<filename>")
def serve_upload(wish_id, filename):
    # Only used in local-dev mode (USE_R2 is False). In production with R2,
    # media is served directly from R2's public URL instead.
    return send_from_directory(os.path.join(LOCAL_UPLOAD_DIR, wish_id), filename)


@app.route("/")
def health():
    return jsonify(
        {
            "status": "ok",
            "message": "Wish App API is running",
            "storage": "postgres" if USE_POSTGRES else "sqlite",
            "media": "r2" if USE_R2 else "local-disk",
        }
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=os.environ.get("FLASK_DEBUG", "0") == "1", host="0.0.0.0", port=port)
