import unittest
from types import SimpleNamespace

import numpy as np
from ok import Box

from src.gifts.affinity import AffinityProgress, parse_affinity
from src.Labels import Labels
from src.tasks.daily.GiftTask import GiftTask


class TestGiftTask(unittest.TestCase):
    def test_ui_commands_prepare_the_task_mode_and_capture_state(self):
        task = object.__new__(GiftTask)
        task.capture_frame = object()
        task.capture_name = "stale"
        task.capture_blocked_slots = (1,)
        task.capture_error = "stale"

        GiftTask.capture_profile(task, "profile-1")

        self.assertEqual(task.mode, GiftTask.MODE_CAPTURE)
        self.assertEqual(task.capture_profile_id, "profile-1")
        self.assertIsNone(task.capture_frame)
        self.assertEqual(task.capture_name, "")
        self.assertEqual(task.capture_blocked_slots, ())
        self.assertEqual(task.capture_error, "")

        GiftTask.run_gift_mode(task)

        self.assertEqual(task.mode, GiftTask.MODE_RUN)

    def test_layout_boxes_are_derived_from_full_frame_size(self):
        task = object.__new__(GiftTask)
        task._executor = SimpleNamespace(frame=np.zeros((100, 200, 3), dtype=np.uint8))
        frame = np.zeros((200, 400, 3), dtype=np.uint8)
        resized = GiftTask.resize_captured_frame(task, frame)
        task.box_of_screen = lambda x, y, to_x, to_y, name: Box(
            round(x * 200),
            round(y * 100),
            round((to_x - x) * 200),
            round((to_y - y) * 100),
            name=name,
        )
        name_box = GiftTask.get_name_box(task)
        gift_boxes = GiftTask.get_gift_boxes(task)
        self.assertGreater(name_box.width, 0)
        self.assertGreater(name_box.height, 0)
        self.assertEqual(resized.shape[:2], task._executor.frame.shape[:2])
        self.assertEqual(len(gift_boxes), 10)
        self.assertEqual(gift_boxes[0].name, "gift_slot_0")
        self.assertGreater(gift_boxes[-1].x, gift_boxes[0].x)
        self.assertEqual(
            gift_boxes[0].crop_frame(frame).shape[:2],
            (gift_boxes[0].height, gift_boxes[0].width),
        )
        task.get_gift_boxes = lambda: gift_boxes
        badge_boxes = GiftTask.get_unlimit_gift_boxes(task)
        self.assertEqual(len(badge_boxes), 10)
        self.assertLess(badge_boxes[0].x, gift_boxes[0].x)
        self.assertLess(badge_boxes[0].y, gift_boxes[0].y)
        self.assertEqual(
            GiftTask.get_unlimit_gift_box(task, gift_boxes[0]).name, "gift_slot_0_unlimit_badge"
        )

    def test_character_match_delegates_template_matching_to_find_one(self):
        task = object.__new__(GiftTask)
        frame = np.full((100, 200, 3), 100, dtype=np.uint8)
        task.manager = SimpleNamespace(load_frame=lambda _profile: frame)
        task._executor = SimpleNamespace(frame=frame)
        task.get_name_box = lambda: Box(0, 0, 45, 7, name="gift_character_name")
        task._report = lambda _message: None
        calls = []
        task.find_one = lambda *args, **kwargs: calls.append((args, kwargs)) or Box(0, 0, 1, 1)

        profile_id = GiftTask._match_current_profile(
            task, {"profile": {"display_name": "角色", "frame_id": "frame"}}
        )

        self.assertEqual(profile_id, "profile")
        self.assertEqual(len(calls), 1)
        ((call_args, call_kwargs),) = calls
        self.assertEqual(call_args, ("gift_name_profile",))
        self.assertEqual(call_kwargs["box"].name, "gift_character_name")
        self.assertEqual(
            call_kwargs["template"].shape[:2],
            task.get_name_box().crop_frame(frame).shape[:2],
        )

    def test_give_profile_respects_target_and_global_limit(self):
        task = object.__new__(GiftTask)
        task._report = lambda _message: None
        task.sleep = lambda _seconds: None
        task.screenshot = lambda _name: None
        task.ocr = lambda *_args, **_kwargs: False
        remaining = [3]
        task._read_character_gift_remaining = lambda: remaining[0]
        task._find_gift_box = lambda _profile: object()
        attempts = []
        task._give_once = lambda _box, previous: (
            attempts.append(previous) or (remaining.__setitem__(0, remaining[0] - 1) or True)
        )
        profile = {"display_name": "角色", "target_count": 3, "selected_slots": [0]}
        summary = {"success": 0, "skipped": [], "failed": []}

        GiftTask._give_profile(task, "profile", profile, summary)
        self.assertEqual(summary["success"], 3)
        self.assertEqual(attempts, [3, 2, 1])
        self.assertEqual(summary["processed_profiles"], {"profile"})

        attempts.clear()
        capped = {"success": GiftTask.MAX_TOTAL_GIFTS, "skipped": [], "failed": []}
        GiftTask._give_profile(task, "profile", profile, capped)
        self.assertEqual(attempts, [])

    def test_give_profile_does_not_count_unchanged_counter(self):
        task = object.__new__(GiftTask)
        task._report = lambda _message: None
        task.screenshot = lambda _name: None
        task.ocr = lambda *_args, **_kwargs: False
        task._read_character_gift_remaining = lambda: 3
        task._find_gift_box = lambda _profile: object()
        task._give_once = lambda _box, _previous: False
        summary = {"success": 0, "skipped": [], "failed": []}

        GiftTask._give_profile(
            task,
            "profile",
            {"display_name": "角色", "target_count": 1, "selected_slots": [0]},
            summary,
        )
        self.assertEqual(summary["success"], 0)
        self.assertEqual(len(summary["failed"]), 1)

    def test_give_once_does_not_click_an_unlimited_gift(self):
        task = object.__new__(GiftTask)
        gift_box = SimpleNamespace(name="gift_slot_0")
        task.get_unlimit_gift_box = lambda box: box
        task.find_one = lambda label, box: label == Labels.unlimit_gift and box is gift_box
        task.log_warning = lambda _message: None
        task.operate_click = lambda *_args: self.fail("must not click an unlimited gift")

        self.assertFalse(GiftTask._give_once(task, gift_box, previous_count=3))

    def test_give_profile_does_not_click_when_character_already_reached_target(self):
        task = object.__new__(GiftTask)
        task._report = lambda _message: None
        task.screenshot = lambda _name: None
        task._read_affinity = lambda: None
        task._read_character_gift_remaining = lambda: 1
        task._find_gift_box = lambda _profile: self.fail(
            "must not search gifts at the configured target"
        )
        task._give_once = lambda _box, _previous: self.fail(
            "must not click at the configured target"
        )
        summary = {"success": 0, "skipped": [], "failed": []}

        GiftTask._give_profile(
            task,
            "profile",
            {"display_name": "角色", "target_count": 1, "selected_slots": [0]},
            summary,
        )

        self.assertEqual(summary["success"], 0)
        self.assertEqual(summary["skipped"], ["角色: 已达赠送目标 2/1"])

    def test_exhausted_character_does_not_use_the_shared_quota(self):
        task = object.__new__(GiftTask)
        task._report = lambda _message: None
        task.sleep = lambda _seconds: None
        task.ocr = lambda *_args, **_kwargs: False
        task._scroll_sidebar_to_top = lambda: None
        task.operate_click = lambda *_args: None
        task._match_current_profile = lambda profiles: next(iter(profiles))
        remaining = iter([0, 3])
        task._read_character_gift_remaining = lambda: next(remaining)
        task._find_gift_box = lambda _profile: self.fail("manual gift selection used in +400 mode")
        gift_box = object()
        task._find_400_gift = lambda: gift_box
        attempts = []
        task._give_once = lambda box, count: attempts.append((box, count)) or True
        profiles = {
            name: {"display_name": name, "target_count": 3, "only_gift_400": True}
            for name in ("A", "B")
        }
        summary = {"limit": 1, "success": 0, "skipped": [], "failed": []}

        task._scan_character_list(profiles, summary)

        self.assertEqual(attempts, [(gift_box, 3)])
        self.assertEqual(summary["success"], 1)
        self.assertEqual(summary["processed_profiles"], {"A", "B"})

    def test_run_gifts_updates_every_target_even_with_zero_or_exhausted_quota(self):
        for limit in (0, 1):
            with self.subTest(limit=limit):
                task = object.__new__(GiftTask)
                task.ensure_main = lambda: None
                task._enter_gift_page_from_main = lambda: None
                task._read_daily_gift_remaining = lambda: limit
                task._report = lambda _message: None
                task.sleep = lambda _seconds: None
                task._iter_sidebar_slots = lambda: iter((0.2, 0.4))
                task._open_character_slot = lambda _y: None
                task._match_current_profile = lambda profiles: next(iter(profiles))
                gift = object()
                task._find_400_gift = lambda: gift
                task._read_character_gift_remaining = lambda: 3
                attempts = []
                task._give_once = lambda box, count: attempts.append((box, count)) or True
                a = AffinityProgress(9, 8440, 16000)
                after_gift = AffinityProgress(9, 8840, 16000)
                b = AffinityProgress(8, 4000, 12000)
                readings = iter((a, after_gift, b) if limit else (a, b))
                task._read_affinity = lambda: next(readings)
                profiles = {
                    name: {"display_name": name, "target_count": 1, "only_gift_400": True}
                    for name in ("A", "B")
                }
                saved = {}
                task.manager = SimpleNamespace(
                    get_enabled_profiles=lambda: profiles,
                    record_affinities=saved.update,
                )

                summary = task.run_gifts()

                self.assertEqual(attempts, [(gift, 3)] if limit else [])
                self.assertEqual(summary["success"], limit)
                self.assertEqual(saved, {"A": after_gift if limit else a, "B": b})

    def test_gift_stops_after_reaching_max_affinity(self):
        task = object.__new__(GiftTask)
        readings = iter((AffinityProgress(9, 15900, 16000), AffinityProgress(10)))
        task._read_affinity = lambda: next(readings)
        task._read_character_gift_remaining = lambda: 3
        task._find_400_gift = lambda: object()
        task._give_once = lambda *_: True
        task._report = lambda _message: None
        task.sleep = lambda _seconds: None
        profile = {"display_name": "角色", "target_count": 3, "only_gift_400": True}
        summary = {"success": 0, "skipped": [], "failed": []}

        task._give_profile("role", profile, summary)

        self.assertEqual(summary["success"], 1)
        self.assertEqual(summary["affinities"]["role"].level, 10)

    def test_400_gift_mode_reminds_when_no_eligible_gift_is_found(self):
        task = object.__new__(GiftTask)
        task.ocr = lambda *_args, **_kwargs: False
        task.screenshot = lambda _name: None
        task._read_character_gift_remaining = lambda: 3
        task._find_400_gift = lambda: None
        task._give_once = lambda *_: self.fail("must not send without a matched gift")
        profile = {"display_name": "角色", "target_count": 1, "only_gift_400": True}
        summary = {"success": 0, "skipped": [], "failed": []}

        task._give_profile("profile", profile, summary)

        self.assertEqual(summary["restock"], ["角色"])
        self.assertEqual(summary["success"], 0)

    def test_400_gift_scan_requires_a_positive_stock_count(self):
        task = object.__new__(GiftTask)
        task._executor = SimpleNamespace(frame=np.zeros((10, 10, 3), dtype=np.uint8))
        gift_boxes = [Box(0, 0, 10, 10, name=str(index)) for index in range(4)]
        task.get_gift_boxes = lambda: gift_boxes
        task.find_one = lambda _label, *, box, frame: box.name.startswith("2_")
        scores = ["200", "400", "400", "400"]
        stocks = ["400", "0", "19", "21"]

        def ocr(left, _top, _right, _bottom, *, match, **_kwargs):
            index = round((left - task.GIFT_FIRST_RATIO[0]) / task.GIFT_COLUMN_STEP)
            value = scores[index] if match == task.AFFINITY_RE else stocks[index]
            return [SimpleNamespace(name=value)] if match.fullmatch(value) else []

        task.ocr = ocr

        self.assertIs(task._find_400_gift(), gift_boxes[3])

    def test_sidebar_scan_rechecks_all_visible_slots_and_requires_two_still_frames(self):
        task = object.__new__(GiftTask)
        task._scroll_sidebar_to_top = lambda: None
        task.sleep = lambda _seconds: None
        clicked_slots = []
        task.operate_click = lambda _x, y, interval=None: clicked_slots.append(y)
        task._match_current_profile = lambda _profiles: None
        task._give_profile = lambda _profile_id, _profile, _summary: None
        task._executor = SimpleNamespace(frame=np.zeros((1, 1, 3), dtype=np.uint8))
        task._sidebar_box = lambda: Box(0, 0, 1, 1)

        scroll_states = iter((False, True, False, True, True))
        task.scroll_and_is_end = lambda *_args, **_kwargs: next(scroll_states)

        GiftTask._scan_character_list(
            task,
            {"unmatched": {"display_name": "未匹配"}},
            {"success": 0, "skipped": [], "failed": []},
        )

        self.assertEqual(clicked_slots, list(GiftTask.CHARACTER_SLOT_YS) * 3)

    def test_character_discovery_reads_newly_revealed_roles_without_sending_gifts(self):
        task = object.__new__(GiftTask)
        task.ensure_main = lambda: None
        task._enter_gift_page_from_main = lambda: None
        task._report = lambda _message: None
        task._scroll_sidebar_to_top = lambda: None
        task.sleep = lambda _seconds: None
        task.CHARACTER_SLOT_YS = (0.2, 0.4)
        task._sidebar_box = lambda: Box(0, 0, 1, 1)
        scroll_ends = iter((False, True, True))
        task.scroll_and_is_end = lambda *_args, **_kwargs: next(scroll_ends)
        task._give_profile = lambda *_: self.fail("character discovery must not send gifts")
        names = iter(("真红", "明音凛", " 明 音 凛 ", "伊洛伊"))
        task._read_character_name = lambda: next(names)
        task._read_affinity = lambda: parse_affinity(["9", "8440/16000"])
        clicks = []
        task.operate_click = lambda _x, y: clicks.append(y)
        registered = []
        task.manager = SimpleNamespace(
            register_characters=lambda names, **_: registered.extend(names) or len(names)
        )

        task._discover_characters()

        self.assertEqual(clicks, [0.2, 0.4, 0.2, 0.4])
        self.assertEqual(registered, ["真红", "明音凛", "伊洛伊"])
        self.assertEqual(task.scan_result, (3, 3))

    def test_gift_ocr_matches_the_registered_name_even_when_the_display_name_is_edited(self):
        task = object.__new__(GiftTask)
        task._report = lambda _message: None
        task.get_name_box = lambda: Box(0, 0, 100, 20)
        profiles = {"role": {"display_name": "明音", "character_name": "明音凛"}}
        names = iter(("明 音 凛", "明音"))
        task.ocr = lambda **_kwargs: [SimpleNamespace(name=next(names))]

        self.assertEqual(task._match_current_profile(profiles), "role")
        self.assertIsNone(task._match_current_profile(profiles))

    def test_gift_ocr_rechecks_recipient_before_committing(self):
        task = object.__new__(GiftTask)
        task._read_character_gift_remaining = lambda: 3
        task.ocr = lambda *_args, **_kwargs: []
        task._find_400_gift = lambda: object()
        task._read_character_name = lambda: "伊洛伊"
        task._give_once = lambda *_: self.fail("the recipient changed")
        profile = {
            "display_name": "明音",
            "character_name": "明音凛",
            "only_gift_400": True,
            "target_count": 1,
        }
        summary = {"success": 0, "skipped": [], "failed": []}

        task._give_profile("role", profile, summary)

        self.assertEqual(summary["success"], 0)
        self.assertEqual(len(summary["skipped"]), 1)

    def test_affinity_gap_uses_all_remaining_levels_and_checks_live_denominator(self):
        self.assertEqual(parse_affinity(["好感度", "9", "8,440/16,000"]).remaining, 7560)
        self.assertEqual(parse_affinity(["8", "4,000/12,000"]).remaining, 24000)
        self.assertEqual(parse_affinity(["10", "3210"]).remaining, 0)
        self.assertIsNone(parse_affinity(["8", "4,000/12,050"]).remaining)
        self.assertIsNone(parse_affinity(["好感度"]))
