import {api, setSession, state} from './state.js';
import {input, readForm, roleLabel, text} from './ui.js';
import {stores} from './pages/stores.js';
import {windows} from './pages/windows.js';
import {heat} from './pages/heat.js';
import {tasks} from './pages/tasks.js';
import {coverage} from './pages/coverage.js';
import {lanes} from './pages/lanes.js';
import {surges} from './pages/surges.js';
import {recoveries} from './pages/recoveries.js';
import {handoffs} from './pages/handoffs.js';

const root = document.querySelector('#app');
const routes = {stores: ['门店档案', stores], windows: ['排队采样', windows], coverage: ['缺测补采', coverage],
  heat: ['热区工作台', heat], tasks: ['客流疏导', tasks], lanes: ['等候线容量排班', lanes],
  surges: ['临时控流', surges], recoveries: ['服务恢复', recoveries], handoffs: ['高峰交接简报', handoffs]};
const hourRoutes = new Set(['windows', 'coverage', 'heat', 'surges', 'recoveries', 'handoffs']);
let generation = 0;
let flash = '';

function loginPage() {
  root.innerHTML = `<main class="login-layout"><section class="login-cover"><div class="mast"><span class="emblem">↗</span> 长河广场</div>
    <div class="cover-copy"><div class="kicker">餐饮楼层运营</div><h1>餐饮排队<br>热区工作台</h1><p>巡场记录、热区判断和现场疏导，共用一份楼层观测。</p></div>
    <div class="cover-map" aria-hidden="true"><i></i><i></i><i></i><i></i><b>F3</b></div></section>
    <section class="entry"><div class="entry-sheet"><h2>登录工作台</h2><p>使用巡场、运营或疏导岗位账号进入。</p>
    <form id="login" class="stack">${input('账号','username','text','autocomplete="username" value="floorlead" required')}
    ${input('密码','password','password','autocomplete="current-password" required')}<button>进入工作台 <span aria-hidden="true">→</span></button></form>
    <div id="feedback" aria-live="polite"></div><div class="demo">演示账号 <b>patrol / floorlead / guide</b><br>演示口令 <b>changhe-demo</b></div></div></section></main>`;
  const form = root.querySelector('#login');
  form.addEventListener('submit', async event => {
    event.preventDefault();
    const button = form.querySelector('button');
    button.disabled = true;
    try {
      setSession(await api('/auth/login', readForm(form)));
      location.hash = state.session.user.role === 'observer' ? 'windows' : state.session.user.role === 'steward' ? 'tasks' : 'heat';
    } catch (error) {
      root.querySelector('#feedback').textContent = error.message;
      button.disabled = false;
    }
  });
}

async function render() {
  const revision = ++generation;
  if (!state.session) { loginPage(); return; }
  const requested = location.hash.slice(1);
  const route = Object.hasOwn(routes, requested) ? requested : 'heat';
  const user = state.session.user;
  root.innerHTML = `<header class="top"><div class="mast"><span class="emblem">↗</span><div>长河广场<small>餐饮运营台</small></div></div>
    <nav aria-label="业务模块">${Object.entries(routes).map(([key, [label]]) => `<a href="#${key}" ${key === route ? 'aria-current="page"' : ''}>${label}</a>`).join('')}</nav>
    <div class="account"><span>${roleLabel[user.role]} <small>${text(user.username)}</small></span><button id="logout" class="secondary">退出</button></div></header>
    <div class="context"><div class="context-inner"><label>楼层<select id="floor">${[1,2,3,4].map(floor => `<option value="${floor}" ${floor === state.floor ? 'selected' : ''}>${floor}F</option>`).join('')}</select></label>
    ${hourRoutes.has(route) ? `<label>起始小时<input type="datetime-local" id="hour" step="3600" value="${text(state.hour)}"></label><span>上海时间</span>` : ''}</div></div>
    <main class="work"><div id="feedback" aria-live="polite" ${flash ? '' : 'hidden'}>${text(flash)}</div><div id="view" aria-busy="true"><p class="loading">正在读取楼层数据…</p></div></main>`;
  flash = '';
  root.querySelector('#logout').onclick = () => { setSession(null); location.hash = 'login'; };
  root.querySelector('#floor').onchange = event => { state.floor = Number(event.target.value); render(); };
  const time = root.querySelector('#hour');
  if (time) time.onchange = () => {
    if (time.value) state.hour = `${time.value.slice(0,13)}:00`;
    render();
  };
  const view = root.querySelector('#view');
  try {
    const page = await routes[route][1]();
    if (revision !== generation) return;
    view.innerHTML = page.html;
    view.removeAttribute('aria-busy');
    page.bind(view, async (mutate, success, control) => {
      const button = control instanceof HTMLFormElement ? control.querySelector('button') : control;
      button.disabled = true;
      try {
        await mutate();
        if (revision !== generation) return;
        flash = success;
        render();
      } catch (error) {
        if (revision !== generation) return;
        const feedback = root.querySelector('#feedback');
        feedback.hidden = false;
        feedback.classList.add('error');
        feedback.textContent = error.message;
        button.disabled = false;
      }
    }, render);
  } catch (error) {
    if (revision !== generation) return;
    view.innerHTML = `<p>${text(error.message)}</p><button id="retry">重新读取</button>`;
    view.querySelector('#retry').onclick = render;
  }
}

window.addEventListener('hashchange', render);
render();
