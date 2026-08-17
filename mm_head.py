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

from PIL import Image
from requests import exceptions, get


class Get:
    POS = 'GET'

    def ext(self, data: str) -> dict:
        fac, rot, url = None, None, None
        trans = str.maketrans(' -', '__', '()')
        mname = True
        loc = search(r' ([\d\-. ]+) ', data).group(1)
        if 'rotation' in data:
            rot = int(search(r'rotation=(\d+)', data).group(1))
        elif 'facing' in data:
            fac = search(r'facing=([^,\]]+)', data).group(1)
        if 'value:' in data:
            bsr = search(r'value: ?"([^\"]+)"', data).group(1)
            bsr += '=' * (-len(bsr) % 4)
            bsd = b64d(bsr).decode()
            url = loads(bsd)['textures']['SKIN']['url'].replace('http:', 'https:')
            name = search(r'(?:name|text): ?"([^"]*)"', data).group(1) \
                .translate(trans).lower()
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
        _ = '''
        if name.isdecimal():
            lg.warning('非法 ID，已更名为 %s。', name[:-1] + 'r', extra={'pos': f'L{self.ln} - {name}'})
            name = name[:-1] + 'r'
        '''
        print(name, end=' - ', flush=True)
        return {
            'id': name,
            'location': loc,
            'rotation': rot,
            'facing': fac,
            'url': url,
            'meaningful': mname
        }

    def dls(self, url: str, name: str) -> bool:
        img_path = self.img_dir / f'{name}.png'
        if argp().nodl or not url or img_path.is_file():
            print('跳过下载...', end='', flush=True)
            if self.rect(img_path):
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
        self.n_lt[name] = (url, dt2['meaningful'])
        return dt1

    def prune(self, dt: dict) -> dict:
        dtn = {}
        url = []
        for i, j in dt.items():
            dtn[i] = []
            if not argp().nourl:
                url = [{f'url:{k["url"].replace(
                    "https://textures.minecraft.net/texture/", ""
                    )}': k['id']} for k in j if k['url']
                ]
            for k in j:
                k.pop('url')
                k.pop('meaningful')
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
                lg.warning('盔甲架输出已关闭。', extra={'pos': f'L{self.ln}'})
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

    def out(self, dt: dict, urls: dict) -> None:
        data = dumps(dt, indent=4)
        u_lt = tuple((i, j, k) for i, (j, k) in self.n_lt.items())
        names = {}
        for name, url, mname in u_lt:
            if mname:
                names[url] = name
        for name, url, mname in u_lt:
            if (nurl := names.get(url)) and name != nurl:
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
            urlsn = []
            for i in urls:
                j = tuple(sorted(i.items()))
                if j not in past:
                    past.add(j)
                    urlsn.append(i)
            with open('output/url.json', 'w', encoding='utf-8') as wt:
                dump(urlsn, wt, indent=4)

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
            dt = self.prune(self.pro('info', data))
        self.out(dt, urls)
        lg.info('信息提取完成！', extra={'pos': self.POS})

class Idt:
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
            j = j.translate(str.maketrans(' -', '__', '()')).lower() + '_' + n[4:6]
            j = sub(r'&(#[\d]+|#x[\da-fA-F]+|[a-zA-Z]+);', '', j)
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

