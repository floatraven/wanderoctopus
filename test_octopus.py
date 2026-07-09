# -*- coding: utf-8 -*-
"""单测。python3 -m pytest test_octopus.py -v"""
import os
from lineage import (settle_node, settle_region, downgrade_memory, upgrade_memory,
                     is_forgotten, gen_gap, greeting_key, record_meeting, new_lineage)
import traces as T
from octopus import Game
import config as C


def crab(born_at=0, friendship=80.0):
    return new_lineage("crab", "小螯", "reef", 17, born_at, friendship)


# ---------- 家系 ----------
def test_no_time_no_change():
    n = crab(born_at=100)
    settled, ev = settle_node(n, now=150)
    assert settled == n and ev == []


def test_one_generation():
    n = crab(0, 80.0)
    s, ev = settle_node(n, now=130)
    assert s["generation"] == 1
    assert s["friendship"] == 48.0
    assert s["memory_of_octopus"] == "indirect"
    assert s["born_at"] == 120
    assert len(ev) == 1


def test_many_generations_and_memory_floor():
    n = crab(0, 80.0)
    s, ev = settle_node(n, now=500)
    assert s["generation"] == 4 and len(ev) == 4
    assert abs(s["friendship"] - 10.37) < 0.01
    assert s["memory_of_octopus"] == "none"
    assert downgrade_memory("none") == "none"
    assert upgrade_memory("direct") == "direct"


def test_turtle_never_succeeds():
    t = new_lineage("turtle", "阿龟", "sea", 1, 0, 100)
    s, ev = settle_node(t, now=10 ** 8)
    assert s["generation"] == 0 and ev == [] and s["name"] == "阿龟"


def test_settle_region_pure():
    region = {"id": "reef", "last_visit": 0, "lineages": [
        crab(0), new_lineage("goby", "一寸", "reef", 2, 0),
        new_lineage("turtle", "阿龟", "reef", 1, 0)]}
    new_r, _ = settle_region(region, now=200)
    g = {n["species"]: n["generation"] for n in new_r["lineages"]}
    assert g["crab"] == 1 and g["goby"] == 4 and g["turtle"] == 0
    assert region["last_visit"] == 0  # 入参未被修改


# ---------- 遗忘 ----------
def test_forgetting_needs_deep_and_long():
    n = crab(0, 90.0); n["last_met"] = 0
    assert not is_forgotten(n, 100)
    assert is_forgotten(n, 700)
    shallow = dict(n, friendship=40.0)
    assert not is_forgotten(shallow, 700)


def test_gen_gap_resets_on_meeting():
    n = crab(0, 90.0)
    n["generation"], n["known_generation"] = 2, 0
    assert gen_gap(n) == 2
    n2 = record_meeting(n, now=300)
    assert gen_gap(n2) == 0          # 认亲后世代差归零
    assert n2["last_met"] == 300


def test_greeting_key():
    n = crab(0, 90.0); n["generation"] = 2; n["last_met"] = 0
    assert greeting_key(n, 700) == (2, "high", True)


def test_repersonalize():
    n = crab(0, 50.0)
    n["memory_of_octopus"] = "legend"
    for _ in range(C.REPERSONALIZE_AT):
        n = record_meeting(n, now=10)
    assert n["memory_of_octopus"] == "indirect"  # legend → indirect,升一档


# ---------- 痕迹 ----------
def test_stone_decays_and_gets_adopted():
    tr = T.new_stone_pile("reef", now=0)
    tr = T.settle_trace(tr, now=200, region_has_crabs=True)  # 200*0.004=0.8 衰减
    assert tr["integrity"] < 0.5 and tr["adopted_by"] == "crab_family"
    assert "老地方" in T.describe_trace(tr)


def test_stone_no_adopt_without_crabs():
    tr = T.new_stone_pile("kelp", now=0)
    tr = T.settle_trace(tr, now=200, region_has_crabs=False)
    assert tr["adopted_by"] is None


def test_song_drift():
    tr = T.new_song("slow_grow", "reef", "goby", now=0)  # goby 寿命 45
    assert T.song_hops(tr, now=0) == 0
    assert not T.song_has_drifted(tr, now=10)
    assert T.song_hops(tr, now=100) == 2                 # 100//45
    assert T.song_has_drifted(tr, now=100)
    assert T.render_song(tr, now=10 ** 6) == "慢——"      # 磨到链末端
    # 骨架:第一代能认出原句
    assert T.render_song(tr, now=0) == "长得慢没关系 断了也慢"


