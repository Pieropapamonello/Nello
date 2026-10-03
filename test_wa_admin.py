import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from wa_admin import WhatsAppAdmin


@patch.dict('os.environ', {'ADMIN_PASSWORD': 'test-password'})
class AdminTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.store = SimpleNamespace(get_chats=AsyncMock(return_value=[]),
                                     set_challenge=AsyncMock())
        self.admin = WhatsAppAdmin(self.store)
        self.jid = '391234567890@s.whatsapp.net'

    async def request(self, text='', action='', jid=None, sender=None):
        jid = jid or self.jid
        return await self.admin.handle({'jid': jid, 'sender': sender or jid,
                                        'text': text, 'action': action})

    async def test_menu_only_after_private_password_login(self):
        self.assertNotIn('menu', await self.request('/menu'))
        self.assertNotIn('menu', await self.request('/admin wrong'))
        result = await self.request('/admin test-password')
        self.assertIn('menu', result)
        self.assertIn('menu', await self.request('/menu'))
        self.assertNotIn('menu', await self.request('/menu', jid='391234000000@lid'))

    async def test_group_and_mismatched_sender_cannot_authenticate(self):
        for jid, sender in (('123-456@g.us', self.jid), (self.jid, '999@lid')):
            self.assertNotIn('menu', await self.request('/admin test-password', jid=jid, sender=sender))
        self.assertFalse(self.admin.sessions)

    async def test_every_button_requires_session_and_logout_revokes_it(self):
        await self.request(action='waadmin:chats')
        self.store.get_chats.assert_not_awaited()
        await self.request('/admin test-password')
        await self.request(action='waadmin:chats')
        self.store.get_chats.assert_awaited_once()
        await self.request(action='waadmin:logout')
        await self.request(action='waadmin:chats')
        self.assertEqual(self.store.get_chats.await_count, 1)
        self.assertNotIn('menu', await self.request('/menu'))

    async def test_expiry_and_password_change_revoke_access(self):
        await self.request('/admin test-password')
        self.admin.sessions[self.jid] = (0, 'test-password')
        self.assertNotIn('menu', await self.request('/menu'))
        await self.request('/admin test-password')
        with patch.dict('os.environ', {'ADMIN_PASSWORD': 'changed-password'}):
            self.assertNotIn('menu', await self.request('/menu'))

    async def test_failed_logins_are_limited(self):
        for _ in range(5):
            await self.request('/admin wrong')
        result = await self.request('/admin test-password')
        self.assertNotIn('menu', result)
        self.assertIn('Troppi tentativi', result['text'])

    async def test_forged_buttons_never_change_challenge(self):
        await self.request('/sfida tema')
        self.store.set_challenge.assert_not_awaited()
        await self.request('/admin test-password')
        await self.request(action='waadmin:challenge')
        self.store.set_challenge.assert_not_awaited()
        await self.request('/sfida il video più assurdo')
        self.store.set_challenge.assert_awaited_once_with('il video più assurdo', 'Admin WhatsApp')


if __name__ == '__main__':
    unittest.main()
