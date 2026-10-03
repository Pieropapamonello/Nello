function createPairingPoller(sock, state, bridge) {
  let ready = false, busy = false, stopped = false;
  async function poll() {
    if (!ready || busy || stopped) return;
    busy = true;
    try {
      const request = await bridge('/pairing/take', { signal: AbortSignal.timeout(10000) });
      if (!request.id || !request.phone) return;
      let result;
      if (stopped || state.creds.registered) result = { id: request.id, reason: 'connected' };
      else {
        try {
          const code = await sock.requestPairingCode(request.phone);
          result = { id: request.id, code };
        } catch (_) { result = { id: request.id, reason: 'failed' }; }
      }
      await bridge('/pairing/result', { method: 'POST', headers: { 'content-type': 'application/json' },
        body: JSON.stringify(result), signal: AbortSignal.timeout(10000) });
    } catch (_) { /* Never log phone numbers, pairing codes or socket error bodies. */ }
    finally { busy = false; }
  }
  const timer = setInterval(poll, 2000);
  return { ready: () => { ready = true; }, poll,
    stop: () => { stopped = true; clearInterval(timer); } };
}

module.exports = { createPairingPoller };
