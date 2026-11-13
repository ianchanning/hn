"""SQLite-backed Hacker News author reputation cache with 7-day TTL.

Persists Firebase/Algolia author karma, account creation timestamp, and submission
activity locally so repeat or cross-thread analyses avoid redundant network round-trips.
"""

from collections.abc import Callable, Iterable, Mapping
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import AbstractContextManager, closing
import json
import os
from pathlib import Path
import sqlite3
import ssl
import time
from typing import Any
from urllib.parse import quote
import urllib.request

DATA_DIR = Path(__file__).resolve().parent / "data"
DEFAULT_DB_PATH = DATA_DIR / "author_cache.db"
DEFAULT_TTL_SECONDS = 7 * 86400.0
USER_AGENT = "hn-epistemic-observatory/2.0 (+https://news.ycombinator.com)"


def build_ssl_context() -> ssl.SSLContext:
    """Create a verified SSLContext honoring system and corporate CA bundle variables."""
    for env_key in ("SSL_CERT_FILE", "REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE"):
        ca_path = os.environ.get(env_key)
        if ca_path and Path(ca_path).is_file():
            return ssl.create_default_context(cafile=ca_path)
    macos_cert = Path("/etc/ssl/cert.pem")
    if macos_cert.is_file():
        return ssl.create_default_context(cafile=str(macos_cert))
    return ssl.create_default_context()


