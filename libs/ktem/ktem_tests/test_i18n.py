from ktem.utils.i18n import translate_choices, translate_ui_text


def test_translate_known_text_and_preserve_extension_text() -> None:
    assert translate_ui_text("Language") == "回答语言"
    assert translate_ui_text("Custom extension option") == "Custom extension option"


def test_translate_choices_preserves_values() -> None:
    assert translate_choices(["all", ("Chinese", "zh")]) == [
        ("全部", "all"),
        ("中文", "zh"),
    ]
