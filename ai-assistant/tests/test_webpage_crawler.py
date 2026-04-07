"""
Unit tests for WebPageCrawler.

Covers:
- HTTPS-only enforcement
- Private IP / SSRF guard
- Timeout → None (no exception propagation)
- Non-HTML content-type → None
- HTML text extraction (tag stripping + 3000-char cap)
- Meta description extraction (name="description", og:description)
- JSON-LD structured data extraction
- LLM extraction → WebCrawlResult on valid JSON
- LLM extraction → None on malformed JSON
- Empty URL → None without any network or LLM call
"""
from __future__ import annotations

import json
import socket
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from ai_assistant.services.webpage_crawler import (
    WebCrawlResult,
    WebPageCrawler,
    _extract_email,
    _extract_text,
    _jsonld_strings,
    _score_and_filter_links,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_crawler() -> tuple[WebPageCrawler, MagicMock]:
    """Return a (WebPageCrawler, llm_mock) pair."""
    llm = MagicMock()
    llm.generate = AsyncMock(return_value="{}")
    crawler = WebPageCrawler(llm_service=llm)
    return crawler, llm


# ---------------------------------------------------------------------------
# Empty URL
# ---------------------------------------------------------------------------


class TestEmptyUrl:
    async def test_returns_none_immediately(self) -> None:
        crawler, llm = _make_crawler()
        result = await crawler.extract_provider_info(url="", provider_name="Acme", query="plumber")
        assert result is None
        llm.generate.assert_not_called()


# ---------------------------------------------------------------------------
# URL scheme handling
# ---------------------------------------------------------------------------


class TestUrlSchemeHandling:
    async def test_http_url_is_upgraded_to_https(self) -> None:
        """Plain http:// URLs are silently upgraded to https:// before fetching."""
        crawler, llm = _make_crawler()

        def _resolve_public(hostname, _, **__):
            return [(socket.AF_INET, None, None, None, ("93.184.216.34", 0))]

        mock_resp = MagicMock()
        mock_resp.content_type = "text/html"
        mock_resp.charset = "utf-8"
        mock_resp.url = MagicMock(__str__=lambda self: "https://example.com/")
        mock_resp.content.read = AsyncMock(return_value=b"<p>Great plumber</p>")
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.get.return_value = mock_resp
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("socket.getaddrinfo", side_effect=_resolve_public),
            patch("aiohttp.ClientSession", return_value=mock_session),
        ):
            html = await crawler._fetch_html("http://example.com/")

        # Should have been called with the HTTPS version
        call_url = mock_session.get.call_args[0][0]
        assert call_url.startswith("https://"), f"Expected https URL, got {call_url!r}"
        assert html is not None
        html_text, final_url = html  # now returns (html, final_url)
        assert final_url == "https://example.com/"

    async def test_ftp_url_returns_none(self) -> None:
        crawler, _ = _make_crawler()
        result = await crawler.extract_provider_info(
            url="ftp://example.com/file.html",
            provider_name="Acme",
            query="plumber",
        )
        assert result is None


# ---------------------------------------------------------------------------
# Private IP / SSRF guard
# ---------------------------------------------------------------------------


class TestPrivateIpGuard:
    async def test_localhost_ip_blocked(self) -> None:
        crawler, llm = _make_crawler()

        def _resolve_localhost(hostname, _, **__):
            return [(socket.AF_INET, None, None, None, ("127.0.0.1", 0))]

        with patch("socket.getaddrinfo", side_effect=_resolve_localhost):
            result = await crawler.extract_provider_info(
                url="https://internal-host.local/",
                provider_name="Acme",
                query="test",
            )

        assert result is None
        llm.generate.assert_not_called()

    async def test_rfc1918_ip_blocked(self) -> None:
        crawler, llm = _make_crawler()

        def _resolve_private(hostname, _, **__):
            return [(socket.AF_INET, None, None, None, ("192.168.1.100", 0))]

        with patch("socket.getaddrinfo", side_effect=_resolve_private):
            result = await crawler.extract_provider_info(
                url="https://internal.corp/",
                provider_name="Acme",
                query="test",
            )

        assert result is None
        llm.generate.assert_not_called()


# ---------------------------------------------------------------------------
# Network / timeout / content-type
# ---------------------------------------------------------------------------


