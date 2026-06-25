from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler
from telegram.error import BadRequest
from database import get_user, get_user_collection, get_card, execute_query
from utils.helpers import delete_previous_messages, track_message
import random
from database import transfer_card, add_battle_history, get_battle_stats, get_user_bonuses, use_user_bonus
from functools import wraps
from telegram.constants import ChatType
import asyncio
import logging
from utils.helpers import track_message
from telegram.constants import ChatType
from datetime import datetime
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters
)

logger = logging.getLogger(__name__)

WAITING_PLAYERS = {}
ACTIVE_BATTLES = {}
BATTLE_MESSAGES = {}
BOT_OPPONENTS = {}  # Словарь для хранения ботов-противников

# Добавляем константу для бота-противника
BOT_OPPONENT_ID = -1000  # Отрицательный ID для ботов
strings = ["Шлам", "Терентий", "Акулина", "Батон", "Семен"]
BOT_OPPONENT_NAME = random.choice(strings)
BOT_RESPONSE_DELAY = (2, 4)  # Задержка ответа бота (мин, макс) в секундах

# Эффекты бонусов
BONUS_EFFECTS = {
    'damage_boost': {
        'name': 'Усиление урона',
        'description': 'Увеличивает урон на 25% на следующий ход',
        'multiplier': 1.25
    },
    'heal': {
        'name': 'Лечение',
        'description': 'Восстанавливает 20% здоровья',
        'heal_percent': 0.2
    },
    'vampirism': {
        'name': 'Вампиризм',
        'description': '50% от урона переходит в здоровье',
        'vampire_percent': 0.5
    },
    'invulnerability': {
        'name': 'Неуязвимость',
        'description': 'Полная защита от урона на следующий ход',
        'immune': True
    }
}


def check_private_chat_only(func):
    """Декоратор для проверки, что команда используется в личном чате"""

    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            if hasattr(update, 'callback_query') and update.callback_query:
                chat = update.callback_query.message.chat
            elif hasattr(update, 'effective_chat') and update.effective_chat:
                chat = update.effective_chat
            else:
                return await func(update, context)

            if chat.type != ChatType.PRIVATE:
                if hasattr(update, 'callback_query') and update.callback_query:
                    await update.callback_query.answer("❌ Бои доступны только в личных сообщениях!", show_alert=True)
                elif hasattr(update, 'message') and update.message:
                    await update.message.reply_text(
                        "❌ Бои доступны только в личных сообщениях с ботом.\n\n"
                        "Перейдите в личные сообщения с ботом и используйте команду /fight там."
                    )
                return
            return await func(update, context)
        except Exception as e:
            logger.error(f"Ошибка в декораторе check_private_chat_only: {e}")
            return await func(update, context)

    return wrapper


@check_private_chat_only
async def fight_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /fight"""
    user = update.effective_user
    chat = update.effective_chat

    await delete_previous_messages(context, chat.id, user.id)
    await show_fight_menu(update, context)


@check_private_chat_only
async def show_fight_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает меню боя"""
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

    keyboard = [
        [InlineKeyboardButton("🎯 Найти противника", callback_data='find_opponent')],
        [InlineKeyboardButton("📊 Статистика боев", callback_data='battle_stats')],
        [InlineKeyboardButton("🎒 Инвентарь бонусов", callback_data='bonus_inventory')],
        [InlineKeyboardButton("🔙 Назад", callback_data='main_menu')]
    ]

    text = (
        "⚔️ *Арена боев*\n\n"
        "Сразитесь с другими игроками в захватывающих дуэлях!\n"
        "• Выберите карточку для боя\n"
        "• Ставьте на кон одну из своих карточек\n"
        "• Победитель забирает карточку проигравшего!\n"
        "• По очереди кидайте кубик, ваш урон будет умножен на это число!\n"
        "• Используйте бонусы для получения преимущества!\n\n"
        "Готовы к битве?"
    )

    try:
        if update.callback_query:
            try:
                await query.edit_message_text(
                    text=text,
                    parse_mode='Markdown',
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            except Exception as edit_error:
                if "message to edit not found" in str(edit_error).lower():
                    msg = await context.bot.send_message(
                        chat_id=chat_id,
                        text=text,
                        parse_mode='Markdown',
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )
                    await track_message(user.id, msg.message_id)
        else:
            msg = await message.reply_text(
                text=text,
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            await track_message(user.id, msg.message_id)
    except Exception as e:
        logger.error(f"Ошибка показа меню боя: {e}")
        try:
            msg = await context.bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            await track_message(user.id, msg.message_id)
        except Exception as fallback_error:
            logger.error(f"Критическая ошибка при отправке меню боя: {fallback_error}")


@check_private_chat_only
async def show_bonus_inventory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает инвентарь бонусов пользователя"""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    bonuses = get_user_bonuses(user_id)

    if not bonuses:
        await query.edit_message_text(
            text="🎒 *Ваш инвентарь бонусов пуст!*\n\n"
                 "Приобретите бонусы в магазине (/shop) чтобы использовать их в бою.",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🛒 Магазин бонусов", callback_data='shop_bonuses')],
                [InlineKeyboardButton("🔙 Назад", callback_data='fight_menu')]
            ])
        )
        return

    text = "🎒 *Ваш инвентарь бонусов:*\n\n"
    for bonus in bonuses:
        text += f"🔹 *{bonus['name']}* - {bonus['quantity']} шт.\n"
        text += f"   {bonus['description']}\n\n"

    keyboard = [
        [InlineKeyboardButton("🔙 Назад", callback_data='fight_menu')]
    ]

    await query.edit_message_text(
        text=text,
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


@check_private_chat_only
async def find_opponent(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Поиск противника"""
    query = update.callback_query
    await query.answer()



    user_id = query.from_user.id
    user_name = query.from_user.first_name
    chat_id = query.message.chat_id

    collection = get_user_collection(user_id)
    if not collection:
        await query.message.reply_text("❌ У вас нет карточек для боя!")
        return

    WAITING_PLAYERS[user_id] = {
        'message_id': query.message.message_id,
        'chat_id': chat_id,
        'username': user_name,
        'joined_at': datetime.now(),
        'search_start_time': datetime.now()  # Добавляем время начала поиска
    }

    await query.edit_message_text(
        text="🔍 Ищем противника...\n\nОжидайте, пока другой игрок присоединится к бою.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Отменить поиск", callback_data='cancel_search')]
        ])
    )

    logger.info(f"Пользователь {user_name} или {user_id} ждет противника")

    # Запускаем таймер для проверки подключения бота
    asyncio.create_task(check_bot_connection(context, user_id))
    asyncio.create_task(matchmaking_task(context))


