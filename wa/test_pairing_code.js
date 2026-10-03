const test = require('node:test');
const assert = require('node:assert/strict');
const { createPairingPoller } = require('./pairing_code');

test('waits for socket readiness and generates one pairing code', async () => {
  const calls = [];
  const sock = { requestPairingCode: async phone => { calls.push(phone); return 'ABCD1234'; } };
  let result;
  const bridge = async (path, options) => {
    if (path === '/pairing/take') return { id: 'job', phone: '393331234567' };
    result = JSON.parse(options.body); return { ok: true };
  };
  const poller = createPairingPoller(sock, { creds: { registered: false } }, bridge);
  try {
    await poller.poll(); assert.equal(calls.length, 0);
    poller.ready(); await poller.poll();
    assert.deepEqual(calls, ['393331234567']);
    assert.deepEqual(result, { id: 'job', code: 'ABCD1234' });
  } finally { poller.stop(); }
});

test('does not replace an already registered connection', async () => {
  const sock = { requestPairingCode: () => assert.fail() };
  let result;
  const bridge = async (path, options) => {
    if (path === '/pairing/take') return { id: 'job', phone: '393331234567' };
    result = JSON.parse(options.body); return { ok: true };
  };
  const poller = createPairingPoller(sock, { creds: { registered: true } }, bridge);
  try { poller.ready(); await poller.poll(); assert.equal(result.reason, 'connected'); }
  finally { poller.stop(); }
});
