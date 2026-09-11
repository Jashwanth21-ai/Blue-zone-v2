'use strict';
// Keep previously shared workspace hash URLs working after adding the public home.
const oldRoute = location.hash.slice(1).split('/')[0];
if (['dashboard','paths','labs','challenges','progress','tutor','admin','settings','unit'].includes(oldRoute)) {
  location.replace('/app' + location.hash);
}

const tabs = Array.from(document.querySelectorAll('[data-step]'));
function selectStep(step, focus = false) {
  tabs.forEach(tab => {
    const active = tab.dataset.step === step;
    tab.classList.toggle('is-active', active);
    tab.setAttribute('aria-selected', String(active));
    tab.tabIndex = active ? 0 : -1;
    document.getElementById(tab.getAttribute('aria-controls')).hidden = !active;
    if (active && focus) tab.focus();
  });
}
tabs.forEach((tab, i) => {
  tab.addEventListener('click', () => selectStep(tab.dataset.step));
  tab.addEventListener('keydown', event => {
    let next;
    if (event.key === 'ArrowRight') next = (i + 1) % tabs.length;
    if (event.key === 'ArrowLeft') next = (i - 1 + tabs.length) % tabs.length;
    if (event.key === 'Home') next = 0;
    if (event.key === 'End') next = tabs.length - 1;
    if (next !== undefined) {
      event.preventDefault();
      selectStep(tabs[next].dataset.step, true);
    }
  });
});
document.querySelectorAll('[data-go]').forEach(button => {
  button.addEventListener('click', () => selectStep(button.dataset.go, true));
});
document.querySelectorAll('[data-answer]').forEach(button => {
  button.addEventListener('click', () => {
    const correct = button.dataset.answer === '600';
    document.querySelectorAll('[data-answer]').forEach(option => option.classList.remove('correct', 'incorrect'));
    button.classList.add(correct ? 'correct' : 'incorrect');
    const feedback = document.getElementById('preview-feedback');
    feedback.classList.toggle('success', correct);
    feedback.textContent = correct
      ? 'Exactly. 600 gives the owner read + write, and everyone else no access. Ready for a full mission?'
      : 'Take another look. Read = 4 and write = 2. The group and others should each have 0 permissions.';
  });
});
