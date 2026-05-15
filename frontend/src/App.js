import "@/App.css";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import LandingPage from "./pages/LandingPage";
import MediaKit from "./pages/MediaKit";

function App() {
  return (
    <div className="App">
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/kit" element={<MediaKit />} />
        </Routes>
      </BrowserRouter>
    </div>
  );
}

export default App;
