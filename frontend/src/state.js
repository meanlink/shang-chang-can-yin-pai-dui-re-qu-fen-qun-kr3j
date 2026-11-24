const key = 'changhe-queue-session';

export const state = {
  session: JSON.parse(sessionStorage.getItem(key) || 'null'),
  floor: 3,
  coverageSample: null,
  bookingTask: null,
  hour: '2026-11-21T12:00',
};

export function setSession(value) {
  state.session = value;
  if (value) sessionStorage.setItem(key, JSON.stringify(value));
  else sessionStorage.removeItem(key);
}

export function shiftQuery() {
  return new URLSearchParams({floor: state.floor, hour_start: state.hour});
}

export async function api(path, body, method = body === undefined ? 'GET' : 'POST') {
  const headers = {};
  if (state.session) headers.Authorization = `Bearer ${state.session.token}`;
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  const response = await fetch(`/api${path}`, {method, headers, body: JSON.stringify(body)});
  const data = await response.json();
  if (response.status === 401 && path !== '/auth/login') {
    setSession(null);
    location.hash = 'login';
  }
  if (!response.ok) {
    const message = Array.isArray(data.detail) ? data.detail.map(row => row.msg).join('；') : data.detail;
    throw Error(message || `请求失败 (${response.status})`);
  }
  return data;
}
