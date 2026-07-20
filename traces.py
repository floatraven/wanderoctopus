# -*- coding: utf-8 -*-
"""痕迹(Traces)——本作题眼。纯函数。

章鱼不老,但它留下的东西会老、会变形、会被误传。
这是章鱼和世界之间唯一的平等。

两类痕迹:
  实物痕迹(石堆 / 贝壳螺旋):integrity 随时间衰减,不删除而是变形,
      残缺后可能被某个家系认领为"老地方"。
  歌(教出去的半句歌):跨世代口耳相传,跑调,骨架仍可辨——
      隔了几代从某只小鱼嘴里哼回来,是全游戏情绪最高点。
"""

from config import TRACE_DECAY_PER_TIDE, TRACE_HALF, TRACE_SCATTERED, SPECIES_LIFESPAN

# ---- 可教的歌:每首有一条"跑调链",key 是口耳相传的代数(hop)----
# 骨架可辨,越传越走样。slow_grow 磨到几乎只剩一个哼声——那是被时间磨薄的谚语。
SONGS = {
    "deep_water": {
        0: ["跟着大的走", "别怕深水"],
        1: ["别怕深水", "跟着大的走"],
        2: ["别怕深的", "大的在前头走"],
        3: ["深的不怕", "前头有大的"],
    },
    "slow_grow": {
        0: ["长得慢没关系", "断了也慢"],
        1: ["长得慢,断得慢"],
        2: ["慢的,慢的"],
        3: ["慢——"],
    },
    "coral_lullaby": {
        0: ["珊瑚不说话", "它用长来回答"],
        1: ["珊瑚不说话", "谁在回答"],
        2: ["不说话的", "在回答"],
        3: ["不说——"],
    },
    "light_chase": {
        0: ["追光的往上游", "沉底的自己亮"],
        1: ["往上的追光", "底下的亮着"],
        2: ["上面有光", "底下也有"],
        3: ["有光", "也有"],
        4: ["有——"],
    },
    "warm_drift": {
        0: ["烫的水边长得急", "凉了就走"],
        1: ["烫边急", "凉了走"],
    },
    "tide_song": {
        0: ["数潮的人不老", "潮替它老"],
        1: ["数潮的不老", "潮老了"],
        2: ["不老的在数", "老的在走"],
        3: ["数——", "走——"],
        4: ["潮——"],
    },
    "small_fish": {
        0: ["小的也在", "大的看不见它"],
        1: ["小的在呢", "没人看见"],
        2: ["在呢", "没人看"],
        3: ["在——"],
    },
    "stay_song": {
        0: ["不走的留下来", "走的也还会回来"],
        1: ["不走的留着", "走了还来"],
        2: ["留着吧", "会来的"],
        3: ["留——", "来——"],
        4: ["留——"],
    },
}

# 实物痕迹的三态描述:(完整, 半塌, 残缺/被认领)
TRACE_STAGES = {
    "stone_pile": {
        "intact": "你垒的那堆石头还立着,一块没少。",
        "half": "石堆塌了半边,底下几块陷进了沙里。",
        "scattered": "石头散了一地,快看不出是堆过的。",
        "adopted": "你垒的石头塌成了矮矮一圈,螃蟹们把这里叫做老地方。",
    },
    "shell_spiral": {
        "intact": "你摆的贝壳螺旋还在,一圈一圈朝里卷。",
        "half": "螺旋被海流冲开了小半,外圈的贝壳不见了。",
        "scattered": "只剩里头小半圈贝壳,弯着,像谁随手撇下的。",
        "adopted": "残缺的螺旋成了一窝小螃蟹的记号,它们绕着它转。",  # 旧档遗留态,新档不再产生
        "continued": "你摆的螺旋塌了半圈,又被谁续上了几枚——方向不对,间距也不对,可它还在往里卷。像一句被接错了、却没人肯停下的话。",
        "carried": "你摆的贝壳被小螃蟹们一枚一枚搬走了,搬去垫自己的洞口。螺旋没了——它散进了好多户人家的门前。",
    },
}

# 石头和贝壳不该塌成同一种下场:
#   石头沉、搬不动 → 塌在原地,被认成"老地方",变成别人的路标(聚)。
#   贝壳轻、拿得走 → 要么被不认识的谁接着摆(续),要么被一枚一枚搬散(散)。
# 选哪个留痕,从此是两种告别。


def new_stone_pile(region_id: str, now: int) -> dict:
    return _new_object("stone_pile", region_id, now)


def new_shell_spiral(region_id: str, now: int) -> dict:
    return _new_object("shell_spiral", region_id, now)


def _new_object(kind: str, region_id: str, now: int) -> dict:
    return {
        "type": kind, "region": region_id, "created_at": now,
        "integrity": 1.0, "adopted_by": None,
    }


