from __future__ import annotations

import copy
import json
from pathlib import Path
from urllib.error import URLError

import pytest
from fastapi.testclient import TestClient
from starlette.datastructures import FormData

from app import homepage_compat as compat, main
from app.compatibility_checks import inspect_configuration
from app.settings import settings
from app.store import HomepageStore, ConfigError
from app.widget_catalog import WIDGET_CATALOG, _schema_diff, effective_schema_ref
from app.widget_schema_sync import parse_widget_document, display_fields_for_config


@pytest.mark.parametrize(('left', 'right', 'expected'), [
    ('2.8.0-rc.1', '2.8.0', -1), ('2.8.0-rc.2', '2.8.0-rc.10', -1),
    ('2.8.0+build.2', '2.8.0', 0), ('2.8.0', '2.7.0', 1), ('latest', '2.8.0', None),
])
def test_semantic_versions_keep_prerelease(left, right, expected):
    assert compat.compare_versions(left, right) == expected
    assert compat.normalize_version('v2.8.0-rc.1') == '2.8.0-rc.1'


@pytest.mark.parametrize(('version', 'affected'), [('1.9.0', False), ('2.0.0', True), ('2.5.0', True), ('2.6.0-rc.1', True), ('2.6.0', False), ('2.8.0', False)])
def test_auth_advisory_range(version, affected):
    summary = compat.compatibility_summary(version)
    assert any('GHSA-qxcr' in item.get('message', '') for item in summary['warnings']) is affected
    assert compat.compatibility_summary('2.8.0-rc.1')['supported_status'] != 'known'


def test_mode_specific_fields_and_existing_fields_are_not_silently_lost(monkeypatch):
    doc = '''Allowed fields: `["queue", "time"]` (version 1) or `["queue", "failed"]` (version 2).
```yaml
widget:
  type: fileflows
  url: http://fileflows
  version: 2
  key: token # required for version 2
```
'''
    _, schema = parse_widget_document(doc, 'fileflows')
    assert display_fields_for_config(schema, {}) == ['queue', 'time']
    assert display_fields_for_config(schema, {'version': 2}) == ['queue', 'failed']
    assert not next(field for field in schema['fields'] if field['name'] == 'key')['required']
    monkeypatch.setitem(WIDGET_CATALOG, 'fileflows', schema)
    form = FormData({'widgets_0_type': 'fileflows', 'widgets_0_field_version': '2', 'widgets_0_field_key': 'fixture-key', 'widgets_0_fields': 'failed'})
    assert main._parse_widget_slot(form, '0', [])['fields'] == ['failed']
    with pytest.raises(ConfigError, match='不支持'):
        main._parse_widget_slot(FormData({'widgets_0_type': 'fileflows', 'widgets_0_fields': 'failed'}), '0', [])
    existing = {'type': 'fileflows', 'version': 2, 'key': 'fixture-key', 'fields': ['futureMetric']}
    form = FormData({'widgets_0_type': 'fileflows', 'widgets_0_field_version': '2', 'widgets_0_original_index': '0', 'widgets_0_fields': 'futureMetric'})
    assert main._parse_widget_slot(form, '0', [existing])['fields'] == ['futureMetric']


def test_beszel_and_offline_stable_snapshot():
    schema = WIDGET_CATALOG['beszel']
    assert display_fields_for_config(schema, {}) == ['systems', 'up']
    assert 'battery' in display_fields_for_config(schema, {'systemId': 'host-1'})
    assert all(key in WIDGET_CATALOG for key in ['bookorbit', 'qui', 'feed', 'netbird'])
    assert WIDGET_CATALOG['netbird']['category'] == '网络'
    assert WIDGET_CATALOG['qui']['category'] == '下载'
    assert WIDGET_CATALOG['bookorbit']['category'] == '媒体'
    snapshot = json.loads((Path(__file__).resolve().parents[1] / 'app/bundled_widget_schema.json').read_text())
    assert snapshot['meta']['ref'] == 'v2.8.0'
    assert snapshot['meta']['error_count'] == 0


