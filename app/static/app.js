(() => {
  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

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

  let dragState = null;
  $$('.item-card[draggable=true]').forEach((card) => {
    card.addEventListener('dragstart', (event) => {
      dragState = {
        source_group: Number(card.dataset.groupIndex),
        source_index: Number(card.dataset.itemIndex),
      };
      card.classList.add('dragging');
      event.dataTransfer.effectAllowed = 'move';
    });
    card.addEventListener('dragend', () => {
      card.classList.remove('dragging');
      $$('.drop-zone').forEach((zone) => zone.classList.remove('drag-over'));
    });
  });

  $$('.drop-zone').forEach((zone) => {
    zone.addEventListener('dragover', (event) => {
      event.preventDefault();
      zone.classList.add('drag-over');
    });
    zone.addEventListener('dragleave', (event) => {
      if (!zone.contains(event.relatedTarget)) zone.classList.remove('drag-over');
    });
    zone.addEventListener('drop', async (event) => {
      event.preventDefault();
      zone.classList.remove('drag-over');
      if (!dragState) return;
      const cards = $$('.item-card', zone).filter((card) => !card.classList.contains('dragging'));
      let targetIndex = cards.length;
      const targetCard = event.target.closest('.item-card');
      if (targetCard) {
        const rect = targetCard.getBoundingClientRect();
        const before = event.clientY < rect.top + rect.height / 2;
        const cardPosition = cards.indexOf(targetCard);
        targetIndex = Math.max(0, cardPosition + (before ? 0 : 1));
      }
      const kind = zone.dataset.kind;
      const payload = {
        ...dragState,
        target_group: Number(zone.dataset.groupIndex),
        target_index: targetIndex,
      };
      try {
        const response = await fetch(`/api/${kind}/move`, {
          method: 'POST',
          headers: {
            'content-type': 'application/json',
            'x-csrf-token': document.body.dataset.csrf,
          },
          body: JSON.stringify(payload),
        });
        const data = await response.json();
        if (!response.ok || !data.ok) throw new Error(data.error || '排序失败');
        window.location.reload();
      } catch (error) {
        window.alert(error.message);
      } finally {
        dragState = null;
      }
    });
  });
})();
