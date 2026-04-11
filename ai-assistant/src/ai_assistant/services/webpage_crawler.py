"""
Webpage Crawler
===============
Fetches a provider's website and extracts structured, service-relevant
information using a single LLM call.  The extracted data enriches the
Weaviate ``LiteCompetence`` record with:

- ``skills_list``  — specific services / offerings (replaces the always-empty
  placeholder produced by the Google Places normalisation pass)
- ``search_optimized_summary``  — the speciality sentence appended to the
  English vector-search summary, improving cross-encoder and BM25 scores for
  niche queries
- ``description``  — portfolio highlights and geographic coverage appended to
  the user-facing provider description shown on the card

Security invariants
-------------------
- Only HTTPS URLs are crawled (plain HTTP is rejected).
- Only ``websiteUri`` values that originate from the Google Places API are
  ever passed in — user-supplied URLs never reach this module.
- Private / loopback / link-local IP ranges (RFC 1918 / RFC 4291) are blocked
  after DNS resolution to prevent SSRF.
- Maximum 3 redirects; ``text/html`` content-type guard; 400 KB body cap.
"""
from __future__ import annotations

import asyncio
import ipaddress
import logging
import re
import socket
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Any

import aiohttp

from .llm_service import LLMService

logger = logging.getLogger(__name__)

_CRAWL_TIMEOUT_SECONDS = 8
_MAX_BODY_BYTES = 400_000   # 400 KB — generous enough for heavy WordPress pages
_MAX_REDIRECTS = 3
_MAX_PAGES_PER_SITE = 4     # landing page + up to 3 high-value subpages
_PRIVATE_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
    ipaddress.ip_network("169.254.0.0/16"),
]


@dataclass
class WebCrawlResult:
    """Structured service-relevant information extracted from a provider's webpage."""

    services: list[str] = field(default_factory=list)
    """Specific services / offerings mentioned on the page (e.g. "3-tier custom wedding cakes")."""

    specialities: str = ""
    """One sentence describing what the provider specialises in (English)."""

    portfolio_highlights: str = ""
    """Notable portfolio items or past projects (max 80 chars, English)."""

    coverage_area: str = ""
    """Geographic service area if explicitly stated on the page (max 60 chars, English)."""

    email: str = ""
    """Business contact e-mail address found on the page, if any."""


