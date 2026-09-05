from argparse import ArgumentParser
from base64 import urlsafe_b64decode as b64d
from csv import reader, writer
from json import dump, dumps, load, loads
from logging import (
    DEBUG,
    WARNING,
    FileHandler,
    Formatter,
    StreamHandler,
    getLogger,
    shutdown,
)
from pathlib import Path
from re import search, sub
from time import sleep
from typing import Final, TypedDict

from deepdiff import DeepDiff
from PIL import Image
from requests import exceptions, get


class ExtractedDictInfo(TypedDict):
    id: str
    location: str
    rotation: int | None
    facing: str | None
    url: str
    meaningful: bool
    armor_stand: bool


type DataDictInfo = dict[str, list[ExtractedDictInfo]]


class Get:
    POS: Final[str] = 'GET'

    @staticmethod
    def search_group(pattern: str, data: str) -> str:
        result = search(pattern, data)
        if not result:
            logger.error('不能从 %s 中获得 "%s"！', data, pattern, extra={'pos': 'GET'})
            raise AssertionError
        return result.group(1)

    @staticmethod
    def get_name(data: str) -> tuple[str, str, bool]:
        name: str = ''
        url: str = ''
        meaningful: bool = True
        trans = str.maketrans(' -', '__', '().#')
        if 'value:' in data:
            b64_raw = Get.search_group(r'value: ?"([^\"]+)"', data)
            b64_raw += '=' * (-len(b64_raw) % 4)
            b64_decoded = b64d(b64_raw).decode()
            url = loads(b64_decoded)['textures']['SKIN']['url'].replace(
                'http:', 'https:'
            )
            name_raw = search(r'(?:name|text): ?"([^"]*)"', data)
            if 'minecraft:custom_name' in data and 'text:' not in data:
                name_raw = search(
                    r'"minecraft:custom_name": ?"(?:§[a-z\d])?([^"]+)"', data
                )
            if not name_raw or name_raw.group(1) == 'textures':
                name = url[url.rfind('/') + 1 : url.rfind('/') + 7]
                meaningful = False
            else:
                name = name_raw.group(1).translate(trans).lower()
        elif 'head:' in data:
            name = Get.search_group(r'head: ?\{[^}]*id: ?"([^"]+)"\}', data)
            name = name.translate(trans).lower()
        else:
            meaningful = False
        if meaningful and name and url:
            name += f'_{url[url.rfind("/") + 1 : url.rfind("/") + 3]}'
        return name, url, meaningful

    def extract(self, data: str) -> ExtractedDictInfo | None:
        facing, rotation = None, None
        armor_stand = 'armor_stand' in data
        location = Get.search_group(r' ([\d\-. ]+) ', data)
        if '.' in location:
            location = [int(float(i)) for i in location.split(' ')]
            location[1] += 1
            location = ' '.join(map(str, location))
        if 'rotation' in data:
            rotation = int(Get.search_group(r'rotation=(\d+)', data))
        elif 'Rotation' in data:
            rotation_map = [180]
            rotation_map.extend(int(-157.5 + i * 22.5) for i in range(15))
            rotation_raw = Get.search_group(r'Rotation: ?\[([\d\-.]+)f', data)
            rotation_raw = '180.0' if rotation_raw == '-180.0' else rotation_raw
            rotation_closest = min(
                rotation_map, key=lambda x: abs(int(float(rotation_raw)) - x)
            )
            rotation = rotation_map.index(rotation_closest)
        elif 'facing' in data:
            facing = Get.search_group(r'facing=([^,\]]+)', data)
        name, url, meaningful = Get.get_name(data)
        if not (name or url or meaningful):
            print()
            logger.warning('无头颅数据。', extra={'pos': f'L{self.ln}'})
            return None
        print(name, end=' - ', flush=True)
        return {
            'id': name,
            'location': location,
            'rotation': rotation,
            'facing': facing,
            'url': url,
            'meaningful': meaningful,
            'armor_stand': armor_stand,
        }

    def downloading(self, url: str, name: str) -> bool:
        img_path = self.img_dir / f'{name}.png'
        if argp().nodl or not url or img_path.is_file():
            print('跳过下载...', end='', flush=True)
            if url and img_path.is_file() and Get.padding(img_path):
                print('成功！', flush=True)
            else:
                print()
            return False
        print('开始下载...', end='', flush=True)
        for i in range(3):
            try:
                response = get(url, timeout=(6.05, 10))
                response.raise_for_status()
                break
            except exceptions.ConnectionError:
                print(f'连接错误（{i + 1}/3）...', end='', flush=True)
                sleep(1)
            except exceptions.HTTPError as e:
                assert e.response is not None
                print(
                    f'状态码 {e.response.status_code}（{i + 1}/3）...',
                    end='',
                    flush=True,
                )
            except exceptions.Timeout:
                print(f'超时（{i + 1}/3）...', end='', flush=True)
                sleep(1)
        else:
            print()
            logger.error('已超时。', extra={'pos': f'L{self.ln} - {name}'})
            return False
        with open(img_path, 'wb') as f:
            _ = f.write(response.content)
        _ = Get.padding(img_path)
        print('成功！', flush=True)
        return True

    @staticmethod
    def padding(img_path: Path) -> bool:
        temp_path = img_path.with_name(img_path.name + '.tmp')
        with Image.open(img_path) as f:
            if f.size != (64, 32):
                return False
            print('转换中...', end='', flush=True)
            img = f.convert('RGBA')
            if 'thegreatergod' in str(img_path):
                print('thelesserdog...', end='', flush=True)
                pixel = img.load()
                assert pixel is not None
                for w in range(31, 64):
                    for h in range(16):
                        if pixel[w, h] == (255, 255, 255, 255):
                            pixel[w, h] = (0, 0, 0, 0)
            new_img = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
            new_img.paste(img, (0, 0), img)
            new_img.save(temp_path, format='PNG')
        _ = temp_path.replace(img_path)
        return True

    def merge(
        self,
        dict_general: DataDictInfo,
        dict_unique: ExtractedDictInfo | None,
        stem: str,
    ) -> DataDictInfo:
        if not dict_unique:
            return dict_general
        name, url = dict_unique['id'], dict_unique['url']
        _ = self.downloading(url, name)
        if dict_general.get(stem):
            location2id = {i['location']: i['id'] for i in dict_general[stem]}
            if not (id_tocheck := location2id.get(dict_unique['location'])):
                dict_general[stem].append(dict_unique)
            else:
                logger.warning(
                    '位置 %s 已存在头颅 %s。',
                    dict_unique['location'],
                    id_tocheck,
                    extra={'pos': f'L{self.ln} - {name}'},
                )
        else:
            dict_general[stem] = [dict_unique]
        if self.n_lt.get(name, [url])[0] != url:
            old = name
            i = 0
            while self.n_lt.get(name, [url])[0] != url:
                i += 1
                name = f'{name}_{i}' if i == 1 else f'{name[: name.rfind("_")]}_{i}'
            dict_unique['id'] = name
            logger.warning(
                '对应多重 URL，已将新的更名为 %s。',
                name,
                extra={'pos': f'L{self.ln} - {old}'},
            )
            print(f'L{self.ln} - {name} - ', end='', flush=True)
            _ = self.downloading(url, name)
        if url:
            self.n_lt[name] = (url, dict_unique['meaningful'])
        return dict_general

    @staticmethod
    def prune(dict_pre: DataDictInfo) -> tuple[DataDictInfo, list[dict[str, str]]]:
        dict_post: DataDictInfo = {}
        url2id: list[dict[str, str]] = []
        for stem, data in dict_pre.items():
            dict_post[stem] = []
            if not argp().nourl:
                url2id = [
                    {
                        f'url:{
                            entry["url"].replace(
                                "https://textures.minecraft.net/texture/", ""
                            )
                        }': entry['id']
                    }
                    for entry in data
                    if entry['url']
                ]
            for entry in data:
                popped = {'url', 'meaningful'}
                if not argp().armorstand:
                    popped.add('armor_stand')
                popped.update(m for m, n in entry.items() if not n and n != 0)
                _ = [entry.pop(item) for item in popped]
                dict_post[stem].append(entry)
        return dict_post, url2id

    def pro(self, stem: str, data: list) -> dict:
        dt = {}
        for i, j in enumerate(data):
            self.ln = str(i + 1).zfill(3)
            if not j.strip():
                continue
            if not argp().armorstand and 'armor_stand' in j:
                logger.info('盔甲架输出已关闭。', extra={'pos': f'L{self.ln}'})
                continue
            try:
                print(f'L{self.ln}', end=' - ', flush=True)
                dt_pending = self.extract(j)
                dt = self.merge(dt, dt_pending, stem)
            except Exception:
                print()
                logger.exception('未知错误。', extra={'pos': f'L{self.ln}'})
        print()
        return dt

    def out(self, dt: dict, urls: list) -> None:
        data = dumps(dt, indent=4)
        dup = {}
        u_lt = tuple((i, j, k) for i, (j, k) in self.n_lt.items())
        names = {}
        for name, url, mname in u_lt:
            if mname:
                names[url] = name
        for name, url, mname in u_lt:
            if (nurl := names.get(url)) and name != nurl:
                dup[name] = nurl
                data = data.replace(f'"{name}"', f'"{nurl}"')
                logger.warning(
                    'URL 对应多重名称，已统一为 %s。', nurl, extra={'pos': f'{name}'}
                )
                if (old := self.img_dir / f'{name}.png').is_file():
                    old.replace(self.img_dir / f'{nurl}.png')
                else:
                    logger.warning('该文件不存在，已跳过。', extra={'pos': f'{name}'})
        with open('output/info.json', 'w', encoding='utf-8') as wt:
            wt.write(data)
        if not argp().nourl:
            past = set()
            urln = []
            for i in urls:
                m, n = next(iter(i.items()))
                if n in dup:
                    i[m] = dup[n]
                j = tuple(sorted(i.items()))
                if j not in past:
                    past.add(j)
                    urln.append(i)
            with open('output/url.json', 'w', encoding='utf-8') as wt:
                dump(urln, wt, indent=4)

    def __init__(self) -> None:
        self.n_lt = {}
        self.img_dir = Path('output/RP/textures/entity')
        dt = {}
        f = None
        urls = []
        if argp().nodl:
            logger.info('跳过下载已开启。', extra={'pos': self.POS})
        else:
            self.img_dir.mkdir(parents=True, exist_ok=True)
        if argp().nourl:
            logger.info('跳过 URL 记录已开启。', extra={'pos': self.POS})
        for f in Path('raw').glob('*.txt'):
            stem = f.stem
            with open(f, 'r', encoding='utf-8') as rd:
                data = rd.read().splitlines()
            logger.warning('%s - L%s', stem, len(data), extra={'pos': self.POS})
            dtn, url = Get.prune(self.pro(stem, data))
            dt |= dtn
            if url:
                urls.extend(url)
        if not f:
            logger.warning(
                '未在 raw 目录内找到 txt 后缀的批处理文件。', extra={'pos': self.POS}
            )
            data = [input('输入待处理项：')]
            dt, url = Get.prune(self.pro('info', data))
            if url:
                urls.extend(url)
        self.out(dt, urls)
        logger.info('信息提取完成！', extra={'pos': self.POS})


