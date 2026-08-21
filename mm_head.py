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

from deepdiff import DeepDiff
from PIL import Image
from requests import exceptions, get


class Get:
    POS = 'GET'

    def ext(self, data: str) -> dict:
        fac, rot, url = None, None, None
        trans = str.maketrans(' -', '__', '().#')
        mname = True
        ars = 'armor_stand' in data
        loc = search(r' ([\d\-. ]+) ', data).group(1)
        if '.' in loc:
            loc = [int(float(i)) for i in loc.split(' ')]
            loc[1] += 1
            loc = ' '.join(map(str, loc))
        if 'rotation' in data:
            rot = int(search(r'rotation=(\d+)', data).group(1))
        elif 'Rotation' in data:
            rot_map = [180]
            rot_map.extend(int(-157.5 + i * 22.5) for i in range(15))
            rot_ori = search(r'Rotation: ?\[([\d\-.]+)f', data).group(1)
            rot_ori = '180.0' if rot_ori == '-180.0' else rot_ori
            rot_closest = min(rot_map, key=lambda x: abs(int(float(rot_ori))-x))
            rot = rot_map.index(rot_closest)
        elif 'facing' in data:
            fac = search(r'facing=([^,\]]+)', data).group(1)
        if 'value:' in data:
            bsr = search(r'value: ?"([^\"]+)"', data).group(1)
            bsr += '=' * (-len(bsr) % 4)
            bsd = b64d(bsr).decode()
            url = loads(bsd)['textures']['SKIN']['url'].replace('http:', 'https:')
            name = search(r'(?:name|text): ?"([^"]*)"', data)
            if 'minecraft:custom_name' in data and 'text:' not in data:
                name = search(r'"minecraft:custom_name": ?"(?:§[a-z\d])?([^"]+)"', data)
            name = name.group(1).translate(trans).lower()
            if not name or name == 'textures':
                name = url[url.rfind('/')+1:url.rfind('/')+7]
                mname = False
        elif 'head:' in data:
            name = search(r'head: ?\{[^}]*id: ?"([^"]+)"\}', data).group(1) \
                .translate(trans).lower()
        else:
            print()
            lg.warning('无头颅数据。', extra={'pos': f'L{self.ln}'})
            return {}
        print(name, end=' - ', flush=True)
        return {
            'id': name,
            'location': loc,
            'rotation': rot,
            'facing': fac,
            'url': url,
            'meaningful': mname,
            'armor_stand': ars
        }

    def dls(self, url: str, name: str) -> bool:
        img_path = self.img_dir / f'{name}.png'
        if argp().nodl or not url or img_path.is_file():
            print('跳过下载...', end='', flush=True)
            if url and self.rect(img_path):
                print('成功！', flush=True)
            else:
                print()
            return False
        print('开始下载...', end='', flush=True)
        for i in range(3):
            try:
                img = get(url, timeout=(6.05, 10))
                break
            except exceptions.Timeout:
                print(f'超时（{i+1}/3）...', end='', flush=True)
                sleep(1)
            except exceptions.ConnectionError:
                print(f'连接错误（{i+1}/3）...', end='', flush=True)
                sleep(1)
        else:
            print()
            lg.error('已超时。', extra={'pos': f'L{self.ln} - {name}'})
            return False
        with open(img_path, 'wb') as png:
            png.write(img.content)
        self.rect(img_path)
        print('成功！', flush=True)
        return True

    def rect(self, img_path) -> bool:
        temp_path = img_path.with_name(img_path.name + '.tmp')
        with Image.open(img_path) as img:
            if img.size != (64, 32):
                return False
            print('转换中...', end='', flush=True)
            img = img.convert('RGBA')
            if 'thegreatergod' in str(img_path):
                print('thelesserdog...', end='', flush=True)
                pix = img.load()
                for w in range(31, 64):
                    for h in range(16):
                        if pix[w, h] == (255, 255, 255, 255):
                            pix[w, h] = (0, 0, 0, 0)
            new_img = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
            new_img.paste(img, (0, 0), img)
            new_img.save(temp_path, format='PNG')
        temp_path.replace(img_path)
        return True

    def merge(self, dt1: dict, dt2: dict, stem: str) -> dict:
        if not dt2:
            return dt1
        name, url = dt2['id'], dt2['url']
        self.dls(url, name)
        if dt1.get(stem):
            dt3 = {i['location']: i['id'] for i in dt1[stem]}
            if not (idn := dt3.get(dt2['location'])):
                dt1[stem].append(dt2)
            else:
                lg.warning(
                    '位置 %s 已存在头颅 %s。',
                    dt2["location"], idn,
                    extra={'pos': f'L{self.ln} - {name}'}
                )
        else:
            dt1[stem] = [dt2]
        if self.n_lt.get(name, [url])[0] != url:
            old = name
            i = 0
            while self.n_lt.get(name, [url])[0] != url:
                i += 1
                name = f'{name}_{i}' if i == 1 else f'{name[:name.rfind('_')]}_{i}'
            dt2['id'] = name
            lg.warning(
                '对应多重 URL，已将新的更名为 %s。',
                name,
                extra={'pos': f'L{self.ln} - {old}'}
            )
            print(f'L{self.ln} - {name} - ', end='', flush=True)
            self.dls(url, name)
        if url:
            self.n_lt[name] = (url, dt2['meaningful'])
        return dt1

    def prune(self, dt: dict) -> tuple:
        dtn = {}
        url = []
        for i, j in dt.items():
            dtn[i] = []
            if not argp().nourl:
                url = [
                    {f'url:{k["url"].replace(
                        "https://textures.minecraft.net/texture/", ""
                    )}': k['id']} for k in j if k['url']
                ]
            for k in j:
                k.pop('url')
                k.pop('meaningful')
                if not argp().armorstand or True:
                    k.pop('armor_stand')
                l = [m for m, n in k.items() if not n and n != 0]
                for m in l:
                    k.pop(m)
                dtn[i].append(k)
        return dtn, url

    def pro(self, stem: str, data: list) -> dict:
        dt = {}
        linum = len(str(len(data)))
        for i, j in enumerate(data):
            self.ln = str(i + 1).zfill(linum)
            if not j.strip():
                continue
            if not argp().armorstand and 'armor_stand' in j:
                lg.info('盔甲架输出已关闭。', extra={'pos': f'L{self.ln}'})
                continue
            try:
                print(f'L{self.ln}', end=' - ', flush=True)
                dt_pending = self.ext(j)
                dt = self.merge(dt, dt_pending, stem)
            except Exception:
                print()
                lg.exception('未知错误。', extra={'pos': f'L{self.ln}'})
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
                data = data.replace(f'"{name}"',f'"{nurl}"')
                lg.warning(
                    'URL 对应多重名称，已将新的统一为 %s。',
                    nurl,
                    extra={'pos': f'{name}'}
                )
                (self.img_dir / f'{name}.png').replace(self.img_dir / f'{nurl}.png')
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
            lg.info('跳过下载已开启。', extra={'pos': self.POS})
        else:
            self.img_dir.mkdir(parents=True, exist_ok=True)
        if argp().nourl:
            lg.info('跳过 URL 记录已开启。', extra={'pos': self.POS})
        for f in Path('raw').glob('*.txt'):
            stem = f.stem
            with open(f, 'r', encoding='utf-8') as rd:
                data = rd.read().splitlines()
            lg.info('%s - L%s',
                stem, len(data),
                extra={'pos': self.POS}
            )
            dtn, url = self.prune(self.pro(stem, data))
            dt |= dtn
            if url:
                urls.extend(url)
        if not f:
            lg.warning('未在 raw 目录内找到 txt 后缀的批处理文件。', extra={'pos': self.POS})
            data = [input('输入待处理项：')]
            dt, url = self.prune(self.pro('info', data))
            if url:
                urls.extend(url)
        self.out(dt, urls)
        lg.info('信息提取完成！', extra={'pos': self.POS})

