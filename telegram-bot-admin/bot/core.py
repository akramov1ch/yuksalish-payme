from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, ConversationHandler
from config import settings
from . import handlers
from . import states

def run_bot():
    updater = Updater(settings.telegram_bot_token, use_context=True)
    dispatcher = updater.dispatcher

    common_fallbacks = [
        CommandHandler('cancel', handlers.cancel),
        MessageHandler(Filters.regex('^⬅️ Orqaga'), handlers.cancel)
    ]

    add_branch_conv = ConversationHandler(
        entry_points=[MessageHandler(Filters.regex('^➕ Filial qo\'shish'), handlers.add_branch_start)],
        states={
            states.BRANCH_NAME: [MessageHandler(Filters.text & ~Filters.command, handlers.get_branch_name)],
            states.BRANCH_FEE: [MessageHandler(Filters.text & ~Filters.command, handlers.get_branch_fee)],
            states.BRANCH_MFO: [MessageHandler(Filters.text & ~Filters.command, handlers.get_branch_mfo)],
            states.BRANCH_ACC: [MessageHandler(Filters.text & ~Filters.command, handlers.get_branch_account)],
            states.BRANCH_MERCHANT: [MessageHandler(Filters.text & ~Filters.command, handlers.get_branch_merchant)],
        },
        fallbacks=common_fallbacks,
    )
    add_student_conv = ConversationHandler(
        entry_points=[MessageHandler(Filters.regex('^👤 O\'quvchi qo\'shish'), handlers.add_student_start)],
        states={
            states.STUDENT_BRANCH: [MessageHandler(Filters.text & ~Filters.command, handlers.get_student_branch)],
            states.STUDENT_PARENT: [MessageHandler(Filters.text & ~Filters.command, handlers.get_student_parent_name)],
            states.STUDENT_FULLNAME: [MessageHandler(Filters.text & ~Filters.command, handlers.get_student_full_name)],
            states.STUDENT_GROUP_NAME: [MessageHandler(Filters.text & ~Filters.command, handlers.get_student_group_name)],
            states.STUDENT_PHONE: [MessageHandler(Filters.text & ~Filters.command, handlers.get_student_phone)],
            states.STUDENT_DISCOUNT: [MessageHandler(Filters.text & ~Filters.command, handlers.get_student_discount)],
        },
        fallbacks=common_fallbacks,
    )

    delete_student_conv = ConversationHandler(
        entry_points=[MessageHandler(Filters.regex('^🗑 O\'quvchini o\'chirish'), handlers.delete_student_start)],
        states={
            states.DELETE_STUDENT_ACCOUNT_ID: [MessageHandler(Filters.text & ~Filters.command, handlers.get_student_account_id_to_delete)],
        },
        fallbacks=common_fallbacks,
    )

    delete_branch_conv = ConversationHandler(
        entry_points=[MessageHandler(Filters.regex('^🗑 Filialni o\'chirish'), handlers.delete_branch_start)],
        states={
            states.DELETE_BRANCH_SELECT: [MessageHandler(Filters.text & ~Filters.command, handlers.get_branch_to_delete)],
            states.DELETE_BRANCH_CONFIRM: [MessageHandler(Filters.text & ~Filters.command, handlers.confirm_branch_delete)],
        },
        fallbacks=common_fallbacks,
    )

    change_status_conv = ConversationHandler(
        entry_points=[MessageHandler(Filters.regex('^🔄 Statusni o\'zgartirish'), handlers.change_status_start)],
        states={
            states.CHANGE_STATUS_ACCOUNT_ID: [MessageHandler(Filters.text & ~Filters.command, handlers.get_student_for_status_change)],
            states.CONFIRM_STATUS_CHANGE: [MessageHandler(Filters.text & ~Filters.command, handlers.confirm_status_change)],
        },
        fallbacks=common_fallbacks,
    )

    dispatcher.add_handler(CommandHandler("start", handlers.start))
    dispatcher.add_handler(MessageHandler(Filters.regex('^🏢 Filiallar'), handlers.list_branches))
    dispatcher.add_handler(MessageHandler(Filters.regex('^🎓 O\'quvchilar'), handlers.list_students))
    dispatcher.add_handler(MessageHandler(Filters.regex('^⚙️ Adminlar'), handlers.manage_admins))
    
    dispatcher.add_handler(MessageHandler(Filters.regex('^🔄 Google Sheets bilan sinxronlash'), handlers.sync_with_google_sheet))

    dispatcher.add_handler(CommandHandler("add_admin", handlers.add_admin_command))
    dispatcher.add_handler(CommandHandler("remove_admin", handlers.remove_admin_command))

    dispatcher.add_handler(add_branch_conv)
    dispatcher.add_handler(add_student_conv)
    dispatcher.add_handler(delete_student_conv)
    dispatcher.add_handler(delete_branch_conv)
    dispatcher.add_handler(change_status_conv)

    updater.start_polling()
    return updater.bot, updater.idle