// Live backend (Render free tier sleeps; the first request wakes it in ~1 min).
// Recorded runs are static files and need no backend.
export const API_URL = (import.meta.env.VITE_API_URL || "").replace(/\/$/, "");

export async function loadJSON(path) {
  const response = await fetch(path);
  if (!response.ok) throw new Error(`${path}: ${response.status}`);
  return response.json();
}

export async function health(signal) {
  const response = await fetch(`${API_URL}/api/health`, { signal });
  if (!response.ok) throw new Error(`health ${response.status}`);
  return response.json();
}

async function errorMessage(response) {
  try {
    const body = await response.json();
    return body.detail || `Server error ${response.status}`;
  } catch {
    return `Server error ${response.status}`;
  }
}

// POST /api/run streams one JSON object per line: {side, type, data}
export async function runLive({ scenario, customAttack, signal, onEvent }) {
  const response = await fetch(`${API_URL}/api/run`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ scenario, custom_attack: customAttack || null }),
    signal,
  });

  if (!response.ok) throw new Error(await errorMessage(response));

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  const started = performance.now();
  let buffer = "";

  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let newline;
    while ((newline = buffer.indexOf("\n")) >= 0) {
      const line = buffer.slice(0, newline).trim();
      buffer = buffer.slice(newline + 1);
      if (line) onEvent({ ...JSON.parse(line), t: Math.round(performance.now() - started) });
    }
  }
}

export async function checkText(text) {
  const response = await fetch(`${API_URL}/api/check`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ text }),
  });

  if (!response.ok) throw new Error(await errorMessage(response));
  return response.json();
}
