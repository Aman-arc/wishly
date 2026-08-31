import { useEffect, useState, useRef } from "react";
import { useParams } from "react-router-dom";
import api, { mediaUrl, API_BASE } from "../api.js";
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

        <a className="save-btn" href={`${API_BASE}/api/wishes/${id}/download`}>
          💾 Save this wish
        </a>
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
