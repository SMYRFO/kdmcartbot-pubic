import logging
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters
)
from handlers.fight import fight_command, setup_fight_handlers, find_opponent
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from utils.logging import setup_logging
from utils.backup import start_backup_scheduler
from database import init_db
from handlers.collection import handle_page_collection
from handlers import (
    start, send_main_menu, my_collection, shop_command, balance_command, gift_command,
    support_command, handle_support_request, handle_support_message,
    process_support_text, process_support_photo, process_support_video,
    done_support_command, cancel_support_command, handle_faq,
    handle_admin_response, reply_command, admins_command,
    add_admin_command, remove_admin_command, check_subscription,
    show_main_shop, buy_case, show_balance, show_gift_menu, handle_gift_coins,
    handle_gift_card, select_card_for_gift, process_gift,
    handle_collection_nav, show_full_collection_excel,
    trade_command, setup_trade_handlers, show_trade_menu, show_cases_shop,
    show_bonuses_shop, show_coins_shop, buy_bonus, show_main_profile,
    accept_payment_command, reject_payment_command, list_payments_command, cancel_coin_purchase,
    handle_coin_amount_input, handle_payment_screenshot,
    new_post_command, new_post_all_command, new_post_chats_command,
    new_post_users_command, confirm_broadcast_command, cancel_broadcast_command, track_chat
)
from config import BOT_TOKEN

# Настройка логирования
logger = setup_logging()