class Identify:
    POS: Final[str] = 'IDT'

    @staticmethod
    def ext(url: str, msg: str) -> str:
        sleep(0.2)
        for i in range(3):
            try:
                res = get(
                    'https://minecraft-heads.com/custom-heads/search',
                    params={'searchterm': url},
                    timeout=(6.05, 10),
                )
                res.raise_for_status()
                break
            except exceptions.ConnectionError:
                print(f'连接错误（{i + 1}/3）...', end='', flush=True)
                sleep(1)
            except exceptions.HTTPError as e:
                data = e.response
                assert data is not None
                if 'Just a moment' in data.text:
                    raise PermissionError from e
                print(f'状态码 {data.status_code}（{i + 1}/3）...', end='', flush=True)
            except exceptions.Timeout:
                print(f'超时（{i + 1}/3）...', end='', flush=True)
                sleep(1)
        else:
            print()
            logger.error('已超时。', extra={'pos': msg})
            return ''
        data = res.text
        if 'No Heads available' in data:
            return ''
        con = data[data.find('descending') : data.find('Search Tips')]
        return Get.search_group(r'a href=.+title="([^"]+)"', con)

    @staticmethod
    def cache() -> dict:
        if argp().nocache:
            logger.info('缓存已忽略！', extra={'pos': 'IDT'})
            return {}
        if not Path('output/cache.json').is_file():
            return {}
        with open('output/cache.json', 'r', encoding='utf-8') as rd:
            data = load(rd)
            data_popped = [i for i, j in data.items() if not j]
            _ = [data.pop(i) for i in data_popped]
            logger.info('缓存已加载！', extra={'pos': 'IDT'})
            return data

    @staticmethod
    def stripping(name: str, identifier: str) -> str:
        name = sub(r'&(#[\d]+|#x[\da-fA-F]+|[a-zA-Z]+);', '', name)
        name = name.translate(str.maketrans(' -', '__', '().#')).lower()
        name += '_' + identifier
        return name

    def pro(self, data: dict, ln: str) -> None:
        n, m = next(iter(data.items()))
        msg = f'L{ln} - {m}'
        print(msg, end=' - ', flush=True)
        if (k := self.c_lt.get(m)) or k == '':
            j = k
            print('（缓存）', end='', flush=True)
        else:
            j = Identify.ext(n, msg)
            if j:
                self.c_lt[m] = j
        if j:
            j = Identify.stripping(j, n[4:6])
            print(j, flush=True)
            if l := self.n_lt.get(j):
                self.dup[j] = self.dup.get(j, 0) + 1
                k = j
                j += f'_{self.dup[j]}'
                logger.warning(
                    '与 %s 拥有共同的新名称，已更名为 %s。', l, j, extra={'pos': msg}
                )
            self.n_lt[j] = m
        else:
            print(m, flush=True)
            j = m
            logger.warning('无可用名称。', extra={'pos': msg})
        self.dt.append({'old': m, 'new': j})

    def __init__(self) -> None:
        self.c_lt = Identify.cache()
        self.dt = []
        self.dup = {}
        self.n_lt = {}
        try:
            path = 'output/url.json'
            if Path(path).is_file():
                with open(path, 'r', encoding='utf-8') as rd:
                    data = load(rd)
                logger.info('%s - L%s', path, len(data), extra={'pos': self.POS})
                for i, j in enumerate(data):
                    self.pro(j, str(i + 1).zfill(3))
                lt = [[i['old'], i['new']] for i in self.dt]
                with open(
                    'output/name.csv', 'w', encoding='utf-8-sig', newline=''
                ) as f:
                    writing = writer(f)
                    writing.writerows(lt)
            else:
                logger.error('%s 不存在！', path, extra={'pos': self.POS})
            logger.info('名称对照完成！', extra={'pos': self.POS})
        except PermissionError:
            print()
            logger.error('已触发 Turnstile！', extra={'pos': self.POS})
            if self.c_lt:
                with open(
                    'output/name.csv', 'w', encoding='utf-8-sig', newline=''
                ) as f:
                    lt = [
                        (i, Identify.stripping(j, i[0:2])) for i, j in self.c_lt.items()
                    ]
                    writing = writer(f)
                    writing.writerows(lt)
        finally:
            with open('output/cache.json', 'w', encoding='utf-8') as wt:
                dump(self.c_lt, wt, indent=4)
                logger.info('缓存已输出！', extra={'pos': self.POS})


