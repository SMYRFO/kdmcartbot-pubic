from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config import ADMINS
from utils.helpers import safe_edit_or_send, delete_previous_messages, track_message
from handlers.admin import is_admin, send_to_all_admins
import logging
from database import get_payment, update_payment_status, update_user, get_user
import re

logger = logging.getLogger(__name__)
support_logger = logging.getLogger('support_handler')
support_logger.setLevel(logging.INFO)

# Создаем обработчик для файла поддержки
file_handler = logging.FileHandler('support_activity.log')
file_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
support_logger.addHandler(file_handler)



async def support_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды обращения в поддержку"""
    user = update.effective_user
    chat = update.effective_chat

    await delete_previous_messages(context, chat.id, user.id)

    keyboard = [
        [InlineKeyboardButton("Написать в поддержку", callback_data='write_to_support')],
        [InlineKeyboardButton("Частые вопросы", callback_data='faq')],
        [InlineKeyboardButton("Назад", callback_data='main_menu')]
    ]

    text = (
        "🛟 *Центр поддержки*\n\n"
        "Здесь вы можете:\n"
        "• 📩 Написать обращение в поддержку\n"
        "• ❓ Посмотреть ответы на частые вопросы\n"
        "• 🔧 Получить помощь по использованию бота\n\n"
        "Мы постараемся ответить как можно скорее!"
    )

    try:
        if update.message:
            msg = await update.message.reply_text(
                text=text,
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            try:
                await update.callback_query.edit_message_text(
                    text=text,
                    parse_mode='Markdown',
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                msg = update.callback_query.message
            except Exception as edit_error:
                if "message to edit not found" in str(edit_error).lower():
                    logger.debug(f"Сообщение для редактирования не найдено, отправляем новое")
                msg = await context.bot.send_message(
                    chat_id=chat.id,
                    text=text,
                    parse_mode='Markdown',
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )

        await track_message(user.id, msg.message_id)

    except Exception as e:
        logger.error(f"Критическая ошибка отправки меню поддержки: {e}")
        try:
            msg = await context.bot.send_message(
                chat_id=chat.id,
                text=text,
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            await track_message(user.id, msg.message_id)
        except Exception as final_error:
            logger.critical(f"Полный сбой отправки меню поддержки: {final_error}")


async def handle_support_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик начала написания обращения"""
    query = update.callback_query
    await query.answer()

    context.user_data['awaiting_support_message'] = True
    context.user_data['support_media'] = []

    try:
        await query.edit_message_text(
            "📝 *Напишите ваше обращение в поддержку:*\n\n"
            "Вы можете отправить:\n"
            "• 📝 Текстовое сообщение\n"
            "• 🖼️ Фото с описанием\n"
            "• 🎥 Видео с описанием\n"
            "• 📎 Документ с комментарием\n\n"
            "❌ Чтобы отменить, отправьте /cancel",
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.warning(f"Не удалось отредактировать сообщение: {e}")
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text="📝 *Напишите ваше обращение в поддержку:*\n\n"
                 "Вы можете отправить текст, фото или видео с описанием.\n\n"
                 "❌ Чтобы отменить, отправьте /cancel",
            parse_mode='Markdown'
        )


