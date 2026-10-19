"""Create deterministic source and installable skill ZIPs; exclude local secrets/caches."""
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
EXCLUDE = {'.git', '.venv', '__pycache__', '.pytest_cache', 'dist', 'build', 'node_modules', '.test-output', '.env', '.agents', '.codex'}


def included(path):
    return not any(p in EXCLUDE or p.endswith('.egg-info') for p in path.relative_to(ROOT).parts) and path.suffix not in {'.pyc', '.zip'}


def build():
    destination = ROOT / 'dist'
    destination.mkdir(exist_ok=True)
    artifacts = {}
    for name, base in [('universal-knowledge-0.1.0.zip', ROOT / 'universal-knowledge'), ('universal-knowledge-source-0.1.0.zip', ROOT)]:
        output = destination / name
        with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(base.rglob('*')):
                if path.is_file() and included(path):
                    relative = path.relative_to(ROOT)
                    info = zipfile.ZipInfo(relative.as_posix(), (2026, 1, 1, 0, 0, 0))
                    info.compress_type = zipfile.ZIP_DEFLATED
                    info.external_attr = 0o644 << 16
                    archive.writestr(info, path.read_bytes())
        with zipfile.ZipFile(output) as archive:
            assert archive.testzip() is None
            assert 'universal-knowledge/SKILL.md' in archive.namelist()
            assert 'universal-knowledge/assets/backend/knowledge/api.py' in archive.namelist()
        artifacts[name] = hashlib.sha256(output.read_bytes()).hexdigest()
    (destination / 'SHA256SUMS.json').write_text(json.dumps(artifacts, indent=2) + '\n')
    print(json.dumps(artifacts, indent=2))


if __name__ == '__main__':
    build()
