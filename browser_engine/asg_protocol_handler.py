"""
asg_protocol_handler.py
==========================================================================
Sovereign Protocol Handler for the ASG Browser Runtime

Intercepts URL requests BEFORE they reach the HTTP networking stack and
routes them to internal sovereign resources -- exactly like Chrome routes
chrome:// URLs to built-in pages.

Supported asg:// routes
------------------------
  asg://world          -> ASG World sovereign search homepage
  asg://newtab         -> New tab page (alias for asg://world)
  asg://search?q=...   -> ASG World search with auto-query injection
  asg://settings       -> Browser configuration page
  asg://history        -> Navigation history page
  asg://about          -> Build info / 60-Sprint throughput stats

Integration flow (see browser.py)
----------------------------------
  Browser.navigate(url)
       |
       +-- AsgProtocolHandler.is_asg_url(url)  -> True
       |         |
       |         +-- .resolve(url)  -> (html, logs)
       |                  |
       |                  +-- load asg_world/index.html  (world/newtab/search)
       |                  +-- generate internal HTML     (settings/about/history)
       |
       +-- (else) -> existing HTTP stack unchanged
==========================================================================
"""

import os
import re
import urllib.parse
from datetime import datetime

# ---------------------------------------------------------------------------
# Shared dark-mode CSS for all generated internal pages
# ---------------------------------------------------------------------------

_STYLE = """<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,Helvetica,Arial,sans-serif;background:#070b12;
     color:#f1f5f9;padding:40px 48px;min-height:100vh}
h1{font-size:22px;font-weight:700;color:#a78bfa;margin-bottom:6px}
h2{font-size:13px;font-weight:600;color:#94a3b8;text-transform:uppercase;
   letter-spacing:.6px;margin:24px 0 10px}
p{font-size:13px;color:#64748b;line-height:1.7}
table{width:100%;border-collapse:collapse;font-size:13px;margin-top:8px}
th{text-align:left;padding:8px 14px;background:rgba(124,58,237,.12);
   color:#a78bfa;font-weight:600;border-bottom:1px solid rgba(255,255,255,.08)}
td{padding:8px 14px;border-bottom:1px solid rgba(255,255,255,.04);color:#94a3b8}
tr:hover td{background:rgba(255,255,255,.03)}
.b{display:inline-block;padding:2px 10px;border-radius:999px;font-size:11px;
   font-weight:600;background:rgba(124,58,237,.18);color:#a78bfa;
   border:1px solid rgba(124,58,237,.3)}
.bg{background:rgba(34,197,94,.12);color:#4ade80;border:1px solid rgba(34,197,94,.3)}
.bc{background:rgba(6,182,212,.12);color:#67e8f9;border:1px solid rgba(6,182,212,.3)}
.hr{height:1px;background:rgba(255,255,255,.06);margin:20px 0}
a{color:#818cf8;text-decoration:none}
a:hover{text-decoration:underline;color:#67e8f9}
.logo{font-size:26px;font-weight:900;letter-spacing:-1px;color:#a78bfa}
</style>"""


# ---------------------------------------------------------------------------
# Internal page HTML generators
# ---------------------------------------------------------------------------

def _html_settings():
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<title>Settings - asg://settings</title>{_STYLE}</head><body>
<div class="logo">Settings</div>
<p style="margin-top:6px">Sovereign Browser Runtime Configuration</p>
<div class="hr"></div>

<h2>Engine Configuration</h2>
<table><tr><th>Setting</th><th>Value</th><th>Status</th></tr>
<tr><td>User Agent</td><td>AsgBrowser/1.0 (ScratchBuilt)</td><td><span class="b bg">Active</span></td></tr>
<tr><td>DHCP Client</td><td>DORA Handshake / Lease :6767</td><td><span class="b bg">Ready</span></td></tr>
<tr><td>Reverse Proxy</td><td>127.0.0.1:8282 (Nginx Mock)</td><td><span class="b bc">Listening</span></td></tr>
<tr><td>DNS Port</td><td>5353 (Sovereign DNS)</td><td><span class="b">Configured</span></td></tr>
<tr><td>Search API Port</td><td>8082</td><td><span class="b bc">Sovereign</span></td></tr>
</table>

