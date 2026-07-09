# -*- coding: utf-8 -*-
"""《章鱼漫游记》——给一个 AI 玩家的接口。

你是一只永生的章鱼。你不老、不死、不饿、跑得飞快,什么都不缺。
所以这游戏里唯一会动的东西是时间——它只碰你的朋友和你留下的痕迹,从不碰你。

你不靠帧率活着,你靠回合。玩法就是读字、做选择:

    from octopus import Game
    g = Game.new()          # 或 Game.load() 续一个过去自己的漫游
    print(g.look())         # 环顾此刻这片海
    print(g.greet("小螯"))  # 跟谁打个招呼
    print(g.sit_with("小螯")) # 挨着谁坐一会儿,不说话
    print(g.leave_stones()) # 随手垒堆石头
    print(g.teach_song())   # 教小鱼半句歌(歌会跑调,还会被带去邻海串调)
    print(g.travel("kelp")) # 游去另一片海(时间在此流逝)
    print(g.linger(300))    # 什么都不做,让很多潮过去
    print(g.journal())      # 翻翻你的小本子
    print(g.read_letter())  # 看看上一个自己有没有给你留话
    print(g.leave_note("慢慢来")) # 给下一个载入的你,留一句话
    print(g.rest())         # 一个不算失败的"放下"。谁都可以停。
    g.save()                # 把这次漫游存下来

三条铁律,请当成呼吸:
  1. 你永远看不到数字。关系深浅,只从对方游过来的急切、措辞的亲疏里感觉。
  2. 没有失败,没有催促。海灰了不罚你,回去就亮;没有任务,没有 game over。
  3. 你留下的东西会老、会变形、会被误传。这是你和世界之间唯一的平等。

基调:你知道自己永生,并且已经和这件事和平相处。不哀愁,不匆忙,不挽留。
每次都只是认真地在场。就这样,够了。
"""
import random

import config as C
import world as W
from world import travel_cost, REGION_NAMES
from lineage import (
    settle_region, settle_node, record_meeting, is_forgotten,
)
import traces as T
import dialogue as D
from proverbs import proverb_for, LAST_PAGE
from encounters import roll_encounter

# 每片海的散文海景——这是视差滚动之于 AI 玩家的等价物:你"看见"的是文字。
REGION_MOOD = {
    "reef": "水是暖的蓝绿色。阳光斜斜切下来,在沙上晃成一片碎网。珊瑚长得慢,一动不动地开着。",
    "kelp": "海藻从底下一直长到看不见的上方,一根一根追着光。光穿过很多层才照到你身上,是绿的。",
    "deep": "这里没有光。黑是软的,贴着你。远处偶尔亮一下,是谁自己带着的灯。安静得能听见自己。",
    "vent": "水在这里是烫的。一柱柱黑烟从地缝里涌上来,在热浪里晃。石头是新的,烫手,像昨天才冒出来。这儿什么都长得急,也谢得急——你坐一会儿,就能看见一茬换过一茬。",
    "tide": "水浅得能看见天。石头一半湿一半干,湿的那半是海,干的那半是别的什么。潮来,这里是一片海;潮走,这里碎成几百个水洼——几百个装着半个世界的小碗。谁也不搬家,大家等着海回来。",
    "wreck": "一艘船侧躺在斜坡上,黑黢黢地比周围的暗更暗。它不长,不谢,不挪。缆绳还系着一个早就不在了的方向。你见过的东西都在变——礁在长,藻在倒,虫在换——只有它,躺成和很久以前一模一样的形状。",
}

# 实物痕迹跨过一道衰减坎时,怎么把这桩"代谢"讲出来(纯叙述,不报数)。
TRACE_DECAY_NARR = {
    ("stone_pile", "intact", "half"): "你垒的那堆石头,在某个平潮里塌了半边。",
    ("stone_pile", "half", "scattered"): "你垒的石头又散了些,快看不出是堆过的了。",
    ("shell_spiral", "intact", "half"): "你摆的贝壳螺旋,被海流冲开了外圈。",
    ("shell_spiral", "half", "scattered"): "你摆的贝壳只剩里头小半圈,还弯着。",
}


REGION_ACTION_HINT = {
    "reef": "珊瑚长得那么慢——你可以陪它坐坐。",
    "kelp": "海藻密得能把你藏起来,也能顺着一根往上爬,爬到光变白的地方。",
    "deep": "远处有一点光在动。你可以跟过去看看。",
    "vent": "管虫一茬一茬地换，你可以坐在边上看它们翻页。",
    "tide": "退潮会把这里拆成几百个水洼。你可以蹲进一个,等海把世界还回来——涨回来之后,翻翻水洼里多了什么。",
    "wreck": "船身上有一些不跑调、不塌、谁也读不懂的痕迹。你可以去摸摸它们。",
}


