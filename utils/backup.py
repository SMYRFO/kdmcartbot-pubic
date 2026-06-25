import os
import shutil
import time
import threading
from datetime import datetime
from config import DB_PATH, BACKUP_DIR, BACKUP_INTERVAL
import logging

logger = logging.getLogger(__name__)

def ensure_backup_dir_exists():
    """Создает директорию для резервных копий если не существует"""
    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)

def create_backup():
    """Создает резервную копию базы данных"""
    try:
        ensure_backup_dir_exists()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = os.path.join(BACKUP_DIR, f"bot_db_backup_{timestamp}.db")

        if os.path.exists(DB_PATH):
            shutil.copyfile(DB_PATH, backup_name)
            logger.info(f"Создана резервная копия: {backup_name}")

            # Удаляем старые резервные копии (оставляем последние 24)
            backups = sorted([f for f in os.listdir(BACKUP_DIR) if f.startswith("bot_db_backup_")])
            if len(backups) > 24:
                for old_backup in backups[:-24]:
                    os.remove(os.path.join(BACKUP_DIR, old_backup))
                    logger.info(f"Удалена старая резервная копия: {old_backup}")
        else:
            logger.warning("Файл базы данных не найден для создания резервной копии")
    except Exception as e:
        logger.error(f"Ошибка при создании резервной копии: {e}")

def schedule_backups():
    """Планировщик резервных копий"""
    while True:
        create_backup()
        time.sleep(BACKUP_INTERVAL)

def start_backup_scheduler():
    """Запускает планировщик резервных копий в отдельном потоке"""
    thread = threading.Thread(target=schedule_backups, daemon=True)
    thread.start()
    logger.info("Запущен планировщик резервных копий (каждый час)")