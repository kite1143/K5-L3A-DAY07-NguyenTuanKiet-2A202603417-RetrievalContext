"""Chuẩn hoá và tách từ dùng chung cho lexical retrieval.

Corpus là tiếng Anh (Jowett), nhưng tokenizer vẫn xử lý Unicode NFC để không
làm hỏng dấu tiếng Việt nếu sau này đổi corpus.
"""
from __future__ import annotations

import re
import unicodedata

TOKEN_RE = re.compile(r"[\w']+")

STOPWORDS = frozenset(
    """
    a an the and or but if then than that this these those of in on at to for from by with without
    as is are was were be been being am do does did doing have has had having not no nor so such
    it its he she they them his her their we you your i me my mine our ours us who whom which what
    when where why how all any both each few more most other some only own same too very can will
    just should now about above after again against below between into once out over under until up
    down during before while here there again further also may might must shall would could
    """.split()
)


def normalize(text: str) -> str:
    return unicodedata.normalize("NFC", text)


def tokenize(text: str, *, drop_stopwords: bool = True) -> list[str]:
    """Trả token đã casefold; giữ dấu nháy để 'one's' không thành 'one s'."""
    tokens = TOKEN_RE.findall(normalize(text).casefold())
    if drop_stopwords:
        return [token for token in tokens if token not in STOPWORDS]
    return tokens
