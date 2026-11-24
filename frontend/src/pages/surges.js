import {api, shiftQuery, state} from '../state.js';
import {badge, empty, header, input, readForm, text} from '../ui.js';

const labels = {planned: '待执行', active: '控流中', resolved: '已解除', cancelled: '已撤销'};
const modes = {meter_entry: '入口分批放行', stagger_pickup: '取餐错峰叫号'};
const noteOptions = 'required minlength="8" maxlength="200"';

function planForm(tasks) {
  if (!tasks.length) return empty('该小时没有可安排控流的在办疏导单。请先在客流疏导认领任务。');
  return `<form id="plan-surge" class="stack"><label>热区疏导单<select name="task_id" required>${tasks.map(task =>
    `<option value="${task.id}">#${task.id} · ${text(task.anchor)} · 起报 ${task.trigger_queue} 人</option>`).join('')}</select></label>
    <label>控流方式<select name="response_mode">${Object.entries(modes).map(([key, label]) =>
      `<option value="${key}">${label}</option>`).join('')}</select></label>
    ${input('当前队尾人数', 'reported_queue', 'number', 'required min="0" max="300"')}
    ${input('现场指令', 'note', 'text', noteOptions)}<button>下发控流方案</button></form>`;
}

function responseCard(row, user) {
  const canGuide = user.role === 'steward' && user.id === row.handled_by;
  return `<article class="peak-card" data-surge="${row.id}"><div class="section-line"><h3>${text(row.anchor)} · 热区 ${row.zone_number}</h3>
    ${badge(labels[row.status], row.status === 'resolved' ? 'good' : 'warm')}</div>
    <p class="peak-caption">控流 #${row.id} · 疏导 #${row.task_id} · ${modes[row.response_mode]}</p>
    <dl class="peak-metrics"><div><dt>封存中位</dt><dd>${text(row.baseline_queue)} 人</dd></div><div><dt>起报队尾</dt><dd>${row.reported_queue} 人</dd></div>
      <div><dt>${row.release_queue == null ? '解除上限' : '解除复测'}</dt><dd>${row.release_queue ?? row.release_limit} 人</dd></div></dl>
    <p>${text(row.plan_note)}</p>${row.outcome_note ? `<p class="peak-outcome">${text(row.outcome_note)}</p>` : ''}
    ${row.status === 'planned' && canGuide ? `<button class="activate-surge">开始执行控流</button>` : ''}
    ${row.status === 'planned' && user.role === 'operator' ? `<details><summary>撤销方案</summary><form class="stack cancel-surge">
      ${input('撤销原因', 'note', 'text', noteOptions)}<button>确认撤销</button></form></details>` : ''}
    ${row.status === 'active' && canGuide ? `<form class="stack release-surge">${input('解除复测人数', 'queue_count', 'number', 'required min="0" max="300"')}
      ${input('解除说明', 'note', 'text', noteOptions)}<button>提交复测并解除</button></form>` : ''}
    ${row.status === 'resolved' ? '<a href="#recoveries">查看门店服务恢复</a>' : ''}</article>`;
}

export async function surges() {
  const model = await api(`/surges?${shiftQuery()}`);
  const user = state.session.user;
  return {
    html: `${header('高峰运营', '临时控流', '锚点队尾显著高于封存中位数时，为在办疏导单部署分批放行或错峰叫号。')}
      <div class="split"><section class="panel"><div class="section-line"><h2>控流记录</h2><a href="#tasks">查看客流疏导</a></div>
      ${model.responses.length ? model.responses.map(row => responseCard(row, user)).join('') : empty('该小时还没有控流记录。')}</section>
      <aside class="side-note"><h2>${user.role === 'operator' ? '下发方案' : '执行规则'}</h2>
      <p>起报至少 25 人，同时比封存中位数多 5 人。复测回到基线以内后，可解除控流并继续疏导。</p>
      ${user.role === 'operator' ? planForm(model.tasks) : '<p>认领原疏导单的现场人员负责启动和解除控流。</p>'}</aside></div>`,
    bind(root, action) {
      const plan = root.querySelector('#plan-surge');
      if (plan) plan.onsubmit = event => {
        event.preventDefault();
        const values = readForm(plan);
        action(() => api('/surges', {...values, task_id: Number(values.task_id), reported_queue: Number(values.reported_queue)}), '已下发控流方案', plan);
      };
      for (const card of root.querySelectorAll('[data-surge]')) {
        const path = `/surges/${card.dataset.surge}`;
        const activate = card.querySelector('.activate-surge');
        if (activate) activate.onclick = () => action(() => api(`${path}/activate`, {}), '现场控流已启动', activate);
        const release = card.querySelector('.release-surge');
        if (release) release.onsubmit = event => {
          event.preventDefault();
          const values = readForm(release);
          action(() => api(`${path}/release`, {...values, queue_count: Number(values.queue_count)}), '临时控流已解除', release);
        };
        const cancel = card.querySelector('.cancel-surge');
        if (cancel) cancel.onsubmit = event => {
          event.preventDefault();
          action(() => api(`${path}/cancel`, readForm(cancel)), '控流方案已撤销', cancel);
        };
      }
    },
  };
}
