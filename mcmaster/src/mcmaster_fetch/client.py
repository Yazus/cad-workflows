"""Thin client for the McMaster-Carr Product Information API.

API reference: https://www.mcmaster.com/help/api
Every request carries the client certificate McMaster-Carr issues to
approved customers, plus a bearer token from ``/v1/login``.
"""

from __future__ import annotations

import re
import time
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse

import requests

from .config import Credentials

BASE_URL = "https://api.mcmaster.com"
_RETRY_STATUSES = {429, 503}


class McMasterError(Exception):
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


class McMasterClient:
    def __init__(
        self,
        credentials: Credentials,
        base_url: str = BASE_URL,
        session: requests.Session | None = None,
        max_retries: int = 3,
        timeout: float = 60,
        sleep=time.sleep,
    ):
        self.credentials = credentials
        self.base_url = base_url.rstrip("/")
        self.session = session or requests.Session()
        self.session.cert = credentials.requests_cert
        self.max_retries = max_retries
        self.timeout = timeout
        self._sleep = sleep
        self._token: str | None = None

    # -- session ---------------------------------------------------------

    def __enter__(self) -> "McMasterClient":
        self.login()
        return self

    def __exit__(self, *exc) -> None:
        self.logout()

    def login(self) -> None:
        resp = self._request(
            "POST",
            "/v1/login",
            json={"UserName": self.credentials.username, "Password": self.credentials.password},
            auth=False,
        )
        self._token = resp.json()["AuthToken"]

    def logout(self) -> None:
        if not self._token:
            return
        try:
            self._request("POST", "/v1/logout")
        except McMasterError:
            pass  # token is dropped either way; it also expires after 24h
        finally:
            self._token = None

    # -- products --------------------------------------------------------

    def subscribe(self, part_number: str) -> dict:
        """Add a part to this account's subscriptions; returns its product info.

        The API only serves product data for subscribed parts. Subscribing an
        already-subscribed part is harmless.
        """
        resp = self._request("PUT", "/v1/products", json={"URL": _product_url(part_number)})
        return resp.json()

    def unsubscribe(self, part_number: str) -> None:
        self._request("DELETE", "/v1/products", json={"URL": _product_url(part_number)})

    def get_product(self, part_number: str) -> dict:
        return self._request("GET", f"/v1/products/{part_number}").json()

    def get_price(self, part_number: str) -> list[dict]:
        return self._request("GET", f"/v1/products/{part_number}/price").json()

    def download(self, link: str, dest_dir: Path) -> Path:
        """Download a file from a product ``Links`` value (CAD, image, datasheet)."""
        resp = self._request("GET", link, stream=True)
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / _filename(resp, link)
        with dest.open("wb") as f:
            for chunk in resp.iter_content(chunk_size=64 * 1024):
                f.write(chunk)
        return dest

    # -- plumbing --------------------------------------------------------

    def _request(self, method: str, path: str, auth: bool = True, **kwargs) -> requests.Response:
        url = urljoin(self.base_url + "/", path.lstrip("/"))
        headers = kwargs.pop("headers", {})
        if auth:
            if not self._token:
                raise McMasterError("Not logged in")
            headers["Authorization"] = f"Bearer {self._token}"

        for attempt in range(self.max_retries + 1):
            resp = self.session.request(method, url, headers=headers, timeout=self.timeout, **kwargs)
            if resp.status_code in _RETRY_STATUSES and attempt < self.max_retries:
                self._sleep(_retry_delay(resp, attempt))
                continue
            break

        if not resp.ok:
            raise McMasterError(_error_message(method, path, resp), resp.status_code)
        return resp


def _product_url(part_number: str) -> str:
    return f"https://mcmaster.com/{part_number}"


def _retry_delay(resp: requests.Response, attempt: int) -> float:
    retry_after = resp.headers.get("Retry-After", "")
    if retry_after.isdigit():
        return float(retry_after)
    return float(2 ** (attempt + 1))


def _error_message(method: str, path: str, resp: requests.Response) -> str:
    detail = ""
    try:
        body = resp.json()
        if isinstance(body, dict):
            detail = body.get("ErrorDescription") or body.get("ErrorMessage") or ""
    except ValueError:
        detail = resp.text[:200]
    msg = f"{method} {path} failed with HTTP {resp.status_code}"
    return f"{msg}: {detail}" if detail else msg


def _filename(resp: requests.Response, link: str) -> str:
    disposition = resp.headers.get("Content-Disposition", "")
    match = re.search(r"filename\*?=(?:UTF-8'')?\"?([^\";]+)\"?", disposition)
    name = unquote(match.group(1)) if match else unquote(Path(urlparse(link).path).name)
    # Never let a server-supplied name escape the destination folder.
    name = Path(name.replace("\\", "/")).name
    return name if name not in ("", ".", "..") else "download"
