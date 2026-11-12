import time
from unicodedata import normalize

from ok import Box, TaskDisabledException

from src.Labels import Labels
from src.tasks.BaseNTETask import BaseNTETask
from src.tasks.NTEOneTimeTask import NTEOneTimeTask
from src.utils import image_utils as iu


class CinemaDateTask(NTEOneTimeTask, BaseNTETask):
    CINEMA_DATE_TARGET = "约会目标"
    TARGET_ALIASES = {"明音": "明音凛", "明音凜": "明音凛"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "影院约会"
        self.group_name = "日常/周常"
        self.visible = False

        self.default_config.update(
            {
                self.CINEMA_DATE_TARGET: "",
            }
        )

    def run(self):
        super().run()
        try:
            self.do_run()
        except TaskDisabledException:
            raise
        except Exception as e:
            self.log_error("CinemaDateTask error", e)
            raise

    def do_run(self, target=None) -> bool:
        if target is None:
            target = self.config.get(self.CINEMA_DATE_TARGET, "")
        return self.run_cinema_date(target)

    def run_cinema_date(self, target=""):
        self.ensure_main(esc=True, time_out=60)
        self._tp_to_cinema()
        self._go_to_front_desk()
        if not self._open_date_invite():
            return False
        if not self._select_date(target):
            return False
        self.sleep(2)

        def post():
            def merged_action():
                self.send_key_down("lalt")
                time.sleep(0.1)
                self.click(0.029, 0.053, move=True)
                time.sleep(0.1)
                self.send_key_up("lalt")

            self.run_with_interval(lambda: self.operate(merged_action, block=True), interval=2)

        return bool(self.wait_until(self.is_in_team, post_action=post, time_out=30))

    def _tp_to_cinema(self):
        def action():
            self.open_f1_domain_page()
            self.sleep(0.5)
            self.operate_click(0.90, 0.15)
            self.sleep(0.5)
            self.operate(
                lambda: self.scroll_relative(0.5, 0.5, -40),
                block=True,
            )
            self.sleep(0.5)
            self.operate_click(0.862, 0.780)
            self.sleep(0.5)
            return self.click_traval_button(raise_if_not_found=False)

        self.retry_on_action(action=action, reset_action=self.ensure_main, raise_if_failed=True)
        self.ensure_main(esc=False, time_out=300)

    def _go_to_front_desk(self):
        self.send_key_down("w")
        self.sleep(1.91)
        self.send_key_up("w")
        self.sleep(0.33)
        self.send_key_down("d")
        self.sleep(3.36)
        self.send_key_up("d")
        self.sleep(0.52)
        self.send_key_down("a")
        self.sleep(0.01)
        self.send_key_down("s")
        self.sleep(2.25)
        self.send_key_up("a")
        timer = self.clock.timer(timeout=3.5)
        while not timer.expired():
            self.send_key("a", down_time=0.15, interval=0.5)
            self.sleep(0.1)
        self.send_key_up("s")
        self.sleep(0.65)
        self.send_key_down("s")
        self.sleep(0.45)
        self.send_key_down("space")
        self.sleep(0.14)
        self.send_key_up("space")
        self.sleep(1.71)
        self.send_key_down("a")
        self.sleep(1.20)
        self.send_key_up("a")
        self.sleep(1.00)
        self.wait_until(self.find_interac, time_out=20)
        self.send_key_up("s")

    def _open_date_invite(self):
        box = self.box_of_screen(0.960, 0.031, 0.984, 0.073, hcenter=True)

        def in_panel():
            return self.find_one(Labels.close_button, box=box)

        def action():
            if self.is_in_team():
                self.send_interac(handle_claim=False)
            elif not in_panel():
                self.operate_click(0.715, 0.543, interval=1)

        if not self.wait_until(in_panel, pre_action=action, time_out=20):
            return False

        if not self.wait_until(self._find_selectable_target, time_out=20):
            return False
        self.sleep(0.5)
        return True

    def _select_date(self, target):
        if target.strip():
            target_box = self._find_configured_target(target)
        else:
            self.log_info("默认使用顶部可选目标")
            target_box = self._top_selectable_target()
            if not target_box:
                self.log_info("未找到任何可选目标")

        if not target_box:
            return False

        return self.wait_click_confirm(
            pre_action=lambda: self.operate_click(target_box, interval=1),
            range=(0.650, 0.608, 0.705, 0.707),
        )

    @classmethod
    def _normalize_target(cls, name: str) -> str:
        name = "".join(normalize("NFKC", name).split()).casefold()
        return cls.TARGET_ALIASES.get(name, name)

    def _find_configured_target(self, target: str) -> Box | None:
        wanted = self._normalize_target(target)
        snap_box = self.box_of_screen(0.724, 0.723, 0.771, 0.892)
        at_end = False
        for _ in range(20):
            names = self.ocr(0.772, 0.228, 0.914, 0.905, log=True)
            matches = [box for box in names if self._normalize_target(box.name or "") == wanted]
            if matches:
                if len(matches) == 1:
                    name_box = matches[0]
                    same_row = [
                        button
                        for button in self._find_selectable_target()
                        if name_box.y < button.y + button.height
                        and button.y < name_box.y + name_box.height
                    ]
                    if len(same_row) == 1:
                        self.log_info(f"找到可邀约目标 {target}")
                        return same_row[0]
                self.log_warning(f"无法确认 {target} 对应的可邀约按钮, 结束任务")
                return None
            if at_end:
                break
            at_end = self.scroll_and_is_end(0.8391, 0.5333, -19, snap_box)
        self.log_warning(f"未找到邀约目标 {target}, 结束任务")
        return None

    def _find_selectable_target(self) -> list[Box]:
        box = self.box_of_screen(0.907, 0.232, 0.947, 0.907, hcenter=True)
        boxes = iu.find_color_enriched_regions(selectable_green_color, box, self.frame)
        return boxes

    def _top_selectable_target(self) -> Box | None:
        boxes = self._find_selectable_target()
        return min(boxes, key=lambda box: box.y, default=None)


selectable_green_color = {
    "r": (55, 65),
    "g": (185, 195),
    "b": (160, 170),
}