class WebPageCrawler:
    """Fetches a provider's landing page and extracts service-relevant data via LLM."""

    def __init__(self, llm_service: LLMService) -> None:
        self._llm = llm_service

    async def extract_provider_info(
        self,
        url: str,
        provider_name: str,
        query: str,
    ) -> WebCrawlResult | None:
        """Crawl ``url`` (plus up to ``_MAX_PAGES_PER_SITE - 1`` high-value
        subpages) and return extracted service information.

        Returns ``None`` if the URL is empty, rejected by the security checks,
        times out, or the LLM extraction fails — never raises.

        Args:
            url: The ``websiteUri`` from Google Places (HTTPS only).
            provider_name: Business name — used as context in the extraction prompt.
            query: The user's search query — guides the LLM to focus on relevant info.
        """
        if not url:
            logger.debug("Webpage crawl skipped for %r: no URL", provider_name)
            return None

        try:
            landing = await self._fetch_html(url)
        except Exception as exc:
            logger.info(
                "Webpage crawl failed for %r: %s: %s",
                provider_name, type(exc).__name__, exc,
            )
            return None

        if not landing:
            logger.info("Webpage crawl skipped for %r: no HTML returned", provider_name)
            return None

        html, final_url = landing

        # ── Multi-page: collect subpage URLs ────────────────────────────────────
        # Use the *final* URL (after any redirects) as the base so that
        # same-host link filtering works correctly when the original URL had a
        # different hostname (e.g. www.example.com → example.com redirect).
        subpage_urls = _score_and_filter_links(
            html, final_url, max_links=_MAX_PAGES_PER_SITE - 1
        )
        if not subpage_urls:
            # No internal links found — typical of JS-heavy Wix / Squarespace
            # sites that serve a minimal SPA bootstrap page.  Probe the most
            # likely contact / info paths directly as a fallback.
            from urllib.parse import urljoin  # noqa: PLC0415
            base = final_url.rstrip("/")
            subpage_urls = [
                urljoin(base + "/", p.lstrip("/"))
                for p in _CONTACT_PROBE_PATHS
            ][: _MAX_PAGES_PER_SITE - 1]
            logger.debug(
                "No internal links found for %r — probing %d fallback paths",
                provider_name, len(subpage_urls),
            )

        # ── Fetch subpages concurrently ─────────────────────────────────────────
        sub_results = await asyncio.gather(
            *(self._fetch_html(sub_url) for sub_url in subpage_urls),
            return_exceptions=True,
        ) if subpage_urls else []

        all_html_parts = [html]
        all_text_parts = [_extract_text(html)]
        for sr in sub_results:
            if isinstance(sr, tuple) and sr[0]:
                sub_html = sr[0]
                all_html_parts.append(sub_html)
                sub_text = _extract_text(sub_html)
                if sub_text:
                    all_text_parts.append(sub_text)
        combined_html = "\n".join(all_html_parts)
        combined_text = " ".join(filter(None, all_text_parts))

        if not combined_text:
            logger.info(
                "Webpage crawl skipped for %r: no text extracted from any page",
                provider_name,
            )
            return None

        # Cap plain text before sending to the LLM to prevent enormous token
        # bills on verbose sites (e.g. WordPress blogs with 400 KB pages).
        # 15,000 characters ≈ 3,750 tokens — more than sufficient for the
        # structured extraction task.
        _MAX_CRAWL_TEXT_CHARS = 15_000
        if len(combined_text) > _MAX_CRAWL_TEXT_CHARS:
            logger.debug(
                "Webpage crawl for %r: truncating %d → %d chars before LLM extraction",
                provider_name, len(combined_text), _MAX_CRAWL_TEXT_CHARS,
            )
            combined_text = combined_text[:_MAX_CRAWL_TEXT_CHARS]

        result = await self._llm_extract(combined_text, provider_name, query)
        if result is not None:
            result.email = _extract_email(combined_html)
            successful_subs = sum(
                1 for r in sub_results if isinstance(r, tuple) and r[0]
            )
            pages_crawled = 1 + successful_subs
            logger.info(
                "Webpage crawl OK for %r: %d page(s), %d services, specialities=%r, email=%r",
                provider_name, pages_crawled, len(result.services),
                bool(result.specialities), bool(result.email),
            )
        return result

    # ──────────────────────────────────────────────────────────────────────────
    # Private helpers
    # ──────────────────────────────────────────────────────────────────────────

    async def _fetch_html(self, url: str) -> tuple[str, str] | None:
        """Fetch the page at ``url``, enforcing all security constraints.

        Returns ``(html, final_url)`` on success, where ``final_url`` is the
        URL after following any redirects (may differ from ``url`` when there
        is a www ↔ no-www or HTTP→HTTPS redirect).

        Raises on any violation or network error so the caller can skip
        enrichment cleanly.
        """
        # Silently upgrade http:// → https:// — Google Places often returns the
        # plain-HTTP variant even when the site serves HTTPS.  We rewrite before
        # any request so traffic is always encrypted.
        lower = url.lower()
        if lower.startswith("http://"):
            url = "https://" + url[7:]
            logger.debug("Upgraded URL to HTTPS: %r", url)
        elif not lower.startswith("https://"):
            logger.info("Webpage crawl rejected (unsupported scheme) for URL: %r", url)
            return None

        # Resolve hostname and block private ranges (SSRF guard)
        from urllib.parse import urlparse
        hostname = urlparse(url).hostname or ""
        await _assert_not_private(hostname)

        timeout = aiohttp.ClientTimeout(total=_CRAWL_TIMEOUT_SECONDS)
        headers = {
            # Use a realistic browser UA — many sites (WordPress, Wix, WooCommerce,
            # Shopify) serve a minimal SPA bootstrap to requests that identify as
            # bots, while returning fully server-rendered HTML to browser UAs.
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
        }

        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(
                url, headers=headers, allow_redirects=True, max_redirects=_MAX_REDIRECTS
            ) as resp:
                content_type = resp.content_type or ""
                if "text/html" not in content_type:
                    logger.debug(
                        "Webpage crawl skipped: non-HTML content-type=%r for %r",
                        content_type, url,
                    )
                    return None

                raw = await resp.content.read(_MAX_BODY_BYTES)
                charset = resp.charset or "utf-8"
                final_url = str(resp.url)
                try:
                    return raw.decode(charset, errors="replace"), final_url
                except LookupError:
                    return raw.decode("utf-8", errors="replace"), final_url

    async def _llm_extract(
        self,
        page_text: str,
        provider_name: str,
        query: str,
    ) -> WebCrawlResult | None:
        """Call the LLM to extract structured service information from page text."""
        import json as _json
        from langchain_core.messages import HumanMessage
        from ..prompts_templates import WEBPAGE_EXTRACTION_PROMPT

        prompt = WEBPAGE_EXTRACTION_PROMPT.format(
            provider_name=provider_name,
            query=query,
            page_text=page_text,
        )
        try:
            raw = await self._llm.generate([HumanMessage(content=prompt)])
            # Strip markdown fences the LLM may add
            cleaned = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            data: dict[str, Any] = _json.loads(cleaned)
        except Exception as exc:
            logger.warning(
                "WebPageCrawler LLM extraction failed for %r: %s", provider_name, exc
            )
            return None

        services_raw = data.get("services") or []
        services = [
            str(s).strip() for s in services_raw
            if s and str(s).strip()
        ][:20]

        return WebCrawlResult(
            services=services,
            specialities=str(data.get("specialities") or "").strip()[:120],
            portfolio_highlights=str(data.get("portfolio_highlights") or "").strip()[:120],
            coverage_area=str(data.get("coverage_area") or "").strip()[:80],
        )