async def check_bot_connection(context: ContextTypes.DEFAULT_TYPE, user_id: int):
    """Проверяет возможность подключить бота-противника"""
    await asyncio.sleep(30)  # Ждем 30 секунд

    # Проверяем, что пользователь все еще в поиске
    if user_id in WAITING_PLAYERS:
        player_data = WAITING_PLAYERS[user_id]
        search_time = (datetime.now() - player_data['search_start_time']).total_seconds()

        if search_time >= 30:
            # Подключаем бота-противника
            await connect_bot_opponent(context, user_id, player_data)


async def connect_bot_opponent(context: ContextTypes.DEFAULT_TYPE, user_id: int, player_data: dict):
    """Подключает бота-противника к пользователю"""
    try:


        # Удаляем пользователя из очереди поиска
        if user_id in WAITING_PLAYERS:
            del WAITING_PLAYERS[user_id]

        # Создаем бота-противника
        bot_player_id = BOT_OPPONENT_ID - random.randint(1, 1000)  # Уникальный ID для бота
        from database import get_cards

        # Получаем все карточки для выбора ботом
        all_cards = get_cards()
        if not all_cards:
            await context.bot.send_message(
                chat_id=player_data['chat_id'],
                text="❌ Ошибка: нет доступных карточек для Шлама"
            )
            return

        # Выбираем случайную карточку для бота
        bot_card = random.choice(all_cards)
        card_stats = get_card_stats(bot_card['card_id'])

        # Создаем бой с ботом
        battle_id = f"battle_{user_id}_{bot_player_id}"

        ACTIVE_BATTLES[battle_id] = {
            'player1': {
                'id': user_id,
                'chat_id': player_data['chat_id'],
                'username': player_data['username'],
                'selected_card': None,
                'health': 0,
                'max_health': 0,
                'damage': 0,
                'active_bonuses': {},
                'bonus_cooldown': 0,
                'is_bot': False
            },
            'player2': {
                'id': bot_player_id,
                'chat_id': None,  # У бота нет чата
                'username': BOT_OPPONENT_NAME,
                'selected_card': bot_card,
                'health': card_stats['health'],
                'max_health': card_stats['health'],
                'damage': card_stats['damage'],
                'active_bonuses': {},
                'bonus_cooldown': 0,
                'is_bot': True
            },
            'current_turn': user_id,  # Первым ходит пользователь
            'round': 1,
            'messages': [],
            'is_bot_battle': True  # Флаг что это бой с ботом
        }

        # Сохраняем информацию о боте
        BOT_OPPONENTS[bot_player_id] = {
            'battle_id': battle_id,
            'user_id': user_id
        }

        # Уведомляем пользователя
        await context.bot.send_message(
            chat_id=player_data['chat_id'],
            text=f"🎉 К вам присоединился {BOT_OPPONENT_NAME}!\n\n"
                 f"Выберите карточку для боя:",
            reply_markup=await get_cards_keyboard(user_id, context)
        )

    except Exception as e:
        logger.error(f"Ошибка подключения бота: {e}")
        try:
            await context.bot.send_message(
                chat_id=player_data['chat_id'],
                text="❌ Ошибка при подключении. Попробуйте снова."
            )
        except:
            pass

