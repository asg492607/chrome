import socket
import threading
import urllib.parse
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from typing import List, Dict, Any, Optional, Tuple
from core_platform.logging_system import sys_logger

from search_platform.search_config import SearchConfig
from search_platform.index_builder import IndexBuilder
from search_platform.query_processor import process_query
from search_platform.ranking_engine import RankingEngine

class AutocompleteEngine:
    """Trie-based Prefix Autocomplete Engine for sub-millisecond query suggestions."""

    def __init__(self):
        self.root: Dict[str, Any] = {}

    def insert(self, word: str) -> None:
        """Inserts word into prefix trie."""
        word = word.lower().strip()
        if not word:
            return
        node = self.root
        for char in word:
            if char not in node:
                node[char] = {}
            node = node[char]
        node['$'] = True

    def autocomplete(self, prefix: str, limit: int = 5) -> List[str]:
        """Returns top completion suggestions for specified prefix."""
        prefix = prefix.lower().strip()
        if not prefix:
            return []

        node = self.root
        for char in prefix:
            if char not in node:
                return []
            node = node[char]

        results: List[str] = []
        self._dfs(node, prefix, results, limit)
        return results

    def _dfs(self, node: Dict[str, Any], current: str, results: List[str], limit: int) -> None:
        if len(results) >= limit:
            return
        if '$' in node:
            results.append(current)
        for char, next_node in node.items():
            if char != '$':
                self._dfs(next_node, current + char, results, limit)


def render_search_homepage():

    return """<html>
<head>
  <title>AsgSearch - Home</title>
  <style>
    body { background-color: #0f172a; color: #cbd5e1; font-family: Arial, sans-serif; padding: 30px; }
    h1 { color: #818cf8; text-align: center; font-size: 36px; margin-top: 60px; }
    p { color: #94a3b8; text-align: center; font-size: 16px; }
    .nav { text-align: center; margin: 30px 0; }
    .search-hint { background-color: #1e293b; border: 1px solid #334155; padding: 15px; border-radius: 8px; margin: 40px auto; max-width: 500px; text-align: center; }
    .hint-title { font-weight: bold; color: #38bdf8; margin-bottom: 5px; }
    .link-group { margin-top: 15px; }
    a { color: #60a5fa; text-decoration: none; }
    a:hover { color: #93c5fd; }
  </style>
</head>
<body>
  <h1>AsgSearch</h1>
  <p>Your Private, Custom Search Engine Stack</p>
  
  <div class="search-hint">
    <div class="hint-title">Search Using Omnibox</div>
    To search, simply type in your address bar:<br>
    <span style="color:#f43f5e;">asgsearch.local/search?q=your_query</span>
  </div>
  
  <div class="nav">
    <b>Try Quick Queries:</b>
    <div class="link-group">
      <a href="http://asgsearch.local/search?q=dhcp">Search: "dhcp"</a> &nbsp;|&nbsp;
      <a href="http://asgsearch.local/search?q=python">Search: "python"</a> &nbsp;|&nbsp;
      <a href="http://asgsearch.local/search?q=agents">Search: "agents"</a>
    </div>
  </div>
</body>
</html>
"""

def render_search_results(query, results):
    results_html = ""
    if not results:
        results_html = '<div class="no-results">No pages found matching search terms. Try indexing more pages.</div>'
    else:
        for item in results:
            results_html += f"""
            <div class="result">
                <div class="title"><a href="{item.url}">{item.title}</a></div>
                <div class="url">{item.url} &nbsp;&nbsp;(Relevance: {item.score:.4f})</div>
                <div class="snippet">{item.snippet}</div>
            </div>
            """

    return f"""<html>
<head>
  <title>AsgSearch - "{query}"</title>
  <style>
    body {{ background-color: #0f172a; color: #cbd5e1; font-family: Arial, sans-serif; padding: 25px; }}
    h1 {{ color: #818cf8; font-size: 24px; border-bottom: 1px solid #334155; padding-bottom: 10px; }}
    .query-text {{ color: #38bdf8; }}
    .result {{ margin-top: 20px; margin-bottom: 25px; border-bottom: 1px dashed #1e293b; padding-bottom: 15px; }}
    .title {{ font-size: 18px; font-weight: bold; margin-bottom: 2px; }}
    .url {{ font-size: 12px; color: #34d399; margin-bottom: 6px; }}
    .snippet {{ font-size: 14px; color: #94a3b8; line-height: 1.4; }}
    .no-results {{ color: #f87171; font-style: italic; font-size: 16px; margin: 30px 0; }}
    .back {{ margin-top: 40px; display: block; color: #60a5fa; text-decoration: none; }}
    a {{ color: #60a5fa; text-decoration: none; }}
    a:hover {{ color: #93c5fd; }}
  </style>
</head>
<body>
  <h1>Search Results for: "<span class="query-text">{query}</span>"</h1>
  
  <div class="results-container">
    {results_html}
  </div>
  
  <a href="http://asgsearch.local/" class="back">&larr; Back to Search Homepage</a>
</body>
</html>
"""

class SearchAPI:
    def __init__(self, host="127.0.0.1", port=8082, index_file=SearchConfig.INDEX_FILE):
        self.host = host
        self.port = port
        self.running = False
        self.server_socket = None
        self.index_builder = IndexBuilder(index_file)
        self.ranking_engine = RankingEngine()
        
    def start(self):
        self.index_builder.load_index()
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self.server_socket.bind((self.host, self.port))
        except Exception as e:
            sys_logger.log(f"[Search API Error] Failed to bind to {self.host}:{self.port}: {e}")
            return
            
        self.server_socket.listen(5)
        self.running = True
        sys_logger.log(f"[Search API] Started listening on {self.host}:{self.port}")
        
        thread = threading.Thread(target=self._accept_loop, daemon=True)
        thread.start()

    def stop(self):
        self.running = False
        if self.server_socket:
            self.server_socket.close()
        sys_logger.log("[Search API] Stopped")

    def _accept_loop(self):
        while self.running:
            try:
                client_sock, client_addr = self.server_socket.accept()
                thread = threading.Thread(target=self._handle_request, args=(client_sock,), daemon=True)
                thread.start()
            except OSError:
                break

    def _handle_request(self, client_sock):
        try:
            request = client_sock.recv(4096).decode('utf-8', errors='ignore')
            lines = request.split("\r\n")
            if not lines or not lines[0]:
                return
            
            parts = lines[0].split(" ")
            if len(parts) < 2:
                return
            
            method, path_url = parts[0], parts[1]
            parsed = urllib.parse.urlparse(path_url)
            route = parsed.path
            query_params = urllib.parse.parse_qs(parsed.query)
            
            if route == "/search" or route == "/search.html":
                query_list = query_params.get("q", [""])
                query = query_list[0].strip()
                if query:
                    self.index_builder.load_index()
                    query_terms = process_query(query, SearchConfig.STOP_WORDS)
                    results = self.ranking_engine.rank(query_terms, self.index_builder.index, self.index_builder.documents)
                    body = render_search_results(query, results)
                else:
                    body = render_search_homepage()
            else:
                body = render_search_homepage()
                
            response = (
                "HTTP/1.1 200 OK\r\n"
                "Content-Type: text/html; charset=utf-8\r\n"
                f"Content-Length: {len(body.encode('utf-8'))}\r\n"
                "Connection: close\r\n\r\n"
                f"{body}"
            )
            client_sock.sendall(response.encode('utf-8'))
        except Exception as e:
            sys_logger.log(f"[Search API Client Error] {e}")
        finally:
            client_sock.close()
