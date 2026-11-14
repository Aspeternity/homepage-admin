/* Pure Compose generation is also exercised by the Node regression checks. */
(() => {
  const quoteLiteral = value => JSON.stringify(String(value).split('$').join('$$'));
  const reference = name => JSON.stringify('${' + name + '}');
  function generate(mode, values, reveal = false) {
    const errors = [];
    const version = String(values.version || '').match(/^(\d+)\.(\d+)\.(\d+)/);
    if (version && Number(version[1]) < 2) errors.push('此配置需要 Homepage v2.0.0 或更新版本。');
    if (mode === 'oidc' && values.autoLogin && version && Number(version[1]) === 2 && Number(version[2]) < 3) errors.push('OIDC 自动登录需要 Homepage v2.3.0 或更新版本。');
    let url;
    try {
      url = new URL(values.url);
      if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password || url.search || url.hash) throw new Error();
    } catch (_) { errors.push('访问地址须为完整 HTTP(S) URL，且不能包含账号、查询参数或片段。'); }
    const lines = ['environment:'];
    const add = (name, value, secret = false) => {
      const supplied = String(value || '');
      lines.push('  ' + name + ': ' + (supplied ? quoteLiteral(secret && !reveal ? '••••••••' : supplied) : reference(name)));
    };
    const minSecret = (value, label) => { if (value && value.length < 32) errors.push(label + '至少需要 32 个字符。'); };
    if (url) add('HOMEPAGE_ALLOWED_HOSTS', url.host);
    if (mode === 'mcp') {
      lines.push('  HOMEPAGE_MCP_ENABLED: "true"');
      add('HOMEPAGE_MCP_TOKEN', values.token, true);
      minSecret(values.token, 'MCP Token');
      if (values.write) lines.push('  HOMEPAGE_MCP_ALLOW_WRITE: "true"');
    } else {
      lines.push('  HOMEPAGE_AUTH_ENABLED: "true"');
      add('HOMEPAGE_AUTH_SECRET', values.secret, true);
      minSecret(values.secret, '会话密钥');
      add('HOMEPAGE_EXTERNAL_URL', values.url);
      if (mode === 'oidc') {
        if (values.issuer) {
          try { const issuer = new URL(values.issuer); if (!['http:', 'https:'].includes(issuer.protocol) || issuer.username || issuer.password || issuer.search || issuer.hash) throw new Error(); }
          catch (_) { errors.push('OIDC Issuer 须为有效的 HTTP(S) 地址。'); }
        }
        add('HOMEPAGE_OIDC_ISSUER', values.issuer);
        add('HOMEPAGE_OIDC_CLIENT_ID', values.clientId);
        add('HOMEPAGE_OIDC_CLIENT_SECRET', values.clientSecret, true);
        if (values.name) add('HOMEPAGE_OIDC_NAME', values.name);
        if (values.scope) add('HOMEPAGE_OIDC_SCOPE', values.scope);
        if (values.autoLogin) lines.push('  HOMEPAGE_OIDC_AUTO_LOGIN: "true"');
      } else add('HOMEPAGE_AUTH_PASSWORD', values.password, true);
    }
    const base = url ? url.href.replace(/\/$/, '') : '';
    const endpoint = mode === 'mcp'
      ? 'MCP Endpoint：' + base + '/api/mcp\n客户端请求头：Authorization: Bearer <你的 Token>\n默认只读；请保管 Token，并限制 Endpoint 的访问范围。'
      : mode === 'oidc'
        ? '回调地址：' + base + '/api/auth/callback/homepage-oidc\n自动登录故障时可访问：' + base + '/auth/signin?autologin=0'
        : '会话密钥应保持稳定，避免重建容器后会话失效。密码登录限流由反向代理提供。';
    return { yaml: lines.join('\n'), errors, endpoint };
  }
  if (typeof module !== 'undefined') module.exports = {generate, quoteLiteral};
  if (typeof document === 'undefined') return;
  const root = document.querySelector('[data-compat-center]');
  if (!root) return;
  const tabs = [...root.querySelectorAll('[data-compat-tab]')];
  const activate = name => {
    if (!tabs.some(tab => tab.dataset.compatTab === name)) name = 'overview';
    tabs.forEach(tab => { const selected = tab.dataset.compatTab === name; tab.setAttribute('aria-selected', String(selected)); tab.tabIndex = selected ? 0 : -1; });
    root.querySelectorAll('[data-compat-panel]').forEach(panel => { panel.hidden = panel.dataset.compatPanel !== name; });
    try { sessionStorage.setItem('homepage-compat-tab', name); } catch (_) {}
  };
  tabs.forEach((tab, index) => {
    tab.addEventListener('click', () => activate(tab.dataset.compatTab));
    tab.addEventListener('keydown', event => {
      let target;
      if (event.key === 'ArrowRight') target = (index + 1) % tabs.length;
      if (event.key === 'ArrowLeft') target = (index + tabs.length - 1) % tabs.length;
      if (event.key === 'Home') target = 0;
      if (event.key === 'End') target = tabs.length - 1;
      if (target !== undefined) { event.preventDefault(); activate(tabs[target].dataset.compatTab); tabs[target].focus(); }
    });
  });
  root.querySelectorAll('[data-compat-go]').forEach(button => button.addEventListener('click', () => activate(button.dataset.compatGo)));
  let initialTab = 'overview';
  try { initialTab = sessionStorage.getItem('homepage-compat-tab') || initialTab; } catch (_) {}
  activate(initialTab);
  const detection = root.querySelector('#compat-detection');
  const detectionToggle = root.querySelector('[data-compat-detection-toggle]');
  const openDetection = () => { detection.hidden = false; detectionToggle.setAttribute('aria-expanded', 'true'); };
  detectionToggle.addEventListener('click', () => { detection.hidden = !detection.hidden; detectionToggle.setAttribute('aria-expanded', String(!detection.hidden)); });
  root.querySelectorAll('a[href="#compat-detection"]').forEach(link => link.addEventListener('click', openDetection));
  if (location.hash === '#compat-detection') openDetection();
  const buttons = [...root.querySelectorAll('[data-compat-check]')];
  const message = root.querySelector('[data-compat-check-message]');
  buttons.forEach(button => button.addEventListener('click', async () => {
    buttons.forEach(node => { node.disabled = true; });
    message.hidden = false;
    message.textContent = '正在识别版本并核对配置…';
    try {
      const response = await fetch('/api/homepage-compatibility/check', {method:'POST',headers:{'x-csrf-token':document.body.dataset.csrf || ''},signal:AbortSignal.timeout(25000)});
      const result = await response.json();
      if (!response.ok || !result.ok) throw new Error('检查失败，请确认登录状态和主机连接后重试。');
      location.reload();
    } catch (error) {
      message.textContent = error.name === 'TimeoutError' ? '检查超时，请稍后重试。' : error.message;
      buttons.forEach(node => { node.disabled = false; });
    }
  }));
  const assistant = root.querySelector('[data-compat-generators]');
  const find = name => assistant.querySelector('[data-compat-' + name + ']');
  const value = name => find(name)?.value || '';
  let reveal = false;
  const values = () => ({version:root.dataset.homepageVersion,url:value('external-url'),secret:value('secret'),password:value('password'),issuer:value('oidc-issuer'),clientId:value('oidc-client-id'),clientSecret:value('oidc-client-secret'),name:value('oidc-name'),scope:value('oidc-scope'),autoLogin:find('oidc-auto').checked,token:value('token'),write:find('mcp-write').checked});
  const render = () => {
    const mode = value('mode');
    find('auth').hidden = mode === 'mcp';
    find('password-field').hidden = mode !== 'password';
    find('oidc').hidden = mode !== 'oidc';
    find('mcp').hidden = mode !== 'mcp';
    const result = generate(mode, values(), reveal);
    find('output').textContent = result.yaml;
    find('error').hidden = !result.errors.length;
    find('error').textContent = result.errors.join(' ');
    find('copy').disabled = !!result.errors.length;
    find('endpoint').textContent = result.endpoint;
    find('reveal').textContent = reveal ? '隐藏敏感值' : '显示敏感值';
    find('reveal').setAttribute('aria-pressed', String(reveal));
  };
  assistant.querySelectorAll('input,select').forEach(input => { input.addEventListener('input',render); input.addEventListener('change',render); });
  find('reveal').addEventListener('click', () => { reveal = !reveal; render(); });
  assistant.querySelectorAll('[data-compat-generate]').forEach(button => button.addEventListener('click', () => {
    const bytes = crypto.getRandomValues(new Uint8Array(36));
    find(button.dataset.compatGenerate).value = [...bytes].map(byte => byte.toString(16).padStart(2,'0')).join('');
    render();
  }));
  find('copy').addEventListener('click', async () => {
    const result = generate(value('mode'),values(),true);
    if (result.errors.length) return;
    try {
      await navigator.clipboard.writeText(result.yaml);
      find('copy').textContent = '已复制完整配置';
      setTimeout(() => { find('copy').textContent = '复制配置'; },1500);
    } catch (_) { find('error').hidden = false; find('error').textContent = '剪贴板不可用，请显示敏感值后手动复制。'; }
  });
  render();
})();