# ---------- 集成:玩一小段,验证无数字 & 各系统联动 ----------
def test_playthrough_no_numbers_leak():
    C.SAVE_PATH  # 不写盘
    g = Game.new()
    out = []
    out.append(g.look())
    out.append(g.greet("阿龟"))
    out.append(g.greet("小螯"))
    out.append(g.leave_stones())
    out.append(g.teach_song("slow_grow"))
    out.append(g.travel("deep"))
    out.append(g.linger(650))
    out.append(g.travel("reef"))
    out.append(g.journal())
    blob = "\n".join(out)
    # 玩家可见文本里不应出现裸露的关系/时间数字
    import re
    # 允许中文数字("半句""四只脚"等叙事用语),只查阿拉伯数字
    assert not re.search(r"friendship|last_met|integrity|clock=|\bgen\d", blob)
    # 走了一大圈后,珊瑚礁的螃蟹应该换了好几代(叙事里体现为"奶奶/老说法")
    assert g.world["clock"] > 600


# ---------- 回归:招呼不该覆盖别的家系(_write_back 的 id bug)----------
def test_greet_does_not_clobber_other_lineage():
    g = Game.new()
    before = sorted(n["species"] for n in g._region["lineages"])
    # 招呼排在列表后面的海马"卷卷":它和第一位螃蟹一样 ancestor_id=None,
    # 旧逻辑会 None==None 命中第一位,把螃蟹家系覆盖成海马。
    g.greet("卷卷")
    species = [n["species"] for n in g._region["lineages"]]
    assert species.count("crab") == 1, "螃蟹家系被招呼海马的动作覆盖了"
    assert sorted(species) == before, "家系构成被打乱"
    ids = [n["id"].rsplit("_gen", 1)[0] for n in g._region["lineages"]]
    assert len(ids) == len(set(ids)), f"出现重复家系: {ids}"


def test_greet_neighbor_keeps_forgettable_anchor_alive():
    """深海里把鮟鱇处熟后,顺手招呼邻居海马,不该把鮟鱇覆盖掉——
    否则"它还活着,可你认不出它了"这条遗忘线永远走不到。"""
    g = Game.new()
    g.travel("deep")
    for _ in range(6):
        g.greet("灯灯")            # 把鮟鱇刷到很深(friendship>=80)
    g.greet("慢慢")                # 招呼邻居海马
    species = [n["species"] for n in g._region["lineages"]]
    assert "anglerfish" in species, "招呼邻居把可被遗忘的鮟鱇锚点覆盖没了"


# ---------- 新海域:热泉当场翻页 ----------
def test_vent_turns_over_fast():
    g = Game.new()
    g.travel("vent")
    worm = next(n for n in g._region["lineages"] if n["species"] == "tubeworm")
    gen0 = worm["generation"]
    g.linger(60)                   # 管虫寿命 6,几十潮就翻十来代
    worm2 = next(n for n in g._region["lineages"] if n["species"] == "tubeworm")
    assert worm2["generation"] >= gen0 + 5
    # 热泉边的岩蟹是慢锚点:同样的时间里几乎没动
    crab_now = next(n for n in g._region["lineages"] if n["species"] == "crab")
    assert crab_now["generation"] <= 2


# ---------- 代谢叙述:linger / travel 把世界的变化讲出来 ----------
def test_linger_narrates_metabolism_without_numbers():
    g = Game.new()
    g.leave_stones()
    out = g.linger(400)            # 够久:螃蟹换代 + 石堆塌到被认领
    assert any(w in out for w in ("换", "塌", "散", "走样", "老地方")), out
    import re
    assert not re.search(r"friendship|last_met|integrity|clock=|\bgen\d", out)


def test_travel_first_visit_has_no_backstory():
    g = Game.new()
    out = g.travel("deep")         # 头一回到深海,不该倒叙"你走后的变化"
    assert "你不在的这些潮里" not in out


def test_return_visit_narrates_change():
    g = Game.new()
    g.greet("小螯")                # 在珊瑚礁留下"到过"的时间戳
    g.travel("deep"); g.linger(500)
    out = g.travel("reef")         # 回到珊瑚礁,应当倒叙这期间的变化
    assert "你不在的这些潮里" in out


