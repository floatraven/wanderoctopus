# -*- coding: utf-8 -*-
"""《章鱼漫游记》全局配置。

所有数字都住在这里——它们永远不进玩家读到的文本。
玩家是一个 AI:它靠读字、做选择来玩,没有帧率,只有回合。
时间(潮)只靠动作流动:游动让世界变老,章鱼自己不变。
"""

# ---- 时间:单位是"潮"(tide),没有现实时钟,只靠动作推进 ----
MOMENT_COST = 1          # 打招呼 / 环顾 / 随手留痕:一个"当下",几乎不惊动世界
# 海域之间的旅程代价见 world.REGION_GRAPH——旅行才是世代翻页的地方

# ---- 家系链 ----
INHERIT_RATIO_DEFAULT = 0.6
FORGET_THRESHOLD = 600       # 潮。同一个体隔这么久没见 → 章鱼"遗忘"(仅当 friendship>=80 才有意义)
GREET_WARMTH = 12            # 每次认真打招呼,引擎侧悄悄加深的友善(玩家只从下次的措辞里感觉到)
FRIENDSHIP_CAP = 100.0
REPERSONALIZE_AT = 3         # 对一个"传说级"后代打够这么多次招呼,它就真的认识你了(记忆回升一档)

MEMORY_LEVELS = ["direct", "indirect", "legend", "none"]

# 物种寿命(单位:潮)。差异就是叙事引擎。
SPECIES_LIFESPAN = {
    "tubeworm": 6,       # 管虫:热泉边最急的一茬,几潮一代——你能坐着看它当场翻篇。
    "goby": 45,          # 虾虎鱼:两三次拜访就换代
    "crab": 120,
    "seahorse": 200,
    "anglerfish": 900,   # 深海本地长寿锚点(鮟鱇),活得够久,才可能被"遗忘"
    "turtle": 10 ** 9,   # 首席锚点阿龟。她不换代——她哪都能找到章鱼,理由不解释。
}

# ---- 痕迹代谢 ----
TRACE_DECAY_PER_TIDE = 0.004   # 完整度每潮衰减;约 250 潮从立着到散尽
TRACE_HALF = 0.66              # 以上:基本完整
TRACE_SCATTERED = 0.33         # 以下:残缺,可能被某个家系认领为"老地方"

# ---- 歌的跨海迁徙 ----
MIGRATE_AFTER_HOPS = 1       # 一首歌跑调到第 1 代后,就可能被游走的生物带去相邻的海
SONG_RETURN_HOPS = 3         # 歌走样到这一代之后,总有一天会被小鱼当\"老歌\"郑重教还给你

# ---- 珊瑚 ----
CORAL_GROW_DWELL = 1200      # 在珊瑚礁累计待满这么多潮,陪坐时能亲眼看见它长了一小截(一世一次)

# ---- 潮汐谚语(唯一的收集)----
PROVERB_DWELL = 80            # 在一片海累计待满这么多潮,解锁它的谚语

# ---- 偶遇事件 ----
ENCOUNTER_CHANCE_LINGER = 0.4
ENCOUNTER_CHANCE_TRAVEL = 0.35
SONG_FORESHADOW_CHANCE = 0.8   # 目的地有你的歌的回声时,旅途上先听见一耳朵的概率

# ---- 阿龟的时代 ----
# 她不换代,所以她的变化只能长在台词里:认识越久,迎你的方式越不一样。
TURTLE_ERA_MID = 240         # 潮。认识超过这么久,进入"熟"档
TURTLE_ERA_LATE = 900        # 潮。认识超过这么久,进入"老朋友"档

# ---- 朋友的暮年 ----
OLD_AGE_FRAC = 0.7           # 寿命过了这个比例还没换代 → linger/travel 叙述里提一句"老了"

# ---- 朋友之间 ----
NPC_INTERACT_CHANCE = 0.5
NPC_MENTION_CHANCE = 0.25

# ---- 礼物 ----
GIFT_PER_LINEAGE = 1             # 一条家系最多收一份礼物——多了就不是礼物了

# ---- 存档 ----
SAVE_PATH = "wander.json"    # 一次漫游的痕迹。未来的章鱼可以读一个过去自己的档。