async def handle_support_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик сообщений и медиа для поддержки"""
    user = update.effective_user
    message = update.message

    # Сначала проверяем, является ли пользователь администратором
    if is_admin(user.id):
        logger.info(f"Сообщение от администратора {user.id}: {message.text}")
        await handle_admin_response(update, context)
        return

    # Затем проверяем, находится ли пользователь в режиме поддержки
    if not context.user_data.get('awaiting_support_message'):
        logger.info(f"Пользователь {user.first_name} не в режиме поддержки: {message.text}")
        # Если не в режиме поддержки, пропускаем обработку
        return

    # Обрабатываем в зависимости от типа сообщения
    if message.text:
        logger.info(f"Текст от пользователя {user.id} в поддержку: {message.text}")
        await process_support_text(update, context)
    elif message.photo:
        logger.info(f"Фото от {user.id} в поддержку")
        await process_support_photo(update, context)
    elif message.video:
        logger.info(f"Видео от {user.id} в поддержку")
        await process_support_video(update, context)
    elif message.document:
        logger.info(f"Документ от {user.id} в поддержку")
        await process_support_document(update, context)
    else:
        logger.warning(f"Неподдерживаемый тип сообщения от {user.id}")
        await message.reply_text(
            "❌ Неподдерживаемый тип сообщения. "
            "Отправьте текст, фото, видео или документ.",
            parse_mode='Markdown'
        )

async def process_support_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка текстового обращения"""
    user = update.effective_user
    message_text = update.message.text

    # Проверяем, не является ли это командой отмены
    if message_text.lower() in ['/cancel', 'отмена', 'cancel']:
        await cancel_support_command(update, context)
        return

    # Проверяем, не является ли это командой завершения
    if message_text.lower() in ['/done', 'готово', 'done']:
        await done_support_command(update, context)
        return

    if context.user_data.get('support_media'):
        # Если есть медиа, сохраняем текст как описание
        context.user_data['support_text'] = message_text
        await update.message.reply_text(
            "📝 Текст сохранен как описание к медиа.\n"
            "✅ /done - отправить обращение\n"
            "❌ /cancel - отменить\n"
            "📎 Можно отправить еще медиа"
        )
    else:
        # Если нет медиа, отправляем текстовое обращение
        context.user_data['awaiting_support_message'] = False
        context.user_data['support_text'] = message_text
        await send_text_support_to_admin(update, context, message_text)


async def process_support_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка фото с описанием"""
    try:
        message = update.message
        photo = message.photo[-1]
        caption = message.caption or "Фото без описания"

        logger.info(f"Обработка фото: file_id={photo.file_id}")

        if 'support_media' not in context.user_data:
            context.user_data['support_media'] = []

        context.user_data['support_media'].append({
            'type': 'photo',
            'file_id': photo.file_id,
            'caption': caption
        })

        await message.reply_text(
            "🖼️ Фото принято! Отправьте еще медиа или текст.\n"
            "✅ /done - закончить\n"
            "❌ /cancel - отменить"
        )

    except Exception as e:
        logger.error(f"Ошибка обработки фото: {e}")
        await update.message.reply_text("❌ Ошибка обработки фото")


async def process_support_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка видео с описанием"""
    try:
        message = update.message
        video = message.video
        caption = message.caption or "Видео без описания"

        logger.info(f"Обработка видео: file_id={video.file_id}")

        if 'support_media' not in context.user_data:
            context.user_data['support_media'] = []

        context.user_data['support_media'].append({
            'type': 'video',
            'file_id': video.file_id,
            'caption': caption
        })

        await message.reply_text(
            "🎥 Видео принято! Отправьте еще медиа или текст.\n"
            "✅ /done - закончить\n"
            "❌ /cancel - отменить"
        )

    except Exception as e:
        logger.error(f"Ошибка обработки видео: {e}")
        await update.message.reply_text("❌ Ошибка обработки видео")


async def send_text_support_to_admin(update: Update, context: ContextTypes.DEFAULT_TYPE, message_text: str):
    """Отправка текстового обращения всем администраторам"""
    user = update.effective_user
    chat_id = update.message.chat_id if update.message else update.effective_chat.id

    admin_text = f"""
🚨 НОВОЕ ТЕКСТОВОЕ ОБРАЩЕНИЕ 🚨

👤 Пользователь: {user.first_name}
📛 Username: @{user.username or 'нет'}
🆔 ID: {user.id}
💬 Chat ID: {chat_id}

💬 Сообщение:
{message_text}

💬 Ответьте на это сообщение или используйте: /reply {user.id} ваш текст
"""

    success = await send_to_all_admins(context, admin_text)

    if success:
        await update.message.reply_text(
            "✅ Ваше обращение отправлено администраторам! Ответ придет сюда.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🏠 Главное меню", callback_data='main_menu')]
            ])
        )
    else:
        await update.message.reply_text("❌ Ошибка отправки обращения")