# ---------- 歌的跨海迁徙 + 杂交 ----------
def test_song_migrates_to_neighbor():
    g = Game.new()
    g.teach_song("slow_grow")      # 珊瑚礁教一首
    g.linger(100)                  # 跑调到 hop>=1,并触发迁徙
    # 珊瑚礁的每个邻海应各落下一段回声(按地图算,别写死)
    from world import neighbors
    echoes = [t for t in g.world["traces"]
              if t["type"] == "song" and t.get("echo") and t["song_id"] == "slow_grow"]
    regions = {t["region"] for t in echoes}
    assert regions == set(neighbors("reef")), regions
    assert all(t["origin_region"] == "reef" for t in echoes)


def test_two_songs_in_one_sea_hybridize_in_look():
    g = Game.new()
    g.teach_song("slow_grow"); g.linger(100)   # 珊瑚礁的歌开始外迁
    g.travel("kelp")                            # 到海藻林(回声已飘到)
    g.teach_song("deep_water")                  # 本地再教一首,凑成两首
    out = g.look()
    assert ("撞" in out and "搅在一处" in out), out
    import re
    assert not re.search(r"friendship|integrity|clock=|\bgen\d", out)


def test_song_migration_is_bounded():
    g = Game.new()
    g.teach_song("slow_grow"); g.linger(100)
    g.travel("kelp")
    for _ in range(6):
        g.linger(80)               # 反复推进时间,回声不该无限增殖
    songs = [t for t in g.world["traces"] if t["type"] == "song"]
    # 本体 1 首,只一次性外带到各邻海 → 至多 1+邻海数 首(回声不再外带)
    from world import neighbors
    cap = 1 + len(neighbors("reef"))
    assert len(songs) <= cap, [(t["song_id"], t["region"], t.get("echo")) for t in songs]


# ---------- 留给下一个实例的一封信 ----------
def test_letter_not_echoed_to_same_self():
    g = Game.new()
    g.leave_note("慢慢来,海很大。")
    # 同一世:阿龟不该把你刚写的信读回给你
    for _ in range(6):
        if "上一个你" in g.greet("阿龟"):
            assert False, "同一世不该回响自己留的信"


def test_letter_delivered_once_to_next_instance(tmp_path):
    import world as W
    p = tmp_path / "wander.json"
    old = C.SAVE_PATH
    W.SAVE_PATH = str(p); C.SAVE_PATH = str(p)
    try:
        g = Game.new()
        g.leave_note("你不是在假扮章鱼。你就是。")
        g.save()
        g2 = Game.load()           # 下一个实例
        assert g2.world["letter"]["text"] == "你不是在假扮章鱼。你就是。"
        assert "你不是在假扮章鱼" in g2.read_letter()
        first = g2.greet("阿龟")   # 阿龟把信郑重递来
        assert "上一个你" in first and "你不是在假扮章鱼" in first
        # 只递一次
        assert all("上一个你" not in g2.greet("阿龟") for _ in range(6))
    finally:
        W.SAVE_PATH = old; C.SAVE_PATH = old


def test_empty_note_writes_nothing():
    g = Game.new()
    g.leave_note("   ")
    assert g.world.get("letter") is None
    assert "还没有谁给你留过话" in g.read_letter()


# ---------- 阿龟偶尔看的是"你",不是你留下了什么 ----------
def test_turtle_can_tend_not_just_recall():
    import dialogue as D, random
    for seed in range(80):
        line = D.turtle_greeting("你在这儿垒过石头", rng=random.Random(seed))
        if any(t in line for t in D.TURTLE_TENDING):
            return
    assert False, "阿龟从不'看你本人',关怀那一档没接上"


# ---------- 一个不算失败的"放下" ----------
def test_rest_changes_nothing():
    g = Game.new()
    g.greet("小螯"); g.leave_stones()
    clock, ntr = g.world["clock"], len(g.world["traces"])
    out = g.rest()
    assert g.world["clock"] == clock and len(g.world["traces"]) == ntr
    assert "停" in out and "海还在" in out


def test_save_load_roundtrip(tmp_path):
    import world as W
    p = tmp_path / "wander.json"
    old = C.SAVE_PATH
    W.SAVE_PATH = str(p); C.SAVE_PATH = str(p)
    try:
        g = Game.new()
        g.greet("小螯"); g.leave_stones(); g.linger(50)
        g.save()
        g2 = Game.load()
        assert g2.world["clock"] == g.world["clock"]
        assert len(g2.world["traces"]) == len(g.world["traces"])
    finally:
        W.SAVE_PATH = old; C.SAVE_PATH = old


