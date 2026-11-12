import unittest
from datetime import UTC, datetime
from unittest.mock import Mock, patch

from ok import Box

from src.tasks.anomaly_sweep import AnomalySweep, SweepQuota
from src.tasks.AnomalyTask import AnomalyTask
from src.tasks.weekly_progress import SWEEP_EXHAUSTED, week_start


class TestAnomalySweep(unittest.TestCase):
    def test_reads_remaining_count_and_rejects_unrelated_or_invalid_numbers(self):
        self.assertEqual(SweepQuota.read("探索次数：0/10"), SweepQuota(0, 10))
        self.assertEqual(SweepQuota.read("探索次数 : 2 / 5"), SweepQuota(2, 5))
        for text in ("0/10", "39/360", "探索次数：11/10", "探索次数：0/0"):
            with self.subTest(text=text):
                self.assertIsNone(SweepQuota.read(text))

    def test_week_boundary_uses_server_time(self):
        self.assertEqual(week_start(datetime(2026, 11, 15, 20, 59, tzinfo=UTC)), "2026-11-09")
        self.assertEqual(week_start(datetime(2026, 11, 15, 21, 0, tzinfo=UTC)), "2026-11-16")

    @patch("src.tasks.weekly_progress.Config")
    def test_only_confirmed_zero_is_cached_for_the_current_account_and_week(self, config):
        with patch("src.tasks.weekly_progress.datetime") as now:
            now.now.return_value = datetime(2026, 11, 12, 11, 0, tzinfo=UTC)
            progress = {SWEEP_EXHAUSTED: {}}
            config.return_value = progress
            task = Mock()
            task.ocr.return_value = [Box(1, 1, 10, 10, name="UID: 123456789")]
            sweep = AnomalySweep(task)
            sweep._open_panel = Mock(side_effect=[None, SweepQuota(2, 10), SweepQuota(0, 10)])

            self.assertIsNone(sweep.check())
            self.assertEqual(sweep.check(), 2)
            self.assertEqual(progress[SWEEP_EXHAUSTED], {})
            self.assertEqual(sweep.check(), 0)
            self.assertEqual(sweep.check(), 0)
            self.assertEqual(sweep._open_panel.call_count, 3)

            sweep._open_panel.side_effect = None
            sweep._open_panel.return_value = SweepQuota(10, 10)
            task.ocr.return_value = [Box(1, 1, 10, 10, name="UID: 123456788")]
            self.assertEqual(sweep.check(), 10)

            task.ocr.return_value = [Box(1, 1, 10, 10, name="UID: 123456789")]
            now.now.return_value = datetime(2026, 11, 15, 21, 0, tzinfo=UTC)
            self.assertEqual(sweep.check(), 10)

    @patch("src.tasks.AnomalyTask.AnomalySweep")
    def test_positive_quota_skips_regular_dungeon(self, sweep):
        task = object.__new__(AnomalyTask)
        task.config = {
            task.CONF_TASK_TYPE: task.TASK_EXP_COIN,
            task.CONF_EXP_TARGET: task.EXP_CHAR,
            task.CONF_CHECK_SWEEP: True,
        }
        task.log_info = Mock()
        task.info_set = Mock()
        task.ensure_main = Mock()
        task.resolve_stamina_target = Mock(return_value=40)
        task.open_f1_domain_page = Mock()
        sweep.return_value.check.return_value = 1

        self.assertIsNone(task.do_run())
        task.open_f1_domain_page.assert_not_called()
