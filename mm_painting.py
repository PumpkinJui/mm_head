from pathlib import Path

from PIL import Image

from mm_head import logger, write_file


def crop(path: Path) -> bool:
    pos = 'CROP'
    output_dir = Path('output/RP_custom_painting/textures/painting')
    stem = path.stem
    template_block = Path('templates/painting.block.json')
    template_item = Path('templates/painting.item.json')
    template_replacer = Path('templates/painting_replacer.item.json')
    output_dir_block = Path(f'output/BP_custom_painting/blocks/painting/{stem}')
    output_dir_item = Path(f'output/BP_custom_painting/items/painting/{stem}')
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    with Image.open(path) as f:
        width, height = f.size
        if width % 16 or height % 16:
            logger.error('尺寸错误！', extra={'pos': f'{pos} - {stem}'})
            return False
        width_mark, height_mark = width // 16, height // 16
        logger.info('%sx%s', width_mark, height_mark, extra={'pos': f'{pos} - {stem}'})
        for w in range(width_mark):
            for h in range(height_mark):
                h_real = height_mark - 1 - h
                location = f'{w}{h_real}'
                tile = f.crop((w * 16, h * 16, (w + 1) * 16, (h + 1) * 16))
                tile.save(output_dir / f'{stem}_{location}.png')
                _ = bp_generator(template_block, output_dir_block, stem, location)
                _ = bp_generator(template_item, output_dir_item, stem, location)
        _ = bp_generator(
            template_replacer, output_dir_item, stem, f'{width_mark}{height_mark}'
        )
    return True


def bp_generator(template: Path, output_dir: Path, stem: str, location: str) -> bool:
    pos = 'GEN'
    file_name = (
        f'{stem}_replacer' if 'replacer' in template.stem else f'{stem}_{location}'
    )
    table = {
        '(id)': stem,
        '(location)': location,
        '(length)': location[0],
        '(height)': location[1],
    }
    str_template = str(template)
    flag = str_template[str_template.rfind('.', 0, -7) + 1 : str_template.rfind('.')]
    if not template.is_file():
        logger.error('缺少模板文件 %s！', template, extra={'pos': pos})
        return False
    with open(template, 'r', encoding='utf-8') as f:
        data = f.read()
    for old, new in table.items():
        data = data.replace(old, new)
    write_file(output_dir / f'{file_name}.{flag}.json', data)
    return True