def test_schema_diff_detects_semantics_not_only_names():
    old = {'test': {'fields': [{'name': 'key', 'kind': 'text', 'required': False}]}}
    new = copy.deepcopy(old)
    new['test']['fields'][0].update(kind='secret', required=True)
    diff = _schema_diff(old, new)
    assert diff['has_changes'] and diff['changed_widgets'][0]['changed_fields'] == ['key']


def test_release_failure_retains_last_success(monkeypatch):
    monkeypatch.setitem(compat._RELEASE_CACHE, 'payload', {'ok': True, 'version': '2.8.0', 'checked_at': 'previous'})
    monkeypatch.setattr(compat, 'urlopen', lambda *_a, **_kw: (_ for _ in ()).throw(URLError('offline')))
    result = compat.latest_homepage_release(force=True)
    assert result['version'] == '2.8.0' and result['stale']
    assert result['checked_at'] == 'previous'


def test_schema_target_prefers_manual_then_detected_then_stable(monkeypatch, tmp_path):
    from app import widget_catalog
    store = HomepageStore(tmp_path / 'config', tmp_path / 'data')
    monkeypatch.setattr(widget_catalog, 'store', store)
    assert effective_schema_ref() == 'v2.8.0'
    store.save_homepage_compatibility_check({'current_version': '2.7.0'})
    assert effective_schema_ref() == 'v2.7.0'
    store.set_homepage_version_override('2.5.0', 'test')
    assert effective_schema_ref() == 'v2.5.0'
    assert compat.schema_ref_for_version('dev', '2.5.0') == 'dev'


def test_configuration_findings_do_not_include_secret_values():
    configs = {'services.yaml': [{'Media': [{'FileFlows': {'widget': {'type': 'fileflows', 'version': 1, 'fields': ['failed'], 'key': 'NEVER-EXPOSE-THIS'}}}]}], 'settings.yaml': {'font': 'plexData', 'quicklaunch': {'disabled': True}}, 'widgets.yaml': [{'customapi': {'url': 'http://example'}}]}
    before = copy.deepcopy(configs)
    findings = inspect_configuration(configs, '2.2.0', WIDGET_CATALOG, {'ref': 'dev'})
    text = json.dumps(findings, ensure_ascii=False)
    assert 'NEVER-EXPOSE-THIS' not in text
    assert 'fileflows' in text and 'quicklaunch.disabled' in text and '顶部 Custom API' in text
    assert configs == before


def test_customapi_info_form_preserves_unknowns_and_masked_credentials():
    original = {'url': 'http://api.example/status', 'password': 'password-secret', 'headers': {'X-API-Token': 'token-secret'}, 'mappings': [{'field': 'value', 'label': 'Value', 'future': True}], 'requestBody': {'query': 'test'}, 'futureOption': 'keep'}
    values = main.info_widget_form_values('customapi', original)
    assert 'password-secret' not in json.dumps(values) and 'token-secret' not in json.dumps(values)
    form = FormData({**{k: str(values.get(k) or '') for k in ['url', 'password', 'extra', 'headers_yaml', 'mappings_yaml', 'requestBody_yaml']}, 'method': 'POST'})
    built = main.build_info_widget_config(form, 'customapi')
    restored = main.restore_masked_secrets(built, original)
    assert restored['password'] == original['password']
    assert restored['headers'] == original['headers']
    assert restored['mappings'] == original['mappings']
    assert restored['futureOption'] == 'keep'