class TestFetchBehaviour:
    async def test_timeout_returns_none(self) -> None:
        crawler, llm = _make_crawler()

        with patch(
            "aiohttp.ClientSession.get",
            side_effect=aiohttp.ServerTimeoutError(),
        ):
            with patch("socket.getaddrinfo", return_value=[(socket.AF_INET, None, None, None, ("93.184.216.34", 0))]):
                result = await crawler.extract_provider_info(
                    url="https://example.com/",
                    provider_name="Acme",
                    query="test",
                )

        assert result is None
        llm.generate.assert_not_called()

    async def test_non_html_content_type_returns_none(self) -> None:
        crawler, llm = _make_crawler()

        mock_resp = MagicMock()
        mock_resp.content_type = "application/pdf"
        mock_resp.content.read = AsyncMock(return_value=b"binary data")
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.get.return_value = mock_resp
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("socket.getaddrinfo", return_value=[(socket.AF_INET, None, None, None, ("93.184.216.34", 0))]),
            patch("aiohttp.ClientSession", return_value=mock_session),
        ):
            result = await crawler.extract_provider_info(
                url="https://example.com/brochure.pdf",
                provider_name="Acme",
                query="test",
            )

        assert result is None
        llm.generate.assert_not_called()


# ---------------------------------------------------------------------------
# HTML text extraction
# ---------------------------------------------------------------------------


class TestExtractText:
    def test_strips_tags(self) -> None:
        html = "<html><body><p>Hello <b>world</b></p></body></html>"
        assert _extract_text(html) == "Hello world"

    def test_skips_script_and_style(self) -> None:
        html = "<html><body><script>alert('x')</script><p>Visible</p><style>body{}</style></html>"
        assert _extract_text(html) == "Visible"

    def test_returns_full_text_without_truncation(self) -> None:
        long_text = "a " * 2000  # 4000 chars
        html = f"<p>{long_text}</p>"
        result = _extract_text(html)
        assert len(result) > 3000

    def test_collapses_whitespace(self) -> None:
        html = "<p>Hello   \n\n   World</p>"
        result = _extract_text(html)
        assert "  " not in result
        assert "Hello" in result
        assert "World" in result

    def test_extracts_title(self) -> None:
        html = "<html><head><title>Best Plumber Berlin</title></head><body><div id='app'></div></body></html>"
        result = _extract_text(html)
        assert "Best Plumber Berlin" in result

    def test_extracts_meta_description(self) -> None:
        html = (
            '<html><head>'
            '<meta name="description" content="We offer bespoke wedding cake services in Berlin.">'
            '</head><body><div id="root"></div></body></html>'
        )
        result = _extract_text(html)
        assert "bespoke wedding cake" in result

    def test_extracts_og_description(self) -> None:
        html = (
            '<html><head>'
            '<meta property="og:description" content="Top-rated tax advisors in Berlin since 1990.">'
            '</head><body></body></html>'
        )
        result = _extract_text(html)
        assert "tax advisors in Berlin" in result

    def test_extracts_jsonld_description(self) -> None:
        schema = {
            "@context": "https://schema.org",
            "@type": "LocalBusiness",
            "name": "Tortenmanufaktur Kalweit",
            "description": "Hand-crafted wedding cakes with pistachio and lemon tiers.",
            "serviceType": "Wedding Cake Bakery",
        }
        html = (
            f'<html><body>'
            f'<script type="application/ld+json">{json.dumps(schema)}</script>'
            f'<div id="app"></div>'
            f'</body></html>'
        )
        result = _extract_text(html)
        assert "Tortenmanufaktur Kalweit" in result
        assert "pistachio" in result
        assert "Wedding Cake Bakery" in result

    def test_extracts_jsonld_array(self) -> None:
        """JSON-LD can be an array of objects."""
        schemas = [
            {"@type": "WebSite", "name": "Acme Corp"},
            {"@type": "LocalBusiness", "description": "Professional tax advisory services."},
        ]
        html = (
            f'<html><body>'
            f'<script type="application/ld+json">{json.dumps(schemas)}</script>'
            f'</body></html>'
        )
        result = _extract_text(html)
        assert "Acme Corp" in result
        assert "tax advisory" in result

    def test_invalid_jsonld_is_ignored_gracefully(self) -> None:
        html = (
            '<html><body>'
            '<script type="application/ld+json">not valid json {{{</script>'
            '<p>Visible text</p>'
            '</body></html>'
        )
        result = _extract_text(html)
        assert "Visible text" in result

    def test_spa_with_only_meta_returns_text(self) -> None:
        """Simulates a JS-only SPA that has no body text but has meta/JSON-LD."""
        schema = {"@type": "LocalBusiness", "name": "Kalweit Confiserie", "description": "Fine pastry shop."}
        html = (
            '<html><head>'
            '<title>Kalweit</title>'
            '<meta name="description" content="Award-winning pastry and cake shop in Berlin.">'
            f'<script type="application/ld+json">{json.dumps(schema)}</script>'
            '</head><body><div id="root"></div></body></html>'
        )
        result = _extract_text(html)
        assert result  # must not be empty
        assert "Kalweit" in result
        assert "pastry" in result


