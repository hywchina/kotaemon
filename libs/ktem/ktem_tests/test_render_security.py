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


def test_markmap_dependencies_are_loaded_sequentially() -> None:
    bootstrap = (ASSETS_DIR / "vendor" / "markmap-bootstrap-0.16.1.js").read_text(
        encoding="utf-8"
    )
    app_source = (Path(__file__).parents[1] / "ktem" / "app.py").read_text(
        encoding="utf-8"
    )
    chat_source = (
        Path(__file__).parents[1] / "ktem" / "pages" / "chat" / "__init__.py"
    ).read_text(encoding="utf-8")
    main_js = (ASSETS_DIR / "js" / "main.js").read_text(encoding="utf-8")
    main_css = (ASSETS_DIR / "css" / "main.css").read_text(encoding="utf-8")

    dependencies = [
        "d3-7.8.5.min.js",
        "markmap-lib-0.16.1.min.js",
        "markmap-view-0.16.0.min.js",
        "markmap-toolbar-0.16.0.min.js",
    ]
    positions = [bootstrap.index(dependency) for dependency in dependencies]

    assert positions == sorted(positions)
    assert "for (const dependency of dependencies)" in bootstrap
    assert "await loadScript(dependency)" in bootstrap
    assert "manual: true" in bootstrap
    assert "window.ktemRenderMindmap" in bootstrap
    assert "window.ktemMarkmapReady" in bootstrap
    assert "markmap-bootstrap-0.16.1.js" in app_source
    assert "asset_path.stat().st_mtime_ns" in app_source
    assert "window.ktemMarkmapReady || Promise.resolve()" in chat_source
    assert "window.ktemRenderMindmap(markmapDiv)" in chat_source
    assert 'classList.toggle("is-expanded", expanded)' in chat_source
    assert 'sourceTree.getBBox()' in chat_source
    assert 'markmapDiv?.querySelector("svg")' in chat_source
    assert 'element.offsetParent !== null' in chat_source
    assert 'window.__ktemMindmapActionsBound' in chat_source
    assert 'target?.closest("#mindmap-export")' in chat_source
    assert 'downloadLink.download = "思维导图.html"' in chat_source
    assert "if (!child) return null;" in main_js
    assert "div.markmap > svg" in main_css
    assert "div.markmap.is-expanded" in main_css


def test_chat_content_uses_one_shared_visual_width() -> None:
    main_css = (ASSETS_DIR / "css" / "main.css").read_text(encoding="utf-8")

    message_width_rule = main_css.split(
        "#main-chat-bot .message-wrap {", maxsplit=1
    )[1].split("}", maxsplit=1)[0]
    composer_width_rule = main_css.split("#chat-composer-row {", maxsplit=1)[1].split(
        "}", maxsplit=1
    )[0]
    settings_width_rule = main_css.split(
        "#chat-settings-expand {", maxsplit=1
    )[1].split("}", maxsplit=1)[0]

    assert "width: calc(100% - 16px);" in message_width_rule
    assert "max-width: 964px;" in message_width_rule
    assert "margin-left: max(8px, calc((100% - 948px) / 2));" in (
        message_width_rule
    )
    for sibling_rule in (composer_width_rule, settings_width_rule):
        assert "width: calc(100% - 32px);" in sibling_rule
        assert "max-width: 964px;" in sibling_rule
        assert "max(8px, calc((100% - 964px) / 2))" in sibling_rule


def test_empty_chat_placeholder_is_centered_inside_conversation_canvas() -> None:
    main_css = (ASSETS_DIR / "css" / "main.css").read_text(encoding="utf-8")

    placeholder_rule = main_css.split(
        "#main-chat-bot .placeholder-container .message-wrap {", maxsplit=1
    )[1].split("}", maxsplit=1)[0]
    placeholder_content_rule = main_css.split(
        "#main-chat-bot .placeholder-container .message-wrap > center {", maxsplit=1
    )[1].split("}", maxsplit=1)[0]

    assert "justify-content: center;" in placeholder_rule
    assert "justify-items: center;" in placeholder_rule
    assert "margin-right: auto;" in placeholder_rule
    assert "margin-left: auto;" in placeholder_rule
    assert "width: 100%;" in placeholder_content_rule
