from argparse import ArgumentParser
from base64 import urlsafe_b64decode as b64d
from csv import DictWriter
from json import dump, load, loads
from logging import DEBUG, FileHandler, Formatter, StreamHandler, getLogger, shutdown
from pathlib import Path
from re import search
from time import sleep

from requests import exceptions, get


class Get:
    def ext(self, data: str) -> dict:
        fac, rot, url = None, None, None
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
            name = search(r'(?:name|text): ?"([^"]*)"', data).group(1)
            if not name or name in {'textures', 'Plummel'}:
                name = url[url.rfind('/')+1:url.rfind('/')+7]
        elif 'head' in data:
            name = search(r'head: ?\{[^}]*id: ?"([^"]+)"\}', data).group(1)
        else:
            print()
            lg.warning('无头颅数据。', extra={'pos': f'L{self.ln}'})
            return {}
        print(name, end='，', flush=True)
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
            lg.error('已超时。', extra={'pos': f'L{self.ln}'})
            return False
        with open(f'{name}.png', 'wb') as png:
            png.write(img.content)
        print('成功！', flush=True)
        return True

    def merge(self, dt1: dict, dt2: dict, stem: str) -> dict:
        if not dt2:
            return dt1
        if not argp().nodl and dt2['url'] and \
            not Path(f'{dt2['id']}.png').is_file():
            self.dls(dt2['url'], dt2['id'])
        else:
            print('跳过下载...', flush=True)
        if dt1.get(stem):
            dt3 = {i['location']: i['id'] for i in dt1[stem]}
            dt4 = {i['id']: i['url'] for i in dt1[stem]}
            if not (idn := dt3.get(dt2['location'])):
                if dt4.get(dt2['id'], dt2['url']) != dt2['url']:
                    lg.warning(
                        '头颅 %s 对应多重 URL。',
                        dt2['id'],
                        extra={'pos': f'L{self.ln}'}
                    )
                dt1[stem].append(dt2)
            else:
                lg.warning(
                    '位置 %s 已存在头颅 %s。',
                    dt2["location"], idn,
                    extra={'pos': f'L{self.ln}'}
                )
            return dt1
        dt1[stem] = [dt2]
        return dt1

    def prune(self, dt: dict) -> dict:
        dtn = {}
        urls = []
        for i, j in dt.items():
            dtn[i] = []
            url = [{m: n} for m, n in {
                k['id']: f'url:{k["url"].replace(
                    "https://textures.minecraft.net/texture/", ""
                    )}' for k in j
                }.items()]
            urls.extend(url)
            for k in j:
                k.pop('url')
                l = [m for m, n in k.items() if not n]
                for m in l:
                    k.pop(m)
                dtn[i].append(k)
        with open('url.json', 'w', encoding='utf-8') as wt:
            urls = {'data': urls}
            dump(urls, wt)
        return dtn

    def pro(self, stem: str, data: list) -> dict:
        dt = {}
        for i, j in enumerate(data):
            self.ln = i + 1
            if not j.strip():
                continue
            try:
                print(f'L{self.ln}', end='：', flush=True)
                dt_pending = self.ext(j)
                dt = self.merge(dt, dt_pending, stem)
            except Exception:
                print()
                lg.exception('未知错误。', extra={'pos': f'L{self.ln}'})
        return dt

    def __init__(self) -> None:
        self.pos = self.__class__.__name__.upper()
        dt = {}
        f = None
        if argp().nodl:
            lg.info('跳过下载已开启。', extra={'pos': self.pos})
        for f in Path('.').glob('*.txt'):
            stem = f.stem
            if stem == 'terlang':
                continue
            with open(f, 'r', encoding='utf-8') as rd:
                data = rd.read().splitlines()
            lg.info('%s - %s',
                stem, len(data),
                extra={'pos': self.pos}
            )
            dt |= self.prune(self.pro(stem, data))
        if not f:
            lg.warning('未找到 txt 后缀的批处理文件。', extra={'pos': self.pos})
            data = [input('输入待处理项：')]
            dt = self.pro('info', data)
        with open('info.json', 'w', encoding='utf-8') as wt:
            dump(dt, wt)
            lg.info('信息提取完成！', extra={'pos': self.pos})
            print()