@check_private_chat_only
async def cancel_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена поиска противника"""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    if user_id in WAITING_PLAYERS:
        del WAITING_PLAYERS[user_id]

    await show_fight_menu(update, context)


async def matchmaking_task(context: ContextTypes.DEFAULT_TYPE):
    """Задача для поиска матча"""
    await asyncio.sleep(2)

    # Фильтруем только реальных игроков (исключаем тех, кто уже получил бота)
    real_players = {pid: data for pid, data in WAITING_PLAYERS.items()
                   if not data.get('bot_assigned', False)}

    if len(real_players) >= 2:
        players = list(real_players.items())[:2]
        player1_id, player1_data = players[0]
        player2_id, player2_data = players[1]

        # Помечаем что эти игроки нашли противника
        WAITING_PLAYERS[player1_id]['bot_assigned'] = True
        WAITING_PLAYERS[player2_id]['bot_assigned'] = True

        del WAITING_PLAYERS[player1_id]
        del WAITING_PLAYERS[player2_id]

        battle_id = f"battle_{player1_id}_{player2_id}"
        logger.info(f"Создан бой: {battle_id}")

        ACTIVE_BATTLES[battle_id] = {
            'player1': {
                'id': player1_id,
                'chat_id': player1_data['chat_id'],
                'username': player1_data['username'],
                'selected_card': None,
                'health': 0,
                'max_health': 0,
                'damage': 0,
                'active_bonuses': {},
                'bonus_cooldown': 0,
                'is_bot': False
            },
            'player2': {
                'id': player2_id,
                'chat_id': player2_data['chat_id'],
                'username': player2_data['username'],
                'selected_card': None,
                'health': 0,
                'max_health': 0,
                'damage': 0,
                'active_bonuses': {},
                'bonus_cooldown': 0,
                'is_bot': False
            },
            'current_turn': player1_id,
            'round': 1,
            'messages': [],
            'is_bot_battle': False
        }

        for player_id, player_data in [(player1_id, player1_data), (player2_id, player2_data)]:
            try:
                opponent_id = player2_id if player_id == player1_id else player1_id
                opponent_name = player2_data['username'] if player_id == player1_id else player1_data['username']

                await context.bot.send_message(
                    chat_id=player_data['chat_id'],
                    text=f"🎉 Найден противник: {opponent_name}!\n\nВыберите карточку для боя:",
                    reply_markup=await get_cards_keyboard(player_id, context)
                )
            except Exception as e:
                logger.error(f"Ошибка отправки игроку {player_id}: {e}")


async def get_cards_keyboard(user_id: int, context: ContextTypes.DEFAULT_TYPE = None):
    """Создает клавиатуру с карточками для выбора"""
    collection = get_user_collection(user_id)
    keyboard = []

    for card in collection:
        if card['quantity'] >= 1:
            card_stats = get_card_stats(card['card_id'])
            keyboard.append([
                InlineKeyboardButton(
                    f"{card['name']} ❤️{card_stats['health']} ⚔️{card_stats['damage']}",
                    callback_data=f'select_battle_card_{card["card_id"]}'
                )
            ])

    keyboard.append([InlineKeyboardButton("❌ Отменить бой", callback_data='cancel_battle')])
    return InlineKeyboardMarkup(keyboard)


def get_card_stats(card_id: int):
    """Возвращает характеристики карточки из базы данных"""
    card = get_card(card_id)
    if not card:
        return {'health': 50, 'damage': 8.0}

    # Преобразуем health в int, damage в float
    health = int(card.get('hp', 50))
    damage = float(card.get('damage', 8.0))

    return {
        'health': max(1, health),
        'damage': max(0.0, damage)
    }


@check_private_chat_only
async def select_battle_card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик выбора карточки для боя"""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    card_id = int(query.data.split('_')[3])

    battle_id = None
    player_role = None

    for bid, battle in ACTIVE_BATTLES.items():
        if battle['player1']['id'] == user_id:
            battle_id = bid
            player_role = 'player1'
            break
        elif battle['player2']['id'] == user_id:
            battle_id = bid
            player_role = 'player2'
            break

    if not battle_id:
        await query.message.reply_text("❌ Активный бой не найден")
        return

    battle = ACTIVE_BATTLES[battle_id]
    card = get_card(card_id)

    if not card:
        await query.message.reply_text("❌ Карточка не найдена")
        return

    card_stats = get_card_stats(card_id)
    battle[player_role]['selected_card'] = card
    battle[player_role]['health'] = card_stats['health']
    battle[player_role]['max_health'] = card_stats['health']
    battle[player_role]['damage'] = card_stats['damage']

    await query.edit_message_text(
        text=f"✅ Выбрана карточка: {card['name']}\n"
             f"❤️ Здоровье: {card_stats['health']}\n"
             f"⚔️ Урон: {card_stats['damage']}\n\n"
             f"Ожидаем выбора противника..."
    )

    if (battle['player1']['selected_card'] and
            battle['player2']['selected_card']):
        await start_battle(context, battle_id)


