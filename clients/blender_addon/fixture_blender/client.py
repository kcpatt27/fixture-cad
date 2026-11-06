from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from . import config


class HarnessClient:
    def __init__(
        self,
        base_url: str | None = None,
        timeout: float | None = None,
    ) -> None:
        self.base_url = (base_url or config.HARNESS_URL).rstrip("/")
        self.timeout = timeout if timeout is not None else config.REQUEST_TIMEOUT

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        data = None
        headers = {"Accept": "application/json"}
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = resp.read().decode("utf-8")
                return json.loads(body) if body else {}
        except urllib.error.HTTPError as exc:
            err_body = exc.read().decode("utf-8", errors="replace")
            try:
                parsed = json.loads(err_body)
            except json.JSONDecodeError:
                parsed = {"error": {"code": "unknown", "message": err_body}}
            raise RuntimeError(str(parsed.get("error", parsed))) from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"harness unreachable: {exc.reason}") from exc

    def health(self) -> dict[str, Any]:
        return self._request("GET", "/health")

    def send_chat(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/chat", payload)

    def send_tool_result(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/tools/result", payload)
