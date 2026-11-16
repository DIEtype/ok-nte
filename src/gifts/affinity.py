from dataclasses import asdict, dataclass
import re


# Incremental thresholds recorded on the in-game affinity panel.
# https://www.taptap.cn/moment/804373686940339398
# https://www.psnine.com/trophy/51218003
LEVEL_COSTS = (100, 500, 1000, 2000, 3500, 5000, 7000, 9000, 12000, 16000)
MAX_LEVEL = len(LEVEL_COSTS)
MAX_AFFINITY = sum(LEVEL_COSTS)
_LEVEL = re.compile(r"(?:lv\.?\s*)?(10|[0-9])(?:级)?", re.IGNORECASE)
_PROGRESS = re.compile(r"(\d{1,5})[/／](\d{2,5})")


@dataclass(frozen=True)
class AffinityProgress:
    level: int
    points: int | None = None
    next_level: int | None = None

    @property
    def remaining(self) -> int | None:
        if self.level == MAX_LEVEL:
            return 0
        if self.points is None or self.next_level != LEVEL_COSTS[self.level]:
            return None
        return sum(LEVEL_COSTS[self.level:]) - self.points

    def to_dict(self) -> dict:
        return asdict(self)


def load_affinity(data: dict | None) -> AffinityProgress | None:
    if not isinstance(data, dict):
        return None
    level, points, goal = (data.get(key) for key in ("level", "points", "next_level"))
    if type(level) is not int or not 0 <= level <= MAX_LEVEL:
        return None
    if type(points) is int and type(goal) is int and 0 <= points <= goal:
        return AffinityProgress(level, points, goal)
    return AffinityProgress(level)


def parse_affinity(texts: list[str]) -> AffinityProgress | None:
    level = None
    for text in texts:
        clean = "".join(text.split()).replace(",", "").replace("，", "")
        if level is None and (match := _LEVEL.fullmatch(clean)):
            level = int(match[1])
            if level == MAX_LEVEL:
                return AffinityProgress(MAX_LEVEL)
        if match := _PROGRESS.fullmatch(clean):
            points, goal = map(int, match.groups())
            if level is None and goal in LEVEL_COSTS:
                level = LEVEL_COSTS.index(goal)
            if level is not None and 0 <= points <= goal:
                return AffinityProgress(level, points, goal)
    return AffinityProgress(level) if level is not None else None
