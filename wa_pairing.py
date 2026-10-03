"""One bounded pairing-code request, owned by an active Telegram admin."""
import asyncio
import re
import uuid
import time


def phone_number(text):
    if not isinstance(text, str) or len(text) > 40 or re.search(r'[^\d+ ()-]', text):
        raise ValueError('invalid phone')
    value = re.sub(r'[ ()-]', '', text).removeprefix('+')
    if not re.fullmatch(r'[1-9][0-9]{7,14}', value):
        raise ValueError('invalid phone')
    return value


class PairingCodes:
    def __init__(self, pairing):
        self.pairing = pairing
        pairing.codes = self
        self.pending = None
        self.pause_qr_until = 0

    async def request(self, admin, phone):
        if not admin or admin != await self.pairing.admin():
            return {'ok': False, 'reason': 'not_admin'}
        try:
            phone = phone_number(phone)
        except ValueError:
            return {'ok': False, 'reason': 'invalid_phone'}
        if self.pairing.connected:
            return {'ok': False, 'reason': 'connected'}
        if self.pending:
            return {'ok': False, 'reason': 'busy'}
        future = asyncio.get_running_loop().create_future()
        request = {'id': str(uuid.uuid4()), 'phone': phone, 'admin': admin,
                   'future': future, 'taken': False}
        self.pending = request
        self.pause_qr_until = time.monotonic() + 90
        delivered = False
        try:
            async with self.pairing.lock:
                if self.pairing.message:
                    await asyncio.to_thread(self.pairing._delete)
            result = await asyncio.wait_for(future, timeout=60)
            if admin != await self.pairing.admin():
                return {'ok': False, 'reason': 'not_admin'}
            delivered = bool(result.get('ok'))
            return result
        except asyncio.TimeoutError:
            return {'ok': False, 'reason': 'timeout'}
        finally:
            if self.pending is request:
                self.pending = None
            if not delivered:
                self.pause_qr_until = 0

    async def take(self):
        request = self.pending
        if not request or request['taken'] or request['admin'] != await self.pairing.admin():
            return {}
        request['taken'] = True
        return {key: request[key] for key in ('id', 'phone')}

    async def finish(self, body):
        request = self.pending
        if not request or body.get('id') != request['id'] or request['future'].done():
            return {'ok': False}
        if request['admin'] != await self.pairing.admin():
            result = {'ok': False, 'reason': 'not_admin'}
        elif isinstance(body.get('code'), str) and re.fullmatch(r'[A-Z0-9]{8}', body['code']):
            result = {'ok': True, 'code': body['code']}
        else:
            reason = body.get('reason')
            result = {'ok': False, 'reason': reason if reason in ('connected', 'not_ready') else 'failed'}
        request['future'].set_result(result)
        return {'ok': True}
