"""Relay authenticated browser audio to the private speech service."""

import asyncio
import json
import logging
import secrets
from dataclasses import dataclass
from threading import Lock
from uuid import uuid4

from cachetools import TTLCache
from decouple import config
from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect, WebSocketState
from websockets.client import connect
from websockets.exceptions import WebSocketException

SERVICE_URL = config("KH_SPEECH_URL", default="")
SERVICE_KEY = config("KH_SPEECH_API_KEY", default="")
ENABLED = bool(SERVICE_URL and SERVICE_KEY) and not config(
    "KH_DEMO_MODE", default=False, cast=bool
)
MAX_AUDIO_BYTES = 300 * 16000 * 2
LOGGER = logging.getLogger(__name__)


@dataclass
class Recording:
    owner: str
    browser_session: str
    conversation: str | None
    id: str
    connected: bool = False
    text: str = ""


class RecordingTickets:
    def __init__(self):
        self.records = TTLCache(maxsize=128, ttl=900)
        self.lock = Lock()

    def issue(self, owner, browser_session, conversation):
        token = secrets.token_urlsafe(32)
        with self.lock:
            self.records[token] = Recording(
                owner, browser_session, conversation, uuid4().hex
            )
        return token

    def claim(self, token):
        with self.lock:
            record = self.records.get(token)
            if record is None or record.connected:
                return None
            record.connected = True
            return record

    def result(self, token, owner, browser_session):
        with self.lock:
            record = self.records.get(token)
            if (
                record
                and record.owner == owner
                and record.browser_session == browser_session
            ):
                return record

    def finish(self, token, text):
        with self.lock:
            record = self.records.get(token)
            if record:
                record.text = text


tickets = RecordingTickets()


async def _forward_audio(browser, worker):
    total = 0
    stopped = False
    while True:
        message = await asyncio.wait_for(
            browser.receive(), timeout=100 if stopped else 15
        )
        if message["type"] == "websocket.disconnect":
            return
        if not stopped and message.get("text") == "stop":
            stopped = True
            await worker.send("stop")
            continue
        chunk = message.get("bytes")
        if stopped or not chunk or len(chunk) % 2 or len(chunk) > 32000:
            raise ValueError("Invalid audio frame")
        total += len(chunk)
        if total > MAX_AUDIO_BYTES:
            raise ValueError("Recording limit exceeded")
        await worker.send(chunk)


async def _forward_transcript(browser, worker, token):
    async for payload in worker:
        message = json.loads(payload)
        if message["type"] == "partial":
            await browser.send_json(message)
        elif message["type"] == "final":
            lines = []
            for segment in message["segments"]:
                speaker = segment["speaker"]
                label = f"说话人 {speaker}：" if speaker is not None else ""
                lines.append(label + segment["text"])
            text = "\n".join(lines)
            tickets.finish(token, text)
            await browser.send_json({"type": "final", "text": text})
            return
    raise ValueError("Speech service ended before final transcript")


async def speech_socket(browser: WebSocket):
    await browser.accept()
    try:
        first = await asyncio.wait_for(browser.receive(), timeout=5)
    except asyncio.TimeoutError:
        await browser.close(code=1008)
        return
    token = first.get("text", "")
    if not token or len(token) != 43 or not tickets.claim(token):
        if first["type"] != "websocket.disconnect":
            await browser.close(code=1008)
        return

    tasks = set()
    try:
        async with connect(
            SERVICE_URL,
            extra_headers={"Authorization": f"Bearer {SERVICE_KEY}"},
            open_timeout=5,
            close_timeout=1,
            max_size=1_048_576,
        ) as worker:
            await browser.send_json({"type": "ready"})
            tasks = {
                asyncio.create_task(_forward_audio(browser, worker)),
                asyncio.create_task(_forward_transcript(browser, worker, token)),
            }
            done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                task.result()
    except (
        OSError,
        ValueError,
        KeyError,
        WebSocketException,
        WebSocketDisconnect,
        asyncio.TimeoutError,
    ) as exc:
        LOGGER.warning("Speech session ended (%s)", type(exc).__name__)
    finally:
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        if browser.client_state is WebSocketState.CONNECTED:
            try:
                await browser.close()
            except WebSocketDisconnect:
                pass


def mount_speech(app, prefix=""):
    if ENABLED:
        app.add_api_websocket_route(f"{prefix}/asr/live", speech_socket)