async def start_battle(context: ContextTypes.DEFAULT_TYPE, battle_id: str):
    """Начинает бой"""
    battle = ACTIVE_BATTLES[battle_id]
    logger.info(f"Начинаем бой: {battle_id}")

    battle_text = await get_battle_status_text(battle)
    BATTLE_MESSAGES[battle_id] = {}

    for player in ['player1', 'player2']:
        # Не отправляем сообщения ботам
        if battle[player].get('is_bot'):
            continue

        try:
            msg = await context.bot.send_message(
                chat_id=battle[player]['chat_id'],
                text=battle_text,
                parse_mode='Markdown'
            )
            BATTLE_MESSAGES[battle_id][player] = msg.message_id
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения о бое: {e}")

    current_player = battle['player1'] if battle['current_turn'] == battle['player1']['id'] else battle['player2']

    # Если текущий игрок - бот, сразу запускаем его ход
    if current_player.get('is_bot'):
        asyncio.create_task(bot_make_turn(context, battle_id, current_player['id']))
        return

    try:
        turn_msg = await context.bot.send_message(
            chat_id=current_player['chat_id'],
            text="🎲 Ваш ход! Выберите действие:",
            reply_markup=await get_battle_keyboard(battle_id, current_player['id'])
        )
        BATTLE_MESSAGES[battle_id]['turn_message'] = turn_msg.message_id
        BATTLE_MESSAGES[battle_id]['turn_chat_id'] = current_player['chat_id']
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления о первом ходе: {e}")

async def get_battle_keyboard(battle_id: str, user_id: int):
    """Создает клавиатуру для боя с учетом доступных бонусов"""
    battle = ACTIVE_BATTLES.get(battle_id)
    if not battle:
        return InlineKeyboardMarkup([[InlineKeyboardButton("❌ Бой завершен", callback_data='fight_menu')]])

    player = battle['player1'] if battle['player1']['id'] == user_id else battle['player2']

    # Боты не получают клавиатуру
    if player.get('is_bot'):
        return None

    bonuses = get_user_bonuses(user_id)

    keyboard = [
        [InlineKeyboardButton("🎲 Бросить кубик", callback_data=f'roll_dice_{battle_id}')]
    ]

    if bonuses and player['bonus_cooldown'] <= 0:
        for bonus in bonuses:
            if bonus['quantity'] > 0:
                keyboard.append([
                    InlineKeyboardButton(
                        f"⚡ {bonus['name']} ({bonus['quantity']})",
                        callback_data=f'use_bonus_{battle_id}_{bonus["bonus_id"]}'
                    )
                ])

    return InlineKeyboardMarkup(keyboard)