# ---------------------------------------------------------------------------
# LLM extraction
# ---------------------------------------------------------------------------


class TestLlmExtract:
    async def test_valid_json_returns_dataclass(self) -> None:
        crawler, llm = _make_crawler()
        payload = {
            "services": ["Pipe repair", "Boiler install"],
            "specialities": "Emergency plumbing specialist",
            "portfolio_highlights": "Completed 200+ installs in 2023",
            "coverage_area": "Serving Berlin and Brandenburg",
        }
        llm.generate = AsyncMock(return_value=json.dumps(payload))

        result = await crawler._llm_extract(
            page_text="We repair pipes and install boilers.",
            provider_name="Acme Plumbing",
            query="plumber Berlin",
        )

        assert isinstance(result, WebCrawlResult)
        assert "Pipe repair" in result.services
        assert result.specialities == "Emergency plumbing specialist"
        assert result.coverage_area == "Serving Berlin and Brandenburg"

    async def test_json_with_markdown_fences_parsed(self) -> None:
        crawler, llm = _make_crawler()
        payload = {"services": ["Baking"], "specialities": "Wedding cakes", "portfolio_highlights": "", "coverage_area": ""}
        llm.generate = AsyncMock(return_value=f"```json\n{json.dumps(payload)}\n```")

        result = await crawler._llm_extract("page text", "Bakery", "cakes")

        assert isinstance(result, WebCrawlResult)
        assert "Baking" in result.services

    async def test_invalid_json_returns_none(self) -> None:
        crawler, llm = _make_crawler()
        llm.generate = AsyncMock(return_value="not json at all")

        result = await crawler._llm_extract("page text", "Acme", "query")

        assert result is None

    async def test_llm_exception_returns_none(self) -> None:
        crawler, llm = _make_crawler()
        llm.generate = AsyncMock(side_effect=Exception("LLM quota exceeded"))

        result = await crawler._llm_extract("page text", "Acme", "query")

        assert result is None

    async def test_services_capped_at_20(self) -> None:
        crawler, llm = _make_crawler()
        payload = {
            "services": [f"Service {i}" for i in range(30)],
            "specialities": "",
            "portfolio_highlights": "",
            "coverage_area": "",
        }
        llm.generate = AsyncMock(return_value=json.dumps(payload))

        result = await crawler._llm_extract("page text", "Acme", "query")

        assert result is not None
        assert len(result.services) == 20


# ---------------------------------------------------------------------------
# Email extraction
# ---------------------------------------------------------------------------


class TestExtractEmail:
    def test_extracts_mailto_href(self) -> None:
        html = '<a href="mailto:info@bakery.de">Contact us</a>'
        assert _extract_email(html) == "info@bakery.de"

    def test_prefers_mailto_over_plain_text(self) -> None:
        html = 'other@example.com <a href="mailto:info@bakery.de">contact</a>'
        assert _extract_email(html) == "info@bakery.de"

    def test_falls_back_to_plain_text(self) -> None:
        html = "<p>Contact: info@example.com</p>"
        assert _extract_email(html) == "info@example.com"

    def test_ignores_asset_like_paths_in_plain_text(self) -> None:
        # "banner@2x.png" is NOT a valid email address, so the regex won't
        # match it — confirm the real address is still returned.
        html = '<p><img src="banner@2x.png"> info@bakery.de</p>'
        assert _extract_email(html) == "info@bakery.de"

    def test_returns_empty_string_when_none_found(self) -> None:
        html = "<p>No contact info here.</p>"
        assert _extract_email(html) == ""

    def test_result_is_lowercased(self) -> None:
        html = '<a href="mailto:Info@Bakery.DE">Contact</a>'
        assert _extract_email(html) == "info@bakery.de"

    def test_strips_query_string_from_mailto(self) -> None:
        html = '<a href="mailto:info@bakery.de?subject=Hello">mail</a>'
        assert _extract_email(html) == "info@bakery.de"

    def test_no_false_positive_from_file_extension(self) -> None:
        html = '<script src="bundle.min.js"></script>'
        assert _extract_email(html) == ""


