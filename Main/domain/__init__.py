"""外部I/Oに依存しないSystemaのドメインロジック。"""

from .auction_time import format_remaining_time, parse_duration_seconds

__all__ = ["format_remaining_time", "parse_duration_seconds"]
