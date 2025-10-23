import logging
from concurrent.futures import ThreadPoolExecutor
from database import db
from config import settings
from grpc_server import server as grpc_server
from bot import core as bot_core

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def initialize_database():
    """Ma'lumotlar bazasini va super adminni sozlaydi."""
    db.init_db()
    if not db.is_admin(settings.super_admin_id):
        db.add_admin(settings.super_admin_id)
        logger.info(f"Super admin {settings.super_admin_id} bazaga qo'shildi.")

if __name__ == '__main__':
    initialize_database()

    bot_instance, bot_idle_func = bot_core.run_bot()
    
    logger.info("Telegram bot ishga tushdi...")

    with ThreadPoolExecutor(max_workers=2) as executor:
        executor.submit(grpc_server.serve, bot_instance)
        
        bot_idle_func()