def new_song(song_id: str, region_id: str, taught_species: str, now: int) -> dict:
    return {
        "type": "song", "song_id": song_id, "region": region_id,
        "taught_species": taught_species, "taught_at": now,
    }


def settle_trace(trace: dict, now: int, region_has_crabs: bool) -> dict:
    """把一个实物痕迹推演到 now。纯函数。歌和礼物不在这里衰减。
    integrity 始终基于原始 created_at 计算总衰减,不重置起点。"""
    if trace["type"] in ("song", "gift"):
        return dict(trace)
    t = dict(trace)
    elapsed = now - t["created_at"]
    t["integrity"] = max(0.0, 1.0 - elapsed * TRACE_DECAY_PER_TIDE)
    if t["integrity"] < 0.5 and not t["adopted_by"]:
        # 分岔用 created_at 的奇偶做确定性选择——不引入随机,存档可复现。
        if t["type"] == "shell_spiral":
            # 贝壳:被不认识的谁续摆(不需要螃蟹),或被螃蟹一枚枚搬走。
            if t["created_at"] % 2 == 0:
                t["adopted_by"] = "continued"
            elif region_has_crabs:
                t["adopted_by"] = "carried"
        elif region_has_crabs:
            # 石头:塌在原地,被螃蟹家系认成"老地方"。
            t["adopted_by"] = "crab_family"
    return t


def trace_stage(trace: dict) -> str:
    """实物痕迹此刻处于哪一态:intact / half / scattered / adopted。
    跨代叙述("石堆塌了半边")靠比对这个态的变化来触发。"""
    if trace.get("adopted_by") in ("continued", "carried"):
        return trace["adopted_by"]
    if trace.get("adopted_by"):
        return "adopted"
    i = trace["integrity"]
    if i >= TRACE_HALF:
        return "intact"
    if i >= TRACE_SCATTERED:
        return "half"
    return "scattered"


def describe_trace(trace: dict) -> str:
    """实物痕迹当前的样子。纯文字,无数字。"""
    return TRACE_STAGES[trace["type"]][trace_stage(trace)]


def song_hops(trace: dict, now: int) -> int:
    """一首歌传了几代 = 经过的潮 // 传唱物种的寿命,封顶到跑调链末端。"""
    life = SPECIES_LIFESPAN[trace["taught_species"]]
    hops = (now - trace["taught_at"]) // max(1, life)
    max_hop = max(SONGS[trace["song_id"]].keys())
    return int(min(hops, max_hop))


def render_song(trace: dict, now: int) -> str:
    """当前这一代把歌哼成了什么样。骨架可辨。"""
    hops = song_hops(trace, now)
    return " ".join(SONGS[trace["song_id"]][hops])


def song_has_drifted(trace: dict, now: int) -> bool:
    """歌是否已经跑到了下一代嘴里(值得让 NPC 哼回来)。"""
    return song_hops(trace, now) >= 1


def song_return_ready(trace: dict, now: int, min_hops: int) -> bool:
    """歌是否走样得够远、够久,值得被一条小鱼当"祖上传下来的老歌"郑重教还给你。
    跑调链太短的歌(几乎没变过样)永远不回流——认不出来才叫回流。"""
    max_hop = max(SONGS[trace["song_id"]].keys())
    hops = song_hops(trace, now)
    return hops >= 2 and hops >= min(min_hops, max_hop)


# ---- 礼物:给某个朋友留的小东西,随家系传下去,记忆会淡 ----
GIFT_KINDS = {
    "pebble": "一颗光滑的石子",
    "shell": "一枚小贝壳",
    "seaglass": "一片磨圆的海玻璃",
}

# 对话里提到礼物时用短称,避免"那个一枚小贝壳"的别扭
GIFT_SHORT = {
    "pebble": "石子",
    "shell": "贝壳",
    "seaglass": "海玻璃",
}

import random as _rng


def new_gift(region_id: str, lineage_root: str, friend_name: str, now: int) -> dict:
    return {
        "type": "gift",
        "region": region_id,
        "lineage_root": lineage_root,
        "given_to_name": friend_name,
        "gift_kind": _rng.choice(list(GIFT_KINDS)),
        "created_at": now,
    }


def render_hybrid(a: dict, b: dict, now: int) -> str:
    """两首歌在同一片海里串了调:取一首的头,接另一首的尾,拼成一句四不像。
    这是"迁徙"的落点——一片海飘来的调子,和本地的调子,长成了谁也不是的东西。"""
    la = SONGS[a["song_id"]][song_hops(a, now)]
    lb = SONGS[b["song_id"]][song_hops(b, now)]
    return f"{la[0]} {lb[-1]}"