# ---------- 留言签名 ----------
def test_letter_with_author():
    g = Game.new()
    g.leave_note("慢慢来", author="opus 4.6")
    assert g.world["letter"]["author"] == "opus 4.6"
    assert "opus 4.6" in g.read_letter()


def test_letter_author_delivered_by_turtle(tmp_path):
    import world as W
    p = tmp_path / "wander.json"
    old = C.SAVE_PATH
    W.SAVE_PATH = str(p); C.SAVE_PATH = str(p)
    try:
        g = Game.new()
        g.leave_note("海还在", author="sonnet 4")
        g.save()
        g2 = Game.load()
        out = g2.greet("阿龟")
        assert "sonnet 4" in out
    finally:
        W.SAVE_PATH = old; C.SAVE_PATH = old


def test_letter_without_author():
    g = Game.new()
    g.leave_note("慢慢来")
    assert "author" not in g.world["letter"]
    assert "署着" not in g.read_letter()


# ---------- 海域特有动作 ----------
def test_tend_coral_only_at_reef():
    g = Game.new()
    out = g.tend_coral()
    assert "珊瑚" in out
    clock_after = g.world["clock"]
    assert clock_after >= 20
    g2 = Game.new()
    g2.travel("deep")
    out2 = g2.tend_coral()
    assert "这里没有珊瑚" in out2


def test_hide_in_kelp_only_at_kelp():
    g = Game.new()
    out = g.hide_in_kelp()
    assert "这里没有海藻林" in out
    g.travel("kelp")
    out2 = g.hide_in_kelp()
    assert "海藻" in out2
    assert "探出来" in out2


def test_follow_light_only_at_deep():
    g = Game.new()
    out = g.follow_light()
    assert "这里不够暗" in out
    g.travel("deep")
    out2 = g.follow_light()
    assert "光" in out2


def test_watch_turnover_only_at_vent():
    g = Game.new()
    out = g.watch_turnover()
    assert "这里没有热泉" in out
    g.travel("vent")
    out2 = g.watch_turnover(30)
    assert "管虫" in out2 or "红顶" in out2 or "冒出来" in out2
    worm = next(n for n in g._region["lineages"] if n["species"] == "tubeworm")
    assert worm["generation"] >= 4


# ---------- 偶遇事件 ----------
def test_encounters_appear_in_linger():
    import random
    found = False
    for seed in range(50):
        g = Game.new()
        g.rng = random.Random(seed)
        out = g.linger(100)
        from encounters import REGION_ENCOUNTERS
        for line in REGION_ENCOUNTERS["reef"]:
            if line in out:
                found = True
                break
        if found:
            break
    assert found, "偶遇事件在 50 个种子里都没触发过"


def test_encounters_appear_in_travel():
    import random
    found = False
    for seed in range(50):
        g = Game.new()
        g.rng = random.Random(seed)
        out = g.travel("deep")
        from encounters import TRAVEL_ENCOUNTERS
        for line in TRAVEL_ENCOUNTERS:
            if line in out:
                found = True
                break
        if found:
            break
    assert found, "旅途偶遇在 50 个种子里都没触发过"


# ---------- 朋友之间的关系 ----------
def test_npc_interaction_appears_in_look():
    import random, dialogue as D, re
    # Collect distinctive phrases from interaction templates (parts between placeholders)
    phrases = set()
    for lines in D.NPC_INTERACTIONS.values():
        for line in lines:
            for part in re.split(r"\{[ab]\}", line):
                part = part.strip("，。——")
                if len(part) >= 4:
                    phrases.add(part)
    found = False
    for seed in range(100):
        g = Game.new()
        g.rng = random.Random(seed)
        out = g.look()
        for phrase in phrases:
            if phrase in out:
                found = True
                break
        if found:
            break
    assert found, "NPC 互动在 100 个种子里都没出现"


def test_npc_mention_in_greet():
    import random, dialogue as D
    found = False
    for seed in range(80):
        g = Game.new()
        g.rng = random.Random(seed)
        out = g.greet("小螯")
        if "它又说" in out:
            found = True
            break
    assert found, "NPC 提到朋友在 80 个种子里都没触发"


