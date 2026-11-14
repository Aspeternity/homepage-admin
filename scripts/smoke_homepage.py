"""Exercise generated settings, authentication and widgets against official Homepage.

Run with the browser dependencies installed and Docker available. All credentials,
volumes and the container belong to this test and are removed on completion.
"""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time

import httpx
import yaml
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
IMAGE = 'ghcr.io/gethomepage/homepage:v2.8.0'


def run(*args, **kwargs):
    return subprocess.run(args, check=True, capture_output=True, text=True, **kwargs).stdout


class Backend(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(b'{"count":42}')

    def log_message(self, *args):
        pass


def main():
    with tempfile.TemporaryDirectory(prefix='homepage-admin-v280-') as tmp:
        root = Path(tmp)
        config = root/'config'
        shutil.copytree(ROOT/'example-config', config)
        os.environ.update(HOMEPAGE_CONFIG_DIR=str(config), ADMIN_DATA_DIR=str(root/'admin'), WIDGET_SCHEMA_AUTO_SYNC='false')
        from app.main import _build_settings_change, build_info_widget_config, store
        from starlette.datastructures import FormData
        settings = _build_settings_change(FormData({'title':'Homepage Admin compatibility smoke','language':'zh-Hans','settings_form_version':'3','cardStyle':'hairline','blockStyle':'refined','font':'plexData','quicklaunch_disabled':'on'}))
        store.write_data('settings.yaml', settings, 'smoke', 'generated settings')
        store.write_data('services.yaml', [{'Smoke':[{'Example':{'href':'http://example.test'}}]}], 'smoke', 'fixture')
        store.write_data('bookmarks.yaml', [], 'smoke', 'fixture')
        backend = ThreadingHTTPServer(('0.0.0.0',0), Backend)
        threading.Thread(target=backend.serve_forever, daemon=True).start()
        widget = build_info_widget_config(FormData({'url':f'http://host.docker.internal:{backend.server_port}/count','label':'Smoke API','refreshInterval':'1000','mappings_yaml':'- field: count\n  label: Count'}), 'customapi')
        store.write_data('widgets.yaml', [{'customapi':widget}], 'smoke', 'generated widget')
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0))
            port = sock.getsockname()[1]
        url = f'http://127.0.0.1:{port}'
        password = secrets.token_urlsafe(24) + '$LITERAL${KEEP}"\\end'
        values = {'url':url,'secret':secrets.token_urlsafe(48),'password':password}
        import playwright
        node = Path(playwright.__file__).parent/'driver/node'
        source = "const fs=require('fs');const {generate}=require(process.argv[1]);console.log(JSON.stringify(generate('password',JSON.parse(fs.readFileSync(0,'utf8')),true)));"
        generated = json.loads(run(str(node),'-e',source,str(ROOT/'app/static/compatibility.js'),input=json.dumps(values)))
        assert not generated['errors']
        compose = 'services:\n  smoke:\n    image: '+IMAGE+'\n'+''.join('    '+line+'\n' for line in generated['yaml'].splitlines())
        project = yaml.safe_load(compose)
        service = project['services']['smoke']
        token = secrets.token_urlsafe(48)
        service['environment'].update(HOMEPAGE_MCP_ENABLED='true',HOMEPAGE_MCP_TOKEN=token)
        name = 'homepage-admin-smoke-'+secrets.token_hex(5)
        service.update(container_name=name, user=f'{os.getuid()}:{os.getgid()}', ports=[f'127.0.0.1:{port}:3000'], volumes=[str(config)+':/app/config'], extra_hosts=['host.docker.internal:host-gateway'])
        compose_file = root/'compose.yaml'
        compose_file.write_text(yaml.safe_dump(project))
        compose_file.chmod(0o600)
        try:
            run('docker','compose','-p',name,'-f',str(compose_file),'up','-d')
            environment = json.loads(run('docker','inspect','--format','{{json .Config.Env}}',name))
            assert 'HOMEPAGE_AUTH_PASSWORD='+password in environment, 'Compose changed the literal password'
            with httpx.Client(base_url=url,trust_env=False,timeout=3) as client:
                deadline = time.monotonic()+90
                while time.monotonic()<deadline:
                    try:
                        if client.get('/api/healthcheck').status_code==200: break
                    except httpx.HTTPError: pass
                    time.sleep(.25)
                else: raise RuntimeError('Homepage did not become healthy')
                protected = client.get('/api/services')
                assert protected.status_code in {401,403} or (protected.is_redirect and '/auth/' in protected.headers.get('location','')), f'Protected API returned {protected.status_code}: {protected.headers.get("location", "")}'
                mcp = client.post('/api/mcp',headers={'Authorization':'Bearer '+token},json={'jsonrpc':'2.0','id':1,'method':'tools/list'})
                mcp.raise_for_status()
                payload=mcp.json()
                names=[item['name'] for item in payload['result']['tools']]
                assert 'read_config_file' in names
                before = (config/'settings.yaml').read_text()
                write_tool = next((item for item in payload['result']['tools'] if item['name']=='write_config_file'), None)
                if write_tool:
                    properties = write_tool.get('inputSchema',{}).get('properties',{})
                    arguments = {key:('title: write-must-be-rejected' if key=='content' else 'settings.yaml') for key in properties}
                    blocked = client.post('/api/mcp',headers={'Authorization':'Bearer '+token},json={'jsonrpc':'2.0','id':2,'method':'tools/call','params':{'name':'write_config_file','arguments':arguments}}).json()
                    assert any(text in json.dumps(blocked).lower() for text in ['read-only','disabled','allow_write']), 'MCP did not report its write restriction'
                assert (config/'settings.yaml').read_text() == before, 'MCP modified settings while writes disabled'
            with sync_playwright() as p:
                browser=p.chromium.launch()
                page=browser.new_page()
                page.goto(url,wait_until='networkidle')
                assert '/auth/signin' in page.url
                page.locator('input[type=password]').fill(password)
                page.locator('button[type=submit]').click()
                page.wait_for_function("!location.pathname.startsWith('/auth/')",timeout=20000)
                page.get_by_text('Smoke API',exact=True).wait_for(timeout=20000)
                page.get_by_text('42',exact=True).wait_for(timeout=20000)
                browser.close()
            assert store.load('settings.yaml')['quicklaunch']['disabled'] is True
            print(json.dumps({'image':IMAGE,'authentication':'passed','compose_literal_dollar_password':'preserved','generated_settings':'loaded','customapi_info_widget':'rendered 42','mcp':'read-only','tools':names},ensure_ascii=False))
        finally:
            subprocess.run(['docker','compose','-p',name,'-f',str(compose_file),'down'],capture_output=True)
            backend.shutdown()


if __name__ == '__main__':
    main()