class Imp:
    POS = 'IMP'

    def blotem(self, idn: str, templ: str) -> bool:
        if not Path(templ).is_file():
            return False
        with open(templ, 'r', encoding='utf-8') as rd:
            tem = rd.read()
        uni = tem.replace('yzbwdlt', idn)
        flag = templ[templ.rfind('.', 0, -7)+1:templ.rfind('.')]
        wt_path = f'output/BP/{flag}s/{idn}.{flag}.json'
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
            f'tile.player_head:{i[0]}.name={
                i[1][:-2].title()
                if '_' == i[1][-2]
                else i[1].title()
            } 的头'
            for i in idn_lt
        ) if fb else '\n'.join(
            f'tile.player_head:{i[0]}.name={
                data.get(i[0], i[1])[:-2].title()
                if '_' == data.get(i[0], i[1])[-2]
                else data.get(i[0], i[1]).title()
            } 的头'
            for i in idn_lt
        )
        enl = '\n'.join(
            f"tile.player_head:{i[0]}.name={
                i[1][:-2].title()
                if '_' == i[1][-2]
                else i[1].title()
            }'s Head"
            for i in idn_lt
        )
        ter_full = (
            '{\n'
            '    "resource_pack_name": "player_head",\n'
            '    "texture_data": {\n'
            f'{ter}\n\n'
            '        "player_head_yzbwdlt": { "textures": "textures/entity/yzbwdlt" },\n'
            '        "player_head_violetmiaw": { "textures": "textures/entity/violetmiaw" },\n'
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
            'tile.player_head:violetmiaw.name=VioletMiaw 的头\n'
        )
        enl_full = (
            '## ===== Blocks =====\n'
            f'{enl}\n\n'
            "tile.player_head:yzbwdlt.name=YZBWDLT's Head\n"
            "tile.player_head:freamoluwu.name=Freamoluwu's Head\n"
            "tile.player_head:jhy2189.name=JHY2189's Head\n"
            "tile.player_head:violetmiaw.name=VioletMiaw's Head\n"
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
        stems = tuple((i, (i[:-3] if i[-3] == '_' else i)) for i in stems)
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
    def rename(re: bool=False) -> None:
        pos = 'REVERT' if re else 'RENAME'
        img_dir = Path('output/RP/textures/entity')
        if Path('templates/playerheads.csv').is_file():
            with open('templates/playerheads.csv', 'r', encoding='utf-8') as rd:
                rd_op = reader(rd)
                name = tuple(rd_op)
                linum = len(str(len(name)))
            lg.info('工作在 playerheads 模式下。', extra={'pos': pos})
        elif Path('output/name.csv').is_file():
            with open('output/name.csv', 'r', encoding='utf-8') as rd:
                rd_op = reader(rd)
                name = tuple(rd_op)
                linum = len(str(len(name)))
            lg.info('工作在 name 模式下。', extra={'pos': pos})
        else:
            lg.error('未找到名称文件，跳过重命名！', extra={'pos': pos})
            return
        if Path('output/info.json').is_file():
            with open('output/info.json', 'r', encoding='utf-8') as rd:
                info = rd.read()
        else:
            lg.warning('未找到信息文件，跳过该文件重命名！', extra={'pos': pos})
            info = ''
        for i, j in enumerate(name):
            old = j[0]
            new = j[1] if j[1] else old
            msg = f'L{str(i+1).zfill(linum)} - {old}'
            if old != new:
                if re:
                    msg = msg.replace(old, new)
                    old, new = new, old
                old_path = img_dir / f'{old}.png'
                new_path = img_dir / f'{new}.png'
                if new_path.is_file():
                    lg.warning('新文件 %s 存在，已覆盖。', new, extra={'pos': msg})
                if old_path.is_file():
                    old_path.replace(new_path)
                else:
                    lg.warning('文件不存在，已跳过。', extra={'pos': msg})
                info = info.replace(old, new)
            else:
                lg.warning('两名称相同，已跳过。', extra={'pos': msg})
        if Path('output/info.json').is_file():
            with open('output/info.json', 'w', encoding='utf-8') as wt:
                wt.write(info)
        lg.info('重命名完成！', extra={'pos': pos})

    @staticmethod
    def wt_op(path: str, con: str) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as wt:
            wt.write(con)

    def __init__(self) -> None:
        self.rename()
        self.gen()

def argp():
    par = ArgumentParser(description='密室杀手自定义头颅生成器')
    par.add_argument(
        '-m', '--mode',
        nargs='+',
        default=['get'],
        help='运行模式，get、idt、imp、all，可多选，默认 get；all = get idt imp'
    )
    par.add_argument('-r', '--revert', action='store_true', help='回退图片命名更改，忽略其他操作')
    par.add_argument('-d', '--demo', action='store_true', help='演示模式，不输出 blocks 和 items')
    par.add_argument('-l', '--nodl', action='store_true', help='跳过下载')
    par.add_argument('-u', '--nourl', action='store_true', help='跳过 URL 记录')
    par.add_argument('-c', '--nocache', action='store_true', help='忽略缓存')
    par.add_argument('-a', '--armorstand', action='store_true', help='输出盔甲架数据')
    args = par.parse_args()
    if 'all' in args.mode:
        args.mode = ['get', 'idt', 'imp']
    if args.revert:
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
            Idt()
            print()
        if 'imp' in argp().mode:
            Imp()
            print()
        if argp().revert:
            Imp.rename(True)
            print()
    except Exception:
        lg.exception('未知错误。', extra={'pos': __name__})
    finally:
        _ = input('按回车退出...')
shutdown()
