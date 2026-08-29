# Wishly 🎁 — Send a Beautiful Wish, Shareable by Link

Fill in an occasion, a message, and optional photos/videos, and get a link
anyone can open — on any computer or phone — to see a beautifully animated
wish page. Leave the message blank and a warm default is used automatically.

Stack: **Python (Flask + SQLite) backend** + **React (Vite) frontend**.

---

## Project structure

```
wish-app/
├── backend/
│   ├── app.py          # Flask API (SQLite storage, serves uploaded media)
│   ├── requirements.txt
│   ├── Procfile         # for gunicorn on Render/Railway/Heroku-style hosts
│   ├── render.yaml       # one-click-ish Render deployment config
│   ├── uploads/          # created automatically — stores photos/videos
│   └── wishes.db         # created automatically — SQLite database
└── frontend/
    ├── src/
    │   ├── api.js             # API client, reads VITE_API_URL
    │   ├── pages/CreateWish.jsx
    │   ├── pages/ViewWish.jsx
    │   ├── App.jsx / main.jsx / styles.css
    ├── public/_redirects      # Netlify SPA routing rule
    ├── vercel.json            # Vercel SPA routing rule
    ├── .env.example
    └── vite.config.js
```

---

## 1. Run it locally first (recommended before deploying)

**Backend:**
```bash
cd backend
python3 -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py
```
Runs at `http://localhost:5000`. SQLite database (`wishes.db`) and the
`uploads/` folder are created automatically on first run.

**Frontend** (second terminal):
```bash
cd frontend
npm install
npm run dev
```
Runs at `http://localhost:5173`. Vite proxies `/api` and `/uploads` to Flask,
so no extra config is needed locally — just leave `VITE_API_URL` unset.

---

## 2. Deploy so the link works for anyone, anywhere

You need the backend and frontend each hosted publicly. This uses two free
tiers: **Render** for the Flask API, **Vercel** for the React app.

### Step A — Deploy the backend to Render
1. Push this project to a GitHub repo (or use Render's "public git repo" option).
2. Go to [render.com](https://render.com) → **New +** → **Blueprint**, and point it
   at your repo — it will pick up `backend/render.yaml` automatically. Or
   manually: **New +** → **Web Service**, root directory `backend`, build
   command `pip install -r requirements.txt`, start command
   `gunicorn -w 2 -b 0.0.0.0:$PORT app:app`.
3. Once deployed, copy the URL Render gives you, e.g.
   `https://wishly-backend.onrender.com`.

   **Note on uploaded photos/videos:** `render.yaml` attaches a small
   persistent disk mounted at the backend folder, so `wishes.db` and
   `uploads/` survive restarts on Render's free tier. If you deploy manually
   without a disk, uploaded files will be wiped whenever the service restarts
   — fine for a quick test, not for anything long‑lived. For a fully durable
   setup later, swap local file storage for an S3‑compatible bucket (e.g.
   Cloudflare R2) — only the two file-save lines in `app.py` would need to
   change.

### Step B — Deploy the frontend to Vercel
1. Go to [vercel.com](https://vercel.com) → **Add New** → **Project** → import
   the same repo, set the root directory to `frontend`.
2. Add an environment variable: `VITE_API_URL` = the Render URL from Step A
   (e.g. `https://wishly-backend.onrender.com`), no trailing slash.
3. Deploy. Vercel will give you a URL like `https://wishly.vercel.app`.

### Step C — Lock down CORS (optional but recommended)
Back in Render, set the backend's `ALLOWED_ORIGINS` environment variable to
your Vercel URL (e.g. `https://wishly.vercel.app`) instead of `*`, then
redeploy the backend. This restricts who can call your API directly.

**That's it.** Now anyone can open `https://wishly.vercel.app`, create a
wish, and share the resulting link — it opens correctly on any phone,
tablet, or computer, no local setup required on their end.

---

## Notes

- Photos accepted: png, jpg, jpeg, gif, webp. Videos: mp4, webm, mov, ogg.
- Max upload size is capped at 150MB per wish in `app.py`
  (`MAX_CONTENT_LENGTH`) — adjust if needed.
- Storage is SQLite (`wishes.db`) — fine for personal/small-scale use. For
  heavier traffic, swap in Postgres; only `get_db`/`init_db` in `app.py`
  would need to change.
- The view page opens with a tap-to-reveal envelope animation, then confetti,
  a photo carousel, optional videos, and the message — themed by occasion.
