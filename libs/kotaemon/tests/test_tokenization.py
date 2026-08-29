from kotaemon.utils.tokenization import approximate_tokenize


def test_approximate_tokenizer_handles_chinese_and_english() -> None:
    tokens = approximate_tokenize("患者 blood pressure 120/80。")

    assert tokens[:2] == ["患", "者"]
    assert "blood" in tokens
    assert "pressure" in tokens
    assert "120" in tokens
