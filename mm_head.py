from base64 import urlsafe_b64decode as b64d
from json import dump, loads
from pathlib import Path
from re import search

from requests import exceptions, get


def ext(data: str) -> dict:
    # data = 'setblock 25 74 -6 minecraft:player_head[powered=false,rotation=0]{components:{},profile:{id:[I;67411088,-739686879,-1666252800,-1432087710],name:"",properties:[{name:"textures",signature:"",value:"eyJ0ZXh0dXJlcyI6eyJTS0lOIjp7InVybCI6Imh0dHA6Ly90ZXh0dXJlcy5taW5lY3JhZnQubmV0L3RleHR1cmUvOWYyNjg4M2RjMjhhNDljYjU4MmI2MGM2ZGNjZGNhMTczZDQ1ZjdiMWE3Yjg2OTBjYThjZTQzY2RlMGUxMzU4OSJ9fX0="}]}}'
    loc = search(r' ([\d\- ]+) ', data).group(1)
    try:
        rot = search(r'rotation=(\d+)', data).group(1)
        fac = None
    except AttributeError:
        rot = None
        fac = search(r'facing=([^,\]]+)', data).group(1)
    bsd = b64d(search(r'value:"([^\"]+)"', data).group(1)).decode()
    url = loads(bsd)['textures']['SKIN']['url'].replace('http:', 'https:')
    name = url[url.rfind('/')+1:url.rfind('/')+7]
    print(name, end='：', flush=True)
    return {
        'id': name,
        'location': loc,
        'rotation': rot,
        'facing': fac,
        'url': url
    }

def dls(url: str) -> bool:
    name = url[url.rfind('/')+1:url.rfind('/')+7]
    path = Path(f'{name}.png')
    if path.is_file():
        print('跳过下载...', flush=True)
        return False
    print('开始下载...', end='', flush=True)
    for i in range(3):
        try:
            img = get(url, timeout=(6.05, 10))
            break
        except exceptions.Timeout:
            print(f'超时（{i+1}/3）...', end='', flush=True)
    else:
        print('已超时。', flush=True)
        return False
    with open(f'{name}.png', 'wb') as png:
        png.write(img.content)
    print('成功！', flush=True)
    return True

def merge(dt1: dict, dt2: dict, stem: str) -> dict:
    dls(dt2['url'])
    dt2.pop('url')
    if dt1.get(stem):
        dt1[stem].append(dt2)
        return dt1
    dt1[stem] = [dt2]
    return dt1

def main(stem: str, data: list) -> dict:
    dt = {}
    for i in data:
        if not i.strip():
            continue
        try:
            dt_pending = ext(i)
            dt = merge(dt, dt_pending, stem)
        except Exception as e:
            print()
            print(f'{type(e).__name__}：{e}', flush=True)
    return dt

def pre() -> None:
    dt = {}
    f = None
    try:
        for f in Path('.').glob('*.txt'):
            stem = f.stem
            with open(f, 'r', encoding='utf-8') as rd:
                data = rd.read().splitlines()
            print(stem)
            dt |= main(stem, data)
        if not f:
            print('未找到 txt 后缀的批处理文件。')
            data = [input('输入待处理项：')]
            dt = main('info', data)
    finally:
        with open('info.json', 'w', encoding='utf-8') as wt:
            dump(dt, wt)

if __name__ == '__main__':
    pre()