class Import:
    POS: Final[str] = 'IMP'

    @staticmethod
    def blotem(idn: str, templ: str) -> bool:
        if not Path(templ).is_file():
            return False
        with open(templ, 'r', encoding='utf-8') as rd:
            tem = rd.read()
        flag = templ[templ.rfind('.', 0, -7) + 1 : templ.rfind('.')]
        wt_path = f'output/BP/{flag}s/{idn}.{flag}.json'
        uni = tem.replace('yzbwdlt', idn)
        if flag == 'block' and idn in {
            'swamp_monster',
            'swamp_monster_3d',
            'diamivore_3d',
        }:
            uni = uni.replace('popped', 'no_reaction')
        Import.writing(wt_path, uni)
        return True

    @staticmethod
    def terlang(idn_lt: tuple) -> None:
        fb = True
        if Path('templates/playerheads.csv').is_file():
            fb = False
            with open('templates/playerheads.csv', 'r', encoding='utf-8-sig') as f:
                reading = reader(f)
                data = {i[1]: i[2] for i in reading}
        else:
            logger.warning('未找到译名文件，使用备用方案！', extra={'pos': 'IMP'})
        ter = '\n'.join(
            f'        "player_head_{i[0]}": {{ "textures": "textures/entity/{i[0]}" }},'
            for i in idn_lt
        )
        zhl = (
            '\n'.join(
                f'tile.player_head:{i[0]}.name={i[1].title()} 的头' for i in idn_lt
            )
            if fb
            else '\n'.join(
                f'tile.player_head:{i[0]}.name={
                    data.get(i[0], i[0])[: data.get(i[0], i[0]).rfind("_")].title()
                    if "_" in {data.get(i[0], i[0])[-3], data.get(i[0], i[0])[-2]}
                    else data.get(i[0], i[1]).title()
                } 的头'
                for i in idn_lt
            )
        )
        enl = '\n'.join(
            f"tile.player_head:{i[0]}.name={i[1].title()}'s Head" for i in idn_lt
        )
        ter_full = (
            '{\n'
            '    "resource_pack_name": "player_head",\n'
            '    "texture_data": {\n'
            f'{ter}\n\n'
            '        "player_head_yzbwdlt": { "textures": "textures/entity/yzbwdlt" },\n'
            '        "player_head_chthollies": { "textures": "textures/entity/chthollies" },\n'
            '        "player_head_jhy2189": { "textures": "textures/entity/jhy2189" },\n'
            '        "player_head_freamoluwu": { "textures": "textures/entity/freamoluwu" \n}'
            '    }'
            '}'
        )
        zhl_full = (
            '## ===== 方块 =====\n'
            f'{zhl}\n\n'
            'tile.player_head:yzbwdlt.name=YZBWDLT 的头\n'
            'tile.player_head:freamoluwu.name=Freamoluwu 的头\n'
            'tile.player_head:jhy2189.name=JHY2189 的头\n'
            'tile.player_head:chthollies.name=Chthollies 的头\n'
        )
        enl_full = (
            '## ===== Blocks =====\n'
            f'{enl}\n\n'
            "tile.player_head:yzbwdlt.name=YZBWDLT's Head\n"
            "tile.player_head:freamoluwu.name=Freamoluwu's Head\n"
            "tile.player_head:jhy2189.name=JHY2189's Head\n"
            "tile.player_head:chthollies.name=Chthollies's Head\n"
        )
        Import.writing('output/RP/textures/terrain_texture.json', ter_full)
        Import.writing('output/RP/texts/en_US.lang', enl_full)
        Import.writing('output/RP/texts/zh_CN.lang', zhl_full)

    def gen(self) -> None:
        block_tem = 'templates/yzbwdlt.block.json'
        item_tem = 'templates/yzbwdlt.item.json'
        img_dir = Path('output/RP/textures/entity')
        block_info, item_info = True, True
        stems = tuple(i.stem for i in img_dir.glob('*.png'))
        if not stems:
            logger.error('无 png 文件！', extra={'pos': self.POS})
            return
        stems = tuple(
            (i, (i[: i.rfind('_')] if '_' in {i[-3], i[-2]} else i)) for i in stems
        )
        Import.terlang(stems)
        if argp().nobp:
            logger.info('跳过 blotem 生成已开启。', extra={'pos': self.POS})
        else:
            for i, _ in stems:
                if not Import.blotem(i, block_tem) and block_info:
                    logger.error(
                        '未找到模板 %s，跳过 block 生成！',
                        block_tem,
                        extra={'pos': self.POS},
                    )
                    block_info = False
                if not Import.blotem(i, item_tem) and item_info:
                    logger.error(
                        '未找到模板 %s，跳过 item 生成！',
                        item_tem,
                        extra={'pos': self.POS},
                    )
                    item_info = False
        logger.info('导入数据生成完成！', extra={'pos': self.POS})

    @staticmethod
    def writing(path: str, content: str) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)

    def __init__(self) -> None:
        Rename()
        self.gen()


