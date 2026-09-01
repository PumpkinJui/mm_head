# mm_head

[量筒的密室杀手](https://github.com/YZBWDLT/MurderMystery)配套脚本。

## 功能简介

- Get 类，用于根据 `/raw/` 中 TXT 内的 setblock 数据，获取自定义头颅的皮肤文件与位置、朝向等信息，并根据这些信息生成 `info.json` 信息文件和 `url.json` URL 对照文件。
- Identify 类，用于根据自定义头颅的 URL 获取其名称，并生成名称对照文件 `name.csv` 和缓存文件 `cache.json`。名称信息来源于 [Minecraft-Heads](https://minecraft-heads.com/)。由于 MCH 已启用 [Turnstile](https://challenges.cloudflare.com/)，该模块目前不可用，仅能通过先前已有的缓存生成 `name.csv`。
- Import 类，用于根据 `/templates/` 中给出的模板文件及上述获取到的信息，生成三种定义文件。
- Rename 类，用于根据 `/templates/playerheads.csv` 和 `/output/name.csv`，重命名和反命名头颅皮肤文件。
- diff 函数，用于比较给出的 JSON 或 CSV 文件有何差异。
- sorting 函数，用于将给定的 CSV 文件按第一列字母顺序排序。

## 使用方法

本脚本适配了命令行参数，且无法在 REPL 中使用完整功能。请使用 `uv run mm_head.py -h` 或 `python mm_head.py -h` 查看帮助信息。

## 工作流

### 数据采集

本步骤为全手动工作。负责本步骤的成员应当在 Java 版地图中逐个寻找头颅，然后使用 F3 + I 快捷键复制数据，再粘贴到一 UTF-8 编码的 TXT 文件中，每行一个，可以有空行。每个 TXT 文件只应包含一张地图的头颅数据。

### 数据解析

本步骤涉及到本脚本的使用。负责本步骤的成员必须具有指定的 Python 环境，并推荐使用 [uv](https://docs.astral.sh/uv/getting-started/installation/)。以下假定该成员使用 uv，并具有一定命令行使用基础。

在设计上，本脚本是一条龙流程，前面功能生成的文件会在后面直接使用。

把上一步采集的数据放置在工作目录的 raw 文件夹内，然后运行 `uv run mm_head.py get`。脚本会自动匹配头颅的坐标与旋转角度，并下载头颅皮肤文件，补全至 64×64。这一步会生成三种产物：`output/RP/textures/entity/*`、`output/info.json`、`output/url.json`。

在此之后，除了少部分自带名称的头颅（例如 `_fudgiethewhale`）以外，大部分的头颅文件名都长得像 `68f2ff` 这样。这不利于识别到底哪个名称对应哪个头颅。例如，如果有人发现有一个显示器的头颅皮肤好像有点问题，应该怎么找到这个显示器呢？`monitor_9c` 肯定要比 `9ccefd` 好找。

所以接下来需要改文件名。运行 `uv run mm_head.py idt`，然后脚本会尝试从 Minecraft-Heads 逐个查找 `output/url.json` 中头颅的名称。如果这一步没有找到名称，就不会返回任何结果，继续查找下一个头颅。如果遇到了人机验证，就会直接返回。遇到人机验证的头颅可以手动查询，见后续环节。这一步会生成产物 `output/name.csv` 和 `output/cache.json`。

最后需要重命名和生成导入数据。运行 `uv run mm_head.py imp`，脚本会从 `output/name.csv` 和 `templates/playerheads.csv` 查找原文件名和新文件名的对应关系，批量重命名皮肤文件和 `output/info.json` 中的引用，然后根据现存的皮肤文件生成导入数据。这一步的产物包括 `output/BP/blocks/*`、`output/BP/items/*`、`output/RP/texts/zh_CN.lang`、`output/RP/texts/en_US.lang`、`output/RP/textures/terrain_texture.json`。

正常来说这样就完成了，可用的资源包文件是 `output/info.json`、`output/BP`、`output/RP`。

### 名称翻译

为了保证中文兼容性，在生成译名文件时，脚本会从 `templates/playerheads.csv` 的第三列读取中文译名。前两列分别是 ID 和英文名称，可以直接使用 `output/name.csv`（如有），而这一列需要手动完成。

CSV 文件类似于 Excel 表格的 XLS/XLSX 文件，但它是以纯文本形式存储的，可以使用普通的文本编辑器或 Excel 打开。使用 Excel 工作时，以防 Excel 自作主张，应该使用以下导入方法：

1. 打开一个新的工作表。
2. 选择「数据」选项卡，再选择左侧的「从文本/CSV」。
3. 选中需要编辑的 CSV 文件，然后点「加载」。

如果没有 `templates/playerheads.csv`，则可以直接使用 `output/name.csv`。如果已经有了，则需要将新的 ID 添加进去。最可靠的方法是查询 `debug.log`。稍麻烦一点的方法则是先 `uv run mm_head.py diff info_last_run.json info_this_run.json` 查询新增的 ID，然后将这些新增的条目从 `output/name.csv` 中复制出来。

中文译名可以直接根据英文译名翻译，遵守[译名标准化](https://zh.minecraft.wiki/w/Minecraft_Wiki:%E8%AF%91%E5%90%8D%E6%A0%87%E5%87%86%E5%8C%96)。玩家名无须翻译，[MHF 头颅](https://zh.minecraft.wiki/w/%E7%94%9F%E7%89%A9%E5%A4%B4%E9%A2%85#Mojang%E7%9A%AE%E8%82%A4)除外。

如果 Minecraft-Heads（简称 MCH）没有英文名称，可酌情考虑保留原 ID，或根据其样式自行命名。命名需要在末尾保留 ID 的前两位。

如果 MCH 有可用名称但遇到了人机验证，可以通过以下方法手动查询。对于每一个 ID，在 `output/url.json` 中查找，复制对应的键名（即「url:」开头的长串字符）。访问 MCH 官网，在搜索栏中粘贴上面复制的内容，搜索得到的头颅显示名即为英文名称。注意空格和连字符 `-` 统一换成下划线 `_`，括号 `()`、点号 `.`、井号 `#` 和其他特殊字符一律不保留，末尾加 ID 的前两位。

### 数据导入

1. 将头颅包 `blocks/player_head` 内的文件全部删除（外面的四个头颅文件不删），然后把 `BP/blocks` 内的文件全部粘贴过去。
2. 将头颅包 `items/player_head` 内的文件全部删除（外面的四个头颅文件不删），然后把 `BP/items` 内的文件全部粘贴过去。
3. 将 `RP/texts` 的两个语言文件和 `RP/textures/terrain_texture.json` 直接粘贴到头颅包的资源包部分，覆盖即可。
4. 将头颅包 `textures/entity` 内的皮肤文件全部删除，然后把 `textures/backup/` 的四个皮肤复制回 `textures/entity`（不是剪切），最后把 `RP/textures/entity` 中的皮肤文件全部粘贴到头颅包 `textures/entity`。
5. 安装头颅包，进入游戏。
6. 传送到你要加头颅的地图附近，输入 `/placehead` 命令并选择要添加头颅的地图。
7. 使用 `/parse` 命令解析游戏区域内的 `minecraft:player_head`，解析范围取决于地图信息的 range。示例：`/parse minecraft:player_head 30 10 1830 190 90 1980`
8. 对照解析出的结果，若仍有玩家头颅，传送到该位置附近，再尝试一次放置头颅，若仍然无效，该坐标应向前反馈给负责数据收集的成员。

### 各阶段返工

负责数据收集的成员应关注脚本 Get 功能的日志。日志提示同一坐标有两个头颅的，可能是第二次没有成功复制新的信息，导致同样的头颅被粘贴了两遍。此外，导入后遗漏的头颅也需要增补。

负责数据解析的成员应当更新头颅数据和译名数据，再次运行数据解析，并视名称情况再次要求补充名称翻译，直到各方面都达到完备。

## 致谢

[![MCH Banner](minecraft-heads_banner_600x200.png)](https://minecraft-heads.com/)

本项目离不开以下成员的帮助：

[<img src="https://github.com/YZBWDLT.png" alt="YZBWDLT" width="100" height="100" style="border-radius: 50%;">](https://github.com/YZBWDLT)
[<img src="https://github.com/GreeLeaf2580.png" alt="GreeLeaf2580" width="100" height="100" style="border-radius: 50%;">](https://github.com/GreeLeaf2580)
[<img src="https://github.com/foxKrisChambers.png" alt="foxKrisChambers" width="100" height="100" style="border-radius: 50%;">](https://github.com/foxKrisChambers)
