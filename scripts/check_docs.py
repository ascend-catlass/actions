"""Check bilingual Action coverage and documented interfaces before site builds."""
from pathlib import Path
import re
import sys

import yaml

ROOT = Path(__file__).resolve().parents[1]


def nav_paths(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for child in value:
            yield from nav_paths(child)
    elif isinstance(value, dict):
        for child in value.values():
            yield from nav_paths(child)


def section(text, title):
    found = re.search(rf'^## {re.escape(title)}\s*\n(.*?)(?=^## |\Z)', text, re.M | re.S)
    if not found:
        raise ValueError(f'Missing section: {title}')
    return found.group(1)


def table_rows(text):
    rows = {}
    for line in text.splitlines():
        if not line.startswith('| `'):
            continue
        cells = [cell.strip() for cell in line.strip('|').split('|')]
        name = cells[0].strip('`')
        if name in rows:
            raise ValueError(f'Duplicate table field: {name}')
        rows[name] = cells
    return rows


def default_value(metadata):
    value = metadata.get('default')
    if value is None:
        return '—'
    return '`""`' if value == '' else f'`{value}`'


def check_page(path, slug, metadata, lang):
    text = path.read_text(encoding='utf-8')
    inputs = metadata.get('inputs', {})
    outputs = metadata.get('outputs', {})
    rows = table_rows(section(text, '输入' if lang == 'zh' else 'Inputs'))
    if set(rows) != set(inputs):
        raise ValueError(f'Input coverage differs: {set(rows) ^ set(inputs)}')
    for name, field in inputs.items():
        required = ('是' if field.get('required') else '否') if lang == 'zh' else ('Yes' if field.get('required') else 'No')
        if len(rows[name]) != 4 or rows[name][1:3] != [required, default_value(field)]:
            raise ValueError(f'Incorrect required/default values: {name}')
    output_rows = table_rows(section(text, '输出' if lang == 'zh' else 'Outputs'))
    if set(output_rows) != set(outputs):
        raise ValueError(f'Output coverage differs: {set(output_rows) ^ set(outputs)}')
    counterpart = f'../../{"en" if lang == "zh" else "zh"}/actions/{slug}.md'
    if f']({counterpart})' not in text:
        raise ValueError('Missing counterpart language link')
    own_examples = 0
    for example in re.findall(r'```yaml\n(.*?)\n```', text, re.S):
        steps = yaml.safe_load(example)
        if not isinstance(steps, list):
            raise ValueError('Example must be a steps list')
        for step in steps:
            if step.get('uses') != f'ascend-catlass/actions/.github/actions/{slug}@main':
                continue
            own_examples += 1
            supplied = step.get('with', {})
            if not set(supplied) <= set(inputs):
                raise ValueError('Example uses unknown inputs')
            missing = {name for name, field in inputs.items() if field.get('required') and name not in supplied}
            if missing:
                raise ValueError(f'Example omits required inputs: {missing}')
    if not own_examples:
        raise ValueError('Missing an example calling this Action')


def main():
    errors = []
    config = yaml.safe_load((ROOT / 'mkdocs.yml').read_text(encoding='utf-8'))
    navigation = list(nav_paths(config['nav']))
    if len(navigation) != len(set(navigation)):
        errors.append('Navigation repeats a page')
    for page in navigation:
        if not (ROOT / 'docs' / page).is_file():
            errors.append(f'Navigation target is missing: {page}')
    actions = sorted((ROOT / '.github/actions').glob('*/action.yml'))
    for action in actions:
        slug = action.parent.name
        metadata = yaml.safe_load(action.read_text(encoding='utf-8'))
        for lang in ('zh', 'en'):
            relative = f'{lang}/actions/{slug}.md'
            try:
                if relative not in navigation:
                    raise ValueError('Missing from navigation')
                check_page(ROOT / 'docs' / relative, slug, metadata, lang)
                readme = (action.parent / 'README.md').read_text(encoding='utf-8')
                if f'../../../docs/{relative}' not in readme:
                    raise ValueError('Missing Action README link')
            except (OSError, ValueError, yaml.YAMLError) as error:
                errors.append(f'{relative}: {error}')
    expected = {p.parent.name for p in actions}
    for lang in ('zh', 'en'):
        actual = {p.stem for p in (ROOT / f'docs/{lang}/actions').glob('*.md')}
        if actual != expected:
            errors.append(f'{lang}: stale or missing Action pages: {actual ^ expected}')
    if errors:
        print('\n'.join(errors), file=sys.stderr)
        return 1
    print(f'Documentation checks passed: {len(actions)} Actions, {2 * len(actions)} bilingual Action pages.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
