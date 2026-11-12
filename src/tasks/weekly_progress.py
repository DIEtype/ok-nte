import re
from datetime import UTC, datetime, timedelta, timezone
from hashlib import blake2s

from ok.util.config import Config

SWEEP_EXHAUSTED = "anomaly_sweep_exhausted"
FLUFF_COLLECTED = "affinity_gift_claimed"
MAMMON_COLLECTED = "mammon_reward_claimed"

_CN_SERVER_TZ = timezone(timedelta(hours=8))
_UID = re.compile(r"UID\s*[:：]\s*([0-9]{9,14})", re.IGNORECASE)


def week_start(now: datetime) -> str:
    server_day = (now.astimezone(_CN_SERVER_TZ) - timedelta(hours=5)).date()
    return (server_day - timedelta(days=server_day.weekday())).isoformat()


class WeeklyProgress:
    """Store confirmed completions by account and server week."""

    def __init__(self, task):
        self.account = self._read_account_key(task)
        self.config = (
            Config(
                "WeeklyTaskProgress",
                {SWEEP_EXHAUSTED: {}, FLUFF_COLLECTED: {}, MAMMON_COLLECTED: {}},
            )
            if self.account
            else None
        )
        self.started_week = week_start(datetime.now(UTC))

    @staticmethod
    def _read_account_key(task) -> str | None:
        for box in task.ocr(0.0, 0.974, 0.108, 1.0):
            if match := _UID.fullmatch(box.name or ""):
                return blake2s(match[1].encode("ascii"), digest_size=16).hexdigest()
        return None

    def is_done(self, key: str) -> bool:
        return self.config is not None and (
            self.config[key].get(self.account) == week_start(datetime.now(UTC))
        )

    def mark_done(self, key: str) -> None:
        if self.config is not None and self.started_week == week_start(datetime.now(UTC)):
            self.config[key] = {**self.config[key], self.account: self.started_week}
