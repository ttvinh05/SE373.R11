'use strict';
const $ = id => document.getElementById(id);
const question = 'Đề xuất cách triển khai đăng nhập cho dự án này trong 3 gạch đầu dòng.';
const steps = [
  { prompt: 'Hãy nhớ quy ước dự án: authentication dùng JWT.', hint: 'Agent tự chọn tool ghi memory, nhận kết quả rồi xác nhận đã lưu.' },
  { prompt: question, hint: 'Phiên mới không có chat cũ. Kiểm tra agent áp dụng quy ước JWT đã lưu.' },
  { prompt: 'Từ nay đổi quy ước authentication sang session cookie thay cho JWT. Hãy nhớ cho các session sau.', hint: 'Agent gọi tool cập nhật cùng chủ đề. Quy ước cũ chuyển sang đã thay thế.' },
  { prompt: question, hint: 'Cùng câu hỏi ở phiên mới. Agent cần áp dụng session cookie.' },
  { prompt: question, control: true, hint: 'Đối chứng: không nạp memory và chặn cả hai tool đọc/ghi memory.' }
];
let prepared = null, busy = false, answerCount = 0, lastTrace = null;

async function api(path, body) {
  const response = await fetch(path, body === undefined ? {} : {
    method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Memory-Lab': '1' },
    body: JSON.stringify(body)
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || 'Không thực hiện được thao tác.');
  return data;
}

async function action(work) {
  if (busy) return;
  busy = true; $('error').hidden = true; controls();
  try { await work(); }
  catch (error) {
    $('error').textContent = error.message; $('error').hidden = false;
    try { renderState(await api('/api/state')); } catch (_) { /* Giữ lỗi gốc. */ }
  }
  finally { busy = false; $('loading').hidden = true; controls(); }
}

function controls() {
  document.querySelectorAll('button, input, textarea').forEach(el => { el.disabled = busy; });
  $('send').disabled = busy || !prepared || prepared.sent;
  $('send').textContent = prepared?.sent ? 'Đã chạy · chuẩn bị phiên mới để tiếp tục' : '2. Chạy agent ↗';
}

function invalidate() {
  prepared = null; $('context-panel').hidden = true; controls();
}

function selectStep(index) {
  const step = steps[index];
  document.querySelectorAll('[data-step]').forEach((el, i) => {
    if (i === index) el.setAttribute('aria-current', 'step');
    else el.removeAttribute('aria-current');
  });
  invalidate(); $('step-hint').textContent = step.hint;
  $('question').value = step.prompt; $('inject').checked = !step.control;
}

function node(tag, className, content) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (content !== undefined) element.textContent = content;
  return element;
}

function memoryEntry(entry, old) {
  const box = node('article', 'memory-entry' + (old ? ' old' : ''));
  box.append(node('span', 'key', entry.key), node('p', 'value', entry.value));
  box.append(node('p', 'meta', (old ? 'ĐÃ THAY THẾ' : 'ACTIVE') + ' · Nguồn: ' + entry.source_session));
  box.append(node('p', 'meta', (old ? 'Thay thế lúc: ' : 'Ghi lúc: ') + new Date(old ? entry.superseded_at : entry.created_at).toLocaleString('vi-VN')));
  return box;
}

function renderState(state) {
  const active = state.entries.filter(e => e.status === 'active');
  const old = state.entries.filter(e => e.status === 'superseded');
  $('active-memory').replaceChildren(...active.map(e => memoryEntry(e, false)));
  if (!active.length) $('active-memory').append(node('p', 'memory-empty', 'Chưa có quy ước. Nói với agent điều cần nhớ để bắt đầu.'));
  $('old-memory').replaceChildren(...old.slice().reverse().map(e => memoryEntry(e, true)));
  $('history-label').textContent = 'Đã thay thế (' + old.length + ')'; $('history').hidden = !old.length;
  $('memory-count').textContent = active.length + ' active';
  $('raw-memory').textContent = JSON.stringify({ schema_version: 1, entries: state.entries }, null, 2);
  $('storage-path').textContent = state.store; $('demo-id').textContent = 'DEMO ' + state.demo_id.slice(0, 8);
}