async def send_media_support_to_admins(update: Update, context: ContextTypes.DEFAULT_TYPE, message_text: str,
                                       media_files: list):
    """Отправляет медиа-обращение всем администраторам"""
    user = update.effective_user
    chat_id = update.message.chat_id if update.message else update.effective_chat.id

    admin_text = f"""
🚨 НОВОЕ ОБРАЩЕНИЕ С МЕДИА 🚨

👤 Пользователь: {user.first_name}
📛 Username: @{user.username or 'нет'}
🆔 ID: {user.id}
💬 Chat ID: {chat_id}

💬 Сообщение:
{message_text[:500]}{'...' if len(message_text) > 500 else ''}

📎 Прикреплено файлов: {len(media_files)}
💬 Ответьте на это сообщение или используйте: /reply {user.id} ваш текст
"""

    success_count = 0

    for admin_id in ADMINS:
        try:
            info_msg = await context.bot.send_message(
                chat_id=admin_id,
                text=admin_text
            )

            for media in media_files:
                try:
                    if media['type'] == 'photo':
                        await context.bot.send_photo(
                            chat_id=admin_id,
                            photo=media['file_id'],
                            caption=f"🖼️ {media.get('caption', 'Фото без описания')}",
                            reply_to_message_id=info_msg.message_id
                        )
                    elif media['type'] == 'video':
                        await context.bot.send_video(
                            chat_id=admin_id,
                            video=media['file_id'],
                            caption=f"🎥 {media.get('caption', 'Видео без описания')}",
                            reply_to_message_id=info_msg.message_id
                        )
                except Exception as media_error:
                    logger.error(f"Ошибка отправки медиа администратору {admin_id}: {media_error}")
                    await context.bot.send_message(
                        chat_id=admin_id,
                        text=f"❌ Не удалось отправить медиафайл: {media_error}",
                        reply_to_message_id=info_msg.message_id
                    )

            success_count += 1
            logger.info(f"Медиа-обращение отправлено администратору {admin_id}")

        except Exception as e:
            logger.error(f"Ошибка отправки администратору {admin_id}: {e}")

    return success_count > 0


async def send_support_to_admins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправка обращения администраторам"""
    user = update.effective_user
    support_text = context.user_data.get('support_text', '')
    support_media = context.user_data.get('support_media', [])

    if support_media:
        return await send_media_support_to_admins(update, context, support_text, support_media)
    else:
        return await send_text_support_to_admin(update, context, support_text)


async def done_support_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Завершение отправки обращения"""
    if not context.user_data.get('awaiting_support_message'):
        await update.message.reply_text("ℹ️ Нет активного обращения")
        return

    support_text = context.user_data.get('support_text', '')
    support_media = context.user_data.get('support_media', [])

    if support_media:
        success = await send_media_support_to_admins(update, context, support_text, support_media)
    else:
        success = await send_text_support_to_admin(update, context, support_text)

    if success:
        context.user_data['awaiting_support_message'] = False
        context.user_data['support_media'] = []
        context.user_data['support_text'] = ''

        await update.message.reply_text(
            "✅ Ваше обращение отправлено администраторам! Ответ придет сюда.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🏠 Главное меню", callback_data='main_menu')]
            ])
        )
    else:
        await update.message.reply_text("❌ Ошибка отправки обращения")


async def cancel_support_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена обращения"""
    if context.user_data.get('awaiting_support_message'):
        context.user_data['awaiting_support_message'] = False
        context.user_data['support_media'] = []
        context.user_data['support_text'] = ''
        await update.message.reply_text(
            "❌ Отправка обращения отменена.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🏠 Главное меню", callback_data='main_menu')]
            ])
        )
    else:
        await update.message.reply_text("ℹ️ Нет активного обращения для отмены")


async def handle_faq(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик частых вопросов"""
    query = update.callback_query
    await query.answer()

    faq_text = (
        "❓ *Частые вопросы*\n\n"
        "1. *Как получить монеты?*\n"
        "   - Нажимайте /balance каждые 3 часа\n"
        "   - Покупайте кейсы в магазине\n\n"
        "2. *Как получить карточки?*\n"
        "   - Открывайте кейсы из магазина\n"
        "   - Получайте ежедневные награды по /check\n\n"
        "3. *Как подарить карточку?*\n"
        "   - Используйте меню подарков (/gift)\n"
        "   - Выберите карточку и укажите username\n\n"
        "4. *Пропала карточка?*\n"
        "   - Напишите в поддержку с описанием проблемы\n\n"
        "Не нашли ответ? Напишите в поддержку!"
    )

    keyboard = [
        [InlineKeyboardButton("📩 Написать в поддержку", callback_data='write_to_support')],
        [InlineKeyboardButton("🔙 Назад", callback_data='support')]
    ]

    try:
        await query.edit_message_text(
            text=faq_text,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as edit_error:
        if "message to edit not found" in str(edit_error).lower():
            logger.debug(f"Сообщение для редактирования не найдено, отправляем новое")
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=faq_text,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )


