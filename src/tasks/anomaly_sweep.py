import re
from dataclasses import dataclass
from unicodedata import normalize

from ok import CannotFindException

from src.tasks.weekly_progress import SWEEP_EXHAUSTED, WeeklyProgress

_HOUSE = "金都云邸"
_BUTLER = re.compile(r"^(?:Mr[.．]?\s*)?尤加利$", re.IGNORECASE)
_QUOTA = re.compile(r"探索次数\s*:\s*([0-9]{1,2})\s*/\s*([0-9]{1,2})")


@dataclass(frozen=True)
class SweepQuota:
    remaining: int
    total: int

    @classmethod
    def read(cls, text):
        match = _QUOTA.fullmatch(normalize("NFKC", text).strip())
        if match:
            remaining, total = map(int, match.groups())
            if 0 <= remaining <= total <= 10 and total > 0:
                return cls(remaining, total)
        return None


class AnomalySweep:
    def __init__(self, task):
        self.task = task

    def check(self) -> int | None:
        """Return confirmed remaining uses, or None if the panel could not be read."""
        task = self.task
        task.ensure_main()
        progress = WeeklyProgress(task)
        if progress.is_done(SWEEP_EXHAUSTED):
            task.log_info("本周已确认管家探索次数用完, 跳过房产")
            return 0

        try:
            quota = self._open_panel()
        except CannotFindException:
            quota = None
        if not quota:
            task.log_warning("未确认管家探索次数, 继续常规副本")
            task.ensure_main()
            return None

        task.log_info(f"管家探索剩余 {quota.remaining}/{quota.total} 次")
        if quota.remaining == 0:
            progress.mark_done(SWEEP_EXHAUSTED)
        task.ensure_main()
        return quota.remaining

    def _read_quota(self) -> SweepQuota | None:
        names = self.task.ocr(0.068, 0.086, 0.239, 0.152)
        return SweepQuota.read(" ".join(box.name or "" for box in names))

    def _open_panel(self) -> SweepQuota | None:
        task = self.task
        if not self._teleport_home():
            return None
        if not self._butler_prompt():
            if not task.walk_to_box(
                self._butler_name, end_condition=self._butler_prompt, time_out=8, y_offset=-0.12
            ):
                return None
        task.send_key("f", after_sleep=0.8)

        def advance_dialogue():
            if task.ocr(0.429, 0.731, 0.571, 0.798, match=_BUTLER):
                task.send_key("space", interval=0.8)

        return task.wait_until(
            self._read_quota, post_action=advance_dialogue, time_out=25, settle_time=0.4
        ) or None

    def _teleport_home(self) -> bool:
        task = self.task
        if not task.open_house_panel():
            return False
        house = task.wait_ocr(
            0.012,
            0.151,
            0.153,
            0.890,
            match=re.compile(f"^{_HOUSE}$"),
            time_out=3,
            raise_if_not_found=False,
        )
        if not house:
            return False
        task.operate_click(house[0])
        if not task.wait_ocr(
            0.661,
            0.364,
            0.948,
            0.428,
            match=re.compile(_HOUSE),
            time_out=3,
            raise_if_not_found=False,
        ):
            return False
        task.operate_click(0.888, 0.951, after_sleep=0.5)
        return task.click_traval_button(raise_if_not_found=False) and bool(
            task.wait_in_team(time_out=300, settle_time=1, raise_if_not_found=False)
        )

    def _butler_name(self):
        return self.task.ocr(0.06, 0.18, 0.90, 0.48, match=_BUTLER)

    def _butler_prompt(self):
        return self.task.ocr(0.591, 0.453, 0.754, 0.653, match=_BUTLER)
