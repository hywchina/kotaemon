"""Token counting that can operate without downloading tokenizer assets."""

from __future__ import annotations

import os
import re
from functools import lru_cache, partial
from typing import Callable

Tokenize = Callable[[str], list]
_TOKEN_PATTERN = re.compile(r"[\u3400-\u9fff]|[A-Za-z0-9_]+|[^\s]")


def approximate_tokenize(text: str, **_: object) -> list[str]:
    """Return deterministic local tokens suitable for length-based splitting."""

    return _TOKEN_PATTERN.findall(text)


@lru_cache(maxsize=1)
def get_tokenizer() -> Tokenize:
    """Return tiktoken when allowed, otherwise a network-free local tokenizer."""

    disabled = os.getenv("KH_DISABLE_TOKENIZER_DOWNLOADS", "false").lower()
    if disabled in {"1", "true", "yes", "on"}:
        return approximate_tokenize

    try:
        import tiktoken

        return partial(
            tiktoken.encoding_for_model("gpt-3.5-turbo").encode,
            allowed_special=set(),
            disallowed_special="all",
        )
    except Exception:
        return approximate_tokenize
