import logging
from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, filters
from database import execute_query
import asyncio

logger = logging.getLogger(__name__)


def is_admin(user_id: int) -> bool:
    """Проверяет, является ли пользователь администратором"""
    from config import ADMINS  # Import locally to avoid circular imports
    return user_id in ADMINS


async def track_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отслеживает все чаты, в которых находится бот"""
    try:
        chat = update.effective_chat
        user = update.effective_user

        # Для пользователей (личные сообщения) - всегда отслеживаем
        if chat.type == 'private' and user:
            # Проверяем, есть ли уже пользователь в базе
            existing_user = execute_query(
                "SELECT user_id FROM broadcast_users WHERE user_id = ?",
                (user.id,),
                fetch_one=True
            )

            user_data = {
                'user_id': user.id,
                'username': user.username,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'language_code': user.language_code
            }

            execute_query('''
                INSERT OR REPLACE INTO broadcast_users 
                (user_id, username, first_name, last_name, language_code, last_seen, is_active)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, TRUE)
            ''', (user_data['user_id'], user_data['username'], user_data['first_name'],
                  user_data['last_name'], user_data['language_code']))

            if not existing_user:
                logger.info(f"Новый пользователь отслежен: {user.first_name} (ID: {user.id})")
            else:
                logger.debug(f"Пользователь обновлен: {user.first_name} (ID: {user.id})")

        # Для групповых чатов и каналов - отслеживаем при любом взаимодействии
        elif chat.type in ['group', 'supergroup', 'channel']:
            # Проверяем, есть ли уже чат в базе
            existing_chat = execute_query(
                "SELECT chat_id FROM chats WHERE chat_id = ?",
                (chat.id,),
                fetch_one=True
            )

            try:
                members_count = await get_chat_members_count(context, chat.id)
            except:
                members_count = 0

            chat_data = {
                'chat_id': chat.id,
                'chat_type': chat.type,
                'chat_title': chat.title,
                'username': chat.username,
                'members_count': members_count
            }

            execute_query('''
                INSERT OR REPLACE INTO chats 
                (chat_id, chat_type, chat_title, username, members_count, last_activity, is_active)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, TRUE)
            ''', (chat_data['chat_id'], chat_data['chat_type'], chat_data['chat_title'],
                  chat_data['username'], chat_data['members_count']))

            if not existing_chat:
                logger.info(f"Новый чат отслежен: {chat_data['chat_title']} (ID: {chat.id}, Тип: {chat.type})")
            else:
                logger.debug(f"Чат обновлен: {chat_data['chat_title']} (ID: {chat.id})")

    except Exception as e:
        logger.error(f"Ошибка отслеживания чата: {e}")


async def get_chat_members_count(context: ContextTypes.DEFAULT_TYPE, chat_id: int) -> int:
    """Получает количество участников чата"""
    try:
        if chat_id < 0:  # Групповые чаты имеют отрицательные ID
            chat = await context.bot.get_chat(chat_id)
            return chat.get_members_count() if hasattr(chat, 'get_members_count') else 0
        return 1  # Для личных чатов
    except Exception as e:
        logger.error(f"Ошибка получения количества участников чата {chat_id}: {e}")
        return 0


def get_all_chats():
    """Получает все чаты (без проверки активности)"""
    return execute_query(
        "SELECT * FROM chats ORDER BY chat_type, chat_title",
        fetch_all=True
    ) or []


def get_all_users():
    """Получает всех пользователей (без проверки активности)"""
    return execute_query(
        "SELECT * FROM broadcast_users ORDER BY first_name",
        fetch_all=True
    ) or []


def get_chats_count():
    """Возвращает количество чатов (без проверки активности)"""
    result = execute_query(
        "SELECT COUNT(*) as count FROM chats",
        fetch_one=True
    )
    return result['count'] if result else 0


def get_users_count():
    """Возвращает количество пользователей (без проверки активности)"""
    result = execute_query(
        "SELECT COUNT(*) as count FROM broadcast_users",
        fetch_one=True
    )
    return result['count'] if result else 0


async def new_post_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда для создания новой рассылки"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Только для администраторов")
        return

    if not context.args:
        # Показываем статистику и инструкцию
        chats_count = get_chats_count()
        users_count = get_users_count()

        message = (
            "📢 *Система рассылки*\n\n"
            f"📊 Статистика:\n"
            f"• Чатов: {chats_count}\n"
            f"• Пользователей: {users_count}\n"
            f"• Всего получателей: {chats_count + users_count}\n\n"
            "💡 *Как сделать рассылку:*\n"
            "1. Ответьте на это сообщение текстом, фото или медиа\n"
            "2. Используйте /new_post_all для рассылки всем\n"
            "3. Используйте /new_post_chats для рассылки только в чаты\n"
            "4. Используйте /new_post_users для рассылки только пользователям\n\n"
            "⚠️ Будьте осторожны: отменить рассылку нельзя!"
        )

        await update.message.reply_text(message, parse_mode='Markdown')
        return


async def new_post_all_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Рассылка всем получателям"""
    await handle_broadcast(update, context, "all")


