from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence

import httpx

from ..core.config import get_settings
from ..models import LineRecipient, LineRecipientType

logger = logging.getLogger(__name__)


class LineNotificationError(RuntimeError):
    pass


@dataclass(frozen=True)
class LineNotifierConfig:
    channel_access_token: str
    push_endpoint: str


def parse_recipient(value: Optional[str]) -> Optional[LineRecipient]:
    """Parse `type:identifier|label` formatted string into a recipient model."""
    if not value:
        return None

    base, _, label = value.partition("|")
    type_value, sep, identifier = base.partition(":")
    if not sep or not identifier:
        raise ValueError(f"Invalid LINE target format: {value}")
    try:
        target_type = LineRecipientType(type_value.strip())
    except ValueError as exc:  # pragma: no cover - defensive
        raise ValueError(f"Unsupported LINE target type: {type_value}") from exc

    return LineRecipient(
        type=target_type,
        identifier=identifier.strip(),
        label=label.strip() or None,
    )


def resolve_config(
    channel_access_token: Optional[str] = None,
    api_base_url: Optional[str] = None,
) -> Optional[LineNotifierConfig]:
    settings = get_settings()
    token = (channel_access_token or settings.line_channel_access_token or "").strip()
    if not token:
        return None
    base_url = (api_base_url or settings.line_api_base_url).rstrip("/")
    return LineNotifierConfig(
        channel_access_token=token,
        push_endpoint=f"{base_url}/message/push",
    )


class LineNotifier:
    def __init__(self, config: Optional[LineNotifierConfig] = None) -> None:
        self._config = config or resolve_config()
        if not self._config:
            raise LineNotificationError("LINE channel access token is not configured")

    async def notify_text(
        self,
        recipients: Sequence[LineRecipient],
        message: str,
        *,
        raise_on_error: bool = False,
    ) -> List[str]:
        if not message.strip():
            logger.debug("Skip sending empty LINE message")
            return []

        errors: List[str] = []
        for recipient in recipients:
            try:
                await self._send_single(recipient, message)
            except LineNotificationError as exc:
                logger.error("LINE push failed for %s (%s): %s", recipient.identifier, recipient.type, exc)
                errors.append(str(exc))

        if errors and raise_on_error:
            raise LineNotificationError(errors[0])

        return errors

    async def _send_single(self, recipient: LineRecipient, message: str) -> None:
        payload = {
            "to": recipient.identifier,
            "messages": [
                {
                    "type": "text",
                    "text": message,
                }
            ],
        }
        headers = {
            "Authorization": f"Bearer {self._config.channel_access_token}",
            "Content-Type": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
                response = await client.post(self._config.push_endpoint, json=payload, headers=headers)
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text
            raise LineNotificationError(
                f"HTTP {exc.response.status_code} from LINE: {detail}"
            ) from exc
        except httpx.HTTPError as exc:
            raise LineNotificationError("Failed to reach LINE API") from exc


def default_recipients() -> Sequence[LineRecipient]:
    target = parse_recipient(get_settings().line_default_target)
    return [target] if target else []


def dedupe_recipients(recipients: Iterable[Optional[LineRecipient]]) -> List[LineRecipient]:
    """Preserve order while removing duplicate targets."""
    observed = set()
    ordered: List[LineRecipient] = []
    for recipient in recipients:
        if not recipient:
            continue
        key = (recipient.type, recipient.identifier)
        if key in observed:
            continue
        observed.add(key)
        ordered.append(recipient)
    return ordered
