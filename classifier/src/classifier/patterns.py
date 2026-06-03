import re
from urllib.parse import unquote

# OWASP CRS v4 inspired patterns (942xxx SQLi, 941xxx XSS)
SQLI_PATTERNS = [
    re.compile(r"(?i)(\bselect\b.+\bfrom\b|\bunion\b.+\bselect\b)"),
    re.compile(r"(?i)('\s*(or|and)\s*'?\d)"),
    re.compile(r"(?i)(--\s*$|#\s*$|/\*.*\*/)"),
    re.compile(r"(?i)\b(drop|insert|delete|update)\b.+\b(table|into)\b"),
    re.compile(r"(?i)'\s*or\s*'1'\s*=\s*'1"),
]

XSS_PATTERNS = [
    re.compile(r"(?i)<script[\s>]"),
    re.compile(r"(?i)javascript\s*:"),
    re.compile(r"(?i)on(error|load|click|mouseover)\s*="),
    re.compile(r"(?i)<iframe"),
    re.compile(r"(?i)document\.(cookie|write)"),
]

SENSITIVE_PATHS = {"/admin", "/.env", "/config", "/wp-login", "/.git", "/.aws/credentials"}


def check_sqli(uri: str) -> bool:
    decoded = unquote(uri)
    return any(p.search(decoded) for p in SQLI_PATTERNS)


def check_xss(uri: str) -> bool:
    decoded = unquote(uri)
    return any(p.search(decoded) for p in XSS_PATTERNS)


def check_recon_path(uri: str) -> str | None:
    path = uri.split("?", 1)[0]
    for sensitive in SENSITIVE_PATHS:
        if path.startswith(sensitive) or sensitive in path:
            return sensitive
    return None
