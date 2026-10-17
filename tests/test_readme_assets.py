"""README images must resolve in HACS's Markdown viewer, not only GitHub."""
from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
RAW_ROOT = "https://raw.githubusercontent.com/Chreece/HA-Air-Quality-Advisor/main/"
LOCAL_ASSET_ROOT = ".github/assets/"


class ImageCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.sources: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "img":
            src = dict(attrs).get("src")
            if src:
                self.sources.append(src)


def test_all_readme_images_use_absolute_https_urls_for_hacs() -> None:
    parser = ImageCollector()
    parser.feed(README.read_text(encoding="utf-8"))
    assert len(parser.sources) >= 9, "README should include banner and dashboard images"

    local_images = 0
    for src in parser.sources:
        url = urlparse(src)
        assert url.scheme == "https" and url.netloc, (
            f"Relative image URL cannot reliably render in HACS: {src}"
        )
        if url.netloc == "raw.githubusercontent.com":
            assert src.startswith(RAW_ROOT + LOCAL_ASSET_ROOT), (
                f"Repository image unexpectedly points elsewhere: {src}"
            )
            relative = unquote(url.path).removeprefix(
                "/Chreece/HA-Air-Quality-Advisor/main/"
            )
            assert relative.startswith(LOCAL_ASSET_ROOT)
            file = ROOT / relative
            assert file.is_file() and file.stat().st_size > 100, (
                f"Broken README image: {src}"
            )
            assert file.suffix.lower() in {".png", ".jpg", ".jpeg", ".svg"}
            local_images += 1

    assert local_images == 9, "Check all repository-owned README images"
