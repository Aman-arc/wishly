import { Routes, Route } from "react-router-dom";
import CreateWish from "./pages/CreateWish.jsx";
import ViewWish from "./pages/ViewWish.jsx";
import ManageWish from "./pages/ManageWish.jsx";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<CreateWish />} />
      <Route path="/wish/:id" element={<ViewWish />} />
      <Route path="/wish/:id/manage" element={<ManageWish />} />
    </Routes>
  );
}
