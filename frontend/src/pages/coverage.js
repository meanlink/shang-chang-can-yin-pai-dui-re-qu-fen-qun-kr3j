import {api, shiftQuery, state} from '../state.js';
import {badge, empty, header, hourLabel, input, readForm, table, text} from '../ui.js';

const states = {open: '待补采', complete: '已补齐', waived: '已豁免'};
const minute = value => String(value).padStart(2, '0');

function operation(store, collecting, role) {
  if (!collecting) return '';
  if (role === 'operator' && store.needed && !store.order_id) {
    return `<button type="button" class="secondary" data-order="${store.id}">下发补采</button>`;
  }
  if (role === 'operator' && store.order_status === 'open') {
    return `<details><summary>登记豁免</summary><form class="stack" data-waive="${store.order_id}">
      ${input('豁免原因', 'note', 'text', 'required minlength="8" maxlength="200"')}<button>确认豁免</button></form></details>`;
  }
  if (role === 'observer' && store.order_status === 'open') {
    return `<a href="#windows" data-sample="${store.id}" data-minute="${minute(store.missing_minutes[0])}">录入缺测窗口</a>`;
  }
  return '';
}

export async function coverage() {
  const model = await api(`/coverage?${shiftQuery()}`);
  const role = state.session.user.role;
  const collecting = model.hour_status === 'collecting';
  const rows = model.stores.map(store => [
    `<b>${text(store.name)}</b><small>${text(store.code)}</small>`,
    store.missing_minutes.length ? store.missing_minutes.map(item => `<span class="minute-tag">${state.hour.slice(11,13)}:${minute(item)}</span>`).join(' ') : '齐全',
    store.needed ? `还差 ${store.needed} 个` : '已达到 3 个',
    store.order_status ? `${badge(states[store.order_status], store.order_status === 'complete' ? 'good' : 'warm')}${store.waiver_reason ? `<small>${text(store.waiver_reason)}</small>` : ''}` : '—',
    operation(store, collecting, role),
  ]);
  return {
    html: `${header('封存前检查', '缺测补采', '楼层运营下发补采后，由巡场补齐三个观测窗口。已下发的任务须完成或注明豁免才可封存。')}
      <section class="panel coverage-panel"><div class="section-line"><h2>门店窗口缺口 ${badge(hourLabel[model.hour_status], collecting ? 'warm' : 'good')}</h2>
      <a href="#windows">查看采样矩阵</a></div>
      ${rows.length ? table(['入口', '待采时点', '分析门槛', '补采状态', '操作'], rows) : empty('该楼层还没有排队入口。')}</section>`,
    bind(root, action) {
      root.querySelectorAll('[data-order]').forEach(button => {
        button.onclick = () => action(() => api('/coverage', {floor: state.floor, hour_start: state.hour,
          store_id: Number(button.dataset.order)}), '补采已下发', button);
      });
      root.querySelectorAll('[data-waive]').forEach(form => {
        form.onsubmit = event => {
          event.preventDefault();
          action(() => api(`/coverage/${form.dataset.waive}/waive`, readForm(form)), '已登记豁免', form);
        };
      });
      root.querySelectorAll('[data-sample]').forEach(link => {
        link.onclick = () => { state.coverageSample = {store: link.dataset.sample, minute: link.dataset.minute}; };
      });
    },
  };
}