class Idt:
    def ext(self, url: str) -> str:
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
            lg.error('已超时。', extra={'pos': f'L{self.msg}'})
            return ''
        data = res.text
        if 'No Heads available' in data:
            return ''
        con = data[data.find('descending'):data.find('Search Tips')]
        return search(r'a href=.+title="([^"]+)"', con).group(1)

    def d2csv(self, dt: dict) -> None:
        with open('name.csv', 'w', encoding='utf-8', newline='') as wt:
            headers = list(dt[0])
            wt_op = DictWriter(wt, fieldnames=headers)
            wt_op.writeheader()
            wt_op.writerows(dt)

    def pro(self, data: dict) -> None:
        m, n = next(iter(data.items()))
        self.msg = f'{self.ln} - {m}'
        print(self.msg, end='：', flush=True)
        j = self.ext(n)
        if j:
            j = j.replace(' ', '_')
            self.dt.append({'old': m, 'new': j})
            print(j, flush=True)
            if j in self.n_lt:
                lg.warning(
                    '与 %s 拥有共同的新名称 %s。',
                    next(iter(self.data[self.n_lt.index(j)].keys())), j,
                    extra={'pos': self.msg}
                )
            self.n_lt.append(j)
        else:
            print('None', flush=True)
            lg.warning('无可用名称。', extra={'pos': self.msg})
        sleep(0.2)

    def __init__(self) -> None:
        self.dt = []
        self.n_lt = []
        self.pos = self.__class__.__name__.upper()
        path = 'url.json'
        if Path(path).is_file():
            with open(path, 'r', encoding='utf-8') as rd:
                self.data = load(rd)['data']
            for i, j in enumerate(self.data):
                self.ln = i + 1
                self.pro(j)
            self.d2csv(self.dt)
        else:
            lg.error('%s 不存在！', path, extra={'pos': self.pos})
        lg.info('名称对照完成！', extra={'pos': self.pos})
        print()

class Imp:
    def blotem(self, idn: str, templ: str) -> bool:
        if not Path(templ).is_file():
            return False
        with open(templ, 'r', encoding='utf-8') as rd:
            tem = rd.read()
        uni = tem.replace('yzbwdlt', idn)
        flag = templ[templ.rfind('.', 0, -7)+1:templ.rfind('.')]
        wt_path = f'{flag}s/{idn}.{flag}.json'
        self.wt_op(wt_path, uni)
        lg.info('%ss 数据已生成！', flag, extra={'pos': self.pos})
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
        self.wt_op('terlang.txt', final)
        lg.info('terlang 数据已生成！', extra={'pos': self.pos})

    def wt_op(self, path: str, con: str) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as wt:
            wt.write(con)

    def __init__(self) -> None:
        self.pos = self.__class__.__name__.upper()
        block_tem = 'templates/yzbwdlt.block.json'
        item_tem = 'templates/yzbwdlt.item.json'
        block_info, item_info = True, True
        stems = tuple(i.stem for i in Path('.').glob('*.png'))
        if not stems:
            lg.error('无 png 文件！', extra={'pos': self.pos})
            return
        self.terlang(stems)
        for i in stems:
            if not self.blotem(i, block_tem) and block_info:
                lg.error(
                    '未找到模板 %s，跳过 block 生成！',
                    block_tem,
                    extra={'pos': self.pos}
                )
                block_info = False
            if not self.blotem(i, item_tem) and item_info:
                lg.error(
                    '未找到模板 %s，跳过 item 生成！',
                    item_tem,
                    extra={'pos': self.pos}
                )
                item_info = False
        print()

def argp():
    par = ArgumentParser(description='密室杀手自定义头颅生成器')
    par.add_argument(
        '-m', '--mode',
        nargs='+',
        default=['ext'],
        help='运行模式，可多选，包括 ext、idt、imp，默认 ext'
    )
    par.add_argument('--nodl', action='store_true', help='跳过下载')
    par.add_argument('--nourl', action='store_true', help='跳过 URL 记录')
    # return par.parse_args(['-m', 'imp'])
    return par.parse_args()

lg = getLogger(__name__)
lg.setLevel(DEBUG)
lg.handlers.clear()
form = Formatter('%(pos)s：%(levelname)s - %(message)s')
fil_h = FileHandler('debug.log', 'w', encoding='utf-8')
std_h = StreamHandler()
fil_h.setFormatter(form)
std_h.setFormatter(form)
lg.addHandler(fil_h)
lg.addHandler(std_h)
if __name__ == '__main__':
    try:
        args = argp()
        if 'get' in args.mode:
            Get()
        if 'idt' in args.mode:
            Idt()
        if 'imp' in args.mode:
            Imp()
    except Exception:
        lg.exception('未知错误。', extra={'pos': __name__})
shutdown()
