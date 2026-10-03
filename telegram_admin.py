"""Explicit Telegram admin login shared with the local WhatsApp bridge."""
import hmac
import os
import threading
import time

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationHandlerStop


class AdminSession:
    def __init__(self):
        self.lock = threading.RLock()
        self.user = 0
        self.expires = 0
        self.password = ''
        self.pending = {}
        self.attempts = {}

    def current(self):
        with self.lock:
            if self.expires <= time.monotonic() or self.password != os.getenv('ADMIN_PASSWORD', ''):
                return 0
            return self.user

    def logout(self, user):
        with self.lock:
            if self.user == user:
                self.user = 0
                self.expires = 0
            self.pending.pop(user, None)

    def authenticate(self, user, password):
        with self.lock:
            now = time.monotonic()
            self.attempts = {u: v for u, v in self.attempts.items() if v[1] > now}
            count, until = self.attempts.get(user, (0, now + 900))
            if count >= 5 or sum(v[0] for v in self.attempts.values()) >= 100:
                return 'Troppi tentativi. Riprova tra 15 minuti.'
            expected = os.getenv('ADMIN_PASSWORD', '')
            if not expected:
                return 'Password admin non configurata.'
            if not hmac.compare_digest(password.encode(), expected.encode()):
                self.attempts[user] = (count + 1, until)
                return 'Password errata.'
            self.attempts.pop(user, None)
            self.user, self.expires, self.password = user, now + 43200, expected
            return None


session = AdminSession()


def keyboard(update):
    if not update.effective_chat or update.effective_chat.type != 'private':
        return None
    if not update.effective_user or session.current() != update.effective_user.id:
        return InlineKeyboardMarkup([[InlineKeyboardButton('Accedi come admin', callback_data='adm:login')]])
    return InlineKeyboardMarkup([
        [InlineKeyboardButton('Stato e aggiornamento cookie', callback_data='cookies:status')],
        [InlineKeyboardButton('QR WhatsApp', callback_data='adm:qr')],
        [InlineKeyboardButton('Chat del bot', callback_data='adm:chats'),
         InlineKeyboardButton('Nuova sfida', callback_data='adm:challenge')],
        [InlineKeyboardButton('Esci da admin', callback_data='adm:logout')],
    ])


class AdminUI:
    def __init__(self, store, qr_command, chats_command):
        self.store, self.qr_command, self.chats_command = store, qr_command, chats_command

    async def login(self, update, context, password):
        user = update.effective_user.id
        session.pending.pop(user, None)
        error = session.authenticate(user, password)
        if error:
            await update.effective_message.reply_text(error, reply_markup=keyboard(update))
            return
        try:
            await self.store.set_admin_chat(user)
        except Exception:
            session.logout(user)
            await update.effective_message.reply_text('Non riesco a salvare l’accesso admin. Riprova tra poco.')
            return
        await update.effective_message.reply_text(
            'Accesso admin riuscito. La sessione dura 12 ore e termina al riavvio.\n'
            'Il QR WhatsApp arriverà solo mentre sei autenticato.', reply_markup=keyboard(update))
        # Retrieve an already available QR rather than waiting for a new rotation.
        if os.getenv('WHATSAPP_ENABLED') == '1':
            await self.qr_command(update, context)

    async def command(self, update, context):
        if update.effective_chat.type != 'private':
            return
        args = context.args or []
        if args:
            password = ' '.join(args).strip()
            try:
                await update.effective_message.delete()
            except Exception:
                pass
            await self.login(update, context, password)
        elif session.current() == update.effective_user.id:
            await update.effective_message.reply_text('Menu admin', reply_markup=keyboard(update))
        else:
            session.pending[update.effective_user.id] = time.monotonic() + 180
            await update.effective_message.reply_text('Invia la password admin in questa chat privata entro 3 minuti. Il messaggio verrà cancellato.')

    async def capture(self, update, context):
        if update.effective_chat.type != 'private':
            return
        user = update.effective_user.id
        expires = session.pending.pop(user, 0)
        if expires <= time.monotonic():
            return
        password = (update.effective_message.text or '').strip()
        try:
            await update.effective_message.delete()
        except Exception:
            pass
        await self.login(update, context, password)
        raise ApplicationHandlerStop

    async def callback(self, update, context):
        query = update.callback_query
        if update.effective_chat.type != 'private':
            await query.answer('Solo in chat privata.', show_alert=True)
            return
        action = query.data.removeprefix('adm:')
        if action == 'login':
            await query.answer()
            context.args = []
            await self.command(update, context)
            return
        if session.current() != update.effective_user.id:
            await query.answer('Accedi prima come admin.', show_alert=True)
            await query.edit_message_reply_markup(reply_markup=keyboard(update))
            return
        await query.answer()
        if action == 'logout':
            session.logout(update.effective_user.id)
            await query.edit_message_reply_markup(reply_markup=keyboard(update))
            await update.effective_message.reply_text('Sei uscito da admin. Non riceverai nuovi QR.')
        elif action == 'qr':
            await self.qr_command(update, context)
        elif action == 'chats':
            await self.chats_command(update, context)
        elif action == 'challenge':
            await update.effective_message.reply_text('Scrivi /sfida seguito dal tema della sfida.')
