from pathlib import Path


def blotem(idn: str, templ: str) -> bool:
    if not Path(templ).is_file():
        return False
    with open(templ, 'r', encoding='utf-8') as rd:
        tem = rd.read()
    uni = tem.replace('yzbwdlt', idn)
    flag = templ[templ.rfind('.', 0, -7)+1:templ.rfind('.')]
    wt_path = f'{flag}s/{idn}.{flag}.json'
    wt_op(wt_path, uni)
    return True

def terlang(idn_lt: tuple) -> None:
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
    wt_op('terlang.txt', final)

def wt_op(path: str, con: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as wt:
        wt.write(con)

def rd_op() -> None:
    block_tem = 'templates/yzbwdlt.block.json'
    item_tem = 'templates/yzbwdlt.item.json'
    block_info, item_info = True, True
    stems = tuple(i.stem for i in Path('.').glob('*.png'))
    if not stems:
        print('无 png 文件！')
        return
    terlang(stems)
    for i in stems:
        if not blotem(i, block_tem) and block_info:
            print(f'未找到模板 {block_tem}！')
            block_info = False
        if not blotem(i, item_tem) and item_info:
            print(f'未找到模板 {item_tem}！')
            item_info = False

if __name__ == '__main__':
    rd_op()
