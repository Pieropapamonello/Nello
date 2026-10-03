const COMMANDS = new Set(['/admin', '/menu', '/cookies', '/chats', '/sfida', '/logout']);

function adminRequest(content) {
  if (!content) return null;
  const text = content.conversation || content.extendedTextMessage?.text || '';
  let action = content.buttonsResponseMessage?.selectedButtonId
    || content.listResponseMessage?.singleSelectReply?.selectedRowId
    || content.templateButtonReplyMessage?.selectedId || '';
  const params = content.interactiveResponseMessage?.nativeFlowResponseMessage?.paramsJson;
  if (typeof params === 'string' && params.length < 4096) {
    try { action = JSON.parse(params).id || action; } catch (_) { /* malformed selection */ }
  }
  if (typeof action !== 'string') action = '';
  if (action.startsWith('waadmin:') || COMMANDS.has(text.trim().split(/\s+/)[0])) {
    return { text: text.trim(), action };
  }
  return null;
}

async function sendAdminMenu(sock, jid, result, makeMessage) {
  if (!Array.isArray(result.menu) || !result.menu.length) {
    if (result.text) await sock.sendMessage(jid, { text: result.text });
    return;
  }
  const content = { viewOnceMessage: { message: {
    messageContextInfo: { deviceListMetadata: {}, deviceListMetadataVersion: 2 },
    interactiveMessage: {
      header: { title: 'Nello — Amministrazione', hasMediaAttachment: false },
      body: { text: result.text + '\n\nApri Comandi admin. Puoi anche scrivere /menu.' },
      footer: { text: 'Solo amministratore autenticato' },
      nativeFlowMessage: { buttons: [{ name: 'single_select', buttonParamsJson: JSON.stringify({
        title: 'Comandi admin', sections: [{ title: 'Amministrazione', rows: result.menu }],
      }) }] },
    },
  } } };
  try {
    const message = makeMessage(jid, content, { userJid: sock.user.id });
    await sock.relayMessage(jid, message.message, { messageId: message.key.id,
      additionalNodes: [{ tag: 'biz', attrs: {}, content: [{ tag: 'interactive',
        attrs: { type: 'native_flow', v: '1' }, content: [{ tag: 'native_flow',
          attrs: { name: 'single_select', v: '3' } }] }] }],
    });
  } catch (_) {
    // Clients may not support the interactive menu. Keep commands usable.
    await sock.sendMessage(jid, { text: result.text + '\n\n'
      + '/cookies — Stato cookie\n/chats — Chat del bot\n/sfida tema — Nuova sfida\n/logout — Esci\n/menu — Menu admin' });
  }
}

module.exports = { adminRequest, sendAdminMenu };
