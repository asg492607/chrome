"""
Strict Content Security Policy (CSP) & CORS Enforcement Engine.
Implements W3C Content Security Policy (CSP) Level 3 header directive parser,
cryptographic nonce & SHA-256 hash validator, WHATWG CORS rules engine, and preflight OPTIONS controller.
"""

import sys
import os
import hashlib
import base64
import urllib.parse
from enum import Enum, auto
from typing import Dict, List, Optional, Tuple, Any

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


class CSPDirective(Enum):
    DEFAULT_SRC = "default-src"
    SCRIPT_SRC = "script-src"
    STYLE_SRC = "style-src"
    IMG_SRC = "img-src"
    CONNECT_SRC = "connect-src"
    FRAME_SRC = "frame-src"


class CSPPolicy:
    """Represents parsed W3C CSP directives for an origin context."""

    def __init__(self, origin: str = "https://self.local"):
        self.origin = origin
        self.directives: Dict[str, List[str]] = {}

    def is_allowed(
        self,
        directive: str,
        target_url_or_source: str,
        nonce: str = "",
        script_body: Optional[bytes] = None
    ) -> bool:
        """Evaluates whether a resource request or inline script complies with CSP policy directives."""
        sources = self.directives.get(directive)
        if not sources and directive != "default-src":
            sources = self.directives.get("default-src")

        if not sources:
            return True # Unrestricted if no policy defined

        if "'none'" in sources:
            return False

        # Nonce verification
        if nonce and f"'nonce-{nonce}'" in sources:
            return True

        # SHA-256 Script Hash verification
        if script_body is not None:
            sha256_digest = base64.b64encode(hashlib.sha256(script_body).digest()).decode('ascii')
            hash_token = f"'sha256-{sha256_digest}'"
            if hash_token in sources:
                return True



        # Inline check
        if target_url_or_source == "inline":
            return "'unsafe-inline'" in sources

        # 'self' check
        if "'self'" in sources:
            if target_url_or_source.startswith(self.origin) or target_url_or_source.startswith("/"):
                return True

        # Domain matching
        for src in sources:
            if src.startswith("'"):
                continue
            if target_url_or_source.startswith(src) or src == "*":
                return True

        return False


class CSPParser:
    """W3C Content Security Policy Header String Parser."""

    @classmethod
    def parse_header(cls, csp_header_str: str, origin: str = "https://self.local") -> CSPPolicy:
        """Parses a Content-Security-Policy HTTP header into a CSPPolicy object."""
        policy = CSPPolicy(origin)
        directives = csp_header_str.split(';')

        for d in directives:
            d = d.strip()
            if not d:
                continue
            parts = d.split()
            dir_name = parts[0].lower()
            sources = [p.strip() for p in parts[1:]]
            policy.directives[dir_name] = sources

        return policy


class CORSRulesEngine:
    """WHATWG Cross-Origin Resource Sharing (CORS) & Preflight OPTIONS Rule Engine."""

    @classmethod
    def check_cors_request(
        cls,
        origin: str,
        request_url: str,
        request_headers: Dict[str, str],
        response_headers: Dict[str, str]
    ) -> bool:
        """Validates cross-origin HTTP response headers against WHATWG CORS rules."""
        req_parsed = urllib.parse.urlparse(origin)
        target_parsed = urllib.parse.urlparse(request_url)

        # Same origin -> allow automatically
        if req_parsed.netloc == target_parsed.netloc and req_parsed.scheme == target_parsed.scheme:
            return True

        allow_origin = response_headers.get("Access-Control-Allow-Origin")
        if not allow_origin:
            return False # Blocked: Missing CORS header

        allow_credentials = response_headers.get("Access-Control-Allow-Credentials", "false").lower() == "true"

        # Wildcard ACAO cannot be combined with credentials=true (WHATWG spec security rule)
        if allow_credentials and allow_origin == "*":
            return False

        if allow_origin == "*" or allow_origin == origin:
            return True

        return False

    @classmethod
    def validate_preflight_options(
        cls,
        origin: str,
        request_method: str,
        request_headers: List[str],
        response_headers: Dict[str, str]
    ) -> bool:
        """Validates CORS Preflight OPTIONS response headers."""
        allow_methods_str = response_headers.get("Access-Control-Allow-Methods", "")
        allowed_methods = [m.strip().upper() for m in allow_methods_str.split(',') if m.strip()]

        if request_method.upper() not in allowed_methods and "*" not in allowed_methods:
            return False

        allow_headers_str = response_headers.get("Access-Control-Allow-Headers", "")
        allowed_headers = [h.strip().lower() for h in allow_headers_str.split(',') if h.strip()]

        for req_h in request_headers:
            if req_h.lower() not in allowed_headers and "*" not in allowed_headers:
                return False

        return True
