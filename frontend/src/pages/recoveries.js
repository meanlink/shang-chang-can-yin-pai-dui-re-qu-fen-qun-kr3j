import {api, shiftQuery, state} from '../state.js';
import {badge, empty, header, input, readForm, stamp, text} from '../ui.js';
import {bindEvidence, evidence, followingSlot, noteOptions, slotField} from './recovery-evidence.js';

const labels = {open: '待跟进', monitoring: '复查中', closed: '已结案'};

function openForm(sources) {
  if (!sources.length) return empty('该小时没有尚待立单的孤立长队或已解除控流的热区成员。');
  return `<form class="stack" id="open-recovery"><label>门店和依据<select name="source" required>${sources.map((source, index) =>
    `<option value="${index}">${text(source.code)} · ${text(source.name)} · ${source.surge_id ? `控流 #${source.surge_id}` : '孤立长队'}</option>`).join('')}</select></label>
    ${input('待处理的服务问题', 'note', 'text', noteOptions)}<button>建立恢复工单</button></form>`;
}

function recoveryCard(row, role) {
  return `<article class="peak-card" data-recovery="${row.id}"><div class="section-line"><h3>${text(row.name)} · ${text(row.code)}</h3>
    ${badge(labels[row.status], row.status === 'closed' ? 'good' : 'warm')}</div>
    <p class="peak-caption">工单 #${row.id} · ${row.surge_id ? `控流 #${row.surge_id}` : '孤立长队'} · 封存中位 ${text(row.source_queue)} 人</p>
    <p>${text(row.issue_note)}</p>
    ${row.action_note ? `<p class="peak-outcome"><b>${stamp(row.action_slot)} 执行</b> ${text(row.action_note)}</p>` : ''}
    ${row.status === 'open' && role === 'steward' ? `<form class="stack apply-action">${slotField('措施执行窗口', followingSlot(state.hour, 60))}
      ${input('已执行的门店措施', 'note', 'text', noteOptions)}<button>登记措施并开始复查</button></form>` : ''}
    ${evidence(row, role)}
    ${row.close_ready && role === 'operator' ? `<form class="stack close-recovery">${input('结案说明', 'note', 'text', noteOptions)}
      <button>核准服务恢复</button></form>` : ''}
    ${row.close_note ? `<p class="peak-outcome">${text(row.close_note)}</p>` : ''}</article>`;
}

export async function recoveries() {
  const model = await api(`/recoveries?${shiftQuery()}`);
  const role = state.session.user.role;
  return {
    html: `${header('门店跟进', '服务恢复', '为孤立长队和已解除控流的热区门店跟进取餐组织、出餐节奏及队尾回落。')}
      <div class="split"><section class="panel"><div class="section-line"><h2>恢复工单</h2><a href="#surges">查看临时控流</a></div>
      ${model.cases.length ? model.cases.map(row => recoveryCard(row, role)).join('') : empty('该小时还没有服务恢复工单。')}</section>
      <aside class="side-note"><h2>${role === 'operator' ? '建立工单' : '复查规则'}</h2><p>措施执行后，最近两个连续的 15 分钟窗口均少于 8 人，运营才能结案。</p>
      ${role === 'operator' ? openForm(model.sources) : ''}<p><a href="#handoffs">查看交接简报</a></p></aside></div>`,
    bind(root, action) {
      const open = root.querySelector('#open-recovery');
      if (open) open.onsubmit = event => {
        event.preventDefault();
        const values = readForm(open);
        const {store_id, surge_id} = model.sources[values.source];
        action(() => api('/recoveries', {floor: state.floor, hour_start: state.hour, store_id, surge_id, note: values.note}), '服务恢复工单已建立', open);
      };
      for (const card of root.querySelectorAll('[data-recovery]')) {
        const path = `/recoveries/${card.dataset.recovery}`;
        const apply = card.querySelector('.apply-action');
        if (apply) apply.onsubmit = event => {
          event.preventDefault();
          action(() => api(`${path}/action`, readForm(apply)), '已登记门店措施，开始复查', apply);
        };
        bindEvidence(card, action, path);
        const close = card.querySelector('.close-recovery');
        if (close) close.onsubmit = event => {
          event.preventDefault();
          action(() => api(`${path}/close`, readForm(close)), '门店服务恢复已结案', close);
        };
      }
    },
  };
}
