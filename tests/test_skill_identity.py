import pytest
from buildrix import skill_manager as sm, hub_client


def test_duplicate_names_require_id_and_install_separately(monkeypatch, tmp_path):
    rows = [{'id': 'a', 'skill_code': 'BXS-000001', 'name': 'load-prediction'},
            {'id': 'b', 'skill_code': 'BXS-000002', 'name': 'load-prediction'}]
    downloads = []
    class Client:
        def __init__(self, **kwargs): pass
        def list_skills(self, search):
            return [r for r in rows if search in (r['name'], r['skill_code'], r['id'])]
        def download_skill(self, id, dest):
            dest.mkdir(parents=True)
            downloads.append((id, dest))
    monkeypatch.setattr(hub_client, 'HubClient', Client)
    monkeypatch.setattr(sm, 'SKILLS_DIR', tmp_path)
    monkeypatch.setattr(sm, '_link_to_claude', lambda *args: None)
    monkeypatch.setattr(sm, 'provision_toolchain', lambda *args: None)
    with pytest.raises(ValueError, match='Install by ID'):
        sm.install_skill('load-prediction')
    first = sm.install_skill('#BXS-000001')
    second = sm.install_skill('BXS-000002')
    assert first != second and first.exists() and second.exists()
    assert [id for id, _ in downloads] == ['a', 'b']
