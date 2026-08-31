import os
import uuid
import json
from datetime import datetime, timedelta, timezone
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

# How many hours a wish stays alive before auto-expiring. Set to 0 to disable
# auto-expiry entirely (wishes then live forever unless manually deleted).
WISH_EXPIRY_HOURS = int(os.environ.get("WISH_EXPIRY_HOURS", "24"))

# Optional shared secret to protect the /api/cleanup endpoint, which an
# external scheduler (e.g. a free cron service) can call periodically to
# actually remove expired wishes and their media. If unset, cleanup is
# still safe to call (it only deletes already-expired wishes) but anyone
# could trigger it, which is fine for low-stakes use, just not ideal.
CLEANUP_SECRET = os.environ.get("CLEANUP_SECRET")

# ---------------------------------------------------------------------------
# Storage mode detection (unchanged from before)
# ---------------------------------------------------------------------------
DATABASE_URL = os.environ.get("DATABASE_URL")
USE_POSTGRES = bool(DATABASE_URL)

R2_ACCOUNT_ID = os.environ.get("R2_ACCOUNT_ID")
R2_ACCESS_KEY_ID = os.environ.get("R2_ACCESS_KEY_ID")
R2_SECRET_ACCESS_KEY = os.environ.get("R2_SECRET_ACCESS_KEY")
R2_BUCKET_NAME = os.environ.get("R2_BUCKET_NAME")
R2_PUBLIC_URL = os.environ.get("R2_PUBLIC_URL")
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
# Database layer
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
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,
                delete_token TEXT
            )
            """
        )
        # Safe to run repeatedly — adds columns only if they don't already exist,
        # so this also upgrades a database created before this feature existed.
        for stmt in [
            "ALTER TABLE wishes ADD COLUMN IF NOT EXISTS expires_at TIMESTAMP",
            "ALTER TABLE wishes ADD COLUMN IF NOT EXISTS delete_token TEXT",
        ]:
            cur.execute(stmt)
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
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                expires_at TEXT,
                delete_token TEXT
            )
            """
        )
        # SQLite has no "ADD COLUMN IF NOT EXISTS", so just try and ignore
        # the error if the column is already there (e.g. on every restart).
        for stmt in [
            "ALTER TABLE wishes ADD COLUMN expires_at TEXT",
            "ALTER TABLE wishes ADD COLUMN delete_token TEXT",
        ]:
            try:
                conn.execute(stmt)
            except Exception:
                pass
        conn.commit()
        conn.close()


init_db()


def insert_wish(wish_id, occasion, title, message, sender, recipient, theme_color, photos, videos, expires_at, delete_token):
    db = get_db()
    placeholder = "%s" if USE_POSTGRES else "?"
    query = f"""
        INSERT INTO wishes (id, occasion, title, message, sender, recipient, theme_color, photos, videos, expires_at, delete_token)
        VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder})
    """
    cur = db.cursor()
    cur.execute(
        query,
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
            expires_at.isoformat() if expires_at else None,
            delete_token,
        ),
    )
    db.commit()
    cur.close()


def fetch_wish_row(wish_id):
    db = get_db()
    placeholder = "%s" if USE_POSTGRES else "?"
    cur = db.cursor()
    cur.execute(f"SELECT * FROM wishes WHERE id = {placeholder}", (wish_id,))
    row = cur.fetchone()
    cur.close()
    if row is None:
        return None
    if USE_POSTGRES:
        cols = [
            "id", "occasion", "title", "message", "sender", "recipient",
            "theme_color", "photos", "videos", "created_at", "expires_at", "delete_token",
        ]
        return dict(zip(cols, row))
    else:
        return dict(row)


def is_expired(row):
    if not row.get("expires_at"):
        return False
    expires_at = row["expires_at"]
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) > expires_at