@check_private_chat_only
async def use_bonus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Использование бонуса в бою"""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    data_parts = query.data.split('_')

    if len(data_parts) < 4:
        await query.message.reply_text("❌ Ошибка обработки команды")
        return

    battle_id = '_'.join(data_parts[2:-1])
    bonus_id = int(data_parts[-1])

    if battle_id not in ACTIVE_BATTLES:
        await query.message.reply_text("❌ Бой не найден или уже завершен")
        return

    battle = ACTIVE_BATTLES[battle_id]

    if battle['current_turn'] != user_id:
        await query.answer("Сейчас не ваш ход!", show_alert=True)
        return

    player = battle['player1'] if user_id == battle['player1']['id'] else battle['player2']

    if player['bonus_cooldown'] > 0:
        await query.answer(f"❌ Бонусы можно использовать раз в {player['bonus_cooldown']} ходов!", show_alert=True)
        return

    bonuses = get_user_bonuses(user_id)
    selected_bonus = next((b for b in bonuses if b['bonus_id'] == bonus_id), None)

    if not selected_bonus or selected_bonus['quantity'] <= 0:
        await query.answer("❌ Бонус не найден!", show_alert=True)
        return

    effect_type = selected_bonus['effect_type']
    effect_value = selected_bonus['effect_value']

    result_text = f"⚡ *{player['username']} использует {selected_bonus['name']}!*\n\n"

    if effect_type == 'damage_boost':
        player['active_bonuses']['damage_boost'] = {
            'multiplier': effect_value,
            'duration': 1
        }
        result_text += f"Урон увеличен на {int((effect_value - 1) * 100)}% на следующий ход!\n"

    elif effect_type == 'heal':
        heal_amount = int(player['max_health'] * effect_value)
        player['health'] = min(player['max_health'], player['health'] + heal_amount)
        result_text += f"Восстановлено {heal_amount} здоровья!\n"

    elif effect_type == 'vampirism':
        player['active_bonuses']['vampirism'] = {
            'percent': effect_value,
            'duration': 1
        }
        result_text += f"Вампиризм активирован! {int(effect_value * 100)}% урона будет восстанавливать здоровье!\n"

    elif effect_type == 'invulnerability':
        player['active_bonuses']['invulnerability'] = {
            'immune': True,
            'duration': 1
        }
        result_text += "Неуязвимость активирована! Полный иммунитет к урону на следующий ход!\n"

    use_user_bonus(user_id, bonus_id)
    player['bonus_cooldown'] = 2

    battle_text = await get_battle_status_text(battle)

    # Отправляем результат только реальным игрокам
    for player_key in ['player1', 'player2']:
        player_data = battle[player_key]
        # Пропускаем ботов
        if player_data.get('is_bot'):
            continue

        try:
            if battle_id in BATTLE_MESSAGES and player_key in BATTLE_MESSAGES[battle_id]:
                await context.bot.edit_message_text(
                    chat_id=player_data['chat_id'],
                    message_id=BATTLE_MESSAGES[battle_id][player_key],
                    text=result_text + battle_text,
                    parse_mode='Markdown'
                )
        except Exception as e:
            logger.error(f"Ошибка обновления сообщения боя: {e}")

    battle['current_turn'] = battle['player2']['id'] if user_id == battle['player1']['id'] else battle['player1']['id']
    battle['round'] += 1

    try:
        if battle_id in BATTLE_MESSAGES and 'turn_message' in BATTLE_MESSAGES[battle_id]:
            await context.bot.delete_message(
                chat_id=BATTLE_MESSAGES[battle_id]['turn_chat_id'],
                message_id=BATTLE_MESSAGES[battle_id]['turn_message']
            )
    except Exception as e:
        logger.error(f"Ошибка удаления сообщения о ходе: {e}")

    next_player = battle['player1'] if battle['current_turn'] == battle['player1']['id'] else battle['player2']

    # Если следующий игрок - бот, запускаем его ход
    if next_player.get('is_bot'):
        asyncio.create_task(bot_make_turn(context, battle_id, next_player['id']))
    else:
        # Отправляем сообщение о ходе реальному игроку
        try:
            turn_msg = await context.bot.send_message(
                chat_id=next_player['chat_id'],
                text="🎲 Ваш ход! Выберите действие:",
                reply_markup=await get_battle_keyboard(battle_id, next_player['id'])
            )
            BATTLE_MESSAGES[battle_id]['turn_message'] = turn_msg.message_id
            BATTLE_MESSAGES[battle_id]['turn_chat_id'] = next_player['chat_id']
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления о ходе: {e}")


@check_private_chat_only
async def roll_dice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Бросок кубика"""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id

    try:
        parts = query.data.split('_')
        if len(parts) >= 3:
            battle_id = '_'.join(parts[2:])
        else:
            raise ValueError("Неверный формат callback_data")
    except Exception as e:
        logger.error(f"Ошибка парсинга battle_id: {e}")
        await query.message.reply_text("❌ Ошибка обработки команды")
        return

    if battle_id not in ACTIVE_BATTLES:
        await query.message.reply_text("❌ Бой не найден или уже завершен")
        return

    battle = ACTIVE_BATTLES[battle_id]

    if battle['current_turn'] != user_id:
        await query.answer("Сейчас не ваш ход!", show_alert=True)
        return

    # Выполняем ход игрока
    dice_roll = random.randint(1, 6)
    attacker = battle['player1'] if user_id == battle['player1']['id'] else battle['player2']
    defender = battle['player2'] if user_id == battle['player1']['id'] else battle['player1']

    base_damage = attacker['damage']

    if 'damage_boost' in attacker['active_bonuses']:
        base_damage *= attacker['active_bonuses']['damage_boost']['multiplier']
        attacker['active_bonuses']['damage_boost']['duration'] -= 1
        if attacker['active_bonuses']['damage_boost']['duration'] <= 0:
            del attacker['active_bonuses']['damage_boost']

    damage = dice_roll * base_damage

    if 'invulnerability' in defender['active_bonuses']:
        damage = 0
        defender['active_bonuses']['invulnerability']['duration'] -= 1
        if defender['active_bonuses']['invulnerability']['duration'] <= 0:
            del defender['active_bonuses']['invulnerability']

    defender['health'] = max(0, defender['health'] - damage)

    heal_amount = 0
    if 'vampirism' in attacker['active_bonuses'] and damage > 0:
        heal_amount = int(damage * attacker['active_bonuses']['vampirism']['percent'])
        attacker['health'] = min(attacker['max_health'], attacker['health'] + heal_amount)
        attacker['active_bonuses']['vampirism']['duration'] -= 1
        if attacker['active_bonuses']['vampirism']['duration'] <= 0:
            del attacker['active_bonuses']['vampirism']

    result_text = (
        f"🎲 *Ход {battle['round']}*\n\n"
        f"{attacker['username']} бросает кубик: 🎯 {dice_roll}\n"
        f"Урон: {dice_roll} × {int(base_damage)} = ⚡{int(damage)}\n\n"
    )

    if damage == 0:
        result_text += f"{defender['username']} полностью блокирует урон!\n"
    else:
        result_text += f"{defender['username']} получает {int(damage)} урона!\n"

    if heal_amount > 0:
        result_text += f"{attacker['username']} восстанавливает {heal_amount} здоровья!\n"

    battle_text = await get_battle_status_text(battle)

    for player_key in ['player1', 'player2']:
        player_data = battle[player_key]
        # Пропускаем ботов
        if player_data.get('is_bot'):
            continue

        try:
            if battle_id in BATTLE_MESSAGES and player_key in BATTLE_MESSAGES[battle_id]:
                await context.bot.edit_message_text(
                    chat_id=player_data['chat_id'],
                    message_id=BATTLE_MESSAGES[battle_id][player_key],
                    text=result_text + battle_text,
                    parse_mode='Markdown'
                )
        except Exception as e:
            logger.error(f"Ошибка обновления сообщения боя: {e}")

    # Проверяем завершение боя после хода игрока
    if defender['health'] <= 0:
        logger.info(f"Бой завершен! Победитель: {attacker['username']}")
        await end_battle(context, battle_id, attacker, defender)
        return

    # Передаем ход следующему игроку
    battle['current_turn'] = defender['id']
    battle['round'] += 1

    for player in ['player1', 'player2']:
        if battle[player]['bonus_cooldown'] > 0:
            battle[player]['bonus_cooldown'] -= 1

    try:
        if battle_id in BATTLE_MESSAGES and 'turn_message' in BATTLE_MESSAGES[battle_id]:
            await context.bot.delete_message(
                chat_id=BATTLE_MESSAGES[battle_id]['turn_chat_id'],
                message_id=BATTLE_MESSAGES[battle_id]['turn_message']
            )
    except Exception as e:
        logger.error(f"Ошибка удаления сообщения о ходе: {e}")

    next_player = battle['player1'] if battle['current_turn'] == battle['player1']['id'] else battle['player2']

    # Если следующий игрок - бот, запускаем его ход
    if next_player.get('is_bot'):
        # Запускаем ход бота с задержкой
        asyncio.create_task(bot_make_turn(context, battle_id, next_player['id']))
    else:
        # Отправляем сообщение о ходе реальному игроку
        try:
            turn_msg = await context.bot.send_message(
                chat_id=next_player['chat_id'],
                text="🎲 Ваш ход! Выберите действие:",
                reply_markup=await get_battle_keyboard(battle_id, next_player['id'])
            )
            BATTLE_MESSAGES[battle_id]['turn_message'] = turn_msg.message_id
            BATTLE_MESSAGES[battle_id]['turn_chat_id'] = next_player['chat_id']
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления о ходе: {e}")