def main():
    # Создаем папку для резервных копий
    from utils.backup import ensure_backup_dir_exists
    ensure_backup_dir_exists()

    # Запускаем планировщик резервных копий
    start_backup_scheduler()

    # Инициализируем базу данных
    init_db()

    # Создаем приложение
    application = Application.builder().token(BOT_TOKEN).build()

    # ОБРАБОТЧИКИ КОМАНД
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("my", my_collection))
    application.add_handler(CommandHandler("shop", shop_command))
    application.add_handler(CommandHandler("balance", balance_command))
    application.add_handler(CommandHandler("gift", gift_command))
    application.add_handler(CommandHandler("check", check_subscription))
    application.add_handler(CommandHandler("support", support_command))
    application.add_handler(CommandHandler("cancel", cancel_support_command))
    application.add_handler(CommandHandler("done", done_support_command))
    application.add_handler(CommandHandler("reply", reply_command))
    application.add_handler(CommandHandler("admins", admins_command))
    application.add_handler(CommandHandler("addadmin", add_admin_command))
    application.add_handler(CommandHandler("removeadmin", remove_admin_command))
    application.add_handler(CommandHandler("fight", fight_command))
    application.add_handler(CommandHandler("trade", trade_command))
    application.add_handler(CommandHandler("accept_pay", accept_payment_command))
    application.add_handler(CommandHandler("reject_pay", reject_payment_command))
    application.add_handler(CommandHandler("list_payments", list_payments_command))
    application.add_handler(CommandHandler("newpost", new_post_command))
    application.add_handler(CommandHandler("newpostall", new_post_all_command))
    application.add_handler(CommandHandler("newpostchats", new_post_chats_command))
    application.add_handler(CommandHandler("newpostusers", new_post_users_command))
    application.add_handler(CommandHandler("confirmbroadcast", confirm_broadcast_command))
    application.add_handler(CommandHandler("cancelbroadcast", cancel_broadcast_command))

    setup_fight_handlers(application)
    setup_trade_handlers(application)


    # ОБРАБОТЧИКИ CALLBACK QUERY
    application.add_handler(CallbackQueryHandler(handle_collection_nav, pattern=r'^collection_(prev|next)_\d+$'))

    # Универсальный обработчик кнопок
    application.add_handler(CallbackQueryHandler(handle_page_collection, pattern="^page_collection$"))
    application.add_handler(CallbackQueryHandler(cancel_coin_purchase, pattern='^cancel_coin_purchase$'))
    application.add_handler(CallbackQueryHandler(show_full_collection_excel, pattern="^full_collection$"))
    application.add_handler(CallbackQueryHandler(handle_collection_nav, pattern="^collection_(prev|next)_"))
    # В main.py замените функцию button_handler на эту:

    # В функции button_handler добавьте обработку новых callback'ов:
    async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()

        try:
            data = query.data

            if data == 'collection':
                await my_collection(update, context)
            elif data == 'shop':
                await show_main_shop(update, context)
            elif data == 'balance':
                await show_balance(update, context)
            elif data.startswith('buy_case_'):
                await buy_case(update, context)
            elif data == 'gift_menu':
                await show_gift_menu(update, context)
            elif data == 'gift_coins':
                await handle_gift_coins(update, context)
            elif data == 'gift_card':
                await handle_gift_card(update, context)
            elif data.startswith('select_card_'):
                await select_card_for_gift(update, context)
            elif data == 'main_menu':
                await send_main_menu(update, context)
            elif data == 'support':
                await support_command(update, context)
            elif data == 'write_to_support':
                await handle_support_request(update, context)
            elif data == 'faq':
                await handle_faq(update, context)
            elif data == 'fight_menu':
                await fight_command(update, context)
            elif data == 'trade_menu':
                await show_trade_menu(update, context)
            elif data == 'show_main_profile':
                await show_main_profile(update, context)
            elif data.startswith('select_card_trade'):
                from handlers.trade import select_card_for_trade
                await select_card_for_trade(update, context)
            elif data.startswith('select_qty_'):
                from handlers.trade import select_quantity_for_trade
                await select_quantity_for_trade(update, context)
            elif data.startswith('finish_selection_'):
                from handlers.trade import finish_selection
                await finish_selection(update, context)
            elif data.startswith('reset_selection_'):
                from handlers.trade import reset_selection
                await reset_selection(update, context)
            # Новые обработчики для магазина
            elif data == 'shop_main':
                await show_main_shop(update, context)
            elif data == 'shop_cases':
                await show_cases_shop(update, context)
            elif data == 'shop_bonuses':
                await show_bonuses_shop(update, context)
            elif data == 'shop_coins':
                await show_coins_shop(update, context)
            elif data.startswith('buy_bonus_'):
                await buy_bonus(update, context)

        except Exception as e:
            logger.error(
                f"Error in button handler for data='{getattr(update.callback_query, 'data', None)}': {e}",
                exc_info=True
            )
            try:
                chat_id = None
                if hasattr(query, 'message') and query.message:
                    chat_id = query.message.chat_id
                elif hasattr(update, 'effective_chat') and update.effective_chat:
                    chat_id = update.effective_chat.id

                if chat_id:
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text="❌ Произошла ошибка. Пожалуйста, попробуйте снова или используйте /start"
                    )
            except Exception as send_error:
                logger.error(f"Couldn't send error message: {send_error}")
    application.add_handler(CallbackQueryHandler(button_handler))

    # ОБРАБОТЧИКИ СООБЩЕНИЙ ДЛЯ ПОДДЕРЖКИ
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_support_message
    ), group=0)  # Группа 0 - высший приоритет

    application.add_handler(MessageHandler(
        filters.PHOTO & ~filters.COMMAND,
        handle_support_message
    ), group=0)

    application.add_handler(MessageHandler(
        filters.VIDEO & ~filters.COMMAND,
        handle_support_message
    ), group=0)

    # ОБРАБОТЧИК ДЛЯ ПОДАРКОВ (НИЖЕ ПРИОРИТЕТ)
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        process_gift
    ), group=1)

    # обработчик для платежей
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_coin_amount_input
    ), group=2)

    application.add_handler(MessageHandler(
        filters.PHOTO & ~filters.COMMAND,
        handle_payment_screenshot
    ), group=2)

    # УНИВЕРСАЛЬНЫЙ ОБРАБОТЧИК ОТСЛЕЖИВАНИЯ ЧАТОВ (САМЫЙ НИЗКИЙ ПРИОРИТЕТ)
    application.add_handler(MessageHandler(
        filters.ALL,
        track_chat
    ), group=4)

    # ОБРАБОТЧИК ДЛЯ ГРУПП
    async def handle_group_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.message.text and ('/start' in update.message.text or context.bot.username in update.message.text):
            await start(update, context)

    application.add_handler(MessageHandler(
        filters.TEXT & filters.ChatType.GROUPS & (filters.Entity("mention") | filters.Entity("text_mention")),
        handle_group_message
    ), group=3)

    # Функция для установки подсказок команд
    async def post_init(application: Application):
        await application.bot.set_my_commands([
            ("start", "Начать работу с ботом"),
            ("my", "Моя коллекция карточек"),
            ("shop", "Меню магазинов"),
            ("balance", "Мой баланс"),
            ("gift", "Меню подарков"),
            ("check", "Проверить подписку и получить награду"),
            ("support", "Обратиться в поддержку"),
            ("fight", "Меню битв"),
            ("trade", "Меню обмена карточек")
        ])
        logger.info("Бот запущен и готов к работе!")

    # Периодическая очистка устаревших сообщений
    async def periodic_cleanup(context: ContextTypes.DEFAULT_TYPE):
        from utils.helpers import cleanup_old_messages
        cleanup_old_messages()

    # Запускаем периодическую задачу очистки
    application.job_queue.run_repeating(
        periodic_cleanup,
        interval=600,
        first=10
    )

    # Устанавливаем post_init функцию
    application.post_init = post_init

    logger.info("Запуск бота...")
    try:
        application.run_polling(
            poll_interval=1.0,
            timeout=30,
            drop_pending_updates=True
        )
    except Exception as e:
        logger.critical(f"Критическая ошибка при запуске бота: {e}")
        raise


if __name__ == '__main__':
    main()