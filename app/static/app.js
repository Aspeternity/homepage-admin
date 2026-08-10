(() => {
  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
  const csrf = () => document.body.dataset.csrf || '';

  const systemTheme = () => window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
  const currentThemeMode = () => document.documentElement.dataset.themeMode || 'dark';
  const resolveTheme = (mode) => mode === 'system' ? systemTheme() : (mode === 'light' ? 'light' : 'dark');

  const applyThemeMode = (mode, persist = true) => {
    const nextMode = ['light', 'dark', 'system'].includes(mode) ? mode : 'dark';
    const resolved = resolveTheme(nextMode);
    document.documentElement.dataset.themeMode = nextMode;
    document.documentElement.dataset.theme = resolved;
    if (persist) {
      try { localStorage.setItem('homepage-admin-theme', nextMode); } catch (_) {}
    }
    $$('[data-theme-icon]').forEach((icon) => {
      icon.textContent = resolved === 'light' ? '☀' : '☾';
    });
    $$('[data-theme-choice]').forEach((button) => {
      const active = button.dataset.themeChoice === nextMode;
      button.classList.toggle('active', active);
      button.setAttribute('aria-pressed', active ? 'true' : 'false');
    });
    $$('[data-theme-menu-toggle], [data-theme-cycle]').forEach((button) => {
      const names = { light: '浅色模式', dark: '深色模式', system: '跟随系统' };
      button.title = `主题：${names[nextMode]}`;
      button.setAttribute('aria-label', `主题：${names[nextMode]}`);
    });
  };

  applyThemeMode(currentThemeMode(), false);

  const themeMedia = window.matchMedia('(prefers-color-scheme: light)');
  const systemThemeChanged = () => {
    if (currentThemeMode() === 'system') applyThemeMode('system', false);
  };
  if (themeMedia.addEventListener) themeMedia.addEventListener('change', systemThemeChanged);
  else if (themeMedia.addListener) themeMedia.addListener(systemThemeChanged);

  $$('[data-theme-choice]').forEach((button) => {
    button.addEventListener('click', () => {
      applyThemeMode(button.dataset.themeChoice);
      const menu = button.closest('[data-theme-menu]');
      const popover = menu?.querySelector('[data-theme-popover]');
      const trigger = menu?.querySelector('[data-theme-menu-toggle]');
      if (popover) popover.hidden = true;
      trigger?.setAttribute('aria-expanded', 'false');
    });
  });

  $$('[data-theme-cycle]').forEach((button) => {
    button.addEventListener('click', () => {
      applyThemeMode(resolveTheme(currentThemeMode()) === 'light' ? 'dark' : 'light');
    });
  });

  $$('[data-theme-menu-toggle]').forEach((button) => {
    button.addEventListener('click', (event) => {
      event.stopPropagation();
      const menu = button.closest('[data-theme-menu]');
      const popover = menu?.querySelector('[data-theme-popover]');
      if (!popover) return;
      const opening = popover.hidden;
      $$('[data-theme-popover]').forEach((other) => { other.hidden = true; });
      $$('[data-theme-menu-toggle]').forEach((other) => other.setAttribute('aria-expanded', 'false'));
      popover.hidden = !opening;
      button.setAttribute('aria-expanded', opening ? 'true' : 'false');
    });
  });

  document.addEventListener('click', (event) => {
    if (event.target.closest('[data-theme-menu]')) return;
    $$('[data-theme-popover]').forEach((popover) => { popover.hidden = true; });
    $$('[data-theme-menu-toggle]').forEach((button) => button.setAttribute('aria-expanded', 'false'));
  });
  document.addEventListener('keydown', (event) => {
    if (event.key !== 'Escape') return;
    $$('[data-theme-popover]').forEach((popover) => { popover.hidden = true; });
    $$('[data-theme-menu-toggle]').forEach((button) => button.setAttribute('aria-expanded', 'false'));
  });

  $('[data-sidebar-toggle]')?.addEventListener('click', () => {
    document.body.classList.toggle('sidebar-open');
  });

  $$('[data-dialog-open]').forEach((button) => {
    button.addEventListener('click', () => {
      const dialog = document.getElementById(button.dataset.dialogOpen);
      dialog?.showModal();
      dialog?.querySelector('input:not([type=hidden])')?.focus();
    });
  });
  $$('[data-dialog-close]').forEach((button) => {
    button.addEventListener('click', () => button.closest('dialog')?.close());
  });
  $$('dialog').forEach((dialog) => {
    dialog.addEventListener('click', (event) => {
      const rect = dialog.getBoundingClientRect();
      const inside = event.clientX >= rect.left && event.clientX <= rect.right && event.clientY >= rect.top && event.clientY <= rect.bottom;
      if (!inside) dialog.close();
    });
  });

  $$('form[data-confirm]').forEach((form) => {
    form.addEventListener('submit', (event) => {
      if (!window.confirm(form.dataset.confirm)) event.preventDefault();
    });
  });

  $('[data-secret-reveal]')?.addEventListener('click', (event) => {
    if (!window.confirm('将临时显示 API Key、Token、Password 等真实敏感值。请避免截图或复制到公开位置。继续吗？')) {
      event.preventDefault();
    }
  });

  $$('textarea').forEach((textarea) => {
    textarea.addEventListener('keydown', (event) => {
      if (event.key !== 'Tab') return;
      event.preventDefault();
      const start = textarea.selectionStart;
      const end = textarea.selectionEnd;
      textarea.value = textarea.value.slice(0, start) + '  ' + textarea.value.slice(end);
      textarea.selectionStart = textarea.selectionEnd = start + 2;
    });
  });

  async function postJson(url, payload) {
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'content-type': 'application/json',
        'x-csrf-token': csrf(),
      },
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (!response.ok || !data.ok) throw new Error(data.error || '操作失败');
    return data;
  }

  // Service/bookmark card drag-and-drop, including cross-group moves.
  let dragState = null;
  $$('.item-card[draggable=true]').forEach((card) => {
    card.addEventListener('dragstart', (event) => {
      dragState = {
        source_group: Number(card.dataset.groupIndex),
        source_index: Number(card.dataset.itemIndex),
      };
      card.classList.add('dragging');
      event.dataTransfer.effectAllowed = 'move';
      event.stopPropagation();
    });
    card.addEventListener('dragend', () => {
      card.classList.remove('dragging');
      $$('.drop-zone').forEach((zone) => zone.classList.remove('drag-over'));
    });
  });

  $$('.drop-zone').forEach((zone) => {
    zone.addEventListener('dragover', (event) => {
      if (!dragState) return;
      event.preventDefault();
      event.stopPropagation();
      zone.classList.add('drag-over');
    });
    zone.addEventListener('dragleave', (event) => {
      if (!zone.contains(event.relatedTarget)) zone.classList.remove('drag-over');
    });
    zone.addEventListener('drop', async (event) => {
      if (!dragState) return;
      event.preventDefault();
      event.stopPropagation();
      zone.classList.remove('drag-over');
      const cards = $$('.item-card', zone).filter((card) => !card.classList.contains('dragging'));
      let targetIndex = cards.length;
      const targetCard = event.target.closest('.item-card');
      if (targetCard) {
        const rect = targetCard.getBoundingClientRect();
        const before = event.clientY < rect.top + rect.height / 2;
        const cardPosition = cards.indexOf(targetCard);
        targetIndex = Math.max(0, cardPosition + (before ? 0 : 1));
      }
      const payload = {
        ...dragState,
        target_group: Number(zone.dataset.groupIndex),
        target_index: targetIndex,
      };
      try {
        await postJson(`/api/${zone.dataset.kind}/move`, payload);
        window.location.reload();
      } catch (error) {
        window.alert(error.message);
      } finally {
        dragState = null;
      }
    });
  });

  // Whole group drag-and-drop. The dedicated handle avoids fighting with item-card dragging.
  let groupDrag = null;
  $$('[data-group-drag]').forEach((handle) => {
    handle.addEventListener('dragstart', (event) => {
      const panel = handle.closest('[data-group-panel]');
      if (!panel) return;
      groupDrag = {
        kind: panel.dataset.kind,
        source_index: Number(panel.dataset.groupIndex),
      };
      panel.classList.add('group-dragging');
      event.dataTransfer.effectAllowed = 'move';
    });
    handle.addEventListener('dragend', () => {
      handle.closest('[data-group-panel]')?.classList.remove('group-dragging');
      $$('[data-group-panel]').forEach((panel) => panel.classList.remove('group-drag-over'));
      groupDrag = null;
    });
  });

  $$('[data-group-panel]').forEach((panel) => {
    panel.addEventListener('dragover', (event) => {
      if (!groupDrag || groupDrag.kind !== panel.dataset.kind) return;
      event.preventDefault();
      panel.classList.add('group-drag-over');
    });
    panel.addEventListener('dragleave', (event) => {
      if (!panel.contains(event.relatedTarget)) panel.classList.remove('group-drag-over');
    });
    panel.addEventListener('drop', async (event) => {
      if (!groupDrag || groupDrag.kind !== panel.dataset.kind) return;
      event.preventDefault();
      panel.classList.remove('group-drag-over');
      const rect = panel.getBoundingClientRect();
      const after = event.clientY > rect.top + rect.height / 2;
      const targetIndex = Number(panel.dataset.groupIndex) + (after ? 1 : 0);
      try {
        await postJson(`/api/${groupDrag.kind}/group/reorder`, {
          source_index: groupDrag.source_index,
          target_index: targetIndex,
        });
        window.location.reload();
      } catch (error) {
        window.alert(error.message);
      } finally {
        groupDrag = null;
      }
    });
  });

  // Top widget drag-and-drop.
  let widgetDrag = null;
  $$('[data-widget-drag]').forEach((handle) => {
    handle.addEventListener('dragstart', (event) => {
      const row = handle.closest('[data-widget-row]');
      if (!row) return;
      widgetDrag = Number(row.dataset.widgetIndex);
      row.classList.add('dragging');
      event.dataTransfer.effectAllowed = 'move';
    });
    handle.addEventListener('dragend', () => {
      handle.closest('[data-widget-row]')?.classList.remove('dragging');
      widgetDrag = null;
    });
  });
  $$('[data-widget-row]').forEach((row) => {
    row.addEventListener('dragover', (event) => {
      if (widgetDrag === null) return;
      event.preventDefault();
      row.classList.add('widget-drag-over');
    });
    row.addEventListener('dragleave', () => row.classList.remove('widget-drag-over'));
    row.addEventListener('drop', async (event) => {
      if (widgetDrag === null) return;
      event.preventDefault();
      row.classList.remove('widget-drag-over');
      const rect = row.getBoundingClientRect();
      const after = event.clientY > rect.top + rect.height / 2;
      const targetIndex = Number(row.dataset.widgetIndex) + (after ? 1 : 0);
      try {
        await postJson('/api/widgets/reorder', { source_index: widgetDrag, target_index: targetIndex });
        window.location.reload();
      } catch (error) {
        window.alert(error.message);
      } finally {
        widgetDrag = null;
      }
    });
  });

  // Widget-specific service form fields. Hidden schemas are disabled so duplicate field names never submit.
  const widgetTypeInput = $('[data-widget-type-input]');
  if (widgetTypeInput) {
    const syncWidgetSchema = () => {
      const selected = widgetTypeInput.value.trim().toLowerCase();
      $$('[data-widget-schema]').forEach((schema) => {
        const active = schema.dataset.widgetSchema === selected;
        schema.hidden = !active;
        schema.disabled = !active;
      });
    };
    widgetTypeInput.addEventListener('input', syncWidgetSchema);
    widgetTypeInput.addEventListener('change', syncWidgetSchema);
    syncWidgetSchema();
  }

  // v0.4.0 Docker multi-host discovery controls.
  const dockerHostFilter = $('[data-docker-host-filter]');
  dockerHostFilter?.addEventListener('change', () => dockerHostFilter.form?.submit());

  const dockerSearch = $('[data-docker-search]');
  const dockerStateFilter = $('[data-docker-state-filter]');
  const dockerAddedFilter = $('[data-docker-added-filter]');
  if (dockerSearch || dockerStateFilter || dockerAddedFilter) {
    const filterDockerCards = () => {
      const query = (dockerSearch?.value || '').trim().toLowerCase();
      const state = dockerStateFilter?.value || 'all';
      const added = dockerAddedFilter?.value || 'all';
      let shown = 0;
      $$('[data-docker-card]').forEach((card) => {
        const searchOk = !query || (card.dataset.search || '').includes(query);
        const stateValue = card.dataset.state || '';
        const stateOk = state === 'all' || (state === 'running' ? stateValue === 'running' : stateValue !== 'running');
        const addedValue = card.dataset.added === '1';
        const addedOk = added === 'all' || (added === 'added' ? addedValue : !addedValue);
        card.hidden = !(searchOk && stateOk && addedOk);
        if (!card.hidden) shown += 1;
      });
      const empty = $('[data-docker-filter-empty]');
      if (empty) empty.hidden = shown !== 0;
    };
    dockerSearch?.addEventListener('input', filterDockerCards);
    dockerStateFilter?.addEventListener('change', filterDockerCards);
    dockerAddedFilter?.addEventListener('change', filterDockerCards);
    filterDockerCards();
  }

  const renderDockerHostTest = (target, ok, message) => {
    if (!target) return;
    target.hidden = false;
    target.classList.toggle('ok', Boolean(ok));
    target.classList.toggle('error', !ok);
    target.textContent = message;
  };
  const testDockerHost = async ({hostId = '', url = '', discoveryOverride = '', homepageServer = '', publicHost = '', button, result}) => {
    const original = button?.textContent || '';
    if (button) { button.disabled = true; button.textContent = '测试中…'; }
    renderDockerHostTest(result, true, '正在连接 Docker API…');
    try {
      const body = new URLSearchParams({csrf: csrf()});
      if (hostId) body.set('host_id', hostId);
      else {
        body.set('url', url);
        body.set('discovery_override', discoveryOverride || '');
        body.set('homepage_server', homepageServer || 'test-server');
        body.set('public_host', publicHost || '');
      }
      const response = await fetch('/api/docker/hosts/test', {method: 'POST', body});
      const payload = await response.json();
      if (!response.ok || !payload.ok) throw new Error(payload.message || '连接测试失败');
      renderDockerHostTest(result, true, payload.message);
    } catch (error) {
      renderDockerHostTest(result, false, error.message || String(error));
    } finally {
      if (button) { button.disabled = false; button.textContent = original; }
    }
  };

  $$('[data-docker-host-test]').forEach((button) => {
    button.addEventListener('click', () => {
      const hostId = button.dataset.hostId || '';
      const result = document.querySelector(`[data-host-test-result="${CSS.escape(hostId)}"]`);
      testDockerHost({hostId, button, result});
    });
  });

  const dockerHostForm = $('[data-docker-host-form]');
  if (dockerHostForm) {
    const button = $('[data-docker-host-form-test]', dockerHostForm);
    button?.addEventListener('click', () => testDockerHost({
      url: $('[data-docker-host-url]', dockerHostForm)?.value.trim() || '',
      discoveryOverride: $('[data-docker-discovery-override]', dockerHostForm)?.value.trim() || '',
      homepageServer: $('[data-docker-homepage-server]', dockerHostForm)?.value.trim() || '',
      publicHost: $('[data-docker-public-host]', dockerHostForm)?.value.trim() || '',
      button,
      result: $('[data-docker-host-form-result]', dockerHostForm),
    }));
  }

  // Docker import group strategy. "auto" lets the wizard choose a group from the recognized service type.
  const importGroup = $('[data-docker-import-group]');
  if (importGroup) {
    const storageKey = 'homepage-admin-docker-import-group-v2';
    try {
      const saved = localStorage.getItem(storageKey);
      if (saved !== null && [...importGroup.options].some((option) => option.value === saved)) importGroup.value = saved;
    } catch (_) {}
    const syncImportLinks = () => {
      $$('[data-docker-import-link]').forEach((link) => {
        const base = link.dataset.importBase || link.getAttribute('href').split('?')[0];
        link.href = importGroup.value === 'auto'
          ? base
          : `${base}?group=${encodeURIComponent(importGroup.value)}`;
      });
    };
    importGroup.addEventListener('change', () => {
      try { localStorage.setItem(storageKey, importGroup.value); } catch (_) {}
      syncImportLinks();
    });
    syncImportLinks();
  }
  // Docker import wizard: live Homepage card + non-sensitive YAML preview.
  const wizard = $('[data-import-wizard]');
  if (wizard) {
    const field = (name) => $(`[data-wizard-field="${name}"]`, wizard);
    const staticField = (name) => $(`[data-wizard-static="${name}"]`, wizard)?.value || '';
    const yamlQuote = (value) => {
      const text = String(value ?? '');
      if (!text) return "''";
      if (/^[A-Za-z0-9_./:@-]+$/.test(text)) return text;
      return JSON.stringify(text);
    };
    const renderWizard = () => {
      const name = field('name')?.value.trim() || '未命名服务';
      const href = field('href')?.value.trim() || '';
      const icon = field('icon')?.value.trim() || '';
      const description = field('description')?.value.trim() || '';
      const siteMonitor = field('siteMonitor')?.value.trim() || '';
      const ping = field('ping')?.value.trim() || '';
      const widgetType = field('widget_type')?.value.trim() || '';
      const widgetUrl = field('widget_url')?.value.trim() || '';
      const groupSelect = field('group');
      const groupName = groupSelect?.selectedOptions?.[0]?.textContent?.trim() || 'Group';
      const previewName = $('[data-preview-name]', wizard);
      const previewDescription = $('[data-preview-description]', wizard);
      const previewIcon = $('[data-preview-icon]', wizard);
      const previewIconImage = $('[data-preview-icon-image]', wizard);
      const previewIconFallback = $('[data-preview-icon-fallback]', wizard);
      const previewWidget = $('[data-preview-widget]', wizard);
      if (previewName) previewName.textContent = name;
      if (previewDescription) previewDescription.textContent = description || href || '暂无说明';
      if (previewIcon) previewIcon.title = icon || '默认首字母图标';
      if (previewIconImage && previewIconFallback) {
        let imageUrl = '';
        let mdiPreview = false;
        if (/^https?:\/\//i.test(icon)) imageUrl = icon;
        else if (/^sh-[a-z0-9._-]+$/i.test(icon)) {
          const slug = icon.slice(3).toLowerCase();
          imageUrl = `https://cdn.jsdelivr.net/gh/selfhst/icons/png/${encodeURIComponent(slug)}.png`;
        } else if (/^mdi-[a-z0-9._-]+$/i.test(icon)) {
          const slug = icon.slice(4).toLowerCase();
          imageUrl = `https://cdn.jsdelivr.net/npm/@mdi/svg@7.4.47/svg/${encodeURIComponent(slug)}.svg`;
          mdiPreview = true;
        }
        previewIconImage.classList.toggle('mdi-preview', mdiPreview);
        previewIconFallback.textContent = icon
          ? icon.replace(/^(sh|mdi)-/, '').slice(0, 2).toUpperCase()
          : name.slice(0, 1).toUpperCase();
        previewIconImage.onerror = () => {
          previewIconImage.hidden = true;
          previewIconFallback.hidden = false;
        };
        if (imageUrl) {
          previewIconFallback.hidden = true;
          previewIconImage.hidden = false;
          previewIconImage.src = imageUrl;
        } else {
          previewIconImage.hidden = true;
          previewIconImage.removeAttribute('src');
          previewIconFallback.hidden = false;
        }
      }
      if (previewWidget) previewWidget.hidden = !widgetType;

      const lines = [`- ${groupName}:`, `    - ${name}:`];
      const push = (key, value) => { if (value) lines.push(`        ${key}: ${yamlQuote(value)}`); };
      push('icon', icon);
      push('href', href);
      push('description', description);
      push('siteMonitor', siteMonitor);
      push('ping', ping);
      push('server', staticField('server'));
      push('container', staticField('container'));
      if (widgetType) {
        lines.push('        widget:');
        lines.push(`          type: ${yamlQuote(widgetType)}`);
        if (widgetUrl) lines.push(`          url: ${yamlQuote(widgetUrl)}`);
      }
      const yaml = $('[data-wizard-yaml]', wizard);
      if (yaml) yaml.textContent = lines.join('\n');
    };
    $$('[data-wizard-field]', wizard).forEach((input) => {
      input.addEventListener('input', renderWizard);
      input.addEventListener('change', renderWizard);
    });
    renderWizard();
  }


  // v0.3.2 Widget Center filters (official Schema-driven catalog).
  const widgetSearch = $('[data-widget-search]');
  const widgetCategory = $('[data-widget-category]');
  if (widgetSearch || widgetCategory) {
    const filterWidgetCenter = () => {
      const query = (widgetSearch?.value || '').trim().toLowerCase();
      const category = widgetCategory?.value || '';
      let visible = 0;
      $$('[data-widget-card]').forEach((card) => {
        const matchesText = !query || (card.dataset.widgetName || '').includes(query);
        const matchesCategory = !category || card.dataset.widgetCategory === category;
        card.hidden = !(matchesText && matchesCategory);
        if (!card.hidden) visible += 1;
      });
      const empty = $('[data-widget-center-empty]');
      if (empty) empty.hidden = visible !== 0;
    };
    widgetSearch?.addEventListener('input', filterWidgetCenter);
    widgetCategory?.addEventListener('change', filterWidgetCenter);
    filterWidgetCenter();
  }

  // v0.3.0 metadata-driven multi-widget editor.
  const serviceEditor = $('[data-service-editor]');
  if (serviceEditor) {
    // v0.4.5 discovery-backed runtime integrations. The visible selects never
    // submit raw names directly; hidden fields remain compatible with Homepage YAML.
    const dockerIntegration = $('[data-service-docker-integration]', serviceEditor);
    if (dockerIntegration) {
      const hostSelect = $('[data-service-docker-host]', dockerIntegration);
      const containerSelect = $('[data-service-docker-container]', dockerIntegration);
      const serverValue = $('[data-service-docker-server-value]', dockerIntegration);
      const containerValue = $('[data-service-docker-container-value]', dockerIntegration);
      const status = $('[data-service-docker-status]', dockerIntegration);
      const currentServer = dockerIntegration.dataset.currentServer || '';
      const currentContainer = dockerIntegration.dataset.currentContainer || '';
      let firstLoad = true;

      const syncDockerHidden = () => {
        const option = hostSelect?.selectedOptions?.[0];
        const server = option?.dataset?.server || '';
        const container = containerSelect?.value || '';
        if (serverValue) serverValue.value = container ? server : '';
        if (containerValue) containerValue.value = container || '';
      };

      const resetDockerContainers = (message = '请先选择 Docker 主机') => {
        if (!containerSelect) return;
        containerSelect.innerHTML = '';
        const option = document.createElement('option');
        option.value = ''; option.textContent = message;
        containerSelect.appendChild(option);
        containerSelect.disabled = true;
      };

      const loadDockerContainers = async () => {
        if (!hostSelect || !containerSelect) return;
        const hostId = hostSelect.value;
        const selected = hostSelect.selectedOptions?.[0];
        const server = selected?.dataset?.server || '';
        const preserveCurrent = firstLoad && server && server === currentServer && currentContainer;
        firstLoad = false;
        if (!hostId || !server) {
          resetDockerContainers();
          if (serverValue) serverValue.value = '';
          if (containerValue) containerValue.value = '';
          if (status) status.textContent = '选择主机后自动读取容器列表。';
          return;
        }
        if (!preserveCurrent) {
          if (serverValue) serverValue.value = '';
          if (containerValue) containerValue.value = '';
        }
        containerSelect.disabled = true;
        containerSelect.innerHTML = '<option value="">正在读取容器…</option>';
        if (status) status.textContent = '正在通过 Docker 发现读取容器列表…';
        try {
          const response = await fetch(`/api/docker/host/${encodeURIComponent(hostId)}/service-options`);
          const data = await response.json();
          if (!response.ok || !data.ok) throw new Error(data.error || '无法读取 Docker 容器');
          containerSelect.innerHTML = '';
          const blank = document.createElement('option');
          blank.value = ''; blank.textContent = '不绑定 Docker 容器';
          containerSelect.appendChild(blank);
          (data.containers || []).forEach((item) => {
            const option = document.createElement('option');
            option.value = item.name;
            option.textContent = `${item.name} · ${item.image || '未知镜像'} · ${item.state || 'unknown'}`;
            if (preserveCurrent && item.name === currentContainer) option.selected = true;
            containerSelect.appendChild(option);
          });
          if (preserveCurrent && ![...containerSelect.options].some((item) => item.value === currentContainer)) {
            const option = document.createElement('option');
            option.value = currentContainer; option.textContent = `${currentContainer}（当前配置，未在发现列表中）`; option.selected = true;
            containerSelect.appendChild(option);
          }
          containerSelect.disabled = false;
          syncDockerHidden();
          if (status) status.textContent = `已读取 ${data.containers?.length || 0} 个容器。`;
        } catch (error) {
          containerSelect.innerHTML = '';
          if (preserveCurrent) {
            const option = document.createElement('option');
            option.value = currentContainer; option.textContent = `${currentContainer}（当前配置）`; option.selected = true;
            containerSelect.appendChild(option);
            containerSelect.disabled = false;
            if (serverValue) serverValue.value = currentServer;
            if (containerValue) containerValue.value = currentContainer;
          } else {
            resetDockerContainers('读取失败，请重新选择主机');
          }
          if (status) status.textContent = `Docker 发现失败：${error.message}`;
        }
      };
      hostSelect?.addEventListener('change', loadDockerContainers);
      containerSelect?.addEventListener('change', syncDockerHidden);
      if (hostSelect?.value) loadDockerContainers();
    }

    const proxmoxIntegration = $('[data-service-proxmox-integration]', serviceEditor);
    if (proxmoxIntegration) {
      const connectionSelect = $('[data-service-proxmox-connection]', proxmoxIntegration);
      const resourceSelect = $('[data-service-proxmox-resource]', proxmoxIntegration);
      const nodeValue = $('[data-service-proxmox-node-value]', proxmoxIntegration);
      const vmidValue = $('[data-service-proxmox-vmid-value]', proxmoxIntegration);
      const typeValue = $('[data-service-proxmox-type-value]', proxmoxIntegration);
      const status = $('[data-service-proxmox-status]', proxmoxIntegration);
      const currentNode = proxmoxIntegration.dataset.currentNode || '';
      const currentVmid = proxmoxIntegration.dataset.currentVmid || '';
      const currentType = proxmoxIntegration.dataset.currentType || 'qemu';
      let firstLoad = true;

      const syncProxmoxHidden = () => {
        const option = resourceSelect?.selectedOptions?.[0];
        if (!option?.value) {
          if (nodeValue) nodeValue.value = '';
          if (vmidValue) vmidValue.value = '';
          if (typeValue) typeValue.value = '';
          return;
        }
        if (nodeValue) nodeValue.value = option.dataset.node || '';
        if (vmidValue) vmidValue.value = option.dataset.vmid || '';
        if (typeValue) typeValue.value = option.dataset.type || 'qemu';
      };

      const resetProxmoxResources = (message = '请先选择 Proxmox 连接') => {
        if (!resourceSelect) return;
        resourceSelect.innerHTML = '';
        const option = document.createElement('option');
        option.value = ''; option.textContent = message;
        resourceSelect.appendChild(option);
        resourceSelect.disabled = true;
      };

      const loadProxmoxResources = async () => {
        if (!connectionSelect || !resourceSelect) return;
        const server = connectionSelect.value;
        const preserveCurrent = firstLoad && server && server === currentNode && currentVmid;
        firstLoad = false;
        if (!server) {
          resetProxmoxResources();
          if (nodeValue) nodeValue.value = '';
          if (vmidValue) vmidValue.value = '';
          if (typeValue) typeValue.value = '';
          if (status) status.textContent = '选择连接后自动读取 VM / LXC 列表。';
          return;
        }
        if (!preserveCurrent) {
          if (nodeValue) nodeValue.value = '';
          if (vmidValue) vmidValue.value = '';
          if (typeValue) typeValue.value = '';
        }
        resourceSelect.disabled = true;
        resourceSelect.innerHTML = '<option value="">正在读取 VM / LXC…</option>';
        if (status) status.textContent = '正在通过 Proxmox 发现读取资源…';
        try {
          const response = await fetch(`/api/proxmox/service-options?server=${encodeURIComponent(server)}`);
          const data = await response.json();
          if (!response.ok || !data.ok) throw new Error(data.error || '无法读取 Proxmox 资源');
          resourceSelect.innerHTML = '';
          const blank = document.createElement('option');
          blank.value = ''; blank.textContent = '不绑定 VM / LXC';
          resourceSelect.appendChild(blank);
          let matched = false;
          (data.resources || []).forEach((item) => {
            const option = document.createElement('option');
            option.value = `${item.node}:${item.type}:${item.vmid}`;
            option.dataset.node = item.node;
            option.dataset.vmid = String(item.vmid);
            option.dataset.type = item.type || 'qemu';
            const available = item.connection_available !== false;
            option.disabled = !available;
            option.textContent = `${item.name} · ${(item.type || 'qemu').toUpperCase()} ${item.vmid} · ${item.node} · ${item.status || 'unknown'}${available ? '' : ' · 缺少同名 proxmox.yaml 连接'}`;
            if (available && preserveCurrent && item.node === currentNode && String(item.vmid) === String(currentVmid) && (item.type || 'qemu') === currentType) { option.selected = true; matched = true; }
            resourceSelect.appendChild(option);
          });
          if (preserveCurrent && !matched) {
            const option = document.createElement('option');
            option.value = 'current'; option.dataset.node = currentNode; option.dataset.vmid = currentVmid; option.dataset.type = currentType;
            option.textContent = `${currentType.toUpperCase()} ${currentVmid} · ${currentNode}（当前配置，未在发现列表中）`; option.selected = true;
            resourceSelect.appendChild(option);
          }
          resourceSelect.disabled = false;
          syncProxmoxHidden();
          if (status) status.textContent = `已读取 ${data.resources?.length || 0} 个 VM / LXC。`;
        } catch (error) {
          resourceSelect.innerHTML = '';
          if (preserveCurrent) {
            const option = document.createElement('option');
            option.value = 'current'; option.dataset.node = currentNode; option.dataset.vmid = currentVmid; option.dataset.type = currentType;
            option.textContent = `${currentType.toUpperCase()} ${currentVmid} · ${currentNode}（当前配置）`; option.selected = true;
            resourceSelect.appendChild(option);
            resourceSelect.disabled = false;
            if (nodeValue) nodeValue.value = currentNode;
            if (vmidValue) vmidValue.value = currentVmid;
            if (typeValue) typeValue.value = currentType;
          } else {
            resetProxmoxResources('读取失败，请重新选择连接');
          }
          if (status) status.textContent = `Proxmox 发现失败：${error.message}`;
        }
      };
      connectionSelect?.addEventListener('change', loadProxmoxResources);
      resourceSelect?.addEventListener('change', syncProxmoxHidden);
      if (connectionSelect?.value) loadProxmoxResources();
    }

    let catalog = {};
    try { catalog = JSON.parse($('#widget-catalog-data')?.textContent || '{}'); } catch (_) {}
    const list = $('[data-service-widgets]', serviceEditor);
    const empty = $('[data-widget-empty]', serviceEditor);
    const slotsInput = $('[data-widget-slots]', serviceEditor);
    const template = $('#service-widget-template');
    const sourceGroup = serviceEditor.querySelector('[name="source_group_index"]')?.value || '0';
    const sourceItem = serviceEditor.querySelector('[name="source_item_index"]')?.value || '';
    let nextSlot = Math.max(0, ...$$('[data-service-widget]', serviceEditor).map((block) => Number(block.dataset.slot) + 1));

    const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, (ch) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));

    const syncWidgetSlots = () => {
      const blocks = $$('[data-service-widget]', serviceEditor);
      if (slotsInput) slotsInput.value = blocks.map((block) => block.dataset.slot).join(',');
      if (empty) empty.hidden = blocks.length > 0;
      blocks.forEach((block, index) => {
        const small = block.querySelector('.service-widget-head small');
        if (small) small.textContent = `Widget #${index + 1}`;
      });
    };

    const initialData = (block) => {
      const script = $('[data-widget-initial]', block);
      try { return JSON.parse(script?.textContent || '{}'); } catch (_) { return {}; }
    };

    const renderWidgetFields = (block, initial = null) => {
      const slot = block.dataset.slot;
      const typeInput = $('[data-widget-type]', block);
      const type = (typeInput?.value || '').trim().toLowerCase();
      const schema = catalog[type];
      const container = $('[data-widget-dynamic-fields]', block);
      const title = $('[data-widget-title]', block);
      if (!container) return;
      if (title) title.textContent = schema?.label || type || '新 Widget';
      if (!schema) {
        container.innerHTML = type
          ? '<div class="alert warning">该类型尚未加入 Widget 中心。可在“Widget 其他配置”里继续使用 YAML；连接测试不可用。</div>'
          : '<div class="widget-schema-placeholder">选择 Widget 类型后显示专属字段。</div>';
        return;
      }
      const values = initial?.fields || {};
      const secretSaved = initial?.secret_saved || {};
      const selectedFields = new Set(initial?.selected_fields || []);
      if (schema.enhanced === false) {
        const docs = escapeHtml(schema.docs || 'https://gethomepage.dev/widgets/services/');
        container.innerHTML = `<div class="widget-schema-head"><div><strong>${escapeHtml(schema.label)}</strong><span class="role-pill">${escapeHtml(schema.category || 'Widget')}</span><span class="role-pill">官方索引</span></div><a href="${docs}" target="_blank" rel="noopener">官方文档 ↗</a></div><div class="alert info">此类型已收录到官方 Widget 索引，但当前版本暂未提供专属字段表单。请在下方“Widget 其他配置（YAML 映射）”中填写除 <code>type</code> 以外的官方配置字段；连接测试当前仅做配置级校验。</div>`;
        return;
      }
      const fields = schema.fields || [];
      const rows = fields.map((field) => {
        const name = String(field.name || '');
        const label = escapeHtml(field.label || name);
        const value = values[name] ?? '';
        const required = field.required ? '<em class="required-mark">必填</em>' : '';
        const help = field.help
          ? `<small class="field-help">${escapeHtml(field.help)}</small>`
          : '<small class="field-help empty" aria-hidden="true">占位</small>';
        const fieldLabel = `<span class="widget-schema-field-label">${label}${required}</span>`;
        const baseName = `widgets_${slot}_field_${name}`;
        if (field.kind === 'secret') {
          const placeholder = secretSaved[name] ? '已保存；留空保持原值' : (field.placeholder || '没有则留空');
          return `<label class="widget-schema-field">${fieldLabel}<input type="password" name="${escapeHtml(baseName)}" data-widget-field-name="${escapeHtml(name)}" placeholder="${escapeHtml(placeholder)}" autocomplete="new-password">${help}</label>`;
        }
        if (field.kind === 'bool') {
          const current = value === true ? 'true' : value === false ? 'false' : '';
          return `<label class="widget-schema-field">${fieldLabel}<select name="${escapeHtml(baseName)}" data-widget-field-name="${escapeHtml(name)}"><option value="" ${current === '' ? 'selected' : ''}>使用 Homepage 默认值</option><option value="true" ${current === 'true' ? 'selected' : ''}>true</option><option value="false" ${current === 'false' ? 'selected' : ''}>false</option></select>${help}</label>`;
        }
        if (field.kind === 'yaml') {
          return `<label class="widget-schema-field widget-schema-field-yaml span-2">${fieldLabel}<textarea name="${escapeHtml(baseName)}" data-widget-field-name="${escapeHtml(name)}" rows="${Number(field.rows || 6)}" spellcheck="false" placeholder="${escapeHtml(field.placeholder || '')}">${escapeHtml(value)}</textarea>${help}</label>`;
        }
        if (field.kind === 'select') {
          const options = (field.options || []).map((option) => `<option value="${escapeHtml(option)}" ${String(value) === String(option) ? 'selected' : ''}>${escapeHtml(option)}</option>`).join('');
          return `<label class="widget-schema-field">${fieldLabel}<select name="${escapeHtml(baseName)}" data-widget-field-name="${escapeHtml(name)}"><option value="">使用默认值</option>${options}</select>${help}</label>`;
        }
        const inputMode = field.kind === 'number' ? ' inputmode="decimal"' : '';
        return `<label class="widget-schema-field">${fieldLabel}<input name="${escapeHtml(baseName)}" data-widget-field-name="${escapeHtml(name)}" value="${escapeHtml(value)}" placeholder="${escapeHtml(field.placeholder || '')}"${inputMode}>${help}</label>`;
      }).join('');
      const allowed = schema.allowed_fields || [];
      const fieldPicker = allowed.length ? `<div class="widget-field-picker span-2"><div class="field-picker-head"><strong>显示字段</strong><span>Homepage 最多显示 4 项；不选择则使用官方默认字段。</span></div><div class="checkbox-row">${allowed.map((name) => `<label class="checkbox compact-check"><input type="checkbox" name="widgets_${slot}_fields" value="${escapeHtml(name)}" ${selectedFields.has(name) ? 'checked' : ''}><span>${escapeHtml(name)}</span></label>`).join('')}</div></div>` : '';
      const notice = schema.notice ? `<div class="alert info span-2">${escapeHtml(schema.notice)}</div>` : '';
      container.innerHTML = `<div class="widget-schema-head"><div><strong>${escapeHtml(schema.label)}</strong><span class="role-pill">${escapeHtml(schema.category || 'Widget')}</span></div><a href="${escapeHtml(schema.docs || '#')}" target="_blank" rel="noopener">官方文档 ↗</a></div><div class="form-grid two">${rows}${fieldPicker}${notice}</div>`;
    };

    const collectWidgetConfig = (block) => {
      const config = {};
      $$('[data-widget-field-name]', block).forEach((input) => { config[input.dataset.widgetFieldName] = input.value; });
      return config;
    };

    const bindWidgetBlock = (block, initial = null) => {
      const typeInput = $('[data-widget-type]', block);
      const testButton = $('[data-widget-test]', block);
      const result = $('[data-widget-test-result]', block);
      renderWidgetFields(block, initial || initialData(block));
      typeInput?.addEventListener('change', () => renderWidgetFields(block, { fields: {}, secret_saved: {}, selected_fields: [] }));
      typeInput?.addEventListener('input', () => {
        const type = typeInput.value.trim().toLowerCase();
        if (catalog[type]) renderWidgetFields(block, { fields: {}, secret_saved: {}, selected_fields: [] });
      });
      $('[data-widget-remove]', block)?.addEventListener('click', () => { block.remove(); syncWidgetSlots(); });
      $('[data-widget-up]', block)?.addEventListener('click', () => {
        const previous = block.previousElementSibling;
        if (previous) list.insertBefore(block, previous);
        syncWidgetSlots();
      });
      $('[data-widget-down]', block)?.addEventListener('click', () => {
        const next = block.nextElementSibling;
        if (next) list.insertBefore(next, block);
        syncWidgetSlots();
      });
      testButton?.addEventListener('click', async () => {
        const type = (typeInput?.value || '').trim().toLowerCase();
        if (!type) { window.alert('请先选择 Widget 类型。'); return; }
        testButton.disabled = true;
        testButton.textContent = '测试中...';
        if (result) { result.hidden = false; result.className = 'widget-test-result testing'; result.textContent = '正在从 Homepage Admin 容器测试 API 连接...'; }
        try {
          const response = await fetch('/api/widgets/test', {
            method: 'POST',
            headers: {'content-type': 'application/json', 'x-csrf-token': csrf()},
            body: JSON.stringify({
              type,
              config: collectWidgetConfig(block),
              original_index: Number($('[data-widget-original-index]', block)?.value || -1),
              group_index: Number(sourceGroup || 0),
              item_index: sourceItem,
            }),
          });
          const data = await response.json();
          if (!response.ok || !data.ok) throw new Error(data.error || '连接测试失败');
          const metrics = (data.metrics || []).map((metric) => `<span><b>${escapeHtml(metric.label)}</b>${escapeHtml(metric.value)}</span>`).join('');
          if (result) { result.className = 'widget-test-result success'; result.innerHTML = `<strong>✓ ${escapeHtml(data.message)}</strong>${metrics ? `<div class="test-metrics">${metrics}</div>` : ''}<small>测试级别：${escapeHtml(data.level || 'deep')}</small>`; }
        } catch (error) {
          if (result) { result.className = 'widget-test-result danger'; result.innerHTML = `<strong>✕ ${escapeHtml(error.message)}</strong>`; }
        } finally {
          testButton.disabled = false;
          testButton.textContent = '测试连接';
        }
      });
    };

    $$('[data-service-widget]', serviceEditor).forEach((block) => bindWidgetBlock(block));
    $('[data-widget-add]', serviceEditor)?.addEventListener('click', () => {
      if (!template || !list) return;
      const slot = nextSlot++;
      const html = template.innerHTML.replaceAll('__INDEX__', String(slot));
      const wrapper = document.createElement('div');
      wrapper.innerHTML = html.trim();
      const block = wrapper.firstElementChild;
      list.appendChild(block);
      bindWidgetBlock(block, {type:'', fields:{}, secret_saved:{}, selected_fields:[], extra:'', original_index:-1});
      syncWidgetSlots();
      $('[data-widget-type]', block)?.focus();
    });
    syncWidgetSlots();

    // Save-before-diff flow. New secret values are posted to the preview endpoint, but the
    // returned diff is generated from masked YAML and never echoes them back.
    const dialog = $('[data-diff-dialog]');
    const output = $('[data-diff-output]', dialog || document);
    let bypassDiff = false;
    const previewDiff = async () => {
      syncWidgetSlots();
      if (output) output.textContent = '正在生成...';
      dialog?.showModal();
      try {
        const response = await fetch('/api/services/preview', { method: 'POST', body: new FormData(serviceEditor) });
        const data = await response.json();
        if (!response.ok || !data.ok) throw new Error(data.error || '无法生成变更预览');
        if (output) output.textContent = data.diff;
        dialog?.classList.toggle('no-change', !data.changed);
      } catch (error) {
        if (output) output.textContent = `预览失败：${error.message}`;
      }
    };
    $('[data-service-preview]', serviceEditor)?.addEventListener('click', previewDiff);
    serviceEditor.addEventListener('submit', (event) => {
      if (bypassDiff) return;
      event.preventDefault();
      previewDiff();
    });
    $$('[data-diff-close]', dialog || document).forEach((button) => button.addEventListener('click', () => dialog?.close()));
    $('[data-diff-confirm]', dialog || document)?.addEventListener('click', () => {
      bypassDiff = true;
      syncWidgetSlots();
      dialog?.close();
      serviceEditor.submit();
    });
  }


  // v0.3.0 advanced editor save-before-diff.
  const yamlDiffForm = $('[data-yaml-diff-form]');
  if (yamlDiffForm) {
    const dialog = $('[data-yaml-diff-dialog]');
    const output = $('[data-yaml-diff-output]', dialog || document);
    const filename = yamlDiffForm.dataset.yamlFilename;
    let bypass = false;
    const preview = async () => {
      if (output) output.textContent = '正在校验并生成 Diff...';
      dialog?.showModal();
      try {
        const response = await fetch(`/api/yaml/${encodeURIComponent(filename)}/diff`, {method:'POST', body:new FormData(yamlDiffForm)});
        const data = await response.json();
        if (!response.ok || !data.ok) throw new Error(data.error || '预览失败');
        if (output) output.textContent = data.diff;
      } catch (error) {
        if (output) output.textContent = `预览失败：${error.message}`;
      }
    };
    $('[data-yaml-preview]', yamlDiffForm)?.addEventListener('click', preview);
    yamlDiffForm.addEventListener('submit', (event) => {
      if (bypass) return;
      event.preventDefault();
      preview();
    });
    $$('[data-yaml-diff-close]', dialog || document).forEach((button) => button.addEventListener('click', () => dialog?.close()));
    $('[data-yaml-diff-confirm]', dialog || document)?.addEventListener('click', () => { bypass = true; dialog?.close(); yamlDiffForm.submit(); });
  }

  // Render ISO timestamps in the browser's local timezone. The Schema cache
  // stores UTC so it is unambiguous across containers and hosts.
  $$('[data-local-datetime]').forEach((node) => {
    const raw = node.getAttribute('datetime') || node.textContent || '';
    const parsed = new Date(raw);
    if (Number.isNaN(parsed.getTime())) return;
    try {
      node.textContent = new Intl.DateTimeFormat(undefined, {
        year: 'numeric', month: '2-digit', day: '2-digit',
        hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false,
      }).format(parsed);
      node.title = `UTC: ${raw}`;
    } catch (_) {}
  });

  // v0.3.6 manual Widget Schema sync: start a background job and show real progress
  // while official documents are downloaded, parsed, merged, and written to /data.
  const schemaSyncForm = $('[data-schema-sync-form]');
  if (schemaSyncForm) {
    const button = $('[data-schema-sync-button]', schemaSyncForm);
    const panel = $('[data-schema-sync-progress]');
    const stageNode = $('[data-schema-sync-stage]', panel || document);
    const percentNode = $('[data-schema-sync-percent]', panel || document);
    const barNode = $('[data-schema-sync-bar]', panel || document);
    const messageNode = $('[data-schema-sync-message]', panel || document);
    const counterNode = $('[data-schema-sync-counter]', panel || document);
    const stageLabels = {
      queued: '等待开始', waiting: '准备同步', listing: '读取目录', documents: '解析文档',
      registry: '读取注册表', merge: '合并 Schema', finalize: '整理结果', cache: '写入缓存',
      complete: '同步完成', error: '同步失败',
    };
    let pollTimer = null;

    const renderSyncState = (state) => {
      if (!panel) return;
      panel.hidden = false;
      panel.classList.toggle('success', state.stage === 'complete' && !state.running);
      panel.classList.toggle('danger', state.stage === 'error');
      const percent = Math.max(0, Math.min(100, Number(state.percent || 0)));
      if (stageNode) stageNode.textContent = stageLabels[state.stage] || '正在同步';
      if (percentNode) percentNode.textContent = `${percent}%`;
      if (barNode) barNode.style.width = `${percent}%`;
      if (messageNode) messageNode.textContent = state.message || '正在同步…';
      if (counterNode) {
        const current = Number(state.current || 0);
        const total = Number(state.total || 0);
        counterNode.textContent = total > 0 ? `进度 ${current} / ${total}` : '';
      }
    };

    const finishPolling = (state) => {
      if (pollTimer) { window.clearTimeout(pollTimer); pollTimer = null; }
      if (button) { button.disabled = false; button.textContent = '立即同步官方 Schema'; }
      if (state.stage === 'complete' && !state.error) {
        window.setTimeout(() => {
          const result = state.result || {};
          const message = `官方 Widget Schema 已同步：${result.widget_count || 0} 个 Widget，自动字段 ${result.generated_field_count || 0} 个。`;
          window.location.href = `/widget-schema?ok=${encodeURIComponent(message)}`;
        }, 650);
      }
    };

    const pollSync = async () => {
      try {
        const response = await fetch('/api/widget-schema/sync/status', {headers: {'accept': 'application/json'}});
        const state = await response.json();
        if (!response.ok || !state.ok) throw new Error(state.error || '无法读取同步进度');
        renderSyncState(state);
        if (!state.running) { finishPolling(state); return; }
        pollTimer = window.setTimeout(pollSync, 450);
      } catch (error) {
        renderSyncState({stage: 'error', message: error.message, percent: 0, running: false});
        finishPolling({stage: 'error', error: error.message});
      }
    };

    schemaSyncForm.addEventListener('submit', async (event) => {
      event.preventDefault();
      if (button) { button.disabled = true; button.textContent = '同步中…'; }
      renderSyncState({stage: 'queued', message: '正在启动同步任务…', percent: 0, running: true});
      try {
        const response = await fetch('/api/widget-schema/sync/start', {
          method: 'POST',
          headers: {'content-type': 'application/json', 'x-csrf-token': csrf()},
          body: '{}',
        });
        const state = await response.json();
        if (!response.ok || !state.ok) throw new Error(state.error || '无法启动同步任务');
        renderSyncState(state);
        pollSync();
      } catch (error) {
        renderSyncState({stage: 'error', message: error.message, percent: 0, running: false});
        finishPolling({stage: 'error', error: error.message});
      }
    });
  }

  // Widget Schema schedule editor: support interval or a daily wall-clock time.
  const schemaSchedule = $('[data-schema-schedule]');
  if (schemaSchedule) {
    const mode = $('[data-schema-schedule-mode]', schemaSchedule);
    const intervalField = $('[data-schema-interval]', schemaSchedule);
    const dailyField = $('[data-schema-daily-time]', schemaSchedule);
    const timezoneField = $('[data-schema-timezone]', schemaSchedule);
    const timezoneInput = $('[data-schema-timezone-input]', schemaSchedule);
    const refreshScheduleFields = () => {
      const daily = mode?.value === 'daily';
      if (intervalField) intervalField.hidden = daily;
      if (dailyField) dailyField.hidden = !daily;
      if (timezoneField) timezoneField.hidden = !daily;
    };
    mode?.addEventListener('change', refreshScheduleFields);
    $('[data-use-browser-timezone]', schemaSchedule)?.addEventListener('click', () => {
      const zone = Intl.DateTimeFormat().resolvedOptions().timeZone;
      if (timezoneInput && zone) timezoneInput.value = zone;
    });
    refreshScheduleFields();
  }

  // v0.3.7 Proxmox bind helper: surface Docker/Proxmox conflicts before saving.
  document.querySelectorAll('[data-proxmox-bind-form]').forEach((form) => {
    const select = form.querySelector('[data-proxmox-service-select]');
    const group = form.querySelector('input[name="group_index"]');
    const item = form.querySelector('input[name="item_index"]');
    const conflict = form.querySelector('[data-proxmox-docker-conflict]');
    const conflictLabel = form.querySelector('[data-proxmox-docker-label]');
    const refresh = () => {
      const option = select?.selectedOptions?.[0];
      const parts = (select?.value || '').split(':');
      if (group) group.value = parts[0] || '';
      if (item) item.value = parts[1] || '';
      const hasDocker = option?.dataset?.hasDocker === '1';
      if (conflict) conflict.hidden = !hasDocker;
      if (conflictLabel) conflictLabel.textContent = option?.dataset?.dockerLabel || '';
    };
    select?.addEventListener('change', refresh);
    form.addEventListener('submit', (event) => {
      refresh();
      if (!group?.value || !item?.value) {
        event.preventDefault();
        window.alert('请选择要关联的 Homepage 服务');
      }
    });
    refresh();
  });

  // v0.3.2 global back-to-top control for long discovery / Widget pages.
  const backToTop = $('[data-back-to-top]');
  if (backToTop) {
    const updateBackToTop = () => { backToTop.hidden = window.scrollY < 520; };
    window.addEventListener('scroll', updateBackToTop, { passive: true });
    backToTop.addEventListener('click', () => window.scrollTo({ top: 0, behavior: 'smooth' }));
    updateBackToTop();
  }

})();

