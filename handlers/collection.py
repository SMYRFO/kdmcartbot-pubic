from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import ContextTypes
from database import get_user_collection, get_cards, get_user
from utils.helpers import USER_COLLECTIONS, track_message
import logging

logger = logging.getLogger(__name__)


async def my_collection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat

    if update.message:
        try:
            await context.bot.delete_message(chat_id=chat.id, message_id=update.message.message_id)
        except Exception as e:
            logger.error(f"Ошибка при удалении сообщения команды: {e}")

    # Показываем полную коллекцию в виде списка
    await show_full_collection_excel(update, context)

    # Дополнительно загружаем данные для постраничного просмотра
    collection = get_user_collection(user.id)
    cards_data = get_cards()

    if not collection:
        return

    enriched_collection = []
    for item in collection:
        card_info = next((c for c in cards_data if c['card_id'] == item['card_id']), None)
        if card_info:
            enriched_collection.append({
                'card_id': item['card_id'],
                'quantity': item['quantity'],
                'image_url': card_info.get('image_url'),
                'name': card_info.get('name'),
                'rarity': card_info.get('rarity', 1)
            })

    USER_COLLECTIONS[user.id] = {
        'cards': enriched_collection,
        'page': 0,
        'last_message_id': None
    }

async def show_collection_page(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 0):
    if update.callback_query:
        query = update.callback_query
        user = query.from_user
        chat_id = query.message.chat_id
        message_id = query.message.message_id
        await query.answer()
    else:
        user = update.effective_user
        chat_id = update.effective_chat.id
        message_id = None

    user_id = user.id
    mention = f"[{user.first_name}](tg://user?id={user_id})"
    collection_data = USER_COLLECTIONS.get(user_id)

    if not collection_data:
        await my_collection(update, context)
        return

    cards = collection_data.get('cards', [])
    if not cards:
        # Пытаемся обновить существующее сообщение
        if message_id:
            try:
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text="Ваша коллекция пуста!",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("В магазин", callback_data='shop')]])
                )
                return
            except Exception as e:
                logger.warning(f"Не удалось обновить сообщение: {e}")

        # Если обновить не удалось, отправляем новое
        await context.bot.send_message(
            chat_id=chat_id,
            text="Ваша коллекция пуста!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("В магазин", callback_data='shop')]])
        )
        return

    total_pages = len(cards)
    current_page = max(0, min(page, total_pages - 1))
    USER_COLLECTIONS[user_id]['page'] = current_page
    card = cards[current_page]

    # Получаем характеристики карточки
    try:
        from handlers.fight import get_card_stats
        card_stats = get_card_stats(card['card_id'])
        # Форматируем значения для отображения
        health_display = int(card_stats['health'])
        damage_display = f"{card_stats['damage']:.1f}"
    except Exception as e:
        logger.error(f"Ошибка получения характеристик карточки: {e}")
        # Используем значения по умолчанию в случае ошибки
        health_display = 50
        damage_display = "8.0"

    caption = (
        f"🏆 *Коллекция карточек* {mention}\n\n"
        f"*{card['name']}* (x{card['quantity']})\n"
        f"Редкость: {card['rarity']}\n"
        f"❤️ Здоровье: {health_display}\n"
        f"⚔️ Урон: {damage_display}\n\n"
        f"Страница {current_page + 1}/{total_pages}"
    )

    keyboard = []
    nav_buttons = []

    if current_page > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ Назад", callback_data=f'collection_prev_{current_page}'))
    if current_page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton("Вперед ➡️", callback_data=f'collection_next_{current_page}'))

    if nav_buttons:
        keyboard.append(nav_buttons)

    keyboard.extend([
        [InlineKeyboardButton("📋 Вся коллекция", callback_data='full_collection')],
        [InlineKeyboardButton("Назад", callback_data='main_menu')]
    ])

    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        # Если есть существующее сообщение и оно с фото - обновляем его
        if message_id and card.get('image_url'):
            try:
                await context.bot.edit_message_media(
                    chat_id=chat_id,
                    message_id=message_id,
                    media=InputMediaPhoto(
                        media=card['image_url'],
                        caption=caption,
                        parse_mode='Markdown'
                    ),
                    reply_markup=reply_markup
                )
                USER_COLLECTIONS[user_id]['last_message_id'] = message_id
                return
            except Exception as e:
                logger.warning(f"Не удалось обновить медиа, пробуем отправить новое: {e}")

        # Если есть существующее сообщение без фото или обновление не удалось
        if message_id:
            try:
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=caption,
                    parse_mode='Markdown',
                    reply_markup=reply_markup
                )
                USER_COLLECTIONS[user_id]['last_message_id'] = message_id
                return
            except Exception as e:
                logger.warning(f"Не удалось обновить текст, отправляем новое сообщение: {e}")

        # Отправляем новое сообщение если обновление невозможно
        if card.get('image_url'):
            msg = await context.bot.send_photo(
                chat_id=chat_id,
                photo=card['image_url'],
                caption=caption,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
        else:
            msg = await context.bot.send_message(
                chat_id=chat_id,
                text=caption,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )

        if msg and hasattr(msg, 'message_id'):
            USER_COLLECTIONS[user_id]['last_message_id'] = msg.message_id
            await track_message(user_id, msg.message_id)

    except Exception as e:
        logger.error(f"Ошибка при работе с сообщением: {e}")
        # Фолбэк на текстовое сообщение
        try:
            msg = await context.bot.send_message(
                chat_id=chat_id,
                text=caption,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
            if msg and hasattr(msg, 'message_id'):
                USER_COLLECTIONS[user_id]['last_message_id'] = msg.message_id
                await track_message(user_id, msg.message_id)
        except Exception as e2:
            logger.error(f"Критическая ошибка: {e2}")

async def handle_collection_nav(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    collection_data = USER_COLLECTIONS.get(user_id)

    if not collection_data or 'cards' not in collection_data:
        await my_collection(update, context)
        return

    # Обработка переключения на полную коллекцию
    if query.data == 'full_collection':
        await show_full_collection_excel(update, context)
        return

    action, current_page = query.data.split('_')[1:]
    current_page = int(current_page)

    if action == 'prev':
        new_page = max(0, current_page - 1)
    elif action == 'next':
        new_page = min(len(collection_data['cards']) - 1, current_page + 1)
    else:
        return

    await show_collection_page(update, context, new_page)


async def show_full_collection_excel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from database import execute_query
    from config import RARITY_ORDER, RARITY_DISPLAY

    try:
        if update.callback_query:
            chat_id = update.callback_query.message.chat_id
            message_id = update.callback_query.message.message_id
        else:
            chat_id = update.effective_chat.id
            message_id = None

        # Исправленный запрос для суммирования количеств
        collections = execute_query('''
            SELECT card_id, SUM(quantity) as total_quantity 
            FROM collections 
            WHERE user_id = ? AND quantity > 0
            GROUP BY card_id
        ''', (update.effective_user.id,), fetch_all=True) or []

        cards = execute_query("SELECT * FROM cards", fetch_all=True) or []

        if not collections or not cards:
            if message_id:
                try:
                    await context.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=message_id,
                        text="❌ Ошибка загрузки данных"
                    )
                    return
                except Exception as e:
                    logger.warning(f"Не удалось обновить сообщение: {e}")

            await context.bot.send_message(chat_id, "❌ Ошибка загрузки данных")
            return

        card_data = {}
        for card in cards:
            try:
                card_id = card.get('card_id')
                if not card_id:
                    continue

                rarity_str = card.get('rarity', '🤍 Редкий')
                rarity_order = RARITY_ORDER.get(rarity_str, 0)

                card_data[card_id] = {
                    'name': str(card.get('name', f"Карточка #{card_id}")),
                    'rarity': rarity_order,
                    'rarity_name': RARITY_DISPLAY.get(rarity_order, "🤍 Редкий"),
                    'image': card.get('image_url')
                }
            except Exception as e:
                logger.error(f"Ошибка обработки карточки {card}: {e}")

        user_collection = []
        for item in collections:
            try:
                card_id = item.get('card_id')
                quantity = item.get('total_quantity', 0)

                if quantity > 0 and card_id in card_data:
                    user_collection.append({
                        'card_id': card_id,
                        'quantity': quantity,
                        **card_data[card_id]
                    })
            except (ValueError, TypeError) as e:
                logger.error(f"Ошибка обработки элемента коллекции {item}: {e}")

        if not user_collection:
            text = "🎒 Ваша коллекция пуста!\nПопробуйте открыть кейсы из /shop"
            markup = InlineKeyboardMarkup([[InlineKeyboardButton("🛍 В магазин", callback_data='shop')]])

            if message_id:
                try:
                    await context.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=message_id,
                        text=text,
                        reply_markup=markup
                    )
                    return
                except Exception as e:
                    logger.warning(f"Не удалось обновить сообщение: {e}")

            await context.bot.send_message(chat_id, text, reply_markup=markup)
            return

        # Сортируем по редкости (от самой высокой к самой низкой)
        user_collection.sort(key=lambda x: x['rarity'], reverse=True)

        message_lines = ["📚 *Ваша коллекция карточек*\n(от самых редких к обычным)\n"]

        current_rarity = None
        for item in user_collection:
            if item['rarity_name'] != current_rarity:
                current_rarity = item['rarity_name']
                message_lines.append(f"\n*{current_rarity}*")

            message_lines.append(f"▫️ {item['name']} (x{item['quantity']})")

        total = sum(item['quantity'] for item in user_collection)
        unique = len(user_collection)
        message_lines.append(f"\n*Итого:* {total} карточек ({unique} уникальных)")

        text = "\n".join(message_lines)

        # Проверяем длину сообщения и разделяем при необходимости
        if len(text) > 4096:
            # Используем функцию send_long_message для разделения
            await send_long_message(update, context, text)

            # Отправляем кнопки отдельным сообщением
            markup = InlineKeyboardMarkup([
                [InlineKeyboardButton("🖼 Посмотреть коллекцию", callback_data='page_collection')],
                [InlineKeyboardButton("🛍 Магазин", callback_data='shop'),
                 InlineKeyboardButton("🎁 Подарки", callback_data='gift_menu')],
                [InlineKeyboardButton("🔙 Назад", callback_data='show_main_profile')]
            ])

            await context.bot.send_message(
                chat_id,
                "Выберите действие:",
                reply_markup=markup
            )
            return

        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("🖼 Посмотреть коллекцию", callback_data='page_collection')],
            [InlineKeyboardButton("🛍 Магазин", callback_data='shop'),
             InlineKeyboardButton("🎁 Подарки", callback_data='gift_menu')],
            [InlineKeyboardButton("🔙 Назад", callback_data='show_main_profile')]
        ])

        if message_id:
            try:
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=text,
                    parse_mode='Markdown',
                    reply_markup=markup
                )
                return
            except Exception as e:
                logger.warning(f"Не удалось обновить сообщение: {e}")

        msg = await context.bot.send_message(
            chat_id,
            text,
            parse_mode='Markdown',
            reply_markup=markup
        )

        # Сохраняем message_id для возможного будущего обновления
        user_id = update.effective_user.id
        if user_id in USER_COLLECTIONS:
            USER_COLLECTIONS[user_id]['last_message_id'] = msg.message_id

    except Exception as e:
        logger.error(f"Критическая ошибка: {e}", exc_info=True)
        error_text = "❌ Произошла непредвиденная ошибка. Администратор уже уведомлён."

        if message_id:
            try:
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=error_text
                )
            except Exception:
                await context.bot.send_message(chat_id, error_text)
        else:
            await context.bot.send_message(chat_id, error_text)