class Identify:
    POS = 'IDT'

    def ext(self, url: str, msg: str) -> str:
        sleep(0.2)
        for i in range(3):
            try:
                res = get(
                    'https://minecraft-heads.com/custom-heads/search',
                    params={'searchterm': url},
                    timeout=(6.05, 10)
                )
                break
            except exceptions.Timeout:
                print(f'超时（{i+1}/3）...', end='', flush=True)
                sleep(1)
            except exceptions.ConnectionError:
                print(f'连接错误（{i+1}/3）...', end='', flush=True)
                sleep(1)
        else:
            print()
            lg.error('已超时。', extra={'pos': msg})
            return ''
        data = res.text
        if 'No Heads available' in data:
            return ''
        con = data[data.find('descending'):data.find('Search Tips')]
        return search(r'a href=.+title="([^"]+)"', con).group(1)

    def cache(self) -> dict:
        if argp().nocache:
            lg.info('缓存已忽略！', extra={'pos': self.POS})
            return {}
        if not Path('output/cache.json').is_file():
            return {}
        with open('output/cache.json', 'r', encoding='utf-8') as rd:
            lg.info('缓存已加载！', extra={'pos': self.POS})
            return load(rd)

    def dout(self) -> None:
        lt = [[i['old'], i['new']] for i in self.dt]
        with open('output/name.csv', 'w', encoding='utf-8', newline='') as wt:
            wt_op = writer(wt)
            wt_op.writerows(lt)

    def pro(self, data: dict, ln: str) -> None:
        n, m = next(iter(data.items()))
        msg = f'L{ln} - {m}'
        print(msg, end=' - ', flush=True)
        if (k := self.c_lt.get(m)) or k == '':
            j = k
            print('（缓存）', end='', flush=True)
        else:
            j = self.ext(n, msg)
            self.c_lt[m] = j
        if j:
            j = sub(r'&(#[\d]+|#x[\da-fA-F]+|[a-zA-Z]+);', '', j)
            j = j.translate(str.maketrans(' -', '__', '().#')).lower() + '_' + n[4:6]
            print(j, flush=True)
            if l := self.n_lt.get(j):
                self.dup[j] = self.dup.get(j, 0) + 1
                k = j
                j += f'_{self.dup[j]}'
                lg.warning('与 %s 拥有共同的新名称，已更名为 %s。', l, j, extra={'pos': msg})
            self.n_lt[j] = m
        else:
            print(m, flush=True)
            j = m
            lg.warning('无可用名称。', extra={'pos': msg})
        self.dt.append({'old': m, 'new': j})

    def __init__(self) -> None:
        self.c_lt = self.cache()
        self.dt = []
        self.dup = {}
        self.n_lt = {}
        try:
            path = 'output/url.json'
            if Path(path).is_file():
                with open(path, 'r', encoding='utf-8') as rd:
                    data = load(rd)
                lg.info('%s - L%s', path, len(data), extra={'pos': self.POS})
                linum = len(str(len(data)))
                for i, j in enumerate(data):
                    self.pro(j, str(i+1).zfill(linum))
                self.dout()
            else:
                lg.error('%s 不存在！', path, extra={'pos': self.POS})
            lg.info('名称对照完成！', extra={'pos': self.POS})
        finally:
            with open('output/cache.json', 'w', encoding='utf-8') as wt:
                dump(self.c_lt, wt, indent=4)
                lg.info('缓存已输出！', extra={'pos': self.POS})

