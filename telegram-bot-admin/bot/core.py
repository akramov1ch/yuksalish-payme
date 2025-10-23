from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, ConversationHandler
from config import settings
from .handlers import (
    start, cancel,
    
    list_branches, add_branch_start, get_branch_name, get_branch_fee,
    get_branch_mfo, get_branch_account, get_branch_merchant,
    delete_branch_start, get_branch_to_delete, confirm_branch_delete,

    list_students, add_student_start, 
    get_student_branch, get_student_parent_name, get_student_full_name,
    get_student_group_name, get_student_phone, get_student_discount,
    delete_student_start, get_student_account_id_to_delete,

    manage_admins, add_admin_command, remove_admin_command,

    upload_students_start, process_excel_file,
)

(BRANCH_NAME, BRANCH_FEE, BRANCH_MFO, BRANCH_ACC, BRANCH_MERCHANT) = range(5)
(
    STUDENT_BRANCH, STUDENT_PARENT, STUDENT_FULLNAME,
    STUDENT_GROUP_NAME, STUDENT_PHONE, STUDENT_DISCOUNT
) = range(5, 11)
(DELETE_STUDENT_ACCOUNT_ID) = range(11, 12)
(DELETE_BRANCH_SELECT, DELETE_BRANCH_CONFIRM) = range(12, 14)
PROCESSING_EXCEL_FILE = range(14, 15)


def run_bot():
    updater = Updater(settings.telegram_bot_token, use_context=True)
    dispatcher = updater.dispatcher

    common_fallbacks = [
        CommandHandler('cancel', cancel),
        MessageHandler(Filters.regex('^⬅️ Orqaga'), cancel)
    ]

    add_branch_conv = ConversationHandler(
        entry_points=[MessageHandler(Filters.regex('^➕ Filial qo\'shish'), add_branch_start)],
        states={
            BRANCH_NAME: [MessageHandler(Filters.text & ~Filters.command, get_branch_name)],
            BRANCH_FEE: [MessageHandler(Filters.text & ~Filters.command, get_branch_fee)],
            BRANCH_MFO: [MessageHandler(Filters.text & ~Filters.command, get_branch_mfo)],
            BRANCH_ACC: [MessageHandler(Filters.text & ~Filters.command, get_branch_account)],
            BRANCH_MERCHANT: [MessageHandler(Filters.text & ~Filters.command, get_branch_merchant)],
        },
        fallbacks=common_fallbacks,
    )

    add_student_conv = ConversationHandler(
        entry_points=[MessageHandler(Filters.regex('^👤 O\'quvchi qo\'shish'), add_student_start)],
        states={
            STUDENT_BRANCH: [MessageHandler(Filters.text & ~Filters.command, get_student_branch)],
            STUDENT_PARENT: [MessageHandler(Filters.text & ~Filters.command, get_student_parent_name)],
            STUDENT_FULLNAME: [MessageHandler(Filters.text & ~Filters.command, get_student_full_name)],
            STUDENT_GROUP_NAME: [MessageHandler(Filters.text & ~Filters.command, get_student_group_name)],
            STUDENT_PHONE: [MessageHandler(Filters.text & ~Filters.command, get_student_phone)],
            STUDENT_DISCOUNT: [MessageHandler(Filters.text & ~Filters.command, get_student_discount)],
        },
        fallbacks=common_fallbacks,
    )

    delete_student_conv = ConversationHandler(
        entry_points=[MessageHandler(Filters.regex('^🗑 O\'quvchini o\'chirish'), delete_student_start)],
        states={
            DELETE_STUDENT_ACCOUNT_ID: [MessageHandler(Filters.text & ~Filters.command, get_student_account_id_to_delete)],
        },
        fallbacks=common_fallbacks,
    )

    delete_branch_conv = ConversationHandler(
        entry_points=[MessageHandler(Filters.regex('^🗑 Filialni o\'chirish'), delete_branch_start)],
        states={
            DELETE_BRANCH_SELECT: [MessageHandler(Filters.text & ~Filters.command, get_branch_to_delete)],
            DELETE_BRANCH_CONFIRM: [MessageHandler(Filters.text & ~Filters.command, confirm_branch_delete)],
        },
        fallbacks=common_fallbacks,
    )

    upload_students_conv = ConversationHandler(
        entry_points=[MessageHandler(Filters.regex('^📤 O\'quvchilarni import qilish'), upload_students_start)],
        states={
            PROCESSING_EXCEL_FILE: [MessageHandler(Filters.document.mime_type("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"), process_excel_file)],
        },
        fallbacks=common_fallbacks,
    )

    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(MessageHandler(Filters.regex('^🏢 Filiallar'), list_branches))
    dispatcher.add_handler(MessageHandler(Filters.regex('^🎓 O\'quvchilar'), list_students))
    dispatcher.add_handler(MessageHandler(Filters.regex('^⚙️ Adminlar'), manage_admins))
    
    dispatcher.add_handler(CommandHandler("add_admin", add_admin_command))
    dispatcher.add_handler(CommandHandler("remove_admin", remove_admin_command))

    dispatcher.add_handler(add_branch_conv)
    dispatcher.add_handler(add_student_conv)
    dispatcher.add_handler(delete_student_conv)
    dispatcher.add_handler(delete_branch_conv)
    dispatcher.add_handler(upload_students_conv)

    updater.start_polling()
    return updater.bot, updater.idle