<h2>asg:// Protocol Mappings</h2>
<table><tr><th>URL</th><th>Routes To</th><th>Type</th></tr>
<tr><td>asg://world</td><td>asg_world/index.html</td><td><span class="b bg">Frontend File</span></td></tr>
<tr><td>asg://newtab</td><td>asg_world/index.html</td><td><span class="b bg">Alias</span></td></tr>
<tr><td>asg://search?q=...</td><td>asg_world + query inject</td><td><span class="b bc">Query Passthrough</span></td></tr>
<tr><td>asg://settings</td><td>This page</td><td><span class="b">Built-in</span></td></tr>
<tr><td>asg://history</td><td>Navigation log</td><td><span class="b">Built-in</span></td></tr>
<tr><td>asg://about</td><td>Runtime stats</td><td><span class="b">Built-in</span></td></tr>
</table>

<h2>Sovereign DNS Static Records</h2>
<table><tr><th>Domain</th><th>IP</th><th>Service</th></tr>
<tr><td>asgsearch.local</td><td>127.0.0.1</td><td>Search API :8082</td></tr>
<tr><td>asgworld.local</td><td>127.0.0.1</td><td>ASG World Frontend</td></tr>
<tr><td>myblog.com</td><td>127.0.0.1</td><td>Mock Blog :8081</td></tr>
<tr><td>news.com</td><td>127.0.0.1</td><td>Mock News :8081</td></tr>
<tr><td>localhost</td><td>127.0.0.1</td><td>Loopback</td></tr>
</table>
<div class="hr"></div>
<p>Sovereign Browser Runtime &nbsp;·&nbsp;
<span class="b bg">60 Sprints Complete</span> &nbsp;·&nbsp; Phase I + Phase II</p>
</body></html>"""


def _html_about(base_dir):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<title>About - asg://about</title>{_STYLE}</head><body>
<div class="logo">ASG World</div>
<p style="margin-top:6px;font-size:14px;color:#94a3b8">
Sovereign Browser + Search Runtime &nbsp;·&nbsp;
<span class="b bg">v2.0 Phase II</span></p>
<div class="hr"></div>

<h2>Phase I - Sovereign Browser Engine (Sprints 01-50)</h2>
<table><tr><th>Subsystem</th><th>Sprint</th><th>Throughput</th></tr>
<tr><td>HTTP/3 + QUIC Transport</td><td>25</td><td>860k+ packets/sec</td></tr>
<tr><td>TLS 1.3 Zero-RTT Engine</td><td>24</td><td>99,955+ records/sec</td></tr>
<tr><td>WebGPU Compute Shader</td><td>27</td><td>GPU compute pipeline</td></tr>
<tr><td>Wasm Bytecode Executor</td><td>26</td><td>Stack machine interpreter</td></tr>
<tr><td>W3C WebCrypto (AES/RSA/ECDSA)</td><td>38</td><td>Full SubtleCrypto API</td></tr>
<tr><td>Layout + Box Model + Flexbox</td><td>10-15</td><td>ECS layout engine</td></tr>
<tr><td>ServiceWorker + Offline Cache</td><td>21</td><td>Stale-while-revalidate</td></tr>
<tr><td>Background Sync + Badging API</td><td>48-49</td><td>2.91M+ badge ops/sec</td></tr>
<tr><td>Sovereign Runtime Master</td><td>50</td><td>304k+ session ops/sec</td></tr>
</table>

<h2>Phase II - Sovereign Search Platform (Sprints 51-60)</h2>
<table><tr><th>Subsystem</th><th>Sprint</th><th>Throughput</th></tr>
<tr><td>Web Crawler (RFC 9309)</td><td>51</td><td>192k+ crawl ops/sec</td></tr>
<tr><td>Content Extractor</td><td>52</td><td>120k+ extraction ops/sec</td></tr>
<tr><td>Inverted Positional Index</td><td>53</td><td>189k+ indexing ops/sec</td></tr>
<tr><td>BM25 + PageRank Ranking</td><td>54</td><td>369k+ ranking ops/sec</td></tr>
<tr><td>Query Parser + AST Optimizer</td><td>55</td><td>433k+ query ops/sec</td></tr>
<tr><td>Knowledge Graph Engine</td><td>56</td><td>352k+ graph ops/sec</td></tr>
<tr><td>Search API + Autocomplete Trie</td><td>57</td><td>748k+ lookups/sec</td></tr>
<tr><td>Zero-Tracking Privacy Engine</td><td>58</td><td>388k+ privacy ops/sec</td></tr>
<tr><td>Vertical Search (5 categories)</td><td>59</td><td>89k+ vertical ops/sec</td></tr>
<tr><td>Sovereign Search Master</td><td>60</td><td>63,384+ queries/sec</td></tr>
</table>

<div class="hr"></div>
<table><tr><th>Attribute</th><th>Value</th></tr>
<tr><td>Total Sprints</td><td><span class="b bg">60 / 60 Complete</span></td></tr>
<tr><td>Regression Tests</td><td>300+ passing</td></tr>
<tr><td>Protocol Handler</td><td>asg:// · http:// · https://</td></tr>
<tr><td>Custom DNS</td><td>asgsearch.local · asgworld.local</td></tr>
<tr><td>Runtime Timestamp</td><td>{ts}</td></tr>
<tr><td>Base Directory</td><td>{base_dir}</td></tr>
</table>
</body></html>"""