class Rename:
    def reading(self, path: Path) -> dict[str, tuple[str, str]]:
        with open(path, 'r', encoding='utf-8-sig') as f:
            reading = reader(f)
            names = {
                ((i[1] or i[0]) if self.revert_mode else i[0]): (
                    (i[0] if self.revert_mode else (i[1] or i[0])),
                    path.stem,
                )
                for i in reading
            }
        names.pop('Column1', None)
        names.pop('Column2', None)
        return names

    def read_names(self) -> dict[str, tuple[str, str]]:
        playerheads_csv = Path('templates/playerheads.csv')
        name_csv = Path('output/name.csv')
        name_list: dict[str, tuple[str, str]] = {}
        if name_csv.is_file():
            name_list.update(self.reading(name_csv))
            logger.info('工作在 name 模式下。', extra={'pos': self.pos})
        if playerheads_csv.is_file():
            name_list.update(self.reading(playerheads_csv))
            logger.info('工作在 playerheads 模式下。', extra={'pos': self.pos})
        return name_list

    def renaming(self, old_stem: str, new_stem: str, info_data: str) -> str:
        old_path = self.img_dir / f'{old_stem}.png'
        new_path = self.img_dir / f'{new_stem}.png'
        logger.info('重命名为 %s。', new_stem, extra={'pos': old_stem})
        if new_path.is_file():
            logger.warning(
                '新文件 %s 存在，已覆盖。', new_stem, extra={'pos': old_stem}
            )
        if old_path.is_file():
            old_path.replace(new_path)
        else:
            logger.warning('该文件不存在，已跳过。', extra={'pos': old_stem})
        return info_data.replace(f'"{old_stem}"', f'"{new_stem}"')

    def __init__(self, revert_mode: bool = False) -> None:
        self.pos: Final[str] = 'REVERT' if revert_mode else 'RENAME'
        self.revert_mode = revert_mode
        self.img_dir = Path('output/RP/textures/entity')
        info_json = Path('output/info.json')
        playerheads_csv = Path('templates/playerheads.csv')
        if not (names := self.read_names()):
            logger.error('未找到名称文件，跳过重命名！', extra={'pos': self.pos})
            return
        if info_json.is_file():
            with open(info_json, 'r', encoding='utf-8') as f:
                info_data = f.read()
        else:
            logger.warning('未找到信息文件，跳过该文件！', extra={'pos': self.pos})
            info_data = ''
        stems = tuple(i.stem for i in self.img_dir.glob('*.png'))
        all_new_stems = (
            {new_stem for new_stem, _ in self.reading(playerheads_csv).values()}
            if playerheads_csv.is_file()
            else set()
        )
        for stem in stems:
            if stem in names:
                new_stem, work_mode = names.pop(stem)
                if new_stem != stem:
                    info_data = self.renaming(stem, new_stem, info_data)
                if (
                    work_mode == 'name'
                    and playerheads_csv.is_file()
                    and new_stem not in all_new_stems
                ):
                    logger.warning(
                        '未在 playerheads 中找到对应的条目，新名称 %s。',
                        new_stem,
                        extra={'pos': stem},
                    )
            elif stem.isdecimal():
                new_stem = stem[:-1] + 'r'
                logger.warning('非法 ID，已更名为 %s。', new_stem, extra={'pos': stem})
                info_data = self.renaming(stem, new_stem, info_data)
            elif playerheads_csv.is_file() and stem not in all_new_stems:
                logger.warning('未在名称文件中找到对应的条目。', extra={'pos': stem})
        names_popped = [stem for stem, info in names.items() if info[1] == 'name']
        _ = [names.pop(unrelated) for unrelated in names_popped]
        if names:
            unused = '、'.join(names.keys())
            logger.warning('未使用的条目：%s。', unused, extra={'pos': self.pos})
        if info_json.is_file():
            with open(info_json, 'w', encoding='utf-8') as f:
                f.write(info_data)
        logger.info('重命名完成！', extra={'pos': self.pos})


