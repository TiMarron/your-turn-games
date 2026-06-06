"""The harness host page — a one-seat analogue of the platform's MatchShellView.

Loads the author's client in a sandboxed iframe (opaque origin), sends `init`
with the seat's stub match token (targetOrigin '*'), and accepts the client's
postMessages only from that iframe (origin 'null').
"""
from __future__ import annotations
import html


def host_page_html(title: str, seat: int, room: str) -> str:
    safe_title = html.escape(title)
    token = f"seat{seat}"
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{safe_title} — seat {seat}</title>
<style>
  body {{ font-family: system-ui, sans-serif; margin: 0; }}
  .bar {{ padding: 6px 12px; background: #eef; border-bottom: 1px solid #ccd;
          font-size: 13px; }}
  iframe {{ width: 100%; height: calc(100vh - 34px); border: 0; display: block; }}
  #ended {{ padding: 8px 12px; font-weight: 600; }}
</style></head>
<body>
  <div class="bar">Harness — {safe_title}, seat <b>{seat}</b> (token <code>{token}</code>).
    This is the local dev shell; the game runs in a sandboxed iframe.</div>
  <div id="ended"></div>
  <iframe id="game" sandbox="allow-scripts" src="/client/index.html"></iframe>
  <script>
    const iframe = document.getElementById("game");
    const INIT = {{ type: "init", token: "{token}", room_code: "{room}",
                    api_base: window.location.origin }};

    function sendInit() {{
      // Opaque-origin (sandboxed) iframe can't be named as a target -> '*'.
      iframe.contentWindow.postMessage(INIT, "*");
    }}

    window.addEventListener("message", (e) => {{
      // Accept only messages from OUR sandboxed iframe (opaque origin -> 'null').
      if (!(e.origin === "null" && e.source === iframe.contentWindow)) return;
      let data = e.data;
      if (typeof data === "string") {{ try {{ data = JSON.parse(data); }} catch {{ return; }} }}
      if (!data || typeof data !== "object") return;
      if (data.type === "ready") sendInit();
      else if (data.type === "game_ended")
        document.getElementById("ended").textContent =
          data.winner_seat === -1 ? "Draw" : ("Winner: seat " + data.winner_seat);
      else if (data.type === "navigate")
        document.getElementById("ended").textContent = "navigate -> " + data.path;
    }});

    // Fallback: if the client never says ready, init shortly after load.
    iframe.addEventListener("load", () => setTimeout(sendInit, 500));
  </script>
</body></html>"""
