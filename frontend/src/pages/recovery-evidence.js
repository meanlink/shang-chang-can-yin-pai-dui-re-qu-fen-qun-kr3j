import {api} from '../state.js';
import {badge, empty, input, readForm, stamp, table, text} from '../ui.js';

export const noteOptions = 'required minlength="8" maxlength="200"';

export function followingSlot(slot, minutes) {
  const wallTime = new Date(`${slot.slice(0, 16)}:00Z`);
  wallTime.setUTCMinutes(wallTime.getUTCMinutes() + minutes);
  return wallTime.toISOString().slice(0, 16);
}

export function slotField(label, firstSlot) {
  return input(label, 'slot_start', 'datetime-local', `required step="900" min="${text(firstSlot)}" value="${text(firstSlot)}"`);
}

export function evidence(row, role) {
  if (row.status === 'open') return '';
  const firstSlot = followingSlot(row.checks.at(-1)?.slot_start || row.action_slot, 15);
  return `<div class="peak-evidence"><h4>复查记录 ${row.close_ready ? badge('满足结案条件', 'good') : ''}</h4>
    ${row.checks.length ? table(['窗口', '队尾', '现场说明', '复查人'], row.checks.map(check => [
      stamp(check.slot_start), `${check.queue_count} 人`, text(check.note), text(check.username),
    ])) : empty('等待措施执行 15 分钟后的首次复查。')}
    ${row.status === 'monitoring' && role === 'steward' ? `<form class="stack record-check">
      <div class="pair">${slotField('复查窗口', firstSlot)}${input('复查队尾人数', 'queue_count', 'number', 'required min="0" max="300"')}</div>
      ${input('复查说明', 'note', 'text', noteOptions)}<button>保存复查</button></form>` : ''}</div>`;
}

export function bindEvidence(card, action, path) {
  const form = card.querySelector('.record-check');
  if (!form) return;
  form.onsubmit = event => {
    event.preventDefault();
    const values = readForm(form);
    action(() => api(`${path}/checks`, {...values, queue_count: Number(values.queue_count)}), '复查已记录', form);
  };
}
