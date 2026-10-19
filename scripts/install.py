"""Install the bundled skill without overwriting an existing installation."""
import argparse
import os
from pathlib import Path
import shutil


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--skills-dir', type=Path, default=Path(os.environ.get('CODEX_HOME', str(Path.home() / '.codex'))) / 'skills')
    args = parser.parse_args()
    source = Path(__file__).resolve().parents[1] / 'universal-knowledge'
    target = args.skills_dir / source.name
    if target.exists() or target.is_symlink():
        parser.exit(1, f'Installation already exists: {target}; review/update manually or use a different directory.\n')
    shutil.copytree(source, target, ignore=shutil.ignore_patterns('__pycache__', '.pytest_cache', 'build', 'dist', 'node_modules', '*.egg-info', '*.pyc', '.env'))
    print(f'Installed {target}; restart Codex or refresh skills, then invoke $universal-knowledge.')


if __name__ == '__main__':
    main()
