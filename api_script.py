"""Consume a public REST API and load the result into a DataFrame.

Kept as a self-contained example of the consuming side of REST: a session with
retries, timeouts, status checks, per-item error handling and a tabular result.

    python api_script.py
"""

import logging

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

API_BASE = "https://api.github.com"
TIMEOUT = 5  # seconds


def build_session() -> requests.Session:
    """Return a session that retries idempotent requests with backoff.

    A bare `requests.get` gives up on the first hiccup; retrying on 429 and 5xx
    is what makes the script usable against a rate-limited API.
    """
    retries = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(["GET"]),
    )
    session = requests.Session()
    session.mount("https://", HTTPAdapter(max_retries=retries))
    session.headers.update({"Accept": "application/vnd.github+json"})
    return session


def get_users_data(users: list[str]) -> pd.DataFrame:
    """Fetch public profile data for each user. Failures are skipped, not fatal."""
    session = build_session()
    results = []

    for user in users:
        try:
            response = session.get(f"{API_BASE}/users/{user}", timeout=TIMEOUT)
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.RequestException as error:
            logger.error("Could not fetch %s: %s", user, error)
            continue

        results.append(
            {
                "user": data["login"],
                "name": data.get("name"),
                "public_repos": data["public_repos"],
                "followers": data["followers"],
            }
        )

    return pd.DataFrame(results)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    users = ["octocat", "torvalds", "gvanrossum"]
    df = get_users_data(users)
    print(df.to_string(index=False))
