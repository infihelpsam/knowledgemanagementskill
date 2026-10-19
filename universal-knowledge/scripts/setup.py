#!/usr/bin/env python3
"""Dependency-free, plan-first project generator."""
import argparse
import hashlib
import json
from pathlib import Path

ASSETS = Path(__file__).resolve().parents[1] / 'assets' / 'backend'


def detect(target):
    return [name for name, files in {'python': ['pyproject.toml', 'requirements.txt'], 'typescript/javascript': ['package.json'], 'go': ['go.mod'], 'rust': ['Cargo.toml']}.items() if any((target / f).is_file() for f in files)] or ['unknown/new project']


def plan(target, output):
    target = Path(target).absolute()
    if not target.is_dir():
        raise ValueError('Target project must exist')
    relative = Path(output)
    if relative.is_absolute() or '..' in relative.parts or not relative.parts:
        raise ValueError('Output must be a non-empty relative directory inside target')
    destination = target / relative
    for path in [target, *target.parents, destination, *destination.parents]:
        if path.is_symlink() or (hasattr(path, 'is_junction') and path.is_junction()):
            raise ValueError('Symlinks/junctions are not accepted')
    files = {}
    for source in sorted(ASSETS.rglob('*')):
        if not source.is_file() or any(p in {'__pycache__', '.pytest_cache', '.venv', 'build', 'dist', 'node_modules'} or p.endswith('.egg-info') for p in source.parts):
            continue
        if source.suffix == '.pyc':
            continue
        files[source.relative_to(ASSETS).as_posix()] = source.read_bytes()
    files['.knowledge-manifest.json'] = (json.dumps({'generator': '0.1.0', 'detected_stack': detect(target), 'output': str(relative)}, indent=2) + '\n').encode()
    manifest = []
    for name, data in files.items():
        path = destination / name
        for parent in [path, *path.parents]:
            if parent == target.parent:
                break
            if parent.is_symlink() or (hasattr(parent, 'is_junction') and parent.is_junction()):
                raise ValueError('Symlinks/junctions are not accepted')
            if parent != path and parent.exists() and not parent.is_dir():
                raise ValueError(f'Destination parent is not a directory: {parent}')
        if path.exists() and not path.is_file():
            raise ValueError(f'Destination is not a file: {path}')
        manifest.append({'path': str(path), 'sha256': hashlib.sha256(data).hexdigest(), 'existing_sha256': hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None})
    digest = hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()
    return destination, files, manifest, digest


def generate(target, output, dry_run=False, approval=None):
    destination, files, manifest, digest = plan(target, output)
    report = {'stack': detect(Path(target)), 'files': manifest, 'approval_digest': digest}
    if dry_run:
        return report
    collisions = [r['path'] for r in manifest if r['existing_sha256'] is not None]
    if collisions and approval != digest:
        raise ValueError(f'Existing files require review and --approve-plan {digest}; run --plan')
    # Revalidate immediately before writing. Callers must avoid concurrent project writes.
    if plan(target, output)[3] != digest:
        raise ValueError('Project changed; review a fresh plan')
    for name, data in files.items():
        path = destination / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('wb' if path.exists() else 'xb') as stream:
            stream.write(data)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target')
    parser.add_argument('--output', default=None)
    parser.add_argument('--plan', action='store_true')
    parser.add_argument('--approve-plan')
    args = parser.parse_args()
    target = args.target or input('Existing project directory: ').strip()
    output = args.output or ('knowledge' if args.target else input('Output directory [knowledge]: ').strip() or 'knowledge')
    try:
        print(json.dumps(generate(target, output, args.plan, args.approve_plan), indent=2))
    except (ValueError, OSError) as error:
        parser.exit(1, f'{error}\n')


if __name__ == '__main__':
    main()
