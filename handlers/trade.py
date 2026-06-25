from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import ContextTypes, CallbackQueryHandler
from database import get_user_collection, get_card, update_collection, get_cards, get_card
from config import RARITY_ORDER, RARITY_DISPLAY
import logging
from utils.helpers import delete_previous_messages, track_message
import random
from handlers.fight import get_card_stats  # Импортируем функцию получения характеристик
from handlers.fight import get_card_stats  # Импортируем функцию получения характеристик

logger = logging.getLogger(__name__)

# Словарь для хранения состояний обмена
USER_TRADE_STATES = {}

# Сопоставление ключей редкостей с отображаемыми названиями
RARITY_KEY_MAP = {
    "common": "🤍 Редкий",
    "uncommon": "💙 Супер редкий",
    "rare": "💜 Эпический",
    "epic": "❤️‍🔥 Мифический",
    "legendary": "💛 Легендарный",
    "exclusive": "🖤 Эксклюзивный"
}

# Обратное сопоставление для поиска по отображаемому названию
DISPLAY_TO_KEY_MAP = {v: k for k, v in RARITY_KEY_MAP.items()}

# Иерархия редкостей для обмена
RARITY_HIERARCHY = ["common", "uncommon", "rare", "epic", "legendary", "exclusive"]


async def trade_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /trade"""
    user = update.effective_user
    chat = update.effective_chat

    await delete_previous_messages(context, chat.id, user.id)
    await show_trade_menu(update, context)


async def show_trade_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает меню обмена"""
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        user = query.from_user
        chat_id = query.message.chat_id
        message = query.message
    else:
        user = update.effective_user
        chat_id = update.effective_chat.id
        message = update.message

    text = (
        "🔄 *Система обмена карточек*\n\n"
        "Обменяйте 10 карточек одной редкости на 1 карточку более высокой редкости!\n\n"
        "Доступные обмены:\n"
        "• 10 🤍 Редких → 1 💙 Супер редкая\n"
        "• 10 💙 Супер редких → 1 💜 Эпическая\n"
        "• 10 💜 Эпических → 1 ❤️‍🔥 Мифическая\n"
        "• 10 ❤️‍🔥 Мифических → 1 💛 Легендарная\n"
        "• 10 💛 Легендарных → 1 🖤 Эксклюзивная\n\n"
        "Выберите редкость для обмена:"
    )

    keyboard = []
    # Доступные для обмена редкости (все кроме эксклюзивной)
    available_rarities = [
        ("🤍 Редкий", "common"),
        ("💙 Супер редкий", "uncommon"),
        ("💜 Эпический", "rare"),
        ("❤️‍🔥 Мифический", "epic"),
        ("💛 Легендарный", "legendary")
    ]

    for rarity_name, rarity_key in available_rarities:
        keyboard.append([
            InlineKeyboardButton(
                f"Обменять {rarity_name}",
                callback_data=f'trade_select_{rarity_key}'
            )
        ])

    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data='main_menu')])

    try:
        if update.callback_query:
            await query.edit_message_text(
                text=text,
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            msg = await message.reply_text(
                text=text,
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            await track_message(user.id, msg.message_id)
    except Exception as e:
        logger.error(f"Ошибка показа меню обмена: {e}")


async def select_rarity_for_trade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик выбора редкости для обмена"""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    rarity_key = query.data.split('_')[2]

    # Получаем коллекцию пользователя
    collection = get_user_collection(user_id)
    if not collection:
        await query.message.reply_text("❌ Ваша коллекция пуста!")
        return

    # Получаем отображаемое название редкости
    target_rarity_display = RARITY_KEY_MAP.get(rarity_key, "🤍 Редкий")

    # Фильтруем карточки выбранной редкости
    selected_rarity_cards = [
        item for item in collection
        if item.get('rarity') == target_rarity_display and item['quantity'] > 0
    ]

    if not selected_rarity_cards:
        await query.message.reply_text(f"❌ У вас нет карточек редкости {target_rarity_display}!")
        return

    # Проверяем общее количество карточек выбранной редкости
    total_quantity = sum(item['quantity'] for item in selected_rarity_cards)
    if total_quantity < 10:
        await query.message.reply_text(
            f"❌ Недостаточно карточек! Нужно 10 {target_rarity_display}, у вас: {total_quantity}"
        )
        return

    # Получаем следующую редкость
    next_rarity_key = get_next_rarity(rarity_key)
    next_rarity_display = RARITY_KEY_MAP.get(next_rarity_key, "💙 Супер редкий")

    # Создаем клавиатуру для выбора карточек
    keyboard = []
    for card in selected_rarity_cards:
        # В функции select_rarity_for_trade убедитесь, что callback_data формируется правильно:
        keyboard.append([
            InlineKeyboardButton(
                f"{card['name']} (x{card['quantity']})",
                callback_data=f'select_card_trade_{card["card_id"]}_{rarity_key}'  # Должно быть 4 части
            )
        ])

    keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data='trade_menu')])

    text = (
        f"🔄 *Выбор карточек для обмена*\n\n"
        f"Выберите карточки редкости {target_rarity_display} для обмена:\n"
        f"• Нужно выбрать карточки на сумму 10 штук\n"
        f"• Вы получите 1 карточку {next_rarity_display}\n\n"
        f"Доступные карточки:"
    )

    # Сохраняем состояние
    USER_TRADE_STATES[user_id] = {
        'selected_rarity': rarity_key,
        'selected_rarity_display': target_rarity_display,
        'next_rarity_display': next_rarity_display,
        'cards': selected_rarity_cards,
        'selected_cards': {},  # card_id: quantity
        'total_selected': 0,
        'message_id': query.message.message_id
    }

    await query.edit_message_text(
        text=text,
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def select_card_for_trade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик выбора конкретной карточки для обмена"""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    data_parts = query.data.split('_')

    # Проверяем корректность формата - должно быть: select_card_trade_123_common
    if len(data_parts) < 5 or data_parts[0] != 'select' or data_parts[1] != 'card' or data_parts[2] != 'trade':
        logger.error(f"Неверный формат callback_data: {query.data}")
        await query.message.reply_text("❌ Ошибка обработки запроса. Попробуйте снова.")
        return

    try:
        card_id = int(data_parts[3])
        rarity_key = data_parts[4]
    except (ValueError, IndexError) as e:
        logger.error(f"Ошибка парсинга callback_data: {e}, data: {query.data}")
        await query.message.reply_text("❌ Ошибка обработки запроса. Попробуйте снова.")
        return

    if user_id not in USER_TRADE_STATES:
        await query.message.reply_text("❌ Сессия обмена истекла. Начните заново.")
        return

    trade_data = USER_TRADE_STATES[user_id]

    # Находим карточку в коллекции
    card_info = next((item for item in trade_data['cards'] if item['card_id'] == card_id), None)
    if not card_info:
        await query.message.reply_text("❌ Карточка не найдена!")
        return

    # Получаем максимальное доступное количество для выбора
    max_available = card_info['quantity']
    already_selected = trade_data['selected_cards'].get(card_id, 0)
    available_to_select = max_available - already_selected

    if available_to_select <= 0:
        await query.answer("❌ Все экземпляры этой карточки уже выбраны!", show_alert=True)
        return

    # Определяем сколько можно выбрать (максимум до 10 в сумме)
    max_to_select = min(available_to_select, 10 - trade_data['total_selected'])

    # Создаем клавиатуру для выбора количества
    keyboard = []
    row = []
    for i in range(1, min(6, max_to_select + 1)):
        row.append(InlineKeyboardButton(str(i), callback_data=f'select_qty_{card_id}_{rarity_key}_{i}'))
        if len(row) == 3:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    keyboard.append([InlineKeyboardButton("❌ Отмена выбора", callback_data=f'trade_select_{rarity_key}')])

    await query.edit_message_text(
        text=f"Выберите количество карточек '{card_info['name']}' для обмена:\n"
             f"Доступно: {available_to_select} из {max_available}\n"
             f"Уже выбрано: {trade_data['total_selected']}/10",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def select_quantity_for_trade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик выбора количества карточек"""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    data_parts = query.data.split('_')

    # Проверяем корректность формата данных - должно быть: select_qty_123_common_2
    if len(data_parts) != 5 or data_parts[0] != 'select' or data_parts[1] != 'qty':
        logger.error(f"Неверный формат callback_data: {query.data}")
        await query.message.reply_text("❌ Ошибка обработки запроса. Попробуйте снова.")
        return

    try:
        card_id = int(data_parts[2])
        rarity_key = data_parts[3]
        quantity = int(data_parts[4])
    except (ValueError, IndexError) as e:
        logger.error(f"Ошибка парсинга callback_data: {e}, data: {query.data}")
        await query.message.reply_text("❌ Ошибка обработки запроса. Попробуйте снова.")
        return

    if user_id not in USER_TRADE_STATES:
        await query.message.reply_text("❌ Сессия обмена истекла. Начните заново.")
        return

    trade_data = USER_TRADE_STATES[user_id]

    # Находим информацию о карточке для проверки доступного количества
    card_info = next((item for item in trade_data['cards'] if item['card_id'] == card_id), None)
    if not card_info:
        await query.message.reply_text("❌ Карточка не найдена!")
        return

    # Проверяем, что пользователь не пытается выбрать больше, чем есть
    available_qty = card_info['quantity']
    already_selected = trade_data['selected_cards'].get(card_id, 0)

    if quantity > (available_qty - already_selected):
        await query.answer("❌ Недостаточно карточек для выбора!", show_alert=True)
        return

    # Обновляем выбранные карточки
    current_qty = trade_data['selected_cards'].get(card_id, 0)
    trade_data['selected_cards'][card_id] = current_qty + quantity
    trade_data['total_selected'] += quantity

    # Остальной код функции остается без изменений...
    # [остальная часть функции]

    # Находим информацию о карточке
    card_info = next((item for item in trade_data['cards'] if item['card_id'] == card_id), None)
    card_name = card_info['name'] if card_info else f"Карточка #{card_id}"

    # Проверяем, достигли ли мы 10 карточек
    if trade_data['total_selected'] >= 10:
        return await confirm_trade_selection(update, context)

    # Показываем обновленный список карточек
    keyboard = []
    for card in trade_data['cards']:
        selected_qty = trade_data['selected_cards'].get(card['card_id'], 0)
        available = card['quantity'] - selected_qty

        if available > 0:
            button_text = f"{card['name']} (выбрано: {selected_qty}, доступно: {available})"
            keyboard.append([
                InlineKeyboardButton(
                    button_text,
                    callback_data=f'select_card_trade_{card["card_id"]}_{rarity_key}'
                )
            ])
    keyboard.append([InlineKeyboardButton("❌ Сбросить выбор", callback_data=f'reset_selection_{rarity_key}')])
    keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data='trade_menu')])

    selected_list = "\n".join([
        f"• {get_card(card_id)['name'] if get_card(card_id) else f'Карточка #{card_id}'}: {qty} шт."
        for card_id, qty in trade_data['selected_cards'].items()
    ]) or "• Пока ничего не выбрано"

    text = (
        f"🔄 *Выбор карточек для обмена*\n\n"
        f"Выбрано: {trade_data['total_selected']}/10 карточек\n"
        f"Выбранные карточки:\n{selected_list}\n\n"
        f"Продолжайте выбирать карточки:"
    )

    await query.edit_message_text(
        text=text,
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
async def finish_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Завершение выбора карточек"""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    rarity_key = query.data.split('_')[2]

    if user_id not in USER_TRADE_STATES:
        await query.message.reply_text("❌ Сессия обмена истекла. Начните заново.")
        return

    trade_data = USER_TRADE_STATES[user_id]

    if trade_data['total_selected'] != 10:
        await query.answer("❌ Нужно выбрать ровно 10 карточек!", show_alert=True)
        return

    await confirm_trade_selection(update, context)


async def confirm_trade_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подтверждение выбранных карточек для обмена"""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id

    if user_id not in USER_TRADE_STATES:
        await query.message.reply_text("❌ Сессия обмена истекла. Начните заново.")
        return

    trade_data = USER_TRADE_STATES[user_id]

    # Формируем список выбранных карточек
    selected_list = "\n".join([
        f"• {get_card(card_id)['name'] if get_card(card_id) else f'Карточка #{card_id}'}: {qty} шт."
        for card_id, qty in trade_data['selected_cards'].items()
    ])

    text = (
        f"🔄 *Подтверждение обмена*\n\n"
        f"Вы хотите обменять:\n{selected_list}\n\n"
        f"Всего: 10 карточек {trade_data['selected_rarity_display']}\n"
        f"На: 1 карточку {trade_data['next_rarity_display']}\n\n"
        f"Подтверждаете обмен?"
    )

    keyboard = [
        [InlineKeyboardButton("✅ Да, обменять", callback_data=f'trade_confirm_{trade_data["selected_rarity"]}')],
        [InlineKeyboardButton("❌ Отмена", callback_data=f'trade_select_{trade_data["selected_rarity"]}')]
    ]

    await query.edit_message_text(
        text=text,
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def reset_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сброс выбранных карточек"""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    rarity_key = query.data.split('_')[2]

    if user_id in USER_TRADE_STATES:
        USER_TRADE_STATES[user_id]['selected_cards'] = {}
        USER_TRADE_STATES[user_id]['total_selected'] = 0

    await select_rarity_for_trade(update, context)


async def confirm_trade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подтверждение и выполнение обмена"""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    rarity_key = query.data.split('_')[2]

    if user_id not in USER_TRADE_STATES:
        await query.message.reply_text("❌ Сессия обмена истекла. Начните заново.")
        return

    trade_data = USER_TRADE_STATES[user_id]

    # Выполняем обмен
    success, reward_card = await process_trade(user_id, trade_data)

    if success and reward_card:
        # Получаем характеристики полученной карточки
        card_stats = get_card_stats(reward_card['card_id'])
        health_display = int(card_stats['health'])
        damage_display = f"{card_stats['damage']:.1f}"

        # Формируем сообщение о полученной карточке
        reward_text = (
            f"🎉 *Обмен выполнен успешно!*\n\n"
            f"Вы получили новую карточку:\n\n"
            f"*{reward_card['name']}*\n"
            f"Редкость: {reward_card['rarity']}\n"
            f"❤️ Здоровье: {health_display}\n"
            f"⚔️ Урон: {damage_display}\n\n"
            f"Поздравляем с получением!"
        )

        # Пытаемся отправить с изображением
        if reward_card.get('image_url'):
            try:
                await context.bot.send_photo(
                    chat_id=query.message.chat_id,
                    photo=reward_card['image_url'],
                    caption=reward_text,
                    parse_mode='Markdown',
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🏠 Главное меню", callback_data='main_menu')]
                    ])
                )
                # Удаляем старое сообщение
                try:
                    await query.message.delete()
                except:
                    pass
                return
            except Exception as e:
                logger.error(f"Ошибка отправки изображения карточки: {e}")

        # Если не удалось отправить с изображением, отправляем текстом
        await query.edit_message_text(
            text=reward_text,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🏠 Главное меню", callback_data='main_menu')]
            ])
        )
    else:
        await query.edit_message_text(
            "❌ Ошибка при выполнении обмена. Попробуйте позже.",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Попробовать снова", callback_data='trade_menu')],
                [InlineKeyboardButton("🏠 Главное меню", callback_data='main_menu')]
            ])
        )

    # Очищаем состояние
    if user_id in USER_TRADE_STATES:
        del USER_TRADE_STATES[user_id]


async def process_trade(user_id: int, trade_data: dict) -> tuple:
    """Выполняет процесс обмена карточек и возвращает (успех, полученная_карточка)"""
    try:
        # ПРЕДВАРИТЕЛЬНАЯ ПРОВЕРКА: убеждаемся, что у пользователя достаточно карточек
        for card_id, quantity in trade_data['selected_cards'].items():
            # Получаем текущее количество карточки у пользователя
            from database import execute_query
            result = execute_query(
                "SELECT quantity FROM collections WHERE user_id = ? AND card_id = ?",
                (user_id, card_id),
                fetch_one=True
            )

            if not result:
                logger.error(f"Карточка {card_id} не найдена в коллекции пользователя {user_id}")
                return False, None

            current_quantity = result['quantity']

            # Проверяем, что у пользователя достаточно карточек
            if current_quantity < quantity:
                logger.error(f"Недостаточно карточек: есть {current_quantity}, нужно {quantity}")
                return False, None

        # Если проверка пройдена, удаляем выбранные карточки
        for card_id, quantity in trade_data['selected_cards'].items():
            # Получаем текущее количество карточки у пользователя
            result = execute_query(
                "SELECT quantity FROM collections WHERE user_id = ? AND card_id = ?",
                (user_id, card_id),
                fetch_one=True
            )

            current_quantity = result['quantity']
            new_quantity = current_quantity - quantity

            # Обновляем количество или удаляем запись
            if new_quantity == 0:
                execute_query(
                    "DELETE FROM collections WHERE user_id = ? AND card_id = ?",
                    (user_id, card_id)
                )
            else:
                execute_query(
                    "UPDATE collections SET quantity = ? WHERE user_id = ? AND card_id = ?",
                    (new_quantity, user_id, card_id)
                )

        # Получаем карточку следующей редкости
        next_rarity_key = get_next_rarity(trade_data['selected_rarity'])
        next_rarity_display = RARITY_KEY_MAP.get(next_rarity_key, "💙 Супер редкий")

        # Получаем все карточки следующей редкости
        all_cards = get_cards()
        next_rarity_cards = [
            card for card in all_cards
            if card.get('rarity') == next_rarity_display
        ]

        if not next_rarity_cards:
            logger.error(f"Нет карточек редкости {next_rarity_display} в базе данных")
            return False, None

        # Выбираем случайную карточку следующей редкости
        reward_card = random.choice(next_rarity_cards)

        # Добавляем новую карточку
        from database import add_to_collection
        if not add_to_collection(user_id, reward_card['card_id']):
            logger.error(f"Не удалось добавить карточку {reward_card['card_id']} пользователю {user_id}")
            return False, None

        return True, reward_card

    except Exception as e:
        logger.error(f"Ошибка при обмене карточек: {e}")
        return False, None


def get_next_rarity(current_rarity: str) -> str:
    """Возвращает ключ следующей редкости"""
    try:
        current_index = RARITY_HIERARCHY.index(current_rarity)
        if current_index < len(RARITY_HIERARCHY) - 1:
            return RARITY_HIERARCHY[current_index + 1]
    except ValueError:
        pass

    return "uncommon"  # fallback


async def cancel_trade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена обмена"""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    if user_id in USER_TRADE_STATES:
        del USER_TRADE_STATES[user_id]

    await show_trade_menu(update, context)


def setup_trade_handlers(application):
    """Добавляет обработчики для системы обмена"""
    application.add_handler(CallbackQueryHandler(select_rarity_for_trade, pattern='^trade_select_'))
    application.add_handler(CallbackQueryHandler(select_card_for_trade, pattern='^select_card_trade'))
    application.add_handler(CallbackQueryHandler(select_quantity_for_trade, pattern='^select_qty_'))
    application.add_handler(CallbackQueryHandler(finish_selection, pattern='^finish_selection_'))
    application.add_handler(CallbackQueryHandler(reset_selection, pattern='^reset_selection_'))
    application.add_handler(CallbackQueryHandler(confirm_trade, pattern='^trade_confirm_'))
    application.add_handler(CallbackQueryHandler(cancel_trade, pattern='^trade_cancel$'))
