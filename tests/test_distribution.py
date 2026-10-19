import importlib.util
from pathlib import Path
import zipfile

spec = importlib.util.spec_from_file_location('release', Path(__file__).parents[1] / 'scripts/package_release.py')
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


def test_archives_are_reproducible_and_exclude_secrets(tmp_path, monkeypatch):
    skill = tmp_path / 'universal-knowledge'
    (skill / 'assets/backend/knowledge').mkdir(parents=True)
    (skill / 'SKILL.md').write_text('skill')
    (skill / 'assets/backend/knowledge/api.py').write_text('source')
    for relative in ['.env', 'build/generated.py', '.venv/secret.txt', '.test-output/secret.txt', 'universal-knowledge/assets/backend/__pycache__/secret.pyc']:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('must not ship')
    monkeypatch.setattr(release, 'ROOT', tmp_path)
    release.build()
    first = (tmp_path / 'dist/SHA256SUMS.json').read_text()
    release.build()
    assert (tmp_path / 'dist/SHA256SUMS.json').read_text() == first
    for path in (tmp_path / 'dist').glob('*.zip'):
        with zipfile.ZipFile(path) as archive:
            assert not any(archive.read(name) == b'must not ship' for name in archive.namelist())