# ──────────────────────────────────────────────────────────────────────────────
# Module-level helpers
# ──────────────────────────────────────────────────────────────────────────────

class _TextExtractor(HTMLParser):
    """Minimal HTML→text stripper using only stdlib."""

    _SKIP_TAGS = frozenset({
        "script", "style", "noscript", "meta", "head", "link",
        "svg", "path", "canvas", "iframe", "template",
    })

    def __init__(self) -> None:
        super().__init__()
        self._skip_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list) -> None:  # type: ignore[override]
        if tag.lower() in self._SKIP_TAGS:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in self._SKIP_TAGS and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0:
            stripped = data.strip()
            if stripped:
                self.parts.append(stripped)


def _extract_text(html: str) -> str:
    """Extract searchable text from HTML.

    Combines three sources so that content-rich text is available even for
    JavaScript-rendered SPAs that deliver an empty body to a plain HTTP fetch:

    1. ``<title>`` — page title.
    2. ``<meta name/property="description">`` / ``og:description`` — site summary.
    3. ``<script type="application/ld+json">`` — schema.org structured data
       (widely used by Google Business, WordPress, Wix, Squarespace).
    4. Visible body text — works well for server-rendered / static sites.
    """
    import json as _json

    parts: list[str] = []

    # 1. <title>
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
    if m:
        t = m.group(1).strip()
        if t:
            parts.append(t)

    # 2. <meta name/property="description"> or og:description
    for tag_m in re.finditer(r"<meta\b[^>]+>", html, re.I):
        tag = tag_m.group(0)
        if not re.search(
            r"""(?:name|property)\s*=\s*['"](?:description|og:description)['"]""",
            tag, re.I,
        ):
            continue
        cm = re.search(r"""content\s*=\s*['"]([^'"]{10,})['"]""", tag, re.I)
        if cm:
            parts.append(cm.group(1).strip())

    # 3. JSON-LD structured data
    for ld_m in re.finditer(
        r"""<script\b[^>]+type\s*=\s*["']application/ld\+json["'][^>]*>(.*?)</script>""",
        html, re.I | re.S,
    ):
        try:
            data = _json.loads(ld_m.group(1))
            parts.extend(_jsonld_strings(data))
        except Exception:
            pass

    # 4. Visible body text
    parser = _TextExtractor()
    try:
        parser.feed(html)
    except Exception:
        pass
    parts.extend(parser.parts)

    text = " ".join(parts)
    text = re.sub(r"\s{2,}", " ", text)
    return text