def diff() -> None:
    pos: Final[str] = 'DIFF'
    file_source, file_dest = map(Path, argp().files)
    if not file_source.is_file():
        logger.error('%s 文件不存在！', str(file_source), extra={'pos': pos})
        return
    if not file_dest.is_file():
        logger.error('%s 文件不存在！', str(file_dest), extra={'pos': pos})
        return
    source_suffix = file_source.suffix.lower()
    dest_suffix = file_dest.suffix.lower()
    if source_suffix != dest_suffix:
        logger.error('后缀名不一致！', extra={'pos': pos})
        return
    if not {source_suffix, dest_suffix}.issubset({'.json', '.csv'}):
        logger.error('后缀名不支持！', extra={'pos': pos})
        return
    with open(file_source, 'r', encoding='utf-8-sig') as f:
        decoded_source = load(f) if source_suffix == '.json' else tuple(reader(f))
    with open(file_dest, 'r', encoding='utf-8-sig') as f:
        decoded_dest = load(f) if dest_suffix == '.json' else tuple(reader(f))
    excluded = r"\['armor_stand'\]" if source_suffix == '.json' else r'root\[\d+\]\[2\]'
    result = DeepDiff(
        decoded_source,
        decoded_dest,
        ignore_order=True,
        exclude_regex_paths=excluded,
        verbose_level=2,
    )
    print(result.pretty())