def fetch_hn_author_network(
    username: str,
    *,
    timeout: float = 10.0,
    ssl_context: ssl.SSLContext | None = None,
) -> dict[str, Any] | None:
    """Fetch a single HN user profile from Firebase v0 with Algolia v1 fallback."""
    ctx = ssl_context or build_ssl_context()
    encoded = quote(username, safe="")

    # Primary: Firebase official HN user endpoint (exact submitted array length + created + karma)
    fb_url = f"https://hacker-news.firebaseio.com/v0/user/{encoded}.json"
    try:
        req = urllib.request.Request(fb_url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            raw = json.loads(resp.read().decode("utf-8", errors="replace"))
        if isinstance(raw, dict) and raw.get("id"):
            submitted = raw.get("submitted")
            sub_cnt = len(submitted) if isinstance(submitted, list) else int(raw.get("submitted_count", 1) or 1)
            return {
                "id": str(raw["id"]),
                "created": int(raw.get("created") or 0),
                "karma": int(raw.get("karma") or 0),
                "submitted_count": max(1, sub_cnt),
                "has_about": bool(raw.get("about")),
            }
    except Exception:
        pass

    # Fallback: Algolia HN users endpoint
    alg_url = f"https://hn.algolia.com/api/v1/users/{encoded}"
    try:
        req = urllib.request.Request(alg_url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            raw = json.loads(resp.read().decode("utf-8", errors="replace"))
        if isinstance(raw, dict) and raw.get("username"):
            sub_cnt = int(raw.get("submission_count") or 0) + int(raw.get("comment_count") or 0)
            return {
                "id": str(raw["username"]),
                "created": int(raw.get("created_at_i") or 0),
                "karma": int(raw.get("karma") or 0),
                "submitted_count": max(1, sub_cnt),
                "has_about": bool(raw.get("about")),
            }
    except Exception:
        return None
    return None


class AuthorCache:
    """SQLite cache for HN author reputation profiles with configurable TTL (default 7 days)."""

    def __init__(
        self,
        db_path: Path = DEFAULT_DB_PATH,
        ttl_seconds: float = DEFAULT_TTL_SECONDS,
    ) -> None:
        self.db_path = Path(db_path)
        self.ttl_seconds = float(ttl_seconds)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> AbstractContextManager[sqlite3.Connection]:
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.execute("PRAGMA journal_mode=WAL")
        return closing(conn)

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS authors (
                    username TEXT PRIMARY KEY,
                    created INTEGER NOT NULL,
                    karma INTEGER NOT NULL,
                    submitted_count INTEGER NOT NULL,
                    has_about INTEGER NOT NULL,
                    fetched_at REAL NOT NULL
                )
                """
            )
            conn.commit()

    @staticmethod
    def _is_valid_username(username: str) -> bool:
        return bool(username) and not username.startswith("[")

    def count(self) -> int:
        """Return total number of author rows currently stored in SQLite."""
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) FROM authors").fetchone()
            return int(row[0]) if row else 0

    def get(self, username: str, *, now: float | None = None) -> dict[str, Any] | None:
        """Return cached author dict if present and fresher than TTL, else None."""
        res = self.get_many([username], now=now)
        return res.get(username)

    def get_many(
        self,
        usernames: Iterable[str],
        *,
        now: float | None = None,
    ) -> dict[str, dict[str, Any]]:
        """Fetch all non-expired cached profiles for the given usernames."""
        clean = sorted({u for u in usernames if self._is_valid_username(u)})
        if not clean:
            return {}
        ts_now = time.time() if now is None else float(now)
        min_fetched_at = ts_now - self.ttl_seconds

        found: dict[str, dict[str, Any]] = {}
        with self._connect() as conn:
            # Query in chunks of 450 to stay well below SQLite's variable limit
            for start in range(0, len(clean), 450):
                batch = clean[start : start + 450]
                placeholders = ",".join("?" for _ in batch)
                rows = conn.execute(
                    f"""
                    SELECT username, created, karma, submitted_count, has_about, fetched_at
                    FROM authors
                    WHERE username IN ({placeholders}) AND fetched_at > ?
                    """,
                    [*batch, min_fetched_at],
                ).fetchall()
                for uname, created, karma, sub_cnt, has_about, _fetched_at in rows:
                    found[str(uname)] = {
                        "id": str(uname),
                        "created": int(created),
                        "karma": int(karma),
                        "submitted_count": max(1, int(sub_cnt)),
                        "has_about": bool(has_about),
                    }
        return found

    def upsert_many(
        self,
        profiles: Mapping[str, Mapping[str, Any]],
        *,
        fetched_at: float | None = None,
    ) -> int:
        """Insert or update multiple author profiles atomically."""
        ts = time.time() if fetched_at is None else float(fetched_at)
        payload: list[tuple[str, int, int, int, int, float]] = []
        for uname, prof in profiles.items():
            if not self._is_valid_username(uname):
                continue
            payload.append(
                (
                    uname,
                    int(prof.get("created") or 0),
                    int(prof.get("karma") or 0),
                    max(1, int(prof.get("submitted_count") or 1)),
                    1 if prof.get("has_about") else 0,
                    ts,
                )
            )
        if not payload:
            return 0
        with self._connect() as conn:
            conn.executemany(
                """
                INSERT INTO authors (username, created, karma, submitted_count, has_about, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(username) DO UPDATE SET
                    created = excluded.created,
                    karma = excluded.karma,
                    submitted_count = excluded.submitted_count,
                    has_about = excluded.has_about,
                    fetched_at = excluded.fetched_at
                """,
                payload,
            )
            conn.commit()
        return len(payload)

    def seed_from_json(self, json_path: Path, *, fetched_at: float | None = None) -> int:
        """Seed SQLite cache from a static JSON mapping such as `data/authors.json`."""
        if not json_path.is_file():
            return 0
        raw = json.loads(json_path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return 0
        return self.upsert_many(raw, fetched_at=fetched_at)

    def purge_expired(self, *, now: float | None = None) -> int:
        """Delete rows older than `ttl_seconds` and return deleted row count."""
        ts_now = time.time() if now is None else float(now)
        cutoff = ts_now - self.ttl_seconds
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM authors WHERE fetched_at <= ?", (cutoff,))
            conn.commit()
            return int(cur.rowcount or 0)

    def resolve_authors(
        self,
        usernames: Iterable[str],
        *,
        now: float | None = None,
        offline: bool = False,
        max_fetch: int = 1500,
        max_workers: int = 16,
        fetcher: Callable[[str], dict[str, Any] | None] | None = None,
    ) -> dict[str, dict[str, Any]]:
        """Return cached profiles within TTL and concurrently fetch any misses when online."""
        clean = sorted({u for u in usernames if self._is_valid_username(u)})
        cached = self.get_many(clean, now=now)
        if offline:
            return cached

        missing = [u for u in clean if u not in cached][:max_fetch]
        if not missing:
            return cached

        ssl_ctx = build_ssl_context()
        fetch_fn = fetcher or (lambda u: fetch_hn_author_network(u, ssl_context=ssl_ctx))

        fresh: dict[str, dict[str, Any]] = {}
        workers = max(1, min(max_workers, len(missing)))
        if workers == 1:
            for uname in missing:
                prof = fetch_fn(uname)
                if prof is not None:
                    fresh[uname] = prof
        else:
            with ThreadPoolExecutor(max_workers=workers) as pool:
                fut_map = {pool.submit(fetch_fn, uname): uname for uname in missing}
                for fut in as_completed(fut_map):
                    uname = fut_map[fut]
                    try:
                        prof = fut.result()
                    except Exception:
                        prof = None
                    if prof is not None:
                        fresh[uname] = prof

        if fresh:
            self.upsert_many(fresh, fetched_at=now)
            cached.update(fresh)
        return cached