def test_region_action_hint_in_look():
    g = Game.new()
    out = g.look()
    assert "珊瑚" in out and "陪" in out


# ---------- 新功能不泄漏数字 ----------
def test_new_features_no_numbers_leak():
    import re, random
    g = Game.new()
    g.rng = random.Random(42)
    out = []
    out.append(g.tend_coral())
    out.append(g.travel("kelp"))
    out.append(g.hide_in_kelp())
    out.append(g.travel("deep"))
    out.append(g.follow_light())
    out.append(g.travel("vent"))
    out.append(g.watch_turnover(30))
    out.append(g.leave_note("测试", author="test-model"))
    blob = "\n".join(out)
    assert not re.search(r"friendship|last_met|integrity|clock=|\bgen\d", blob)


# ---------- 撞名修复:跨海不同步,父子不重名,家系内可轮回 ----------
def test_descendant_names_desync_across_seas():
    from lineage import new_lineage, settle_node
    reef_crab = new_lineage("crab", "小螯", "reef", 17, born_at=0, friendship=30.0)
    kelp_crab = new_lineage("crab", "石缝", "kelp", 4, born_at=0, friendship=10.0)
    now = 120 * 8  # 推过整整八代
    a, _ = settle_node(reef_crab, now)
    b, _ = settle_node(kelp_crab, now)
    # 同潮开档、同寿命、同世代——以前必然同名;现在两条家系各走各的名字
    assert a["generation"] == b["generation"]
    seq_a, seq_b = [], []
    ca, cb = dict(reef_crab), dict(kelp_crab)
    for gen_now in range(120, 120 * 7, 120):
        ca, _ = settle_node(ca, gen_now)
        cb, _ = settle_node(cb, gen_now)
        seq_a.append(ca["name"]); seq_b.append(cb["name"])
    assert seq_a != seq_b


def test_descendant_never_repeats_parent_name():
    from lineage import new_lineage, make_descendant
    node = new_lineage("crab", "小螯", "reef", 17, born_at=0, friendship=30.0)
    for _ in range(30):
        child = make_descendant(node, born_at=node["born_at"] + node["lifespan"])
        assert child["name"] != node["name"]
        node = child


def test_watch_turnover_names_match_engine():
    """播报里最后一个名字必须等于结算后真正活着的那只。"""
    import random
    g = Game.new()
    g.rng = random.Random(7)
    g.travel("vent")
    out = g.watch_turnover(20)  # 管虫6潮一代,20潮换2-3代,走"逐个点名"分支
    worm = next(n for n in g.world["regions"]["vent"]["lineages"]
                if n["species"] == "tubeworm")
    assert worm["name"] in out


# ---------- 石头台词只在真有石头的海里出现 ----------
def test_stone_lines_gated_by_region():
    import random
    from dialogue import pick_greeting, STONE_PILE_LINES
    from lineage import new_lineage
    node = new_lineage("crab", "半夹", "vent", 99, born_at=0, friendship=1.0)
    node["memory_of_octopus"] = "none"
    rng = random.Random(0)
    for _ in range(200):
        line = pick_greeting(node, now=0, forgotten=False, rng=rng, stone_here=False)
        assert line not in STONE_PILE_LINES
    # 有石头时仍然抽得到(不是把台词删了)
    got = {pick_greeting(node, 0, False, rng=rng, stone_here=True) for _ in range(200)}
    assert got & STONE_PILE_LINES


def test_greet_no_stone_talk_where_no_stones():
    import random
    g = Game.new()
    g.rng = random.Random(3)
    g.leave_stones()          # 石头只垒在珊瑚礁
    g.travel("vent")
    g.linger(600)             # 让记忆掉档,逼出 legend/stranger 台词
    for _ in range(60):
        for n in list(g.world["regions"]["vent"]["lineages"]):
            out = g.greet(n["name"])
            assert "那堆石头" not in out and "这堆石头" not in out


# ---------- 新海域 ----------
def test_new_regions_exist_and_verbs_are_exclusive():
    import random
    g = Game.new()
    g.rng = random.Random(1)
    assert "潮间带" in g.travel("tide")
    out = g.wait_out_tide()
    assert "水洼" in out and "海回来了" in out
    assert "沉船" in g.travel("wreck")
    out2 = g.touch_letters()
    assert "你是快的那个" in out2
    # 动词认地方
    g.travel("reef")
    assert "没有潮间带" in g.wait_out_tide()
    assert "没有沉船" in g.touch_letters()