async def bot_make_turn(context: ContextTypes.DEFAULT_TYPE, battle_id: str, bot_id: int):
    """Ход бота-противника"""
    try:
        if battle_id not in ACTIVE_BATTLES:
            return

        battle = ACTIVE_BATTLES[battle_id]  # Определяем переменную battle здесь
        bot_player = battle['player1'] if battle['player1']['id'] == bot_id else battle['player2']

        # Имитируем раздумье бота (2-4 секунды)
        delay = random.uniform(BOT_RESPONSE_DELAY[0], BOT_RESPONSE_DELAY[1])
        await asyncio.sleep(delay)

        # Бот всегда бросает кубик (не использует бонусы)
        dice_roll = random.randint(1, 6)
        attacker = bot_player
        defender = battle['player2'] if battle['player1']['id'] == bot_id else battle['player1']

        base_damage = attacker['damage']

        if 'damage_boost' in attacker['active_bonuses']:
            base_damage *= attacker['active_bonuses']['damage_boost']['multiplier']
            attacker['active_bonuses']['damage_boost']['duration'] -= 1
            if attacker['active_bonuses']['damage_boost']['duration'] <= 0:
                del attacker['active_bonuses']['damage_boost']

        damage = dice_roll * base_damage

        if 'invulnerability' in defender['active_bonuses']:
            damage = 0
            defender['active_bonuses']['invulnerability']['duration'] -= 1
            if defender['active_bonuses']['invulnerability']['duration'] <= 0:
                del defender['active_bonuses']['invulnerability']

        defender['health'] = max(0, defender['health'] - damage)

        heal_amount = 0
        if 'vampirism' in attacker['active_bonuses'] and damage > 0:
            heal_amount = int(damage * attacker['active_bonuses']['vampirism']['percent'])
            attacker['health'] = min(attacker['max_health'], attacker['health'] + heal_amount)
            attacker['active_bonuses']['vampirism']['duration'] -= 1
            if attacker['active_bonuses']['vampirism']['duration'] <= 0:
                del attacker['active_bonuses']['vampirism']

        result_text = (
            f"🎲 *Ход {battle['round']}*\n\n"
            f"{attacker['username']} бросает кубик: 🎯 {dice_roll}\n"
            f"Урон: {dice_roll} × {int(base_damage)} = ⚡{int(damage)}\n\n"
        )

        if damage == 0:
            result_text += f"{defender['username']} полностью блокирует урон!\n"
        else:
            result_text += f"{defender['username']} получает {int(damage)} урона!\n"

        if heal_amount > 0:
            result_text += f"{attacker['username']} восстанавливает {heal_amount} здоровья!\n"

        battle_text = await get_battle_status_text(battle)

        # Отправляем результат хода бота
        for player_key in ['player1', 'player2']:
            player = battle[player_key]
            if not player.get('is_bot') and player['chat_id']:  # Только реальным игрокам
                try:
                    if battle_id in BATTLE_MESSAGES and player_key in BATTLE_MESSAGES[battle_id]:
                        await context.bot.edit_message_text(
                            chat_id=player['chat_id'],
                            message_id=BATTLE_MESSAGES[battle_id][player_key],
                            text=result_text + battle_text,
                            parse_mode='Markdown'
                        )
                except Exception as e:
                    logger.error(f"Ошибка обновления сообщения боя: {e}")

        # Проверяем завершение боя после хода бота
        if defender['health'] <= 0:
            logger.info(f"Бой завершен! Победитель: {attacker['username']}")
            await end_battle(context, battle_id, attacker, defender)
            return

        # Передаем ход следующему игроку
        battle['current_turn'] = defender['id']
        battle['round'] += 1

        for player in ['player1', 'player2']:
            if battle[player]['bonus_cooldown'] > 0:
                battle[player]['bonus_cooldown'] -= 1

        # Если следующий игрок - реальный игрок, отправляем ему сообщение
        next_player = battle['player1'] if battle['current_turn'] == battle['player1']['id'] else battle['player2']
        if not next_player.get('is_bot'):
            try:
                turn_msg = await context.bot.send_message(
                    chat_id=next_player['chat_id'],
                    text="🎲 Ваш ход! Выберите действие:",
                    reply_markup=await get_battle_keyboard(battle_id, next_player['id'])
                )
                if battle_id not in BATTLE_MESSAGES:
                    BATTLE_MESSAGES[battle_id] = {}
                BATTLE_MESSAGES[battle_id]['turn_message'] = turn_msg.message_id
                BATTLE_MESSAGES[battle_id]['turn_chat_id'] = next_player['chat_id']
            except Exception as e:
                logger.error(f"Ошибка отправки уведомления о ходе: {e}")

    except Exception as e:
        logger.error(f"Ошибка в ходе бота: {e}")

