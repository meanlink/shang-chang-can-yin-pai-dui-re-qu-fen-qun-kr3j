export const roleLabel = {observer: '巡场采样', operator: '楼层运营', steward: '现场疏导'};
export const pointLabel = {insufficient: '样本不足', below_threshold: '低于阈值', noise: '噪声点', core: '核心点', border: '边界点'};
export const taskLabel = {assigned: '待认领', active: '疏导中', closed: '已结案'};
export const hourLabel = {collecting: '采集中', queued: '计算中', ready: '已封存', failed: '计算失败'};

export function text(value) {
  return String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[char]));
}

export const clock = value => String(value).slice(11,16);
export const stamp = value => String(value).slice(0,16).replace('T',' ');
export const badge = (label, type = '') => `<span class="badge ${type}">${text(label)}</span>`;
export const empty = line => `<div class="empty">${text(line)}</div>`;

export function header(kicker, title, blurb) {
  return `<header class="page-heading"><div class="kicker">${kicker}</div><h1>${title}</h1><p>${blurb}</p></header>`;
}

export function table(labels, rows) {
  return `<div class="table-wrap"><table><thead><tr>${labels.map(label => `<th>${label}</th>`).join('')}</tr></thead>
    <tbody>${rows.map(row => `<tr>${row.map(cell => `<td>${cell}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
}

export function input(label, name, type, attributes = '') {
  return `<label>${label}<input name="${name}" type="${type}" ${attributes}></label>`;
}

export function readForm(form) {
  return Object.fromEntries(new FormData(form));
}
