import axios from "axios";

// In development this is left empty and Vite's proxy (see vite.config.js)
// forwards /api and /uploads to the local Flask server.
//
// In production, set VITE_API_URL to your deployed backend's URL, e.g.
//   VITE_API_URL=https://wishly-backend.onrender.com
// (Vercel/Netlify: add this as an environment variable in the project settings.)
export const API_BASE = import.meta.env.VITE_API_URL || "";

const api = axios.create({
  baseURL: API_BASE,
});

// Turns a relative media path returned by the API (e.g. "/uploads/abc/x.jpg")
// into a full URL that works no matter which domain the frontend is on.
export function mediaUrl(path) {
  if (!path) return path;
  if (path.startsWith("http")) return path;
  return `${API_BASE}${path}`;
}

export default api;