# ---------------------------------------------------------------------------
# Link scoring / filtering
# ---------------------------------------------------------------------------


class TestScoreAndFilterLinks:
    def test_extracts_relative_links(self) -> None:
        html = '<a href="/about">About</a><a href="/services">Services</a>'
        result = _score_and_filter_links(html, "https://example.com/", max_links=5)
        assert "https://example.com/about" in result
        assert "https://example.com/services" in result

    def test_rejects_external_links(self) -> None:
        html = '<a href="https://other.com/page">External</a>'
        result = _score_and_filter_links(html, "https://example.com/", max_links=5)
        assert result == []

    def test_rejects_anchor_only_links(self) -> None:
        html = '<a href="#section">Jump</a>'
        result = _score_and_filter_links(html, "https://example.com/", max_links=5)
        assert result == []

    def test_rejects_asset_links(self) -> None:
        html = '<a href="/logo.png">Logo</a><a href="/about">About</a>'
        result = _score_and_filter_links(html, "https://example.com/", max_links=5)
        assert "https://example.com/logo.png" not in result
        assert "https://example.com/about" in result

    def test_deduplicates_same_url(self) -> None:
        html = '<a href="/contact">A</a><a href="/contact">B</a>'
        result = _score_and_filter_links(html, "https://example.com/", max_links=5)
        assert len([u for u in result if u.endswith("/contact")]) == 1

    def test_excludes_base_url(self) -> None:
        html = '<a href="/">Home</a><a href="/about">About</a>'
        result = _score_and_filter_links(html, "https://example.com/", max_links=5)
        assert "https://example.com" not in result
        assert "https://example.com/about" in result

    def test_high_value_paths_ranked_first(self) -> None:
        html = '<a href="/gallery">Gallery</a><a href="/kontakt">Kontakt</a>'
        result = _score_and_filter_links(html, "https://example.com/", max_links=5)
        # /kontakt matches a high-value term; /gallery does not
        assert result.index("https://example.com/kontakt") < result.index(
            "https://example.com/gallery"
        )

    def test_respects_max_links(self) -> None:
        html = "".join(f'<a href="/page{i}">P{i}</a>' for i in range(10))
        result = _score_and_filter_links(html, "https://example.com/", max_links=3)
        assert len(result) <= 3

    def test_empty_html_returns_empty(self) -> None:
        assert _score_and_filter_links("", "https://example.com/", max_links=5) == []

    def test_rejects_feed_and_rss_paths(self) -> None:
        html = (
            '<a href="/feed/">Feed</a>'
            '<a href="/comments/feed">Comments feed</a>'
            '<a href="/rss">RSS</a>'
            '<a href="/sitemap">Sitemap</a>'
            '<a href="/atom">Atom</a>'
            '<a href="/kontakt">Kontakt</a>'
        )
        result = _score_and_filter_links(html, "https://example.com/", max_links=5)
        assert result == ["https://example.com/kontakt"]

    def test_rejects_wordpress_admin_paths(self) -> None:
        html = (
            '<a href="/wp-admin/edit.php">WP Admin</a>'
            '<a href="/wp-json/wp/v2/posts">WP API</a>'
            '<a href="/checkout">Checkout</a>'
            '<a href="/leistungen">Services</a>'
        )
        result = _score_and_filter_links(html, "https://example.com/", max_links=5)
        assert result == ["https://example.com/leistungen"]


# ---------------------------------------------------------------------------
# Multi-page crawl integration
# ---------------------------------------------------------------------------


