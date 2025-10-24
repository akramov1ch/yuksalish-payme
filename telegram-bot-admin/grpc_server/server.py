import grpc
from concurrent import futures
import logging
from generated import bot_admin_pb2, bot_admin_pb2_grpc
from database import db
from config import settings
from google.protobuf import empty_pb2

logger = logging.getLogger(__name__)

class BotAdminService(bot_admin_pb2_grpc.BotAdminServiceServicer):
    def __init__(self, bot_instance):
        self.bot = bot_instance

    def NotifyPaymentSuccess(self, request, context):
        # Diagnostika uchun kelgan ma'lumotni to'liq logga chiqarish
        logger.info(f"To'lov haqida gRPC xabarnomasi keldi: {request}")
        
        # Xabar matnini yangi maydonlar bilan formatlash
        message = (
            f"💸 *Yangi To'lov!*\n\n"
            f"👤 *O'quvchi:* {request.student_name}\n"
            f"🆔 *ID:* `{request.account_id}`\n"
            f"📄 *Shartnoma №:* `{request.contract_number}`\n"
            f"🏢 *Filial:* {request.branch_name}\n"
            f"👨‍🏫 *Guruh:* {request.group_name}\n"
            f"💰 *Summa:* {request.amount:,} so'm\n"
            f"⏰ *Vaqt:* {request.payment_time}"
        ).replace(',', ' ')

        admin_ids = db.get_all_admins()
        if self.bot:
            for admin_id in admin_ids:
                try:
                    self.bot.send_message(chat_id=admin_id, text=message, parse_mode='Markdown')
                except Exception as e:
                    logger.error(f"{admin_id} ga xabar yuborishda xatolik: {e}")
        
        return empty_pb2.Empty()

def serve(bot_instance):
    """Botning gRPC serverini ishga tushiradi."""
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    bot_admin_pb2_grpc.add_BotAdminServiceServicer_to_server(
        BotAdminService(bot_instance), server
    )
    port = settings.grpc_bot_server_port
    server.add_insecure_port(f'[::]:{port}')
    server.start()
    logger.info(f"gRPC server {port}-portda ishga tushdi.")
    server.wait_for_termination()