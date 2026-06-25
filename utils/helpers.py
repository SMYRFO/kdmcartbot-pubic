import random
import logging
from datetime import datetime, timedelta
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config import COIN_COOLDOWN

logger = logging.getLogger(__name__)

# Глобальные переменные для трекинга сообщений
USER_LAST_MESSAGES = {}
USER_COLLECTIONS = {}


def log_user_activity(user_id: int, username: str, action: str, details: str = ""):
    logger.info(f"USER ACTIVITY | ID: {user_id} | Username: @{username} | Action: {action} | {details}")


def check_coins(user_id):
    from database import get_user, update_user

    user = get_user(user_id)
    if not user:
        return 0

    last_coin_time = datetime.fromisoformat(user['last_coin_time']) if user['last_coin_time'] else None
    now = datetime.now()

    if last_coin_time is None or (now - last_coin_time) > COIN_COOLDOWN:
        coins = random.randint(1, 10)
        update_user(user_id, {
            'coins': user['coins'] + coins,
            'last_coin_time': now.isoformat()
        })
        return coins
    return 0


async def track_message(user_id: int, message_id: int):
    """Трекинг сообщений с ограничением размера"""
    try:
        if user_id not in USER_LAST_MESSAGES:
            USER_LAST_MESSAGES[user_id] = []

        # Проверяем что message_id не None
        if message_id is not None:
            USER_LAST_MESSAGES[user_id].append(message_id)

            if len(USER_LAST_MESSAGES[user_id]) > 50:
                USER_LAST_MESSAGES[user_id] = USER_LAST_MESSAGES[user_id][-50:]
    except Exception as e:
        logger.error(f"Ошибка в track_message: {e}")

async def delete_previous_messages(context: ContextTypes.DEFAULT_TYPE, chat_id: int, user_id: int):
    """Безопасное удаление предыдущих сообщений"""
    if user_id in USER_LAST_MESSAGES:
        remaining_messages = []
        for msg_id in USER_LAST_MESSAGES[user_id]:
            try:
                await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
            except Exception as e:
                if "message not found" not in str(e).lower() and "message to delete not found" not in str(e).lower():
                    logger.warning(f"Couldn't delete message {msg_id}: {e}")
                remaining_messages.append(msg_id)

        USER_LAST_MESSAGES[user_id] = remaining_messages


async def cleanup_user_messages(user_id: int, chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    """Clean up all tracked messages for a user"""
    if user_id in USER_LAST_MESSAGES:
        for msg_id in USER_LAST_MESSAGES[user_id]:
            try:
                await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
            except Exception as e:
                if "message not found" not in str(e).lower() and "message to delete not found" not in str(e).lower():
                    logger.debug(f"Couldn't delete message {msg_id} during cleanup: {e}")
        USER_LAST_MESSAGES[user_id] = []


def cleanup_old_messages():
    """Очищает устаревшие сообщения из трекинга"""
    global USER_LAST_MESSAGES

    for user_id in list(USER_LAST_MESSAGES.keys()):
        if len(USER_LAST_MESSAGES[user_id]) > 50:
            USER_LAST_MESSAGES[user_id] = USER_LAST_MESSAGES[user_id][-50:]

        if not USER_LAST_MESSAGES[user_id]:
            del USER_LAST_MESSAGES[user_id]


async def safe_edit_or_send(update, text, reply_markup=None, parse_mode='Markdown'):
    """Безопасное редактирование или отправка нового сообщения"""
    try:
        if hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.edit_message_text(
                text=text,
                parse_mode=parse_mode,
                reply_markup=reply_markup
            )
            return update.callback_query.message
        else:
            return await update.message.reply_text(
                text=text,
                parse_mode=parse_mode,
                reply_markup=reply_markup
            )
    except Exception as edit_error:
        if "message to edit not found" in str(edit_error).lower():
            logger.debug(f"Сообщение для редактирования не найдено, отправляем новое")
        if hasattr(update, 'callback_query') and update.callback_query:
            return await update.callback_query.message.reply_text(
                text=text,
                parse_mode=parse_mode,
                reply_markup=reply_markup
            )
        else:
            return await update.message.reply_text(
                text=text,
                parse_mode=parse_mode,
                reply_markup=reply_markup
            )


async def give_case_card(user_id: int, chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    """Выдает случайную карточку пользователю и показывает ее характеристики"""
    try:
        from database import get_case_contents, add_to_collection, get_card

        case_contents = get_case_contents(1)
        if not case_contents:
            return

        card_id = random.choice(case_contents)
        add_to_collection(user_id, card_id)

        card = get_card(card_id)
        if not card:
            return

        # Получаем характеристики карточки
        from handlers.fight import get_card_stats  # Импортируем функцию получения характеристик
        card_stats = get_card_stats(card_id)

        user = await context.bot.get_chat_member(chat_id, user_id)
        mention = f"[{user.user.first_name}](tg://user?id={user_id})"

        from handlers.fight import get_card_stats
        card_stats = get_card_stats(card_id)
        health_display = int(card_stats['health'])
        damage_display = f"{card_stats['damage']:.1f}"

        message_text = (
            f"🎉 {mention} получил новую карточку!\n\n"
            f"*{card['name']}*\n"
            f"Редкость: {card['rarity']}\n"
            f"❤️ Здоровье: {health_display}\n"
            f"⚔️ Урон: {damage_display}"
        )

        if card.get('image_url'):
            try:
                await context.bot.send_photo(
                    chat_id=chat_id,
                    photo=card['image_url'],
                    caption=message_text,
                    parse_mode='Markdown'
                )
                return
            except Exception as e:
                logger.error(f"Ошибка отправки изображения карточки: {e}")

        await context.bot.send_message(
            chat_id=chat_id,
            text=message_text,
            parse_mode='Markdown'
        )

    except Exception as e:
        logger.error(f"Ошибка в give_case_card: {e}")