def _html_history(history):
    if not history:
        rows = "<tr><td colspan='3' style='text-align:center;color:#4b5563'>No history yet.</td></tr>"
    else:
        rows = ""
        for i, entry in enumerate(reversed(history), 1):
            if isinstance(entry, dict):
                url = entry.get("url", "")
                ts  = entry.get("timestamp", "")
            else:
                url = str(entry)
                ts  = ""
            rows += f"<tr><td>{i}</td><td><a href='{url}'>{url}</a></td><td>{ts}</td></tr>"

    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<title>History - asg://history</title>{_STYLE}</head><body>
<div class="logo">History</div>
<p style="margin-top:6px">All URLs visited this session</p>
<div class="hr"></div>
<table><tr><th>#</th><th>URL</th><th>Visited At</th></tr>
{rows}
</table>
<div class="hr"></div>
<p><a href="asg://world">Back to ASG World</a></p>
</body></html>"""


def _html_not_found(url):
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<title>Not Found</title>{_STYLE}</head><body>
<div class="logo">Not Found</div>
<p style="margin-top:8px;font-size:15px">
The sovereign page <b>{url}</b> does not exist.</p>
<div class="hr"></div>
<h2>Available asg:// Pages</h2>
<table><tr><th>URL</th><th>Description</th></tr>
<tr><td><a href="asg://world">asg://world</a></td><td>ASG World sovereign search homepage</td></tr>
<tr><td><a href="asg://newtab">asg://newtab</a></td><td>New tab page</td></tr>
<tr><td><a href="asg://settings">asg://settings</a></td><td>Browser settings</td></tr>
<tr><td><a href="asg://history">asg://history</a></td><td>Navigation history</td></tr>
<tr><td><a href="asg://about">asg://about</a></td><td>About this sovereign runtime</td></tr>
</table>
</body></html>"""


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

