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
        if (/^https?:\/\//i.test(icon)) imageUrl = icon;
        else if (/^sh-[a-z0-9._-]+$/i.test(icon)) {
          const slug = icon.slice(3).toLowerCase();
          imageUrl = `https://cdn.jsdelivr.net/gh/selfhst/icons/png/${encodeURIComponent(slug)}.png`;
        }
        previewIconFallback.textContent = icon
          ? icon.replace(/^sh-/, '').slice(0, 2).toUpperCase()
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

})();
