import { useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import api from "../api.js";

export default function ManageWish() {
  const { id } = useParams();
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token");

  const [status, setStatus] = useState("idle"); // idle | confirming | deleting | deleted | error
  const [errorMsg, setErrorMsg] = useState("");

  async function handleDelete() {
    setStatus("deleting");
    try {
      await api.delete(`/api/wishes/${id}`, { params: { token } });
      setStatus("deleted");
    } catch (err) {
      setErrorMsg(
        err?.response?.data?.error || "Couldn't delete this wish. The link may be invalid or already used."
      );
      setStatus("error");
    }
  }

  if (!token) {
    return (
      <div className="page view-page not-found">
        <div className="not-found-card">
          <span style={{ fontSize: "3rem" }}>🔒</span>
          <h2>Missing delete link</h2>
          <p>This page needs the private delete link shown when the wish was created.</p>
        </div>
      </div>
    );
  }

  if (status === "deleted") {
    return (
      <div className="page view-page not-found">
        <div className="not-found-card">
          <span style={{ fontSize: "3rem" }}>🗑️</span>
          <h2>Wish deleted</h2>
          <p>This wish and its photos/videos have been permanently removed.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="page view-page not-found">
      <div className="not-found-card">
        <span style={{ fontSize: "3rem" }}>⚙️</span>
        <h2>Manage this wish</h2>
        <p style={{ marginBottom: 20 }}>
          Deleting it removes the wish, its message, and any photos/videos permanently — the
          share link will stop working immediately.
        </p>

        {status !== "confirming" ? (
          <button className="submit-btn" style={{ background: "#e63946" }} onClick={() => setStatus("confirming")}>
            Delete this wish
          </button>
        ) : (
          <>
            <p style={{ fontWeight: 600, marginBottom: 12 }}>Are you sure? This can't be undone.</p>
            <div className="result-actions">
              <button
                className="submit-btn"
                style={{ background: "#e63946" }}
                onClick={handleDelete}
                disabled={status === "deleting"}
              >
                {status === "deleting" ? "Deleting..." : "Yes, delete permanently"}
              </button>
              <button className="secondary-btn" onClick={() => setStatus("idle")}>
                Cancel
              </button>
            </div>
          </>
        )}

        {status === "error" && <p className="error-text" style={{ marginTop: 16 }}>{errorMsg}</p>}
      </div>
    </div>
  );
}
