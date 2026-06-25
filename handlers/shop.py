from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import get_user, get_cases, get_case_contents, update_user, add_to_collection, get_card, get_bonuses, add_user_bonus
from utils.helpers import track_message, delete_previous_messages
import random
import logging

logger = logging.getLogger(__name__)


async def shop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat

    await delete_previous_messages(context, chat.id, user.id)
    await show_main_shop(update, context)


async def show_main_shop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает главное меню магазина"""
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

        shop_text = "🏪 *Главный магазин*\n\n"
        shop_text += f"💰 Ваш баланс: *{user_data['coins']}* монет\n\n"
        shop_text += "Выберите раздел магазина:"

        keyboard = [
            [InlineKeyboardButton("🎁 Магазин кейсов", callback_data='shop_cases')],
            [InlineKeyboardButton("⚡ Магазин бонусов", callback_data='shop_bonuses')],
            [InlineKeyboardButton("🪙 Магазин монет", callback_data='shop_coins')],
            [InlineKeyboardButton("🔙 Назад", callback_data='main_menu')]
        ]

        try:
            if update.callback_query:
                await query.edit_message_text(
                    text=shop_text,
                    parse_mode='Markdown',
                    reply_markup=InlineKeyboardMarkup(keyboard))
            else:
                msg = await message.reply_text(
                    text=shop_text,
                    parse_mode='Markdown',
                    reply_markup=InlineKeyboardMarkup(keyboard))
                if msg and hasattr(msg, 'message_id'):
                    await track_message(user.id, msg.message_id)
        except Exception as e:
            logger.error(f"Error showing main shop: {e}")
            msg = await context.bot.send_message(
                chat_id=chat_id,
                text=shop_text,
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


async def show_cases_shop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает магазин кейсов (старая функция shop_command)"""
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
        cases = get_cases()

        shop_text = "🛒 *Магазин кейсов*\n\n"
        shop_text += f"💰 Ваш баланс: *{user_data['coins']}* монет\n\n"

        for case in cases:
            shop_text += f"*{case['name']}* - {case['price']} монет\n"

        keyboard = []
        for case in cases:
            keyboard.append([
                InlineKeyboardButton(
                    f"Купить {case['name']}",
                    callback_data=f'buy_case_{case["case_id"]}'
                )
            ])
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data='shop_main')])

        try:
            if update.callback_query:
                await query.edit_message_text(
                    text=shop_text,
                    parse_mode='Markdown',
                    reply_markup=InlineKeyboardMarkup(keyboard))
            else:
                msg = await message.reply_text(
                    text=shop_text,
                    parse_mode='Markdown',
                    reply_markup=InlineKeyboardMarkup(keyboard))
                if msg and hasattr(msg, 'message_id'):
                    await track_message(user.id, msg.message_id)
        except Exception as e:
            logger.error(f"Error showing cases shop: {e}")
            msg = await context.bot.send_message(
                chat_id=chat_id,
                text=shop_text,
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard))
            if msg and hasattr(msg, 'message_id'):
                await track_message(user.id, msg.message_id)

    except Exception as e:
        logger.error(f"Error in show_cases_shop: {e}")
        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text="❌ Произошла ошибка при загрузке магазина кейсов."
            )
        except Exception:
            pass


