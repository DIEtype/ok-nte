import unittest
from unittest.mock import Mock

from ok import Box

from src.tasks.daily.CinemaDateTask import CinemaDateTask


class TestCinemaDateTask(unittest.TestCase):
    def setUp(self):
        self.task = object.__new__(CinemaDateTask)
        self.task.box_of_screen = Mock()
        self.task.log_info = Mock()
        self.task.log_warning = Mock()
        self.task.ocr = Mock()
        self.task.scroll_and_is_end = Mock(return_value=True)
        self.top = Box(920, 200, 40, 32)
        self.task._find_selectable_target = Mock(return_value=[self.top])
        self.task.operate_click = Mock()
        self.task.wait_click_confirm = Mock(
            side_effect=lambda pre_action, **kwargs: pre_action() or True
        )

    def test_target_match_on_last_page_uses_same_row_button(self):
        target_button = Box(920, 340, 40, 34)
        target_name = Box(790, 334, 60, 17, name="明音 凜")
        self.task.ocr.side_effect = [[], [target_name]]
        self.task._find_selectable_target.return_value = [target_button, self.top]

        self.assertTrue(self.task._select_date("明音"))
        self.task.operate_click.assert_called_once_with(target_button, interval=1)

    def test_missing_or_unavailable_target_never_invites_someone_else(self):
        for names in ([], [Box(790, 340, 60, 20, name="明音凛")]):
            with self.subTest(names=names):
                self.task.ocr.return_value = names
                self.assertFalse(self.task._select_date("明音"))
                self.task.wait_click_confirm.assert_not_called()

    def test_empty_target_uses_top_selectable_row(self):
        self.task._find_selectable_target.return_value = [Box(920, 340, 40, 34), self.top]

        self.assertTrue(self.task._select_date(""))
        self.task.operate_click.assert_called_once_with(self.top, interval=1)
