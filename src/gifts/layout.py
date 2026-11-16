from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GiftLayout:
    name_ratio: tuple[float, float, float, float] = (0.524, 0.148, 0.750, 0.222)
    gift_first_ratio: tuple[float, float, float, float] = (0.533, 0.479, 0.584, 0.516)
    gift_columns: int = 5
    gift_rows: int = 2
    gift_column_step: float = 0.0651
    gift_row_step: float = 0.1351
    unlimited_icon_x_offset_ratio: float = 0.10
    unlimited_icon_y_offset_ratio: float = 0.74
    unlimited_icon_width_reduction_ratio: float = 0.45
    character_slot_x: float = 0.946
    character_slot_ys: tuple[float, ...] = (0.177, 0.326, 0.472, 0.624, 0.772)
    sidebar_box: tuple[float, float, float, float] = (0.928, 0.133, 0.966, 0.815)
    sidebar_scroll_x: float = 0.947
    sidebar_scroll_y: float = 0.500
    sidebar_scroll_step: int = -2
    sidebar_reset_step: int = 40
    max_sidebar_pages: int = 55
    affinity_box: tuple[float, float, float, float] = (0.765, 0.148, 0.862, 0.275)
    send_button: tuple[float, float] = (0.656, 0.787)
    counter_box: tuple[float, float, float, float] = (0.589, 0.763, 0.720, 0.813)
    daily_counter_box: tuple[float, float, float, float] = (0.544, 0.686, 0.851, 0.754)
    first_gift_stock_band: tuple[float, float] = (0.517, 0.548)
    first_gift_affinity_band: tuple[float, float] = (0.549, 0.588)


GIFT_LAYOUT = GiftLayout()
