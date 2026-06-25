from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import add_user
from utils.helpers import delete_previous_messages, track_message
import logging

logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat

    from utils.helpers import log_user_activity
    log_user_activity(user.id, user.username, "Start command", "User initiated the bot")

    await delete_previous_messages(context, chat.id, user.id)
    add_user(user.id, user.username)
    await send_main_menu(update, context)


async def send_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat_id = update.effective_chat.id
    mention = f"[{user.first_name}](tg://user?id={user.id})"

    await delete_previous_messages(context, chat_id, user.id)

    keyboard = [
        [InlineKeyboardButton("👤 Профиль", callback_data='show_main_profile')],
        [InlineKeyboardButton("🏪 Магазины", callback_data='shop')],
        [InlineKeyboardButton("⚔️ Арена боев", callback_data='fight_menu')],
        [
            InlineKeyboardButton("🔄 Обмен карточек", callback_data='trade_menu'),
            InlineKeyboardButton("🛟 Поддержка", callback_data='support')
        ]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)
    text = (f"Привет, {mention}! Это бот для коллекционирования карточек. \n\n"
            f"❗️Раз в 3 часа ты можешь получить бесплатную карточку \n"
            f"и монеты, нажав кнопку 'мой баланс' или прописав '/balance' \n\n"
            f"❗️Раз в сутки можно получить "
            f"дополнительную карточку, \n подписавшись на канал разработчиков и прописав '/check'\n\n "
            f"Выберите действие:\n\n")

    try:
        msg = None
        if update.callback_query:
            try:
                await update.callback_query.edit_message_text(
                    text=text,
                    parse_mode='Markdown',
                    reply_markup=reply_markup
                )
                msg = update.callback_query.message
            except Exception as edit_error:
                if "message to edit not found" in str(edit_error).lower():
                    logger.debug(f"Сообщение для редактирования не найдено, отправляем новое")
                msg = await context.bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    parse_mode='Markdown',
                    reply_markup=reply_markup
                )
        else:
            msg = await context.bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )

        if msg and hasattr(msg, 'message_id'):
            await track_message(user.id, msg.message_id)
        return msg

    except Exception as e:
        logger.error(f"Ошибка в send_main_menu: {e}")
        try:
            msg = await context.bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode='Markdown'
            )
            if msg and hasattr(msg, 'message_id'):
                await track_message(user.id, msg.message_id)
            return msg
        except Exception as fallback_error:
            logger.critical(f"Complete failure in send_main_menu: {fallback_error}")
            return None