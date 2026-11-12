import unittest
from unittest.mock import Mock, patch

from ok import Box

from src.Labels import Labels
from src.tasks.daily.FurnitureTask import FurnitureTask
from src.tasks.weekly_progress import FLUFF_COLLECTED, MAMMON_COLLECTED


class TestFurnitureWeekly(unittest.TestCase):
    def setUp(self):
        self.task = object.__new__(FurnitureTask)
        self.task.log_info = Mock()
        self.task.log_warning = Mock()
        self.task.ensure_main = Mock()
        self.task.operate_click = Mock()
        self.task.box_of_screen = Mock()
        self.progress = Mock()

    @patch("src.tasks.daily.FurnitureTask.WeeklyProgress")
    def test_weekly_cache_skips_only_the_confirmed_furniture(self, tracker):
        self.task.config = {
            FurnitureTask.CONF_MAMMON: True,
            FurnitureTask.CONF_WEEKLY_TRACKING: True,
        }
        self.task.claim_furniture = Mock(return_value=True)
        self.progress.is_done.side_effect = lambda key: key == FLUFF_COLLECTED
        tracker.return_value = self.progress

        self.assertTrue(self.task.claim_anomaly_furniture())
        self.task.claim_furniture.assert_called_once_with(Labels.anomaly_mammon, self.progress)

    @patch("src.tasks.daily.FurnitureTask.WeeklyProgress")
    def test_all_selected_furniture_already_claimed_is_skipped(self, tracker):
        self.task.config = {
            FurnitureTask.CONF_FLUFF: False,
            FurnitureTask.CONF_MAMMON: True,
            FurnitureTask.CONF_WEEKLY_TRACKING: True,
        }
        self.task.claim_furniture = Mock()
        tracker.return_value = self.progress
        self.progress.is_done.return_value = True

        self.assertIsNone(self.task.do_run())
        self.progress.is_done.assert_called_once_with(MAMMON_COLLECTED)
        self.task.claim_furniture.assert_not_called()

    def test_fluff_waits_for_item_receipt_before_saving(self):
        self.task.wait_until = Mock(side_effect=[False, True])
        self.assertFalse(self.task._claim_weekly_fluff(Mock(), self.progress))
        self.progress.mark_done.assert_not_called()
        self.assertTrue(self.task._claim_weekly_fluff(Mock(), self.progress))
        self.progress.mark_done.assert_called_once_with(FLUFF_COLLECTED)

    def test_mammon_existing_record_avoids_another_fight(self):
        self.task.wait_ocr = Mock(return_value=[Box(1, 1, 10, 10, name="开始挑战")])
        self.task._mammon_week_record = Mock(return_value=75000)

        self.assertTrue(self.task._claim_weekly_mammon(self.progress))
        self.task.operate_click.assert_not_called()
        self.progress.mark_done.assert_called_once_with(MAMMON_COLLECTED)

    def test_mammon_without_settlement_can_be_retried(self):
        self.task.wait_ocr = Mock(return_value=[Box(1, 1, 10, 10, name="开始挑战")])
        self.task._mammon_week_record = Mock(return_value=0)
        self.task.wait_in_team = Mock(return_value=True)
        self.task._fight_mammon = Mock(return_value=None)
        self.task.exit_anomaly = Mock()

        self.assertFalse(self.task._claim_weekly_mammon(self.progress))
        self.progress.mark_done.assert_not_called()
        self.task.exit_anomaly.assert_called_once()
