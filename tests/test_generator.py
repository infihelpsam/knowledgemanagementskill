import importlib.util
from pathlib import Path
import pytest

spec = importlib.util.spec_from_file_location('setup_skill', Path(__file__).parents[1] / 'universal-knowledge/scripts/setup.py')
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)


def test_generation_and_approval(tmp_path):
    (tmp_path / 'package.json').write_text('{}')
    preview = setup.generate(tmp_path, 'services/knowledge', dry_run=True)
    assert preview['stack'] == ['typescript/javascript']
    assert not (tmp_path / 'services').exists()
    setup.generate(tmp_path, 'services/knowledge')
    target = tmp_path / 'services/knowledge/knowledge/api.py'
    assert target.exists()
    target.write_text('local change')
    with pytest.raises(ValueError): setup.generate(tmp_path, 'services/knowledge')
    plan = setup.generate(tmp_path, 'services/knowledge', dry_run=True)
    target.write_text('another change')
    with pytest.raises(ValueError): setup.generate(tmp_path, 'services/knowledge', approval=plan['approval_digest'])
    plan = setup.generate(tmp_path, 'services/knowledge', dry_run=True)
    setup.generate(tmp_path, 'services/knowledge', approval=plan['approval_digest'])
    assert 'FastAPI' in target.read_text()


@pytest.mark.parametrize('output', ['../escape', 'a/../../escape', '.'])
def test_escape(tmp_path, output):
    with pytest.raises(ValueError): setup.generate(tmp_path, output)


def test_blocking_parent_is_rejected_before_partial_output(tmp_path):
    (tmp_path / 'knowledge').mkdir()
    (tmp_path / 'knowledge/knowledge').write_text('existing project file')
    with pytest.raises(ValueError): setup.generate(tmp_path, 'knowledge')
    assert sorted(p.name for p in (tmp_path / 'knowledge').iterdir()) == ['knowledge']


def test_symlink_is_rejected(tmp_path):
    outside = tmp_path / 'outside'
    outside.mkdir()
    try:
        (tmp_path / 'knowledge').symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip('Symlink creation unavailable on this Windows host')
    with pytest.raises(ValueError): setup.generate(tmp_path, 'knowledge')
