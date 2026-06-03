import json
from dataclasses import dataclass


@dataclass
class LogEntry:
    time: str
    ip: str
    method: str
    uri: str
    status: int
    bytes: int
    referer: str
    ua: str
    duration_us: int


def parse_line(line: str) -> LogEntry | None:
    line = line.strip()
    if not line:
        return None
    try:
        data = json.loads(line)
    except json.JSONDecodeError:
        return None
    try:
        return LogEntry(
            time=str(data.get("time", "")),
            ip=str(data.get("ip", "-")),
            method=str(data.get("method", "GET")),
            uri=str(data.get("uri", "/")),
            status=int(data.get("status", 0)),
            bytes=int(data.get("bytes", 0) or 0),
            referer=str(data.get("referer", "-")),
            ua=str(data.get("ua", "-")),
            duration_us=int(data.get("duration_us", 0) or 0),
        )
    except (TypeError, ValueError):
        return None
