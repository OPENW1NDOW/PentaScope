import json
import logging
import os
import secrets
from datetime import datetime, timezone, timedelta
from pathlib import Path
from pydantic import BaseModel

logger = logging.getLogger(__name__)

_BEIJING = timezone(timedelta(hours=8))


class TraceWriter:
    def __init__(self, trace_id: str, base_dir: Path):
        self.trace_id = trace_id
        self.dir = Path(base_dir) / trace_id
        self._written: set[str] = set()

    @staticmethod
    def new_trace_id(base_dir: Path) -> str:
        base = Path(base_dir)
        while True:
            ts = datetime.now(_BEIJING).strftime("%Y%m%d-%H%M%S")
            tid = f"{ts}-{secrets.token_hex(3)}"  # 3 bytes -> 6 hex
            if not (base / tid).exists():
                return tid