async def get_battle_status_text(battle: dict) -> str:
    """Возвращает текст статуса боя"""
    p1 = battle['player1']
    p2 = battle['player2']

    health_bar1 = get_health_bar(p1['health'], p1['max_health'])
    health_bar2 = get_health_bar(p2['health'], p2['max_health'])

    health1_display = f"{p1['health']:.2f}"
    health2_display = f"{p2['health']:.2f}"
    max_health1_display = f"{p1['max_health']}"
    max_health2_display = f"{p2['max_health']}"

    status_text = (
        f"⚔️ *Бой продолжается!*\n\n"
        f"**{p1['username']}**\n"
        f"{p1['selected_card']['name']}\n"
        f"❤️ {health_bar1} {health1_display}/{max_health1_display}\n"
        f"⚔️ Урон: {p1['damage']:.2f}\n"
    )

    if p1['active_bonuses']:
        status_text += "🔮 Активные бонусы:\n"
        for bonus_name, bonus_data in p1['active_bonuses'].items():
            if bonus_name == 'damage_boost':
                status_text += f"   ⚡ Усиление урона ({bonus_data['duration']} ход)\n"
            elif bonus_name == 'vampirism':
                status_text += f"   🩸 Вампиризм ({bonus_data['duration']} ход)\n"
            elif bonus_name == 'invulnerability':
                status_text += f"   🛡️ Неуязвимость ({bonus_data['duration']} ход)\n"

    status_text += f"\n**{p2['username']}**\n"
    status_text += f"{p2['selected_card']['name']}\n"
    status_text += f"❤️ {health_bar2} {health2_display}/{max_health2_display}\n"
    status_text += f"⚔️ Урон: {p2['damage']:.2f}\n"

    if p2['active_bonuses']:
        status_text += "🔮 Активные бонусы:\n"
        for bonus_name, bonus_data in p2['active_bonuses'].items():
            if bonus_name == 'damage_boost':
                status_text += f"   ⚡ Усиление урона ({bonus_data['duration']} ход)\n"
            elif bonus_name == 'vampirism':
                status_text += f"   🩸 Вампиризм ({bonus_data['duration']} ход)\n"
            elif bonus_name == 'invulnerability':
                status_text += f"   🛡️ Неуязвимость ({bonus_data['duration']} ход)\n"

    status_text += f"\nРаунд: {battle['round']}"

    return status_text


def get_health_bar(current: int, max_health: int) -> str:
    """Создает текстовую полоску здоровья"""
    bars = 10
    filled = int((current / max_health) * bars)
    empty = bars - filled
    return '█' * filled + '░' * empty


