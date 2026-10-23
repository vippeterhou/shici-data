from __future__ import annotations

import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Callable


RAW_URL = "https://raw.githubusercontent.com/{repository}/{commit}/{path}"


def git_source_fetcher(
    repository: Path,
    commit: str,
) -> Callable[[str], bytes]:
    def fetch(path: str) -> bytes:
        result = subprocess.run(
            ["git", "-C", str(repository), "show", f"{commit}:{path}"],
            check=True,
            capture_output=True,
        )
        return result.stdout

    return fetch


def remote_source_fetcher(
    repository: str,
    commit: str,
) -> Callable[[str], bytes]:
    def fetch(path: str) -> bytes:
        encoded_path = urllib.parse.quote(path)
        url = RAW_URL.format(
            repository=repository,
            commit=commit,
            path=encoded_path,
        )
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "shici-data-source-audit/1.0"},
        )
        for attempt in range(4):
            try:
                with urllib.request.urlopen(
                    request,
                    timeout=30,
                ) as response:
                    return response.read()
            except (urllib.error.URLError, OSError, TimeoutError):
                if attempt == 3:
                    raise
                time.sleep(0.25 * (2**attempt))
        raise RuntimeError("unreachable source fetch retry state")

    return fetch
