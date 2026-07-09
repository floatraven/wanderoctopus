# -*- coding: utf-8 -*-
"""家系链(Lineage)——纯函数,不 import 引擎状态,可独立单测。

一个朋友是链上的一个节点(dict,可直接 JSON):
{
  "id": "crab_reef_017_gen2",
  "name": "小螯",
  "species": "crab",
  "generation": 2,
  "ancestor_id": "crab_reef_017_gen1",
  "friendship": 80,              # 永不显示给玩家
  "inherit_ratio": 0.6,
  "lifespan": 120,
  "born_at": 3400,
  "memory_of_octopus": "indirect",
  "last_met": 3500,             # 章鱼上次亲自见到这条家系的潮
  "known_generation": 0,        # 章鱼亲自认识过的最高世代(算世代差用)
  "met_count": 1,               # 章鱼一共跟这条家系打过几次招呼
}
"""

from config import (
    MEMORY_LEVELS, SPECIES_LIFESPAN, INHERIT_RATIO_DEFAULT,
    FORGET_THRESHOLD, GREET_WARMTH, FRIENDSHIP_CAP, REPERSONALIZE_AT,
)

import random as _random

# 子代名字池:给点味道,不够就编号续
NAME_POOL = {
    "tubeworm": ["红顶", "新茬", "急急", "又冒", "刚醒"],
    "crab": ["小螯", "石缝", "斑斑", "横横", "旧钳", "半夹"],
    "goby": ["一寸", "沙沙", "眨眨", "浅浅", "碎碎"],
    "seahorse": ["卷卷", "立立", "慢慢", "悬悬"],
    "anglerfish": ["灯灯", "深深", "微亮"],
    "turtle": ["阿龟"],  # 她只有一个。
}


def descendant_name(species: str, base_id: str, gen: int, parent_name: str) -> str:
    """给子代取名。按家系与世代做确定性抽取(可复现、可单测),
    并保证两件事:
    1. 不同海的同种家系不再同步撞名(以前是 gen % 池长,全海一个节拍);
    2. 子代不会顶着父代刚放下的名字(名字的轮回要隔几代才动人)。
    名字池是轮回的:隔上几代,"一寸"还是会在新的一茬身上复活——这是特性,不是bug。"""
    pool = NAME_POOL.get(species, [])
    if not pool:
        return f"{species}_{gen}"
    if len(pool) == 1:
        return pool[0]
    rng = _random.Random(f"{base_id}:{gen}")
    return rng.choice([n for n in pool if n != parent_name])


def downgrade_memory(level: str) -> str:
    """记忆降一级:direct → indirect → legend → none,到底不再降。"""
    i = MEMORY_LEVELS.index(level)
    return MEMORY_LEVELS[min(i + 1, len(MEMORY_LEVELS) - 1)]


def upgrade_memory(level: str) -> str:
    """记忆升一级(反复亲自见面,后代重新认识了你本人)。"""
    i = MEMORY_LEVELS.index(level)
    return MEMORY_LEVELS[max(i - 1, 0)]


def make_descendant(node: dict, born_at: int) -> dict:
    """由父代生成子代。纯函数,不改入参。友善按比例继承,记忆降一档。"""
    gen = node["generation"] + 1
    base_id = node["id"].rsplit("_gen", 1)[0]
    name = descendant_name(node["species"], base_id, gen, node["name"])
    return {
        "id": f"{base_id}_gen{gen}",
        "name": name,
        "species": node["species"],
        "generation": gen,
        "ancestor_id": node["id"],
        "friendship": round(node["friendship"] * node.get("inherit_ratio", INHERIT_RATIO_DEFAULT), 2),
        "inherit_ratio": node.get("inherit_ratio", INHERIT_RATIO_DEFAULT),
        "lifespan": node["lifespan"],
        "born_at": born_at,
        "memory_of_octopus": downgrade_memory(node["memory_of_octopus"]),
        "last_met": node.get("last_met", node["born_at"]),
        "known_generation": node.get("known_generation", 0),  # 沿链传下去
        "met_count": 0,  # 后代还没亲自被打过招呼
    }


