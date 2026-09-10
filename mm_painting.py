from json import dump, load
from pathlib import Path
from shutil import copy2
from typing import Final, TypedDict, cast

from PIL import Image

from mm_head import logger, write_file


class TextureInfo(TypedDict):
    resource_pack_name: str
    texture_data: dict[str, dict[str, str]]


class Painting:
    POS: Final[str] = 'PAINTING'

    def crop(self, path: Path) -> bool:
        pos = 'CROP'
        stem = path.stem
        with Image.open(path) as f:
            width, height = f.size
            if width % 16 or height % 16:
                logger.error('尺寸错误！', extra={'pos': f'{pos} - {stem}'})
                return False
            width_mark, height_mark = width // 16, height // 16
            logger.info(
                '%sx%s', width_mark, height_mark, extra={'pos': f'{pos} - {stem}'}
            )
            Painting.bp_generator(
                self.path_map['template']['replacer'],
                self.path_map['output']['item'],
                stem,
                f'{width_mark}{height_mark}',
            )
            self.texture_json['texture_data'][stem] = {
                'textures': f'textures/painting/{stem}'
            }
            for w in range(width_mark):
                for h in range(height_mark):
                    h_real = height_mark - 1 - h
                    location = f'{w}{h_real}'
                    tile_name = f'{stem}_{location}'
                    tile = f.crop((w * 16, h * 16, (w + 1) * 16, (h + 1) * 16))
                    tile.save(self.path_map['output']['painting'] / f'{tile_name}.png')
                    Painting.bp_generator(
                        self.path_map['template']['block'],
                        self.path_map['output']['block'],
                        stem,
                        location,
                    )
                    Painting.bp_generator(
                        self.path_map['template']['item'],
                        self.path_map['output']['item'],
                        stem,
                        location,
                    )
                    self.texture_json['texture_data'][tile_name] = {
                        'textures': f'textures/painting/{tile_name}'
                    }
        return True

    @staticmethod
    def bp_generator(
        template: Path, output_dir: Path, stem: str, location: str
    ) -> None:
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
        flag = str_template[
            str_template.rfind('.', 0, -7) + 1 : str_template.rfind('.')
        ]
        with open(template, 'r', encoding='utf-8') as f:
            data = f.read()
        for old, new in table.items():
            data = data.replace(old, new)
        write_file(output_dir / stem / f'{file_name}.{flag}.json', data)

    def __init__(self) -> None:
        self.enlang: list[str] = ['## ===== Items =====', '']
        self.texture_json: TextureInfo = {
            'resource_pack_name': 'painting',
            'texture_data': {
                'background': {'textures': 'textures/painting/background'},
            },
        }
        self.path_map: dict[str, dict[str, Path]] = {
            'template': {
                'block': Path('templates/painting.block.json'),
                'item': Path('templates/painting.item.json'),
                'replacer': Path('templates/painting_replacer.item.json'),
            },
            'input': {
                'json': Path('raw_painting/vanillaPaintingData.json'),
                'painting': Path('raw_painting'),
            },
            'output': {
                'block': Path('output/BP_custom_painting/blocks/painting'),
                'item': Path('output/BP_custom_painting/items/painting'),
                'painting': Path('output/RP_custom_painting/textures/painting'),
            },
        }
        for path in self.path_map['template'].values():
            if not path.is_file():
                logger.error('模板不存在！', extra={'pos': f'{self.POS} - {path.name}'})
                return
        if not (data_json := self.path_map['input']['json']).is_file():
            logger.error(
                '译名不存在！', extra={'pos': f'{self.POS} - {data_json.name}'}
            )
            return
        for path in self.path_map['output'].values():
            path.mkdir(parents=True, exist_ok=True)
        with open(data_json, 'r', encoding='utf-8') as f:
            lang_json = cast(list[dict[str, str]], load(f))
            lang_dict = {entry['id'].lower(): entry['name'] for entry in lang_json}
        for painting in Path(self.path_map['input']['painting']).glob('*.png'):
            stem = painting.stem
            _ = copy2(painting, self.path_map['output']['painting'] / painting.name)
            self.enlang.append(f'item.painting:{stem}.name={lang_dict.get(stem, stem)}')
            if stem not in lang_dict:
                logger.warning('无译名。', extra={'pos': f'{self.POS} - {stem}'})
            _ = self.crop(painting)
        with open(
            'output/RP_custom_painting/textures/terrain_texture.json',
            'w',
            encoding='utf-8',
        ) as f:
            dump(self.texture_json, f, indent=4)
        _ = copy2(
            'output/RP_custom_painting/textures/terrain_texture.json',
            'output/RP_custom_painting/textures/item_texture.json',
        )
        self.enlang.append('')
        write_file('output/RP_custom_painting/texts/en_US.lang', '\n'.join(self.enlang))
        logger.info('输出完成！', extra={'pos': self.POS})


if __name__ == '__main__':
    _ = Painting()
