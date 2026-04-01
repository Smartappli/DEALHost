from __future__ import annotations

import asyncio
import json
from typing import Any

from django.conf import settings


async def _publish(subject: str, payload: dict[str, Any]) -> None:
    if not settings.NATS["ENABLED"]:
        return

    from nats.aio.client import Client as NATS

    client = NATS()
    await client.connect(settings.NATS["URL"])
    try:
        await client.publish(subject, json.dumps(payload).encode("utf-8"))
        await client.flush()
    finally:
        await client.close()


def publish(subject: str, payload: dict[str, Any]) -> None:
    try:
        asyncio.run(_publish(subject=subject, payload=payload))
    except RuntimeError:
        # Fallback for environments that already run an event loop.
        loop = asyncio.get_event_loop()
        loop.run_until_complete(_publish(subject=subject, payload=payload))
