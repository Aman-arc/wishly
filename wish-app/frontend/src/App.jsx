import { Routes, Route } from "react-router-dom";
import CreateWish from "./pages/CreateWish.jsx";
import ViewWish from "./pages/ViewWish.jsx";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<CreateWish />} />
      <Route path="/wish/:id" element={<ViewWish />} />
    </Routes>
  );
}
