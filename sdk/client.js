// your-turn game client SDK (dependency-free ESM). Copy this file into your
// client bundle (e.g. client/sdk.js) and import { connect } from "./sdk.js".
//
// Same code runs in the dev harness and on the platform: it speaks the platform
// protocol — postMessage ready/init with the host, a WebSocket for live state,
// and HTTP POST for moves.

export function connect({ onState }) {
  // Resolves once the host sends `init`. Returns { cfg, sendAction }.
  return new Promise((resolve) => {
    let endedSent = false;

    window.addEventListener("message", (e) => {
      let d = e.data;
      if (typeof d === "string") { try { d = JSON.parse(d); } catch { return; } }
      if (!d || d.type !== "init") return;

      const cfg = { token: d.token, room_code: d.room_code, api_base: d.api_base };

      // Live updates over WebSocket (same-origin as api_base, http -> ws).
      const wsUrl = cfg.api_base.replace(/^http/, "ws") +
        `/api/ws/${cfg.room_code}?token=${encodeURIComponent(cfg.token)}`;
      const ws = new WebSocket(wsUrl);
      ws.addEventListener("message", (ev) => {
        let m;
        try { m = JSON.parse(ev.data); } catch { return; }
        if (m.type !== "game_state") return;
        if (typeof onState === "function") onState(m);
        // Tell the host the game finished (drives the platform's end overlay).
        if (m.phase === "finished" && !endedSent) {
          endedSent = true;
          window.parent.postMessage(JSON.stringify({
            type: "game_ended",
            winner_seat: m.winner === null ? -1 : m.winner,
          }), "*");
        }
      });

      // Send a move over HTTP; the resulting state arrives via the WS push above.
      const sendAction = (type, data = {}) =>
        fetch(`${cfg.api_base}/api/games/${cfg.room_code}/action`, {
          method: "POST",
          headers: { "Authorization": "Bearer " + cfg.token, "Content-Type": "application/json" },
          body: JSON.stringify({ type, data }),
        }).then((r) => {
          if (!r.ok) throw new Error("action failed: HTTP " + r.status);
          return r.json();
        });

      resolve({ cfg, sendAction, ws });
    });

    // Tell the host we're ready (targetOrigin '*' — sandboxed iframe is opaque-origin).
    window.parent.postMessage(JSON.stringify({ type: "ready" }), "*");
  });
}
