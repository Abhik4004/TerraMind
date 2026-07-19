// src/App.jsx
import React from "react";
import { BrowserRouter as Router, Routes, Route } from "react-router-dom";
import Landing from "./pages/Landing";
import Signup from "./pages/Signup";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import LandAnalyze from "./pages/LandAnalyze";
import MapSelector from "./pages/MapSelector";
import WeatherAnalysis from "./pages/WeatherAnalyze";
import "./App.css";

function App() {
  return (
    <Router>
      <div className="container">
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/signup" element={<Signup />} />
          <Route path="/login" element={<Login />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/analyze" element={<LandAnalyze />} />
          <Route path="/map" element={<MapSelector />} />
          <Route path="/weather" element={<WeatherAnalysis />} />
        </Routes>
      </div>
    </Router>
  );
}

export default App;