async def handle_admin_response(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ответов администраторов"""
    if update.effective_user.id not in ADMINS:
        return

    if not update.message.reply_to_message:
        await update.message.reply_text("Ответьте на сообщение с обращением")
        return

    replied_message = update.message.reply_to_message
    response_text = update.message.text

    chat_id = None
    user_id_match = re.search(r'ID: (\d+)', replied_message.text)

    if user_id_match:
        user_id = int(user_id_match.group(1))
        chat_id = user_id

    if chat_id:
        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"📩 *Ответ от поддержки:*\n\n{response_text}",
                parse_mode='Markdown'
            )
            await update.message.reply_text(f"✅ Ответ отправлен!")
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка отправки: {e}")



async def reply_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда для ответа на обращения"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Только для администраторов")
        return

    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "Использование: /reply <user_id> <текст ответа>\n\n"
            "Пример: /reply 123456789 Привет! Ваша проблема решена."
        )
        return

    try:
        user_id = int(context.args[0])
        response_text = ' '.join(context.args[1:])

        await context.bot.send_message(
            chat_id=user_id,
            text=f"📩 *Ответ от поддержки:*\n\n{response_text}\n\n"
                 f"_Если нужна дополнительная помощь, обращайтесь снова_",
            parse_mode='Markdown'
        )

        await update.message.reply_text(f"✅ Ответ отправлен пользователю {user_id}")

    except ValueError:
        await update.message.reply_text("❌ user_id должен быть числом")
    except Exception as e:
        error_msg = str(e)
        if "chat not found" in error_msg:
            await update.message.reply_text(f"❌ Пользователь {user_id} не найден")
        else:
            await update.message.reply_text(f"❌ Ошибка: {error_msg}")


async def admins_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает список администраторов"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Только для администраторов")
        return

    admins_list = "\n".join([f"• {admin_id}" for admin_id in ADMINS])
    await update.message.reply_text(
        f"👥 Список администраторов:\n\n{admins_list}\n\n"
        f"Всего: {len(ADMINS)} администраторов"
    )


async def add_admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Добавляет администратора"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Только для администраторов")
        return

    if not context.args:
        await update.message.reply_text("Использование: /addadmin <user_id>")
        return

    try:
        new_admin_id = int(context.args[0])
        if new_admin_id in ADMINS:
            await update.message.reply_text("❌ Этот пользователь уже администратор")
            return

        ADMINS.append(new_admin_id)
        await update.message.reply_text(f"✅ Пользователь {new_admin_id} добавлен в администраторы")

    except ValueError:
        await update.message.reply_text("❌ user_id должен быть числом")


async def remove_admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Удаляет администратора"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Только для администраторов")
        return

    if not context.args:
        await update.message.reply_text("Использование: /removeadmin <user_id>")
        return

    try:
        admin_id = int(context.args[0])
        if admin_id not in ADMINS:
            await update.message.reply_text("❌ Этот пользователь не администратор")
            return

        if len(ADMINS) <= 1:
            await update.message.reply_text("❌ Нельзя удалить последнего администратора")
            return

        ADMINS.remove(admin_id)
        await update.message.reply_text(f"✅ Пользователь {admin_id} удален из администраторов")

    except ValueError:
        await update.message.reply_text("❌ user_id должен быть числом")


# support.py - добавьте команды для управления платежами

async def accept_payment_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда для подтверждения платежа"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Только для администраторов")
        return

    if not context.args:
        await update.message.reply_text("Использование: /accept_pay <payment_id>")
        return

    try:
        payment_id = int(context.args[0])
        admin_id = update.effective_user.id

        from database import get_payment, update_payment_status, update_user, get_user

        payment = get_payment(payment_id)
        if not payment:
            await update.message.reply_text("❌ Платеж не найден")
            return

        if payment['status'] != 'pending':
            await update.message.reply_text(f"❌ Платеж уже обработан (статус: {payment['status']})")
            return

        # Обновляем статус платежа
        update_payment_status(payment_id, 'approved', admin_id)

        # Начисляем монеты пользователю
        user = get_user(payment['user_id'])
        new_balance = user['coins'] + payment['amount_coins']
        update_user(payment['user_id'], {'coins': new_balance})

        # Уведомляем пользователя
        try:
            await context.bot.send_message(
                chat_id=payment['user_id'],
                text=f"✅ Ваш платеж #{payment_id} подтвержден!\n\n"
                     f"🪙 Начислено: {payment['amount_coins']} монет\n"
                     f"💰 Новый баланс: {new_balance} монет\n\n"
                     f"Спасибо за покупку! 🎉"
            )
        except Exception as e:
            logger.error(f"Ошибка уведомления пользователя: {e}")

        await update.message.reply_text(
            f"✅ Платеж #{payment_id} подтвержден!\n"
            f"Пользователю {payment['user_id']} начислено {payment['amount_coins']} монет."
        )

    except ValueError:
        await update.message.reply_text("❌ payment_id должен быть числом")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")


async def reject_payment_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда для отклонения платежа"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Только для администраторов")
        return

    if not context.args:
        await update.message.reply_text("Использование: /reject_pay <payment_id> [причина]")
        return

    try:
        payment_id = int(context.args[0])
        reason = ' '.join(context.args[1:]) if len(context.args) > 1 else "Причина не указана"
        admin_id = update.effective_user.id

        from database import get_payment, update_payment_status

        payment = get_payment(payment_id)
        if not payment:
            await update.message.reply_text("❌ Платеж не найден")
            return

        if payment['status'] != 'pending':
            await update.message.reply_text(f"❌ Платеж уже обработан (статус: {payment['status']})")
            return

        # Обновляем статус платежа
        update_payment_status(payment_id, 'rejected', admin_id)

        # Уведомляем пользователя
        try:
            await context.bot.send_message(
                chat_id=payment['user_id'],
                text=f"❌ Ваш платеж #{payment_id} отклонен.\n\n"
                     f"📋 Причина: {reason}\n\n"
                     f"Если вы считаете это ошибкой, обратитесь в поддержку."
            )
        except Exception as e:
            logger.error(f"Ошибка уведомления пользователя: {e}")

        await update.message.reply_text(f"✅ Платеж #{payment_id} отклонен.")

    except ValueError:
        await update.message.reply_text("❌ payment_id должен быть числом")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")


async def list_payments_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда для просмотра платежей"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Только для администраторов")
        return

    from database import get_pending_payments

    payments = get_pending_payments()

    if not payments:
        await update.message.reply_text("📊 Ожидающих платежей нет.")
        return

    message = "📊 *Ожидающие платежи:*\n\n"

    for payment in payments:
        message += (
            f"🆔 #{payment['payment_id']}\n"
            f"👤 User ID: {payment['user_id']}\n"
            f"💳 Сумма: {payment['amount_rub']:.2f} руб.\n"
            f"🪙 Монет: {payment['amount_coins']}\n"
            f"📅 Дата: {payment['created_at']}\n"
            f"✅ /accept_pay {payment['payment_id']}\n"
            f"❌ /reject_pay {payment['payment_id']}\n\n"
        )

    await update.message.reply_text(message, parse_mode='Markdown')


async def process_support_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка документа с описанием"""
    try:
        message = update.message
        document = message.document
        caption = message.caption or "Документ без описания"

        logger.info(f"Обработка документа: file_id={document.file_id}")

        if 'support_media' not in context.user_data:
            context.user_data['support_media'] = []

        context.user_data['support_media'].append({
            'type': 'document',
            'file_id': document.file_id,
            'caption': caption
        })

        await message.reply_text(
            "📎 Документ принят! Отправьте еще медиа или текст.\n"
            "✅ /done - закончить и отправить\n"
            "❌ /cancel - отменить обращение"
        )

    except Exception as e:
        logger.error(f"Ошибка обработки документа: {e}")
        await update.message.reply_text("❌ Ошибка обработки документа")
