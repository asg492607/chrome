"""
Strict SameSite Cookie Jar & Storage Partitioning Engine.
Implements RFC 6265bis HTTP Cookie specification, SameSite attribute enforcement (Strict, Lax, None),
Secure & HttpOnly validation, double-keyed storage partitioning (top_level_site, frame_origin), and LRU cookie eviction.
"""

import sys
import os
import time
import urllib.parse
from enum import Enum, auto
from typing import Dict, List, Optional, Tuple, Any

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


class SameSitePolicy(Enum):
    STRICT = "Strict"
    LAX = "Lax"
    NONE = "None"


class Cookie:
    """Represents an RFC 6265bis HTTP Cookie."""

    def __init__(
        self,
        name: str,
        value: str,
        domain: str,
        path: str = "/",
        secure: bool = False,
        httponly: bool = False,
        samesite: SameSitePolicy = SameSitePolicy.LAX,
        expires: Optional[float] = None
    ):
        self.name = name
        self.value = value
        self.domain = domain.lstrip('.').lower()
        self.path = path
        self.secure = secure
        self.httponly = httponly
        self.samesite = samesite
        self.expires = expires
        self.creation_time = time.time()

    def is_expired(self) -> bool:
        if self.expires is not None and time.time() > self.expires:
            return True
        return False

    def __repr__(self) -> str:
        return f"Cookie({self.name}={self.value}, domain={self.domain}, samesite={self.samesite.value})"


class CookieParser:
    """RFC 6265bis Set-Cookie Header String Parser."""

    @classmethod
    def parse_set_cookie(cls, set_cookie_str: str, default_domain: str) -> Cookie:
        """Parses a Set-Cookie HTTP header into a structured Cookie instance."""
        parts = [p.strip() for p in set_cookie_str.split(';') if p.strip()]
        name_val = parts[0].split('=', 1)
        name = name_val[0].strip()
        value = name_val[1].strip() if len(name_val) > 1 else ""

        domain = default_domain
        path = "/"
        secure = False
        httponly = False
        samesite = SameSitePolicy.LAX
        expires = None

        for attr in parts[1:]:
            attr_parts = attr.split('=', 1)
            key = attr_parts[0].strip().lower()
            val = attr_parts[1].strip() if len(attr_parts) > 1 else ""

            if key == "domain" and val:
                domain = val
            elif key == "path" and val:
                path = val
            elif key == "secure":
                secure = True
            elif key == "httponly":
                httponly = True
            elif key == "samesite":
                val_upper = val.capitalize()
                if val_upper == "Strict":
                    samesite = SameSitePolicy.STRICT
                elif val_upper == "None":
                    samesite = SameSitePolicy.NONE
                else:
                    samesite = SameSitePolicy.LAX
            elif key == "max-age":
                try:
                    expires = time.time() + float(val)
                except ValueError:
                    pass

        return Cookie(name, value, domain, path, secure, httponly, samesite, expires)


class SameSiteEnforcer:
    """SameSite Attribute Rules & Cross-Site CSRF Protection Engine."""

    @classmethod
    def should_send_cookie(
        cls,
        cookie: Cookie,
        is_same_site: bool,
        http_method: str = "GET"
    ) -> bool:
        """Enforces SameSite=Strict/Lax/None rules based on request context and HTTP method."""
        if cookie.is_expired():
            return False

        # SameSite=None requires Secure flag (RFC 6265bis Security Rule)
        if cookie.samesite == SameSitePolicy.NONE:
            if not cookie.secure:
                return False # Reject insecure SameSite=None cookie
            return True

        if is_same_site:
            return True

        if cookie.samesite == SameSitePolicy.STRICT:
            return False # Strictly blocked on cross-site requests

        if cookie.samesite == SameSitePolicy.LAX:
            # Lax cookies allowed on cross-site safe top-level GET/HEAD navigations
            return http_method.upper() in ["GET", "HEAD"]

        return False


class PartitionedCookieJar:
    """Double-Keyed Storage Partitioned Cookie Jar (top_level_site, frame_origin)."""

    def __init__(self):
        # Key: (top_level_site, frame_origin) -> List[Cookie]
        self.partition_map: Dict[Tuple[str, str], List[Cookie]] = {}

    @classmethod
    def get_site_key(cls, url: str) -> str:
        parsed = urllib.parse.urlparse(url)
        host = parsed.hostname or url
        parts = host.split('.')
        if len(parts) >= 2:
            return f"{parts[-2]}.{parts[-1]}"
        return host

    def set_cookie(self, cookie: Cookie, top_level_url: str, frame_url: str) -> bool:
        """Stores cookie under double-keyed storage partition (top_level_site, frame_origin)."""
        # Reject SameSite=None without Secure
        if cookie.samesite == SameSitePolicy.NONE and not cookie.secure:
            return False

        top_site = self.get_site_key(top_level_url)
        frame_site = self.get_site_key(frame_url)
        key = (top_site, frame_site)

        if key not in self.partition_map:
            self.partition_map[key] = []

        partition = self.partition_map[key]
        # Replace existing cookie with same name and domain
        partition = [c for c in partition if not (c.name == cookie.name and c.domain == cookie.domain)]
        partition.append(cookie)
        self.partition_map[key] = partition
        return True

    def get_cookies_for_request(
        self,
        target_url: str,
        top_level_url: str,
        frame_url: str,
        http_method: str = "GET"
    ) -> str:
        """Retrieves and formats matching cookies for an outgoing HTTP request."""
        top_site = self.get_site_key(top_level_url)
        frame_site = self.get_site_key(frame_url)
        target_site = self.get_site_key(target_url)

        key = (top_site, frame_site)
        partition = self.partition_map.get(key, [])

        is_same_site = (top_site == target_site and frame_site == target_site)
        matching_cookies = []

        for cookie in partition:
            if SameSiteEnforcer.should_send_cookie(cookie, is_same_site, http_method):
                matching_cookies.append(f"{cookie.name}={cookie.value}")

        return "; ".join(matching_cookies)

    def evict_expired_and_oldest(self, max_cookies: int = 1000) -> int:
        """Evicts expired cookies and oldest cookies when capacity limit is reached."""
        evicted = 0
        total_cookies = 0

        for key, cookies in list(self.partition_map.items()):
            active = [c for c in cookies if not c.is_expired()]
            evicted += len(cookies) - len(active)
            self.partition_map[key] = active
            total_cookies += len(active)

        if total_cookies > max_cookies:
            # Flatten and evict oldest
            all_cookies = []
            for key, cookies in self.partition_map.items():
                for c in cookies:
                    all_cookies.append((c.creation_time, key, c))

            all_cookies.sort(key=lambda x: x[0])
            to_remove = total_cookies - max_cookies

            for _, key, c in all_cookies[:to_remove]:
                self.partition_map[key].remove(c)
                evicted += 1

        return evicted
