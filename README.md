# mm_head

[量筒的密室杀手](https://github.com/YZBWDLT/MurderMystery)配套脚本。

本脚本提供以下功能：

- Get 类，用于根据 `/raw/` 中 TXT 内的 setblock 数据，获取自定义头颅的皮肤文件与位置、朝向等信息，并根据这些信息生成 `info.json` 信息文件和 `url.json` URL 对照文件。
- Identify 类，用于根据自定义头颅的 URL 获取其名称，并生成名称对照文件 `name.csv` 和缓存文件 `cache.json`。名称信息来源于 [Minecraft-Heads](https://minecraft-heads.com/)。由于 MCH 已启用 [Turnstile](https://challenges.cloudflare.com/)，该模块目前不可用，仅能通过先前已有的缓存生成 `name.csv`。
- Import 类，用于根据 `/templates/` 中给出的模板文件及上述获取到的信息，生成三种定义文件。
- Rename 类，用于根据 `/templates/playerheads.csv` 和 `/output/name.csv`，重命名和反命名皮肤文件。
- diff 函数，用于比较给出的 JSON 或 CSV 文件有何差异。
- sorting 函数，用于将给定的 CSV 文件按第一列字母顺序排序。

本脚本最低运行版本为 Python 3.10。

本脚本为命令行脚本，请使用 `uv run mm_head.py -h` 查看帮助信息。

[![MCH Banner](minecraft-heads_banner_600x200.png)](https://minecraft-heads.com/)

本项目离不开以下成员的帮助：

[<img src="https://github.com/YZBWDLT.png" alt="YZBWDLT" width="100" height="100" style="border-radius: 50%;">](https://github.com/YZBWDLT)
[<img src="https://github.com/GreeLeaf2580.png" alt="GreeLeaf2580" width="100" height="100" style="border-radius: 50%;">](https://github.com/GreeLeaf2580)
[<img src="https://github.com/foxKrisChambers.png" alt="foxKrisChambers" width="100" height="100" style="border-radius: 50%;">](https://github.com/foxKrisChambers)
