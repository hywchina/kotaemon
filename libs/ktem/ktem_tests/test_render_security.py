from pathlib import Path

from kotaemon.base import RetrievedDocument

from ktem.utils.render import Render, get_header


ASSETS_DIR = Path(__file__).parents[1] / "ktem" / "assets"


def test_markdown_render_escapes_raw_html() -> None:
    rendered = Render.table('<img src=x onerror="alert(1)">')

    assert "<img" not in rendered
    assert "&lt;img" in rendered


def test_document_header_escapes_file_name() -> None:
    doc = RetrievedDocument(
        text="safe",
        metadata={"file_name": "<script>alert(1)</script>", "page_label": 1},
    )

    header = get_header(doc)

    assert "<script>" not in header
    assert "&lt;script&gt;" in header


def test_highlight_escapes_content_and_identifier() -> None:
    rendered = Render.highlight("<b>unsafe</b>", "x' onclick='alert(1)")

    assert "<b>" not in rendered
    assert "onclick='" not in rendered
    assert "&lt;b&gt;unsafe&lt;/b&gt;" in rendered


def test_evidence_search_does_not_rebuild_untrusted_html() -> None:
    main_js = (ASSETS_DIR / "js" / "main.js").read_text(encoding="utf-8")
    chat_source = (
        Path(__file__).parents[1] / "ktem" / "pages" / "chat" / "__init__.py"
    ).read_text(encoding="utf-8")

    assert "p.innerHTML = p_content.replace" not in main_js
    assert "mark.outerHTML = mark.innerText" not in main_js
    assert 'createTreeWalker(container, NodeFilter.SHOW_TEXT)' in main_js
    assert "setTimeout(fullTextSearch, 100)" in chat_source
