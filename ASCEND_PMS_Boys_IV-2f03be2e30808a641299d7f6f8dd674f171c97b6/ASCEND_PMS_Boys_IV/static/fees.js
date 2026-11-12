(() => {
  document.querySelectorAll('[data-currency-picker]').forEach(picker => {
    const select = picker.querySelector('[data-currency-select]');
    const other = picker.querySelector('[data-currency-other]');
    const input = other.querySelector('input');
    const update = () => { const active = select.value === 'OTHER'; other.hidden = !active; input.required = active; };
    select.addEventListener('change', update);
    update();
  });
  document.querySelectorAll('.fee-copy').forEach(button => button.addEventListener('click', async () => {
    const feedback = document.querySelector('.fee-copy-feedback');
    try { await navigator.clipboard.writeText(button.dataset.copy); feedback.textContent = 'Payment detail copied.'; }
    catch (_) { feedback.textContent = 'Could not copy automatically. Please select and copy the detail.'; }
  }));
  document.querySelectorAll('[data-fee-upload]').forEach(form => {
    const input = form.querySelector('[data-receipt-input]'), preview = form.querySelector('.fee-preview'), message = form.querySelector('.fee-upload-message'), button = form.querySelector('button[type=submit]');

    input.addEventListener('change', () => {

      preview.hidden = true; message.textContent = '';
      const file = input.files[0];
      input.setCustomValidity('');
      if (!file) return;
      if (file.size > 4000000 || !['image/jpeg','image/png','image/webp'].includes(file.type)) { input.setCustomValidity('Choose a JPG, PNG or WEBP image smaller than 4 MB.'); message.textContent = input.validationMessage; return; }
      const reader = new FileReader(); reader.onload = () => { preview.src = reader.result; preview.hidden = false; }; reader.readAsDataURL(file);
    });
    const drop = form.querySelector('.fee-upload');
    ['dragenter', 'dragover'].forEach(event => drop.addEventListener(event, e => { e.preventDefault(); }));
    drop.addEventListener('drop', e => {
      e.preventDefault();
      if (e.dataTransfer.files.length !== 1) { message.textContent = 'Please drop one receipt image.'; return; }
      input.files = e.dataTransfer.files; input.dispatchEvent(new Event('change', { bubbles: true }));
    });
    form.addEventListener('submit', e => {
      e.preventDefault(); if (!form.reportValidity() || button.disabled) return;
      const xhr = new XMLHttpRequest(); xhr.open('POST', form.action); button.disabled = true;
      xhr.upload.onprogress = e => { if (e.lengthComputable) message.textContent = 'Uploading: ' + Math.round(e.loaded / e.total * 100) + '%'; };
      xhr.onload = () => { if (xhr.status === 200 && xhr.responseURL && xhr.responseURL !== form.action) window.location.assign(xhr.responseURL); else { message.textContent = 'Upload failed. Please check your file and try again.'; button.disabled = false; } };
      xhr.onerror = () => { message.textContent = 'Network error. Check your connection before trying again.'; button.disabled = false; };
      xhr.send(new FormData(form));
    });
  });
})();
