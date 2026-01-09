import grpc
from concurrent import futures
import logging
from generated import bot_admin_pb2, bot_admin_pb2_grpc
from database import db
from config import settings
from google.protobuf import empty_pb2
import html  # <--- Muhim: HTML kutubxonasi qo'shildi

logger = logging.getLogger(__name__)

class BotAdminService(bot_admin_pb2_grpc.BotAdminServiceServicer):
    def __init__(self, bot_instance):
        self.bot = bot_instance

    def NotifyPaymentSuccess(self, request, context):
        logger.info(f"To'lov haqida gRPC xabarnomasi keldi: {request}")
        
        # Summani formatlash (tiyindan so'mga o'tkazish va probel qo'shish)
        amount_in_som = request.amount / 100
        formatted_amount = f"{amount_in_som:,.2f}".replace(',', ' ').replace('.', ',')

        # HTML formatida xatolik bo'lmasligi uchun maxsus belgilarni zararsizlantiramiz
        # Masalan: <, >, &, " va ' belgilari
        safe_student_name = html.escape(request.student_name)
        safe_branch_name = html.escape(request.branch_name)
        safe_group_name = html.escape(request.group_name)
        safe_contract = html.escape(request.contract_number)
        safe_account_id = html.escape(request.account_id)

        # Xabarni HTML formatida tayyorlaymiz
        # <b> - qalin yozuv
        # <code> - nusxalash uchun qulay format (monospaced)
        message = (
            f"💸 <b>Yangi To'lov!</b>\n\n"
            f"👤 <b>O'quvchi:</b> {safe_student_name}\n"
            f"🆔 <b>ID:</b> <code>{safe_account_id}</code>\n"
            f"📄 <b>Shartnoma №:</b> <code>{safe_contract}</code>\n"
            f"🏢 <b>Filial:</b> {safe_branch_name}\n"
            f"👨‍🏫 <b>Guruh:</b> {safe_group_name}\n"
            f"💰 <b>Summa:</b> {formatted_amount} so'm\n"
            f"⏰ <b>Vaqt:</b> {request.payment_time}"
        )

        target_group_id = settings.telegram_payment_group_id
        
        if self.bot and target_group_id:
            try:
                # Agar topic_id 0 bo'lsa, umumiy chatga, aks holda topicga boradi
                thread_id = request.topic_id if request.topic_id > 0 else None
                
                self.bot.send_message(
                    chat_id=target_group_id, 
                    text=message, 
                    parse_mode='HTML',  # <--- O'ZGARISH: Markdown o'rniga HTML
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