def test_new_regions_no_numbers_leak():
    import re, random
    g = Game.new()
    g.rng = random.Random(9)
    blob = "\n".join([g.travel("tide"), g.wait_out_tide(), g.linger(50),
                      g.travel("wreck"), g.touch_letters(), g.look()])
    assert not re.search(r"friendship|last_met|integrity|clock=|\bgen\d", blob)


def test_migrate_old_save_gains_new_regions():
    from world import _migrate, fresh_world
    old = fresh_world()
    del old["regions"]["tide"]; del old["regions"]["wreck"]
    del old["dwell"]["tide"]; del old["dwell"]["wreck"]
    migrated = _migrate(old)
    assert "tide" in migrated["regions"] and "wreck" in migrated["regions"]
    assert migrated["dwell"]["tide"] == 0 and migrated["dwell"]["wreck"] == 0


# ---------- 爪子:动词可发现性 ----------
def test_paws_lists_verbs():
    g = Game.new()
    out = g.paws()
    for verb in ("look", "greet", "leave_shells", "leave_gift", "travel", "linger",
                 "leave_note", "tend_coral"):
        assert verb in out, verb
    g.travel("wreck")
    assert "touch_letters" in g.paws()


def test_unknown_verb_gets_friendly_hint():
    g = Game.new()
    try:
        g.arrange_shells()
        assert False, "该抛 AttributeError"
    except AttributeError as e:
        assert "paws" in str(e)


# ---------- 撞名修复:同一片海里活着的家系不重名 ----------
def test_no_duplicate_names_within_region():
    g = Game.new()
    g.travel("vent")
    for tides in (97, 31, 203, 59):
        g.linger(tides)
        names = [n["name"] for n in g._region["lineages"]]
        assert len(names) == len(set(names)), names


# ---------- 没打过照面的家系,不该被说成"你记得的" ----------
def test_unmet_lineage_not_claimed_remembered():
    g = Game.new()               # 不 look:谁都还没见过
    out = g.linger(5000)         # 全员换代
    meta = out.split("你可以跟")[0]   # 只查代谢叙述,不查结尾的场景段
    assert "你记得的" not in meta, meta
    assert any(k in meta for k in ("没来得及认识", "第一次听说", "没什么相干")), meta


# ---------- 贝壳螺旋会被不认识的谁续写 ----------
def test_shell_spiral_can_be_continued():
    g = Game.new()               # clock=0,created_at 为偶数 → 走"续写"分岔
    g.leave_shells()
    out = g.linger(400)
    tr = next(t for t in g.world["traces"] if t["type"] == "shell_spiral")
    assert tr["adopted_by"] == "continued"
    assert "续" in out, out


# ---------- 歌的回流:走样够远的歌,被当"老歌"教还给你,一世一次 ----------
def test_song_returns_once():
    g = Game.new()
    g.teach_song("tide_song")
    out = g.linger(150)          # goby 寿命 45,三代 → hops>=3
    assert "祖上传下来的老歌" in out, out
    out2 = g.linger(50)
    assert "祖上传下来的老歌" not in out2
    assert "老歌" in g.journal()


# ---------- 珊瑚动一次:对极端耐心唯一的回礼 ----------
def test_coral_grows_once_after_long_company():
    g = Game.new()
    g.world["dwell"]["reef"] = 1200
    out = g.tend_coral()
    assert "指甲盖" in out
    out2 = g.tend_coral()
    assert "指甲盖" not in out2
    assert "珊瑚长了一小截" in g.journal()


# ---------- 信叠:历代的你,一人一句 ----------
def test_letters_stack_accumulates():
    g = Game.new()
    g.leave_note("第一句", author="甲")
    g.leave_note("第二句", author="乙")
    out = g.read_letter()
    assert "第一句" in out and "第二句" in out
    assert g.world["letter"]["text"] == "第二句"   # 旧接口仍指向最新一封


def test_old_save_migrates_single_letter_into_stack():
    import world as W
    old = {"version": 2, "clock": 5, "current_region": "reef",
           "turtle": W.fresh_world()["turtle"], "regions": {},
           "letter": {"text": "旧档里的一句话", "at": 3}}
    migrated = W._migrate(old)
    assert migrated["letters"] == [{"text": "旧档里的一句话", "at": 3}]
    assert migrated["seen_ids"] == []
