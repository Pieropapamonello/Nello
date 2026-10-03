const test = require('node:test');
const assert = require('node:assert/strict');
const { adminRequest, sendAdminMenu } = require('./admin_menu');

test('recognizes commands and native/legacy selections without intercepting links', () => {
  assert.equal(adminRequest({ conversation: 'https://youtube.com/watch?v=abc' }), null);
  assert.equal(adminRequest({ conversation: '/administrator' }), null);
  assert.equal(adminRequest({ conversation: '/admin secret' }).text, '/admin secret');
  assert.equal(adminRequest({ buttonsResponseMessage: { selectedButtonId: 'waadmin:chats' } }).action, 'waadmin:chats');
  assert.equal(adminRequest({ interactiveResponseMessage: { nativeFlowResponseMessage: {
    paramsJson: '{"id":"waadmin:cookies"}' } } }).action, 'waadmin:cookies');
  assert.equal(adminRequest({ interactiveResponseMessage: { nativeFlowResponseMessage: { paramsJson: '{broken' } } }), null);
});

test('denied login does not produce interactive menus', async () => {
  const sent = [];
  const sock = { sendMessage: async (...args) => sent.push(args), relayMessage: () => assert.fail() };
  await sendAdminMenu(sock, '123@lid', { text: 'Accedi prima.' }, () => assert.fail());
  assert.equal(sent[0][1].text, 'Accedi prima.');
});

test('authorized menu uses native single_select and falls back if relay fails', async () => {
  const sent = [];
  const sock = { user: { id: '999@lid' }, sendMessage: async (...args) => sent.push(args),
    relayMessage: async () => { throw new Error('unsupported'); } };
  let content;
  const make = (jid, value) => { content = value; return { message: value, key: { id: 'test' } }; };
  await sendAdminMenu(sock, '123@lid', { text: 'Menu', menu: [{ id: 'waadmin:logout', title: 'Esci' }] }, make);
  const button = content.viewOnceMessage.message.interactiveMessage.nativeFlowMessage.buttons[0];
  assert.equal(button.name, 'single_select');
  assert.equal(JSON.parse(button.buttonParamsJson).sections[0].rows[0].id, 'waadmin:logout');
  assert.match(sent[0][1].text, /\/logout/);
});
