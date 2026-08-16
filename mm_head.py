from argparse import ArgumentParser
from base64 import urlsafe_b64decode as b64d
from csv import DictReader, DictWriter
from json import dump, load, loads
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

from requests import exceptions, get


class Get:
    POS = 'GET'

    def ext(self, data: str) -> dict:
        fac, rot, url = None, None, None
        trans = str.maketrans(' ', '_', '()')
        loc = search(r' ([\d\-. ]+) ', data).group(1)
        if 'rotation' in data:
            rot = search(r'rotation=(\d+)', data).group(1)
        elif 'facing' in data:
            fac = search(r'facing=([^,\]]+)', data).group(1)
        if 'value' in data:
            bsr = search(r'value: ?"([^\"]+)"', data).group(1)
            bsr += '=' * (-len(bsr) % 4)
            bsd = b64d(bsr).decode()
            url = loads(bsd)['textures']['SKIN']['url'].replace('http:', 'https:')
            name = search(r'(?:name|text): ?"([^"]*)"', data).group(1) \
                .translate(trans).lower()
            if not name or name in {'textures', 'plummel'}:
                name = url[url.rfind('/')+1:url.rfind('/')+7]
        elif 'head' in data:
            name = search(r'head: ?\{[^}]*id: ?"([^"]+)"\}', data).group(1) \
                .translate(trans).lower()
        else:
            print()
            lg.warning('无头颅数据。', extra={'pos': f'L{self.ln}'})
            return {}
        print(name, end='：', flush=True)
        return {
            'id': name,
            'location': loc,
            'rotation': rot,
            'facing': fac,
            'url': url
        }

    def dls(self, url: str, name: str) -> bool:
        print('开始下载...', end='', flush=True)
        for i in range(3):
            try:
                img = get(url, timeout=(6.05, 10))
                break
            except exceptions.Timeout:
                print(f'超时（{i+1}/3）...', end='', flush=True)
                sleep(1)
        else:
            print()
            lg.error('已超时。', extra={'pos': f'L{self.ln} - {name}'})
            return False
        with open(f'assets/{name}.png', 'wb') as png:
            png.write(img.content)
        print('成功！', flush=True)
        return True

    def merge(self, dt1: dict, dt2: dict, stem: str) -> dict:
        if not dt2:
            return dt1
        name, url = dt2['id'], dt2['url']
        if not argp().nodl and url and \
            not Path(f'assets/{name}.png').is_file():
            self.dls(url, name)
        else:
            print('跳过下载...', flush=True)
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
        if self.n_lt.get(name, url) != url:
            self.dup[name] = self.dup.get(name, 0) + 1
            i = name
            dt2['id'] += f'_{self.dup[name]}'
            name = dt2['id']
            lg.warning(
                '头颅 %s 对应多重 URL，已将新的更名为 %s。',
                i, name,
                extra={'pos': f'L{self.ln} - {i}'}
            )
            print(f'L{self.ln} - {name}：', end='', flush=True)
            if not argp().nodl and url and \
                not Path(f'assets/{name}.png').is_file():
                self.dls(url, name)
            else:
                print('跳过下载...', flush=True)
        self.n_lt[name] = url
        return dt1

    def prune(self, dt: dict) -> dict:
        dtn = {}
        for i, j in dt.items():
            dtn[i] = []
            if not argp().nourl:
                url = [{f'url:{k["url"].replace(
                    "https://textures.minecraft.net/texture/", ""
                    )}': k['id']} for k in j if k['url']
                ]
                self.urls.extend(url)
            for k in j:
                k.pop('url')
                l = [m for m, n in k.items() if not n]
                for m in l:
                    k.pop(m)
                dtn[i].append(k)
        return dtn

    def pro(self, stem: str, data: list) -> dict:
        dt = {}
        for i, j in enumerate(data):
            self.ln = i + 1
            if not j.strip():
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

    def __init__(self) -> None:
        self.dup = {}
        self.n_lt = {}
        dt = {}
        f = None
        if argp().nodl:
            lg.info('跳过下载已开启。', extra={'pos': self.POS})
        else:
            Path('assets').mkdir(parents=True, exist_ok=True)
        if argp().nourl:
            lg.info('跳过 URL 记录已开启。', extra={'pos': self.POS})
        else:
            self.urls = []
        for f in Path('./raw').glob('*.txt'):
            stem = f.stem
            if stem == 'terlang':
                continue
            with open(f, 'r', encoding='utf-8') as rd:
                data = rd.read().splitlines()
            lg.info('%s - L%s',
                stem, len(data),
                extra={'pos': self.POS}
            )
            dt |= self.prune(self.pro(stem, data))
        if not f:
            lg.warning('未在 raw 目录内找到 txt 后缀的批处理文件。', extra={'pos': self.POS})
            data = [input('输入待处理项：')]
            dt = self.pro('info', data)
        with open('output/info.json', 'w', encoding='utf-8') as wt:
            dump(dt, wt)
        if not argp().nourl:
            past = set()
            urls = []
            for i in self.urls:
                j = tuple(sorted(i.items()))
                if j not in past:
                    past.add(j)
                    urls.append(i)
            urls = {'data': urls}
            with open('output/url.json', 'w', encoding='utf-8') as wt:
                dump(urls, wt)
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
        else:
            print()
            lg.error('已超时。', extra={'pos': f'{msg}'})
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
        with open('output/name.csv', 'w', encoding='utf-8', newline='') as wt:
            headers = list(self.dt[0])
            wt_op = DictWriter(wt, fieldnames=headers)
            wt_op.writeheader()
            wt_op.writerows(self.dt)

    def pro(self, data: dict, ln: int) -> None:
        n, m = next(iter(data.items()))
        msg = f'L{ln} - {m}'
        print(msg, end='：', flush=True)
        if (k := self.c_lt.get(m)) or k == '':
            j = k
            print('（缓存）', end='', flush=True)
        else:
            j = self.ext(n, msg)
            self.c_lt[m] = j
        if j:
            j = j.translate(str.maketrans(' ', '_', '()')).lower() + '_' + n[4:6]
            j = sub(r'&(#[\d]+|#x[\da-fA-F]+|[a-zA-Z]+);', '', j)
            print(j, flush=True)
            if l := self.n_lt.get(j):
                self.dup[j] = self.dup.get(j, 0) + 1
                k = j
                j += f'_{self.dup[j]}'
                lg.warning('与 %s 拥有共同的新名称，已更名为 %s。', l, j, extra={'pos': msg})
            self.n_lt[j] = m
        else:
            print('None', flush=True)
            j = None
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
                    data = load(rd)['data']
                lg.info('%s - L%s', path, len(data), extra={'pos': self.POS})
                for i, j in enumerate(data):
                    self.pro(j, i+1)
                self.dout()
            else:
                lg.error('%s 不存在！', path, extra={'pos': self.POS})
            lg.info('名称对照完成！', extra={'pos': self.POS})
        finally:
            with open('output/cache.json', 'w', encoding='utf-8') as wt:
                dump(self.c_lt, wt)
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
        wt_path = f'output/{flag}s/{idn}.{flag}.json'
        self.wt_op(wt_path, uni)
        return True

    def terlang(self, idn_lt: tuple) -> None:
        ter = '\n'.join(
            f'"player_head_{i}": {{ "textures": "textures/entity/{i}" }},' \
            for i in idn_lt
        )
        zhl = '\n'.join(
            f'tile.player_head:{i}.name={i} 的头' \
            for i in idn_lt
        )
        enl = '\n'.join(
            f"tile.player_head:{i}.name={i}'s Head" \
            for i in idn_lt
        )
        final = (
            '// ===== terrain_texture.json =====\n' + ter +
            '\n\n// ===== zh_CN.lang =====\n' + zhl +
            '\n\n// ===== en_US.lang =====\n' + enl + '\n'
        )
        self.wt_op('output/terlang.txt', final)

    def gen(self) -> None:
        block_tem = 'templates/yzbwdlt.block.json'
        item_tem = 'templates/yzbwdlt.item.json'
        block_info, item_info = True, True
        stems = tuple(i.stem for i in Path('./assets').glob('*.png'))
        if not stems:
            lg.error('无 png 文件！', extra={'pos': self.POS})
            return
        self.terlang(stems)
        for i in stems:
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

    def rename(self) -> None:
        with open('output/info.json', 'r', encoding='utf-8') as rd:
            data = rd.read()
        with open('output/name.csv', 'r', encoding='utf-8') as rd:
            rd_op = DictReader(rd)
            for i, j in enumerate(rd_op):
                old = j['old']
                new = j['new']
                ln = f'L{i+1}'
                if new:
                    if Path(f'assets/{old}.png').is_file():
                        Path(f'assets/{old}.png').rename(f'assets/{new}.png')
                    else:
                        lg.warning('%s 文件不存在，已跳过。', old, extra={'pos': ln})
                    data = data.replace(old, new)
                else:
                    lg.warning('%s 新名称为空，已跳过。', old, extra={'pos': ln})
        with open('output/info.json', 'w', encoding='utf-8') as wt:
            wt.write(data)
        lg.info('重命名完成！', extra={'pos': self.POS})

    def wt_op(self, path: str, con: str) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as wt:
            wt.write(con)

    def __init__(self) -> None:
        if not Path('output/name.csv').is_file():
            lg.error('未找到名称文件，跳过重命名！', extra={'pos': self.POS})
        elif not Path('output/info.json').is_file():
            lg.error('未找到信息文件，跳过重命名！', extra={'pos': self.POS})
        else:
            self.rename()
        self.gen()

def argp():
    par = ArgumentParser(description='密室杀手自定义头颅生成器')
    par.add_argument(
        '-m', '--mode',
        nargs='+',
        default=['get'],
        help='运行模式，可多选，包括 get、idt、imp，默认 get'
    )
    par.add_argument('-d', '--nodl', action='store_true', help='跳过下载')
    par.add_argument('-u', '--nourl', action='store_true', help='跳过 URL 记录')
    par.add_argument('-c', '--nocache', action='store_true', help='忽略缓存')
    # return par.parse_args(['-m', 'imp'])
    return par.parse_args()

Path('./output').mkdir(parents=True, exist_ok=True)
lg = getLogger(__name__)
lg.setLevel(DEBUG)
lg.handlers.clear()
form = Formatter('%(pos)s：%(levelname)s - %(message)s')
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
    except Exception:
        lg.exception('未知错误。', extra={'pos': __name__})
    finally:
        _ = input('按回车退出...')
shutdown()