def test_new_settings_roundtrip_preserves_future_fields(monkeypatch, tmp_path):
    store = HomepageStore(tmp_path / 'config', tmp_path / 'data')
    monkeypatch.setattr(main, 'store', store)
    store.write_data('settings.yaml', {'title': 'Before', 'cardStyle': 'hairline', 'blockStyle': 'refined', 'font': 'plexData', 'futureTop': {'keep': True}, 'quicklaunch': {'disabled': True, 'futureNested': 5}}, 'test', 'fixture')
    form = FormData({'title': 'After', 'settings_form_version': '3', 'cardStyle': 'hairline', 'blockStyle': 'refined', 'font': 'plexData', 'quicklaunch_disabled': 'on', 'extra': 'futureTop:\n  keep: true'})
    result = main._build_settings_change(form)
    assert result['quicklaunch'] == {'disabled': True, 'futureNested': 5}
    assert result['futureTop'] == {'keep': True}
    assert result['font'] == 'plexData'


def test_page_get_is_cached_and_check_requires_csrf(monkeypatch, tmp_path):
    store = HomepageStore(tmp_path / 'config', tmp_path / 'data')
    monkeypatch.setattr(main, 'store', store)
    client = TestClient(main.app)
    client.post('/login', data={'username': 'admin', 'password': 'test-password'})
    calls = []
    monkeypatch.setattr(main, 'detect_homepage_version_from_hosts', lambda _hosts: calls.append('docker') or {'found': False, 'version': '', 'candidates': [], 'errors': []})
    monkeypatch.setattr(main, 'latest_homepage_release', lambda **_kw: {'ok': True, 'version': '2.8.0'})
    page = client.get('/homepage-compatibility')
    assert page.status_code == 200 and calls == []
    assert client.post('/api/homepage-compatibility/check').status_code == 403
    import re
    csrf = re.search('data-csrf="([^"]+)"', page.text).group(1)
    assert client.post('/api/homepage-compatibility/check', headers={'x-csrf-token': csrf}).status_code == 200
    assert calls == ['docker']
    assert store.homepage_compatibility_check()['checked_at']
    assert '概览' in client.get('/homepage-compatibility').text


def test_selected_instance_and_stale_release_remain_distinct(monkeypatch, tmp_path):
    store = HomepageStore(tmp_path/'config', tmp_path/'data')
    monkeypatch.setattr(main, 'store', store)
    store.set_homepage_version_override('', 'test', 'second/homepage')
    store.save_homepage_compatibility_check({'latest': {'ok': True, 'version': '2.8.0', 'checked_at': 'previous'}})
    candidates = [dict(host='first', container='homepage', version='2.2.0', image='homepage:2.2.0'), dict(host='second', container='homepage', version='2.8.0', image='homepage:2.8.0')]
    monkeypatch.setattr(main, 'docker_discovery_hosts', lambda: [])
    monkeypatch.setattr(main, 'detect_homepage_version_from_hosts', lambda _hosts: dict(found=True,version='2.2.0',candidates=candidates,errors=[]))
    monkeypatch.setattr(main, 'latest_homepage_release', lambda **_kw: dict(ok=False,error='offline'))
    report=main.collect_homepage_compatibility_check()
    assert report['current_version'] == '2.8.0'
    assert report['detection']['host'] == 'second'
    assert report['latest']['stale'] is True
    assert report['latest']['checked_at'] == 'previous'
    assert not list((tmp_path/'config').glob('*.yaml'))


def test_advanced_fileflows_credentials_and_version_are_validated_after_merge():
    form=FormData({'widgets_0_type':'fileflows','widgets_0_fields':'failed','widgets_0_extra':'version: 2\nkey: fixture-token'})
    widget=main._parse_widget_slot(form,'0',[])
    assert widget['fields'] == ['failed']
    assert widget['key'] == 'fixture-token'


def test_session_expiry_remains_enforced(monkeypatch):
    from itsdangerous import TimestampSigner, SignatureExpired
    signer=TimestampSigner('test-secret')
    monkeypatch.setattr(TimestampSigner,'get_timestamp',lambda self:100000)
    token=signer.sign(b'test-session')
    monkeypatch.setattr(TimestampSigner,'get_timestamp',lambda self:143201)
    with pytest.raises(SignatureExpired):
        signer.unsign(token,max_age=43200)