async def show_bonuses_shop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает магазин бонусов"""
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
        bonuses = get_bonuses()

        shop_text = "⚡ *Магазин бонусов*\n\n"
        shop_text += f"💰 Ваш баланс: *{user_data['coins']}* монет\n\n"
        shop_text += "*Доступные бонусы:*\n\n"

        for bonus in bonuses:
            shop_text += f"🔹 *{bonus['name']}*\n"
            shop_text += f"   {bonus['description']}\n"
            shop_text += f"   Цена: {bonus['price']} монет\n\n"

        keyboard = []
        for bonus in bonuses:
            keyboard.append([
                InlineKeyboardButton(
                    f"Купить {bonus['name']}",
                    callback_data=f'buy_bonus_{bonus["bonus_id"]}'
                )
            ])
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data='shop_main')])

        try:
            if update.callback_query:
                await query.edit_message_text(
                    text=shop_text,
                    parse_mode='Markdown',
                    reply_markup=InlineKeyboardMarkup(keyboard))
            else:
                msg = await message.reply_text(
                    text=shop_text,
                    parse_mode='Markdown',
                    reply_markup=InlineKeyboardMarkup(keyboard))
                if msg and hasattr(msg, 'message_id'):
                    await track_message(user.id, msg.message_id)
        except Exception as e:
            logger.error(f"Error showing bonuses shop: {e}")
            msg = await context.bot.send_message(
                chat_id=chat_id,
                text=shop_text,
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard))
            if msg and hasattr(msg, 'message_id'):
                await track_message(user.id, msg.message_id)

    except Exception as e:
        logger.error(f"Error in show_bonuses_shop: {e}")
        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text="❌ Произошла ошибка при загрузке магазина бонусов."
            )
        except Exception:
            pass


async def show_coins_shop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает магазин монет с инструкцией по покупке"""
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

        from config import COIN_PRICE, PAYMENT_CARD, PAYMENT_RECEIVER

        user_data = get_user(user.id)

        shop_text = (
            "🪙 *Магазин монет*\n\n"
            f"💰 Ваш текущий баланс: *{user_data['coins']}* монет\n\n"
            "💳 *Как купить монеты:*\n"
            "1. Введите количество монет которые хотите купить\n"
            "2. Оплатите рассчитанную сумму на карту\n"
            "3. Отправьте скриншот оплаты\n"
            "4. Администратор подтвердит платеж\n\n"
            f"📊 *Курс:* 1 рубль = 5 монет\n\n"
            "Введите количество монет для покупки:"
        )

        keyboard = [
            [InlineKeyboardButton("🔙 Назад", callback_data='shop_main')]
        ]

        # Сохраняем состояние ожидания ввода количества монет
        context.user_data['awaiting_coin_amount'] = True

        try:
            if update.callback_query:
                await query.edit_message_text(
                    text=shop_text,
                    parse_mode='Markdown',
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            else:
                msg = await message.reply_text(
                    text=shop_text,
                    parse_mode='Markdown',
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                if msg and hasattr(msg, 'message_id'):
                    await track_message(user.id, msg.message_id)
        except Exception as e:
            logger.error(f"Error showing coins shop: {e}")
            msg = await context.bot.send_message(
                chat_id=chat_id,
                text=shop_text,
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            if msg and hasattr(msg, 'message_id'):
                await track_message(user.id, msg.message_id)

    except Exception as e:
        logger.error(f"Error in show_coins_shop: {e}")
        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text="❌ Произошла ошибка при загрузке магазина монет."
            )
        except Exception:
            pass

async def buy_bonus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Покупка бонуса"""
    query = update.callback_query
    await query.answer()

    try:
        bonus_id = int(query.data.split('_')[2])
        user_id = query.from_user.id
        username = query.from_user.username or query.from_user.first_name
        mention = f"[{query.from_user.first_name}](tg://user?id={user_id})"

        logger.info(f"Покупка бонуса | User: {user_id} | Bonus: {bonus_id}")

        user = get_user(user_id)
        if not user:
            logger.error(f"Пользователь не найден | User: {user_id}")
            await query.message.reply_text("❌ Ошибка: ваш профиль не найден, нажмите /start")
            return

        bonuses = get_bonuses()
        bonus = next((b for b in bonuses if b['bonus_id'] == bonus_id), None)

        if not bonus:
            logger.warning(f"Бонус не найден | Bonus: {bonus_id}")
            await query.message.reply_text("❌ Этот бонус временно недоступен")
            return

        if user['coins'] < bonus['price']:
            logger.info(f"Недостаточно монет | User: {user_id} | Balance: {user['coins']} | Price: {bonus['price']}")
            await query.message.reply_text(
                f"❌ У {mention} недостаточно монет. Нужно: {bonus['price']}, у вас: {user['coins']}",
                parse_mode='Markdown'
            )
            return

        new_balance = user['coins'] - bonus['price']

        if not update_user(user_id, {'coins': new_balance}):
            logger.error(f"Ошибка обновления баланса | User: {user_id}")
            await query.message.reply_text("❌ Ошибка обновления баланса")
            return

        if not add_user_bonus(user_id, bonus_id):
            logger.error(f"Ошибка добавления бонуса | User: {user_id} | Bonus: {bonus_id}")
            await query.message.reply_text("❌ Ошибка добавления бонуса")
            return

        logger.info(f"Успешная покупка бонуса | User: {user_id} | Bonus: {bonus_id} | New balance: {new_balance}")

        keyboard = [
            [InlineKeyboardButton("Купить еще", callback_data=f'buy_bonus_{bonus_id}')],
            [InlineKeyboardButton("Назад в магазин", callback_data='shop_bonuses')],
        ]

        message_text = (
            f"🎉 {mention} приобрел бонус:\n"
            f"*{bonus['name']}*\n"
            f"{bonus['description']}\n\n"
            f"💰 Новый баланс: {new_balance} монет"
        )

        await query.message.reply_text(
            message_text,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    except Exception as e:
        logger.error(f"Критическая ошибка в buy_bonus: {str(e)}", exc_info=True)
        try:
            await query.message.reply_text("❌ Произошла ошибка. Попробуйте /start")
        except Exception as send_error:
            logger.error(f"Не удалось отправить сообщение об ошибке: {send_error}")


# Обновим функцию buy_case для работы с новым меню
async def buy_case(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    try:
        case_id = int(query.data.split('_')[2])
        user_id = query.from_user.id
        chat_id = query.message.chat.id
        username = query.from_user.username or query.from_user.first_name
        mention = f"[{query.from_user.first_name}](tg://user?id={user_id})"

        logger.info(f"Покупка кейса | User: {user_id} | Case: {case_id}")

        user = get_user(user_id)
        if not user:
            logger.error(f"Пользователь не найден | User: {user_id}")
            await query.message.reply_text("❌ Ошибка: ваш профиль не найден, нажмите /start")
            return

        cases = get_cases()
        case = next((c for c in cases if c['case_id'] == case_id), None)

        if not case:
            logger.warning(f"Кейс не найден | Case: {case_id}")
            await query.message.reply_text("❌ Этот кейс временно недоступен")
            return

        if user['coins'] < case['price']:
            logger.info(f"Недостаточно монет | User: {user_id} | Balance: {user['coins']} | Price: {case['price']}")
            await query.message.reply_text(
                f"❌ У {mention} недостаточно монет. Нужно: {case['price']}, у вас: {user['coins']}",
                parse_mode='Markdown'
            )
            return

        available_cards = get_case_contents(case_id)

        if not available_cards:
            logger.error(f"Нет карточек в кейсе | Case: {case_id}")
            await query.message.reply_text("❌ В этом кейсе закончились карточки")
            return

        card_id = random.choice(available_cards)
        new_balance = user['coins'] - case['price']

        if not update_user(user_id, {'coins': new_balance}):
            logger.error(f"Ошибка обновления баланса | User: {user_id}")
            await query.message.reply_text("❌ Ошибка обновления баланса")
            return

        if not add_to_collection(user_id, card_id):
            logger.error(f"Ошибка добавления карточки | User: {user_id} | Card: {card_id}")
            await query.message.reply_text("❌ Ошибка добавления карточки в коллекцию")
            return

        card = get_card(card_id)
        card_name = card['name'] if card else f"карточка #{card_id}"
        rarity = card['rarity'] if card else "🤍 Редкий"

        # Получаем характеристики карточки
        from handlers.fight import get_card_stats
        card_stats = get_card_stats(card_id)

        logger.info(
            f"Успешная покупка | User: {user_id} | Case: {case_id} | Card: {card_id} | New balance: {new_balance}")

        keyboard = [
            [InlineKeyboardButton("Открыть еще", callback_data=f'buy_case_{case_id}')],
            [InlineKeyboardButton("Моя коллекция", callback_data='collection')],
            [InlineKeyboardButton("Назад в магазин", callback_data='shop_cases')],
        ]

        from handlers.fight import get_card_stats
        card_stats = get_card_stats(card_id)
        health_display = int(card_stats['health'])
        damage_display = f"{card_stats['damage']:.1f}"

        message_text = (
            f"🎉 {mention} получил:\n"
            f"*{card_name}* {rarity}\n"
            f"❤️ Здоровье: {health_display}\n"
            f"⚔️ Урон: {damage_display}\n\n"
            f"💰 Новый баланс: {new_balance} монет"
        )

        if card and card.get('image_url'):
            try:
                await query.message.reply_photo(
                    photo=card['image_url'],
                    caption=message_text,
                    parse_mode='Markdown',
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                return
            except Exception as e:
                logger.error(f"Ошибка отправки фото карточки: {e}")

        await query.message.reply_text(
            message_text,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    except Exception as e:
        logger.error(f"Критическая ошибка в buy_case: {str(e)}", exc_info=True)
        try:
            await query.message.reply_text("❌ Произошла ошибка. Попробуйте /start")
        except Exception as send_error:
            logger.error(f"Не удалось отправить сообщение об ошибке: {send_error}")


async def handle_coin_amount_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает ввод количества монет для покупки"""
    if not context.user_data.get('awaiting_coin_amount'):
        return

    user = update.effective_user
    message_text = update.message.text.strip()

    try:
        coin_amount = int(message_text)

        if coin_amount <= 0:
            await update.message.reply_text("❌ Количество монет должно быть больше 0!")
            return

        if coin_amount > 10000:
            await update.message.reply_text("❌ Максимальное количество за раз - 10,000 монет!")
            return

        from config import COIN_PRICE, PAYMENT_CARD, PAYMENT_RECEIVER

        # Рассчитываем сумму в рублях
        amount_rub = coin_amount * COIN_PRICE

        payment_text = (
            f"💳 *Детали оплаты*\n\n"
            f"🪙 Монет к покупке: *{coin_amount}*\n"
            f"💰 Сумма к оплате: *{amount_rub:.2f} руб.*\n\n"
            f"💳 *Реквизиты для оплаты:*\n"
            f"Номер карты: `{PAYMENT_CARD}`\n\n"
            f"После оплаты отправьте скриншот чека или подтверждения оплаты.\n"
            f"Администратор проверит платеж и начислит монеты."
        )

        # Сохраняем данные о покупке
        context.user_data['coin_purchase'] = {
            'coin_amount': coin_amount,
            'amount_rub': amount_rub
        }
        context.user_data['awaiting_coin_amount'] = False
        context.user_data['awaiting_payment_screenshot'] = True

        await update.message.reply_text(
            text=payment_text,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ Отменить покупку", callback_data='cancel_coin_purchase')]
            ])
        )

    except ValueError:
        await update.message.reply_text("❌ Пожалуйста, введите число (например: 100)")
    except Exception as e:
        logger.error(f"Ошибка обработки ввода монет: {e}")
        await update.message.reply_text("❌ Произошла ошибка. Попробуйте снова.")