// v0.4.2 compatibility helpers for Docker host editor and delete wizard.
(() => {
  const renderResult = (target, ok, message) => {
    if (!target) return;
    target.hidden = false;
    target.classList.toggle('ok', Boolean(ok));
    target.classList.toggle('error', !ok);
    target.textContent = message;
  };
  const testUrl = async (url, button, result) => {
    const original = button?.textContent || '';
    if (button) { button.disabled = true; button.textContent = '测试中…'; }
    renderResult(result, true, '正在连接 Docker API…');
    try {
      const body = new URLSearchParams({
        csrf: document.body.dataset.csrf || '',
        url,
        homepage_server: 'test-server',
        public_host: '',
      });
      const response = await fetch('/api/docker/hosts/test', {method: 'POST', body});
      const payload = await response.json();
      if (!response.ok || !payload.ok) throw new Error(payload.message || '连接测试失败');
      renderResult(result, true, payload.message);
    } catch (error) {
      renderResult(result, false, error.message || String(error));
    } finally {
      if (button) { button.disabled = false; button.textContent = original; }
    }
  };

  const form = document.querySelector('[data-docker-yaml-host-form]');
  if (form) {
    const mode = form.querySelector('[data-docker-yaml-mode]');
    const remotes = [...form.querySelectorAll('[data-docker-yaml-remote]')];
    const sockets = [...form.querySelectorAll('[data-docker-yaml-socket]')];
    const syncMode = () => {
      const socketMode = mode?.value === 'socket';
      remotes.forEach((el) => { el.hidden = socketMode; });
      sockets.forEach((el) => { el.hidden = !socketMode; });
    };
    mode?.addEventListener('change', syncMode);
    syncMode();

    const testButton = form.querySelector('[data-docker-yaml-form-test]');
    const result = form.querySelector('[data-docker-yaml-form-result]');
    testButton?.addEventListener('click', async () => {
      if (mode?.value === 'socket') {
        renderResult(result, false, 'Socket 模式不能由 Homepage Admin 直接测试；建议使用只读 Docker Socket Proxy。');
        return;
      }
      const host = form.querySelector('[data-docker-yaml-host]')?.value.trim() || '';
      const port = form.querySelector('[data-docker-yaml-port]')?.value.trim() || '';
      const protocol = form.querySelector('[data-docker-yaml-protocol]')?.value || 'http';
      if (!host || !port) {
        renderResult(result, false, '请先填写 Host 与 Port。');
        return;
      }
      const displayHost = host.includes(':') && !host.startsWith('[') ? `[${host}]` : host;
      await testUrl(`${protocol}://${displayHost}:${port}`, testButton, result);
    });
  }

  const removeYaml = document.querySelector('[data-remove-docker-yaml]');
  const clearRefs = document.querySelector('[data-clear-docker-refs]');
  if (removeYaml && clearRefs) {
    const sync = () => {
      clearRefs.disabled = !removeYaml.checked;
      if (!removeYaml.checked) clearRefs.checked = false;
    };
    removeYaml.addEventListener('change', sync);
    sync();
  }

  // v0.4.6 settings workspace.
  const settingsEditor = document.querySelector('[data-settings-editor]');
  if (settingsEditor) {
    const provider = settingsEditor.querySelector('[data-quicklaunch-provider]');
    const customPanel = settingsEditor.querySelector('[data-quicklaunch-custom]');
    const syncQuicklaunch = () => {
      if (customPanel) customPanel.hidden = provider?.value !== 'custom';
    };
    provider?.addEventListener('change', syncQuicklaunch);
    syncQuicklaunch();

    const backgroundInput = settingsEditor.querySelector('[data-background-image]');
    const backgroundPreview = settingsEditor.querySelector('[data-background-preview]');
    const syncBackgroundPreview = () => {
      const value = backgroundInput?.value.trim() || '';
      if (!backgroundPreview) return;
      backgroundPreview.hidden = !value;
      backgroundPreview.style.backgroundImage = value ? `url(${JSON.stringify(value)})` : '';
    };
    backgroundInput?.addEventListener('input', syncBackgroundPreview);
    syncBackgroundPreview();

    const cardBlur = settingsEditor.querySelector('[data-card-blur]');
    const backgroundFilters = [...settingsEditor.querySelectorAll('[data-background-filter]')];
    const compatWarning = settingsEditor.querySelector('[data-background-compat]');
    const hasBackgroundFilter = () => backgroundFilters.some((control) => {
      const value = (control.value || '').trim();
      if (control.name === 'background_blur_mode') return !['', '__unset__', '__empty__'].includes(value);
      return value !== '';
    });
    const syncCompatibility = () => {
      if (compatWarning) compatWarning.hidden = !(cardBlur?.value && hasBackgroundFilter());
    };
    cardBlur?.addEventListener('change', syncCompatibility);
    backgroundFilters.forEach((control) => {
      control.addEventListener('change', syncCompatibility);
      control.addEventListener('input', syncCompatibility);
    });
    syncCompatibility();

    const layoutList = settingsEditor.querySelector('[data-settings-layout-list]');
    const layoutRows = () => [...settingsEditor.querySelectorAll('[data-settings-layout-row]')];
    const reindexLayout = () => {
      layoutRows().forEach((row, index) => {
        row.querySelectorAll('[name]').forEach((field) => {
          if (/^layout_\d+_/.test(field.name)) field.name = field.name.replace(/^layout_\d+_/, `layout_${index}_`);
        });
      });
    };
    reindexLayout();

    let draggedLayout = null;
    layoutRows().forEach((row) => {
      row.addEventListener('dragstart', (event) => {
        if (!event.target.closest('[data-layout-drag]')) {
          event.preventDefault();
          return;
        }
        draggedLayout = row;
        row.classList.add('dragging');
        event.dataTransfer.effectAllowed = 'move';
      });
      row.addEventListener('dragend', () => {
        row.classList.remove('dragging');
        layoutRows().forEach((item) => item.classList.remove('drag-over'));
        draggedLayout = null;
        reindexLayout();
      });
      row.addEventListener('dragover', (event) => {
        if (!draggedLayout || draggedLayout === row) return;
        event.preventDefault();
        row.classList.add('drag-over');
      });
      row.addEventListener('dragleave', () => row.classList.remove('drag-over'));
      row.addEventListener('drop', (event) => {
        if (!draggedLayout || draggedLayout === row || !layoutList) return;
        event.preventDefault();
        row.classList.remove('drag-over');
        const rect = row.getBoundingClientRect();
        const before = event.clientY < rect.top + rect.height / 2;
        layoutList.insertBefore(draggedLayout, before ? row : row.nextSibling);
        reindexLayout();
      });
    });

    const dialog = document.querySelector('[data-settings-diff-dialog]');
    const output = dialog?.querySelector('[data-settings-diff-output]');
    let bypassPreview = false;
    const previewSettings = async () => {
      reindexLayout();
      if (output) output.textContent = '正在校验并生成 Diff...';
      dialog?.showModal();
      try {
        const response = await fetch('/api/settings/preview', {method:'POST', body:new FormData(settingsEditor)});
        const data = await response.json();
        if (!response.ok || !data.ok) throw new Error(data.error || '无法生成变更预览');
        if (output) output.textContent = data.diff;
        dialog?.classList.toggle('no-change', !data.changed);
      } catch (error) {
        if (output) output.textContent = `预览失败：${error.message}`;
      }
    };
    settingsEditor.querySelector('[data-settings-preview]')?.addEventListener('click', previewSettings);
    settingsEditor.addEventListener('submit', (event) => {
      reindexLayout();
      if (bypassPreview) return;
      event.preventDefault();
      previewSettings();
    });
    dialog?.querySelectorAll('[data-settings-diff-close]').forEach((button) => button.addEventListener('click', () => dialog.close()));
    dialog?.querySelector('[data-settings-diff-confirm]')?.addEventListener('click', () => {
      bypassPreview = true;
      reindexLayout();
      dialog.close();
      settingsEditor.submit();
    });
  }

})();
