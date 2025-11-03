# telegram-bot-admin/bot/handlers.py

from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import CallbackContext, ConversationHandler
from functools import wraps
from config import settings, SHEET_COLUMNS_CONFIG, START_ROW
from database import db
from grpc_client import client as grpc_client
import logging
import gspread
from google.oauth2.service_account import Credentials
from . import states

logger = logging.getLogger(__name__)
super_admin_id = settings.super_admin_id

# --- Yordamchi Funksiyalar ---

def get_gsheet_client():
    """Google Sheets'ga ulanish uchun yordamchi funksiya."""
    try:
        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        creds = Credentials.from_service_account_file(settings.google_creds_file, scopes=scopes)
        client = gspread.authorize(creds)
        return client, None
    except Exception as e:
        logger.error(f"Google Sheets'ga ulanishda xatolik: {e}")
        return None, str(e)

def get_back_keyboard():
    return ReplyKeyboardMarkup([["⬅️ Orqaga"]], resize_keyboard=True)

def create_dynamic_keyboard(items):
    keyboard = [[item] for item in items]
    keyboard.append(["⬅️ Orqaga"])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)

def normalize_text(s):
    """Matnni kichik harflarga o'tkazib, ortiqcha bo'shliqlardan tozalaydi."""
    return (s or "").strip().lower()

def are_students_equal(s_sheet, s_db):
    """Ikki o'quvchi ob'ektini taqqoslaydi (faqat sinxronizatsiya uchun muhim maydonlar)."""
    if normalize_text(s_sheet['full_name']) != normalize_text(s_db.full_name): return False
    if normalize_text(s_sheet['parent_name']) != normalize_text(s_db.parent_name): return False
    if normalize_text(s_sheet['phone']) != normalize_text(s_db.phone): return False
    if normalize_text(s_sheet['group_name']) != normalize_text(s_db.group_name): return False
    if s_sheet['branch_id'] != s_db.branch_id: return False
    if float(s_sheet['discount_percent']) != float(s_db.discount_percent): return False
    if (s_sheet['status_str'] == 'amalda') != s_db.status: return False
    if normalize_text(s_sheet['contract_number']) != normalize_text(s_db.contract_number or ""): return False
    return True

# --- Dekoratorlar ---

def admin_required(func):
    @wraps(func)
    def wrapped(update: Update, context: CallbackContext, *args, **kwargs):
        user_id = update.effective_user.id
        if not db.is_admin(user_id):
            update.message.reply_text("Sizda bu buyruqni ishlatish uchun ruxsat yo'q.")
            return
        return func(update, context, *args, **kwargs)
    return wrapped

def super_admin_required(func):
    @wraps(func)
    def wrapped(update: Update, context: CallbackContext, *args, **kwargs):
        user_id = update.effective_user.id
        if user_id != super_admin_id:
            update.message.reply_text("Bu buyruq faqat super admin uchun mavjud.")
            return
        return func(update, context, *args, **kwargs)
    return wrapped

# --- Asosiy Handler'lar ---

