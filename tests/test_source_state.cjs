// Dependency-free regression test for the actual frontend request/render flow.
// Run: node tests/test_source_state.cjs
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

class Element {
  constructor() { this.children = []; this.textContent = ''; this.innerHTML = ''; this.open = false; }
  append(...nodes) { this.children.push(...nodes); }
  appendChild(node) { this.append(node); }
  replaceChildren(...nodes) { this.children = nodes; this.innerHTML = ''; }
  addEventListener() {}
  showModal() { this.open = true; }
  close() { this.open = false; }
  focus() {}
  remove() {}
}

(async () => {
  const elements = new Map();
  const requests = [];
  let reply = {};
  let status = 200;
  const context = vm.createContext({
    document: {
      getElementById(id) {
        if (!elements.has(id)) elements.set(id, new Element());
        return elements.get(id);
      },
      createElement: () => new Element(),
    },
    window: { location: { origin: 'http://test.local' } },
    fetch: async (url, options) => {
      requests.push({ url, options });
      if (url.endsWith('/health')) return { ok: true, json: async () => ({ status: 'ok' }) };
      if (url.endsWith('/videos')) return { ok: true, json: async () => [] };
      if (url.endsWith('/sources')) return { ok: true, json: async () => [] };
      return { ok: status === 200, status, json: async () => reply };
    },
  });
  const file = process.env.FRONTEND_UNDER_TEST || path.join(__dirname, '../frontend/app.js');
  vm.runInContext(fs.readFileSync(file, 'utf8'), context);
  const source = { subject_area_number: '1', subject_area_name: 'Photovoltaik',
    module_number: '01', module_name: 'Stringdesign', video_number: '2',
    video_name: 'Kenngrößen', time_range: '(0:01:00 - 0:01:30)', text: 'Originalzitat\n<unverändert>' };
  reply = { conversation_id: 'session-a', answer: source.text, citations: [source] };
  await context.sendMessage('Frage');
  await context.loadSources();
  assert.equal(requests.filter(r => r.url.endsWith('/sources')).length, 0,
    'Must not discard answer citations in favour of a second empty lookup');
  const body = elements.get('dialog-body');
  assert.equal(body.children[0].children[0].children[4].textContent, source.text);
  assert.equal(body.children[0].children[0].children[0].textContent, 'Fachbereich 1 · Photovoltaik');

  // Failed requests preserve the last successful answer and its sources.
  status = 500; reply = { detail: 'Testfehler' };
  await context.sendMessage('Fehlgeschlagene Frage');
  await context.loadSources();
  assert.equal(body.children[0].children[0].children[4].textContent, source.text);

  status = 200; reply = { conversation_id: 'session-a', answer: 'Gerne', citations: [] };
  await context.sendMessage('Danke');
  await context.loadSources();
  assert.match(body.innerHTML, /keine zitierten Quellenstellen/);
  const turns = requests.filter(r => r.url.endsWith('/chat'));
  assert.equal(turns[1].options.headers['X-Conversation-ID'], 'session-a');

  // Older responses must not disguise missing citation data as an empty list,
  // nor promote unselected retrieval candidates from the legacy sources field.
  reply = { conversation_id: 'session-a', answer: source.text, sources: [source] };
  await context.sendMessage('Alte Serverantwort');
  await context.loadSources();
  assert.match(body.innerHTML, /nicht zugeordnet/);

  status = 404; reply = { detail: 'Sitzung abgelaufen' };
  await context.sendMessage('Abgelaufene Sitzung');
  await context.loadSources();
  assert.match(body.innerHTML, /keine zitierten Quellenstellen/);
  console.log('Source-state regression passed: answer citations, failed lookup, errors, empty and legacy responses.');
})().catch(error => { console.error(error); process.exitCode = 1; });
