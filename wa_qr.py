"""WhatsApp pairing QR delivery to the authenticated Telegram admin only."""
import asyncio
import io
import logging
import os
import time

import aiohttp
import qrcode
import requests

log = logging.getLogger(__name__)


class WhatsAppQR:
    def __init__(self, ns):
        self.ns = ns
        self.qr = None
        self.expires = 0
        self.connected = False
        self.message = None
        self.sent_qr = None
        self.lock = asyncio.Lock()

    async def admin(self):
        try:
            ident = await self.ns.ranking_store.get_admin_chat()
        except Exception:
            ident = None
        try:
            ident = int(ident or self.ns.admin_user_id or 0)
        except (ValueError, TypeError):
            return None
        # Negative IDs are groups/channels. Never deliver pairing credentials there.
        return ident if ident > 0 else None

    def status(self):
        return {'connected': self.connected,
                'qr_available': bool(self.qr and time.monotonic() < self.expires)}

    async def update(self, body):
        async with self.lock:
            if body.get('connected') is True:
                self.connected = True
                self.qr = None
                self.expires = 0
                if self.message:
                    await asyncio.to_thread(self._delete)
                return {'ok': True}
            if body.get('connected') is False:
                self.connected = False
                self.qr = None
                self.expires = 0
                if self.message:
                    await asyncio.to_thread(self._delete)
                return {'ok': True}
            qr = body.get('qr')
            if not isinstance(qr, str) or not 20 <= len(qr) <= 4096:
                return {'ok': False}
            self.connected = False
            self.qr = qr
            self.expires = time.monotonic() + 60
            return await self._deliver()

    async def resend(self):
        async with self.lock:
            if not self.status()['qr_available']:
                return {'ok': False, **self.status()}
            return await self._deliver(force=True)

    async def _deliver(self, force=False):
        admin = await self.admin()
        if not admin or not self.ns.telegram_token:
            return {'ok': False}
        if self.message and self.message[0] != admin:
            await asyncio.to_thread(self._delete)
        if not force and self.sent_qr == self.qr and self.message:
            return {'ok': True}
        try:
            ok = await asyncio.to_thread(self._send, admin, self.qr)
            return {'ok': ok}
        except Exception:
            # Telegram exceptions may include the bot token or pairing material.
            log.warning('WhatsApp QR delivery failed')
            return {'ok': False}

    def _delete(self):
        chat, message = self.message
        try:
            requests.post(self._url('deleteMessage'), json={
                'chat_id': chat, 'message_id': message}, timeout=15)
        except Exception:
            log.warning('WhatsApp QR removal failed')
        self.message = None
        self.sent_qr = None

    def _url(self, method):
        return f'https://api.telegram.org/bot{self.ns.telegram_token}/{method}'

    def _send(self, admin, qr):
        output = io.BytesIO()
        image = qrcode.make(qr, box_size=8, border=4)
        image.save(output, format='PNG')
        caption = ('WhatsApp da ricollegare.\n'
                   'WhatsApp → Dispositivi collegati → Collega un dispositivo.\n'
                   'Scansiona questo QR da un altro schermo. Si aggiorna automaticamente; '
                   'usa /whatsapp se è scaduto.')
        fields = {'chat_id': admin}
        if self.message:
            import json
            fields.update(message_id=self.message[1], media=json.dumps({
                'type': 'photo', 'media': 'attach://photo', 'caption': caption}))
            method = 'editMessageMedia'
        else:
            fields['caption'] = caption
            method = 'sendPhoto'
        response = requests.post(self._url(method), data=fields,
                                 files={'photo': ('whatsapp-qr.png', output.getvalue(), 'image/png')},
                                 timeout=20).json()
        if response.get('ok'):
            self.message = (admin, response['result']['message_id'])
            self.sent_qr = qr
            return True
        if method == 'editMessageMedia' and 'message is not modified' in response.get('description', '').lower():
            return True
        # An expired/deleted message can be recreated on the next QR rotation.
        if method == 'editMessageMedia':
            self.message = None
            self.sent_qr = None
        return False


def command(admin_id):
    async def whatsapp(update, context):
        admin = await admin_id()
        if not (admin and admin > 0 and update.effective_user and update.effective_chat
                and update.effective_chat.type == 'private'
                and update.effective_chat.id == admin and update.effective_user.id == admin):
            await update.effective_message.reply_text('Comando riservato all’admin in chat privata.')
            return
        if os.getenv('WHATSAPP_ENABLED') != '1':
            await update.effective_message.reply_text('WhatsApp non è attivo sul bot.')
            return
        try:
            port = int(os.getenv('WA_BRIDGE_PORT', '8765'))
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
                async with session.post(f'http://127.0.0.1:{port}/whatsapp-qr/resend') as response:
                    result = await response.json()
            if not result.get('ok'):
                await update.effective_message.reply_text(
                    'WhatsApp è già collegato.' if result.get('connected') else
                    'Il QR non è ancora disponibile. Ti arriverà automaticamente appena viene generato.')
        except Exception:
            await update.effective_message.reply_text('Collegamento WhatsApp momentaneamente non disponibile. Riprova tra poco.')
    return whatsapp
