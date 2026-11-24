import {api, state} from '../state.js';
import {empty, header, input, readForm, table, text} from '../ui.js';

export async function stores() {
  const data = await api(`/stores?floor=${state.floor}`);
  const operator = state.session.user.role === 'operator';
  return {
    html: `${header('租户与场地', '门店档案', '记录队尾入口的实测坐标和客流可暂时停留的位置。')}
      <div class="split"><section class="panel"><h2>${state.floor}F 门店名录 <span class="count">${data.length}</span></h2>
      ${data.length ? table(['编号','门店','排队入口（米）','临时等候点'], data.map(row => [
        `<b class="mono">${text(row.code)}</b>`, text(row.name), `${row.x} / ${row.y}`, text(row.staging_point),
      ])) : empty('本层暂无门店，可由楼层运营登记。')}</section>
      <aside class="side-note"><h2>${operator ? '登记门店' : '坐标口径'}</h2>
      ${operator ? `<form id="new-store" class="stack">${input('门店编号','code','text','required pattern="[A-Z0-9\\-]{2,16}"')}
        ${input('招牌名称','name','text','required maxlength="60"')}
        <div class="pair">${input('X（米）','x','number','min="0" max="120" required')}${input('Y（米）','y','number','min="0" max="64" required')}</div>
        ${input('临时等候点','staging_point','text','required maxlength="80"')}<button>保存档案</button></form>` :
        '<p>以楼层平面西北角为原点。夫妻店、堂食窗口和快闪柜台都以实际队尾入口作为采样位置。</p>'}
      <p class="minor">队列距离按同层平面直线距离计算。跨楼层入口独立登记。</p></aside></div>`,
    bind(root, action) {
      const form = root.querySelector('#new-store');
      form?.addEventListener('submit', event => {
        event.preventDefault();
        const values = readForm(form);
        action(() => api('/stores', {...values, floor: state.floor, x: Number(values.x), y: Number(values.y)}), '门店已登记', form);
      });
    },
  };
}
