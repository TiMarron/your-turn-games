// your-turn game client SDK (dependency-free ESM). Copy this file into your
// client bundle (e.g. client/sdk.js) and import { connect } from "./sdk.js".
//
// Same code runs in the dev harness and on the platform: it speaks the platform
// protocol — postMessage ready/init with the host, a WebSocket for live state,
// and HTTP POST for moves.
//
// Replay: the host can step through past positions of the game. It sends
// `replay_state` (show this snapshot, read-only) and later `replay_exit`. The
// SDK calls onState(snapshot, { replay: true }) for a past position, holds live
// updates meanwhile, and on exit calls onState(newest live, { replay: false }).
// While replaying, sendAction rejects and `game.replay` is true — hide your
// move controls. Pass { replay: false } to connect() to opt out.

export function connect({ onState, replay: replaySupported = true }) {
  // Resolves once the host sends `init`. Returns { cfg, sendAction, ws, replay }.
  return new Promise((resolve) => {
    let endedSent = false;
    let initialized = false;
    let replay = false;     // showing a past position
    let live = null;        // newest live snapshot

    const show = (snap, isReplay) => {
      if (typeof onState === "function") onState(snap, { replay: isReplay });
    };

    // Tell the host the game finished (drives the platform's end overlay).
    // Not for a past position: only live states, and only once.
    const reportEnd = (m) => {
      if (m.phase !== "finished" || endedSent) return;
      endedSent = true;
      window.parent.postMessage(JSON.stringify({
        type: "game_ended",
        winner_seat: m.winner === null ? -1 : m.winner,
      }), "*");
    };

    window.addEventListener("message", (e) => {
      let d = e.data;
      if (typeof d === "string") { try { d = JSON.parse(d); } catch { return; } }
      if (!d) return;
      if (replaySupported && d.type === "replay_state" && d.state) {
        replay = true;
        show(d.state, true);
        return;
      }
      if (replaySupported && d.type === "replay_exit") {
        if (!replay) return;
        replay = false;
        if (live) { show(live, false); reportEnd(live); }
        return;
      }
      if (d.type !== "init") return;
      if (initialized) return;   // host may send init more than once (ready + load fallback)
      initialized = true;

      const cfg = { token: d.token, room_code: d.room_code, api_base: d.api_base };

      // Live updates over WebSocket (same-origin as api_base, http -> ws).
      const wsUrl = cfg.api_base.replace(/^http/, "ws") +
        `/api/ws/${cfg.room_code}?token=${encodeURIComponent(cfg.token)}`;
      const ws = new WebSocket(wsUrl);
      ws.addEventListener("message", (ev) => {
        let m;
        try { m = JSON.parse(ev.data); } catch { return; }
        if (m.type !== "game_state") return;
        live = m;
        if (replay) return;       // shown when the host ends the replay
        show(m, false);
        reportEnd(m);
      });

      // Send a move over HTTP; the resulting state arrives via the WS push above.
      const sendAction = (type, data = {}) => replay
        ? Promise.reject(new Error("replay mode"))
        : fetch(`${cfg.api_base}/api/games/${cfg.room_code}/action`, {
          method: "POST",
          headers: { "Authorization": "Bearer " + cfg.token, "Content-Type": "application/json" },
          body: JSON.stringify({ type, data }),
        }).then((r) => {
          if (!r.ok) throw new Error("action failed: HTTP " + r.status);
          return r.json();
        });

      resolve({ cfg, sendAction, ws, get replay() { return replay; } });
    });

    // Tell the host we're ready (targetOrigin '*' — sandboxed iframe is opaque-origin).
    const ready = replaySupported ? { type: "ready", features: ["replay"] } : { type: "ready" };
    window.parent.postMessage(JSON.stringify(ready), "*");
  });
}