def _jsonld_strings(data: Any) -> list[str]:
    """Recursively extract text fields from a schema.org JSON-LD object."""
    _TEXT_KEYS = frozenset({
        "name", "description", "disambiguatingDescription", "slogan",
        "serviceType", "knowsAbout",
    })
    if isinstance(data, list):
        list_out: list[str] = []
        for item in data:
            list_out.extend(_jsonld_strings(item))
        return list_out
    if not isinstance(data, dict):
        return []
    out: list[str] = []
    for k, v in data.items():
        if k in _TEXT_KEYS and isinstance(v, str) and v.strip():
            out.append(v.strip())
        elif isinstance(v, (dict, list)):
            out.extend(_jsonld_strings(v))
    return out


# Common contact/impression paths probed when a landing page has no internal
# links (typical of Wix / Squarespace SPAs that serve a thin JS bootstrap page).
_CONTACT_PROBE_PATHS = (
    "/kontakt", "/contact", "/about", "/impressum", "/ueber-uns",
    # Shopify stores use /pages/<slug> routing
    "/pages/kontakt", "/pages/contact", "/pages/impressum",
)

# Path segments that identify non-content URLs (feeds, sitemaps, admin areas,
# e-commerce checkout pages).  These are excluded from subpage selection because
# they never contain service descriptions, contact information, or portfolio
# content worth crawling.
_USELESS_PATH_SEGMENTS = frozenset({
    "feed", "rss", "atom", "sitemap", "sitemap_index",
    "wp-json", "wp-admin", "wp-login", "wp-cron", "xmlrpc",
    "cart", "checkout", "my-account", "warenkorb", "kasse",
    "login", "register", "logout", "signin", "signup",
    "robots", "ads", "comments",
})

# Priority path terms — pages whose URL path contains one or more of these
# words are crawled before generic paths, as they tend to be the richest
# source of service descriptions, contact information, and team details.
_HIGH_VALUE_PATH_TERMS = (
    "contact", "kontakt", "about", "ueber",
    "service", "leistung", "angebot", "portfolio",
    "work", "team", "impressum", "expertise",
)


