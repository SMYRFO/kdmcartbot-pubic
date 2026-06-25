from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ChatMemberStatus
from datetime import datetime, timedelta
from database import get_user, update_user
from utils.helpers import check_coins, delete_previous_messages
from config import CHANNEL_ID
import logging
from handlers.fight import get_card_stats  # Добавьте этот импорт

logger = logging.getLogger(__name__)


async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat

    await delete_previous_messages(context, chat.id, user.id)
    await show_balance(update, context)


async def show_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from database import get_user
    from utils.helpers import give_case_card

    if update.callback_query:
        query = update.callback_query
        await query.answer()
        user = query.from_user
        chat_id = query.message.chat.id
        message = query.message
    else:
        user = update.effective_user
        chat_id = update.effective_chat.id
        message = update.message

    mention = f"[{user.first_name}](tg://user?id={user.id})"
    new_coins = check_coins(user.id)
    user_data = get_user(user.id)

    if new_coins > 0:
        await give_case_card(user.id, chat_id, context)
        message_text = f"🎁 {mention} получил {new_coins} монет!\n\n"
    else:
        if user_data['last_coin_time']:
            next_coin_time = datetime.fromisoformat(user_data['last_coin_time']) + timedelta(hours=3)
            remaining = next_coin_time - datetime.now()
            hours = remaining.seconds // 3600
            minutes = (remaining.seconds % 3600) // 60
            message_text = f"⏳ Следующие монеты через {hours}ч {minutes}м\n\n"
        else:
            message_text = ""

    message_text += f"💰 Баланс {mention}: {user_data['coins']} монет"

    keyboard = [
        [InlineKeyboardButton("Главное меню", callback_data='main_menu')]
    ]

    if update.callback_query:
        await query.edit_message_text(
            text=message_text,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await message.reply_text(
            text=message_text,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard))


async def check_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    from utils.helpers import give_case_card

    user = update.effective_user
    chat_id = update.effective_chat.id

    try:
        member = await context.bot.get_chat_member(CHANNEL_ID, user.id)

        if member.status in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
            user_data = get_user(user.id)
            if not user_data:
                from database import add_user
                add_user(user.id, user.username)
                user_data = get_user(user.id)

            now = datetime.now()
            last_reward_str = user_data.get('last_reward_date')
            last_reward = datetime.fromisoformat(last_reward_str) if last_reward_str else None

            if last_reward is None or last_reward.date() < now.date():
                update_user(user.id, {'last_reward_date': now.isoformat()})
                await update.message.reply_text(
                    "✅ Вы подписаны на наш канал! Вот ваша ежедневная награда!",
                    parse_mode=None
                )
                await give_case_card(user.id, chat_id, context)  # Теперь покажет характеристики
            else:
                next_reward_time = last_reward + timedelta(days=1)
                hours_left = (next_reward_time - now).seconds // 3600
                minutes_left = ((next_reward_time - now).seconds % 3600) // 60

                await update.message.reply_text(
                    f"✅ Вы подписаны на наш канал!\n"
                    f"Следующую награду можно получить через {hours_left}ч {minutes_left}м",
                    parse_mode=None
                )
        else:
            keyboard = [[InlineKeyboardButton("Подписаться", url=f"https://t.me/{CHANNEL_ID[1:]}")]]
            await update.message.reply_text(
                "❌ Пожалуйста, подпишитесь на наш канал, чтобы получать ежедневные награды:",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=None
            )

    except Exception as e:
        logger.error(f"Ошибка проверки подписки: {e}")
        await update.message.reply_text(
            "⚠️ Произошла ошибка при проверке подписки. Попробуйте позже.",
            parse_mode=None
        )