async def new_post_chats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Рассылка только в чаты"""
    await handle_broadcast(update, context, "chats")


async def new_post_users_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Рассылка только пользователям"""
    await handle_broadcast(update, context, "users")


async def handle_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE, target: str):
    """Обрабатывает рассылку"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Только для администраторов")
        return

    # Проверяем, что это ответ на сообщение
    if not update.message.reply_to_message:
        await update.message.reply_text(
            "❌ Ответьте на сообщение, которое хотите разослать!\n\n"
            "Пример:\n"
            "1. Отправьте сообщение (текст, фото и т.д.)\n"
            "2. Ответьте на него командой /new_post_all"
        )
        return

    source_message = update.message.reply_to_message
    admin = update.effective_user

    # Получаем получателей в зависимости от цели
    if target == "all":
        chats = get_all_chats()
        users = get_all_users()
        total_recipients = len(chats) + len(users)
        target_name = "всем получателям"
    elif target == "chats":
        chats = get_all_chats()
        users = []
        total_recipients = len(chats)
        target_name = "только в чаты"
    elif target == "users":
        chats = []
        users = get_all_users()
        total_recipients = len(users)
        target_name = "только пользователям"
    else:
        await update.message.reply_text("❌ Неверная цель рассылки")
        return

    if total_recipients == 0:
        await update.message.reply_text("❌ Нет получателей для рассылки")
        return

    # Подтверждение рассылки
    confirm_text = (
        f"⚠️ *Подтверждение рассылки*\n\n"
        f"Цель: {target_name}\n"
        f"Получателей: {total_recipients}\n\n"
        f"Сообщение:\n"
        f"{source_message.text or 'Медиа-сообщение'[:100]}...\n\n"
        f"✅ Для подтверждения введите /confirm_broadcast\n"
        f"❌ Для отмены введите /cancel_broadcast"
    )

    # Сохраняем данные рассылки во временное хранилище
    context.user_data['pending_broadcast'] = {
        'source_message': source_message,
        'target': target,
        'chats': chats,
        'users': users,
        'admin_id': admin.id
    }

    await update.message.reply_text(confirm_text, parse_mode='Markdown')


async def confirm_broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подтверждает рассылку"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Только для администраторов")
        return

    if 'pending_broadcast' not in context.user_data:
        await update.message.reply_text("❌ Нет ожидающих рассылок")
        return

    broadcast_data = context.user_data['pending_broadcast']
    source_message = broadcast_data['source_message']
    chats = broadcast_data['chats']
    users = broadcast_data['users']

    total_recipients = len(chats) + len(users)
    success_count = 0
    fail_count = 0

    # Отправляем статус начала рассылки
    status_message = await update.message.reply_text(
        f"🚀 Начинаем рассылку...\n0/{total_recipients}"
    )

    # Рассылаем в чаты
    for chat in chats:
        try:
            await send_message_to_chat(context, source_message, chat['chat_id'])
            success_count += 1
        except Exception as e:
            logger.error(f"Ошибка отправки в чат {chat['chat_id']}: {e}")
            fail_count += 1
            # Помечаем чат как неактивный при ошибке
            execute_query(
                "UPDATE chats SET is_active = FALSE WHERE chat_id = ?",
                (chat['chat_id'],)
            )

        # Обновляем статус каждые 10 отправок
        if (success_count + fail_count) % 10 == 0:
            try:
                await status_message.edit_text(
                    f"📤 Рассылка...\n{success_count + fail_count}/{total_recipients}\n"
                    f"✅ Успешно: {success_count}\n"
                    f"❌ Ошибок: {fail_count}"
                )
            except:
                pass

    # Рассылаем пользователям
    for user in users:
        try:
            await send_message_to_chat(context, source_message, user['user_id'])
            success_count += 1
        except Exception as e:
            logger.error(f"Ошибка отправки пользователю {user['user_id']}: {e}")
            fail_count += 1
            # Помечаем пользователя как неактивного при ошибке
            execute_query(
                "UPDATE broadcast_users SET is_active = FALSE WHERE user_id = ?",
                (user['user_id'],)
            )

        # Обновляем статус
        if (success_count + fail_count) % 10 == 0:
            try:
                await status_message.edit_text(
                    f"📤 Рассылка...\n{success_count + fail_count}/{total_recipients}\n"
                    f"✅ Успешно: {success_count}\n"
                    f"❌ Ошибок: {fail_count}"
                )
            except:
                pass

    # Финальный статус
    result_text = (
        f"🎉 *Рассылка завершена!*\n\n"
        f"📊 Результаты:\n"
        f"• Всего получателей: {total_recipients}\n"
        f"• ✅ Успешно: {success_count}\n"
        f"• ❌ Ошибок: {fail_count}\n"
        f"• 📈 Эффективность: {(success_count / total_recipients * 100):.1f}%"
    )

    try:
        await status_message.edit_text(result_text, parse_mode='Markdown')
    except:
        await update.message.reply_text(result_text, parse_mode='Markdown')

    # Очищаем временные данные
    if 'pending_broadcast' in context.user_data:
        del context.user_data['pending_broadcast']


async def cancel_broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отменяет рассылку"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Только для администраторов")
        return

    if 'pending_broadcast' in context.user_data:
        del context.user_data['pending_broadcast']
        await update.message.reply_text("✅ Рассылка отменена")
    else:
        await update.message.reply_text("❌ Нет активных рассылок для отмены")


async def send_message_to_chat(context: ContextTypes.DEFAULT_TYPE, source_message, chat_id: int):
    """Отправляет сообщение в указанный чат"""
    try:
        # Получаем parse_mode из исходного сообщения, если он есть
        parse_mode = getattr(source_message, 'parse_mode', None)

        if source_message.text:
            await context.bot.send_message(
                chat_id=chat_id,
                text=source_message.text,
                parse_mode=parse_mode,
                reply_markup=source_message.reply_markup
            )
        elif source_message.photo:
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=source_message.photo[-1].file_id,
                caption=source_message.caption,
                parse_mode=parse_mode,
                reply_markup=source_message.reply_markup
            )
        elif source_message.video:
            await context.bot.send_video(
                chat_id=chat_id,
                video=source_message.video.file_id,
                caption=source_message.caption,
                parse_mode=parse_mode,
                reply_markup=source_message.reply_markup
            )
        elif source_message.document:
            await context.bot.send_document(
                chat_id=chat_id,
                document=source_message.document.file_id,
                caption=source_message.caption,
                parse_mode=parse_mode,
                reply_markup=source_message.reply_markup
            )
        else:
            logger.warning(f"Неизвестный тип сообщения для чата {chat_id}")
    except Exception as e:
        raise e