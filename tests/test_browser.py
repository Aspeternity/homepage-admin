"""Real Chromium regression tests; use requirements-browser.txt and install Chromium."""
from __future__ import annotations

import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import sys
import time

import httpx
import pytest

playwright_api = pytest.importorskip('playwright.sync_api')
ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope='module')
def browser_server(tmp_path_factory):
    root = tmp_path_factory.mktemp('browser-runtime')
    shutil.copytree(ROOT / 'example-config', root / 'config')
    data = root / 'data'
    data.mkdir()
    (data / 'admin-settings.json').write_text(json.dumps({'homepage_compatibility': {'version_override': '2.8.0'}}))
    password = secrets.token_urlsafe(32)
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0))
        port = sock.getsockname()[1]
    env = {**os.environ, 'HOMEPAGE_CONFIG_DIR':str(root/'config'),'ADMIN_DATA_DIR':str(data),'ADMIN_USERNAME':'browser-test','ADMIN_PASSWORD':password,'ADMIN_PASSWORD_HASH':'','SESSION_SECRET':secrets.token_urlsafe(48),'WIDGET_SCHEMA_AUTO_SYNC':'false','ADMIN_ALLOWED_HOSTS':'localhost,127.0.0.1'}
    # Test-process-only clock; production middleware and expiry rules are unchanged.
    bootstrap = '''import sys,time
from itsdangerous import TimestampSigner
wall,mono=time.time(),time.monotonic()
TimestampSigner.get_timestamp=lambda self:int(wall+time.monotonic()-mono)
import uvicorn
uvicorn.run('app.main:app',host='127.0.0.1',port=int(sys.argv[1]))
'''
    with (root/'server.log').open('w') as log:
        process = subprocess.Popen([sys.executable,'-c',bootstrap,str(port)],cwd=ROOT,env=env,stdout=log,stderr=log)
        url = f'http://127.0.0.1:{port}'
        try:
            for _ in range(100):
                try:
                    if httpx.get(url+'/healthz',trust_env=False).status_code == 200: break
                except httpx.HTTPError: pass
                time.sleep(.1)
            else: raise AssertionError((root/'server.log').read_text())
            yield url,password,data
        finally:
            process.terminate()
            process.wait(timeout=15)


@pytest.fixture(scope='module')
def browser():
    with playwright_api.sync_playwright() as p:
        browser = p.chromium.launch()
        yield browser
        browser.close()


@pytest.fixture
def page(browser,browser_server):
    url,password,_ = browser_server
    context = browser.new_context(viewport={'width':1440,'height':1000},color_scheme='light',locale='zh-CN',timezone_id='Asia/Shanghai')
    page = context.new_page()
    errors=[]
    page.on('pageerror',lambda error: errors.append(str(error)))
    page.goto(url+'/login')
    page.locator('input[name=username]').fill('browser-test')
    page.locator('input[name=password]').fill(password)
    page.locator('button[type=submit]').click()
    page.wait_for_url('**/services')
    yield page
    assert errors == []
    context.close()