def delete_wish_completely(wish_id, row):
    """Removes the DB row and any associated media (R2 or local disk)."""
    photos = json.loads(row["photos"])
    videos = json.loads(row["videos"])

    if USE_R2:
        for url in photos + videos:
            key = url.replace(R2_PUBLIC_URL.rstrip("/") + "/", "")
            try:
                r2_client.delete_object(Bucket=R2_BUCKET_NAME, Key=key)
            except Exception:
                pass
    else:
        wish_folder = os.path.join(LOCAL_UPLOAD_DIR, wish_id)
        if os.path.isdir(wish_folder):
            import shutil

            shutil.rmtree(wish_folder, ignore_errors=True)

    db = get_db()
    placeholder = "%s" if USE_POSTGRES else "?"
    cur = db.cursor()
    cur.execute(f"DELETE FROM wishes WHERE id = {placeholder}", (wish_id,))
    db.commit()
    cur.close()


# ---------------------------------------------------------------------------
# Media storage layer
# ---------------------------------------------------------------------------
def save_media_file(file, wish_id, unique_name):
    if USE_R2:
        key = f"{wish_id}/{unique_name}"
        content_type = file.mimetype or "application/octet-stream"
        r2_client.upload_fileobj(
            file,
            R2_BUCKET_NAME,
            key,
            ExtraArgs={"ContentType": content_type},
        )
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
    delete_token = uuid.uuid4().hex

    expires_at = None
    if WISH_EXPIRY_HOURS > 0:
        expires_at = datetime.now(timezone.utc) + timedelta(hours=WISH_EXPIRY_HOURS)

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

    insert_wish(wish_id, occasion, title, message, sender, recipient, theme_color, photos, videos, expires_at, delete_token)

    return jsonify(
        {
            "id": wish_id,
            "deleteToken": delete_token,
            "expiresAt": expires_at.isoformat() if expires_at else None,
        }
    ), 201


@app.route("/api/wishes/<wish_id>", methods=["GET"])
def get_wish(wish_id):
    row = fetch_wish_row(wish_id)
    if not row:
        return jsonify({"error": "Wish not found"}), 404

    if is_expired(row):
        # Lazily clean it up the moment someone tries to view it past expiry.
        delete_wish_completely(wish_id, row)
        return jsonify({"error": "This wish has expired"}), 410

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
            "photos": photos,
            "videos": videos,
            "expiresAt": row["expires_at"],
        }
    )


@app.route("/api/wishes/<wish_id>", methods=["DELETE"])
def delete_wish(wish_id):
    row = fetch_wish_row(wish_id)
    if not row:
        return jsonify({"error": "Wish not found"}), 404

    token = request.args.get("token") or (request.json or {}).get("token") if request.is_json else request.args.get("token")
    if not token or token != row["delete_token"]:
        return jsonify({"error": "Invalid or missing delete token"}), 403

    delete_wish_completely(wish_id, row)
    return jsonify({"deleted": True})


@app.route("/api/cleanup", methods=["POST"])
def cleanup_expired():
    """Deletes all expired wishes and their media. Meant to be called
    periodically by an external scheduler (e.g. a free cron service hitting
    this endpoint once a day)."""
    if CLEANUP_SECRET:
        provided = request.headers.get("X-Cleanup-Secret")
        if provided != CLEANUP_SECRET:
            return jsonify({"error": "Unauthorized"}), 401

    db = get_db()
    placeholder = "%s" if USE_POSTGRES else "?"
    now = datetime.now(timezone.utc).isoformat()
    cur = db.cursor()
    cur.execute(f"SELECT id FROM wishes WHERE expires_at IS NOT NULL AND expires_at < {placeholder}", (now,))
    expired_ids = [r[0] for r in cur.fetchall()]
    cur.close()

    deleted = 0
    for wish_id in expired_ids:
        row = fetch_wish_row(wish_id)
        if row:
            delete_wish_completely(wish_id, row)
            deleted += 1

    return jsonify({"deleted": deleted})


@app.route("/uploads/<wish_id>/<filename>")
def serve_upload(wish_id, filename):
    return send_from_directory(os.path.join(LOCAL_UPLOAD_DIR, wish_id), filename)


@app.route("/")
def health():
    return jsonify(
        {
            "status": "ok",
            "message": "Wish App API is running",
            "storage": "postgres" if USE_POSTGRES else "sqlite",
            "media": "r2" if USE_R2 else "local-disk",
            "expiryHours": WISH_EXPIRY_HOURS,
        }
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=os.environ.get("FLASK_DEBUG", "0") == "1", host="0.0.0.0", port=port)