'use strict';

// Behavior checks against the shipped application script; no browser or server.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const webDirectory = path.join(__dirname, '..', 'web');
const source = fs.readFileSync(path.join(webDirectory, 'app.js'), 'utf8');
const html = fs.readFileSync(path.join(webDirectory, 'index.html'), 'utf8');
const defaultUser = {user_id: 'Dhanesh', role: 'CEO', department: 'Executive'};
const otherUser = {user_id: 'Arjun', role: 'Engineer', department: 'Engineering'};

class Element {
  constructor() {
    this.children = [];
    this.listeners = new Map();
    this.value = '';
    this.textContent = '';
    this.hidden = false;
    this.disabled = false;
  }
  addEventListener(type, listener) {
    const listeners = this.listeners.get(type) || [];
    this.listeners.set(type, [...listeners, listener]);
  }
  async emit(type) {
    for (const listener of this.listeners.get(type) || []) {
      await listener({preventDefault() {}});
    }
  }
  replaceChildren(...children) { this.children = children; }
  append(...children) { this.children.push(...children); }
  add(child) { this.children.push(child); }
  querySelectorAll() { return []; }
  focus() {}
  scrollIntoView() {}
}

function response(status, body) {
  return {ok: status >= 200 && status < 300, status, json: async () => body};
}

async function makeApp() {
  const elements = new Map([...html.matchAll(/\bid="([^"]+)"/g)]
    .map(match => [match[1], new Element()]));
  const element = id => {
    assert.ok(elements.has(id), 'Application refers to missing HTML element: ' + id);
    return elements.get(id);
  };
  const requests = [];
  const context = vm.createContext({
    console,
    document: {
      getElementById: element,
      createElement: () => new Element(),
      querySelectorAll: () => [],
    },
    Option: class extends Element {
      constructor(label, value) { super(); this.textContent = label; this.value = value; }
    },
    confirm: () => false,
    fetch(url, options) {
      if (url === '/api/session') {
        return Promise.resolve(response(200, {user: defaultUser, is_admin: true}));
      }
      assert.equal(url, '/api/ask', 'Unexpected request from conversation test');
      assert.equal(options.method, 'POST');
      return new Promise(resolve => {
        requests.push({
          data: JSON.parse(options.body),
          reply: (status, body) => resolve(response(status, body)),
        });
      });
    },
  });
  vm.runInContext(source, context, {filename: 'web/app.js'});
  await new Promise(resolve => setImmediate(resolve));
  assert.match(element('signed-in-as').textContent, /Dhanesh/);
  return {
    element,
    requests,
    changeUser: user => context.showUser(user),
    submit(question) {
      element('question').value = question;
      return element('ask-form').emit('submit');
    },
  };
}

async function answer(app, question, text = 'Grounded answer') {
  const pending = app.submit(question);
  const request = app.requests.at(-1);
  request.reply(200, {answer: text, sources: ['source-document']});
  await pending;
  return request.data;
}

const tests = [
  ['sends at most three previous user questions with the current account', async () => {
    const app = await makeApp();
    const questions = ['First?', 'Second?', 'Third?', 'Fourth?', 'Fifth?'];
    for (let index = 0; index < questions.length; index++) {
      const data = await answer(app, questions[index], 'Answer must never become history');
      assert.deepEqual(data, {
        question: questions[index],
        history: questions.slice(Math.max(0, index - 3), index),
        history_user_id: 'Dhanesh',
      });
    }
    assert.equal(app.element('messages').children.length, 10);
  }],
  ['New conversation clears displayed messages and outbound history', async () => {
    const app = await makeApp();
    await answer(app, 'What is Project Horizon?');
    await answer(app, 'Who owns it?');
    app.element('question').value = 'Unsent question';
    await app.element('new-conversation').emit('click');
    assert.equal(app.element('messages').children.length, 0);
    assert.equal(app.element('empty').hidden, false);
    assert.equal(app.element('question').value, '');
    const data = await answer(app, 'A new topic?');
    assert.deepEqual(data.history, []);
  }],
  ['an account change clears history and discards a stale answer', async () => {
    const app = await makeApp();
    await answer(app, 'Private CEO question?');
    const pending = app.submit('Tell me more.');
    const oldRequest = app.requests.at(-1);
    app.changeUser(otherUser);
    assert.equal(app.element('messages').children.length, 0);
    oldRequest.reply(200, {answer: 'Private CEO answer must not appear', sources: ['private']});
    await pending;
    assert.equal(app.element('messages').children.length, 0);
    assert.match(app.element('signed-in-as').textContent, /Arjun/);
    const data = await answer(app, 'Engineering question?');
    assert.deepEqual(data.history, []);
    assert.equal(data.history_user_id, 'Arjun');
  }],
  ['a stale failure does not sign out the replacement account', async () => {
    const app = await makeApp();
    const pending = app.submit('CEO question?');
    app.changeUser(otherUser);
    app.requests.at(-1).reply(401, {error: 'Old session expired'});
    await pending;
    assert.equal(app.element('ask-view').hidden, false);
    assert.equal(app.element('login-view').hidden, true);
    assert.equal(app.element('login-error').textContent, '');
    assert.equal(app.element('messages').children.length, 0);
    assert.match(app.element('signed-in-as').textContent, /Arjun/);
  }],
  ['a pending request prevents duplicate submits and conversation resets', async () => {
    const app = await makeApp();
    await answer(app, 'First question?');
    const pending = app.submit('Follow-up?');
    const requestCount = app.requests.length;
    for (const id of ['ask-button', 'logout', 'new-conversation']) {
      assert.equal(app.element(id).disabled, true);
    }
    await app.submit('Duplicate submission?');
    await app.element('new-conversation').emit('click');
    assert.equal(app.requests.length, requestCount);
    assert.equal(app.element('messages').children.length, 2);
    app.requests.at(-1).reply(200, {answer: 'Follow-up answer', sources: []});
    await pending;
    for (const id of ['ask-button', 'logout', 'new-conversation']) {
      assert.equal(app.element(id).disabled, false);
    }
    assert.equal(app.element('messages').children.length, 4);
  }],
  ['401 and 409 clear the conversation and require a new session', async () => {
    for (const status of [401, 409]) {
      const app = await makeApp();
      await answer(app, 'Earlier private question?');
      const pending = app.submit('Follow-up?');
      app.requests.at(-1).reply(status, {error: 'Session or account changed'});
      await pending;
      assert.equal(app.element('messages').children.length, 0);
      assert.equal(app.element('question').value, '');
      assert.equal(app.element('ask-view').hidden, true);
      assert.equal(app.element('login-view').hidden, false);
      assert.match(app.element('login-error').textContent, /sign in again/i);
      const requestCount = app.requests.length;
      await app.submit('Cannot ask while signed out');
      assert.equal(app.requests.length, requestCount);
      app.changeUser(defaultUser);
      assert.deepEqual((await answer(app, 'Fresh session question?')).history, []);
    }
  }],
  ['a failed question is not added to subsequent context', async () => {
    const app = await makeApp();
    await answer(app, 'Successful question?');
    const pending = app.submit('Failed question?');
    app.requests.at(-1).reply(503, {error: 'Please retry'});
    await pending;
    assert.equal(app.element('messages').children.length, 2);
    assert.equal(app.element('ask-error').textContent, 'Please retry');
    assert.deepEqual((await answer(app, 'Next question?')).history, ['Successful question?']);
  }],
];

(async () => {
  for (const [name, test] of tests) {
    await test();
    console.log('PASS: ' + name);
  }
  console.log(`${tests.length} conversation UI behavior tests passed.`);
})().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