async def end_battle(context: ContextTypes.DEFAULT_TYPE, battle_id: str, winner: dict, loser: dict):
    """Завершает бой и обрабатывает результат"""
    logger.info(f"Завершение боя {battle_id}, победитель: {winner['username']}")


    # Обрабатываем передачу карточек в зависимости от типа боя
    if not loser.get('is_bot') and not winner.get('is_bot'):
        # Бой между реальными игроками - обычная передача карточки
        if not loser.get('is_bot'):
            transfer_success = transfer_card(
                loser['id'],
                winner['id'],
                loser['selected_card']['card_id']
            )
    else:
        # Бой с ботом - особые правила
        if winner.get('is_bot'):
            # Бот победил - удаляем карточку у пользователя
            from database import update_collection
            user_collection = get_user_collection(loser['id'])
            current_quantity = next((item['quantity'] for item in user_collection
                                     if item['card_id'] == loser['selected_card']['card_id']), 0)

            if current_quantity > 0:
                update_collection(loser['id'], loser['selected_card']['card_id'], current_quantity - 1)
        else:
            # Пользователь победил бота - добавляем карточку бота пользователю
            from database import add_to_collection
            add_to_collection(winner['id'], loser['selected_card']['card_id'])

    # Добавляем запись в историю боев только для реальных игроков
    if 1==1:
        add_battle_history(
            winner_id=winner['id'],
            loser_id=loser['id'],
            winner_card_id=winner['selected_card']['card_id'],
            loser_card_id=loser['selected_card']['card_id'],
            rounds=ACTIVE_BATTLES[battle_id]['round'],
            winner_health=winner['health']
        )

    # Отправляем результаты только реальным игрокам
    result_text = (
        f"🏆 *Бой завершен!*\n\n"
        f"🎉 Победитель: {winner['username']}\n"
        f"💔 Проигравший: {loser['username']}\n\n"
    )

    result_text += f"Победитель получает карточку: {loser['selected_card']['name']}\n"

    result_text += f"Всего раундов: {ACTIVE_BATTLES[battle_id]['round']}"

    for player in ['player1', 'player2']:
        player_data = ACTIVE_BATTLES[battle_id][player]
        # Пропускаем ботов
        if player_data.get('is_bot'):
            continue

        try:
            await context.bot.send_message(
                chat_id=player_data['chat_id'],
                text=result_text,
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("⚔️ Снова в бой", callback_data='find_opponent')],
                    [InlineKeyboardButton("🏠 Главное меню", callback_data='main_menu')]
                ])
            )
        except Exception as e:
            logger.error(f"Ошибка отправки результата боя: {e}")

    # Очищаем данные боя
    if battle_id in ACTIVE_BATTLES:
        # Удаляем информацию о боте если был бой с ботом
        if ACTIVE_BATTLES[battle_id].get('is_bot_battle'):
            bot_id = ACTIVE_BATTLES[battle_id]['player2']['id'] if ACTIVE_BATTLES[battle_id]['player1'][
                                                                       'id'] != BOT_OPPONENT_ID else \
                ACTIVE_BATTLES[battle_id]['player1']['id']
            if bot_id in BOT_OPPONENTS:
                del BOT_OPPONENTS[bot_id]

        del ACTIVE_BATTLES[battle_id]
        logger.info(f"Бой {battle_id} удален из активных")
@check_private_chat_only
async def cancel_battle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена боя"""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id

    for battle_id in list(ACTIVE_BATTLES.keys()):
        battle = ACTIVE_BATTLES[battle_id]
        if battle['player1']['id'] == user_id or battle['player2']['id'] == user_id:
            other_player = battle['player2'] if battle['player1']['id'] == user_id else battle['player1']
            try:
                await context.bot.send_message(
                    chat_id=other_player['chat_id'],
                    text="❌ Противник отменил бой"
                )
            except Exception as e:
                logger.error(f"Ошибка уведомления об отмене: {e}")

            del ACTIVE_BATTLES[battle_id]
            break

    await show_fight_menu(update, context)


@check_private_chat_only
@check_private_chat_only
async def battle_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает статистику боев"""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    stats = get_battle_stats(user_id)

    text = (
        f"📊 *Ваша статистика боев*\n\n"
        f"🏆 Побед: {stats['wins']}\n"
        f"💔 Поражений: {stats['losses']}\n"
        f"⚔️ Всего боев: {stats['total']}\n"
        f"🎯 Процент побед: {stats['win_rate']}%\n\n"
        f"📈 Последние бои:\n"
    )

    for battle in stats['recent_battles']:
        result = "✅ Победа" if battle['is_win'] else "❌ Поражение"
        # Убираем Markdown форматирование из имен оппонентов на случай специальных символов
        opponent_name = battle['opponent'].replace('*', '').replace('_', '').replace('`', '')
        text += f"{result} против {opponent_name} ({battle['rounds']} раундов)\n"

    # Если нет последних боев
    if not stats['recent_battles']:
        text += "Пока нет завершенных боев\n"

    try:
        await query.edit_message_text(
            text=text,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Назад", callback_data='fight_menu')]
            ])
        )
    except BadRequest as e:
        if "Can't parse entities" in str(e):
            # Если есть ошибка парсинга, отправляем без Markdown
            await query.edit_message_text(
                text=text.replace('*', '').replace('_', '').replace('`', ''),
                parse_mode=None,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Назад", callback_data='fight_menu')]
                ])
            )
        else:
            raise e


def setup_fight_handlers(application):
    """Добавляет обработчики для боев"""
    application.add_handler(CallbackQueryHandler(find_opponent, pattern='^find_opponent$'))
    application.add_handler(CallbackQueryHandler(cancel_search, pattern='^cancel_search$'))
    application.add_handler(CallbackQueryHandler(show_bonus_inventory, pattern='^bonus_inventory$'))
    application.add_handler(CallbackQueryHandler(battle_stats, pattern='^battle_stats$'))
    application.add_handler(CallbackQueryHandler(select_battle_card, pattern='^select_battle_card_'))
    application.add_handler(CallbackQueryHandler(roll_dice, pattern='^roll_dice_'))
    application.add_handler(CallbackQueryHandler(use_bonus, pattern='^use_bonus_'))
    application.add_handler(CallbackQueryHandler(cancel_battle, pattern='^cancel_battle$'))
    application.add_handler(CallbackQueryHandler(show_fight_menu, pattern='^fight_menu$'))
