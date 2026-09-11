"""Metadados de origem (canal / lead) embutidos em evaluation_json das mesas."""

from __future__ import annotations

from json import dumps as json_dumps
from json import loads as json_loads

CHANNEL_LABELS = {
    "SITE_CHAT": "Site (chat)",
    "SDC_DESK": "Mesa SDC",
    "FLASH_DESK": "Mesa Flash",
    "QUITCON_DESK": "Mesa QuitCon",
}


def channel_label(channel: str | None) -> str | None:
    if not channel:
        return None
    return CHANNEL_LABELS.get(channel, channel.replace("_", " ").title())


def evaluation_meta(evaluation_json: str | None) -> dict:
    channel = None
    lead_id = None
    if evaluation_json:
        try:
            data = json_loads(evaluation_json)
            if isinstance(data, dict):
                raw_channel = data.get("channel")
                if raw_channel:
                    channel = str(raw_channel).strip() or None
                raw_lead = data.get("lead_id")
                if raw_lead:
                    lead_id = str(raw_lead).strip() or None
        except (TypeError, ValueError):
            pass
    return {
        "source_channel": channel,
        "source_channel_label": channel_label(channel),
        "lead_id": lead_id,
    }


def evaluation_json_with_meta(result: dict, *, channel: str, lead_id: str | None = None) -> str:
    payload = {**result, "channel": channel}
    if lead_id:
        payload["lead_id"] = lead_id
    return json_dumps(payload, ensure_ascii=False)