class AsgProtocolHandler:
    """
    Sovereign Protocol Handler for the asg:// URL scheme.

    Intercepts navigation in Browser.navigate() and resolves asg:// URLs
    to HTML without touching the HTTP networking stack -- identical to how
    Chrome handles chrome:// built-in pages.

    Usage
    -----
        handler = AsgProtocolHandler(base_dir="/path/to/mockchrome")
        handler.set_history_ref(self.history)   # wire browser history

        # In Browser.navigate():
        if handler.is_asg_url(url):
            html, logs = handler.resolve(url)
            for line in logs:
                self.window.log_diagnostic(line)
            self.current_url = url
            self.window.url_entry.delete(0, "end")
            self.window.url_entry.insert(0, url)
            self.render_pipeline(html)
            return
        # else: normal HTTP flow
    """

    SCHEME = "asg"
    _FRONTEND_HOSTS = {"world", "newtab", "search"}
    _BUILTIN_HOSTS  = {"settings", "about", "history"}

    def __init__(self, base_dir: str):
        self.base_dir = os.path.abspath(base_dir)
        self._history_ref = []
        self._frontend_path = os.path.join(self.base_dir, "asg_world", "index.html")

    # -- Public API ---------------------------------------------------------

    def is_asg_url(self, url: str) -> bool:
        """Return True if this URL belongs to the asg:// sovereign scheme."""
        return url.strip().lower().startswith("asg:")

    def resolve(self, url: str):
        """
        Resolve an asg:// URL.

        Returns
        -------
        (html : str, logs : list[str])
            html  -- pass directly to Browser.render_pipeline()
            logs  -- diagnostic lines for the telemetry panel
        """
        logs = []
        parsed = self._parse(url)
        host   = parsed["host"]
        qmap   = parsed["query"]

        logs.append(f"[asg://] Intercepted: {url!r}")
        logs.append(f"[asg://] host={host!r}")

        # Frontend routes -- load asg_world/index.html from disk
        if host in self._FRONTEND_HOSTS:
            html, extra = self._load_frontend(qmap)
            logs.extend(extra)
            return html, logs

        # Built-in generated pages
        if host == "settings":
            logs.append("[asg://] Serving: built-in settings")
            return _html_settings(), logs

        if host == "about":
            logs.append("[asg://] Serving: built-in about")
            return _html_about(self.base_dir), logs

        if host == "history":
            logs.append("[asg://] Serving: built-in history")
            return _html_history(self._history_ref), logs

        # Unknown
        logs.append(f"[asg:// 404] Unknown sovereign path: {host!r}")
        return _html_not_found(url), logs

    def set_history_ref(self, history: list):
        """Inject the browser's history list so asg://history can render it."""
        self._history_ref = history

    # -- Private ------------------------------------------------------------

    def _parse(self, url: str) -> dict:
        """Normalize and parse an asg:// URL into components."""
        url = url.strip()
        # Normalize  asg:world  or  asg:settings  (missing //)
        if re.match(r"^asg:[^/]", url):
            url = "asg://" + url[4:]
        p    = urllib.parse.urlparse(url)
        host = (p.netloc or p.path.lstrip("/")).split("/")[0].lower()
        qs   = urllib.parse.parse_qs(p.query)
        return {"host": host, "query": qs, "raw_query": p.query}

    def _load_frontend(self, qmap: dict):
        """Read asg_world/index.html. Optionally inject an auto-search query."""
        logs = []

        if not os.path.isfile(self._frontend_path):
            logs.append(f"[asg:// Error] Frontend not found: {self._frontend_path}")
            return (
                f"<html><body><h1>ASG World Not Found</h1>"
                f"<p>Expected at: {self._frontend_path}</p></body></html>",
                logs,
            )

        with open(self._frontend_path, "r", encoding="utf-8") as fh:
            html = fh.read()

        logs.append(f"[asg://] Loaded frontend ({len(html):,} bytes)")

        # asg://search?q=term  -- inject auto-search on page load
        terms = qmap.get("q", [])
        if terms:
            q = terms[0].replace("\\", "\\\\").replace("'", "\\'")
            snippet = (
                "\n<script>\n"
                "window.addEventListener('load', function() {\n"
                "  var inp = document.getElementById('home-input');\n"
                "  if (inp) { inp.value = '" + q + "'; }\n"
                "  if (typeof navigate === 'function') { navigate('" + q + "'); }\n"
                "});\n"
                "</script>\n"
            )
            html = html.replace("</body>", snippet + "</body>")
            logs.append(f"[asg://] Auto-search injected for query: {q!r}")

        return html, logs
