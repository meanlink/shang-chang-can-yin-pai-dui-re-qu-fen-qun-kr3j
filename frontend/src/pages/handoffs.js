import {api, shiftQuery, state} from '../state.js';
import {badge, empty, header, input, pointLabel, readForm, stamp, table, text} from '../ui.js';

const responsePhases = {planned: '待执行', active: '控流中', resolved: '已解除', cancelled: '已撤销'};
const recoveryPhases = {open: '待跟进', monitoring: '复查中', closed: '已结案'};

const phases = {waiting_analysis: '等待分析', waiting_dispatch: '等待疏导收尾', publishable: '待发布', published: '待签收', received: '已签收'};

function reportSheet(report) {
  return `<dl class="handoff-totals"><div><dt>实采窗口</dt><dd>${report.observed_windows}</dd></div>
    <div><dt>缺测窗口</dt><dd>${report.missing_windows}</dd></div><div><dt>确认热区</dt><dd>${report.confirmed} / ${report.zones.length}</dd></div>
    <div><dt>等候线实际入线</dt><dd>${report.moved} 人</dd></div></dl>
    <div class="handoff-section"><h3>热区疏导结果</h3>${report.zones.length ? table(['热区', '锚点', '疏导单', '复测人数', '结果'], report.zones.map(zone => [
      `热区 ${zone.zone_number}`, text(zone.anchor), zone.task_id ? `#${zone.task_id}` : '—', zone.cleared_queue == null ? '—' : `${zone.cleared_queue} 人`, text(zone.close_note || '待收尾'),
    ])) : empty('该小时没有密度热区。')}</div>
    ${report.surges?.length ? `<div class="handoff-section"><h3>临时控流</h3>${table(['方案', '锚点', '起报', '解除复测', '发布时状态'], report.surges.map(row => [
      `#${row.id}`, text(row.anchor), `${row.reported_queue} 人`, row.release_queue == null ? '—' : `${row.release_queue} 人`, responsePhases[row.status],
    ]))}</div>` : ''}
    ${report.recoveries?.length ? `<div class="handoff-section"><h3>门店服务恢复</h3>${table(['工单', '门店', '待处理问题', '复查', '发布时状态'], report.recoveries.map(row => [
      `#${row.id}`, text(row.name), text(row.issue_note), `${row.checks} 次`, recoveryPhases[row.status],
    ]))}<p><a href="#recoveries">查看工单当前进度</a></p></div>` : ''}
    <div class="handoff-section"><h3>下班次继续关注</h3>${report.watch.length ? table(['入口', '原因', '窗口', '补采说明'], report.watch.map(item => [
      text(item.name), `${pointLabel[item.kind]}${item.kind === 'noise' ? ` · 中位 ${item.median_queue} 人` : ''}`, `${item.windows}/4`, text(item.waiver_reason || '—'),
    ])) : empty('本轮没有样本不足或孤立拥堵入口。')}</div>
    ${report.lane_uses.length ? `<div class="handoff-section"><h3>已释放的等候线</h3><ul class="known-lines">${report.lane_uses.map(line => `<li>${text(line.lane_name)} · 疏导 #${line.task_id}<b>入线 ${line.moved_count} 人</b></li>`).join('')}</ul></div>` : ''}`;
}

export async function handoffs() {
  const model = await api(`/handoffs?${shiftQuery()}`);
  const role = state.session.user.role;
  const record = model.record;
  return {
    html: `${header('楼层交班', '高峰交接简报', '热区和疏导全部收尾后发布。接班人按同一份快照核对疏导结果与下一班继续关注的入口。')}
      <div class="split"><section class="panel"><div class="section-line"><h2>${state.floor}F · ${stamp(state.hour)} ${badge(phases[model.state], record?.received_by ? 'good' : 'warm')}</h2>
      <a href="#heat">查看该小时热区</a></div>${model.report ? reportSheet(model.report) : empty('该楼层小时完成热区分析后会生成简报预览。')}</section>
      <aside class="side-note"><h2>交接签收</h2>${model.state === 'waiting_dispatch' ? empty(`还有 ${model.report.pending} 个热区待确认或疏导未结案。`) : ''}
      ${record ? `<div class="handoff-section"><h3>发布 · ${text(record.publisher)}</h3><p>${text(record.publish_note)}</p></div>` : ''}
      ${model.state === 'publishable' && role === 'operator' ? `<form class="stack" id="publish-handoff">
        ${input('交接提示','note','text','required minlength="8" maxlength="200"')}<button>发布交接简报</button></form>` : ''}
      ${model.state === 'published' && role === 'steward' ? `<form class="stack" id="receive-handoff">
        ${input('签收备注','note','text','required minlength="8" maxlength="200"')}<button>签收交接简报</button></form>` : ''}
      ${record?.recipient ? `<div class="handoff-section"><h3>签收 · ${text(record.recipient)}</h3><p>${text(record.receive_note)}</p></div>` : ''}</aside></div>`,
    bind(root, action) {
      const publish = root.querySelector('#publish-handoff');
      if (publish) publish.onsubmit = event => {
        event.preventDefault();
        action(() => api('/handoffs', {...readForm(publish), floor: state.floor, hour_start: state.hour}), '交接简报已发布', publish);
      };
      const receive = root.querySelector('#receive-handoff');
      if (receive) receive.onsubmit = event => {
        event.preventDefault();
        action(() => api(`/handoffs/${record.id}/ack`, readForm(receive)), '交接简报已签收', receive);
      };
    },
  };
}
