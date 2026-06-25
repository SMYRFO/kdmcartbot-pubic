import logging
import sys

def setup_logging():
    """Настройка логирования с поддержкой Unicode"""
    # Настраиваем основное логирование
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO,
        handlers=[
            logging.FileHandler('bot_activity.log', encoding='utf-8'),
            logging.StreamHandler(sys.stdout)  # Используем stdout с поддержкой Unicode
        ]
    )

    # Уменьшаем логи HTTP-запросов
    logging.getLogger('httpx').setLevel(logging.WARNING)

    # Уменьшаем логи APScheduler
    logging.getLogger('apscheduler').setLevel(logging.WARNING)
    logging.getLogger('apscheduler.executors.default').setLevel(logging.WARNING)
    logging.getLogger('apscheduler.scheduler').setLevel(logging.WARNING)

    # Уменьшаем логи HTTP-запросов
    logging.getLogger('httpx').setLevel(logging.WARNING)

    return logging.getLogger(__name__)