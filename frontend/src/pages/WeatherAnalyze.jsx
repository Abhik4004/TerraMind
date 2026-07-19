import React, { useState, useRef, useEffect } from "react";
import MapSelector from "./MapSelector";
import ReasoningPanel from "../components/ReasoningPanel";
import { useNavigate } from "react-router-dom";

export default function WeatherAnalyze() {
  const navigate = useNavigate();
  const [coords, setCoords] = useState(null);
  const [query, setQuery] = useState("");
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const timerRef = useRef(null);

  useEffect(() => () => { if (timerRef.current) clearInterval(timerRef.current); }, []);

  const runDummy = () => {
    setLoading(true);
    setLogs([]);
    setResult(null);

    const steps = [
      "Validating input and coordinates",
      "Fetching recent weather baselines",
      "Estimating wind/precip patterns around selected point",
      "Synthesizing a concise answer",
    ];
    let i = 0;
    timerRef.current = setInterval(() => {
      setLogs((prev) => [...prev, steps[i]]);
      i++;
      if (i >= steps.length) {
        clearInterval(timerRef.current);
        setLoading(false);
        setResult({
          title: "Weather Summary (dummy)",
          text:
            `Query: "${query || "N/A"}"\n` +
            `Point: ${coords ? `${coords.lat.toFixed(4)}, ${coords.lng.toFixed(4)}` : "not selected"}\n` +
            "Answer: Expect mild conditions with intermittent clouds (placeholder).",
        });
      }
    }, 600);
  };

  const handleRun = () => {
    if (!coords) {
      alert("Please select a location on the map.");
      return;
    }
    runDummy();
  };

  return (
    <div style={styles.page}>
      <div style={styles.header}>
        <button onClick={() => navigate("/dashboard")} style={styles.backBtn}>← Back</button>
        <h2 style={{ margin: 0 }}>🌦 Weather Analysis</h2>
      </div>

      <div style={styles.grid}>
        <div style={styles.left}>
          <div style={styles.card}>
            <h3 style={styles.h3}>Select Location</h3>
            <MapSelector selected={coords} onSelect={setCoords} height="380px" />
            <div style={styles.coordRow}>
              <div><b>Lat:</b> {coords ? coords.lat.toFixed(5) : "-"}</div>
              <div><b>Lng:</b> {coords ? coords.lng.toFixed(5) : "-"}</div>
            </div>
          </div>

          <div style={styles.card}>
            <h3 style={styles.h3}>Your Query</h3>
            <textarea
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="e.g., Give me a 24h weather outlook for construction planning"
              style={styles.textarea}
            />
            <button onClick={handleRun} style={styles.runBtn}>
              ▶ Run analysis
            </button>
          </div>
        </div>

        <div style={styles.right}>
          <div style={styles.card}>
            <h3 style={styles.h3}>Result</h3>
            {!result && <div style={styles.dim}>No result yet. Run an analysis to see output.</div>}
            {result && (
              <pre style={styles.pre}>
{result.title}

{result.text}
              </pre>
            )}
          </div>

          <ReasoningPanel logs={logs} loading={loading} onClear={() => setLogs([])} />
        </div>
      </div>
    </div>
  );
}

const styles = {
  page: { padding: 20 },
  header: { display: "flex", alignItems: "center", gap: 12, marginBottom: 16 },
  backBtn: {
    border: "1px solid #ddd", borderRadius: 8, padding: "6px 10px", background: "#fff", cursor: "pointer",
  },
  grid: { display: "grid", gridTemplateColumns: "1.1fr 0.9fr", gap: 20 },
  left: { display: "grid", gap: 20 },
  right: { display: "grid", gap: 20 },
  card: { background: "#fff", border: "1px solid #eee", borderRadius: 12, padding: 16, boxShadow: "0 2px 8px rgba(0,0,0,0.04)" },
  h3: { marginTop: 0, marginBottom: 12 },
  coordRow: { display: "flex", gap: 16, marginTop: 12, color: "#444" },
  textarea: {
    width: "100%", minHeight: 110, borderRadius: 10, border: "1px solid #ddd", padding: 12, outline: "none",
    fontFamily: "inherit", resize: "vertical",
  },
  runBtn: {
    marginTop: 10, padding: "10px 16px", borderRadius: 10, border: "none",
    background: "#2563eb", color: "#fff", cursor: "pointer", fontWeight: 600,
  },
  dim: { color: "#888" },
  pre: {
    background: "#f7f7f7", border: "1px solid #eee", borderRadius: 10, padding: 12,
    whiteSpace: "pre-wrap", wordWrap: "break-word",
  },
};
