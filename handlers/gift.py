from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import get_user_collection, get_user_by_username, transfer_card, transfer_coins, can_gift_card, can_gift_coins, get_card
from utils.helpers import delete_previous_messages
import logging

logger = logging.getLogger(__name__)

async def gift_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat

    await delete_previous_messages(context, chat.id, user.id)
    await show_gift_menu(update, context)

async def show_gift_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        message = query.message
    else:
        message = update.message

    keyboard = [
        [InlineKeyboardButton("Подарить монеты", callback_data='gift_coins')],
        [InlineKeyboardButton("Подарить карточку", callback_data='gift_card')],
        [InlineKeyboardButton("Назад", callback_data='main_menu')]
    ]

    if update.callback_query:
        await query.edit_message_text(
            text="Выберите что хотите подарить:",
            reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await message.reply_text(
            text="Выберите что хотите подарить:",
            reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_gift_coins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    context.user_data['gift_type'] = 'coins'
    await query.message.reply_text(
        "Ответе на это сообщение и введите сумму монет и username получателя через пробел (например: 10 @username)"
    )

async def handle_gift_card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    collection = get_user_collection(user_id)

    if not collection:
        await query.message.reply_text("❌ Ваша коллекция пуста")
        return

    keyboard = []
    for card in collection:
        if card['quantity'] >= 1:
            remaining = card['quantity']
            button_text = f"{card['name']} (осталось: {remaining})" if remaining - 1 > 0 else f"{card['name']} (последняя)"
            keyboard.append([
                InlineKeyboardButton(
                    button_text,
                    callback_data=f'select_card_{card["card_id"]}'
                )
            ])

    if not keyboard:
        await query.message.reply_text("❌ У вас нет карточек для подарка")
        return

    keyboard.append([InlineKeyboardButton("Назад", callback_data='gift_menu')])

    context.user_data['gift_type'] = 'card'
    await query.message.reply_text(
        "Выберите карточку для подарка:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def select_card_for_gift(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    card_id = int(query.data.split('_')[2])
    context.user_data['gift_card_id'] = card_id

    await query.message.reply_text(
        "Ответе на это сообщение и введите username получателя (например: @username)"
    )


async def process_gift(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    username = update.message.from_user.username or update.message.from_user.first_name
    sender_mention = f"[{username}](tg://user?id={user_id})"
    text = update.message.text.strip()

    if 'gift_type' not in context.user_data:
        return

    if context.user_data['gift_type'] == 'coins':
        try:
            parts = text.split()
            if len(parts) != 2 or not parts[0].isdigit() or not parts[1].startswith('@'):
                raise ValueError

            amount = int(parts[0])
            receiver_username = parts[1][1:]

            receiver = get_user_by_username(receiver_username)

            if not receiver:
                await update.message.reply_text("❌ Пользователь не найден")
                return

            if receiver['user_id'] == user_id:
                await update.message.reply_text("❌ Нельзя дарить себе!")
                return

            if not can_gift_coins(user_id, amount):
                await update.message.reply_text("❌ Недостаточно монет!")
                return

            if transfer_coins(user_id, receiver['user_id'], amount):
                receiver_mention = f"[{receiver_username}](tg://user?id={receiver['user_id']})"

                # Сообщение отправителю
                await update.message.reply_text(
                    f"🎁 Вы подарили {receiver_mention} {amount} монет!",
                    parse_mode='Markdown'
                )

                # Сообщение получателю
                try:
                    await context.bot.send_message(
                        chat_id=receiver['user_id'],
                        text=f"🎁 Вам подарили {amount} монет от {sender_mention}!",
                        parse_mode='Markdown'
                    )
                except Exception as e:
                    logger.error(f"Не удалось отправить сообщение получателю: {e}")

            else:
                await update.message.reply_text("❌ Ошибка при передаче монет")

        except ValueError:
            await update.message.reply_text("❌ Неверный формат. Пример: `10 @username`", parse_mode='Markdown')

    elif context.user_data['gift_type'] == 'card':
        try:
            if not text.startswith('@'):
                raise ValueError

            receiver_username = text[1:]
            card_id = context.user_data['gift_card_id']

            receiver = get_user_by_username(receiver_username)

            if not receiver:
                await update.message.reply_text("❌ Пользователь не найден")
                return

            if receiver['user_id'] == user_id:
                await update.message.reply_text("❌ Нельзя дарить себе!")
                return

            if not can_gift_card(user_id, card_id):
                await update.message.reply_text("❌ У вас нет этой карточки!")
                return

            if transfer_card(user_id, receiver['user_id'], card_id):
                card = get_card(card_id)
                card_name = card['name'] if card else f"карточка #{card_id}"
                receiver_mention = f"[{receiver_username}](tg://user?id={receiver['user_id']})"

                # Сообщение отправителю
                if card and card.get('image_url'):
                    try:
                        await update.message.reply_photo(
                            photo=card['image_url'],
                            caption=f"🎁 Вы подарили {receiver_mention} карточку: {card_name}!",
                            parse_mode='Markdown'
                        )
                    except Exception as e:
                        logger.error(f"Ошибка отправки картинки карточки отправителю: {e}")
                        await update.message.reply_text(
                            f"🎁 Вы подарили {receiver_mention} карточку: {card_name}!",
                            parse_mode='Markdown'
                        )
                else:
                    await update.message.reply_text(
                        f"🎁 Вы подарили {receiver_mention} карточку: {card_name}!",
                        parse_mode='Markdown'
                    )

                # Сообщение получателю с изображением карточки
                try:
                    if card and card.get('image_url'):
                        await context.bot.send_photo(
                            chat_id=receiver['user_id'],
                            photo=card['image_url'],
                            caption=f"🎁 Вам подарили карточку: {card_name} от {sender_mention}!",
                            parse_mode='Markdown'
                        )
                    else:
                        await context.bot.send_message(
                            chat_id=receiver['user_id'],
                            text=f"🎁 Вам подарили карточку: {card_name} от {sender_mention}!",
                            parse_mode='Markdown'
                        )
                except Exception as e:
                    logger.error(f"Не удалось отправить сообщение получателю: {e}")

            else:
                await update.message.reply_text("❌ Ошибка при передаче карточки")

        except ValueError:
            await update.message.reply_text("❌ Неверный формат. Пример: `@username`", parse_mode='Markdown')

    context.user_data.clear()