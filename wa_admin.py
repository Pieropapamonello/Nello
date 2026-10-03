"""Private WhatsApp admin sessions; authorization is checked on every action."""
import hmac
import asyncio
import os
import re
import time

from cookie_admin import CookieAdmin, LABELS, STATES, ISSUES

ROWS = [
    {'id': 'waadmin:cookies', 'title': 'Stato cookie'},
    {'id': 'waadmin:update_cookies', 'title': 'Aggiorna cookie'},
    {'id': 'waadmin:chats', 'title': 'Chat del bot'},
    {'id': 'waadmin:challenge', 'title': 'Nuova sfida'},
    {'id': 'waadmin:logout', 'title': 'Esci da admin'},
]


class WhatsAppAdmin:
    def __init__(self, store):
        self.store = store
        self.sessions = {}
        self.attempts = {}

    async def handle(self, body):
        jid, sender = body.get('jid', ''), body.get('sender', '')
        # Group administration in WhatsApp does not grant bot administration.
        if not isinstance(jid, str) or not re.fullmatch(r'\d+@(s\.whatsapp\.net|lid)', jid):
            return {'handled': True, 'text': 'Usa i comandi admin soltanto nella chat privata del bot.'}
        if sender != jid:
            return {'handled': True, 'text': 'Richiesta non autorizzata.'}
        text, action = body.get('text', ''), body.get('action', '')
        if not isinstance(text, str) or not isinstance(action, str) or len(text) > 4096:
            return {'handled': True, 'text': 'Richiesta non valida.'}
        now = time.monotonic()
        self.sessions = {j: s for j, s in self.sessions.items() if s[0] > now}
        self.attempts = {j: s for j, s in self.attempts.items() if s[1] > now}
        password = os.getenv('ADMIN_PASSWORD', '')
        result = {'handled': True}
        if text.split(maxsplit=1)[:1] == ['/admin']:
            if not password:
                return {**result, 'text': 'Password amministratore non configurata.'}
            parts = text.split(maxsplit=1)
            if len(parts) < 2:
                if jid in self.sessions and self.sessions[jid][1] == password:
                    return self.menu()
                return {**result, 'text': 'Accedi con /admin seguito dalla password, solo in questa chat privata.'}
            count, until = self.attempts.get(jid, (0, now + 900))
            if count >= 5 or sum(s[0] for s in self.attempts.values()) >= 100:
                return {**result, 'text': 'Troppi tentativi. Riprova tra 15 minuti.'}
            if not hmac.compare_digest(parts[1].encode(), password.encode()):
                self.attempts[jid] = (count + 1, until)
                return {**result, 'text': 'Password non corretta.'}
            self.attempts.pop(jid, None)
            self.sessions[jid] = (now + 43200, password)
            return self.menu('Accesso admin riuscito. La sessione dura 12 ore e termina al riavvio del bot.')
        if jid not in self.sessions or self.sessions[jid][1] != password or not password:
            self.sessions.pop(jid, None)
            return {**result, 'text': 'Accedi prima con /admin seguito dalla password, in privato.'}
        action = action.removeprefix('waadmin:') if action.startswith('waadmin:') else text.split(maxsplit=1)[0].removeprefix('/') if text else ''
        if action in ('menu', 'admin'):
            return self.menu()
        if action == 'logout':
            self.sessions.pop(jid, None)
            return {**result, 'text': 'Sei uscito dalla modalità admin.'}
        if action == 'cookies':
            try:
                data = await asyncio.wait_for(CookieAdmin(None).api(), timeout=20)
                lines = ['Stato cookie']
                for platform, item in data.get('platforms', {}).items():
                    if platform in LABELS:
                        state = ISSUES.get(item.get('issue')) or STATES.get(item.get('state'), 'da verificare')
                        lines.append(LABELS[platform] + ': ' + state)
                return {**result, 'text': '\n'.join(lines)}
            except Exception:
                return {**result, 'text': 'Downloader momentaneamente non raggiungibile. Riprova tra poco.'}
        if action == 'update_cookies':
            return {**result, 'text': 'Per aggiornare i cookie apri il bot Telegram e usa /cookies nella chat privata admin. Gli aggiornamenti valgono anche per WhatsApp e Discord.'}
        if action == 'chats':
            try:
                chats = await self.store.get_chats()
                lines = ['Chat che usano il bot']
                for chat in chats[:30]:
                    lines.append(f"• {str(chat.get('title') or chat.get('id'))[:100]} — {chat.get('count', 0)} download")
                return {**result, 'text': '\n'.join(lines) if chats else 'Nessuna chat registrata.'}
            except Exception:
                return {**result, 'text': 'Database momentaneamente non disponibile.'}
        if action in ('challenge', 'sfida'):
            parts = text.split(maxsplit=1)
            if action == 'challenge' or len(parts) < 2:
                return {**result, 'text': 'Scrivi /sfida seguito dal tema, per esempio: /sfida il video più assurdo'}
            theme = parts[1].strip()[:300]
            try:
                await self.store.set_challenge(theme, 'Admin WhatsApp')
                return {**result, 'text': 'Sfida impostata:\n\n' + theme}
            except Exception:
                return {**result, 'text': 'Non riesco a salvare la sfida. Riprova tra poco.'}
        return {**result, 'text': 'Comando non disponibile. Usa /menu.'}

    @staticmethod
    def menu(text='Menu amministratore'):
        return {'handled': True, 'text': text, 'menu': ROWS}
