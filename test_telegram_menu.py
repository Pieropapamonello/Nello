import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from telegram_menu import main_keyboard, callback, OPTIONS
from telegram_admin import session


class MenuTests(unittest.IsolatedAsyncioTestCase):
    def tearDown(self):
        session.logout(session.user)

    def update(self, kind='private'):
        return SimpleNamespace(effective_chat=SimpleNamespace(type=kind),
                               effective_user=SimpleNamespace(id=123))

    def test_every_public_command_has_a_button_before_login(self):
        session.logout(session.user)
        data = [button.callback_data for row in main_keyboard(self.update()).inline_keyboard for button in row]
        self.assertTrue(all('menu:' + name in data for _, name in OPTIONS))
        self.assertIn('adm:login', data)
        self.assertNotIn('adm:qr', data)
        self.assertNotIn('adm:code', data)

    @patch.dict('os.environ', {'ADMIN_PASSWORD': 'test-password'})
    def test_qr_and_code_buttons_are_only_for_logged_in_admin_in_private(self):
        session.authenticate(123, 'test-password')
        data = [button.callback_data for row in main_keyboard(self.update()).inline_keyboard for button in row]
        self.assertIn('adm:qr', data)
        self.assertIn('adm:code', data)
        update = self.update(); update.effective_user.id = 456
        data = [b.callback_data for row in main_keyboard(update).inline_keyboard for b in row]
        self.assertNotIn('adm:qr', data)
        data = [b.callback_data for row in main_keyboard(self.update('supergroup')).inline_keyboard for b in row]
        self.assertTrue(all(value.startswith('menu:') for value in data))

    async def test_button_dispatch_uses_the_clicking_user_and_rejects_unknown_actions(self):
        handler = AsyncMock()
        dispatcher = callback({'stats': handler})
        update = self.update()
        update.callback_query = SimpleNamespace(data='menu:stats', answer=AsyncMock())
        context = object()
        await dispatcher(update, context)
        handler.assert_awaited_once_with(update, context)
        self.assertEqual(handler.await_args.args[0].effective_user.id, 123)
        update.callback_query.data = 'menu:unknown'
        await dispatcher(update, context)
        self.assertEqual(handler.await_count, 1)


if __name__ == '__main__':
    unittest.main()