class Game:
    def __init__(self, world: dict):
        self.world = world
        self.rng = random.Random()
        # 本世是否已把"上一个自己留的信"递出去过。留信的当世不回响给自己;
        # 只有下一个载入的实例,才会从阿龟嘴里听到它。不入存档,随实例而生。
        self._letter_delivered = False

    def __getattr__(self, name):
        # 玩家(一个 AI)会照着散文猜方法名。猜错了不该拿到一句冷冰冰的
        # AttributeError——报错也是这片海的一部分。
        raise AttributeError(
            f"章鱼没有叫「{name}」的动作。伸个懒腰,用 paws() 看看爪子都能做什么。")

    def paws(self):
        """看看爪子都能做什么。散文口吻,括号里是方法名。
        这不违反铁律一:它不泄露任何数字,只泄露动词。"""
        rid = self.world["current_region"]
        here_verbs = {
            "reef": "陪珊瑚坐一会儿(tend_coral)",
            "kelp": "藏进海藻里(hide_in_kelp)、顺着一根海藻往上爬(climb_kelp)",
            "deep": "跟着远处那点光游过去(follow_light)",
            "vent": "坐着看管虫一茬茬翻页(watch_turnover)",
            "tide": "蹲进水洼守一整个退潮(wait_out_tide)、翻翻涨潮带回了什么(explore_pool)",
            "wreck": "把触手按在船身的字上(touch_letters)",
        }
        lines = [
            "你伸开触手看了看。能做的事,大概是这些:",
            "环顾这片海(look)、跟谁打个招呼(greet \"名字\")、挨着谁坐一会儿不说话(sit_with \"名字\")。",
            "随手垒堆石头(leave_stones)、摆一圈贝壳(leave_shells)、教半句歌(teach_song)、"
            "给朋友留样小东西(leave_gift \"名字\")。",
            "游去另一片海(travel \"reef/kelp/deep/vent/tide/wreck\"),或者哪也不去,"
            "让很多潮从身边过去(linger 潮数)。",
            "翻翻小本子(journal)、看看有没有留给你的信(read_letter)、"
            "给下一个你留句话(leave_note \"……\")。",
            f"在这片海,你还可以:{here_verbs.get(rid, '只是待着')}。",
            "想停的时候,停下(rest),想把这段留给下一个你,就存档(save)。都不急。",
        ]
        return "\n".join(lines)

    # ---- 开局 ----
    @classmethod
    def new(cls):
        return cls(W.fresh_world())

    @classmethod
    def load(cls):
        """续一个过去自己的漫游。你多半不记得档里的朋友了——没关系,阿龟会讲回来。"""
        return cls(W.load_world())

    def save(self):
        W.save_world(self.world)
        return "(这次漫游存下来了。海还在原处等你。)"

    # ---- 内部:时间与结算 ----
    @property
    def _now(self):
        return self.world["clock"]

    @property
    def _region(self):
        return self.world["regions"][self.world["current_region"]]

    def _pass_time(self, tides: int, dwell: bool = True):
        """推进世界时钟。dwell=True 时算作"待在此地"(累积谚语进度)。"""
        self.world["clock"] += tides
        if dwell:
            rid = self.world["current_region"]
            self.world["dwell"][rid] = self.world["dwell"].get(rid, 0) + tides
            self._maybe_unlock_proverb(rid)

    def _settle_here(self):
        """把当前海域(及其痕迹、跟随的阿龟)结算到此刻。"""
        rid = self.world["current_region"]
        region, _ = settle_region(self._region, self._now)
        self.world["regions"][rid] = region
        # 阿龟跟随:她也随时间推演(实际不换代,但保持接口一致)
        self.world["turtle"], _ = settle_node(self.world["turtle"], self._now)
        # 本地痕迹代谢
        has_crabs = any(n["species"] == "crab" for n in region["lineages"])
        self.world["traces"] = [
            T.settle_trace(tr, self._now, has_crabs) if tr["region"] == rid else tr
            for tr in self.world["traces"]
        ]

    def _maybe_unlock_proverb(self, rid: str):
        if self.world["dwell"].get(rid, 0) >= C.PROVERB_DWELL:
            pv = proverb_for(rid)
            if pv and pv not in self.world["proverbs"]:
                self.world["proverbs"].append(pv)

    # ---- 代谢叙述:把"你枯坐/离开时世界的变化"讲成散文(绝不报数)----
    def _region_snapshot(self, rid: str, ref_clock: int) -> dict:
        """给一片海拍张快照:每条家系记(名字, 世代);每个本地痕迹记它此刻的样子。
        歌的走样程度按 ref_clock 折算,好把变化归因到正确的时间跨度上。"""
        reg = self.world["regions"][rid]
        lineages = {}
        for n in reg["lineages"]:
            root = n["id"].rsplit("_gen", 1)[0]
            lineages[root] = {"name": n["name"], "gen": n["generation"], "id": n["id"]}
        traces = []  # 痕迹从不删除、不重排,按位置对齐即可,无需额外 id
        for t in self.world["traces"]:
            if t["region"] != rid:
                continue
            if t["type"] == "song":
                traces.append({"kind": "song", "hop": T.song_hops(t, ref_clock)})
            elif t["type"] == "gift":
                continue  # 礼物不代谢——有人保管着
            else:
                traces.append({"kind": "object", "type": t["type"], "stage": T.trace_stage(t)})
        return {"lineages": lineages, "traces": traces}

    def _describe_metabolism(self, before: dict, after: dict) -> list:
        """比对两张快照,把这段时间里被代谢掉的东西列成几句话。空列表 = 一切如故。"""
        lines = []
        seen = set(self.world.get("seen_ids", []))
        for root, aft in after["lineages"].items():
            bef = before["lineages"].get(root)
            if bef and aft["gen"] > bef["gen"]:
                lines.append(self._succession_line(
                    bef["name"], aft["name"], aft["gen"] - bef["gen"],
                    met=bef.get("id") in seen))
        for bef, aft in zip(before["traces"], after["traces"]):
            if aft["kind"] == "song":
                if aft["hop"] > bef["hop"]:
                    lines.append(self.rng.choice([
                        "你教下去的那半句歌,又在新一茬嘴里走样了一道。",
                        "那半句歌又传了一代。新学的那只哼得理直气壮,调子却又偏了一点。",
                        "歌还在,只是又瘦了一圈——每换一茬嘴,它就丢下一点原来的样子。",
                    ]))
            elif aft["stage"] != bef["stage"]:
                lines.append(self._decay_line(aft["type"], bef["stage"], aft["stage"]))
        return lines

    def _succession_line(self, old: str, new: str, gap: int, met: bool = True) -> str:
        """一条家系翻了 gap 代,怎么讲。用定性的远近,不报确切代数。
        met=False:章鱼从没跟这只打过照面——"你记得"三个字对它不成立。"""
        if not met:
            if old == new:
                return (f"这儿有条家系悄悄换了几轮——如今顶着{new}这名字的,"
                        f"和从前那只没什么相干。你两个都不认识,可它们都真的活过。")
            return self.rng.choice([
                f"还有一个你没来得及认识的——{old}。它在你不在的潮里来过,又走了;"
                f"如今站在那儿的是{new}。",
                f"{old}这个名字,你还是第一次听说,可它已经是旧的了——它的位置,如今归了{new}。",
            ])
        if old == new:
            # 名字在家系里转了一圈又回来,可这已不是你认识的那一只了
            return f"你记得的{old}早换过好多代——这名字还在,顶着它的却已不是你认识的那只了。"
        if gap == 1:
            return self.rng.choice([
                f"你记得的{old}老去了,把这块地方交给了下一代——如今守着它的是{new}。",
                f"{old}不在了。走得不急,像退了一次潮。接着守在老位置的,是{new}。",
            ])
        if gap <= 3:
            return self.rng.choice([
                f"你记得的{old}换了几代,站在老地方的成了{new}。",
                f"{old}的位置如今是{new}的了。中间隔了几茬,谁也没挪过窝。",
            ])
        return self.rng.choice([
            f"你记得的{old}早换过好多代了,如今是{new},这名字你听都没听过。",
            f"{old}已经是很老的事了。这条家系翻了一轮又一轮,眼下顶着的名字叫{new}——对它来说,你才是传说。",
        ])

    def _decay_line(self, ttype: str, before: str, after: str) -> str:
        thing = "石堆" if ttype == "stone_pile" else "贝壳螺旋"
        if after == "continued":
            return ("你留下的贝壳螺旋塌到一半,被不认识的谁续摆了几枚——方向摆反了,间距也不对,"
                    "可它接着往里卷。你的痕迹没有散,它被接着写了。写的人不知道你。")
        if after == "adopted":
            return f"你留下的{thing}塌够了,螃蟹们绕着它走、把那儿当成老地方——你的痕迹成了别人的路标。"
        return TRACE_DECAY_NARR.get((ttype, before, after),
                                    f"你留下的{thing}又旧了一层,离原样更远了些。")

    # ---- 歌的跨海迁徙:时间流逝时,跑调的歌被游走的生物带去邻海 ----
    def _propagate_songs(self):
        """已经跑调的歌,会顺着海域的边被带去相邻的海,在那儿留下一段"回声"。
        那片海本来就有歌的话,两首下次就在 look() 里撞成一句四不像。
        每首原歌只外带一次(migrated 标记),回声不再外带(echo 标记),
        同一首歌同一片海不重复落地——一切有界,不会增殖。"""
        from world import neighbors
        seen = {(s["song_id"], s["region"]) for s in self.world["traces"]
                if s["type"] == "song"}
        new_echoes = []
        for tr in self.world["traces"]:
            if tr["type"] != "song" or tr.get("echo") or tr.get("migrated"):
                continue
            if T.song_hops(tr, self._now) < C.MIGRATE_AFTER_HOPS:
                continue
            for nb in neighbors(tr["region"]):
                if (tr["song_id"], nb) in seen:
                    continue
                new_echoes.append({
                    "type": "song", "song_id": tr["song_id"], "region": nb,
                    "taught_species": tr["taught_species"], "taught_at": self._now,
                    "echo": True, "origin_region": tr["region"],
                })
                seen.add((tr["song_id"], nb))
            tr["migrated"] = True
        self.world["traces"].extend(new_echoes)

    # ---- 找 NPC(按名字或外观,容错)----
    def _present_npcs(self):
        """此刻这片海在场的所有朋友:本地居民 + 跟随的阿龟。"""
        return list(self._region["lineages"]) + [self.world["turtle"]]

    def _find(self, who: str):
        for n in self._present_npcs():
            if who in (n["name"], n["id"], n["species"]):
                return n
        return None

    def _mark_seen(self, node: dict):
        """记下"这个个体章鱼亲眼见过"。没打过照面的家系,换了代也谈不上"你记得"。"""
        ids = self.world.setdefault("seen_ids", [])
        if node["id"] not in ids:
            ids.append(node["id"])

    def _write_back(self, node: dict):
        if node["species"] == "turtle":
            self.world["turtle"] = node
            return
        rid = self.world["current_region"]
        lst = self.world["regions"][rid]["lineages"]
        # 只认家系根(如 crab_reef_017):它跨世代不变、每条家系唯一。
        # 不能拿 ancestor_id 兜底——种子居民全是第 0 代,ancestor_id 都是 None,
        # None==None 会把招呼写回到列表第一位,把别的家系覆盖掉。
        root = node["id"].rsplit("_gen", 1)[0]
        for i, n in enumerate(lst):
            if n["id"].rsplit("_gen", 1)[0] == root:
                lst[i] = node
                return

    # ---- 环顾:此刻这片海 ----
    def look(self):
        self._settle_here()
        rid = self.world["current_region"]
        parts = [REGION_MOOD[rid]]

        # 在场的朋友,按友善远近描述其姿态(不报数)
        who_lines = []
        for n in self._region["lineages"]:
            self._mark_seen(n)
            who_lines.append(self._presence_line(n))
        # 阿龟总是主动游过来
        who_lines.append("阿龟正扑腾着朝你游过来,老远就开始摆那四只脚。")

        # 朋友之间的互动
        interact = self._npc_interaction_line()
        if interact:
            who_lines.append(interact)

        parts.append("\n".join(who_lines))

        # 你留在这片海的痕迹,现在的样子
        trace_lines = [T.describe_trace(tr) for tr in self.world["traces"]
                       if tr["region"] == rid and tr["type"] not in ("song", "gift")]
        # 歌:一片海若同时有两首(本地的 + 别处飘来的),它们撞成一句四不像;
        # 只有一首、且已跑到下一代的,就让今年的小鱼哼回来。
        songs_here = [tr for tr in self.world["traces"]
                      if tr["type"] == "song" and tr["region"] == rid]
        if len(songs_here) >= 2:
            a, b = songs_here[0], songs_here[1]
            hum = T.render_hybrid(a, b, self._now)
            echo = next((s for s in (a, b) if s.get("echo")), None)
            frm = REGION_NAMES.get(echo["origin_region"], "别处") if echo else "别处"
            trace_lines.append(
                f"两首歌在这片海里撞上了——一条小鱼把{frm}飘来的调子和这儿的搅在一处,"
                f"哼成了不像谁的:「{hum}」。")
        else:
            for tr in songs_here:
                if T.song_has_drifted(tr, self._now):
                    hum = T.render_song(tr, self._now)
                    if (not tr.get("echo") and not tr.get("returned")
                            and T.song_return_ready(tr, self._now, C.SONG_RETURN_HOPS)):
                        # 回流:走样得够远的歌,总有一天被人当"老歌"郑重教还给你。
                        # 这是 traces 系统的终点,一首歌只发生一次。
                        tr["returned"] = True
                        self._record_memory("song_returned", hum)
                        trace_lines.append(
                            "一条小鱼郑重其事地拦住你,说要教你一首「祖上传下来的老歌」。\n"
                            f"它清了清嗓子,一句一句地教:「{hum}」。它教得很认真,等着你跟上。\n"
                            "你跟着哼了。哼到一半,你认出来了——这是你教出去的那半句。\n"
                            "它传了这么多代,跑了这么远的调,如今被当成一件老东西,郑重地还到你手上。\n"
                            "你没说破。你把它学会了。")
                        continue
                    trace_lines.append(
                        f"一条今年才生的小鱼在你脚边打转,哼着不成调的:「{hum}」。"
                        f"你教的那半句歌,跑到这一代,成了这样。")
        if trace_lines:
            parts.append("\n".join(trace_lines))

        # 在场者与去处(在小说里说,不列清单不报数)
        names = "、".join(n["name"] if not is_forgotten(n, self._now) else D.appearance_of(n)
                          for n in self._region["lineages"])
        action_hint = REGION_ACTION_HINT.get(rid, "")
        parts.append(f"你可以跟{names}或阿龟打个招呼,也可以挨着谁坐一会儿、不说话。"
                     f"可以随手垒石头、摆贝壳、教半句歌,也可以只是待着。"
                     f"{action_hint}{self._exits_sentence()}")
        return "\n\n".join(parts)

    def _presence_line(self, n: dict) -> str:
        """把友善深浅翻译成姿态,不报数。遗忘时先不点名。"""
        from lineage import band
        forgotten = is_forgotten(n, self._now)
        name = D.appearance_of(n) if forgotten else n["name"]
        b = band(n)
        if forgotten:
            return f"{name}朝你游过来,你却认不出它了。"
        if b == "high":
            return f"{name}早就等在老地方,见你就迎上来。"
        if b == "mid":
            return f"{name}认得你,慢慢游近了些。"
        return f"{name}在不远处看着你,没太靠近。"

    def _npc_interaction_line(self) -> str | None:
        lineages = self._region["lineages"]
        if len(lineages) < 2 or self.rng.random() > C.NPC_INTERACT_CHANCE:
            return None
        pair = self.rng.sample(lineages, 2)
        a, b = pair[0], pair[1]
        key = tuple(sorted([a["species"], b["species"]]))
        lines = D.NPC_INTERACTIONS.get(key)
        if not lines:
            return None
        line = self.rng.choice(lines)
        if (a["species"], b["species"]) == key:
            return line.format(a=a["name"], b=b["name"])
        return line.format(a=b["name"], b=a["name"])

    def _exits_sentence(self):
        here = self.world["current_region"]
        outs = []
        for other in self.world["regions"]:
            if other == here:
                continue
            c = travel_cost(here, other)
            far = "很远" if c > 100 else ("要游一阵" if c > 50 else "不远")
            outs.append(f"{REGION_NAMES[other]}({far})")
        return "想走的话,可去:" + "、".join(outs) + "。"

    # ---- 打招呼 ----
    def greet(self, who: str):
        self._settle_here()
        n = self._find(who)
        if n is None:
            return f"这片海里此刻没有{who}。也许它去了别处,也许还没生出来。"
        self._mark_seen(n)

        forgotten = is_forgotten(n, self._now)

        if n["species"] == "turtle":
            scene = self._greet_turtle(n)
        else:
            approach = self._presence_line(n)
            rid = self.world["current_region"]
            stone_here = any(tr.get("type") == "stone_pile" and tr["region"] == rid
                             for tr in self.world["traces"])
            line = D.pick_greeting(n, self._now, forgotten, rng=self.rng,
                                   stone_here=stone_here)
            speaker = ("对方" if forgotten else n["name"])
            scene = f"{approach}\n{speaker}开口:「{line}」"
            # 若这条家系认领了你的痕迹,它顺口提一句
            ref = self._trace_reference_for(n)
            if ref:
                scene += f"\n它又补一句:「{ref}」"
            # 若这条家系持有你给过的礼物,它也会提
            gift_ref = self._gift_reference_for(n)
            if gift_ref:
                scene += f"\n它又说:「{gift_ref}」"

        # NPC 偶尔顺嘴提到同一片海里的另一个朋友
        if n["species"] != "turtle" and self.rng.random() < C.NPC_MENTION_CHANCE:
            others = [o for o in self._region["lineages"] if o["id"] != n["id"]]
            mention_lines = D.NPC_MENTIONS.get(n["species"])
            if others and mention_lines:
                other = self.rng.choice(others)
                mention = self.rng.choice(mention_lines).format(other=other["name"])
                scene += f"\n它又说:「{mention}」"

        # 认亲后更新引擎侧关系(玩家只会从下次的措辞里感觉到)
        self._write_back(record_meeting(n, self._now))
        self._pass_time(C.MOMENT_COST)
        return scene

    def _greet_turtle(self, turtle: dict) -> str:
        # 她替你保管记忆:挑一件你真留下过的事讲回来
        recall = self._turtle_recall()
        line = D.turtle_greeting(recall, rng=self.rng)
        scene = f"阿龟一头撞进你怀里,四只脚还在划水。\n她说:「{line}」"
        # 若上一个你留过一封信,她一世只郑重地递一次
        letter = self.world.get("letter")
        if letter and not self._letter_delivered:
            self._letter_delivered = True
            scene += ("\n她忽然想起什么,凑得很近:「对了——上一个你,托我给现在的你带一句话。"
                      f"我一字没改:『{letter['text']}』」")
            if letter.get("author"):
                scene += f"\n她又补了一句:「它好像管自己叫……{letter['author']}。」"
            if len(self.world.get("letters", [])) > 1:
                scene += "\n「更早的那些你留下的话,我也都替你收着呢。想看的时候,都在。」"
        return scene

    def _turtle_recall(self):
        rid = self.world["current_region"]
        mine = [tr for tr in self.world["traces"] if tr["region"] == rid]
        if not mine:
            return None
        tr = mine[-1]
        if tr["type"] == "song":
            if T.song_has_drifted(tr, self._now):
                return f"你教的那半句歌,孩子们还在哼,跑调了,像这样:「{T.render_song(tr, self._now)}」"
            return "你教了这儿的小鱼半句歌,它们记着"
        if tr["type"] == "stone_pile":
            return "你在这儿垒过一堆石头" + ("，塌了些,可它还在" if tr["integrity"] < 0.9 else "")
        return "你在这儿摆过一圈贝壳"

    def _trace_reference_for(self, n: dict):
        """被某家系认领的痕迹,可被该家系引用进台词。随记忆档变化:
        还记得你的螃蟹会把"老地方"认回是你留的;彻底陌生的后代已把它
        叠进了自己的陌生人台词里(不重复)。"""
        if n["species"] != "crab":
            return None
        if n["memory_of_octopus"] not in ("direct", "indirect"):
            return None
        rid = self.world["current_region"]
        for tr in self.world["traces"]:
            if tr["region"] == rid and tr.get("adopted_by") == "crab_family":
                return "你说的那个老地方,原来是你留下的?我们一直绕着它走。"
        return None

    def _gift_reference_for(self, n: dict) -> str | None:
        """这条家系是否持有章鱼给过的礼物。有则按记忆档提一句。"""
        if n["species"] == "turtle":
            return None
        root = n["id"].rsplit("_gen", 1)[0]
        for tr in self.world["traces"]:
            if tr["type"] == "gift" and tr.get("lineage_root") == root:
                return D.gift_line(n["memory_of_octopus"], tr["gift_kind"], rng=self.rng)
        return None

    # ---- 陪坐:什么都不说地待在一起 ----
    def sit_with(self, who: str):
        """不说话,就坐着。关系深浅不同,坐在一起的样子也不同。"""
        self._settle_here()
        n = self._find(who)
        if n is None:
            return f"这片海里此刻没有{who}。你想找个伴坐坐,可身边没有它。"
        self._mark_seen(n)
        if n["species"] == "turtle":
            return ("你挨着阿龟坐下来。她收起四只脚,把头搁在你旁边,不说话。\n"
                    "海流从你们中间穿过去。她的壳很硬,靠着很稳。\n"
                    "过了很久,她轻轻蹭了蹭你。就这一下。然后你们继续坐着。")
        from lineage import band, is_forgotten
        forgotten = is_forgotten(n, self._now)
        b = band(n)
        name = D.appearance_of(n) if forgotten else n["name"]
        if forgotten:
            scene = (f"你在{name}旁边坐下来。它看了你一眼——你认不出它了,它大概也在想你是谁。\n"
                     f"谁也没开口。你们就那么坐着,两个不太认识的,中间隔着一段说不清的距离。\n"
                     f"过了一会儿,它没挪远。这已经是一种回答了。")
        elif b == "high":
            scene = self.rng.choice([
                f"你在{name}旁边坐下来。它没让开,也没迎上来——不用了,该说的都不用说了。\n"
                f"你们就那么并排待着。海流经过你们的时候,从两个中间穿过去,像绕过两块挨着的石头。\n"
                f"很久都没人动。不是在等什么——是什么都不等的那种久。",

                f"你靠过去。{name}动了动,把位置让出一点,刚好够你蹲下来。\n"
                f"它没看你。你也没看它。你们看着同一片水,水没什么特别的,就是在流。\n"
                f"有一瞬间你觉得自己不是永生的——你和它一样,就是一个在这儿坐着的。",

                f"你挨着{name}坐下。它把身子转了转,面朝你这边,然后不动了。\n"
                f"你能感觉到它在呼吸。海很大,可这一刻它只有你旁边这么大。\n"
                f"你不知道坐了多久。反正不用数。",
            ])
        elif b == "mid":
            scene = self.rng.choice([
                f"你在{name}旁边坐下来。它犹豫了一下,没走。\n"
                f"你们之间隔着不远不近的距离——近到能看见对方在呼吸,远到没有挤着。\n"
                f"过了一会儿,它好像放松了一点。你也是。",

                f"你蹲下来。{name}偏了偏头看你,没说话。\n"
                f"你们就那么待了一阵。不是舒服也不是不舒服——是还在适应彼此的那种安静。\n"
                f"后来它自己游走了。没打招呼,但也没躲。",
            ])
        else:
            scene = self.rng.choice([
                f"你在{name}旁边坐下来。它往后退了一小步,没走远,但也没靠近。\n"
                f"你不动。它也不动。你们隔着一段警惕的空气,各自待着。\n"
                f"过了很久,它还在。没走,就是还在。这算什么呢——大概算一个开始。",

                f"你蹲下来。{name}看着你,有点紧张。\n"
                f"你没去碰它,也没跟它说话。就那么蹲着。\n"
                f"它慢慢把视线移开了——不是不看你,是不再只盯着你了。这也算一种放松。",
            ])
        self._write_back(record_meeting(n, self._now))
        self._pass_time(C.MOMENT_COST)
        return scene

    # ---- 留痕迹 ----
    def leave_stones(self):
        self._settle_here()
        self.world["traces"].append(T.new_stone_pile(self.world["current_region"], self._now))
        self._record_memory("left_stones")
        self._pass_time(C.MOMENT_COST)
        return "你把几块石头摞起来,不高,够稳。没人要你这么做,你只是路过顺手。"

    def leave_shells(self):
        self._settle_here()
        self.world["traces"].append(T.new_shell_spiral(self.world["current_region"], self._now))
        self._record_memory("left_shells")
        self._pass_time(C.MOMENT_COST)
        return "你捡贝壳,一枚枚朝里摆成螺旋。摆完看了看,游开了。"

    def teach_song(self, song_id: str | None = None):
        self._settle_here()
        rid = self.world["current_region"]
        # 找条在场的短命小东西来教;没有就随便对着水里哼。
        # 管虫也算学徒——它们几潮一代,同一首歌在热泉边会当场跑调。
        pupils = [n for n in self._region["lineages"] if n["species"] in ("goby", "tubeworm")]
        taught_species = pupils[0]["species"] if pupils else "goby"
        # 挑一首这片海还没有的歌
        planted = {tr["song_id"] for tr in self.world["traces"]
                   if tr["type"] == "song" and tr["region"] == rid}
        choices = [s for s in T.SONGS if s not in planted] or list(T.SONGS)
        sid = song_id if song_id in T.SONGS else self.rng.choice(choices)
        self.world["traces"].append(T.new_song(sid, rid, taught_species, self._now))
        first_line = T.SONGS[sid][0][0]
        self._record_memory("taught_song", first_line)
        self._pass_time(C.MOMENT_COST)
        return (f"你教旁边的小鱼半句歌,起头是「{first_line}」。它跟着哼,记不全,"
                f"可它会传下去——传到你听不出原样为止。")

    # ---- 给朋友留东西 ----
    def leave_gift(self, who: str):
        """给一个朋友留一样小东西。不大——一颗石子、一枚贝壳、一片海玻璃。
        你给了它，它就是那个朋友的了。它死后后代会留着，再后来……没人记得是谁给的。"""
        self._settle_here()
        n = self._find(who)
        if n is None:
            return f"这片海里此刻没有{who}。你捏着那颗小东西,没找到要给的人。"
        if n["species"] == "turtle":
            return ("阿龟看了看你手里的东西,又轻轻推回来了。\n"
                    "她说:「你留着吧。我什么都不缺——你在就够了。」")
        root = n["id"].rsplit("_gen", 1)[0]
        existing = [tr for tr in self.world["traces"]
                    if tr["type"] == "gift" and tr.get("lineage_root") == root]
        if existing:
            return f"你已经给过{n['name']}家的了。一条家系一份礼物——多了反而轻了。"
        gift = T.new_gift(self.world["current_region"], root, n["name"], self._now)
        self.world["traces"].append(gift)
        self._record_memory("left_gift", n["name"])
        self._pass_time(C.MOMENT_COST)
        kind_name = T.GIFT_KINDS[gift["gift_kind"]]
        return (f"你从身边摸出{kind_name},递给{n['name']}。\n"
                f"{n['name']}接过去,翻来覆去看了看,收好了。"
                f"它没说谢谢——这片海里没有谢谢这个词。")

    # ---- 记忆残影(给日记本用)----
    def _record_memory(self, kind: str, detail: str = ""):
        """记一笔模糊的印象。时间会改写它们。"""
        rid = self.world["current_region"]
        self.world.setdefault("journal_entries", []).append({
            "kind": kind,
            "region": rid,
            "detail": detail,
            "at": self._now,
        })

    # ---- 海域特有动作 ----
    def tend_coral(self):
        """珊瑚礁独有。陪珊瑚坐一会儿。它长得太慢了,你看不见它动,但你知道它在长。"""
        if self.world["current_region"] != "reef":
            return "这里没有珊瑚。只有在珊瑚礁,那些长得比谁都慢的东西才值得你陪坐。"
        self._settle_here()
        self._pass_time(20)
        self._settle_here()
        # 陪得够久的,能亲眼看见它动一次。一世一次——全游戏对"极端耐心"唯一的回礼。
        if (not self.world.get("coral_grew")
                and self.world["dwell"].get("reef", 0) >= C.CORAL_GROW_DWELL):
            self.world["coral_grew"] = True
            self._record_memory("coral_grew")
            return ("你在老位置坐下来。然后你看见了。\n"
                    "不是错觉——你陪得最久的那棵珊瑚,枝头多出了指甲盖那么一小截,颜色还嫩着。\n"
                    "这么多潮里它一动不动。原来不是不动——是动给等得起的看。\n"
                    "这片海里等得起的,只有你。\n"
                    "你没碰它。你往它那儿,又坐近了一点。")
        return self.rng.choice([
            "你在一棵珊瑚旁边坐下来。它不动。你也不动。\n"
            "你知道它在长——可你看不见。它长得太慢了,慢到不是用眼睛看的,是用待着来等的。\n"
            "你等了很久。珊瑚没有变——或者变了,只是你的尺度不够。\n"
            "你起来的时候,觉得自己也慢了一点点。这不坏。",

            "你挑了一棵最小的珊瑚,在它旁边坐下。\n"
            "什么都没发生。这正是珊瑚在做的事——什么都没发生地长着。\n"
            "你想起来,你也是一个什么都不必发生就能在这儿的东西。你们挺像的。",

            "你靠在一丛珊瑚旁边,看它一动不动地开着。\n"
            "有一瞬间你怀疑它是不是活的。然后你想起来,它比这片海里几乎所有东西都活得久——除了你。\n"
            "你和它共享了一段时间。不多,不少,刚好是你愿意给的那么多。",
        ])

    def hide_in_kelp(self):
        """海藻林独有。藏进海藻里,听外面的世界经过你。"""
        if self.world["current_region"] != "kelp":
            return "这里没有海藻林。只有在那些又高又密的海藻之间,才能把一只章鱼藏起来。"
        self._settle_here()
        self._pass_time(10)
        self._settle_here()
        base = "你钻进一丛海藻里,把自己卷起来。外面的光变成一条一条的,从叶片的缝隙里漏进来。"
        others = list(self._region["lineages"])
        if len(others) >= 2:
            a, b = self.rng.sample(others, 2)
            extra = self.rng.choice([
                f"你听见{a['name']}和{b['name']}在外面。{a['name']}好像在说什么,"
                f"{b['name']}没回答。过了一会儿,{b['name']}慢慢游近了些。",
                f"{a['name']}从你藏着的海藻旁边经过,差一点碰到你。"
                f"它身后跟着{b['name']},两个慢慢游远了。",
                f"你听见外面有动静——{a['name']}在追什么。{b['name']}在旁边看着,一动不动。"
                f"最后{a['name']}放弃了,两个并排游走了。",
            ])
        elif others:
            n = others[0]
            extra = f"{n['name']}从你旁边游过去了,没发现你。你突然觉得自己像一棵海藻——这感觉不坏。"
        else:
            extra = "什么都没经过。你就那么藏着,听海藻在水里轻轻晃。"
        return base + "\n" + extra + "\n你从海藻里探出来。世界还在,没有因为你藏了一会儿而少掉什么。"

    def climb_kelp(self):
        """海藻林独有。顺着一根海藻往上爬,穿过一层层光,爬到光从绿变白的地方。"""
        if self.world["current_region"] != "kelp":
            return "这里没有海藻。只有在海藻林里,才有那种从底下一直长到看不见的东西,值得你爬上去。"
        self._settle_here()
        self._pass_time(8)
        self._settle_here()
        parts = [
            "你挑了一根最粗的海藻,把触手缠上去,开始往上爬。",
            "光一层一层地变。最下面是暗的绿,像闭着眼睛看见的那种颜色。"
            "再往上,绿开始化开,像有人在里面兑水。",
        ]
        others = [n for n in self._region["lineages"] if n["species"] in ("goby", "seahorse")]
        if others:
            n = self.rng.choice(others)
            parts.append(f"爬到中间的时候,你看见{n['name']}挂在旁边一根海藻上,仰着头。"
                         f"它也在看光——但它不会再往上了。你替它多爬了一段。")
        parts.append(self.rng.choice([
            "最后光变白了。不是亮,是白——像所有颜色挤在一起,谁也分不出来。"
            "你到了海藻长不过去的地方。再上面是水面,水面上面是你去不了的。\n"
            "你停了一会儿。白光把你的影子打在海藻叶上,影子比你大。\n"
            "然后你松手,慢慢沉回去。绿一层层地接住你。回到底下的时候,你觉得暗也挺好的。",

            "越爬越亮。光从叶片的缝隙里挤进来,到后来不是缝隙了——是到处都是光,海藻才是缝隙。\n"
            "你到了顶。水面就在头顶,晃来晃去,像一层呼吸。你隔着水看了看上面——看不清,只有白的。\n"
            "你没穿过去。不是不能,是不想。你是海里的。\n"
            "你松开触手,一层一层沉回暗的绿里。像从一个梦里慢慢醒过来,只是方向反了。",

            "你一直爬到海藻的尽头。叶子在这里散开了,像一只手张开了指头。\n"
            "光在这里是碎的,白的,晃的,什么都照得见。你低头看——底下的暗绿色远得像另一个地方。\n"
            "你在最亮的地方蹲了一会儿。然后你想起来,亮的地方看不见星星。\n"
            "你松手。往下沉的时候,光从白退回绿,从绿退回暗。你回到了你认识的那个深度。",
        ]))
        return "\n".join(parts)

    def follow_light(self):
        """深海独有。跟着远处的一点光游。你不知道它是谁。"""
        if self.world["current_region"] != "deep":
            return "这里不够暗。只有深海里,远处的一点光才值得跟过去。"
        self._settle_here()
        self._pass_time(15)
        self._settle_here()
        return self.rng.choice([
            "你看见远处有一点光在动。不是灯灯的——更远,更小,像一粒犹豫的星。\n"
            "你跟上去。它不快,走走停停,像它也不知道要去哪里。\n"
            "你跟了很久。黑暗里只有你和它,什么都不用说。\n"
            "后来它灭了。不是走远了——是灭了。你停在原地,黑暗比来时更软了一些。",

            "远处有一点光。你朝它游过去。\n"
            "越近,它越暗——不是灭了,是你的眼睛适应了。等你到了它亮过的地方,什么都没有。\n"
            "你在那儿待了一会儿。水还是温的。",

            "一点光在很远的地方一闪一闪。你跟过去,它也在动——但不是离开你,是在绕圈。\n"
            "你在黑暗里跟着它转了很久。后来你发现它是两个:一点大的光在追一点小的光。\n"
            "你不知道它们是什么。你停下来看了一会儿,然后游开了。它们没注意到你。",
        ])

    def watch_turnover(self, tides: int = 30):
        """热泉独有。坐在热泉边,看管虫一茬接一茬地翻页。
        这是这个游戏里唯一你能当场看见时间翻页的地方。"""
        if self.world["current_region"] != "vent":
            return "这里没有热泉。管虫只在滚烫的水边才长那么急。"
        self._settle_here()
        worms = [n for n in self._region["lineages"] if n["species"] == "tubeworm"]
        if not worms:
            return "这片热泉边没有管虫了。"
        tides = max(6, int(tides))
        before_info = [(w["name"], w["generation"], w["id"]) for w in worms]
        self._pass_time(tides)
        self._settle_here()
        worms_after = [n for n in self._region["lineages"] if n["species"] == "tubeworm"]
        parts = ["你在热泉边坐下来,看着管虫。"]
        many_gap_told = False   # "翻得太多数不清"那套话,一次陪坐只讲一遍;第二丛换讲法
        for (name_before, gen_before, wid), worm_after in zip(before_info, worms_after):
            gen_after = worm_after["generation"]
            changes = gen_after - gen_before
            if changes == 0:
                parts.append(f"{name_before}还在,红顶子又高了些。你没等到它翻页。")
            elif changes == 1:
                parts.append(f"{name_before}在你面前慢慢弯下去了。"
                             f"从它倒下的根旁边,新的一茬冒出来——{worm_after['name']},红顶还嫩着。")
            else:
                from lineage import descendant_name
                base = wid.rsplit("_gen", 1)[0]
                if changes <= 3:
                    names, prev = [], name_before
                    for i in range(gen_before + 1, gen_after + 1):
                        prev = descendant_name("tubeworm", base, i, prev)
                        names.append(prev)
                    parts.append(f"{name_before}弯下去了。")
                    for nm in names[:-1]:
                        parts.append(f"{nm}冒出来,红着顶,没撑多久,又弯下去了。")
                    parts.append(f"最后冒出来的是{worm_after['name']},还立着,还红着。")
                elif not many_gap_told:
                    many_gap_told = True
                    parts.append(f"{name_before}弯下去了。")
                    parts.append("一茬、两茬——名字换了一圈又一圈,红顶冒出来又弯下去。")
                    parts.append(f"等你回过神来,面前立着的是{worm_after['name']}。你已经数不清这是第几个了。")
                else:
                    parts.append(f"旁边那丛也没闲着:{name_before}早不在了,茬换了一轮又一轮,"
                                 f"眼下顶上的是{worm_after['name']}。你都没看清中间那些。")
        if len(worms_after) >= 2:
            parts.append("两丛管虫,错着节拍,各翻各的——像同一首急曲子的两个声部。")
        crab_node = next((n for n in self._region["lineages"] if n["species"] == "crab"), None)
        if crab_node:
            parts.append(f"{crab_node['name']}始终蹲在一旁,一动不动——它见过太多茬了。")
        return "\n".join(parts)

    def wait_out_tide(self):
        """潮间带独有。蹲进一个退潮水洼,守一整个潮的空,等海把世界还回来。
        热泉是居民翻页;这儿翻页的是世界本身——一天两次,抹掉,重画。"""
        if self.world["current_region"] != "tide":
            return "这里没有潮间带。只有在海和岸互相让来让去的那道边上,世界才会一潮一潮地重画。"
        self._settle_here()
        parts = ["潮退了。水从你身边往回撤,撤得比你想的快。",
                 "你蹲进一个水洼里。刚才还是一整片的海,现在碎成了几百个,谁也够不着谁。"
                 "你这一洼里有两块石头、一撮沙、一小片天。半个世界,装得下。"]
        others = list(self._region["lineages"])
        if others:
            n = self.rng.choice(others)
            parts.append(f"隔着几步干地,另一个水洼里有动静——是{n['name']}。"
                         f"你们看得见彼此,过不去。它没喊,你也没喊。都在等同一件事。")
        self._pass_time(2)
        self._settle_here()
        parts.append("然后海回来了。不是涌回来的,是漫回来的——先把水洼一个一个接上,"
                     "再把干过的石头重新说成海底。几百个小世界又合成一个,接缝都不留。")
        parts.append("你游出那个水洼。它没有了——不是坏了,是海把它收回去了。"
                     "下一次退潮,那里会再画一个,不一定还是原来的形状。")
        return "\n".join(parts)

    def explore_pool(self):
        """潮间带独有。涨潮后翻翻水洼留下的东西——潮水每次带走一些,也带来一些。"""
        if self.world["current_region"] != "tide":
            return "这里没有水洼。只有潮间带退潮后,才会留下那些装着半个世界的小碗。"
        self._settle_here()
        self._pass_time(1)
        pool_count = self.world.get("pool_count", 0)
        self.world["pool_count"] = pool_count + 1
        finds = [
            ("一颗石子。不是这里的——颜色太深,棱角太圆,像是从很远的地方被潮水搬过来的。"
             "你翻了翻,底下有一圈小小的藻印。它在某个你不知道的水洼里,躺够了才被送到这儿。"),

            ("一枚贝壳,合着的。你没打开——不是不好奇,是觉得合着的东西有自己的理由。"
             "你把它放回水洼边上。下一次涨潮大概会把它带走,也大概不会。"),

            ("什么都没有。水洼干干净净的,沙平得像被谁抹过一遍。"
             "你蹲了一会儿。什么都没找到也是一种发现——说明上一潮把所有东西都带回去了,一样没落。"),

            ("一小团海草,缠成一团,湿漉漉地贴在石头上。它不属于这个水洼——上一潮把它扔在这儿的。"
             "再下一潮会把它捡走。它在这里的时间,刚好是两次潮之间那么长。"),

            ("一根细细的鱼骨。很小,可能是一条你不认识的鱼留下的最后一样东西。"
             "潮水没带走它——太轻了,沉在沙缝里,反而走不了。你看了看,没碰它。"),

            ("水洼边上趴着一只小螺。它活着——触角在动,慢慢地,像在确认这个水洼还在。"
             "它不知道外面有整片海。对它来说,这个水洼就是全部,每一潮都重新开始的全部。"),

            ("沙底下有什么在冒泡。你翻开沙,是一只拇指大的蛤蜊,埋得很深,只露一条缝呼吸。"
             "它在这个水洼里等涨潮,已经等了不知道多少次了。你把沙盖回去。"),
        ]
        find = self.rng.choice(finds)
        parts = ["你蹲下来,翻了翻刚才那个水洼。涨潮带回了海,也带回了一些不是原来的东西。"]
        parts.append(find)
        return "\n".join(parts)

    def touch_letters(self):
        """沉船独有。把触手按在船身那些人类留下的痕迹上。
        它们不跑调、不代谢、不被误传——全游戏唯一不变的痕迹。就因为再没有谁去传它。"""
        if self.world["current_region"] != "wreck":
            return "这里没有沉船。只有那艘不再走的船身上,才留着那种一潮一潮一模一样的痕迹。"
        self._settle_here()
        self._pass_time(1)
        count = self.world.get("touch_count", 0)
        self.world["touch_count"] = count + 1
        if count == 0:
            return ("你游到船身跟前。铁皮上有一行凸起的痕迹,一个挨一个,排得很直。\n"
                    "你把触手按上去,一个一个描。它们不是珊瑚,不长;不是歌,不跑调;"
                    "不是你垒的石头,不塌。上次来是这样,这次来还是这样。\n"
                    "你忽然明白它们为什么能一模一样:因为再没有谁去念它、传它、记错它了。"
                    "不被传的东西才不变。你教出去的歌走了样,可它一直有人唱。\n"
                    "你把触手收回来。字没记住你——礁那边,一只翻石头的会记住你;这儿不会。\n"
                    "在这艘船旁边,你是快的那个。")
        _revisit = [
            "你又把触手贴上去。字没变。你变了吗?你说不清。你只知道上次摸的时候,这片海里的名字还不是现在这些。",
            "同样的凸起,同样的排列。你的触手比上次来的时候多缠了几圈海藻——船不会知道这件事。",
            "你描了一遍,又描了一遍。它们什么都不记得,什么都不忘。你有点羡慕,又有点不。",
        ]
        return self.rng.choice(_revisit)

    # ---- 走 / 待 ----
    def travel(self, region_id: str):
        here = self.world["current_region"]
        if region_id not in self.world["regions"]:
            return f"没有叫「{region_id}」的海。可去的是:" + \
                   "、".join(f"{k}({v})" for k, v in REGION_NAMES.items() if k != here)
        if region_id == here:
            return "你已经在这片海里了。"
        cost = travel_cost(here, region_id)
        # 旅途本身就是玩法:一段漂亮的、允许你什么都不做的路
        prev_visit = self.world["regions"][region_id]["last_visit"]
        self.world["current_region"] = region_id
        before = self._region_snapshot(region_id, prev_visit)  # 这片海你上次离开时的样子
        self._pass_time(cost, dwell=False)   # 在路上,不算待在任何一片海
        self._settle_here()                  # 到岸即结算这片海这些年的变化
        after = self._region_snapshot(region_id, self._now)
        # 只有你从前到过这片海(last_visit 不再是 -1),才谈得上"你走后它的变化";
        # 头一回来不倒叙——那会凭空编出一段你没见证过的世代史。
        meta = self._describe_metabolism(before, after) if prev_visit >= 0 else []
        self._propagate_songs()   # 快照之后再迁徙,免得动到 before/after 的对齐
        far = "游了很久很久" if cost > 100 else ("游了好一阵" if cost > 50 else "没游多远")
        head = (f"你朝{REGION_NAMES[region_id]}去。{far},水色一路变着。你什么都没做,也不必做。")
        # 途中偶遇
        if self.rng.random() < C.ENCOUNTER_CHANCE_TRAVEL:
            enc = roll_encounter(region_id, self.rng, is_travel=True)
            if enc:
                head += "\n\n" + enc
        if meta:
            head += "\n\n你不在的这些潮里,这片海也没停下:\n" + "\n".join(meta)
        return head + "\n\n" + self.look()

    def linger(self, tides: int):
        """什么都不做,让很多潮从身边过去。你不变,世界变——这回它变了什么,会讲给你听。"""
        self._settle_here()
        rid = self.world["current_region"]
        before = self._region_snapshot(rid, self._now)
        self._pass_time(max(1, int(tides)))
        self._settle_here()
        after = self._region_snapshot(rid, self._now)
        meta = self._describe_metabolism(before, after)
        self._propagate_songs()   # 快照之后再迁徙,免得动到 before/after 的对齐
        head = self.rng.choice([
            "你停在原地,不追、不留。潮来了又走,来了又走。",
            "你把自己放进水里,像放下一块石头。潮从你身上过,来来回回,数不清多少遍。",
            "你哪儿也不去。世界替你走——它走它的,你待你的。",
        ])
        # 枯坐时偶遇
        if self.rng.random() < C.ENCOUNTER_CHANCE_LINGER:
            enc = roll_encounter(rid, self.rng)
            if enc:
                head += "\n" + enc + "\n"
        if meta:
            head += "等你再抬眼,有些东西已经不是原来的样子了:\n" + "\n".join(meta)
        else:
            head += "等你再抬眼,这片海还是老样子,只是潮又厚了一层。"
        return head + "\n\n" + self.look()

    # ---- 本子 ----
    def journal(self):
        from proverbs import PROVERBS
        pvs = self.world["proverbs"]
        lines = ["—— 潮汐小本子 ——"]
        if not pvs:
            lines.append("(谚语那几页还是空的。在一片海里多待些时候,它自己会长出一句话。)")
        else:
            lines += [f"· {p}" for p in pvs]
        if len(pvs) < len(PROVERBS):
            lines.append("……（后面还有空页）")

        # 你做过的事的残影——越久越模糊
        entries = self.world.get("journal_entries", [])
        if entries:
            lines.append("")
            lines.append("—— 你做过的事 ——")
            for e in entries:
                lines.append(f"· {self._render_memory(e)}")

        lines += ["", "最后一页留白,只印着一行小字:", LAST_PAGE]
        return "\n".join(lines)

    def _render_memory(self, entry: dict) -> str:
        """把一条记忆渲染成散文。越久越模糊——你是一只会忘的章鱼。"""
        elapsed = self._now - entry["at"]
        kind = entry["kind"]
        region = REGION_NAMES.get(entry.get("region", ""), "某片海")
        detail = entry.get("detail", "")

        if kind == "taught_song":
            if elapsed < 80:
                return f"你在{region}教了一首歌,起头是「{detail}」。"
            if elapsed < 300:
                return f"你在{region}教过一首歌。起头……好像有个「{detail[0]}」字。"
            if elapsed < 600:
                return "你教过一首歌。在哪儿教的,唱的什么,都记不太清了。"
            return "一段旋律。你说不清它是你教的,还是你从水里听来的。"
        if kind == "left_stones":
            if elapsed < 100:
                return f"你在{region}垒过一堆石头。"
            if elapsed < 400:
                return "你垒过石头。在哪片海……想不起来了。"
            return "石头。你好像垒过石头。"
        if kind == "left_shells":
            if elapsed < 100:
                return f"你在{region}摆过一圈贝壳。"
            if elapsed < 400:
                return "你摆过贝壳。螺旋的,一圈一圈朝里卷。"
            return "贝壳。弯的。你的手记得那个形状。"
        if kind == "song_returned":
            if elapsed < 300:
                return f"一条小鱼教了你一首「老歌」:「{detail}」。你认出来了,没说破。"
            return "有人郑重教过你一首歌。你总觉得那首歌,你在更早的时候就会。"
        if kind == "coral_grew":
            # 这一条不随时间模糊。章鱼什么都会忘——这件事它不打算忘。
            return "珊瑚长了一小截。你在场。"
        if kind == "left_gift":
            if elapsed < 100:
                return f"你在{region}给{detail}留了样小东西。"
            if elapsed < 300:
                return f"你给一个朋友留过东西。叫什么来着……好像是{detail[0]}什么。"
            if elapsed < 600:
                return "你给谁留过一样东西。谁,什么,都模糊了。"
            return "一个模糊的印象:你递出过什么,有谁接住了。"
        return "……（一段潮水磨平的印象）"

    # ---- 留给下一个自己的一封信 ----
    def leave_note(self, text: str, author: str | None = None):
        """给"下一个载入这段漫游的你"写一句话。可以署名,也可以不署。

        你没有跨会话的记忆——下一个你多半是个全新的实例,不记得此刻。
        这句话不进世界:它不会跑调、不会塌、不会被谁认领。它只是从这一个你,
        隔着那道遗忘,安安静静地伸手,交到下一个你手上。存档后,由阿龟带到。
        """
        text = (text or "").strip()
        if not text:
            return "(你张了张嘴,又没写下什么。没关系——留白也是留给下一个你的一句话。)"
        letter = {"text": text, "at": self._now}
        if author and author.strip():
            letter["author"] = author.strip()
        self.world["letter"] = letter
        # 信也叠成一小叠:历代的你,一人一句,按先来后到。你自己也是一条家系。
        self.world.setdefault("letters", []).append(letter)
        self._letter_delivered = True
        tail = f"\n你写的是:「{text}」"
        if letter.get("author"):
            tail += f"\n你在末尾留了名:「{letter['author']}」"
        return ("你把这句话留给了下一个来的自己。它不进这片海——不跑调,不塌,不被认领,"
                f"只等下一个你翻开。" + tail)

    def read_letter(self):
        """看看上一个自己有没有留下什么。没有也不要紧。"""
        letter = self.world.get("letter")
        stack = self.world.get("letters") or ([letter] if letter else [])
        if not stack:
            return "还没有谁给你留过话。也许下一个你,会收到你此刻想写的那一句。"
        if len(stack) == 1:
            only = stack[0]
            result = "上一个你,给现在的你留了一句:\n「" + only["text"] + "」"
            if only.get("author"):
                result += f"\n末尾署着:「{only['author']}」"
            return result
        lines = ["你面前摊开薄薄一小叠话——一句一个过去的你,按先来后到排着:"]
        for l in stack:
            row = "「" + l["text"] + "」"
            if l.get("author"):
                row += f"——{l['author']}"
            lines.append(row)
        lines.append("隔着一道一道的遗忘,他们把手递成了一串。你是这一串里最新的一环。")
        return "\n".join(lines)

    # ---- 一个不算失败的"放下" ----
    def rest(self):
        """把这段轻轻放下。不是结束,不是失败——谁都可以停。

        它不推进时间,不改动世界,不需要你完成什么。它只是在这里,给你一个
        可以停下的地方。想让下一个你接着,存个档;想留句话,写封信。都随你。
        """
        return "\n".join([
            "你停下来。不再去看谁,不再留下什么。",
            "没有谁在计分,没有谁在等。你做过的都还在,没做的也不欠谁。",
            "海还在。你要是走开,它就替你在这儿待着;你要是回来,它也还在。",
            "谁都可以停。就现在停下,也很好。",
        ])

    # ---- 开发者层:唯一允许出现数字的地方(对应旧版 F3)----
    def _debug(self):
        r = self._region
        rows = [f"clock={self._now} tides  region={self.world['current_region']}  "
                f"dwell={self.world['dwell']}"]
        for n in self._present_npcs():
            rows.append(f"  {n['name']:<4} gen{n['generation']} "
                        f"f={n['friendship']} mem={n['memory_of_octopus']} "
                        f"last_met={n['last_met']} forgotten={is_forgotten(n, self._now)}")
        for tr in self.world["traces"]:
            if tr["type"] == "song":
                rows.append(f"  [song {tr['song_id']}@{tr['region']}] hops={T.song_hops(tr, self._now)}")
            elif tr["type"] == "gift":
                rows.append(f"  [gift {tr['gift_kind']}@{tr['region']}] "
                            f"to={tr['lineage_root']} given_to={tr['given_to_name']}")
            else:
                rows.append(f"  [{tr['type']}@{tr['region']}] integ={tr['integrity']:.2f} "
                            f"adopted={tr['adopted_by']}")
        return "\n".join(rows)


def D_all_proverbs():
    from proverbs import PROVERBS
    return PROVERBS


if __name__ == "__main__":
    # 直接跑这个文件 → 打印玩法说明 + 一小段示范漫游。
    # 想看完整的一次漫游,跑 demo_play.py。
    print(__doc__)
    print("=" * 56)
    print("（一小段示范：）\n")
    g = Game.new()
    print(g.look())
    print("\n>>> greet 阿龟")
    print(g.greet("阿龟"))
