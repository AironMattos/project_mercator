from __future__ import annotations

import re
import unicodedata


def slugify(texto: str) -> str:
    normalizado = unicodedata.normalize("NFKD", texto)
    sem_acento = normalizado.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", sem_acento.lower()).strip("-")
