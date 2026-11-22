(() => {
  const root = document.getElementById('demo-app');
  if (!root) return;
  const tabs = [...root.querySelectorAll('[data-demo-tab]')];
  const panels = [...root.querySelectorAll('[data-demo-panel]')];
  function show(name) {
    if (!panels.some(panel => panel.dataset.demoPanel === name)) return;
    panels.forEach(panel => { panel.hidden = panel.dataset.demoPanel !== name; });
    tabs.forEach(tab => { if (tab.dataset.demoTab === name) tab.setAttribute('aria-current', 'page'); else tab.removeAttribute('aria-current'); });
  }
  tabs.forEach(tab => tab.addEventListener('click', () => show(tab.dataset.demoTab)));
  root.querySelector('[data-demo-open]').addEventListener('click', () => show('classes'));
  root.querySelector('[data-demo-lesson]').addEventListener('click', () => { root.querySelector('[data-demo-lesson-content]').hidden = false; });
  let solved = false;
  root.querySelectorAll('[data-demo-answer]').forEach(button => button.addEventListener('click', () => {
    const result = root.querySelector('[data-demo-result]');
    if (button.dataset.demoAnswer === 'right') {
      result.textContent = 'Correct! You earned 10 example points.';
      if (!solved) { root.querySelector('[data-demo-points]').textContent = '130'; root.querySelector('[data-demo-rank-points]').textContent = '130'; }
      solved = true;
    } else result.textContent = 'Not quite. Try again!';
  }));
  root.querySelector('[data-demo-reward]').addEventListener('click', () => { root.querySelector('[data-demo-reward-result]').textContent = 'Example request sent for review. No real reward was requested.'; });
  root.querySelector('[data-demo-fee]').addEventListener('click', () => { root.querySelector('[data-demo-fee-result]').textContent = 'Example status: awaiting academy review. No payment was submitted.'; });
  root.querySelector('[data-demo-ack]').addEventListener('click', () => { root.querySelector('[data-demo-ack-result]').textContent = 'Example response: Thank you — noted.'; });
})();
