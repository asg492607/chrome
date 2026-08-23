"""
chromium_engine/web_gateway.py
==========================================================================
Chromium Web Gateway & Live Proxy Subsystem

Handles high-performance outbound HTTP/HTTPS requests to live internet sites,
automatic cookie management, redirect following, www-prefix fallback,
CSS & font CORS rewriting, and the ASG Chromium Client Shim.
==========================================================================
"""

import urllib.request
import urllib.parse
import ssl
import gzip
import io
import re
from typing import Tuple, Dict, Any, Optional
from core_platform.logging_system import sys_logger


class WebGateway:
    """Universal live internet proxy and web scraper gateway for ASG World Chromium."""

    def __init__(self, timeout: int = 12):
        self.timeout = timeout
        self.ssl_context = ssl.create_default_context()
        self.ssl_context.check_hostname = False
        self.ssl_context.verify_mode = ssl.CERT_NONE

        # Build opener with full cookie processor and redirect handler
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPSHandler(context=self.ssl_context),
            urllib.request.HTTPCookieProcessor(),
            urllib.request.HTTPRedirectHandler()
        )
        self.opener.addheaders = [
            ('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'),
            ('Accept', 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8'),
            ('Accept-Language', 'en-US,en;q=0.9'),
            ('Accept-Encoding', 'gzip, deflate'),
            ('Sec-Ch-Ua', '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"'),
            ('Sec-Ch-Ua-Mobile', '?0'),
            ('Sec-Ch-Ua-Platform', '"Windows"')
        ]

    def fetch_url(self, target_url: str) -> Tuple[int, str, bytes]:
        """
        Fetches an external or local URL and returns (status_code, content_type, body_bytes).
        If the domain lookup fails, attempts 'www.' prefix or falls back to ASG World search.
        """
        if not target_url:
            return 400, "text/plain", b"Missing target URL."

        target_url = target_url.strip()
        if not target_url.startswith("http://") and not target_url.startswith("https://"):
            target_url = "https://" + target_url

        try:
            return self._perform_fetch(target_url)
        except Exception as first_error:
            # Try www fallback if not present
            parsed = urllib.parse.urlparse(target_url)
            if not parsed.netloc.startswith("www.") and "." in parsed.netloc:
                www_url = parsed._replace(netloc="www." + parsed.netloc).geturl()
                try:
                    return self._perform_fetch(www_url)
                except Exception:
                    pass

            query_term = parsed.netloc.split(".")[0] if parsed.netloc else target_url
            sys_logger.log(f"[WebGateway Notice] Domain {target_url} unreachable. Rendering search gateway.")
            
            fallback_html = f"""
            <!DOCTYPE html>
            <html lang="en">
            <head>
              <meta charset="utf-8">
              <meta name="viewport" content="width=device-width, initial-scale=1.0">
              <title>Search — {target_url}</title>
              <style>
                body {{
                  font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                  background: #070b12; color: #f1f5f9; padding: 40px 24px; min-height: 100vh;
                  display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center;
                }}
                .box {{
                  background: #111624; border: 1px solid rgba(255,255,255,0.08); border-radius: 18px;
                  max-width: 640px; width: 100%; padding: 36px 28px; box-shadow: 0 12px 40px rgba(0,0,0,0.6);
                }}
                .badge {{
                  display: inline-block; padding: 4px 14px; border-radius: 20px; font-size: 12px;
                  font-weight: 600; background: rgba(124,58,237,0.18); color: #c4b5fd; border: 1px solid rgba(124,58,237,0.3); margin-bottom: 16px;
                }}
                h1 {{ font-size: 22px; font-weight: 700; color: #f1f5f9; margin-bottom: 8px; }}
                p {{ font-size: 14px; color: #94a3b8; line-height: 1.6; margin-bottom: 24px; }}
                .search-btn {{
                  display: inline-flex; align-items: center; gap: 8px;
                  background: linear-gradient(135deg, #7c3aed, #06b6d4); color: white;
                  padding: 10px 24px; border-radius: 24px; text-decoration: none; font-size: 14px; font-weight: 600;
                  box-shadow: 0 4px 18px rgba(124,58,237,0.4); transition: transform 0.18s;
                }}
                .search-btn:hover {{ transform: translateY(-1px); }}
                .suggestions {{ margin-top: 28px; display: flex; gap: 8px; flex-wrap: wrap; justify-content: center; }}
                .chip {{
                  padding: 6px 14px; border-radius: 20px; font-size: 12px; color: #cbd5e1;
                  background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.08); text-decoration: none;
                }}
                .chip:hover {{ background: rgba(255,255,255,0.1); color: #67e8f9; }}
              </style>
            </head>
            <body>
              <div class="box">
                <span class="badge">🌐 ASG World Chromium Gateway</span>
                <h1>Domain <code>{parsed.netloc}</code> is not directly reachable</h1>
                <p>The web address you entered might be mistyped or requires standard search resolution. Search for <strong>"{query_term}"</strong> on ASG World to open official sites and articles.</p>
                
                <a href="/world?q={urllib.parse.quote(query_term)}" class="search-btn">
                  🔍 Search ASG World for "{query_term}"
                </a>

                <div class="suggestions">
                  <a href="/proxy?url=https://www.google.com" class="chip">🌐 Google</a>
                  <a href="/proxy?url=https://en.wikipedia.org" class="chip">📚 Wikipedia</a>
                  <a href="/proxy?url=https://www.python.org" class="chip">🐍 Python</a>
                  <a href="/blog/" class="chip">📝 The Packet Hacker</a>
                  <a href="/news/" class="chip">📰 Tech News</a>
                </div>
              </div>
            </body>
            </html>
            """
            return 200, "text/html; charset=utf-8", fallback_html.encode('utf-8')

    def _perform_fetch(self, url: str) -> Tuple[int, str, bytes]:
        req = urllib.request.Request(url)
        with self.opener.open(req, timeout=self.timeout) as response:
            status_code = response.status
            content_type = response.headers.get('Content-Type', 'text/html; charset=utf-8')
            raw_body = response.read()
            final_url = response.geturl()

            # Handle gzip
            if response.headers.get('Content-Encoding') == 'gzip':
                try:
                    raw_body = gzip.GzipFile(fileobj=io.BytesIO(raw_body)).read()
                except Exception:
                    pass

            # CSS url(...) rewriting to route fonts and sub-assets through proxy
            if "text/css" in content_type.lower():
                try:
                    css_text = raw_body.decode('utf-8', errors='ignore')
                    def replace_css_url(match):
                        u = match.group(1).strip('\'" \t\r\n')
                        if u.startswith('data:') or u.startswith('blob:') or '/proxy?url=' in u:
                            return f'url({match.group(1)})'
                        full = urllib.parse.urljoin(final_url, u)
                        return f'url("/proxy?url={urllib.parse.quote(full)}")'
                    
                    css_text = re.sub(r'url\((.*?)\)', replace_css_url, css_text)
                    raw_body = css_text.encode('utf-8')
                except Exception:
                    pass

            elif "text/html" in content_type.lower():
                try:
                    html_text = raw_body.decode('utf-8', errors='ignore')
                    
                    # Rewrite stylesheets to load through /proxy?url=
                    def replace_link(match):
                        pre = match.group(1)
                        href = match.group(2)
                        post = match.group(3)
                        if href.startswith('data:') or '/proxy?url=' in href:
                            return match.group(0)
                        full = urllib.parse.urljoin(final_url, href)
                        return f'{pre}/proxy?url={urllib.parse.quote(full)}{post}'

                    html_text = re.sub(r'(<link[^>]+href=["\'])([^"\']+)(["\'])', replace_link, html_text, flags=re.IGNORECASE)

                    base_tag = f'<base href="{final_url}">'
                    
                    shim_script = f"""
                    <script id="asg-chromium-engine-shim">
                    (function() {{
                      var baseUrl = "{final_url}";
                      var proxyPrefix = window.location.origin + "/proxy?url=";

                      // 1. Safe History API Wrapper
                      var origPushState = history.pushState;
                      var origReplaceState = history.replaceState;
                      history.pushState = function(state, unused, url) {{
                        try {{
                          if (url) {{
                            var full = new URL(url, baseUrl).href;
                            return origPushState.call(history, state, unused, proxyPrefix + encodeURIComponent(full));
                          }}
                          return origPushState.apply(history, arguments);
                        }} catch(e) {{}}
                      }};
                      history.replaceState = function(state, unused, url) {{
                        try {{
                          if (url) {{
                            var full = new URL(url, baseUrl).href;
                            return origReplaceState.call(history, state, unused, proxyPrefix + encodeURIComponent(full));
                          }}
                          return origReplaceState.apply(history, arguments);
                        }} catch(e) {{}}
                      }};

                      // 2. Fetch & XHR Proxy Interceptors (fixes CORS completely)
                      var origFetch = window.fetch;
                      window.fetch = function(input, init) {{
                        try {{
                          var target = typeof input === 'string' ? input : (input && input.url ? input.url : '');
                          if (target && !target.startsWith('data:') && !target.startsWith('blob:')) {{
                            var resolved = new URL(target, baseUrl).href;
                            if (!resolved.includes('/proxy?url=')) {{
                              if (typeof input === 'string') {{
                                input = proxyPrefix + encodeURIComponent(resolved);
                              }} else if (input && input.url) {{
                                input = new Request(proxyPrefix + encodeURIComponent(resolved), init || input);
                              }}
                            }}
                          }}
                        }} catch(e) {{}}
                        return origFetch.call(window, input, init);
                      }};

                      var origXhrOpen = XMLHttpRequest.prototype.open;
                      XMLHttpRequest.prototype.open = function(method, url, async, user, password) {{
                        try {{
                          if (url && typeof url === 'string' && !url.startsWith('data:') && !url.startsWith('blob:')) {{
                            var resolved = new URL(url, baseUrl).href;
                            if (!resolved.includes('/proxy?url=')) {{
                              url = proxyPrefix + encodeURIComponent(resolved);
                            }}
                          }}
                        }} catch(e) {{}}
                        return origXhrOpen.call(this, method, url, async !== false, user, password);
                      }};

                      // 3. Form Submit Interceptor
                      document.addEventListener('submit', function(e) {{
                        var form = e.target;
                        if (form && form.action) {{
                          try {{
                            var resolvedAction = new URL(form.action, baseUrl).href;
                            if (!form.method || form.method.toUpperCase() === 'GET') {{
                              e.preventDefault();
                              var formData = new FormData(form);
                              var params = new URLSearchParams(formData).toString();
                              var finalTarget = resolvedAction + (resolvedAction.includes('?') ? '&' : '?') + params;
                              window.location.href = proxyPrefix + encodeURIComponent(finalTarget);
                            }}
                          }} catch(err) {{}}
                        }}
                      }}, true);

                      // Frame-busting neutralizer
                      try {{
                        Object.defineProperty(window, 'top', {{ get: function() {{ return window.self; }}, configurable: true }});
                        Object.defineProperty(window, 'parent', {{ get: function() {{ return window.self; }}, configurable: true }});
                      }} catch(e) {{}}

                      // Clean target attributes dynamically
                      function cleanTargets() {{
                        try {{
                          var targets = document.querySelectorAll('a[target], form[target], base[target]');
                          for (var i = 0; i < targets.length; i++) {{
                            targets[i].removeAttribute('target');
                          }}
                        }} catch(e) {{}}
                      }}
                      document.addEventListener('DOMContentLoaded', cleanTargets);
                      var obs = new MutationObserver(cleanTargets);
                      try {{ obs.observe(document.documentElement, {{ childList: true, subtree: true }}); }} catch(e) {{}}

                      // 4. In-frame click capturing to maintain proxy flow
                      document.addEventListener('click', function(e) {{
                        var link = e.target.closest('a');
                        if (link && link.href && !link.href.startsWith('javascript:')) {{
                          e.preventDefault();
                          var resolved = new URL(link.getAttribute('href') || link.href, baseUrl).href;
                          window.location.href = proxyPrefix + encodeURIComponent(resolved);
                        }}
                      }}, true);
                    }})();
                    </script>
                    """

                    injection = base_tag + shim_script
                    if "<head>" in html_text:
                        html_text = html_text.replace("<head>", f"<head>{injection}", 1)
                    elif "<HEAD>" in html_text:
                        html_text = html_text.replace("<HEAD>", f"<HEAD>{injection}", 1)
                    else:
                        html_text = injection + html_text

                    raw_body = html_text.encode('utf-8')
                except Exception as e:
                    sys_logger.log(f"[WebGateway] HTML rewrite note: {e}")

            sys_logger.log(f"[WebGateway] 200 OK - Proxied {final_url} ({len(raw_body)} bytes)")
            return status_code, content_type, raw_body