def test_compatibility_tabs_forms_and_responsive_layout(page,browser_server):
    url,_,_ = browser_server
    page.goto(url+'/homepage-compatibility')
    with page.expect_navigation(wait_until='networkidle',timeout=30000):
        page.locator('[data-compat-check]').first.click()
    assert page.locator('.compat-status-label').inner_text() == '已检查'
    page.locator('[data-compat-tab=assistant]').click()
    page.locator('[data-compat-secret]').fill('x'*40)
    page.locator('[data-compat-password]').fill('literal$PASSWORD')
    assert 'literal' not in page.locator('[data-compat-output]').inner_text()
    page.locator('[data-compat-reveal]').click()
    assert 'literal$$PASSWORD' in page.locator('[data-compat-output]').inner_text()
    page.locator('[data-compat-mode]').select_option('oidc')
    page.locator('[data-compat-oidc-auto]').check()
    assert 'HOMEPAGE_OIDC_AUTO_LOGIN' in page.locator('[data-compat-output]').inner_text()
    assert '/api/auth/callback/homepage-oidc' in page.locator('[data-compat-endpoint]').inner_text()
    page.locator('[data-compat-mode]').select_option('mcp')
    page.locator('[data-compat-generate=token]').click()
    assert len(page.locator('[data-compat-token]').input_value()) >= 32
    assert not page.locator('[data-compat-mcp-write]').is_checked()
    page.locator('[data-compat-external-url]').fill('bad-url')
    assert page.locator('[data-compat-copy]').is_disabled()
    page.locator('[data-compat-external-url]').fill('https://homepage.example.com')
    assert page.locator('[data-compat-copy]').is_enabled()
    page.locator('[data-compat-tab=overview]').click()
    page.locator('[data-compat-detection-toggle]').click()
    assert page.locator('#compat-detection').is_visible()
    for theme in ('light','dark'):
        page.evaluate('(theme)=>document.documentElement.dataset.theme=theme',theme)
        for width in (1440,768,390,320):
            page.set_viewport_size({'width':width,'height':1000})
            for tab in ('overview','upgrade','assistant'):
                page.locator(f'[data-compat-tab={tab}]').click()
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'),f'{theme} {width} {tab}'
    page.locator('[data-compat-tab=overview]').click()
    output=os.getenv('HOMEPAGE_SCREENSHOT_DIR')
    if output:
        Path(output).mkdir(parents=True,exist_ok=True)
        page.set_viewport_size({'width':1440,'height':1000})
        page.evaluate("document.documentElement.dataset.theme='light'")
        page.locator('[data-compat-detection-toggle]').click()
        page.screenshot(path=str(Path(output)/'homepage-compatibility-light.png'),full_page=True,animations='disabled')
        page.evaluate("document.documentElement.dataset.theme='dark'")
        page.screenshot(path=str(Path(output)/'homepage-compatibility-dark.png'),full_page=True,animations='disabled')


def test_widget_mode_switching_preserves_entered_secret(page,browser_server):
    url,_,_ = browser_server
    page.goto(url+'/services/item/new?widget=fileflows')
    page.locator('[data-widget-field-name=version]').fill('2')
    page.locator('[data-widget-field-name=key]').fill('not-a-real-token')
    assert page.locator('input[type=checkbox][value=failed]').is_visible()
    assert page.locator('input[type=checkbox][value=time]').count() == 0
    page.locator('[data-widget-field-name=version]').fill('1')
    assert page.locator('input[type=checkbox][value=time]').is_visible()
    assert page.locator('[data-widget-field-name=key]').input_value() == 'not-a-real-token'
    page.goto(url+'/services/item/new?widget=beszel')
    assert page.locator('input[type=checkbox][value=systems]').is_visible()
    page.locator('[data-widget-field-name=systemId]').fill('server-1')
    assert page.locator('input[type=checkbox][value=battery]').is_visible()
    assert page.locator('input[type=checkbox][value=systems]').count() == 0


def test_settings_and_customapi_form_save(page,browser_server):
    url,_,data=browser_server
    page.goto(url+'/widgets/new?type=customapi')
    page.locator('input[name=url]').fill('http://example.test/api')
    page.locator('textarea[name=mappings_yaml]').fill('- field: count\n  label: Count')
    page.locator('textarea[name=headers_yaml]').fill('X-API-Token: browser-fixture-secret')
    page.get_by_role('button', name='保存组件', exact=True).click()
    page.wait_for_url('**/widgets?*')
    page.goto(url+'/settings')
    page.locator('select[name=font]').select_option('plexData')
    page.locator('select[name=cardStyle]').select_option('hairline')
    page.locator('input[name=quicklaunch_disabled]').check()
    # Use the existing settings diff flow rather than bypassing validation.
    with page.expect_response('**/api/settings/preview') as preview:
        page.locator('[data-settings-preview]').click()
    assert preview.value.json()['ok'] is True
    page.locator('[data-settings-diff-confirm]').click()
    page.wait_for_url('**/settings?*')
    assert page.locator('select[name=font]').input_value() == 'plexData'
    assert page.locator('input[name=quicklaunch_disabled]').is_checked()
