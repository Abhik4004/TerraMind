import React from "react";

export default function ReasoningPanel({
  logs = [],
  loading = false,
  onClear,
}) {
  return (
    <div style={styles.box}>
      <div style={styles.header}>
        <span>🧠 Model reasoning (concise)</span>
        <div>
          <button onClick={onClear} style={styles.btnSm}>
            Clear
          </button>
        </div>
      </div>
      <div style={styles.content}>
        {loading && <div style={styles.dim}>Running analysis…</div>}
        {!loading && logs.length === 0 && (
          <div style={styles.dim}>
            No reasoning yet. Run an analysis to see steps.
          </div>
        )}
        {logs.map((line, i) => (
          <div key={i} style={styles.line}>
            • {line}
          </div>
        ))}
      </div>
    </div>
  );
}

const styles = {
  box: {
    background: "#fafafa",
    borderRadius: 12,
    border: "1px solid #eee",
    padding: 16,
  },
  header: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    fontWeight: 600,
    marginBottom: 8,
  },
  content: {
    fontFamily:
      "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
    fontSize: 13,
    lineHeight: 1.5,
    maxHeight: 200,
    overflow: "auto",
  },
  dim: { color: "#888" },
  line: { marginBottom: 6 },
  btnSm: {
    border: "1px solid #ddd",
    borderRadius: 8,
    padding: "4px 10px",
    background: "#fff",
    cursor: "pointer",
  },
};
