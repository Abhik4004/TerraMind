/**
 * Export utilities for TerraMind chat sessions.
 * No external dependencies — uses native browser APIs only.
 */

/** Download the session as a formatted JSON file. */
export function exportAsJSON(messages, sessionId) {
  const data = {
    session_id: sessionId,
    exported_at: new Date().toISOString(),
    message_count: messages.length,
    messages: messages.map((m) => ({
      role: m.role,
      content: m.content,
      timestamp: m.timestamp,
      tools_used: m.tools_used ?? [],
      from_cache: m.from_cache ?? false,
    })),
  };

  const blob = new Blob([JSON.stringify(data, null, 2)], {
    type: "application/json",
  });
  _download(blob, `terramind-${sessionId.slice(0, 8)}-${_dateStamp()}.json`);
}

/** Open a print-optimised window so the browser can save as PDF. */
export function exportAsPDF(messages, sessionId, locationInfo) {
  const html = _buildPrintHTML(messages, sessionId, locationInfo);
  const win = window.open("", "_blank");
  if (!win) {
    alert("Pop-up blocked — please allow pop-ups for this site to export PDF.");
    return;
  }
  win.document.write(html);
  win.document.close();
  win.focus();
  // Small delay so styles render before the dialog opens
  setTimeout(() => {
    win.print();
  }, 400);
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function _download(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

function _dateStamp() {
  return new Date().toISOString().slice(0, 10);
}

function _esc(str) {
  return String(str ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function _buildPrintHTML(messages, sessionId, locationInfo) {
  const locationLine = locationInfo
    ? `<p class="meta">Location: ${_esc(locationInfo.place_name)}</p>`
    : "";

  const msgHtml = messages
    .map((m) => {
      const role = m.role === "user" ? "You" : "TerraMind";
      const ts = m.timestamp
        ? new Date(m.timestamp).toLocaleString()
        : "";
      return `
        <div class="msg ${m.role}">
          <div class="msg-header">
            <strong>${role}</strong>
            ${ts ? `<span class="ts">${_esc(ts)}</span>` : ""}
          </div>
          <div class="msg-body">${_esc(m.content).replace(/\n/g, "<br>")}</div>
        </div>`;
    })
    .join("\n");

  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>TerraMind Session ${_esc(sessionId.slice(0, 8))}</title>
  <style>
    body { font-family: "Segoe UI", sans-serif; max-width: 800px; margin: 2rem auto; color: #1e293b; }
    h1 { font-size: 1.4rem; color: #1b5e20; margin-bottom: 0.25rem; }
    .meta { color: #64748b; font-size: 0.85rem; margin-bottom: 1.5rem; }
    .msg { margin-bottom: 1.25rem; padding: 0.75rem 1rem; border-radius: 8px; }
    .msg.user { background: #e3f2fd; border-left: 4px solid #1976d2; }
    .msg.assistant { background: #e8f5e9; border-left: 4px solid #2e7d32; }
    .msg-header { display: flex; justify-content: space-between; margin-bottom: 0.4rem; }
    .msg-header strong { font-size: 0.9rem; }
    .ts { color: #94a3b8; font-size: 0.78rem; }
    .msg-body { font-size: 0.93rem; line-height: 1.6; white-space: pre-wrap; }
    @media print { body { margin: 1rem; } }
  </style>
</head>
<body>
  <h1>🌍 TerraMind Analysis Session</h1>
  <p class="meta">Session ID: ${_esc(sessionId)} &nbsp;|&nbsp; Exported: ${new Date().toLocaleString()}</p>
  ${locationLine}
  ${msgHtml}
</body>
</html>`;
}
