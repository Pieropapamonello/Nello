"""Public command buttons plus private, session-protected admin controls."""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram_admin import keyboard as admin_keyboard

OPTIONS = (
    ('Classifica settimanale', 'classifica'), ('Video più votati', 'votati'),
    ('Classifica mensile', 'mensile'), ('Record di sempre', 'record'),
    ('Il mio profilo', 'profilo'), ('Le mie statistiche', 'stats'),
)


def main_keyboard(update):
    buttons = [InlineKeyboardButton(label, callback_data='menu:' + name) for label, name in OPTIONS]
    rows = [buttons[index:index + 2] for index in range(0, len(buttons), 2)]
    admin = admin_keyboard(update)
    if admin:
        rows.extend(list(row) for row in admin.inline_keyboard)
    return InlineKeyboardMarkup(rows)


def callback(handlers):
    async def dispatch(update, context):
        query = update.callback_query
        name = query.data.removeprefix('menu:')
        handler = handlers.get(name)
        if not handler:
            await query.answer('Opzione non disponibile.', show_alert=True)
            return
        await query.answer()
        # effective_user is the person pressing the button, not the menu sender.
        await handler(update, context)
    return dispatch
