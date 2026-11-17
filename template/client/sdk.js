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
//
// Reconnect: the WebSocket comes back by itself after a drop (growing pause
// 1 s → 30 s with jitter, reset only once a message arrives), at once when the
// tab is visible again or the network returns, and after 75 s of silence (the
// server pings idle sockets every 30 s). Close codes 4001/4003/4004 are final:
// it stops for good. Every connection starts with a fresh game_state, so missed
// moves arrive through onState as usual. Don't open your own WebSocket next to
// the SDK; read `game.ws` each time you need the socket (it changes on reconnect).

const RECONNECT_MIN_MS = 1000;
const RECONNECT_MAX_MS = 30000;
const SILENCE_LIMIT_MS = 75000;
const FINAL_CLOSE_CODES = [4001, 4003, 4004];   // bad token / not a player / no room

// Keep one live socket open to `url`, reconnecting as described above.
function liveSocket(url, onMessage) {
  let ws = null;
  let stopped = false;   // the server refused for good
  let delay = RECONNECT_MIN_MS;
  let retryTimer = null;
  let watchdogTimer = null;

  const clearTimers = () => {
    clearTimeout(retryTimer); clearTimeout(watchdogTimer);
    retryTimer = watchdogTimer = null;
  };
  const armWatchdog = () => {
    clearTimeout(watchdogTimer);
    watchdogTimer = setTimeout(reconnectNow, SILENCE_LIMIT_MS);
  };
  const drop = () => {
    clearTimers();
    const sock = ws;
    ws = null;
    if (sock) {
      sock.onopen = sock.onmessage = sock.onclose = sock.onerror = null;
      try { sock.close(); } catch { /* already closed */ }
    }
  };
  function open() {
    if (stopped) return;
    drop();
    const sock = new WebSocket(url);
    ws = sock;
    armWatchdog();          // also bounds a handshake hanging on a half-dead network
    sock.onopen = () => { armWatchdog(); };
    sock.onmessage = (ev) => {
      delay = RECONNECT_MIN_MS;
      armWatchdog();
      let m;
      try { m = JSON.parse(ev.data); } catch { return; }
      if (m && m.type !== "ping") onMessage(m);
    };
    sock.onclose = (ev) => {
      if (ws !== sock) return;
      ws = null;
      clearTimers();
      if (FINAL_CLOSE_CODES.includes(ev.code)) { stopped = true; return; }
      retryTimer = setTimeout(open, delay * (0.8 + Math.random() * 0.4));
      delay = Math.min(delay * 2, RECONNECT_MAX_MS);
    };
  }
  function reconnectNow() { if (stopped) return; delay = RECONNECT_MIN_MS; open(); }
  const isDown = () => !ws || ws.readyState === WebSocket.CLOSING || ws.readyState === WebSocket.CLOSED;
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible" && isDown()) reconnectNow();
  });
  window.addEventListener("online", () => { if (isDown()) reconnectNow(); });
  open();
  return { get socket() { return ws; } };
}

export function connect({ onState, replay: replaySupported = true }) {
  // Resolves once the host sends `init`. Returns { cfg, sendAction, ws, replay }
  // (`ws` is the current socket; it is replaced on every reconnect).
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

      // Live updates over WebSocket (same-origin as api_base, http -> ws),
      // reconnecting by itself after a drop.
      const wsUrl = cfg.api_base.replace(/^http/, "ws") +
        `/api/ws/${cfg.room_code}?token=${encodeURIComponent(cfg.token)}`;
      const sock = liveSocket(wsUrl, (m) => {
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

      resolve({ cfg, sendAction, get ws() { return sock.socket; }, get replay() { return replay; } });
    });

    // Tell the host we're ready (targetOrigin '*' — sandboxed iframe is opaque-origin).
    const ready = replaySupported ? { type: "ready", features: ["replay"] } : { type: "ready" };
    window.parent.postMessage(JSON.stringify(ready), "*");
  });
}
