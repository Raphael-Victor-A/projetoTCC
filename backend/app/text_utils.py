"""Normalizacao de texto compartilhada.

Usada para deduplicar questoes: acento, caixa e pontuacao nao deveriam
transformar a mesma pergunta em duas linhas diferentes no banco.
"""

import hashlib
import re
import unicodedata


def normalize_statement(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def statement_hash(text: str) -> str:
    return hashlib.sha256(normalize_statement(text).encode("utf-8")).hexdigest()[:32]
