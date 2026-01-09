import argparse
import json
import mimetypes
import os
import sys
from typing import Any, Dict

import requests


def check_health(base_url: str, timeout: float) -> Dict[str, Any]:
    url = f"{base_url.rstrip('/')}/health"
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def transcribe(base_url: str, audio_path: str, timeout: float) -> Dict[str, Any]:
    if not os.path.isfile(audio_path):
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    url = f"{base_url.rstrip('/')}/asr"
    guessed_type = mimetypes.guess_type(audio_path)[0] or "audio/wav"

    with open(audio_path, "rb") as f:
        files = {"file": (os.path.basename(audio_path), f, guessed_type)}
        resp = requests.post(url, files=files, timeout=timeout)
        resp.raise_for_status()
        return resp.json()


def main() -> None:
    parser = argparse.ArgumentParser(description="Simple client to test local ASR service")
    parser.add_argument("audio", nargs="?", help="Path to audio file to transcribe")
    parser.add_argument(
        "--base-url",
        default="http://0.0.0.0:8002",
        help="Base URL of the ASR service (default: http://0.0.0.0:8002)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="HTTP request timeout in seconds (default: 30)",
    )
    parser.add_argument(
        "--health",
        action="store_true",
        help="Only run the /health check",
    )

    args = parser.parse_args()

    try:
        if args.health:
            data = check_health(args.base_url, args.timeout)
            print(json.dumps(data, ensure_ascii=False, indent=2))
            return

        if not args.audio:
            raise SystemExit("Audio path is required unless --health is used")

        data = transcribe(args.base_url, args.audio, args.timeout)
        print(json.dumps(data, ensure_ascii=False, indent=2))
    except requests.HTTPError as exc:
        # Print server response to help debugging failures
        print(f"HTTP error: {exc}")
        if exc.response is not None:
            print(f"Status: {exc.response.status_code}")
            print(f"Body: {exc.response.text}")
        sys.exit(1)
    except Exception as exc:
        print(f"Error: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