@admin_required
def start(update: Update, context: CallbackContext):
    keyboard = [
        ["🏢 Filiallar", "🎓 O'quvchilar"],
        ["➕ Filial qo'shish", "👤 O'quvchi qo'shish"],
        ["🗑 Filialni o'chirish", "🗑 O'quvchini o'chirish"],
        ["🔄 Statusni o'zgartirish"],
        ["🔄 Google Sheets bilan sinxronlash"],
        ["⚙️ Adminlar"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    update.message.reply_text("Boshqaruv paneliga xush kelibsiz!", reply_markup=reply_markup)

def cancel(update: Update, context: CallbackContext):
    update.message.reply_text("Amal bekor qilindi. Bosh menyuga qaytilmoqda...", reply_markup=ReplyKeyboardRemove())
    context.user_data.clear()
    start(update, context)
    return ConversationHandler.END

# ====================================================================
# SINXRONIZATSIYA FUNKSIYASINING YANGI VERSIYASI
# ====================================================================
@admin_required
def sync_with_google_sheet(update: Update, context: CallbackContext):
    progress_message = update.message.reply_text(
        "⏳ Google Sheets bilan sinxronizatsiya boshlanmoqda...",
        reply_markup=ReplyKeyboardRemove()
    )

    def edit_progress_message(new_text):
        if progress_message.text != new_text:
            try:
                progress_message.edit_text(new_text)
            except Exception as e:
                logger.warning(f"Progress xabarini yangilab bo'lmadi: {e}")

    gspread_client, gsheet_error = get_gsheet_client()
    if gsheet_error:
        edit_progress_message(f"❌ Google Sheets'ga ulanib bo'lmadi: {gsheet_error}")
        start(update, context)
        return

    total_added = 0
    total_updated = 0
    error_sheets = []

    try:
        edit_progress_message("⏳ Ma'lumotlar bazasidan filiallar va o'quvchilar ro'yxati olinmoqda...")
        all_branches, branch_err = grpc_client.list_branches()
        all_students, student_err = grpc_client.list_students()
        if branch_err or student_err:
            raise Exception(f"Baza bilan ishlashda xatolik: {branch_err or student_err}")

        branch_map_by_name = {normalize_text(b.name): b.id for b in all_branches}
        existing_students_by_uuid = {s.id: s for s in all_students}
        logger.info(f"Bazadan {len(all_branches)} ta filial va {len(all_students)} ta o'quvchi olindi.")

        edit_progress_message(f"⏳ Google Sheets fayli ({settings.google_spreadsheet_id}) ochilmoqda...")
        spreadsheet = gspread_client.open_by_key(settings.google_spreadsheet_id)

    except Exception as e:
        edit_progress_message(f"❌ Boshlang'ich ma'lumotlarni olishda kutilmagan xatolik: {e}")
        start(update, context)
        return

    # Har bir varaq (worksheet) uchun sinxronizatsiyani bajarish
    for sheet_name in settings.google_worksheet_name_list:
        try:
            edit_progress_message(f"⏳ '{sheet_name}' varag'i bilan ishlanmoqda...")
            worksheet = spreadsheet.worksheet(sheet_name)

            all_data = worksheet.get_all_values()
            rows_to_process = all_data[START_ROW-1:]
            total_rows_in_sheet = len(rows_to_process)
            
            students_to_add = []
            students_to_update = []
            updates_for_gsheet = []
            UPDATE_INTERVAL = 20

            for i, row_values in enumerate(rows_to_process):
                row_number = i + START_ROW
                logger.info(f"[{sheet_name}] Qator {row_number} tekshirilmoqda: {row_values}")
                
                if (i + 1) % UPDATE_INTERVAL == 0 or (i + 1) == total_rows_in_sheet:
                    edit_progress_message(
                        f"⏳ '{sheet_name}' varag'i bilan ishlanmoqda...\n\n"
                        f"✅ {i + 1}/{total_rows_in_sheet} qator tekshirildi."
                    )

                # <<< O'ZGARTIRILGAN QISM BOSHI >>>
                student_name_col = SHEET_COLUMNS_CONFIG["student_name"]
                if len(row_values) <= student_name_col or not str(row_values[student_name_col]).strip():
                    logger.info(f"  -> O'TKAZIB YUBORILDI: Qator bo'sh yoki F.I.Sh. ustuni ({student_name_col+1}) kiritilmagan.")
                    continue
                # <<< O'ZGARTIRILGAN QISM TUGADI >>>

                branch_name = str(row_values[SHEET_COLUMNS_CONFIG["branch_name"]] or '').strip()
                branch_id = branch_map_by_name.get(normalize_text(branch_name))
                if not branch_id:
                    logger.warning(f"  -> O'TKAZIB YUBORILDI: '{branch_name}' nomli filial bazada topilmadi.")
                    continue

                student_data_from_sheet = {
                    'branch_id': branch_id, 'contract_number': str(row_values[SHEET_COLUMNS_CONFIG["contract_number"]] or '').strip(),
                    'full_name': str(row_values[SHEET_COLUMNS_CONFIG["student_name"]]).strip(), 'group_name': f"{str(row_values[SHEET_COLUMNS_CONFIG['class']] or '').strip()}-sinf",
                    'parent_name': str(row_values[SHEET_COLUMNS_CONFIG["parent_name"]] or '').strip(), 'phone': str(row_values[SHEET_COLUMNS_CONFIG["phone"]] or '').strip(),
                    'discount_percent': float(str(row_values[SHEET_COLUMNS_CONFIG["discount"]]).replace('%', '').strip() or 0),
                    'status_str': str(row_values[SHEET_COLUMNS_CONFIG["status"]] or '').strip().lower(),
                }
                
                uuid_val = ""
                if len(row_values) > SHEET_COLUMNS_CONFIG["uuid"]:
                    uuid_val = str(row_values[SHEET_COLUMNS_CONFIG["uuid"]]).strip()

                if uuid_val and uuid_val in existing_students_by_uuid:
                    student_from_db = existing_students_by_uuid[uuid_val]
                    if not are_students_equal(student_data_from_sheet, student_from_db):
                        logger.info(f"  -> YANGILANADI: '{student_from_db.full_name}' uchun o'zgarish topildi.")
                        students_to_update.append({
                            'id': student_from_db.id, 'account_id': student_from_db.account_id, 'balance': student_from_db.balance,
                            'status': (student_data_from_sheet['status_str'] == 'amalda'), **student_data_from_sheet
                        })
                    else:
                        logger.info(f"  -> O'zgarish yo'q: '{student_from_db.full_name}'.")
                else:
                    logger.info(f"  -> QO'SHILADI: Yangi o'quvchi '{student_data_from_sheet['full_name']}' topildi.")
                    students_to_add.append({'row_number': row_number, **student_data_from_sheet})
            
            if students_to_add:
                edit_progress_message(f"⏳ '{sheet_name}' varag'idan {len(students_to_add)} ta yangi o'quvchi bazaga qo'shilmoqda...")
                grpc_students_to_add = [ {k: v for k, v in s.items() if k != 'row_number'} for s in students_to_add]
                created_students, err = grpc_client.create_students_batch(grpc_students_to_add)
                if err: raise Exception(f"Ommaviy qo'shishda xatolik: {err}")
                
                total_added += len(created_students)
                created_map = { (s.branch_id, normalize_text(s.full_name), normalize_text(s.parent_name)): s for s in created_students }
                
                for s_to_add in students_to_add:
                    key = (s_to_add['branch_id'], normalize_text(s_to_add['full_name']), normalize_text(s_to_add['parent_name']))
                    created = created_map.get(key)
                    if created:
                        updates_for_gsheet.append(gspread.Cell(s_to_add['row_number'], SHEET_COLUMNS_CONFIG["account_id"] + 1, created.account_id))
                        updates_for_gsheet.append(gspread.Cell(s_to_add['row_number'], SHEET_COLUMNS_CONFIG["uuid"] + 1, created.id))

            if students_to_update:
                edit_progress_message(f"⏳ '{sheet_name}' varag'idan {len(students_to_update)} ta o'quvchi ma'lumotlari yangilanmoqda...")
                success, err = grpc_client.update_students_batch(students_to_update)
                if not success: raise Exception(f"Ommaviy yangilashda xatolik: {err}")
                total_updated += len(students_to_update)

            if updates_for_gsheet:
                edit_progress_message(f"⏳ '{sheet_name}' varag'iga yangi ID'lar yozilmoqda...")
                worksheet.update_cells(updates_for_gsheet, value_input_option='USER_ENTERED')
                logger.info(f"'{worksheet.title}' varog'iga {len(updates_for_gsheet)//2} ta o'quvchi ID'si yozildi.")

        except Exception as e:
            logger.error(f"'{sheet_name}' varag'i bilan ishlashda xatolik: {e}", exc_info=True)
            error_sheets.append(sheet_name)

    final_message = (
        f"✅ Sinxronizatsiya yakunlandi!\n\n"
        f"📄 Jami varaqlar: {len(settings.google_worksheet_name_list)}\n"
        f"✔️ Muvaffaqiyatli: {len(settings.google_worksheet_name_list) - len(error_sheets)}\n"
        f"❌ Xatolik yuz berganlar: {len(error_sheets)}\n\n"
        f"📊 Umumiy natija:\n"
        f"➕ Yangi qo'shilgan o'quvchilar: {total_added}\n"
        f"🔄 Ma'lumotlari yangilanganlar: {total_updated}\n"
    )
    if error_sheets:
        final_message += f"\n❗️ Xatolik yuz bergan varaqlar: {', '.join(error_sheets)}"

    edit_progress_message(final_message)
    start(update, context)


# --- QOLGAN BARCHA HANDLER'LAR O'ZGARISHSIZ QOLADI ---

@admin_required
def list_branches(update: Update, context: CallbackContext):
    branches_info, error = grpc_client.list_branches_with_student_counts()
    if error:
        update.message.reply_text(f"Xatolik: {error}")
        return
    if not branches_info:
        update.message.reply_text("Hozircha filiallar mavjud emas.")
        return
    message = "🏢 *Barcha filiallar:*\n\n"
    for info in branches_info:
        branch = info['branch']
        count = info['student_count']
        fee_in_som = branch.monthly_fee
        formatted_fee = f"{fee_in_som:,.0f}".replace(',', ' ')
        message += f"▪️ *{branch.name}*\n   - Oylik to'lov: {formatted_fee} so'm\n   - O'quvchilar soni: {count} ta\n\n"
    update.message.reply_text(message, parse_mode='Markdown')

@admin_required
def add_branch_start(update: Update, context: CallbackContext):
    update.message.reply_text("Yangi filial nomini kiriting:", reply_markup=get_back_keyboard())
    return states.BRANCH_NAME

def get_branch_name(update: Update, context: CallbackContext):
    if update.message.text == "⬅️ Orqaga": return cancel(update, context)
    context.user_data['branch_name'] = update.message.text
    update.message.reply_text("Filial uchun oylik to'lov miqdorini kiriting (faqat raqam, masalan: 300000):", reply_markup=get_back_keyboard())
    return states.BRANCH_FEE

def get_branch_fee(update: Update, context: CallbackContext):
    if update.message.text == "⬅️ Orqaga": return cancel(update, context)
    context.user_data['branch_fee'] = update.message.text
    update.message.reply_text("Bank MFO kodini kiriting (masalan, 00450):", reply_markup=get_back_keyboard())
    return states.BRANCH_MFO

def get_branch_mfo(update: Update, context: CallbackContext):
    if update.message.text == "⬅️ Orqaga": return cancel(update, context)
    context.user_data['branch_mfo'] = update.message.text
    update.message.reply_text("Bank hisob raqamini kiriting (masalan, 20206000100200300400):", reply_markup=get_back_keyboard())
    return states.BRANCH_ACC

def get_branch_account(update: Update, context: CallbackContext):
    if update.message.text == "⬅️ Orqaga": return cancel(update, context)
    context.user_data['branch_account'] = update.message.text
    update.message.reply_text("To'lov tizimi uchun Merchant ID'ni kiriting:", reply_markup=get_back_keyboard())
    return states.BRANCH_MERCHANT

def get_branch_merchant(update: Update, context: CallbackContext):
    if update.message.text == "⬅️ Orqaga": return cancel(update, context)
    context.user_data['branch_merchant'] = update.message.text
    try:
        branch_data = {'name': context.user_data['branch_name'], 'monthly_fee': int(context.user_data['branch_fee']), 'mfo_code': context.user_data['branch_mfo'], 'account_number': context.user_data['branch_account'], 'merchant_id': context.user_data['branch_merchant']}
        new_branch, error = grpc_client.create_branch(branch_data)
        if error:
            update.message.reply_text(f"Xatolik yuz berdi: {error}")
        else:
            update.message.reply_text(f"✅ Muvaffaqiyatli! '{new_branch.name}' nomli yangi filial qo'shildi.")
    except (ValueError, KeyError) as e:
        update.message.reply_text(f"Kiritishda xatolik: {e}. Iltimos, qaytadan boshlang.")
    context.user_data.clear()
    start(update, context)
    return ConversationHandler.END

@admin_required
def delete_branch_start(update: Update, context: CallbackContext):
    branches, error = grpc_client.list_branches()
    if error or not branches:
        update.message.reply_text("Filiallar topilmadi yoki xatolik yuz berdi.")
        start(update, context)
        return ConversationHandler.END
    context.user_data['branches_list'] = branches
    branch_names = [branch.name for branch in branches]
    reply_markup = create_dynamic_keyboard(branch_names)
    update.message.reply_text("Qaysi filialni o'chirmoqchisiz?", reply_markup=reply_markup)
    return states.DELETE_BRANCH_SELECT

def get_branch_to_delete(update: Update, context: CallbackContext):
    if update.message.text == "⬅️ Orqaga": return cancel(update, context)
    branch_name = update.message.text
    branches = context.user_data.get('branches_list', [])
    selected_branch = next((b for b in branches if b.name == branch_name), None)
    if not selected_branch:
        update.message.reply_text("Noto'g'ri filial tanlandi. Iltimos, qaytadan urinib ko'ring.")
        return states.DELETE_BRANCH_SELECT
    context.user_data['branch_to_delete_id'] = selected_branch.id
    context.user_data['branch_to_delete_name'] = selected_branch.name
    warning_text = f"❗️ *DIQQAT!* ❗️\n\nSiz *'{selected_branch.name}'* filialini o'chirmoqchisiz.\n\nBu amalni orqaga qaytarib bo'lmaydi. Agar bu filialda o'quvchilar mavjud bo'lsa, ularni o'chirishda xatolik yuz berishi mumkin.\n\nHaqiqatan ham davom etasizmi?"
    keyboard = [["✅ Ha, o'chirish", "❌ Yo'q, bekor qilish"], ["⬅️ Orqaga"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    update.message.reply_text(warning_text, reply_markup=reply_markup, parse_mode='Markdown')
    return states.DELETE_BRANCH_CONFIRM

def confirm_branch_delete(update: Update, context: CallbackContext):
    if update.message.text == "⬅️ Orqaga": return cancel(update, context)
    choice = update.message.text
    if "❌ Yo'q" in choice:
        return cancel(update, context)
    if "✅ Ha" in choice:
        branch_id = context.user_data.get('branch_to_delete_id')
        branch_name = context.user_data.get('branch_to_delete_name')
        success, error = grpc_client.delete_branch(branch_id)
        if success:
            update.message.reply_text(f"✅ Filial '{branch_name}' muvaffaqiyatli o'chirildi.")
        else:
            update.message.reply_text(f"❌ Xatolik: {error}")
        context.user_data.clear()
        start(update, context)
        return ConversationHandler.END
    update.message.reply_text("Iltimos, quyidagi tugmalardan birini tanlang.", reply_markup=get_back_keyboard())
    return states.DELETE_BRANCH_CONFIRM

@admin_required
def list_students(update: Update, context: CallbackContext):
    branches, branch_error = grpc_client.list_branches()
    students, student_error = grpc_client.list_students()
    if branch_error or student_error:
        update.message.reply_text(f"Ma'lumotlarni olishda xatolik yuz berdi.")
        return
    if not students:
        update.message.reply_text("Hozircha o'quvchilar mavjud emas.")
        return
    branch_map = {branch.id: branch.name for branch in branches}
    student_counts_by_branch = {branch.id: 0 for branch in branches}
    active_students = 0
    inactive_students = 0
    for student in students:
        if student.branch_id in student_counts_by_branch:
            student_counts_by_branch[student.branch_id] += 1
        if student.status:
            active_students += 1
        else:
            inactive_students += 1
    total_students = len(students)
    message = f"🎓 *O'quvchilar haqida umumiy ma'lumot:*\n\n"
    message += f"🔹 Jami o'quvchilar soni: *{total_students}*\n"
    message += f"✅ Faol o'quvchilar: *{active_students}*\n"
    message += f"❌ Nofaol o'quvchilar: *{inactive_students}*\n\n"
    message += "Filiallar bo'yicha taqsimot:\n"
    for branch_id, count in student_counts_by_branch.items():
        branch_name = branch_map.get(branch_id, "Noma'lum filial")
        message += f"- {branch_name}: *{count}* ta o'quvchi\n"
    update.message.reply_text(message, parse_mode='Markdown')

@admin_required
def add_student_start(update: Update, context: CallbackContext):
    branches, error = grpc_client.list_branches()
    if error or not branches:
        update.message.reply_text("Filiallar topilmadi yoki xatolik yuz berdi. Avval filial qo'shing.")
        start(update, context)
        return ConversationHandler.END
    context.user_data['branches_list'] = branches
    branch_names = [branch.name for branch in branches]
    reply_markup = create_dynamic_keyboard(branch_names)
    update.message.reply_text("O'quvchi qaysi filialga tegishli ekanini tanlang:", reply_markup=reply_markup)
    return states.STUDENT_BRANCH

def get_student_branch(update: Update, context: CallbackContext):
    if update.message.text == "⬅️ Orqaga": return cancel(update, context)
    branch_name = update.message.text
    branches = context.user_data.get('branches_list', [])
    selected_branch = next((b for b in branches if b.name == branch_name), None)
    if not selected_branch:
        update.message.reply_text("Noto'g'ri filial tanlandi. Iltimos, qaytadan urinib ko'ring.")
        return states.STUDENT_BRANCH
    context.user_data['student_branch_id'] = selected_branch.id
    update.message.reply_text("Ota-onasining ismini kiriting (masalan, Olimov A.):", reply_markup=get_back_keyboard())
    return states.STUDENT_PARENT

def get_student_parent_name(update: Update, context: CallbackContext):
    if update.message.text == "⬅️ Orqaga": return cancel(update, context)
    context.user_data['student_parent_name'] = update.message.text
    update.message.reply_text("O'quvchining to'liq F.I.Sh. ni kiriting:", reply_markup=get_back_keyboard())
    return states.STUDENT_FULLNAME

def get_student_full_name(update: Update, context: CallbackContext):
    if update.message.text == "⬅️ Orqaga": return cancel(update, context)
    context.user_data['student_full_name'] = update.message.text
    update.message.reply_text("O'quvchining guruh/sinf nomini kiriting (masalan, '7-sinf'):", reply_markup=get_back_keyboard())
    return states.STUDENT_GROUP_NAME

def get_student_group_name(update: Update, context: CallbackContext):
    if update.message.text == "⬅️ Orqaga": return cancel(update, context)
    context.user_data['student_group_name'] = update.message.text
    update.message.reply_text("O'quvchining telefon raqamini kiriting (+998...):", reply_markup=get_back_keyboard())
    return states.STUDENT_PHONE

def get_student_phone(update: Update, context: CallbackContext):
    if update.message.text == "⬅️ Orqaga": return cancel(update, context)
    context.user_data['student_phone'] = update.message.text
    update.message.reply_text("Chegirma foizini kiriting (agar yo'q bo'lsa, 0 kiriting):", reply_markup=get_back_keyboard())
    return states.STUDENT_DISCOUNT

def get_student_discount(update: Update, context: CallbackContext):
    if update.message.text == "⬅️ Orqaga": return cancel(update, context)
    try:
        discount = float(update.message.text)
        student_data = {'branch_id': context.user_data['student_branch_id'], 'parent_name': context.user_data['student_parent_name'], 'full_name': context.user_data['student_full_name'], 'group_name': context.user_data['student_group_name'], 'phone': context.user_data['student_phone'], 'discount_percent': discount}
        new_student, error = grpc_client.create_student(student_data)
        if error:
            update.message.reply_text(f"Xatolik yuz berdi: {error}")
        else:
            success_message = f"✅ Muvaffaqiyatli! Yangi o'quvchi qo'shildi.\n\n👤 *F.I.Sh:* {new_student.full_name}\n🆔 *Hisob raqami:* `{new_student.account_id}`\n\nUshbu hisob raqamini o'quvchiga taqdim eting."
            update.message.reply_text(success_message, parse_mode='Markdown')
    except (ValueError, KeyError) as e:
        update.message.reply_text(f"Kiritishda xatolik: {e}. Iltimos, qaytadan boshlang.")
    context.user_data.clear()
    start(update, context)
    return ConversationHandler.END

@admin_required
def delete_student_start(update: Update, context: CallbackContext):
    update.message.reply_text("O'chiriladigan o'quvchining hisob raqamini kiriting (masalan, YM19857):", reply_markup=get_back_keyboard())
    return states.DELETE_STUDENT_ACCOUNT_ID

def get_student_account_id_to_delete(update: Update, context: CallbackContext):
    if update.message.text == "⬅️ Orqaga": return cancel(update, context)
    account_id = update.message.text.strip()
    if not account_id.upper().startswith("YM"):
        update.message.reply_text("Noto'g'ri format. Hisob raqami 'YM' bilan boshlanishi kerak. Qaytadan kiriting:", reply_markup=get_back_keyboard())
        return states.DELETE_STUDENT_ACCOUNT_ID
    success, error = grpc_client.delete_student_by_account_id(account_id)
    if error:
        update.message.reply_text(f"❌ Xatolik: {error}")
    else:
        update.message.reply_text(f"✅ O'quvchi (hisob raqami: {account_id}) muvaffaqiyatli o'chirildi.")
    start(update, context)
    return ConversationHandler.END

@admin_required
def change_status_start(update: Update, context: CallbackContext):
    update.message.reply_text("Statusini o'zgartirmoqchi bo'lgan o'quvchining hisob raqamini kiriting:", reply_markup=get_back_keyboard())
    return states.CHANGE_STATUS_ACCOUNT_ID

def get_student_for_status_change(update: Update, context: CallbackContext):
    if update.message.text == "⬅️ Orqaga": return cancel(update, context)
    account_id = update.message.text.strip()
    student, error = grpc_client.get_student_by_account_id(account_id)
    if error or not student:
        update.message.reply_text(f"❌ Xatolik: {error or 'O`quvchi topilmadi.'}\nQaytadan kiriting:")
        return states.CHANGE_STATUS_ACCOUNT_ID
    context.user_data['student_to_update'] = student
    status_text = "✅ Faol" if student.status else "❌ Nofaol"
    message = f"O'quvchi topildi:\n\n👤 *F.I.Sh:* {student.full_name}\n🆔 *Hisob raqami:* `{student.account_id}`\n✳️ *Joriy holati:* {status_text}\n\nYangi holatni tanlang:"
    keyboard = [["✅ Faollashtirish", "❌ Nofaollashtirish"], ["⬅️ Orqaga"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    update.message.reply_text(message, reply_markup=reply_markup, parse_mode='Markdown')
    return states.CONFIRM_STATUS_CHANGE

def confirm_status_change(update: Update, context: CallbackContext):
    if update.message.text == "⬅️ Orqaga": return cancel(update, context)
    choice = update.message.text
    student_to_update = context.user_data.get('student_to_update')
    if not student_to_update:
        update.message.reply_text("Xatolik yuz berdi. Iltimos, boshidan boshlang.")
        return cancel(update, context)
    new_status = "✅ Faollashtirish" in choice
    student_data = {'id': student_to_update.id, 'account_id': student_to_update.account_id, 'branch_id': student_to_update.branch_id, 'parent_name': student_to_update.parent_name, 'discount_percent': student_to_update.discount_percent, 'balance': student_to_update.balance, 'full_name': student_to_update.full_name, 'group_name': student_to_update.group_name, 'phone': student_to_update.phone, 'contract_number': student_to_update.contract_number, 'status': new_status}
    updated_student, error = grpc_client.update_student(student_data)
    if error:
        update.message.reply_text(f"❌ Statusni yangilashda xatolik: {error}")
    else:
        status_text = "✅ Faol" if updated_student.status else "❌ Nofaol"
        update.message.reply_text(f"✅ Muvaffaqiyatli! O'quvchi *{updated_student.full_name}* uchun yangi holat: *{status_text}*", parse_mode='Markdown')
    return cancel(update, context)

@admin_required
def manage_admins(update: Update, context: CallbackContext):
    admin_ids = db.get_all_admins()
    message = "⚙️ *Mavjud adminlar:*\n"
    for admin_id in admin_ids:
        message += f"- `{admin_id}`"
        if admin_id == super_admin_id:
            message += " (Super Admin)\n"
        else:
            message += "\n"
    message += "\nAdmin qo'shish uchun: `/add_admin <user_id>`"
    message += "\nAdminni o'chirish uchun: `/remove_admin <user_id>`"
    update.message.reply_text(message, parse_mode='Markdown')

@super_admin_required
def add_admin_command(update: Update, context: CallbackContext):
    try:
        user_id = int(context.args[0])
        if db.add_admin(user_id):
            update.message.reply_text(f"✅ Admin `{user_id}` muvaffaqiyatli qo'shildi.")
        else:
            update.message.reply_text(f"ℹ️ Bu foydalanuvchi allaqachon admin.")
    except (IndexError, ValueError):
        update.message.reply_text("Noto'g'ri format. Ishlatish: /add_admin <user_id>")

@super_admin_required
def remove_admin_command(update: Update, context: CallbackContext):
    try:
        user_id = int(context.args[0])
        if user_id == super_admin_id:
            update.message.reply_text("Super adminni o'chirib bo'lmaydi.")
            return
        if db.remove_admin(user_id):
            update.message.reply_text(f"✅ Admin `{user_id}` muvaffaqiyatli o'chirildi.")
        else:
            update.message.reply_text(f"❌ Bu ID raqamli admin topilmadi.")
    except (IndexError, ValueError):
        update.message.reply_text("Noto'g'ri format. Ishlatish: /remove_admin <user_id>")