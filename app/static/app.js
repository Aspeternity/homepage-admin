(() => {
  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
  const csrf = () => document.body.dataset.csrf || '';

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
})();
