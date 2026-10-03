import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from wa_qr import WhatsAppQR, command


class PairingTests(unittest.IsolatedAsyncioTestCase):
    def make_pairing(self, admin=123):
        import os
        from telegram_admin import session
        session.user = 123
        session.expires = __import__('time').monotonic() + 60
        session.password = os.getenv('ADMIN_PASSWORD', '')
        store = SimpleNamespace(get_admin_chat=AsyncMock(return_value=admin))
        return WhatsAppQR(SimpleNamespace(ranking_store=store, admin_user_id=0,
                                          telegram_token='test-token'))

    @patch('wa_qr.requests.post')
    async def test_configured_or_persisted_admin_without_login_never_gets_qr(self, post):
        from telegram_admin import session
        pairing = self.make_pairing()
        session.logout(123)
        self.assertFalse((await pairing.update({'qr': 'sensitive-qr-value' * 4}))['ok'])
        post.assert_not_called()

    @patch('wa_qr.requests.post')
    async def test_group_admin_never_receives_pairing_material(self, post):
        pairing = self.make_pairing(-100123)
        self.assertFalse((await pairing.update({'qr': 'sensitive-qr-value' * 4}))['ok'])
        post.assert_not_called()

    @patch('wa_qr.requests.post')
    async def test_qr_is_png_and_rotations_edit_one_private_message(self, post):
        post.return_value.json.return_value = {'ok': True, 'result': {'message_id': 7}}
        pairing = self.make_pairing()
        first = 'sensitive-first-qr-value' * 4
        self.assertTrue((await pairing.update({'qr': first}))['ok'])
        sent = post.call_args
        self.assertTrue(sent.args[0].endswith('/sendPhoto'))
        self.assertEqual(sent.kwargs['data']['chat_id'], 123)
        self.assertTrue(sent.kwargs['files']['photo'][1].startswith(b'\x89PNG'))
        self.assertNotIn(first, str(sent.kwargs['data']))
        await pairing.update({'qr': 'sensitive-next-qr-value' * 4})
        self.assertTrue(post.call_args.args[0].endswith('/editMessageMedia'))
        self.assertEqual(post.call_args.kwargs['data']['message_id'], 7)
        await pairing.update({'connected': True})
        self.assertTrue(post.call_args.args[0].endswith('/deleteMessage'))
        self.assertEqual(pairing.status(), {'connected': True, 'qr_available': False})

    @patch('wa_qr.requests.post')
    async def test_expired_or_disconnected_qr_cannot_be_resent(self, post):
        pairing = self.make_pairing()
        pairing.qr = 'expired-qr'
        pairing.expires = 0
        self.assertFalse((await pairing.resend())['ok'])
        post.assert_not_called()
        await pairing.update({'connected': False})
        self.assertIsNone(pairing.qr)

    @patch('wa_qr.requests.post')
    async def test_failed_delivery_does_not_suppress_retry(self, post):
        pairing = self.make_pairing()
        post.return_value.json.return_value = {'ok': False}
        qr = 'sensitive-qr-value' * 4
        self.assertFalse((await pairing.update({'qr': qr}))['ok'])
        post.return_value.json.return_value = {'ok': True, 'result': {'message_id': 7}}
        self.assertTrue((await pairing.update({'qr': qr}))['ok'])
        self.assertEqual(post.call_count, 2)

    @patch('wa_qr.aiohttp.ClientSession')
    async def test_non_admin_and_group_commands_never_contact_bridge(self, session):
        handler = command(AsyncMock(return_value=123))
        for user, chat, kind in ((456, 456, 'private'), (123, -100, 'supergroup')):
            update = SimpleNamespace(effective_user=SimpleNamespace(id=user),
                                     effective_chat=SimpleNamespace(id=chat, type=kind),
                                     effective_message=SimpleNamespace(reply_text=AsyncMock()))
            await handler(update, MagicMock())
            update.effective_message.reply_text.assert_awaited_once()
        session.assert_not_called()


if __name__ == '__main__':
    unittest.main()
