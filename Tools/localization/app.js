const $ = (id) => document.getElementById(id);
const labels = {all: 'Все записи', same: 'Совпадают с оригиналом', missing: 'Отсутствуют или неполны', different: 'Отличаются от оригинала', extra: 'Только в переводе'};
const state = {status: 'same', rows: [], total: 0, detail: null, token: '', busy: false, generation: 0, selection: 0};
const dirty = () => state.detail && $('target').value !== state.detail.target.replace(/\r\n?/g, '\n');
const number = (value) => value.toLocaleString('ru-RU');
function showMessage(text, success = false) {
  $('message').textContent = text;
  $('message').className = success ? 'success' : '';
  $('message').hidden = !text;
}
async function api(path, body) {
  const response = await fetch(path, body === undefined ? {} : {
    method: 'POST', headers: {'Content-Type': 'application/json', 'X-Editor-Token': state.token}, body: JSON.stringify(body)
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || 'Не удалось выполнить запрос.');
  return result;
}
function canLeave() {
  return !state.busy && (!dirty() || window.confirm('Есть несохранённый перевод. Отбросить правку?'));
}
function updateDirty() {
  $('dirty').textContent = dirty() ? 'Не сохранено' : 'Без изменений';
  $('dirty').className = dirty() ? 'changed' : '';
  $('save').disabled = state.busy || !dirty();
  $('save-next').disabled = state.busy || !state.detail;
  $('reset').disabled = state.busy || !dirty();
  $('copy').disabled = state.busy || !state.detail?.source;
  $('target').readOnly = state.busy;
}
function renderRows() {
  const fragment = document.createDocumentFragment();
  for (const row of state.rows) {
    const button = document.createElement('button');
    button.className = 'entry-row' + (state.detail?.key === row.key ? ' selected' : '');
    button.title = row.key + '\n' + labels[row.status];
    button.setAttribute('aria-pressed', String(state.detail?.key === row.key));
    const top = document.createElement('div'); top.className = 'row-top';
    const dot = document.createElement('span'); dot.className = 'status-dot ' + row.status;
    const key = document.createElement('span'); key.className = 'row-key'; key.textContent = row.key;
    top.append(dot, key);
    const preview = document.createElement('div'); preview.className = 'row-preview'; preview.textContent = row.preview;
    const path = document.createElement('span'); path.className = 'row-path'; path.textContent = row.file;
    button.append(top, preview, path);
    button.addEventListener('click', () => select(row.key));
    fragment.append(button);
  }
  if (!state.rows.length) {
    const empty = document.createElement('p'); empty.className = 'no-results';
    empty.textContent = 'Записей не найдено. Измените запрос или выберите другой фильтр.';
    fragment.append(empty);
  }
  $('rows').replaceChildren(fragment);
  $('more').hidden = state.rows.length >= state.total;
}
async function load(more = false) {
  const generation = ++state.generation;
  const query = new URLSearchParams({q: $('search').value, kind: $('kind').value, status: state.status, folder: $('folder').value, offset: more ? state.rows.length : 0});
  try {
    const data = await api('/api/entries?' + query);
    if (generation !== state.generation) return;
    state.rows = more ? [...state.rows, ...data.rows] : data.rows;
    state.total = data.total;
    $('result-count').textContent = 'Записей: ' + number(data.total);
    $('filter-label').textContent = labels[state.status];
    for (const [status, count] of Object.entries(data.counts)) $('count-' + status).textContent = number(count);
    $('count-all').textContent = number(Object.values(data.counts).reduce((a, b) => a + b, 0));
    const diagnostics = [];
    if (data.errors.length) diagnostics.push('Ошибки каталога (сохранение заблокировано):\n' + data.errors.join('\n'));
    if (data.warnings?.length) diagnostics.push('Пропущены некорректные прототипы:\n' + data.warnings.join('\n'));
    $('catalog-errors').hidden = !diagnostics.length;
    $('catalog-errors').textContent = diagnostics.join('\n\n');
    const folder = $('folder').value;
    $('folder').replaceChildren(new Option('Все разделы', ''), ...data.folders.map(f => new Option(f, f)));
    $('folder').value = folder;
    $('source-locale').textContent = data.source; $('target-locale').textContent = data.target;
    $('source-tag').textContent = data.source.toUpperCase(); $('target-tag').textContent = data.target.toUpperCase();
    renderRows();
  } catch (error) {
    $('catalog-errors').hidden = false;
    $('catalog-errors').textContent = error.message;
  }
}
function display(detail) {
  state.detail = detail;
  $('empty').hidden = true; $('edit-content').hidden = false;
  $('entry-key').textContent = detail.key; $('entry-path').textContent = detail.file;
  $('source').value = detail.source; $('target').value = detail.target;
  $('comment').textContent = detail.comment; $('comment').hidden = !detail.comment;
  $('entity-context').hidden = !detail.entity?.length;
  $('entity-context').textContent = (detail.entity || []).map(p =>
    `Entity: ${p.id}${p.abstract ? ' (абстрактный)' : ''}\n${p.path}\nРодители: ${p.parents.join(', ') || 'нет'}`
  ).join('\n\n') + '\nИсточник учитывает FTL, поля YAML и наследование. Сохраняется только русский FTL.';
  $('variables').replaceChildren(...detail.variables.map(v => {
    const tag = document.createElement('span'); tag.className = 'variable'; tag.textContent = v; return tag;
  }));
  showMessage(detail.errors.join('\n'));
  updateDirty(); renderRows();
}
async function select(key) {
  if (!canLeave()) return;
  const selection = ++state.selection;
  state.busy = true; updateDirty();
  try {
    const detail = await api('/api/entry?key=' + encodeURIComponent(key));
    if (selection === state.selection) display(detail);
  } catch (error) { showMessage(error.message); }
  finally { state.busy = false; updateDirty(); }
}
async function save(next = false) {
  if (!state.detail || state.busy) return;
  const index = state.rows.findIndex(r => r.key === state.detail.key);
  const nextKey = state.rows[index + 1]?.key;
  state.busy = true; updateDirty(); showMessage('Проверка и сохранение…', true);
  let saved = false;
  try {
    if (dirty()) {
      const detail = await api('/api/save', {...state.detail, text: $('target').value});
      display(detail);
    }
    showMessage('Сохранено в файл проекта.', true);
    await load();
    saved = true;
  } catch (error) { showMessage(error.message); }
  finally { state.busy = false; updateDirty(); }
  if (next && saved) {
    const key = state.rows.some(r => r.key === nextKey) ? nextKey : state.rows.find(r => r.key !== state.detail.key)?.key;
    if (key) await select(key);
    else showMessage('Сохранено. В текущем списке больше нет записей.', true);
  }
}
$('target').addEventListener('input', () => { updateDirty(); showMessage(''); });
$('target').addEventListener('keydown', event => {
  if (event.key === 'Tab') {
    event.preventDefault();
    $('target').setRangeText('    ', $('target').selectionStart, $('target').selectionEnd, 'end');
    updateDirty();
  }
});
$('copy').addEventListener('click', () => {
  if (dirty() && !window.confirm('Заменить текущую правку оригиналом?')) return;
  $('target').value = state.detail.source; updateDirty(); $('target').focus();
});
$('reset').addEventListener('click', () => { if (canLeave()) display(state.detail); });
$('save').addEventListener('click', () => save());
$('save-next').addEventListener('click', () => save(true));
$('more').addEventListener('click', () => load(true));
$('filters').addEventListener('click', event => {
  const button = event.target.closest('button');
  if (!button || state.busy) return;
  state.status = button.dataset.status;
  document.querySelectorAll('#filters button').forEach(b => b.classList.toggle('active', b === button));
  load();
});
let debounce;
$('search').addEventListener('input', () => { clearTimeout(debounce); debounce = setTimeout(() => load(), 200); });
$('folder').addEventListener('change', () => load());
$('kind').addEventListener('change', () => load());
$('refresh').addEventListener('click', async () => {
  if (!canLeave()) return;
  state.busy = true; updateDirty(); $('refresh').disabled = true; $('refresh').textContent = 'Чтение файлов…';
  try {
    await api('/api/refresh', {});
    if (state.detail) display(await api('/api/entry?key=' + encodeURIComponent(state.detail.key)));
    await load();
  } catch (error) { $('catalog-errors').textContent = error.message; $('catalog-errors').hidden = false; }
  finally { state.busy = false; updateDirty(); $('refresh').disabled = false; $('refresh').textContent = '↻ Перечитать файлы'; }
});
window.addEventListener('beforeunload', event => { if (dirty()) { event.preventDefault(); event.returnValue = ''; } });
document.addEventListener('keydown', event => {
  if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') { event.preventDefault(); save(event.shiftKey); }
  if (event.key === '/' && !['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement.tagName)) { event.preventDefault(); $('search').focus(); }
});
(async () => {
  try { state.token = (await api('/api/session')).token; await load(); }
  catch (error) { $('catalog-errors').hidden = false; $('catalog-errors').textContent = 'Не удалось подключиться: ' + error.message; }
})();
