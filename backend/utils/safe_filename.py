import re
import unicodedata


def safe_filename(name: str) -> str:
    """Strip accents, then collapse anything outside [A-Za-z0-9._-] to '_'.
    Supabase Storage rejects non-ASCII bytes in object keys outright
    (InvalidKey) — and plain re.sub(r"[^\\w.\\-]", ...) isn't enough on its
    own because Python's \\w is Unicode-aware and lets 'é'/'è' etc. through
    unescaped, which is exactly what French filenames and course titles are
    full of in this app."""
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^\w.\-]", "_", ascii_name, flags=re.ASCII)
