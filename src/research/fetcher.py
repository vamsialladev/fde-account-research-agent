"""A polite page fetcher for the critic's checks: robots.txt first, a clear user agent, a size and time limit, and
a disk cache so the same page is fetched once.

The research itself goes through Anthropic's web search tool. This fetcher only re-reads a cited page to check
that the quoted text is really there; if robots.txt disallows it, the page is not fetched and the source is marked
"robots.txt" (not verified, not removed).
"""

import hashlib
import json
import re
import urllib.error
import urllib.request
import urllib.robotparser
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

from research import config


class _Text(HTMLParser):
    SKIP = {"script", "style", "noscript", "svg", "head"}

    def __init__(self):
        super().__init__()
        self.parts, self.skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip += 1

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.skip:
            self.skip -= 1

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def html_to_text(html: str) -> str:
    """Visible text. A page Python's parser can't read (it raises on some malformed markup) gives ValueError."""
    p = _Text()
    try:
        p.feed(html)
        p.close()
    except AssertionError as exc:  # html.parser raises AssertionError on e.g. "<![h..." marked sections
        raise ValueError("unparseable page") from exc
    return " ".join(" ".join(p.parts).split())


def normalize(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", (text or "").lower()))


class Fetcher:
    def __init__(self, cache_dir: Path | None = None, opener=None):
        self.cache = Path(cache_dir or config.CACHE_DIR)
        self.opener = opener or self._open
        self.robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}

    def _open(self, url: str) -> bytes:
        req = urllib.request.Request(url, headers={"User-Agent": config.USER_AGENT})
        with urllib.request.urlopen(req, timeout=config.FETCH_TIMEOUT_S) as resp:  # noqa: S310 - http(s) only, checked
            return resp.read(config.FETCH_MAX_BYTES)

    def allowed(self, url: str) -> bool:
        parts = urlparse(url)
        host = f"{parts.scheme}://{parts.netloc}"
        if host not in self.robots:
            rp = urllib.robotparser.RobotFileParser()
            try:
                rp.parse(self.opener(host + "/robots.txt").decode("utf-8", "replace").splitlines())
                self.robots[host] = rp
            except (urllib.error.URLError, OSError, ValueError):
                self.robots[host] = None  # no readable robots.txt: allowed, as crawlers treat it
        rp = self.robots[host]
        return True if rp is None else rp.can_fetch(config.USER_AGENT, url)

    def text(self, url: str) -> tuple[str, str]:
        """(status, page text). status: ok | robots.txt | unreachable | not http."""
        if urlparse(url).scheme not in ("http", "https"):
            return "not http", ""
        key = hashlib.sha256(url.encode()).hexdigest()[:24]
        path = self.cache / f"{key}.json"
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            return data["status"], data["text"]
        if not self.allowed(url):
            status, text = "robots.txt", ""
        else:
            try:
                status, text = "ok", html_to_text(self.opener(url).decode("utf-8", "replace"))
            except (urllib.error.URLError, OSError, ValueError):
                status, text = "unreachable", ""
        self.cache.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"url": url, "status": status, "text": text[:200_000]}), encoding="utf-8")
        return status, text

    def check(self, url: str, quote: str) -> str:
        """found | not found | robots.txt | unreachable | not checked (no quote)."""
        if not quote.strip():
            return "not checked"
        status, text = self.text(url)
        if status != "ok":
            return status
        q, t = normalize(quote), normalize(text)
        if q and q in t:
            return "found"
        words = q.split()  # a long quote may be trimmed or reflowed: accept 12 consecutive words from it
        windows = [" ".join(words[i : i + 12]) for i in range(0, max(len(words) - 11, 1), 6)]
        return "found" if any(w and w in t for w in windows) else "not found"