# Добавляем обработчик для переключения в постраничный режим
async def handle_page_collection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info('Обработчик постраничного просмотра')
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    collection_data = USER_COLLECTIONS.get(user_id)

    if collection_data:
        # Начинаем с первой страницы
        await show_collection_page(update, context, 0)
    else:
        # Если данных нет, загружаем коллекцию заново
        await my_collection(update, context)

async def show_main_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает главное меню профиля"""
    try:
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

        user_data = get_user(user.id)

        mention = f"[{user.first_name}](tg://user?id={user.id})"

        profile_text = f"Пользователь: {mention}\n\n"
        profile_text += f"💰 Ваш баланс: *{user_data['coins']}* монет\n\n"
        profile_text += "Выберите раздел профиля:"

        keyboard = [
            [InlineKeyboardButton("Моя коллекция", callback_data='collection')],
            [InlineKeyboardButton("Мой баланс", callback_data='balance')],
            [InlineKeyboardButton("Подарки", callback_data='gift_menu')],
            [InlineKeyboardButton("🔙 Назад", callback_data='main_menu')]
        ]

        try:
            if update.callback_query:
                await query.edit_message_text(
                    text=profile_text,
                    parse_mode='Markdown',
                    reply_markup=InlineKeyboardMarkup(keyboard))
            else:
                msg = await message.reply_text(
                    text=profile_text,
                    parse_mode='Markdown',
                    reply_markup=InlineKeyboardMarkup(keyboard))
                if msg and hasattr(msg, 'message_id'):
                    await track_message(user.id, msg.message_id)
        except Exception as e:
            logger.error(f"Error showing main shop: {e}")
            msg = await context.bot.send_message(
                chat_id=chat_id,
                text=profile_text,
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard))
            if msg and hasattr(msg, 'message_id'):
                await track_message(user.id, msg.message_id)

    except Exception as e:
        logger.error(f"Error in show_main_shop: {e}")
        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text="❌ Произошла ошибка при загрузке магазина. Попробуйте нажать /start."
            )
        except Exception:
            pass


async def send_long_message(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    """Функция для отправки длинных сообщений с автоматическим разделением"""
    max_length = 4096

    if len(text) <= max_length:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=text,
            parse_mode='Markdown'
        )
        return

    # Разделяем текст на части
    parts = []
    while text:
        if len(text) > max_length:
            # Находим последний перенос строки в пределах лимита
            split_pos = text.rfind('\n', 0, max_length)
            if split_pos == -1:
                split_pos = max_length

            parts.append(text[:split_pos])
            text = text[split_pos:].lstrip()
        else:
            parts.append(text)
            break

    # Отправляем части по очереди
    for part in parts:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=part,
            parse_mode='Markdown'
        )