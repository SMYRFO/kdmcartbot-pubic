# handlers/__init__.py
try:
    from .start import start, send_main_menu
except ImportError as e:
    print(f"Warning: Could not import from start: {e}")

try:
    from .collection import (my_collection, show_collection_page, handle_collection_nav, show_full_collection_excel,
                             show_main_profile)
except ImportError as e:
    print(f"Warning: Could not import from collection: {e}")

try:
    from .shop import (shop_command, show_main_shop, show_cases_shop, show_bonuses_shop, show_coins_shop, buy_bonus,
                       buy_case, cancel_coin_purchase, handle_payment_screenshot, handle_coin_amount_input)
except ImportError as e:
    print(f"Warning: Could not import from shop: {e}")

try:
    from .balance import balance_command, show_balance, check_subscription
except ImportError as e:
    print(f"Warning: Could not import from balance: {e}")

try:
    from .gift import gift_command, show_gift_menu, handle_gift_coins, handle_gift_card, select_card_for_gift, process_gift
except ImportError as e:
    print(f"Warning: Could not import from gift: {e}")

try:
    from .support import (
        support_command, handle_support_request, handle_support_message,
        process_support_text, process_support_photo, process_support_video,
        send_text_support_to_admin, send_media_support_to_admins, send_support_to_admins,
        done_support_command, cancel_support_command, handle_faq,
        handle_admin_response, reply_command, admins_command,
        add_admin_command, remove_admin_command, accept_payment_command, reject_payment_command, list_payments_command
)
except ImportError as e:
    print(f"Warning: Could not import from support: {e}")

try:
    from .admin import is_admin, send_to_all_admins
except ImportError as e:
    print(f"Warning: Could not import from admin: {e}")

try:
    from .trade import trade_command, show_trade_menu, select_rarity_for_trade, confirm_trade, cancel_trade, setup_trade_handlers
except ImportError as e:
    print(f"Warning: Could not import from trade: {e}")

try:
    from .idgetter import (
        track_chat,
        new_post_command, new_post_all_command, new_post_chats_command,
        new_post_users_command, confirm_broadcast_command, cancel_broadcast_command,
    )
except ImportError as e:
    print(f"Warning: Could not import from idgetter: {e}")


__all__ = [
    'start', 'send_main_menu',
    'my_collection', 'show_collection_page', 'handle_collection_nav', 'show_full_collection_excel',
    'shop_command', 'show_main_shop', 'buy_case',
    'balance_command', 'show_balance', 'check_subscription',
    'gift_command', 'show_gift_menu', 'handle_gift_coins', 'handle_gift_card',
    'select_card_for_gift', 'process_gift',
    'support_command', 'handle_support_request', 'handle_support_message',
    'process_support_text', 'process_support_photo', 'process_support_video',
    'send_text_support_to_admin', 'send_media_support_to_admins', 'send_support_to_admins',
    'done_support_command', 'cancel_support_command', 'handle_faq',
    'handle_admin_response', 'reply_command', 'admins_command',
    'add_admin_command', 'remove_admin_command',
    'is_admin', 'send_to_all_admins',
    'trade_command', 'show_trade_menu', 'select_rarity_for_trade',
    'confirm_trade', 'cancel_trade', 'setup_trade_handlers',
    'show_cases_shop', 'show_bonuses_shop', 'show_coins_shop', 'buy_bonus', 'show_main_profile',
    'accept_payment_command', 'reject_payment_command', 'list_payments_command', 'cancel_coin_purchase',
    'handle_coin_amount_input', 'handle_payment_screenshot', 'track_chat',
    'new_post_command', 'new_post_all_command', 'new_post_chats_command',
    'new_post_users_command', 'confirm_broadcast_command', 'cancel_broadcast_command',
    'setup_id_getter_handlers'
]
