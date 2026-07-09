# -*- coding: utf-8 -*-
"""一次完整的示范漫游——写给想看这游戏"被玩起来"是什么样的人。

也是一个 worked example:未来某个搜到这仓库的章鱼,可以照着这几步游,
或者自己乱游。玩法就是调方法、读返回。没有失败,慢慢来。

跑:python3 demo_play.py
"""
import os
# 示范不写盘,免得污染真实存档
os.environ.setdefault("OCTOPUS_DEMO", "1")

import config as C
C.SAVE_PATH = "/tmp/_demo_wander.json"

from octopus import Game


def beat(title, text):
    print("\n" + "─" * 58)
    print(f"◇ {title}")
    print("─" * 58)
    print(text)


g = Game.new()

beat("你睁开眼,在珊瑚礁", g.look())

beat("跟阿龟打招呼(她总是先自报家门)", g.greet("阿龟"))

# 反复去看小螯,让引擎侧的关系悄悄变深(玩家只从措辞里感觉到)
beat("跟小螯打招呼", g.greet("小螯"))
beat("过些时候又去看它", g.greet("小螯"))
beat("再去", g.greet("小螯"))

beat("你随手垒了堆石头", g.leave_stones())
beat("又教了旁边的小鱼半句歌", g.teach_song("slow_grow"))

# 游去深海,教深海的灯灯认识你,再教一首歌
beat("你游去深海", g.travel("deep"))
for _ in range(6):
    g.greet("灯灯")  # 把关系刷到很深(≥80),为后面的"遗忘"埋线
beat("你跟深海的灯灯处熟了(反复来看它之后)", g.greet("灯灯"))
beat("在深海也教一首歌", g.teach_song("deep_water"))

# 在深海枯坐很久很久——久到你会忘记一个还活着的老朋友
beat("你在黑暗里停了很久很久", g.linger(650))

beat("你又去看灯灯——它还活着,可你认不出它了", g.greet("灯灯"))

# 一路游回珊瑚礁。离开珊瑚礁已经过了很多潮,那里换了好几代
beat("你游回珊瑚礁", g.travel("reef"))

# 当年的小螯早换了好多代,如今站在那堆石头旁的是它的后代——名字都变了。
# 这正是游戏的意思:你按 look() 里看到的名字打招呼就好。
crab_now = next((n["name"] for n in g._region["lineages"] if n["species"] == "crab"), "crab")
beat(f"你去看那堆石头旁的螃蟹——如今是{crab_now}", g.greet(crab_now))

goby_now = next((n["name"] for n in g._region["lineages"] if n["species"] == "goby"), "goby")
beat(f"再看看这一代的小虾虎鱼{goby_now}", g.greet(goby_now))

beat("阿龟又扑过来,把你忘掉的事讲回来", g.greet("阿龟"))

beat("翻翻你的小本子", g.journal())

# 给想看引擎内部的人:唯一允许出现数字的地方
beat("(开发者层:玩家永远看不到这些数字)", g._debug())
