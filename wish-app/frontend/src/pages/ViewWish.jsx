import { useEffect, useState, useRef } from "react";
import { useParams } from "react-router-dom";
import api, { mediaUrl } from "../api.js";
import confetti from "canvas-confetti";

const OCCASION_EMOJI = {
  birthday: "🎂",
  anniversary: "💍",
  congratulations: "🎉",
  wedding: "💐",
  graduation: "🎓",
  farewell: "👋",
  getwellsoon: "💐",
  newborn: "👶",
  other: "✨",
};

export default function ViewWish() {
  const { id } = useParams();
  const [wish, setWish] = useState(null);
  const [error, setError] = useState("");
  const [activePhoto, setActivePhoto] = useState(0);
  const [opened, setOpened] = useState(false);
  const [lightbox, setLightbox] = useState(null); // { type: 'image'|'video', src }
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState("");
  const fired = useRef(false);

  useEffect(() => {
    api
      .get(`/api/wishes/${id}`)
      .then((res) => setWish(res.data))
      .catch((err) => {
        if (err?.response?.status === 410) {
          setError("This wish has expired and is no longer available.");
        } else {
          setError("This wish couldn't be found. The link may be incorrect.");
        }
      });
  }, [id]);

  useEffect(() => {
    if (opened && wish && !fired.current) {
      fired.current = true;
      launchConfetti(wish.themeColor);
    }
  }, [opened, wish]);

  useEffect(() => {
    if (!wish || !wish.photos || wish.photos.length < 2) return;
    const t = setInterval(() => {
      setActivePhoto((p) => (p + 1) % wish.photos.length);
    }, 3500);
    return () => clearInterval(t);
  }, [wish]);

  function launchConfetti(color) {
    const colors = color ? [color, "#ffffff", "#ffd700"] : undefined;
    const duration = 2500;
    const end = Date.now() + duration;
    (function frame() {
      confetti({ particleCount: 4, angle: 60, spread: 55, origin: { x: 0 }, colors });
      confetti({ particleCount: 4, angle: 120, spread: 55, origin: { x: 1 }, colors });
      if (Date.now() < end) requestAnimationFrame(frame);
    })();
    confetti({ particleCount: 120, spread: 100, origin: { y: 0.6 }, colors });
  }

  async function urlToDataUrl(url) {
    const res = await fetch(url);
    if (!res.ok) throw new Error(`Failed to fetch ${url}`);
    const blob = await res.blob();
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onloadend = () => resolve(reader.result);
      reader.onerror = reject;
      reader.readAsDataURL(blob);
    });
  }

  function escapeHtml(str) {
    if (!str) return "";
    return str
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function buildStandaloneHtml({ title, message, sender, recipient, accent, emoji, photoDataUrls, videoDataUrls }) {
    const photosHtml = photoDataUrls
      .map((src) => `<img src="${src}" alt="Memory" style="width:100%;display:block;border-radius:16px;margin-bottom:16px;" />`)
      .join("\n");
    const videosHtml = videoDataUrls
      .map((src) => `<video src="${src}" controls playsinline style="width:100%;border-radius:16px;margin-bottom:16px;"></video>`)
      .join("\n");

    return `<!doctype html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>${escapeHtml(title)}</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Poppins, sans-serif;
    background: radial-gradient(circle at top, ${accent}30, #fff5f8);
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 24px;
  }
  .card {
    max-width: 620px;
    width: 100%;
    background: rgba(255,255,255,0.95);
    border-radius: 28px;
    padding: 40px 34px;
    text-align: center;
    box-shadow: 0 25px 70px rgba(0,0,0,0.12);
  }
  .to-line { color: #8d99ae; font-size: 0.95rem; margin-bottom: 4px; }
  h1 {
    font-size: 2.1rem;
    font-weight: 800;
    background: linear-gradient(90deg, ${accent}, #c77dff);
    -webkit-background-clip: text;
    background-clip: text;
    color: transparent;
    margin-bottom: 18px;
  }
  .message { font-size: 1.08rem; line-height: 1.7; color: #3a3d5c; margin: 22px 0; white-space: pre-wrap; }
  .from-line { font-size: 1.4rem; font-style: italic; color: ${accent}; margin-bottom: 10px; }
  .footer { font-size: 0.75rem; color: #c1c4d6; margin-top: 16px; }
  .saved-note { font-size: 0.72rem; color: #c1c4d6; margin-top: 4px; }
</style>
</head>
<body>
  <div class="card">
    ${recipient ? `<p class="to-line">To ${escapeHtml(recipient)}</p>` : ""}
    <h1>${emoji} ${escapeHtml(title)}</h1>
    ${photosHtml}
    <p class="message">${escapeHtml(message)}</p>
    ${videosHtml}
    ${sender ? `<p class="from-line">With love, ${escapeHtml(sender)} 💌</p>` : ""}
    <div class="footer">Made with Wishly ✨</div>
    <div class="saved-note">Saved on ${new Date().toLocaleDateString()} — this is a permanent offline copy.</div>
  </div>
</body>
</html>`;
  }

  async function handleSaveWish() {
    setSaving(true);
    setSaveError("");
    try {
      const photoDataUrls = await Promise.all(wish.photos.map((p) => urlToDataUrl(mediaUrl(p))));
      const videoDataUrls = await Promise.all(wish.videos.map((v) => urlToDataUrl(mediaUrl(v))));

      const html = buildStandaloneHtml({
        title: wish.title,
        message: wish.message,
        sender: wish.sender,
        recipient: wish.recipient,
        accent: wish.themeColor || "#ff6b9d",
        emoji: OCCASION_EMOJI[wish.occasion] || "✨",
        photoDataUrls,
        videoDataUrls,
      });

      const blob = new Blob([html], { type: "text/html" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${(wish.title || "wish").replace(/[^a-z0-9]+/gi, "_").toLowerCase()}.html`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error(err);
      setSaveError("Couldn't save this wish right now — please try again.");
    } finally {
      setSaving(false);
    }
  }

  if (error) {
    return (
      <div className="page view-page not-found">
        <div className="not-found-card">
          <span style={{ fontSize: "3rem" }}>💔</span>
          <h2>{error}</h2>
        </div>
      </div>
    );
  }

  if (!wish) {
    return (
      <div className="page view-page loading-page">
        <div className="loader" />
        <p>Loading your surprise...</p>
      </div>
    );
  }

  const emoji = OCCASION_EMOJI[wish.occasion] || "✨";
  const accent = wish.themeColor || "#ff6b9d";

  if (!opened) {
    return (
      <div className="page view-page envelope-page" style={{ "--accent": accent }}>
        <div className="envelope" onClick={() => setOpened(true)}>
          <div className="envelope-emoji">{emoji}</div>
          <p className="envelope-hint">Tap to open your surprise</p>
        </div>
        {wish.recipient && <p className="envelope-to">For {wish.recipient}</p>}
      </div>
    );
  }

  return (
    <div className="page view-page reveal" style={{ "--accent": accent }}>
      <div className="floating-shapes" aria-hidden="true">
        {Array.from({ length: 12 }).map((_, i) => (
          <span key={i} className={`shape shape-${i % 4}`} style={{ animationDelay: `${i * 0.6}s` }}>
            {emoji}
          </span>
        ))}
      </div>

      <div className="wish-card">
        {wish.recipient && <p className="to-line">To {wish.recipient}</p>}
        <h1 className="wish-title">
          {emoji} {wish.title}
        </h1>

        {wish.photos.length > 0 && (
          <div className="photo-carousel">
            <img
              src={mediaUrl(wish.photos[activePhoto])}
              alt="Memory"
              onClick={() => setLightbox({ type: "image", src: mediaUrl(wish.photos[activePhoto]) })}
            />
            {wish.photos.length > 1 && (
              <div className="dots">
                {wish.photos.map((_, i) => (
                  <span
                    key={i}
                    className={`dot ${i === activePhoto ? "active" : ""}`}
                    onClick={() => setActivePhoto(i)}
                  />
                ))}
              </div>
            )}
          </div>
        )}

        <p className="wish-message">{wish.message}</p>

        {wish.videos.length > 0 && (
          <div className="video-grid">
            {wish.videos.map((v, i) => (
              <video
                key={i}
                src={mediaUrl(v)}
                controls
                playsInline
                onClick={(e) => {
                  e.preventDefault();
                  setLightbox({ type: "video", src: mediaUrl(v) });
                }}
              />
            ))}
          </div>
        )}

        {wish.sender && <p className="from-line">With love, {wish.sender} 💌</p>}

        <button className="save-btn" onClick={handleSaveWish} disabled={saving}>
          {saving ? "Preparing your download..." : "💾 Save this wish"}
        </button>
        {saveError && <p className="error-text">{saveError}</p>}
        <p className="save-hint">Downloads a permanent copy you can open anytime, even offline.</p>

        <div className="footer-tag">Made with Wishly ✨</div>
      </div>

      {lightbox && (
        <div className="lightbox-overlay" onClick={() => setLightbox(null)}>
          <button className="lightbox-close" onClick={() => setLightbox(null)}>
            ✕
          </button>
          {lightbox.type === "image" ? (
            <img src={lightbox.src} alt="Full size" onClick={(e) => e.stopPropagation()} />
          ) : (
            <video src={lightbox.src} controls autoPlay playsInline onClick={(e) => e.stopPropagation()} />
          )}
        </div>
      )}
    </div>
  );
}
