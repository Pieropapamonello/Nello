import time
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from telegram_admin import AdminSession, AdminUI, keyboard, session


class LoginTests(unittest.IsolatedAsyncioTestCase):
    def tearDown(self):
        session.logout(session.user)

    @patch.dict('os.environ', {'ADMIN_PASSWORD': 'test-password'})
    def test_login_expiry_logout_password_change(self):
        auth = AdminSession()
        self.assertEqual(auth.current(), 0)
        self.assertIsNotNone(auth.authenticate(123, 'wrong'))
        self.assertIsNone(auth.authenticate(123, 'test-password'))
        self.assertEqual(auth.current(), 123)
        auth.expires = 0
        self.assertEqual(auth.current(), 0)
        auth.authenticate(123, 'test-password')
        with patch.dict('os.environ', {'ADMIN_PASSWORD': 'changed'}):
            self.assertEqual(auth.current(), 0)
        auth.logout(123)
        self.assertEqual(auth.current(), 0)

    def test_login_button_is_private_and_admin_menu_requires_active_login(self):
        session.logout(session.user)
        update = SimpleNamespace(effective_chat=SimpleNamespace(type='private'), effective_user=SimpleNamespace(id=123))
        self.assertEqual(keyboard(update).inline_keyboard[0][0].callback_data, 'adm:login')
        update.effective_chat.type = 'supergroup'
        self.assertIsNone(keyboard(update))

    @patch.dict('os.environ', {'ADMIN_PASSWORD': 'test-password', 'WHATSAPP_ENABLED': '0'})
    async def test_store_failure_revokes_login_instead_of_claiming_success(self):
        store = SimpleNamespace(set_admin_chat=AsyncMock(side_effect=RuntimeError()))
        ui = AdminUI(store, AsyncMock(), AsyncMock())
        update = SimpleNamespace(effective_user=SimpleNamespace(id=123), effective_chat=SimpleNamespace(type='private'),
                                 effective_message=SimpleNamespace(reply_text=AsyncMock()))
        await ui.login(update, SimpleNamespace(), 'test-password')
        self.assertEqual(session.current(), 0)

    async def test_old_admin_button_cannot_run_command_without_login(self):
        session.logout(session.user)
        qr, chats = AsyncMock(), AsyncMock()
        ui = AdminUI(None, qr, chats)
        query = SimpleNamespace(data='adm:qr', answer=AsyncMock(), edit_message_reply_markup=AsyncMock())
        update = SimpleNamespace(effective_user=SimpleNamespace(id=123), effective_chat=SimpleNamespace(type='private'), callback_query=query)
        await ui.callback(update, None)
        qr.assert_not_awaited()
        chats.assert_not_awaited()


if __name__ == '__main__':
    unittest.main()