class Import:
    POS = 'IMP'

    def blotem(self, idn: str, templ: str) -> bool:
        if not Path(templ).is_file():
            return False
        with open(templ, 'r', encoding='utf-8') as rd:
            tem = rd.read()
        flag = templ[templ.rfind('.', 0, -7)+1:templ.rfind('.')]
        wt_path = f'output/BP/{flag}s/{idn}.{flag}.json'
        uni = tem.replace('yzbwdlt', idn)
        if flag == 'block' and idn in {'swamp_monster', 'diamivore_3d'}:
            uni = uni.replace('popped', 'no_reaction')
        self.wt_op(wt_path, uni)
        return True

    def terlang(self, idn_lt: tuple) -> None:
        fb = True
        if Path('templates/playerheads.csv').is_file():
            fb = False
            with open('templates/playerheads.csv', 'r', encoding='utf-8-sig') as rd:
                rd_op = reader(rd)
                data = {i[1]: i[2] for i in rd_op}
        else:
            lg.warning('未找到译名文件，使用备用方案！', extra={'pos': self.POS})
        ter = '\n'.join(
            f'        "player_head_{i[0]}": {{ "textures": "textures/entity/{i[0]}" }},'
            for i in idn_lt
        )
        zhl = '\n'.join(
            f'tile.player_head:{i[0]}.name={i[1].title()} 的头'
            for i in idn_lt
        ) if fb else '\n'.join(
            f'tile.player_head:{i[0]}.name={
                data.get(i[0], i[0])[:data.get(i[0], i[0]).rfind('_')].title()
                if '_' in {data.get(i[0], i[0])[-3], data.get(i[0], i[0])[-2]}
                else data.get(i[0], i[1]).title()
            } 的头'
            for i in idn_lt
        )
        enl = '\n'.join(
            f"tile.player_head:{i[0]}.name={i[1].title()}'s Head"
            for i in idn_lt
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
        self.wt_op('output/RP/textures/terrain_texture.json', ter_full)
        self.wt_op('output/RP/texts/en_US.lang', enl_full)
        self.wt_op('output/RP/texts/zh_CN.lang', zhl_full)

    def gen(self) -> None:
        block_tem = 'templates/yzbwdlt.block.json'
        item_tem = 'templates/yzbwdlt.item.json'
        img_dir = Path('output/RP/textures/entity')
        block_info, item_info = True, True
        stems = tuple(i.stem for i in img_dir.glob('*.png'))
        if not stems:
            lg.error('无 png 文件！', extra={'pos': self.POS})
            return
        stems = tuple(
            (i, (i[:i.rfind('_')] if '_' in {i[-3], i[-2]} else i))
            for i in stems
        )
        self.terlang(stems)
        if argp().demo:
            lg.info('演示模式，跳过 blotem 生成！', extra={'pos': self.POS})
        for i, _ in stems:
            if not self.blotem(i, block_tem) and block_info:
                lg.error(
                    '未找到模板 %s，跳过 block 生成！',
                    block_tem,
                    extra={'pos': self.POS}
                )
                block_info = False
            if not self.blotem(i, item_tem) and item_info:
                lg.error(
                    '未找到模板 %s，跳过 item 生成！',
                    item_tem,
                    extra={'pos': self.POS}
                )
                item_info = False
        lg.info('导入数据生成完成！', extra={'pos': self.POS})

    @staticmethod
    def wt_op(path: str, con: str) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as wt:
            wt.write(con)

    def __init__(self) -> None:
        Rename()
        self.gen()

class Rename:
    def read_operator(self, path) -> dict:
        with open(path, 'r', encoding='utf-8-sig') as f:
            reading = reader(f)
            names = {
                ((i[1] or i[0]) if self.revert_mode else i[0]):
                ((i[0] if self.revert_mode else (i[1] or i[0])), path.stem)
                for i in reading
            }
        names.pop('Column1', None)
        names.pop('Column2', None)
        lg.info('工作在 %s 模式下。', path.stem, extra={'pos': self.pos})
        return names

    def read_names(self) -> dict:
        playerheads_csv = Path('templates/playerheads.csv')
        name_csv = Path('output/name.csv')
        name_list = {}
        if name_csv.is_file():
            name_list.update(self.read_operator(name_csv))
        if playerheads_csv.is_file():
            name_list.update(self.read_operator(playerheads_csv))
        return name_list

    def rename_operator(self, old_stem: str, new_stem: str, info_data: str) -> str:
        old_path = self.img_dir / f'{old_stem}.png'
        new_path = self.img_dir / f'{new_stem}.png'
        lg.info('重命名为 %s。', new_stem, extra={'pos': old_stem})
        if new_path.is_file():
            lg.warning('新文件 %s 存在，已覆盖。', new_stem, extra={'pos': old_stem})
        old_path.replace(new_path)
        return info_data.replace(f'"{old_stem}"', f'"{new_stem}"')

    def __init__(self, revert_mode: bool=False) -> None:
        self.pos = 'REVERT' if revert_mode else 'RENAME'
        self.revert_mode = revert_mode
        self.img_dir = Path('output/RP/textures/entity')
        info_json = Path('output/info.json')
        if not (names := self.read_names()):
            lg.error('未找到名称文件，跳过重命名！', extra={'pos': self.pos})
            return
        if info_json.is_file():
            with open(info_json, 'r', encoding='utf-8') as f:
                info_data = f.read()
        else:
            lg.warning('未找到信息文件，跳过该文件！', extra={'pos': self.pos})
            info_data = ''
        stems = tuple(i.stem for i in self.img_dir.glob('*.png'))
        for stem in stems:
            if stem in names:
                new_stem, work_mode = names.pop(stem)
                if new_stem != stem:
                    info_data = self.rename_operator(stem, new_stem, info_data)
                if work_mode == 'name' and Path('templates/playerheads.csv').is_file():
                    lg.warning('未在 playerheads 中找到对应的条目，新名称 %s。', new_stem, extra={'pos': stem})
            elif stem.isdecimal():
                new_stem = stem[:-1] + 'r'
                lg.warning('非法 ID，已更名为 %s。', new_stem, extra={'pos': stem})
                info_data = self.rename_operator(stem, new_stem, info_data)
            else:
                lg.warning('未在名称文件中找到对应的条目。', extra={'pos': stem})
        if names:
            unused = '、'.join(names.keys())
            lg.warning('未使用的条目：%s。', unused, extra={'pos': self.pos})
        if info_json.is_file():
            with open(info_json, 'w', encoding='utf-8') as f:
                f.write(info_data)
        lg.info('重命名完成！', extra={'pos': self.pos})

def diff() -> None:
    pos = 'DIFF'
    file_source, file_dest = map(Path, argp().compare)
    if not file_source.is_file():
        lg.error('%s 文件不存在！', str(file_source), extra={'pos': pos})
        return
    if not file_dest.is_file():
        lg.error('%s 文件不存在！', str(file_dest), extra={'pos': pos})
        return
    source_suffix = file_source.suffix.lower()
    dest_suffix = file_dest.suffix.lower()
    if source_suffix != dest_suffix:
        lg.error('后缀名不一致！', extra={'pos': pos})
        return
    if not {source_suffix, dest_suffix}.issubset({'.json', '.csv'}):
        lg.error('后缀名不支持！', extra={'pos': pos})
        return
    with open(file_source, 'r', encoding='utf-8-sig') as f:
        decoded_source = load(f) if source_suffix == '.json' else tuple(reader(f))
    with open(file_dest, 'r', encoding='utf-8-sig') as f:
        decoded_dest = load(f) if dest_suffix == '.json' else tuple(reader(f))
    excluded = r"\['armor_stand'\]" if source_suffix == '.json' \
        else r"root\[\d+\]\[2\]"
    result = DeepDiff(
        decoded_source,
        decoded_dest,
        ignore_order = True,
        exclude_regex_paths = excluded,
        verbose_level = 2
    )
    print(result.pretty())

def argp():
    par = ArgumentParser(description='密室杀手自定义头颅生成器')
    par.add_argument(
        '-m', '--mode',
        nargs='+',
        default=['get'],
        help='运行模式，get、idt、imp、all，可多选，默认 get；all = get idt imp'
    )
    par.add_argument(
        '-c', '--compare',
        nargs=2,
        help='比较给出的两个文件，目前支持 JSON 和 CSV 格式，忽略其他操作'
    )
    par.add_argument('-r', '--revert', action='store_true', help='回退图片命名更改，忽略其他操作')
    par.add_argument('-d', '--demo', action='store_true', help='演示模式，不输出 blocks 和 items')
    par.add_argument('-l', '--nodl', action='store_true', help='跳过下载')
    par.add_argument('-u', '--nourl', action='store_true', help='跳过 URL 记录')
    par.add_argument('-e', '--nocache', action='store_true', help='忽略缓存')
    par.add_argument('-a', '--armorstand', action='store_true', help='输出盔甲架数据')
    args = par.parse_args()
    if 'all' in args.mode:
        args.mode = ['get', 'idt', 'imp']
    if args.revert or args.compare:
        args.mode = []
    return args

Path('output').mkdir(parents=True, exist_ok=True)
lg = getLogger(__name__)
lg.setLevel(DEBUG)
lg.handlers.clear()
form = Formatter('%(pos)s - %(levelname)s - %(message)s')
fil_h = FileHandler('output/debug.log', 'w', encoding='utf-8')
std_h = StreamHandler()
fil_h.setFormatter(form)
std_h.setFormatter(form)
fil_h.setLevel(WARNING)
lg.addHandler(fil_h)
lg.addHandler(std_h)
if __name__ == '__main__':
    try:
        if 'get' in argp().mode:
            Get()
            print()
        if 'idt' in argp().mode:
            Identify()
            print()
        if 'imp' in argp().mode:
            Import()
            print()
        if argp().revert and not argp().compare:
            Rename(True)
            print()
        if argp().compare and not argp().revert:
            diff()
            print()
    except Exception:
        lg.exception('未知错误。', extra={'pos': __name__})
    finally:
        _ = input('按回车退出...')
shutdown()
