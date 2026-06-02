import json
import logging
import os
import secrets
from datetime import datetime, timezone, timedelta
from pathlib import Path

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

    def _atomic_write_json(self, path: Path, obj) -> None:
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(
            json.dumps(obj, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        os.replace(tmp, path)

    @staticmethod
    def _serialize(data):
        if isinstance(data, list):
            return [m.model_dump(mode="json") for m in data]
        return data.model_dump(mode="json")

    def _next_version(self, stage: str) -> int:
        existing = list(self.dir.glob(f"{stage}_v*.json"))
        nums = []
        for p in existing:
            suffix = p.stem[len(stage) + 2:]  # 去掉 "{stage}_v"
            if suffix.isdigit():
                nums.append(int(suffix))
        return (max(nums) + 1) if nums else 1

    def save_stage(self, stage: str, data) -> None:
        try:
            self.dir.mkdir(parents=True, exist_ok=True)
            target = self.dir / f"{stage}.json"
            if target.exists():
                n = self._next_version(stage)
                os.replace(target, self.dir / f"{stage}_v{n}.json")
            obj = self._serialize(data)
            self._atomic_write_json(target, obj)
            self._written.add(stage)
        except Exception as e:  # noqa: BLE001 — 落盘是辅助能力，绝不阻塞主流程
            logger.warning("[trace] 落盘失败 stage=%s trace=%s: %s", stage, self.trace_id, e)

    def save_meta(self, meta: dict) -> None:
        try:
            self.dir.mkdir(parents=True, exist_ok=True)
            self._atomic_write_json(self.dir / "meta.json", meta)
        except Exception as e:  # noqa: BLE001
            logger.warning("[trace] meta 落盘失败 trace=%s: %s", self.trace_id, e)
