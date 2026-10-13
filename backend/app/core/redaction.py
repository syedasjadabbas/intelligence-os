"""Helpers for keeping credentials out of log output."""
import re

from sqlalchemy.engine import make_url

# scheme://user:password@host  ->  scheme://***@host
_URL_USERINFO = re.compile(r"(?P<scheme>[A-Za-z][A-Za-z0-9+.\-]*://)[^/@\s]+@")
# password=secret / pwd: secret / passwd='secret'  ->  password=***
_KEY_VALUE_SECRET = re.compile(
    r"(?P<key>\b(?:password|passwd|pwd)\b\s*[=:]\s*)(?P<quote>['\"]?)[^\s'\"&;,)]+(?P=quote)",
    re.IGNORECASE,
)


def describe_database_url(url: str) -> str:
    """
    Returns a log-safe description of a database URL: driver, host, port and
    database name. Username, password and query parameters (which may carry
    credentials such as ``?password=``) are never included.
    """
    try:
        parsed = make_url(url)
    except Exception:
        return "<unparseable database URL>"

    credentials = "***@" if (parsed.username or parsed.password) else ""
    host = parsed.host or ""
    port = f":{parsed.port}" if parsed.port else ""
    database = f"/{parsed.database}" if parsed.database else ""
    return f"{parsed.drivername}://{credentials}{host}{port}{database}"


def redact_credentials(text: str) -> str:
    """Masks URL user-info and password key/value pairs inside free-form text."""
    text = _URL_USERINFO.sub(lambda m: f"{m.group('scheme')}***@", text)
    return _KEY_VALUE_SECRET.sub(lambda m: f"{m.group('key')}***", text)