def sorting() -> None:
    pos: Final[str] = 'SORT'
    file = Path(argp().file)
    if not file.is_file():
        logger.error('文件不存在！', extra={'pos': pos})
        return
    if file.suffix.lower() != '.csv':
        logger.error('后缀名不支持！', extra={'pos': pos})
        return
    with open(file, 'r', encoding='utf-8-sig') as f:
        data = [(i[0], i[1], i[2]) for i in reader(f)]
    data.sort(key=lambda x: x[0])
    with open(file, 'w', encoding='utf-8-sig', newline='') as f:
        writing = writer(f)
        writing.writerows(data)
    logger.info('排序完成！', extra={'pos': pos})


def argp():
    par = ArgumentParser(description='密室杀手自定义头颅生成器')
    subpar = par.add_subparsers(dest='cmd')
    p_get = subpar.add_parser('get', help='提取头颅信息')
    p_get.add_argument('-a', '--armorstand', action='store_true', help='输出盔甲架数据')
    p_get.add_argument('-l', '--nodl', action='store_true', help='跳过皮肤文件下载')
    p_get.add_argument('-u', '--nourl', action='store_true', help='跳过 URL 记录')
    p_idt = subpar.add_parser('idt', help='获取 ID 对应的名称')
    p_idt.add_argument('-e', '--nocache', action='store_true', help='忽略缓存')
    p_imp = subpar.add_parser('imp', help='生成导入数据')
    p_imp.add_argument(
        '-b', '--nobp', action='store_true', help='跳过 BP 输出，即 blocks 和 items'
    )
    subpar.add_parser('revert', help='回退图片命名更改')
    p_diff = subpar.add_parser('diff', help='比较两个文件')
    p_diff.add_argument(
        'files', nargs=2, help='要比较的两个文件，支持 JSON 和 CSV 格式'
    )
    p_sort = subpar.add_parser('sort', help='排序文件')
    p_sort.add_argument('file', help='要排序的 CSV 文件')
    args = par.parse_args()
    return args


Path('output').mkdir(parents=True, exist_ok=True)
logger = getLogger(__name__)
logger.setLevel(DEBUG)
logger.handlers.clear()
form = Formatter('%(pos)s - %(levelname)s - %(message)s')
fil_h = FileHandler('output/debug.log', 'w', encoding='utf-8')
std_h = StreamHandler()
fil_h.setFormatter(form)
std_h.setFormatter(form)
fil_h.setLevel(WARNING)
logger.addHandler(fil_h)
logger.addHandler(std_h)
if __name__ == '__main__':
    try:
        match argp().cmd:
            case 'get':
                _ = Get()
            case 'idt':
                _ = Identify()
            case 'imp':
                _ = Import()
            case 'revert':
                _ = Rename(True)
            case 'diff':
                diff()
            case 'sort':
                sorting()
        print()
    except AssertionError:
        pass
    except Exception:
        logger.exception('未知错误。', extra={'pos': __name__})
    finally:
        _ = input('按回车退出...')
shutdown()
