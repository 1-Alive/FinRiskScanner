from __future__ import annotations

import os
import socket
from urllib.parse import urlparse

from openai import OpenAI

from classifier import load_dotenv_file


def mask_secret(value: str) -> str:
    if not value:
        return "MISSING"
    if len(value) <= 10:
        return "*" * len(value)
    return f"{value[:6]}...{value[-4:]}"


def tcp_check(host: str, port: int, timeout: float = 8.0) -> tuple[bool, str]:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True, "ok"
    except Exception as exc:  # noqa: BLE001
        return False, f"{type(exc).__name__}: {exc}"


def main() -> None:
    load_dotenv_file()

    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    model = os.environ.get("OPENAI_MODEL", "gpt-5.4-mini").strip()
    base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").strip() or "https://api.openai.com/v1"
    http_proxy = os.environ.get("HTTP_PROXY", "").strip()
    https_proxy = os.environ.get("HTTPS_PROXY", "").strip()

    parsed = urlparse(base_url)
    host = parsed.hostname or "api.openai.com"
    port = parsed.port or (443 if parsed.scheme == "https" else 80)

    print("OpenAI connectivity test")
    print(f"API key: {mask_secret(api_key)}")
    print(f"Model: {model}")
    print(f"Base URL: {base_url}")
    print(f"HTTP_PROXY: {'SET' if http_proxy else 'MISSING'}")
    print(f"HTTPS_PROXY: {'SET' if https_proxy else 'MISSING'}")

    tcp_ok, tcp_message = tcp_check(host, port)
    print(f"TCP check to {host}:{port}: {'PASS' if tcp_ok else 'FAIL'}")
    if tcp_message != "ok":
        print(tcp_message)

    if not api_key:
        print("Result: OPENAI_API_KEY is missing.")
        return

    client = OpenAI(api_key=api_key, base_url=base_url)

    try:
        response = client.responses.create(
            model=model,
            reasoning={"effort": "low"},
            input="Reply with JSON only: {\"status\":\"ok\"}",
        )
        print("API request: PASS")
        output_text = getattr(response, "output_text", "") or ""
        print(output_text or "[empty output_text]")
    except Exception as exc:  # noqa: BLE001
        print("API request: FAIL")
        print(f"{type(exc).__name__}: {exc}")


if __name__ == "__main__":
    main()
