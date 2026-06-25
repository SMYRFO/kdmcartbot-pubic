import os
from datetime import timedelta

# Конфигурация бота
BOT_TOKEN = "TOKEN"
ADMINS = [7167893112, 551769460]
CHANNEL_ID = "@kdm_shop"

# Конфигурация базы данных
DB_PATH = 'bot_database.db'
BACKUP_DIR = "backups"
BACKUP_INTERVAL = 3600 * 6  # 1 час

COIN_PRICE = 0.2  # 1 рубль = 5 монет (1/5 = 0.2 рубля за монету)
PAYMENT_CARD = "2200248002704939"  # Номер карты для оплаты
PAYMENT_RECEIVER = "Иван Иванов"    # Получатель платежа

# Статусы платежей
PAYMENT_STATUS_PENDING = "pending"
PAYMENT_STATUS_APPROVED = "approved"
PAYMENT_STATUS_REJECTED = "rejected"

# Настройки времени
COIN_COOLDOWN = timedelta(hours=3)
REWARD_COOLDOWN = timedelta(days=1)

# Эмодзи для редкостей
RARITY_DISPLAY = {
    5: "🖤 Эксклюзивный",
    4: "💛 Легендарный",
    3: "❤️‍🔥 Мифический",
    2: "💜 Эпический",
    1: "💙 Супер редкий",
    0: "🤍 Редкий"
}

RARITY_ORDER = {
    "🖤 Эксклюзивный": 5,
    "💛 Легендарный": 4,
    "❤️‍🔥 Мифический": 3,
    "💜 Эпический": 2,
    "💙 Супер редкий": 1,
    "🤍 Редкий": 0
}