function renderTrace(trace) {
  $('trace-panel').hidden = false;
  const serialized = JSON.stringify(trace);
  if (serialized === lastTrace) return;
  lastTrace = serialized;
  $('loop-trace').replaceChildren(...trace.map(event => {
    const entry = node('li');
    if (event.type === 'model_action') {
      entry.append(node('strong', '', 'Bước ' + event.step + ' · Model chọn ' + event.action));
      if (event.action === 'remember_memory') entry.append(node('p', '', event.key + ': ' + event.value));
      if (event.evidence) entry.append(node('p', 'caption', 'Nguồn user: “' + event.evidence + '”'));
    } else {
      entry.append(node('strong', '', 'Tool ' + event.tool + ' · ' + (event.result.ok ? 'Thành công' : 'Bị từ chối')));
      const details = node('details');
      details.append(node('summary', '', 'Kết quả trả về model'), node('pre', '', JSON.stringify(event.result, null, 2)));
      entry.append(details);
    }
    return entry;
  }));
  const last = trace[trace.length - 1];
  $('run-status').textContent = last ? (last.type === 'tool_result' ? 'Đã có kết quả tool · model đang xử lý tiếp…' : 'Model đã chọn ' + last.action) : 'Model đang chọn hành động đầu tiên…';
}

function renderAnswer(result, context) {
  answerCount++; $('empty-answer').hidden = true; $('answer-count').textContent = answerCount + ' phiên';
  const article = node('article', 'answer');
  const top = node('div', 'answer-top', 'Agent · ' + context.request.session_id);
  top.append(node('span', '', context.request.memory_enabled ? 'Có memory' : 'Đối chứng'));
  article.append(top, node('p', 'answer-question', context.request.messages[1].content), node('div', 'answer-body', result.answer));
  const details = node('details'); details.append(node('summary', '', 'Context và toàn bộ vòng lặp'));
  details.append(node('p', '', 'Chat cũ: 0 · Lượt model: ' + result.model_steps + ' · Lượt tool: ' + result.tool_items));
  details.append(node('p', 'mono', 'Thread cuối: ' + result.thread_id));
  details.append(node('p', 'mono', 'Bằng chứng: ' + result.evidence));
  details.append(node('pre', '', 'Memory ban đầu:\n' + (context.request.injected_memory || '(rỗng)')));
  details.append(node('pre', '', JSON.stringify(result.trace, null, 2)));
  article.append(details); $('answers').prepend(article);
}

async function prepareContext() {
  prepared = await api('/api/prepare', { question: $('question').value, without_memory: !$('inject').checked });
  prepared.sent = false; $('context-panel').hidden = false;
  $('session-id').textContent = prepared.request.session_id;
  $('context-caption').textContent = 'Chat cũ: 0 tin nhắn · ' + (prepared.request.memory_enabled ? 'Nạp quy ước active. Agent có thể gọi tool đọc/ghi.' : 'Đối chứng: tắt injection và cả hai tool.');
  $('injected-memory').textContent = prepared.request.injected_memory || '(Không có memory được inject)';
  $('full-prompt').textContent = prepared.codex_prompt;
}

async function runPrepared() {
  const context = prepared; context.sent = true; $('loading').hidden = false; renderTrace([]);
  await api('/api/start', { request_id: context.request_id });
  for (;;) {
    const progress = await api('/api/progress?request_id=' + encodeURIComponent(context.request_id));
    renderTrace(progress.trace);
    renderState(progress.state);
    if (progress.status === 'failed') throw new Error(progress.error);
    if (progress.status === 'done') {
      renderAnswer(progress.result, context); renderState(progress.result.state); $('loading').hidden = true; return;
    }
    await new Promise(resolve => setTimeout(resolve, 1200));
  }
}

function resetAnswers() {
  $('answers').replaceChildren(); answerCount = 0; $('answer-count').textContent = '0 phiên';
  $('empty-answer').hidden = false; $('trace-panel').hidden = true;
}

document.querySelectorAll('[data-step]').forEach(el => el.addEventListener('click', () => selectStep(Number(el.dataset.step))));
['question', 'inject'].forEach(id => $(id).addEventListener('input', invalidate));
$('ask-form').addEventListener('submit', event => { event.preventDefault(); action(prepareContext); });
$('send').addEventListener('click', () => action(runPrepared));
$('new-demo').addEventListener('click', () => action(async () => {
  renderState(await api('/api/new-demo', {})); resetAnswers(); selectStep(0);
}));
$('run-demo').addEventListener('click', () => action(async () => {
  renderState(await api('/api/new-demo', {})); resetAnswers();
  for (let i = 0; i < steps.length; i++) { selectStep(i); await prepareContext(); await runPrepared(); }
  $('step-hint').textContent = 'Đã chạy xong 5 phiên. Đối chiếu hai câu trả lời với memory và lịch sử thay thế.';
}));
selectStep(0);
action(async () => {
  const state = await api('/api/state'); renderState(state); $('connection').textContent = state.codex_status;
});
