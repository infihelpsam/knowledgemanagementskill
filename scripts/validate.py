"""Validate repository resources and compile Python without executing services."""
import ast
from pathlib import Path
import re
import sys
import tomllib


def main():
    root = Path(__file__).resolve().parents[1]
    skill = root / 'universal-knowledge'
    text = (skill / 'SKILL.md').read_text(encoding='utf-8')
    assert text.startswith('---\nname: universal-knowledge\ndescription:')
    assert len(text.split('---', 2)) == 3
    for match in re.finditer(r'\]\(([^)]+)\)', text):
        link = match.group(1)
        if '://' not in link:
            assert (skill / link).exists(), link
    files = [p for p in skill.rglob('*.py') if not any(part in {'build', '__pycache__', '.venv'} or part.endswith('.egg-info') for part in p.parts)] + list((root / 'scripts').glob('*.py')) + list((root / 'tests').glob('*.py'))
    for file in files:
        ast.parse(file.read_text(encoding='utf-8'), filename=str(file))
    tomllib.loads((skill / 'assets/backend/pyproject.toml').read_text())
    print(f'Validated skill links, metadata, project TOML and {len(files)} Python sources')


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
