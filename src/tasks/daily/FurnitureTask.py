import re

from ok import TaskDisabledException

from src.combat.BaseCombatTask import BaseCombatTask
from src.Labels import Labels
from src.tasks.NTEOneTimeTask import NTEOneTimeTask
from src.tasks.weekly_progress import FLUFF_COLLECTED, MAMMON_COLLECTED, WeeklyProgress

_FLUFF_TOAST = re.compile(r"^绒绒棉花\s*[x×]\s*[1-9][0-9]*$", re.IGNORECASE)
_MAMMON_EXIT = re.compile(r"^退出(?:[（(][0-9]+\s*s[）)])?$", re.IGNORECASE)
_GOLD_NUMBER = re.compile(r"(?:[0-9]+|[0-9]{1,3}(?:[,，][0-9]{3})+)")


class FurnitureTask(NTEOneTimeTask, BaseCombatTask):
    CONF_FLUFF = "领取绒绒棉花"
    CONF_MAMMON = "挑战玛门"
    CONF_WEEKLY_TRACKING = "记住本周家具奖励"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "周常家具奖励"
        self.group_name = "日常/周常"
        self.visible = False
        self.default_config.update(
            {self.CONF_FLUFF: True, self.CONF_MAMMON: True, self.CONF_WEEKLY_TRACKING: False}
        )
        self.config_description[self.CONF_WEEKLY_TRACKING] = (
            "确认领取绒绒棉花或玛门奖励后, 本周跳过该项目。"
        )

    def run(self):
        super().run()
        try:
            self.do_run()
        except TaskDisabledException:
            raise
        except Exception as e:
            self.log_error("FurnitureTask error", e)
            raise

    def do_run(self) -> bool | None:
        return self.claim_anomaly_furniture()

    def claim_anomaly_furniture(self):
        """领取异象家具奖励"""

        self.log_info("正在领取异象家具奖励")

        furniture_list = []
        if self.config.get(self.CONF_FLUFF, True):
            furniture_list.append(Labels.anomaly_fluff)
        if self.config.get(self.CONF_MAMMON):
            furniture_list.append(Labels.anomaly_mammon)
        if not furniture_list:
            return None

        progress = None
        if self.config.get(self.CONF_WEEKLY_TRACKING):
            self.ensure_main()
            progress = WeeklyProgress(self)

        furniture_results = {}
        for furniture in furniture_list:
            key = FLUFF_COLLECTED if furniture == Labels.anomaly_fluff else MAMMON_COLLECTED
            if progress is not None and progress.is_done(key):
                self.log_info(f"本周已确认 {furniture} 领取完成, 跳过")
                continue
            try:
                claimed = self.claim_furniture(furniture, progress)
            except TaskDisabledException:
                raise
            except Exception as e:
                self.log_error(f"领取异象家具失败: {furniture}", e)
                claimed = False

            furniture_results[furniture] = claimed
            result = "成功" if claimed else "失败"
            self.log_info(f"异象家具 {furniture} 领取{result}")

        if not furniture_results:
            return None
        all_claimed = all(furniture_results.values())
        if all_claimed:
            self.log_info("异象家具奖励全部领取成功")
        else:
            self.log_error("异象家具奖励未能全部领取成功")
        return all_claimed

    def check_house_lock(self, ratio_y):
        box = self.box_of_screen(0.050, ratio_y - 0.1, width=0.054, height=0.079, hcenter=True)
        return self.find_one(Labels.f5_house_lock, box=box)

    def check_house_card(self, ratio_y, snapshot):
        box = self.get_box_by_name(Labels.box_house_list_snapshot)
        box.y = int(ratio_y * self.height) - box.height
        search_box = box.copy(y_offset=-box.height, height_offset=box.height)

        click = True
        if snapshot is None:
            click = False
            snapshot = box.crop_frame(self.frame)
        else:
            if self.find_one(
                "house_card_snapshot", template=snapshot, box=search_box, threshold=0.9
            ):
                click = False
            else:
                snapshot = box.crop_frame(self.frame)
        return click, snapshot

    def teleport_to_furniture(self, furniture):
        house_box = self.box_of_screen(0.507, 0.476, 0.956, 0.795, hcenter=True)

        shown = 4
        ratio_x = 0.079
        ratio_y = 0.308
        gap = 0.183
        scroll_per_item = 6

        click_card_snapshot = None
        scroll = True
        scroll_times = 0
        i = 0
        if not self.open_house_panel():
            return False

        # 寻找目标家具
        while scroll or i < shown:
            self.next_frame()
            if scroll:
                target_y = ratio_y
            else:
                target_y = ratio_y + gap * i
                i += 1

            # 检查房子是否解锁
            if self.check_house_lock(target_y):
                self.sleep(0.25)
            else:
                click_card, candidate_snapshot = self.check_house_card(
                    target_y, click_card_snapshot
                )
                if click_card_snapshot is None:
                    click_card_snapshot = candidate_snapshot
                    check_furniture = True
                else:
                    check_furniture = not click_card

                if click_card:
                    box = self.get_box_by_name(Labels.box_house_preview_snapshot)
                    preview_snapshot = box.crop_frame(self.frame)

                    self.operate_click(ratio_x, target_y)
                    check_furniture = bool(
                        self.wait_until(
                            lambda: (
                                not self.find_one(
                                    "preview_snapshot", template=preview_snapshot, box=box
                                )
                            ),
                            time_out=2.5,
                            raise_if_not_found=False,
                        )
                    )
                    click_card_snapshot = candidate_snapshot

                if check_furniture and self.find_sift_feature(furniture, box=house_box):
                    break

            # 滚动并检查是否成功滚动
            if scroll:
                scroll_times += 1
                box = self.get_box_by_name(Labels.box_house_list_snapshot)
                search_box = box.copy(y_offset=-box.height, height_offset=box.height)
                scroll = not self.scroll_and_is_end(
                    ratio_x,
                    ratio_y,
                    -scroll_per_item,
                    snap_box=box,
                    check_box=search_box,
                    threshold=0.9,
                )
        else:
            self.log_info(f"not found furniture {furniture}")
            self.operate(
                lambda: (
                    self.scroll(ratio_x, ratio_y, scroll_per_item * (scroll_times + 2)),
                    self.sleep(0.25),
                ),
                block=True,
            )
            return False

        # 传送至目标房子
        self.wait_until(
            lambda: not self.find_one(Labels.f5_house_panel),
            pre_action=lambda: self.operate_click(0.891, 0.951, after_sleep=1),
        )
        self.click_traval_button()
        return self.wait_in_team(time_out=300, settle_time=1)

    def claim_furniture(self, furniture, progress=None):
        if not self.teleport_to_furniture(furniture):
            return False

        # 打开异象家具
        def action_1():
            try:
                self.send_key_down("lalt")
                self.sleep(0.25)
                self.operate_click(0.465, 0.056)
            finally:
                self.send_key_up("lalt")
            self.sleep(2)
            if not self.is_in_team():
                return True

        self.retry_on_action(action_1, attempt=10, raise_if_failed=True)

        # 切换领取页面
        confirm_box = self.box_of_screen(0.913, 0.887, 0.967, 0.976)

        def action_2():
            self.operate_click(0.924, 0.174)
            self.sleep(1)
            if confirm := self.find_confirm(box=confirm_box):
                return confirm

        confirm = self.retry_on_action(action_2, attempt=10, raise_if_failed=True)

        if furniture == Labels.anomaly_fluff:
            if progress is None:
                ret = self.operate_click(confirm, after_sleep=0.5)
            else:
                ret = self._claim_weekly_fluff(confirm, progress)
        else:
            ret = self.click_furniture(furniture, progress)

        self.ensure_main()
        return ret

    def click_furniture(self, furniture, progress=None):
        # 滚动至顶部
        self.operate(
            lambda: self.scroll(
                0.8566, 0.4701, 40
            ),
            block=True,
        )

        box_left = self.box_of_screen(0.024, 0.181, 0.278, 0.775, hcenter=True)
        self.wait_until(
            lambda: self.find_sift_feature(furniture, box=box_left), raise_if_not_found=True
        )
        self.sleep(0.5)
        box_right = self.box_of_screen(0.738, 0.236, 0.805, 0.959, hcenter=True)

        # 点击异象家具
        def action():
            box = self.find_sift_feature(furniture, box=box_left)
            if box:
                self.operate_click(box)
                self.sleep(0.5)
                if self.find_sift_feature(furniture, box=box_right):
                    return True
            self.sleep(0.5)

        self.retry_on_action(action, attempt=10, raise_if_failed=True)

        # 领取目标家具
        self.sleep(0.5)
        self.operate(
            lambda: (
                self.click(0.938, 0.283, move=True),
                self.sleep(0.1),
                self.click(0.938, 0.303, move=True),
            ),
            block=True,
        )
        self.sleep(0.5)
        return self.after_claim_action(furniture, progress)

    def after_claim_action(self, furniture, progress=None):
        match furniture:
            case Labels.anomaly_mammon:
                if progress is not None:
                    return self._claim_weekly_mammon(progress)
                return self.claim_mammon()
            case _:
                return True

    def _claim_weekly_fluff(self, confirm, progress):
        popup_box = self.box_of_screen(0.452, 0.270, 0.547, 0.427, hcenter=True)

        def dismiss_popup():
            if self.find_one(Labels.reward_popup, box=popup_box):
                self.operate_click(0.5, 0.77, interval=0.8, action_name="dismiss_fluff_reward")

        self.operate_click(confirm)
        if not self.wait_until(self._find_fluff_toast, post_action=dismiss_popup, time_out=6):
            self.log_warning("未看到绒绒棉花到账")
            return False
        progress.mark_done(FLUFF_COLLECTED)
        return True

    def _find_fluff_toast(self):
        return self.ocr(0.0, 0.389, 0.198, 0.556, match=_FLUFF_TOAST)

    def _read_mammon_gold(self, region) -> int | None:
        values = [
            box.name.strip()
            for box in self.ocr(*region)
            if box.name and _GOLD_NUMBER.fullmatch(box.name.strip())
        ]
        if len(values) == 1:
            return int(values[0].replace(",", "").replace("，", ""))
        return None

    def _mammon_week_record(self) -> int | None:
        if self.ocr(0.584, 0.554, 0.711, 0.606, match="本期最高夺金记录"):
            return self._read_mammon_gold((0.698, 0.597, 0.766, 0.685))
        return None

    def _mammon_reward_exit(self):
        if not self.ocr(0.297, 0.585, 0.463, 0.635, match="本次夺金记录"):
            return None
        if not self._read_mammon_gold((0.636, 0.585, 0.702, 0.635)):
            return None
        exits = self.ocr(0.313, 0.832, 0.446, 0.887, match=_MAMMON_EXIT)
        return exits[0] if exits else None

    def _claim_weekly_mammon(self, progress):
        start = self.wait_ocr(0.531, 0.744, 0.674, 0.795, match="开始挑战", time_out=8)
        if not start:
            return False
        record = self._mammon_week_record()
        if record is None:
            self.log_warning("未能确认玛门本期最高夺金记录")
            return False
        if record > 0:
            progress.mark_done(MAMMON_COLLECTED)
            return True

        def collect():
            if exit_button := self._mammon_reward_exit():
                return exit_button
            self.walk_to_treasure()
            self.send_interac(handle_claim=False)
            return self.wait_until(self._mammon_reward_exit, time_out=4)

        self.operate_click(start[0])
        if self.wait_in_team(time_out=60, settle_time=0.5, raise_if_not_found=False):
            if exit_button := self._fight_mammon(collect):
                progress.mark_done(MAMMON_COLLECTED)
                self.operate_click(exit_button)
                return True
            self.exit_anomaly()
        return False

    def _fight_mammon(self, collect):
        if self.walk_until_combat(run=True):
            self.combat_once()
            self.rotate_and_find_treasure()
            return self.retry_on_action(collect)
        return None

    def claim_mammon(self):
        exc_msg = "mammon has record"

        def check_record():
            mammon_record = self.ocr(0.634, 0.609, 0.762, 0.674, name="mammon_record")
            if self.parse_ocr_number(mammon_record) > 0:
                raise Exception(exc_msg)

        def action():
            self.walk_to_treasure()
            self.send_interac(handle_claim=False)
            if self.wait_click_confirm(
                range=(0.4168, 0.8153, 0.4609, 0.9049), raise_if_not_found=False, time_out=1.5
            ):
                return True

        run_mammon = False
        ret = False
        try:
            run_mammon = self.wait_click_confirm(
                range=(0.628, 0.712, 0.682, 0.815),
                time_out=10,
                raise_if_not_found=False,
                on_found=check_record,
            )
        except Exception as e:
            if str(e) == exc_msg:
                ret = True
            else:
                raise

        if run_mammon:
            if self._fight_mammon(action):
                return True
            self.exit_anomaly()
        self.ensure_main()
        return ret
