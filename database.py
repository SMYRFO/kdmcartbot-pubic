import sqlite3
import logging
from config import DB_PATH

logger = logging.getLogger(__name__)

# database.py - исправьте функцию execute_query

def execute_query(query, params=(), fetch_one=False, fetch_all=False, lastrowid=False):
    """Универсальная функция для выполнения запросов"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(query, params)

        if fetch_one:
            result = cursor.fetchone()
            result = dict(result) if result else None
        elif fetch_all:
            result = [dict(row) for row in cursor.fetchall()]
        elif lastrowid:
            result = cursor.lastrowid  # Возвращаем ID последней вставленной записи
        else:
            result = None

        conn.commit()
        conn.close()
        return result
    except Exception as e:
        logger.error(f"Ошибка выполнения запроса: {e}")
        return None

def init_db():
    """Инициализирует структуру базы данных"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Таблица пользователей
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                coins INTEGER DEFAULT 0,
                last_coin_time TEXT,
                last_reward_date TEXT
            )
        ''')

        # Таблица карточек
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cards (
                card_id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                rarity TEXT,
                image_url TEXT
            )
        ''')

        # Таблица кейсов
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cases (
                case_id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                price INTEGER
            )
        ''')

        # Таблица содержимого кейсов
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS case_contents (
                case_id INTEGER,
                card_id INTEGER,
                FOREIGN KEY (case_id) REFERENCES cases (case_id),
                FOREIGN KEY (card_id) REFERENCES cards (card_id),
                PRIMARY KEY (case_id, card_id)
            )
        ''')

        # Таблица коллекций пользователей
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS collections (
                user_id INTEGER,
                card_id INTEGER,
                quantity INTEGER DEFAULT 1,
                obtained_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id),
                FOREIGN KEY (card_id) REFERENCES cards (card_id),
                PRIMARY KEY (user_id, card_id)
            )
        ''')

        conn.commit()
        conn.close()
        logger.info("База данных инициализирована")
    except Exception as e:
        logger.error(f"Ошибка инициализации базы данных: {e}")

# Функции для работы с пользователями
def get_user(user_id):
    return execute_query(
        "SELECT * FROM users WHERE user_id = ?",
        (user_id,),
        fetch_one=True
    )


def add_user(user_id, username):
    try:
        # Сначала проверяем, существует ли пользователь
        existing_user = get_user(user_id)

        if existing_user:
            # Если пользователь существует и имя изменилось - обновляем
            if existing_user.get('username') != username:
                execute_query(
                    "UPDATE users SET username = ? WHERE user_id = ?",
                    (username, user_id)
                )
                logger.info(f"Обновлен username пользователя {user_id}: {username}")
            return True
        else:
            # Если пользователя нет - создаем нового
            execute_query(
                "INSERT INTO users (user_id, username, coins) VALUES (?, ?, 0)",
                (user_id, username)
            )
            logger.info(f"Добавлен новый пользователь: {user_id}, {username}")
            return True
    except Exception as e:
        logger.error(f"Ошибка добавления/обновления пользователя: {e}")
        return False


def update_user(user_id, updates):
    try:
        set_clause = ', '.join([f"{key} = ?" for key in updates.keys()])
        values = list(updates.values()) + [user_id]
        execute_query(
            f"UPDATE users SET {set_clause} WHERE user_id = ?",
            values
        )
        return True
    except Exception as e:
        logger.error(f"Ошибка обновления пользователя: {e}")
        return False

def get_user_by_username(username):
    return execute_query(
        "SELECT * FROM users WHERE username = ?",
        (username,),
        fetch_one=True
    )

# Функции для работы с коллекциями
def get_user_collection(user_id):
    return execute_query('''
        SELECT c.card_id, c.name, c.rarity, c.image_url, col.quantity
        FROM collections col
        JOIN cards c ON col.card_id = c.card_id
        WHERE col.user_id = ? AND col.quantity > 0
        ORDER BY c.rarity DESC, c.name
    ''', (user_id,), fetch_all=True) or []

def add_to_collection(user_id, card_id):
    try:
        # Сначала проверяем, есть ли уже такая карточка у пользователя
        existing = execute_query(
            "SELECT quantity FROM collections WHERE user_id = ? AND card_id = ?",
            (user_id, card_id),
            fetch_one=True
        )

        if existing:
            # Если карточка уже есть - увеличиваем количество
            execute_query(
                "UPDATE collections SET quantity = quantity + 1 WHERE user_id = ? AND card_id = ?",
                (user_id, card_id)
            )
        else:
            # Если карточки нет - создаем новую запись
            execute_query(
                "INSERT INTO collections (user_id, card_id, quantity) VALUES (?, ?, 1)",
                (user_id, card_id)
            )
        return True
    except Exception as e:
        logger.error(f"Ошибка добавления в коллекцию: {e}")
        return False# Функции для работы с кейсами
def get_cases():
    return execute_query("SELECT * FROM cases ORDER BY case_id", fetch_all=True) or []

def get_case_contents(case_id):
    result = execute_query(
        "SELECT card_id FROM case_contents WHERE case_id = ?",
        (case_id,),
        fetch_all=True
    )
    return [item['card_id'] for item in result] if result else []

# Функции для работы с карточками
def get_cards():
    return execute_query("SELECT * FROM cards", fetch_all=True) or []

def get_card(card_id):
    return execute_query(
        "SELECT * FROM cards WHERE card_id = ?",
        (card_id,),
        fetch_one=True
    )

# Функции для передачи предметов
def transfer_card(sender_id, receiver_id, card_id):
    """Передает карточку от отправителя получателю"""
    try:
        # Проверяем, есть ли карточка у отправителя
        sender_quantity = execute_query(
            "SELECT quantity FROM collections WHERE user_id = ? AND card_id = ?",
            (sender_id, card_id),
            fetch_one=True
        )

        if not sender_quantity or sender_quantity['quantity'] < 1:
            return False

        # Уменьшаем количество у отправителя
        execute_query(
            "UPDATE collections SET quantity = quantity - 1 WHERE user_id = ? AND card_id = ?",
            (sender_id, card_id)
        )

        # Удаляем запись, если количество стало 0
        execute_query(
            "DELETE FROM collections WHERE user_id = ? AND card_id = ? AND quantity = 0",
            (sender_id, card_id)
        )

        # Добавляем карточку получателю
        # Сначала проверяем, есть ли уже такая карточка у получателя
        receiver_quantity = execute_query(
            "SELECT quantity FROM collections WHERE user_id = ? AND card_id = ?",
            (receiver_id, card_id),
            fetch_one=True
        )

        if receiver_quantity:
            # Если есть - увеличиваем количество
            execute_query(
                "UPDATE collections SET quantity = quantity + 1 WHERE user_id = ? AND card_id = ?",
                (receiver_id, card_id)
            )
        else:
            # Если нет - создаем новую запись
            execute_query(
                "INSERT INTO collections (user_id, card_id, quantity) VALUES (?, ?, 1)",
                (receiver_id, card_id)
            )

        return True

    except Exception as e:
        logger.error(f"Ошибка передачи карточки: {e}")
        return False


def transfer_coins(sender_id, receiver_id, amount):
    try:
        sender = get_user(sender_id)
        if not sender or sender['coins'] < amount:
            return False

        execute_query(
            "UPDATE users SET coins = coins - ? WHERE user_id = ?",
            (amount, sender_id)
        )
        execute_query(
            "UPDATE users SET coins = coins + ? WHERE user_id = ?",
            (amount, receiver_id)
        )
        return True
    except Exception as e:
        logger.error(f"Ошибка передачи монет: {e}")
        return False

def can_gift_card(sender_id, card_id):
    result = execute_query(
        "SELECT quantity FROM collections WHERE user_id = ? AND card_id = ?",
        (sender_id, card_id),
        fetch_one=True
    )
    return result and result['quantity'] >= 1

def can_gift_coins(sender_id, amount):
    user = get_user(sender_id)
    return user and user.get('coins', 0) >= amount

# Добавьте эти функции в конец файла database.py

# Функции для истории боев
def add_battle_history(winner_id, loser_id, winner_card_id, loser_card_id, rounds, winner_health):
    """Добавляет запись о бое в историю"""
    try:
        execute_query('''
            INSERT INTO battle_history 
            (winner_id, loser_id, winner_card_id, loser_card_id, rounds, winner_health, battle_date)
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ''', (winner_id, loser_id, winner_card_id, loser_card_id, rounds, winner_health))
        return True
    except Exception as e:
        logger.error(f"Ошибка добавления истории боя: {e}")
        return False

def get_battle_stats(user_id: int) -> dict:
    """Возвращает статистику боев пользователя"""
    try:
        # Статистика побед и поражений
        wins = execute_query(
            "SELECT COUNT(*) as count FROM battle_history WHERE winner_id = ?",
            (user_id,),
            fetch_one=True
        )['count'] or 0

        losses = execute_query(
            "SELECT COUNT(*) as count FROM battle_history WHERE loser_id = ?",
            (user_id,),
            fetch_one=True
        )['count'] or 0

        total = wins + losses
        win_rate = round((wins / total * 100), 2) if total > 0 else 0

        # Последние бои
        recent_battles = execute_query('''
            SELECT 
                bh.*,
                CASE WHEN bh.winner_id = ? THEN 'win' ELSE 'loss' END as result,
                CASE WHEN bh.winner_id = ? THEN u2.username ELSE u1.username END as opponent
            FROM battle_history bh
            LEFT JOIN users u1 ON bh.winner_id = u1.user_id
            LEFT JOIN users u2 ON bh.loser_id = u2.user_id
            WHERE bh.winner_id = ? OR bh.loser_id = ?
            ORDER BY bh.battle_date DESC
            LIMIT 5
        ''', (user_id, user_id, user_id, user_id), fetch_all=True) or []

        formatted_battles = []
        for battle in recent_battles:
            formatted_battles.append({
                'is_win': battle['result'] == 'win',
                'opponent': battle['opponent'] or 'Неизвестный',
                'rounds': battle['rounds']
            })

        return {
            'wins': wins,
            'losses': losses,
            'total': total,
            'win_rate': win_rate,
            'recent_battles': formatted_battles
        }

    except Exception as e:
        logger.error(f"Ошибка получения статистики боев: {e}")
        return {
            'wins': 0,
            'losses': 0,
            'total': 0,
            'win_rate': 0,
            'recent_battles': []
        }
def update_collection(user_id: int, card_id: int, quantity: int) -> bool:
    """Обновляет количество карточки в коллекции пользователя"""
    try:
        if quantity <= 0:
            # Удаляем запись если количество 0 или меньше
            execute_query(
                "DELETE FROM collections WHERE user_id = ? AND card_id = ?",
                (user_id, card_id)
            )
        else:
            # Обновляем или добавляем запись
            execute_query(
                """INSERT OR REPLACE INTO collections (user_id, card_id, quantity)
                   VALUES (?, ?, ?)""",
                (user_id, card_id, quantity)
            )
        return True
    except Exception as e:
        logger.error(f"Ошибка обновления коллекции: {e}")
        return False


# Добавим функции для работы с бонусами:
def get_bonuses():
    """Получает все доступные бонусы"""
    return execute_query("SELECT * FROM bonuses ORDER BY bonus_id", fetch_all=True) or []



def add_user_bonus(user_id, bonus_id, quantity=1):
    """Добавляет бонус пользователю"""
    try:
        execute_query('''
            INSERT INTO user_bonuses (user_id, bonus_id, quantity)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id, bonus_id) 
            DO UPDATE SET quantity = quantity + ?
        ''', (user_id, bonus_id, quantity, quantity))
        return True
    except Exception as e:
        logger.error(f"Ошибка добавления бонуса: {e}")
        return False


def get_user_bonuses(user_id: int) -> list:
    """Получает бонусы пользователя"""
    query = """
        SELECT ub.bonus_id, b.name, b.description, b.effect_type, b.effect_value, ub.quantity
        FROM user_bonuses ub
        JOIN bonuses b ON ub.bonus_id = b.bonus_id
        WHERE ub.user_id = ? AND ub.quantity > 0
        ORDER BY b.name
    """
    result = execute_query(query, (user_id,), fetch_all=True)
    return result if result else []


def use_user_bonus(user_id: int, bonus_id: int) -> bool:
    """Использует один бонус пользователя"""
    query = """
        UPDATE user_bonuses 
        SET quantity = quantity - 1 
        WHERE user_id = ? AND bonus_id = ? AND quantity > 0
    """
    result = execute_query(query, (user_id, bonus_id))
    return result is not None

def create_payment(user_id: int, amount_rub: float, amount_coins: int, screenshot_url: str = None) -> int:
    """Создает запись о платеже и возвращает ID"""
    query = """
        INSERT INTO payments (user_id, amount_rub, amount_coins, screenshot_url)
        VALUES (?, ?, ?, ?)
    """
    result = execute_query(
        query,
        (user_id, amount_rub, amount_coins, screenshot_url),
        lastrowid=True  # Указываем, что нужно вернуть lastrowid
    )
    return result


def get_payment(payment_id: int):
    """Получает информацию о платеже"""
    return execute_query(
        "SELECT * FROM payments WHERE payment_id = ?",
        (payment_id,),
        fetch_one=True
    )

def get_pending_payments():
    """Получает все ожидающие платежи"""
    return execute_query(
        "SELECT * FROM payments WHERE status = 'pending' ORDER BY created_at DESC",
        fetch_all=True
    )

def update_payment_status(payment_id: int, status: str, admin_id: int = None):
    """Обновляет статус платежа"""
    query = """
        UPDATE payments 
        SET status = ?, processed_at = CURRENT_TIMESTAMP, admin_id = ?
        WHERE payment_id = ?
    """
    return execute_query(query, (status, admin_id, payment_id))

def get_user_payments(user_id: int):
    """Получает платежи пользователя"""
    return execute_query(
        "SELECT * FROM payments WHERE user_id = ? ORDER BY created_at DESC",
        (user_id,),
        fetch_all=True
    )