# shop.py - добавьте обработчик отмены покупки

async def cancel_coin_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отменяет покупку монет"""
    query = update.callback_query
    await query.answer()

    # Очищаем состояние покупки
    if 'coin_purchase' in context.user_data:
        del context.user_data['coin_purchase']
    context.user_data['awaiting_coin_amount'] = False
    context.user_data['awaiting_payment_screenshot'] = False

    await show_coins_shop(update, context)


# shop.py - добавьте обработчик медиа для скриншотов оплаты

# shop.py - исправьте handle_payment_screenshot

async def handle_payment_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает скриншот оплаты"""
    if not context.user_data.get('awaiting_payment_screenshot'):
        return

    user = update.effective_user
    message = update.message

    if not context.user_data.get('coin_purchase'):
        await message.reply_text("❌ Данные о покупке не найдены. Начните заново.")
        return

    purchase_data = context.user_data['coin_purchase']

    # Получаем file_id медиа
    if message.photo:
        file_id = message.photo[-1].file_id
        media_type = 'photo'
    elif message.document:
        file_id = message.document.file_id
        media_type = 'document'
    else:
        await message.reply_text("❌ Пожалуйста, отправьте скриншот или фото чека.")
        return

    try:
        # Сохраняем информацию о платеже в базу
        from database import create_payment
        payment_id = create_payment(
            user_id=user.id,
            amount_rub=purchase_data['amount_rub'],
            amount_coins=purchase_data['coin_amount'],
            screenshot_url=file_id
        )

        # Проверяем, что payment_id получен
        if payment_id is None:
            logger.error("Не удалось получить ID платежа из базы данных")
            await message.reply_text("❌ Ошибка при создании платежа. Попробуйте снова.")
            return

        logger.info(f"Создан платеж ID: {payment_id} для пользователя {user.id}")

        # Отправляем уведомление администраторам
        from handlers.admin import send_to_all_admins
        admin_message = (
            f"🪙 *НОВЫЙ ПЛАТЕЖ* 🪙\n\n"
            f"👤 Пользователь: {user.first_name} (@{user.username or 'нет'})\n"
            f"🆔 ID: {user.id}\n"
            f"💳 Сумма: {purchase_data['amount_rub']:.2f} руб.\n"
            f"🪙 Монет: {purchase_data['coin_amount']}\n"
            f"📋 ID платежа: {payment_id}\n\n"
            f"✅ Для подтверждения: /accept_pay {payment_id}\n"
            f"❌ Для отклонения: /reject_pay {payment_id}"
        )

        await send_to_all_admins(context, admin_message)

        # Отправляем само медиа администраторам
        from config import ADMINS
        for admin_id in ADMINS:
            try:
                if media_type == 'photo':
                    await context.bot.send_photo(
                        chat_id=admin_id,
                        photo=file_id,
                        caption=f"Скриншот оплаты для платежа #{payment_id}"
                    )
                else:
                    await context.bot.send_document(
                        chat_id=admin_id,
                        document=file_id,
                        caption=f"Документ оплаты для платежа #{payment_id}"
                    )
            except Exception as e:
                logger.error(f"Ошибка отправки медиа администратору {admin_id}: {e}")

        # Очищаем состояние
        del context.user_data['coin_purchase']
        context.user_data['awaiting_payment_screenshot'] = False

        await message.reply_text(
            f"✅ Скриншот оплаты принят! Ожидайте подтверждения администратора.\n"
            f"📋 ID вашего платежа: {payment_id}\n"
            f"Монеты будут начислены в течение 24 часов после проверки платежа.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🏪 Вернуться в магазин", callback_data='shop_main')]
            ])
        )

    except Exception as e:
        logger.error(f"Ошибка обработки скриншота оплаты: {e}")
        await message.reply_text("❌ Произошла ошибка при обработке платежа. Попробуйте снова.")
