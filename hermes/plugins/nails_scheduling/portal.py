from urllib.parse import quote

PORTAL_URL = "https://de.funti.cc:8446/web/"
PORTAL_CONTINUE_URL = "https://de.funti.cc:8446/web/api/auth/continue"


def build_login_url(continuation_token: str) -> str:
    return f"{PORTAL_CONTINUE_URL}?token={quote(continuation_token, safe='')}"
