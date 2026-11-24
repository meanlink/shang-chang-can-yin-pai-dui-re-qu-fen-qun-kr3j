import {api, shiftQuery, state} from '../state.js';
import {badge, clock, empty, header, hourLabel, input, readForm, table, text} from '../ui.js';

export async function windows() {
  const data = await api(`/observations?${shiftQuery()}`);
  const status = data.hour?.status || 'collecting';
  const editable = state.session.user.role === 'observer' && status === 'collecting' && data.stores.length;
  const offsets = ['00','15','30','45'];
  const sample = state.coverageSample;
  state.coverageSample = null;
  const rows = data.stores.map(store => {
    const recorded = data.observations.filter(window => window.store_id === store.id);
    return [`<b>${text(store.name)}</b><small>${text(store.code)}</small>`, ...offsets.map(offset => {
      const window = recorded.find(row => clock(row.window_start).slice(3) === offset);
      return window ? `<span class="counter" title="巡场员 ${text(window.username)}">${window.queue_count}</span>` : '<span class="missing">待采</span>';
    }), badge(`${recorded.length}/4`, recorded.length < 3 ? 'warm' : 'good')];
  });
  return {
    html: `${header('现场巡场', '排队采样', '每个门店每 15 分钟记录一次排队人数。点击右侧表单登记一个窗口。')}
      <div class="split"><section class="panel"><h2>15 分钟观测矩阵 ${badge(hourLabel[status], status === 'collecting' ? 'good' : 'warm')}</h2>
      ${rows.length ? table(['排队入口',...offsets.map(minute => `${state.hour.slice(11,13)}:${minute}`),'覆盖'], rows) : empty('先在门店档案中登记本层入口。')}
      <p class="minor under">单位为现场排队人数。有效分析至少需要同一门店的三个观测窗口。</p><a href="#coverage">查看缺测补采清单</a></section>
      <aside class="side-note"><h2>记录观测</h2>${editable ? `<form class="stack" id="add-window">
        <label>门店<select name="store_id">${data.stores.map(store => `<option value="${store.id}" ${String(store.id) === sample?.store ? 'selected' : ''}>${text(store.name)}</option>`).join('')}</select></label>
        <label>窗口起始<select name="minute">${offsets.map(minute => `<option value="${minute}" ${minute === sample?.minute ? 'selected' : ''}>${state.hour.slice(11,13)}:${minute}</option>`).join('')}</select></label>
        ${input('排队人数','queue_count','number','min="0" max="300" required')}<button>保存观测</button></form>` :
        empty(status === 'collecting' ? '有门店档案后，巡场采样账号可在这里登记窗口。' : '当前窗口已交给分析员，采样记录已封存。')}</aside></div>`,
    bind(root, action) {
      const form = root.querySelector('#add-window');
      form?.addEventListener('submit', event => {
        event.preventDefault();
        const row = readForm(form);
        action(() => api('/observations', {store_id: Number(row.store_id), queue_count: Number(row.queue_count),
          window_start: `${state.hour.slice(0,14)}${row.minute}`} ), '观测已保存', form);
      });
    },
  };
}