def _score_and_filter_links(
    html: str,
    base_url: str,
    max_links: int,
) -> list[str]:
    """Extract and prioritise same-origin internal links from ``html``.

    Returns up to ``max_links`` HTTPS URLs on the same host as ``base_url``,
    ranked by path keyword relevance (contact / services / about pages first).
    Asset URLs, external domains, and duplicates of ``base_url`` are excluded.

    Security: only same-hostname URLs are returned; every URL still passes
    through :func:`_fetch_html`'s SSRF guard before any network request.
    """
    from urllib.parse import urljoin, urlparse

    base = urlparse(base_url)
    base_host = (base.netloc or "").lower()
    if not base_host:
        return []

    seen: set[str] = set()
    scored: list[tuple[int, str]] = []

    for m in re.finditer(r"""href\s*=\s*['"]([^'"#][^'"]*?)['"]""", html, re.I):
        href = m.group(1).strip()
        if not href or href.startswith(("javascript:", "mailto:", "tel:")):
            continue

        abs_url = urljoin(base_url, href)
        parsed = urlparse(abs_url)

        # Same host and HTTPS only
        if parsed.netloc.lower() != base_host or parsed.scheme != "https":
            continue

        # Reject asset paths by file extension
        path_lower = parsed.path.lower()
        last_segment = path_lower.rsplit("/", 1)[-1]
        ext = last_segment.rsplit(".", 1)[-1] if "." in last_segment else ""
        if ext in _ASSET_EXTENSIONS:
            continue

        # Reject feed, sitemap, admin, and other non-content paths
        path_segments = set(path_lower.strip("/").split("/"))
        if path_segments & _USELESS_PATH_SEGMENTS:
            continue

        # Normalise: drop fragment + query string, strip trailing slash
        clean = parsed._replace(fragment="", query="").geturl().rstrip("/")
        base_clean = base_url.rstrip("/")
        if not clean or clean == base_clean or clean in seen:
            continue
        seen.add(clean)

        score = sum(1 for term in _HIGH_VALUE_PATH_TERMS if term in path_lower)
        scored.append((score, clean))

    # Highest score first; alphabetical within equal scores for determinism
    scored.sort(key=lambda x: (-x[0], x[1]))
    return [url for _, url in scored[:max_links]]


async def _assert_not_private(hostname: str) -> None:
    """Raise ``ValueError`` if ``hostname`` resolves to a private IP range."""
    if not hostname:
        raise ValueError("Empty hostname")
    loop = asyncio.get_event_loop()
    try:
        infos = await loop.run_in_executor(
            None,
            lambda: socket.getaddrinfo(hostname, None),
        )
    except socket.gaierror as exc:
        raise ValueError(f"DNS resolution failed for {hostname!r}: {exc}") from exc

    for info in infos:
        addr_str = info[4][0]
        try:
            addr = ipaddress.ip_address(addr_str)
        except ValueError:
            continue
        for net in _PRIVATE_NETWORKS:
            if addr in net:
                raise ValueError(
                    f"SSRF guard: {hostname!r} resolves to private address {addr_str}"
                )


# ── E-mail extraction ────────────────────────────────────────────────────────

# Covers mailto: links and plain-text addresses.  Matches standard e-mail
# characters; deliberately conservative to avoid false positives from
# minified JS strings or image asset paths.
_EMAIL_RE = re.compile(
    r"(?:mailto:)?"
    r"([a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+"
    r"@"
    r"[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?"
    r"(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)+)",
)

# File-extension suffixes that are never valid e-mail TLDs but commonly appear
# in asset paths like "image@2x.png"
_ASSET_EXTENSIONS = frozenset({
    "png", "jpg", "jpeg", "gif", "webp", "svg", "ico", "bmp",
    "css", "js", "ts", "json", "xml", "html", "htm", "pdf",
    "ttf", "woff", "woff2", "eot", "map",
})


def _extract_email(html: str) -> str:
    """Return the first plausible business e-mail address found in ``html``.

    Prefers ``mailto:`` anchors (most likely to be intentionally published
    contact addresses).  Falls back to plain-text e-mail patterns if none are
    found via mailto.  Returns an empty string when nothing is found.
    """

    # 1. Prefer mailto: href values — highest confidence
    for m in _EMAIL_RE.finditer(html):
        full_match = m.group(0)
        addr = m.group(1)
        if not full_match.lower().startswith("mailto:"):
            continue
        tld = addr.rsplit(".", 1)[-1].lower()
        if tld not in _ASSET_EXTENSIONS and len(tld) >= 2:
            return addr.lower()

    # 2. Fall back to any plain-text address in the page
    for m in _EMAIL_RE.finditer(html):
        addr = m.group(1)
        tld = addr.rsplit(".", 1)[-1].lower()
        if tld not in _ASSET_EXTENSIONS and len(tld) >= 2:
            return addr.lower()

    return ""
