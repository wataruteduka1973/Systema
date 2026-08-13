"""オークション時刻に関する純粋なドメインロジック。"""

import re
from datetime import datetime, timezone


def parse_duration_seconds(value: object) -> float:
    """「2日5時間20分」を秒へ変換する。解釈不能な値は無限大を返す。"""
    if not isinstance(value, str):
        return float("inf")

    text = value.replace(" ", "")
    days = int(match.group(1)) if (match := re.search(r"(\d+)日", text)) else 0
    hours = int(match.group(1)) if (match := re.search(r"(\d+)時間", text)) else 0
    minutes = int(match.group(1)) if (match := re.search(r"(\d+)分", text)) else 0
    if not (days or hours or minutes) and text not in {"0分", "0秒"}:
        return float("inf")
    return float(days * 86400 + hours * 3600 + minutes * 60)


def format_remaining_time(end_time: object, *, now: datetime | None = None) -> str:
    """絶対終了日時を「日・時間・分」表記へ変換する。"""
    if not end_time or end_time == "N/A":
        return "N/A"
    text = str(end_time).strip()
    if re.search(r"[日時分秒]", text):
        return text

    try:
        end = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return "N/A"

    current = now or datetime.now(end.tzinfo or timezone.utc)
    remaining_seconds = max(int((end - current).total_seconds()), 0)
    days, remainder = divmod(remaining_seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, _ = divmod(remainder, 60)
    parts = []
    if days:
        parts.append(f"{days}日")
    if hours:
        parts.append(f"{hours}時間")
    if minutes:
        parts.append(f"{minutes}分")
    return "".join(parts) if parts else "0分"
