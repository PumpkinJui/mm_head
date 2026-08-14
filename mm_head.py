from base64 import urlsafe_b64decode as b64d
from json import dump, loads
from logging import FileHandler, Formatter, StreamHandler, getLogger, shutdown
from pathlib import Path
from re import search

from requests import exceptions, get


class Main:
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
            lg.warning('无头颅数据。', extra={'ln': self.ln})
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
        else:
            print()
            lg.warning('已超时。', extra={'ln': self.ln})
            return False
        with open(f'{name}.png', 'wb') as png:
            png.write(img.content)
        print('成功！', flush=True)
        return True

    def merge(self, dt1: dict, dt2: dict, stem: str, dl: bool=True) -> dict:
        if not dt2:
            return dt1
        if dl and dt2['url'] and not Path(f'{dt2['id']}.png').is_file():
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
                        extra={'ln': self.ln}
                    )
                dt1[stem].append(dt2)
            else:
                lg.warning(
                    '位置 %s 已存在头颅 %s。',
                    dt2["location"], idn,
                    extra={'ln': self.ln}
                )
            return dt1
        dt1[stem] = [dt2]
        return dt1

    def prune(self, dt: dict) -> dict:
        dtn = {}
        for i, j in dt.items():
            dtn[i] = []
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
                print(f'L{self.ln}', end='：', flush=True)
                dt_pending = self.ext(j)
                dt = self.merge(dt, dt_pending, stem)
            except Exception:
                print()
                lg.exception('未知错误。', extra={'ln': self.ln})
        return dt

    def __init__(self) -> None:
        dt = {}
        f = None
        fg_reset = '\033[0m'
        fg_bold = '\033[1m'
        fg_blue = '\033[34m'
        try:
            for f in Path('.').glob('*.txt'):
                stem = f.stem
                with open(f, 'r', encoding='utf-8') as rd:
                    data = rd.read().splitlines()
                print(fg_blue, fg_bold, stem, fg_reset, ' ', len(data), sep='')
                dt |= self.prune(self.pro(stem, data))
            if not f:
                print('未找到 txt 后缀的批处理文件。')
                data = [input('输入待处理项：')]
                dt = self.pro('info', data)
        finally:
            with open('info.json', 'w', encoding='utf-8') as wt:
                dump(dt, wt)

lg = getLogger(__name__)
lg.handlers.clear()
form = Formatter('L%(ln)s - %(levelname)s - %(message)s')
fil_h = FileHandler('debug.log', 'w', encoding='utf-8')
std_h = StreamHandler()
fil_h.setFormatter(form)
std_h.setFormatter(form)
lg.addHandler(fil_h)
lg.addHandler(std_h)
if __name__ == '__main__':
    Main()
shutdown()
