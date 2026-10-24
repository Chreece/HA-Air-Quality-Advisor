"""README images must resolve in HACS's Markdown viewer, not only GitHub."""
from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
RAW_ROOT = "https://raw.githubusercontent.com/Chreece/HA-Home-Environment-Manager/"
VALID_REFS = ("main", "v0.6.0b1", "v0.6.0b2", "v0.6.0b3", "v0.6.0b4", "v0.6.0b5", "v0.6.0b6", "v0.6.0b7", "v0.6.0b8", "v0.6.0b9", "v0.6.0b10", "v0.6.0b11", "v0.6.0b12", "v0.6.0b13", "v0.6.0b14", "v0.6.0b15", "v0.6.0b16", "v0.6.0b17", "v0.6.0b18", "v0.6.0b21", "v0.6.0b22", "v0.6.0b23", "v0.6.0b24", "v0.6.0b25")
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
            matched = next((tag for tag in VALID_REFS if src.startswith(
                RAW_ROOT + tag + "/" + LOCAL_ASSET_ROOT)), None)
            assert matched is not None, (
                f"Repository image must point to the stable branch or pinned beta: {src}"
            )
            relative = unquote(url.path).removeprefix(
                "/Chreece/HA-Home-Environment-Manager/" + matched + "/"
            )
            assert relative.startswith(LOCAL_ASSET_ROOT)
            file = ROOT / relative
            assert file.is_file() and file.stat().st_size > 100, (
                f"Broken README image: {src}"
            )
            assert file.suffix.lower() in {".png", ".jpg", ".jpeg", ".svg"}
            local_images += 1

    assert local_images == 13, "Check all repository-owned README images"