def settle_node(node: dict, now: int):
    """把一个节点推演到 now。elapsed 远超寿命时循环换代。

    返回 (当前存活节点, 事件列表)。事件供叙事用,不上屏。
    """
    events = []
    current = dict(node)
    while now - current["born_at"] >= current["lifespan"]:
        died_at = current["born_at"] + current["lifespan"]
        child = make_descendant(current, born_at=died_at)
        events.append({"type": "succession", "old_id": current["id"],
                       "new_id": child["id"], "at": died_at})
        current = child
    return current, events


def settle_region(region: dict, now: int):
    """结算一片海域:推演所有家系。纯函数。"""
    new_region = dict(region)
    all_events, new_lineages = [], []
    for node in region.get("lineages", []):
        settled, events = settle_node(node, now)
        new_lineages.append(settled)
        all_events.extend(events)
    _dedupe_living_names(new_lineages)
    new_region["lineages"] = new_lineages
    new_region["last_visit"] = now
    return new_region, all_events


def _dedupe_living_names(lineages: list) -> None:
    """同一片海里,活着的两条家系不该同时顶着一个名字——玩家会绕晕,
    叙事会露馅(两丛管虫的接班人都叫\"急急\",像复制粘贴)。
    后结算的那条让名:确定性地(按 id 播种)从池里另抽一个没被占用的。
    只动 settle_node 刚复制出来的新节点,不碰入参,settle_region 仍是纯函数。"""
    taken = set()
    for node in lineages:
        if node["name"] in taken:
            pool = NAME_POOL.get(node["species"], [])
            free = [n for n in pool if n not in taken]
            if free:
                rng = _random.Random(f"{node['id']}:dedupe")
                node["name"] = rng.choice(free)
        taken.add(node["name"])


def is_forgotten(node: dict, now: int) -> bool:
    """章鱼遗忘:关系够深(friendship>=80)但同一个体太久没见。

    引擎记得,主角忘了,关系还在。触发时不显示名字,由对方先开口认亲。
    注意:短命物种隔久了是"换代"而非"遗忘"——你不会忘一只螃蟹,
    你会遇到它的曾曾孙,它只把你当传说。遗忘只发生在活得够久的个体身上。
    """
    return node["friendship"] >= 80 and (now - node.get("last_met", node["born_at"])) > FORGET_THRESHOLD


def gen_gap(node: dict) -> int:
    """当前节点比章鱼亲自认识过的世代下移了几代。"""
    return node["generation"] - node.get("known_generation", 0)


def band(node: dict) -> str:
    f = node["friendship"]
    return "high" if f >= 60 else ("mid" if f >= 30 else "low")


def greeting_key(node: dict, now: int):
    """重逢台词池三维索引:(世代差, 友善区间, 是否已遗忘)。"""
    return (gen_gap(node), band(node), is_forgotten(node, now))


def record_meeting(node: dict, now: int) -> dict:
    """认亲后更新节点(纯函数):

    - last_met = now,遗忘 flag 天然解除
    - known_generation 抬到当前世代(世代差归零)
    - 友善悄悄加深(引擎侧,玩家不可见)
    - 反复见面够多次,后代重新把你当熟人(记忆回升一档)
    """
    n = dict(node)
    n["last_met"] = now
    n["known_generation"] = n["generation"]
    n["friendship"] = min(FRIENDSHIP_CAP, n["friendship"] + GREET_WARMTH)
    n["met_count"] = n.get("met_count", 0) + 1
    if n["met_count"] >= REPERSONALIZE_AT and n["memory_of_octopus"] != "direct":
        n["memory_of_octopus"] = upgrade_memory(n["memory_of_octopus"])
        n["met_count"] = 0
    return n


def new_lineage(species: str, name: str, region_id: str, idx: int,
                born_at: int, friendship: float = 10.0) -> dict:
    """开一条新家系(章鱼第一次认识某个朋友)。"""
    return {
        "id": f"{species}_{region_id}_{idx:03d}_gen0",
        "name": name,
        "species": species,
        "generation": 0,
        "ancestor_id": None,
        "friendship": friendship,
        "inherit_ratio": INHERIT_RATIO_DEFAULT,
        "lifespan": SPECIES_LIFESPAN[species],
        "born_at": born_at,
        "memory_of_octopus": "direct",
        "last_met": born_at,
        "known_generation": 0,
        "met_count": 0,
    }