class TestMultiPageCrawl:
    async def test_fetches_subpages_when_links_present(self) -> None:
        """extract_provider_info fetches linked high-value subpages."""
        landing_html = (
            "<html><body>"
            '<a href="/kontakt">Kontakt</a>'
            "<p>Bakery landing page.</p>"
            "</body></html>"
        )
        contact_html = "<html><body><p>Contact info on subpage.</p></body></html>"

        crawler, llm = _make_crawler()
        fetched: list[str] = []

        async def mock_fetch(url: str) -> tuple[str, str] | None:
            fetched.append(url)
            if url == "https://example.com/":
                return landing_html, "https://example.com/"
            if url == "https://example.com/kontakt":
                return contact_html, "https://example.com/kontakt"
            return None

        payload = {
            "services": ["Baking"],
            "specialities": "Cakes",
            "portfolio_highlights": "",
            "coverage_area": "",
        }
        llm.generate = AsyncMock(return_value=json.dumps(payload))

        with patch.object(crawler, "_fetch_html", side_effect=mock_fetch):
            result = await crawler.extract_provider_info(
                "https://example.com/", "Bakery", "wedding cake"
            )

        assert result is not None
        assert "https://example.com/" in fetched
        assert "https://example.com/kontakt" in fetched

    async def test_succeeds_when_subpage_fetch_fails(self) -> None:
        """A subpage fetch failure must not prevent the landing-page result."""
        landing_html = (
            "<html><body>"
            '<a href="/kontakt">Kontakt</a>'
            "<p>Landing content here.</p>"
            "</body></html>"
        )

        crawler, llm = _make_crawler()

        async def mock_fetch(url: str) -> tuple[str, str] | None:
            if url == "https://example.com/":
                return landing_html, "https://example.com/"
            raise TimeoutError("subpage timeout")

        payload = {
            "services": ["Baking"],
            "specialities": "",
            "portfolio_highlights": "",
            "coverage_area": "",
        }
        llm.generate = AsyncMock(return_value=json.dumps(payload))

        with patch.object(crawler, "_fetch_html", side_effect=mock_fetch):
            result = await crawler.extract_provider_info(
                "https://example.com/", "Bakery", "wedding cake"
            )

        assert result is not None
        assert result.services == ["Baking"]

    async def test_redirect_url_used_for_link_extraction(self) -> None:
        """When a redirect changes hostname (e.g. www → no-www), links are still found."""
        # Landing page served at cake-artist.de but Google Places URL was www.cake-artist.de.
        # All in-page links use the no-www hostname.
        landing_html = (
            "<html><body>"
            '<a href="https://cake-artist.de/kontakt">Kontakt</a>'
            "<p>Landing content.</p>"
            "</body></html>"
        )
        contact_html = '<html><body><a href="mailto:info@cake-artist.de">Email</a></body></html>'

        crawler, llm = _make_crawler()
        fetched: list[str] = []

        async def mock_fetch(url: str) -> tuple[str, str] | None:
            fetched.append(url)
            # Simulate www → no-www redirect: original url is www, final url is no-www
            if url == "https://www.cake-artist.de/":
                return landing_html, "https://cake-artist.de/"  # final URL differs
            if url == "https://cake-artist.de/kontakt":
                return contact_html, "https://cake-artist.de/kontakt"
            return None

        payload = {"services": ["Cakes"], "specialities": "Wedding cakes",
                   "portfolio_highlights": "", "coverage_area": ""}
        llm.generate = AsyncMock(return_value=json.dumps(payload))

        with patch.object(crawler, "_fetch_html", side_effect=mock_fetch):
            result = await crawler.extract_provider_info(
                "https://www.cake-artist.de/", "Cake Artist", "wedding cake"
            )

        assert result is not None
        assert "https://cake-artist.de/kontakt" in fetched
        assert result.email == "info@cake-artist.de"

    async def test_fallback_probe_when_no_links_found(self) -> None:
        """When the landing page has no internal links, common paths are probed."""
        # Simulates a Wix SPA bootstrap page — no useful links in server HTML.
        landing_html = "<html><body><p>Spa page with no links.</p></body></html>"
        about_html = '<html><body><p>Email us: info@lottastorten.de</p></body></html>'

        crawler, llm = _make_crawler()
        fetched: list[str] = []

        async def mock_fetch(url: str) -> tuple[str, str] | None:
            fetched.append(url)
            if url == "https://www.lottastorten.de/":
                return landing_html, "https://www.lottastorten.de/"
            if url == "https://www.lottastorten.de/about":
                return about_html, "https://www.lottastorten.de/about"
            return None  # all other probe paths return 404 / non-HTML

        payload = {"services": ["Cakes"], "specialities": "Custom cakes",
                   "portfolio_highlights": "", "coverage_area": ""}
        llm.generate = AsyncMock(return_value=json.dumps(payload))

        with patch.object(crawler, "_fetch_html", side_effect=mock_fetch):
            result = await crawler.extract_provider_info(
                "https://www.lottastorten.de/", "Lottas Torten", "wedding cake"
            )

        assert result is not None
        # Fallback probes should include /kontakt and /about (from _CONTACT_PROBE_PATHS)
        assert any("/kontakt" in u or "/about" in u for u in fetched)
        assert result.email == "info@lottastorten.de"
