import {api, shiftQuery, state} from '../state.js';
import {badge, empty, header, hourLabel, pointLabel, text} from '../ui.js';

function floorPlan(points, zones) {
  const marks = points.filter(point => point.kind !== 'insufficient');
  return `<div class="map" aria-label="排队入口平面图">
    <div class="map-caption">${state.floor}F 平面 · 120 × 64 m</div><div class="map-north">↑ 北</div>
    <div class="map-field">
      ${zones.map((zone, index) => {
        const members = marks.filter(point => point.hotspot_id === zone.id);
        const xs = members.map(point => point.x);
        const ys = members.map(point => point.y);
        const left = Math.max(0, Math.min(...xs) - 6);
        const top = Math.max(0, Math.min(...ys) - 9);
        const width = Math.min(120, Math.max(...xs) + 6) - left;
        const height = Math.min(64, Math.max(...ys) + 9) - top;
        return `<div class="map-zone" style="left:${left/1.2}%;top:${top/0.64}%;width:${width/1.2}%;height:${height/0.64}%"><span>热区 ${index + 1}</span></div>`;
      }).join('')}
      ${marks.map(point => `<div class="marker ${point.kind}" tabindex="0" data-store="${text(point.code)}" style="left:${point.x/1.2}%;top:${point.y/0.64}%" title="${text(point.name)} · ${pointLabel[point.kind]} · 中位 ${point.median_queue} 人"><i></i><span>${text(point.code.slice(-3))}</span></div>`).join('')}
    </div><div class="legend">${Object.entries(pointLabel).filter(([key]) => key !== 'insufficient').map(([key,label]) => `<span><i class="${key}"></i>${label}</span>`).join('')}</div></div>`;
}

export async function heat() {
  const data = await api(`/observations?${shiftQuery()}`);
  const hour = data.hour;
  const result = hour && hour.status !== 'collecting' ? await api(`/analyses/${hour.id}`) : null;
  const ready = result?.hour.status === 'ready';
  const waiting = result?.hour.status === 'queued';
  const operator = state.session.user.role === 'operator';
  const short = result?.points.filter(point => point.kind === 'insufficient') || [];
  const noise = result?.points.filter(point => point.kind === 'noise') || [];
  return {
    html: `${header('楼层运营', '热区工作台', '将短距离内持续排队的入口聚成热区。仅楼层运营可确认并下发疏导单。')}
      <div class="split heat-split"><section class="panel"><div class="section-line"><h2>餐饮入口分布 ${badge(hourLabel[result?.hour.status || hour?.status || 'collecting'], ready ? 'good' : 'warm')}</h2>
      ${operator && !ready && !waiting && hour && data.observations.length ? `<button id="analyze">${result ? '重试分析' : '封存并识别热区'}</button>` : ''}
      ${waiting ? '<button class="secondary" id="refresh">刷新结果</button>' : ''}</div>
      ${ready ? floorPlan(result.points, result.hotspots) : empty(waiting ? '后台正在计算，稍后刷新结果。' : '请在排队采样页收齐观测。完成后封存这一小时并启动分析。')}
      <div class="map-rules">${ready ? '<a href="#handoffs">查看本小时交接简报</a>' : '<a href="#coverage">检查缺测补采</a>'}<span>邻域半径 <b>18 m</b></span><span>邻域门店 <b>至少 3 家</b></span><span>拥堵门槛 <b>中位 8 人</b></span></div></section>
      <aside class="side-note"><h2>热区和疏导点 ${ready ? `<span class="count">${result.hotspots.length}</span>` : ''}</h2>
      ${result?.hotspots.map(zone => `<article class="area"><div class="section-line"><h3>热区 ${zone.zone_number}</h3>${badge(zone.status === 'confirmed' ? '已派单' : '待确认', zone.status === 'confirmed' ? 'good' : 'warm')}</div>
        <strong>${text(zone.staging_point)}</strong><p class="minor">锚点 ${text(zone.anchor)} · ${result.points.filter(p => p.hotspot_id === zone.id).length} 个入口</p>
        ${operator && zone.status === 'proposed' ? `<button data-confirm="${zone.id}">确认并下发</button>` : ''}</article>`).join('') || empty(ready ? '该时段没有符合密度条件的热区。' : '等待本楼层分析结果。')}
      ${ready ? `<div class="exceptions"><h3>样本不足 · ${short.length}</h3>${short.length ? short.map(point => `<p>${text(point.name)} <b>${point.windows}/3 窗口</b></p>`).join('') : '<p>所有门店均有至少三个窗口。</p>'}
        <h3>孤立拥堵 · ${noise.length}</h3>${noise.map(point => `<p>${text(point.name)} <b>中位 ${point.median_queue} 人</b></p>`).join('')}</div>` : ''}</aside></div>`,
    bind(root, action, refresh) {
      const analyze = root.querySelector('#analyze');
      analyze?.addEventListener('click', () => action(() => api('/analyses', {floor: state.floor, hour_start: state.hour}), '已封存，等待 worker 计算', analyze));
      root.querySelector('#refresh')?.addEventListener('click', refresh);
      root.querySelectorAll('[data-confirm]').forEach(button => button.addEventListener('click', () =>
        action(() => api(`/hotspots/${button.dataset.confirm}/confirm`, {}), '热区已确认，疏导单已下发', button)));
    },
  };
}
