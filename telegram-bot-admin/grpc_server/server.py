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
        logger.info(f"To'lov haqida gRPC xabarnomasi keldi: {request}")
        
        amount_in_som = request.amount / 100
        formatted_amount = f"{amount_in_som:,.2f}".replace(',', ' ').replace('.', ',')

        # Hashtag (#) olib tashlandi, chunki endi Topic bor
        message = (
            f"💸 *Yangi To'lov!*\n\n"
            f"👤 *O'quvchi:* {request.student_name}\n"
            f"🆔 *ID:* `{request.account_id}`\n"
            f"📄 *Shartnoma №:* `{request.contract_number}`\n"
            f"🏢 *Filial:* {request.branch_name}\n"
            f"👨‍🏫 *Guruh:* {request.group_name}\n"
            f"💰 *Summa:* {formatted_amount} so'm\n"
            f"⏰ *Vaqt:* {request.payment_time}"
        )

        # YANGI MANTIQ: Guruhga yuborish
        target_group_id = settings.telegram_payment_group_id
        
        if self.bot and target_group_id:
            try:
                # Agar topic_id 0 bo'lsa, umumiy chatga, aks holda topicga boradi
                thread_id = request.topic_id if request.topic_id > 0 else None
                
                self.bot.send_message(
                    chat_id=target_group_id, 
                    text=message, 
                    parse_mode='Markdown',
                    message_thread_id=thread_id 
                )
                logger.info(f"Xabar guruhga ({target_group_id}) Topic: {thread_id} yuborildi.")
            except Exception as e:
                logger.error(f"Guruhga xabar yuborishda xatolik: {e}")
        
        return empty_pb2.Empty()

def serve(bot_instance):
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    bot_admin_pb2_grpc.add_BotAdminServiceServicer_to_server(
        BotAdminService(bot_instance), server
    )
    port = settings.grpc_bot_server_port
    server.add_insecure_port(f'[::]:{port}')
    server.start()
    logger.info(f"gRPC server {port}-portda ishga tushdi.")
    server.wait_for_termination()