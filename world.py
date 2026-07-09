# -*- coding: utf-8 -*-
"""世界状态 + 海域图 + 存档。读写各一处,别处不碰磁盘。

阿龟不属于任何海域——她是全局跟随的:章鱼在哪片海,她就在哪片海。
她哪都能找到章鱼,理由不解释,这很她。
"""
import json
import os

from config import SAVE_PATH
from lineage import new_lineage

# 海域之间的旅程代价(潮)。旅行是世代翻页的地方。
REGION_GRAPH = {
    ("reef", "kelp"): 40,
    ("kelp", "deep"): 70,
    ("reef", "deep"): 120,
    ("deep", "vent"): 50,    # 热泉紧挨着深海底,顺流而下没多远
    ("kelp", "vent"): 90,
    ("reef", "tide"): 25,    # 潮间带就在礁盘上缘,涨潮时是一片海,退潮时是很多小海
    ("tide", "kelp"): 55,
    ("deep", "wreck"): 45,   # 沉船躺在深海边的斜坡上,黑暗替它挡了大半个世界
    ("wreck", "vent"): 80,
    ("reef", "vent"): 100,   # 从浅水一路下到热泉,要穿过好几层水色
    ("reef", "wreck"): 130,  # 从阳光最亮的地方到最暗的角落,整片海的距离
    ("tide", "deep"): 110,   # 从最浅的水洼到最深的黑暗
    ("tide", "vent"): 95,
    ("tide", "wreck"): 120,
    ("kelp", "wreck"): 85,   # 海藻林下方的斜坡,渐渐变暗
}

REGION_NAMES = {"reef": "珊瑚礁", "kelp": "海藻林", "deep": "深海",
                "vent": "热泉", "tide": "潮间带", "wreck": "沉船"}


def travel_cost(a: str, b: str) -> int:
    return REGION_GRAPH.get((a, b)) or REGION_GRAPH.get((b, a)) or 60


def neighbors(region_id: str) -> list:
    """与某片海直接相邻的海(歌就顺着这些边被带去别处)。"""
    ns = set()
    for a, b in REGION_GRAPH:
        if a == region_id:
            ns.add(b)
        elif b == region_id:
            ns.add(a)
    return sorted(ns)


def fresh_world() -> dict:
    """新档。阿龟全局跟随,单列;各海域有自己的本地居民与一个偏长寿的锚点。"""
    return {
        "version": 3,
        "clock": 0,                      # 单位:潮,只靠动作推进
        "current_region": "reef",
        "turtle": new_lineage("turtle", "阿龟", "sea", 1, born_at=0, friendship=100.0),
        "regions": {
            "reef": {
                "id": "reef", "name": "珊瑚礁", "last_visit": -1,
                "lineages": [
                    new_lineage("crab", "小螯", "reef", 17, born_at=0, friendship=30.0),
                    new_lineage("goby", "一寸", "reef", 2, born_at=0, friendship=15.0),
                    new_lineage("seahorse", "卷卷", "reef", 3, born_at=0, friendship=20.0),
                ],
            },
            "kelp": {
                "id": "kelp", "name": "海藻林", "last_visit": -1,
                "lineages": [
                    new_lineage("crab", "石缝", "kelp", 4, born_at=0, friendship=10.0),
                    new_lineage("goby", "沙沙", "kelp", 5, born_at=0, friendship=10.0),
                    new_lineage("seahorse", "立立", "kelp", 6, born_at=0, friendship=10.0),
                ],
            },
            "deep": {
                "id": "deep", "name": "深海", "last_visit": -1,
                "lineages": [
                    new_lineage("anglerfish", "灯灯", "deep", 7, born_at=0, friendship=10.0),
                    new_lineage("seahorse", "慢慢", "deep", 8, born_at=0, friendship=10.0),
                ],
            },
            # 热泉:一片当场翻页的海。管虫几潮一代,你能坐着看名字一茬换一茬;
            # 一只长寿的岩钳蟹是这片急海里唯一慢下来的锚点——快与慢挨在一处。
            "vent": {
                "id": "vent", "name": "热泉", "last_visit": -1,
                "lineages": [
                    new_lineage("tubeworm", "红顶", "vent", 9, born_at=0, friendship=10.0),
                    new_lineage("tubeworm", "小冒", "vent", 16, born_at=3, friendship=10.0),
                    new_lineage("crab", "岩钳", "vent", 11, born_at=0, friendship=10.0),
                ],
            },
            # 潮间带:每一潮都把这里抹平重画一遍的海。比热泉更极端——
            # 热泉是居民换得快,这儿是"世界"本身一天两次被拿走再还回来。
            "tide": {
                "id": "tide", "name": "潮间带", "last_visit": -1,
                "lineages": [
                    new_lineage("crab", "翻翻", "tide", 12, born_at=0, friendship=10.0),
                    new_lineage("goby", "弹弹", "tide", 13, born_at=0, friendship=10.0),
                ],
            },
            # 沉船:全游戏唯一比章鱼更不变的东西。你到处看别人代谢——
            # 只有在这儿,轮到你当"快"的那个。
            "wreck": {
                "id": "wreck", "name": "沉船", "last_visit": -1,
                "lineages": [
                    new_lineage("seahorse", "缆缆", "wreck", 14, born_at=0, friendship=10.0),
                    new_lineage("crab", "锅底", "wreck", 15, born_at=0, friendship=10.0),
                ],
            },
        },
        "traces": [],
        "dwell": {"reef": 0, "kelp": 0, "deep": 0, "vent": 0, "tide": 0, "wreck": 0},
        "proverbs": [],
        "journal_entries": [],   # 你做过的事的残影——会被时间改写,越久越模糊
        "letter": None,          # 最新的一封信(留给下一个自己;不进世界,不会代谢)
        "letters": [],           # 历代的你留下的信,按先来后到叠成一小叠——你自己也是一条家系
        "seen_ids": [],          # 章鱼亲眼见过的那些"个体"。没打过照面的,谈不上"你记得"
    }


def _migrate(world: dict) -> dict:
    """把旧档补齐到当前结构:后加的海域按新档模板塞进去,别的原样保留。
    章鱼是会忘的,存档不该因为世界长出了新海域就崩掉。"""
    fresh = fresh_world()
    world.setdefault("regions", {})
    for rid, region in fresh["regions"].items():
        world["regions"].setdefault(rid, region)
    world.setdefault("dwell", {})
    for rid in fresh["dwell"]:
        world["dwell"].setdefault(rid, 0)
    world.setdefault("traces", [])
    world.setdefault("proverbs", [])
    world.setdefault("journal_entries", [])
    world.setdefault("letter", None)
    world.setdefault("seen_ids", [])
    if "letters" not in world:   # 旧档只有单封信:把它接进信叠,一封不丢
        world["letters"] = [world["letter"]] if world.get("letter") else []
    world["version"] = fresh["version"]
    return world


def load_world() -> dict:
    if os.path.exists(SAVE_PATH):
        try:
            with open(SAVE_PATH, "r", encoding="utf-8") as f:
                return _migrate(json.load(f))
        except (json.JSONDecodeError, OSError):
            try:  # 坏档不惩罚:留个备份,静默开新档
                os.replace(SAVE_PATH, SAVE_PATH + ".broken")
            except OSError:
                pass
    return fresh_world()


def save_world(world: dict) -> None:
    tmp = SAVE_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(world, f, ensure_ascii=False, indent=1)
    os.replace(tmp, SAVE_PATH)   # 原子写,断电不丢档
