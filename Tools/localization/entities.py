"""Read entity metadata without constructing game-specific YAML tags."""
from pathlib import Path
import json
import re

import yaml


def literal(value):
    # YAML strings are literal text, not Fluent expressions. Quote each line so
    # braces, leading dots, dollar signs and quotes cannot become Fluent syntax.
    lines = str(value).splitlines() or ['']
    return '\n        '.join('{ ' + json.dumps(line, ensure_ascii=False) + ' }' for line in lines)


def scan_entities(root):
    records, errors = {}, []
    loader = getattr(yaml, 'CBaseLoader', yaml.BaseLoader)
    for base in (root / 'Resources/Prototypes', root / 'Content.CMU/Resources/Prototypes'):
        if not base.exists():
            continue
        for path in sorted(set(base.rglob('*.yml')) | set(base.rglob('*.yaml'))):
            if not path.resolve().is_relative_to(root):
                errors.append(f'Прототип вне проекта: {path}')
                continue
            try:
                # BaseLoader treats !type:... tags as plain mappings/scalars.
                documents = list(yaml.load_all(path.read_text(encoding='utf-8-sig'), Loader=loader))
            except (yaml.YAMLError, UnicodeError, OSError) as exc:
                errors.append(f'{path.relative_to(root)}: {exc}')
                continue
            for document in documents:
                if not isinstance(document, list):
                    continue
                expanded = []
                for item in document:
                    if isinstance(item, dict) and isinstance(item.get('id'), dict):
                        identifiers = item['id'].get('values', [])
                        for index, ident in enumerate(identifiers):
                            variant = dict(item, id=ident)
                            for field in ('parent', 'name', 'description', 'suffix', 'localizationId'):
                                value = variant.get(field)
                                if isinstance(value, dict):
                                    choices = value.get('values', value.get('sequences', []))
                                    if index < len(choices):
                                        variant[field] = choices[index]
                            expanded.append(variant)
                    else:
                        expanded.append(item)
                for item in expanded:
                    if not isinstance(item, dict) or item.get('type') != 'entity' or not item.get('id'):
                        continue
                    ident = item['id']
                    if not isinstance(ident, str):
                        errors.append(f'{path.relative_to(root)}: entity id должен быть строкой')
                        continue
                    key = item.get('localizationId') or 'ent-' + ident
                    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]*', key):
                        errors.append(f'{path.relative_to(root)}: неверный ключ {key}')
                        continue
                    parents = item.get('parent', [])
                    if isinstance(parents, str):
                        parents = [parents]
                    if ident in records:
                        errors.append(f'Повтор entity {ident}: {path.relative_to(root)}')
                        continue
                    records[ident] = dict(id=ident, key=key, path=path,
                                         relative=path.relative_to(base), parents=parents,
                                         abstract=item.get('abstract') == 'true',
                                         fields={field: item[field] for field in ('name', 'description', 'suffix')
                                                 if isinstance(item.get(field), str)})
    return records, errors
