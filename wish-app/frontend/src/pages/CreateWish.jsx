import { useState } from "react";
import api from "../api.js";

const OCCASIONS = [
  { value: "birthday", label: "🎂 Birthday", color: "#ff6b9d" },
  { value: "anniversary", label: "💍 Anniversary", color: "#c77dff" },
  { value: "congratulations", label: "🎉 Congratulations", color: "#ffb703" },
  { value: "wedding", label: "💐 Wedding", color: "#ff8fab" },
  { value: "graduation", label: "🎓 Graduation", color: "#4361ee" },
  { value: "farewell", label: "👋 Farewell", color: "#4cc9f0" },
  { value: "getwellsoon", label: "💐 Get Well Soon", color: "#80ed99" },
  { value: "newborn", label: "👶 New Baby", color: "#ffc6ff" },
  { value: "other", label: "✨ Something Else", color: "#8d99ae" },
];

export default function CreateWish() {
  const [occasion, setOccasion] = useState("birthday");
  const [title, setTitle] = useState("");
  const [message, setMessage] = useState("");
  const [sender, setSender] = useState("");
  const [recipient, setRecipient] = useState("");
  const [photos, setPhotos] = useState([]);
  const [videos, setVideos] = useState([]);
  const [loading, setLoading] = useState(false);
  const [shareLink, setShareLink] = useState(null);
  const [manageLink, setManageLink] = useState(null);
  const [expiresAt, setExpiresAt] = useState(null);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);

  const activeOccasion = OCCASIONS.find((o) => o.value === occasion);

  async function handleSubmit(e) {
    e.preventDefault();
    setLoading(true);
    setError("");

    try {
      const formData = new FormData();
      formData.append("occasion", occasion);
      formData.append("title", title);
      formData.append("message", message);
      formData.append("sender", sender);
      formData.append("recipient", recipient);
      formData.append("themeColor", activeOccasion.color);
      photos.forEach((f) => formData.append("photos", f));
      videos.forEach((f) => formData.append("videos", f));

      const res = await api.post("/api/wishes", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });

      const link = `${window.location.origin}/wish/${res.data.id}`;
      setShareLink(link);
      setManageLink(`${window.location.origin}/wish/${res.data.id}/manage?token=${res.data.deleteToken}`);
      setExpiresAt(res.data.expiresAt);
    } catch (err) {
      setError("Something went wrong while creating your wish. Please try again.");
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  function copyLink() {
    navigator.clipboard.writeText(shareLink);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  function resetForm() {
    setShareLink(null);
    setManageLink(null);
    setExpiresAt(null);
    setTitle("");
    setMessage("");
    setSender("");
    setRecipient("");
    setPhotos([]);
    setVideos([]);
  }

  function formatExpiry(iso) {
    if (!iso) return null;
    const d = new Date(iso);
    return d.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
  }

  return (
    <div className="page create-page" style={{ "--accent": activeOccasion.color }}>
      <div className="create-card">
        <div className="brand">
          <span className="brand-icon">🎁</span>
          <h1>Wishly</h1>
        </div>
        <p className="subtitle">Create a beautiful wish and share it with a link</p>

        {!shareLink ? (
          <form onSubmit={handleSubmit} className="wish-form">
            <label className="field-label">Occasion</label>
            <div className="occasion-grid">
              {OCCASIONS.map((o) => (
                <button
                  type="button"
                  key={o.value}
                  className={`occasion-chip ${occasion === o.value ? "active" : ""}`}
                  style={{ "--chip-color": o.color }}
                  onClick={() => setOccasion(o.value)}
                >
                  {o.label}
                </button>
              ))}
            </div>

            <div className="field-row">
              <div className="field">
                <label className="field-label">To (recipient's name)</label>
                <input
                  type="text"
                  placeholder="e.g. Priya"
                  value={recipient}
                  onChange={(e) => setRecipient(e.target.value)}
                />
              </div>
              <div className="field">
                <label className="field-label">From (your name)</label>
                <input
                  type="text"
                  placeholder="e.g. Rahul"
                  value={sender}
                  onChange={(e) => setSender(e.target.value)}
                />
              </div>
            </div>

            <div className="field">
              <label className="field-label">Title (optional)</label>
              <input
                type="text"
                placeholder={`Default: "${
                  OCCASIONS.find((o) => o.value === occasion).label.replace(/^\S+\s/, "")
                }!"`}
                value={title}
                onChange={(e) => setTitle(e.target.value)}
              />
            </div>

            <div className="field">
              <label className="field-label">Message (optional — a lovely default is used if left blank)</label>
              <textarea
                rows={4}
                placeholder="Write your heartfelt message here..."
                value={message}
                onChange={(e) => setMessage(e.target.value)}
              />
            </div>

            <div className="field-row">
              <div className="field">
                <label className="field-label">Photos (optional)</label>
                <label className="upload-box">
                  📷 {photos.length > 0 ? `${photos.length} photo(s) selected` : "Choose photos"}
                  <input
                    type="file"
                    accept="image/*"
                    multiple
                    hidden
                    onChange={(e) => setPhotos(Array.from(e.target.files))}
                  />
                </label>
              </div>
              <div className="field">
                <label className="field-label">Videos (optional)</label>
                <label className="upload-box">
                  🎬 {videos.length > 0 ? `${videos.length} video(s) selected` : "Choose videos"}
                  <input
                    type="file"
                    accept="video/*"
                    multiple
                    hidden
                    onChange={(e) => setVideos(Array.from(e.target.files))}
                  />
                </label>
              </div>
            </div>

            {error && <p className="error-text">{error}</p>}

            <button type="submit" className="submit-btn" disabled={loading}>
              {loading ? "Creating your wish..." : "✨ Create & Get Shareable Link"}
            </button>
          </form>
        ) : (
          <div className="link-result">
            <div className="success-icon">🎉</div>
            <h2>Your wish is ready!</h2>
            <p>Share this link with anyone — it opens beautifully on any device.</p>
            <div className="link-box">
              <input type="text" readOnly value={shareLink} />
              <button onClick={copyLink}>{copied ? "Copied!" : "Copy"}</button>
            </div>
            {expiresAt && (
              <p className="expiry-note">
                ⏳ This wish auto-deletes on <strong>{formatExpiry(expiresAt)}</strong>
              </p>
            )}
            {manageLink && (
              <p className="manage-note">
                Want to delete it sooner? Save this private link:{" "}
                <a href={manageLink}>{manageLink}</a>
                <br />
                <span className="manage-warning">This link is shown only once — save it now if you might need it.</span>
              </p>
            )}
            <div className="result-actions">
              <a href={shareLink} target="_blank" rel="noreferrer" className="preview-btn">
                Preview Wish →
              </a>
              <button className="secondary-btn" onClick={resetForm}>
                Create Another
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
