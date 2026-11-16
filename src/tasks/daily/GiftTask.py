import re

import cv2
import numpy as np
from ok import CannotFindException, TaskDisabledException

from src.gifts import GiftDb
from src.gifts.affinity import MAX_LEVEL, AffinityProgress, parse_affinity
from src.gifts.GiftManager import GiftManager
from src.gifts.layout import GIFT_LAYOUT
from src.gifts.restock import restock_message
from src.Labels import Labels
from src.tasks.BaseNTETask import BaseNTETask
from src.tasks.NTEOneTimeTask import NTEOneTimeTask
from src.utils import image_utils as iu


class GiftTask(NTEOneTimeTask, BaseNTETask):
    """Give first-page gifts to configured characters."""

    MAX_TOTAL_GIFTS = 10
    MAX_GIFTS_PER_CHARACTER = 3
    NAME_MATCH_THRESHOLD = 0.82
    GIFT_MATCH_THRESHOLD = 0.80
    NAME_RATIO = GIFT_LAYOUT.name_ratio
    GIFT_FIRST_RATIO = GIFT_LAYOUT.gift_first_ratio
    GIFT_COLUMNS = GIFT_LAYOUT.gift_columns
    GIFT_ROWS = GIFT_LAYOUT.gift_rows
    GIFT_COLUMN_STEP = GIFT_LAYOUT.gift_column_step
    GIFT_ROW_STEP = GIFT_LAYOUT.gift_row_step
    UNLIMIT_ICON_X_OFFSET_RATIO = GIFT_LAYOUT.unlimited_icon_x_offset_ratio
    UNLIMIT_ICON_Y_OFFSET_RATIO = GIFT_LAYOUT.unlimited_icon_y_offset_ratio
    UNLIMIT_ICON_WIDTH_REDUCTION_RATIO = GIFT_LAYOUT.unlimited_icon_width_reduction_ratio
    CHARACTER_SLOT_X = GIFT_LAYOUT.character_slot_x
    CHARACTER_SLOT_YS = GIFT_LAYOUT.character_slot_ys
    SIDEBAR_BOX = GIFT_LAYOUT.sidebar_box
    SIDEBAR_SCROLL_X = GIFT_LAYOUT.sidebar_scroll_x
    SIDEBAR_SCROLL_Y = GIFT_LAYOUT.sidebar_scroll_y
    SIDEBAR_SCROLL_STEP = GIFT_LAYOUT.sidebar_scroll_step
    SIDEBAR_RESET_STEP = GIFT_LAYOUT.sidebar_reset_step
    MAX_SIDEBAR_PAGES = GIFT_LAYOUT.max_sidebar_pages
    SEND_BUTTON = GIFT_LAYOUT.send_button
    COUNTER_BOX = GIFT_LAYOUT.counter_box
    COUNTER_RE = re.compile(r"(?<!\d)([0-3])\s*/\s*3(?!\d)")
    DAILY_COUNTER_RE = re.compile(r"今日还[能可]赠送(10|[0-9])次礼物")
    STOCK_RE = re.compile(r"^[1-9][0-9]*$")
    AFFINITY_RE = re.compile(r"^[+＋]?\s*400$")
    MODE_CAPTURE = "capture"
    MODE_SCAN = "scan"
    MODE_RUN = "run"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "羁遇赠礼"
        self.visible = False
        self.manager = GiftManager()
        self.mode: str | None = None
        self.capture_profile_id: str | None = None
        self.capture_frame = None
        self.capture_name = ""
        self.capture_blocked_slots: tuple[int, ...] = ()
        self.capture_error = ""
        self.scan_result: tuple[int, int] | None = None
        self.scan_error = ""

    def capture_profile(self, profile_id: str | None) -> None:
        self.mode = self.MODE_CAPTURE
        self.capture_profile_id = profile_id
        self.capture_frame = None
        self.capture_name = ""
        self.capture_blocked_slots = ()
        self.capture_error = ""

    def run_gift_mode(self) -> None:
        self.mode = self.MODE_RUN

    def request_character_scan(self) -> None:
        self.mode = self.MODE_SCAN
        self.scan_result = None
        self.scan_error = ""

    def _capture_profile(self) -> None:

        frame = self.frame
        if frame is None or not getattr(frame, "size", 0):
            self.capture_error = self.tr("没有可用的游戏画面")
            return

        if self._read_character_gift_remaining(frame=frame) is None:
            self.capture_error = self.tr("请先打开目标角色的赠礼页")
            return

        name = self.tr("未命名角色")
        try:
            name = self._read_character_name(frame=frame) or name
        except Exception as error:
            self.log_debug(f"gift capture name OCR failed: {type(error).__name__}")

        blocked_slots = []
        try:
            blocked_slots = [
                index
                for index, badge_box in enumerate(self.get_unlimit_gift_boxes())
                if self.find_one("unlimit_gift", box=badge_box, frame=frame)
            ]
        except Exception as error:
            self.log_debug(f"gift capture unlimited-gift detection failed: {type(error).__name__}")
        self.capture_frame = frame
        self.capture_name = name
        self.capture_blocked_slots = tuple(blocked_slots)

    def _report(self, message: str) -> None:
        self.log_info(message)

    def run(self):
        mode = self.mode or self.MODE_RUN
        try:
            super().run()
            if mode == self.MODE_CAPTURE:
                self._capture_profile()
            elif mode == self.MODE_SCAN:
                self._discover_characters()
            else:
                self.do_run()
        except TaskDisabledException:
            if mode == self.MODE_CAPTURE:
                self.capture_error = self.tr("任务已停止")
            elif mode == self.MODE_SCAN:
                self.scan_error = self.tr("任务已停止")
            raise
        except Exception as e:
            if mode == self.MODE_CAPTURE:
                self.capture_error = str(e).strip() or e.__class__.__name__
            elif mode == self.MODE_SCAN:
                self.scan_error = str(e).strip() or self.tr("无法扫描角色")
            else:
                self.screenshot("gift_task_failure")
                self.log_error("GiftTask error", e)
            raise
        finally:
            self.mode = None

    def do_run(self) -> bool:
        summary = self.run_gifts()
        return not summary["failed"]

    def run_gifts(self) -> dict:
        profiles = self.manager.get_enabled_profiles()
        summary = {"success": 0, "skipped": [], "failed": []}

        if not profiles:
            self.log_info("No enabled gift profile has a gift selection")
            return summary

        self._report(f"开始赠礼，共 {len(profiles)} 个已启用角色")
        self.ensure_main()
        try:
            self._enter_gift_page_from_main()
            daily_remaining = self._read_daily_gift_remaining()
            summary["limit"] = self.MAX_TOTAL_GIFTS if daily_remaining is None else daily_remaining
            if summary["limit"] == 0:
                self._report("今日赠送次数已用完，继续读取赠礼名单的好感度")
            self._scan_character_list(profiles, summary)
            affinities = summary.get("affinities", {})
            if affinities:
                self.manager.record_affinities(affinities)
            processed = self._processed_profiles(summary)
            missing_names = []
            for profile_id, profile in profiles.items():
                name = profile["display_name"]
                if profile_id not in processed:
                    summary["skipped"].append(f"{name}: 未在角色列表中找到")
                    missing_names.append(name)
                elif affinity := affinities.get(profile_id):
                    self._report_affinity(name, affinity)
                else:
                    self._report(f"{name} 本轮未读取到好感度")
            self.ensure_main()
            if missing_names:
                self.log_warning(f"未识别到这些赠礼目标 {'、'.join(missing_names)}", notify=True)
            return summary
        finally:
            self._report(
                f"赠礼结束：成功 {summary['success']} 次，"
                f"跳过 {len(summary['skipped'])} 项，失败 {len(summary['failed'])} 项"
            )
            for reason in summary["skipped"]:
                self._report(f"跳过：{reason}")
            for reason in summary["failed"]:
                self._report(f"失败：{reason}")
            if restock := summary.get("restock"):
                self.log_warning(restock_message(restock), notify=True)

    def _enter_gift_page_from_main(self) -> None:
        """User-owned navigation seam. Keep all game-specific route actions here."""

        def action():
            self.openESCpanel()
            self.operate_click(*self.pos.panels.esc.gift)
            self.sleep(0.5)
            return self.wait_panel(Labels.bond_panel)

        result = self.retry_on_action(action, self.ensure_main)
        if not result:
            self.log_error("无法找到赠礼面板")
            raise CannotFindException()
        self.sleep(1)
        self._open_gift_tab()

    def _open_gift_tab(self) -> None:
        self.operate_click(0.802, 0.124)
        self.sleep(1)

    def get_name_box(self):
        return self.box_of_screen(*self.NAME_RATIO, name="gift_character_name")

    def _read_character_name(self, frame=None) -> str:
        results = self.ocr(box=self.get_name_box(), frame=frame, threshold=0.75)
        name = " ".join(result.name.strip() for result in results or []).strip()
        return name if 0 < len(name) <= 32 and any(char.isalpha() for char in name) else ""

    def _read_affinity(self) -> AffinityProgress | None:
        results = self.ocr(*GIFT_LAYOUT.affinity_box, threshold=0.75, name="gift_affinity")
        return parse_affinity([result.name for result in results or []])

    def get_gift_boxes(self):
        first_x, first_y, first_to_x, first_to_y = self.GIFT_FIRST_RATIO
        box_width = first_to_x - first_x
        box_height = first_to_y - first_y
        return [
            self.box_of_screen(
                first_x + column * self.GIFT_COLUMN_STEP,
                first_y + row * self.GIFT_ROW_STEP,
                first_x + column * self.GIFT_COLUMN_STEP + box_width,
                first_y + row * self.GIFT_ROW_STEP + box_height,
                name=f"gift_slot_{row * self.GIFT_COLUMNS + column}",
            )
            for row in range(self.GIFT_ROWS)
            for column in range(self.GIFT_COLUMNS)
        ]

    def get_unlimit_gift_box(self, gift_box):
        """Return the small upper-left unlimited-gift badge zone for one gift slot."""
        return gift_box.copy(
            x_offset=-round(gift_box.width * self.UNLIMIT_ICON_X_OFFSET_RATIO),
            y_offset=-round(gift_box.height * self.UNLIMIT_ICON_Y_OFFSET_RATIO),
            width_offset=-round(gift_box.width * self.UNLIMIT_ICON_WIDTH_REDUCTION_RATIO),
            name=f"{gift_box.name}_unlimit_badge",
        )

    def get_unlimit_gift_boxes(self):
        """Return the small upper-left badge zone associated with each visible gift slot."""
        return [self.get_unlimit_gift_box(gift_box) for gift_box in self.get_gift_boxes()]

    def resize_captured_frame(self, frame: np.ndarray) -> np.ndarray:
        """Fit a saved full frame to the current game frame so every layout Box is reusable."""
        current_frame = self.frame
        if frame.shape[:2] == current_frame.shape[:2]:
            return frame
        interpolation = (
            cv2.INTER_AREA if frame.shape[0] > current_frame.shape[0] else cv2.INTER_CUBIC
        )
        return cv2.resize(
            frame, (current_frame.shape[1], current_frame.shape[0]), interpolation=interpolation
        )

    def _sidebar_box(self):
        return self.box_of_screen(*self.SIDEBAR_BOX, name="gift_character_sidebar")

    def _scroll_sidebar_to_top(self) -> None:
        for _ in range(3):
            self.operate(
                lambda: self.scroll_relative(
                    self.SIDEBAR_SCROLL_X, self.SIDEBAR_SCROLL_Y, self.SIDEBAR_RESET_STEP
                ),
                block=True,
            )
            self.sleep(0.25)

    def _iter_sidebar_slots(self):
        self._scroll_sidebar_to_top()
        yield from self.CHARACTER_SLOT_YS
        sidebar = self._sidebar_box()
        still_frames = 0
        for _ in range(self.MAX_SIDEBAR_PAGES):
            if self.scroll_and_is_end(
                self.SIDEBAR_SCROLL_X,
                self.SIDEBAR_SCROLL_Y,
                self.SIDEBAR_SCROLL_STEP,
                sidebar,
                check_box=sidebar,
                after_sleep=0.45,
                threshold=0.97,
            ):
                still_frames += 1
                if still_frames == 2:
                    return
            else:
                still_frames = 0
                yield from self.CHARACTER_SLOT_YS
        self.log_warning("角色侧栏已达到本轮滚动上限")

    def _open_character_slot(self, y: float) -> None:
        self.operate_click(self.CHARACTER_SLOT_X, y)
        self.sleep(1)

    def _discover_characters(self) -> None:
        self.ensure_main()
        self._enter_gift_page_from_main()
        names = {}
        affinities = {}
        for y in self._iter_sidebar_slots():
            self._open_character_slot(y)
            if name := self._read_character_name():
                key = GiftDb.character_name_key(name)
                names.setdefault(key, name)
                if key not in affinities and (affinity := self._read_affinity()):
                    affinities[key] = affinity
        self.ensure_main()
        if not names:
            self.scan_error = self.tr("没有识别到角色名字，请确认游戏界面可见")
            return
        added = self.manager.register_characters(list(names.values()), affinities=affinities)
        self.scan_result = len(names), added
        self._report(f"已识别 {len(names)} 个角色，新增 {added} 个赠礼档案")

    def _scan_character_list(self, profiles: dict[str, dict], summary: dict) -> None:
        remaining = dict(profiles)
        if not remaining:
            return
        for y in self._iter_sidebar_slots():
            self._open_character_slot(y)
            if profile_id := self._match_current_profile(remaining):
                self._give_profile(profile_id, remaining.pop(profile_id), summary)
            if not remaining:
                return

    @staticmethod
    def _processed_profiles(summary: dict) -> set[str]:
        return set(summary.get("processed_profiles", set()))

    def _match_current_profile(self, profiles: dict[str, dict]) -> str | None:
        named_profiles = {
            GiftDb.character_name_key(profile["character_name"]): profile_id
            for profile_id, profile in profiles.items()
            if profile.get("character_name")
        }
        if named_profiles:
            name_key = GiftDb.character_name_key(self._read_character_name())
            if profile_id := named_profiles.get(name_key):
                self._report(f"找到角色 {profiles[profile_id]['display_name']}")
                return profile_id

        current_name_box = self.get_name_box()
        for profile_id, profile in profiles.items():
            if profile.get("character_name"):
                continue
            frame = self.manager.load_frame(profile)
            if frame is None:
                continue
            frame = self.resize_captured_frame(frame)
            template = iu.trim_right_background(current_name_box.crop_frame(frame))
            if self.find_one(
                f"gift_name_{profile_id}",
                template=template,
                box=current_name_box.scale(1.1),
                threshold=self.NAME_MATCH_THRESHOLD,
            ):
                self._report(f"找到角色 {profile['display_name']}")
                return profile_id
        return None

    def _read_character_gift_remaining(self, frame=None) -> int | None:
        box = self.box_of_screen(*self.COUNTER_BOX, name="gift_counter")
        results = self.ocr(box=box, match=self.COUNTER_RE, frame=frame)
        for result in results or []:
            match = self.COUNTER_RE.search(result.name)
            if match:
                return int(match.group(1))
        return None

    def _read_daily_gift_remaining(self) -> int | None:
        for result in self.ocr(*GIFT_LAYOUT.daily_counter_box, name="daily_gift_counter"):
            match = self.DAILY_COUNTER_RE.search("".join(result.name.split()))
            if match:
                return int(match.group(1))
        return None

    def _find_gift_box(self, profile: dict):
        saved_frame = self.manager.load_frame(profile)
        if saved_frame is None:
            return None
        saved_frame = self.resize_captured_frame(saved_frame)
        current_boxes = self.get_gift_boxes()
        for saved_index in profile["selected_slots"]:
            if saved_index in profile.get("blocked_slots", []):
                continue
            template = current_boxes[saved_index].crop_frame(saved_frame)
            for current_box in current_boxes:
                if self.find_one(
                    f"gift_{profile['frame_id']}_{saved_index}",
                    template=template,
                    box=current_box.scale(1.1),
                    threshold=self.GIFT_MATCH_THRESHOLD,
                ):
                    self.log_debug(
                        f"matched gift slot configured={saved_index} current={current_box.name}"
                    )
                    return current_box
        self.log_info("Not found any selected gift")
        return None

    def _find_400_gift(self):
        frame = self.frame
        first_x, _, _, _ = self.GIFT_FIRST_RATIO
        for index, gift_box in enumerate(self.get_gift_boxes()):
            row, column = divmod(index, self.GIFT_COLUMNS)
            left = first_x + column * self.GIFT_COLUMN_STEP
            right = left + self.GIFT_COLUMN_STEP
            y_offset = row * self.GIFT_ROW_STEP
            top, bottom = GIFT_LAYOUT.first_gift_affinity_band
            affinity = self.ocr(
                left,
                top + y_offset,
                right,
                bottom + y_offset,
                match=self.AFFINITY_RE,
                frame=frame,
                threshold=0.75,
            )
            if not affinity or self.find_one(
                Labels.unlimit_gift, box=self.get_unlimit_gift_box(gift_box), frame=frame
            ):
                continue
            top, bottom = GIFT_LAYOUT.first_gift_stock_band
            stock = self.ocr(
                left,
                top + y_offset,
                right,
                bottom + y_offset,
                match=self.STOCK_RE,
                frame=frame,
                threshold=0.75,
            )
            if stock:
                return gift_box
        return None

    def _remember_affinity(self, profile_id: str, summary: dict) -> AffinityProgress | None:
        affinity = self._read_affinity()
        if affinity is not None:
            summary.setdefault("affinities", {})[profile_id] = affinity
        return affinity

    def _report_affinity(self, name: str, affinity: AffinityProgress) -> None:
        if affinity.level == MAX_LEVEL:
            self._report(f"{name} 好感度已满级")
        elif affinity.remaining is not None:
            self._report(f"{name} 好感度 {affinity.level} 级，距满级还差 {affinity.remaining:,}")
        else:
            self._report(f"{name} 好感度 {affinity.level} 级，距满级点数待确认")

    def _give_profile(self, profile_id: str, profile: dict, summary: dict) -> None:
        summary.setdefault("processed_profiles", set()).add(profile_id)
        name = profile["display_name"]
        affinity = self._remember_affinity(profile_id, summary)
        if affinity and affinity.level == MAX_LEVEL:
            summary["skipped"].append(f"{name}: 好感度已满级")
            return

        limit = summary.get("limit", self.MAX_TOTAL_GIFTS)
        if summary["success"] >= limit:
            summary["skipped"].append(f"{name}: 本轮赠送额度已用完")
            return

        character_name = profile.get("character_name", "")
        character_key = GiftDb.character_name_key(character_name)
        remaining = self._read_character_gift_remaining()
        if remaining is None and character_key:
            self._open_gift_tab()
            remaining = self._read_character_gift_remaining()
        if remaining is None:
            summary["skipped"].append(f"{profile['display_name']}: 无法读取赠送次数")
            self.screenshot("gift_count_unreadable")
            return

        requested = min(profile["target_count"], self.MAX_GIFTS_PER_CHARACTER)
        sent = self.MAX_GIFTS_PER_CHARACTER - remaining
        if sent >= requested:
            summary["skipped"].append(f"{profile['display_name']}: 已达赠送目标 {sent}/{requested}")
            return

        only_gift_400 = profile.get("only_gift_400", False)
        while sent < requested and summary["success"] < limit:
            gift_box = self._find_400_gift() if only_gift_400 else self._find_gift_box(profile)
            if gift_box is None:
                if only_gift_400:
                    summary.setdefault("restock", []).append(character_name or name)
                    summary["skipped"].append(f"{name}: 首屏未确认有库存的 +400 礼物")
                else:
                    summary["skipped"].append(f"{name}: 首屏没有已配置礼物")
                self.screenshot("gift_not_found")
                return
            current_key = (
                GiftDb.character_name_key(self._read_character_name()) if character_key else ""
            )
            if current_key != character_key:
                summary["skipped"].append(f"{profile['display_name']}: 赠送前无法再次确认角色")
                return
            if not self._give_once(gift_box, remaining):
                summary["failed"].append(f"{profile['display_name']}: 点击后剩余赠送次数未减少 1 次")
                self.screenshot("gift_count_unchanged")
                self._remember_affinity(profile_id, summary)
                return
            self.sleep(3)
            remaining -= 1
            sent += 1
            summary["success"] += 1
            self._report(f"{profile['display_name']} 已赠送 {sent}/{requested}")
            if (affinity := self._remember_affinity(profile_id, summary)) and affinity.level == MAX_LEVEL:
                return

    def _give_once(self, gift_box, previous_count: int) -> bool:
        if self.find_one(Labels.unlimit_gift, box=self.get_unlimit_gift_box(gift_box)):
            self.log_warning(f"检测到无限礼物，取消赠送: {gift_box.name}")
            return False
        self.operate_click(gift_box)
        self.sleep(0.3)
        self.operate_click(*self.SEND_BUTTON)
        return bool(
            self.wait_until(
                lambda: self._read_character_gift_remaining() == previous_count - 1,
                time_out=4,
                raise_if_not_found=False,
                settle_time=0.2,
            )
        )
