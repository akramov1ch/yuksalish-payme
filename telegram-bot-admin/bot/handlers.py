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

# Loglarni terminalga chiqarish
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
super_admin_id = settings.super_admin_id

# --- Yordamchi Funksiyalar ---
def get_gsheet_client():
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
    return (s or "").strip().lower().replace(" ", "")

def safe_get(row, index):
    """Ro'yxatdan indeks bo'yicha xavfsiz olish"""
    try:
        val = row[index]
        return str(val).strip() if val else ""
    except IndexError:
        return ""

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
    update.message.reply_text("Amal bekor qilindi.", reply_markup=ReplyKeyboardRemove())
    context.user_data.clear()
    start(update, context)
    return ConversationHandler.END

# ====================================================================
# SINXRONIZATSIYA
# ====================================================================
@admin_required
def sync_with_google_sheet(update: Update, context: CallbackContext):
    progress_message = update.message.reply_text("⏳ Sinxronizatsiya boshlanmoqda... (Loglarni terminalda kuzating)", reply_markup=ReplyKeyboardRemove())

    def edit_progress(text):
        try:
            if progress_message.text != text: progress_message.edit_text(text)
        except: pass

    gspread_client, err = get_gsheet_client()
    if err:
        edit_progress(f"❌ Google Sheets xatosi: {err}")
        start(update, context)
        return

    try:
        edit_progress("⏳ Bazadan ma'lumotlar olinmoqda...")
        all_branches, _ = grpc_client.list_branches()
        all_students, _ = grpc_client.list_students()
        
        if not all_branches:
            edit_progress("❌ DIQQAT: Bazada hech qanday filial yo'q! Avval bot orqali '➕ Filial qo'shish' tugmasi bilan filial yarating.")
            return

        branch_map = {normalize_text(b.name): b.id for b in all_branches}
        db_students_by_uuid = {s.id: s for s in all_students}

        spreadsheet = gspread_client.open_by_key(settings.google_spreadsheet_id)
    except Exception as e:
        edit_progress(f"❌ Xatolik: {e}")
        logger.error(f"Boshlang'ich xatolik: {e}")
        start(update, context)
        return

    total_created = 0
    total_updated = 0

    for sheet_name in settings.google_worksheet_name_list:
        try:
            edit_progress(f"⏳ '{sheet_name}' varag'i o'qilmoqda...")
            logger.info(f"--- VARAQ: {sheet_name} ---")
            
            try:
                worksheet = spreadsheet.worksheet(sheet_name)
            except gspread.exceptions.WorksheetNotFound:
                logger.error(f"Varaq topilmadi: {sheet_name}")
                continue

            rows = worksheet.get_all_values()[START_ROW-1:]
            
            to_create = [] 
            to_update = [] 
            updates_for_sheet = [] 

            for i, row in enumerate(rows):
                row_num = i + START_ROW
                
                student_name_raw = safe_get(row, SHEET_COLUMNS_CONFIG["student_name"])
                if not student_name_raw:
                    continue

                b_name_raw = safe_get(row, SHEET_COLUMNS_CONFIG["branch_name"])
                b_name_norm = normalize_text(b_name_raw)
                b_id = branch_map.get(b_name_norm)
                
                if not b_id: 
                    continue 

                acc_id = safe_get(row, SHEET_COLUMNS_CONFIG["account_id"]).upper().replace(" ", "")
                uuid_val = safe_get(row, SHEET_COLUMNS_CONFIG["uuid"])
                
                logger.info(f"Qator {row_num}: {student_name_raw} | ID: '{acc_id}' | UUID: '{uuid_val}'")

                try:
                    discount_str = safe_get(row, SHEET_COLUMNS_CONFIG["discount"]).replace('%', '')
                    discount_val = float(discount_str) if discount_str else 0.0
                except:
                    discount_val = 0.0

                student_data = {
                    'branch_id': b_id,
                    'account_id': acc_id,
                    'full_name': student_name_raw,
                    'parent_name': safe_get(row, SHEET_COLUMNS_CONFIG["parent_name"]),
                    'phone': safe_get(row, SHEET_COLUMNS_CONFIG["phone"]),
                    'group_name': f"{safe_get(row, SHEET_COLUMNS_CONFIG['class'])}-sinf",
                    'contract_number': safe_get(row, SHEET_COLUMNS_CONFIG["contract_number"]),
                    'discount_percent': discount_val,
                    'status': (safe_get(row, SHEET_COLUMNS_CONFIG["status"]).lower() == 'amalda')
                }

                if uuid_val and uuid_val in db_students_by_uuid:
                    student_data['id'] = uuid_val
                    to_update.append(student_data)
                else:
                    student_data['row_number'] = row_num
                    to_create.append(student_data)

            if to_update:
                logger.info(f"Yangilanmoqda: {len(to_update)} ta")
                grpc_client.update_students_batch(to_update)
                total_updated += len(to_update)

            if to_create:
                logger.info(f"Yaratilmoqda/Tekshirilmoqda: {len(to_create)} ta")
                clean_create_list = [{k: v for k, v in s.items() if k != 'row_number'} for s in to_create]
                
                created_students, err = grpc_client.create_students_batch(clean_create_list)
                if err:
                    logger.error(f"Create batch error: {err}")
                else:
                    total_created += len(created_students)
                    created_map = {s.account_id: s for s in created_students}

                    for item in to_create:
                        res = created_map.get(item['account_id'])
                        
                        if not res:
                             for s in created_students:
                                 if s.branch_id == item['branch_id'] and normalize_text(s.full_name) == normalize_text(item['full_name']):
                                     res = s
                                     break
                        
                        if res:
                            updates_for_sheet.append(gspread.Cell(item['row_number'], SHEET_COLUMNS_CONFIG["uuid"] + 1, res.id))
                            if not item['account_id']:
                                 updates_for_sheet.append(gspread.Cell(item['row_number'], SHEET_COLUMNS_CONFIG["account_id"] + 1, res.account_id))

            if updates_for_sheet:
                logger.info(f"Sheet yangilanmoqda: {len(updates_for_sheet)} ta katak")
                worksheet.update_cells(updates_for_sheet, value_input_option='USER_ENTERED')

        except Exception as e:
            logger.error(f"Sheet loop error: {e}", exc_info=True)
            edit_progress(f"⚠️ Xatolik varaqda: {e}")

    final_msg = f"✅ Tugadi!\nYangilandi: {total_updated}\nQo'shildi: {total_created}"
    logger.info(final_msg)
    edit_progress(final_msg)
    start(update, context)

# --- FILIALLAR ---
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
        message += f"▪️ *{branch.name}*\n   - Oylik to'lov: {formatted_fee} so'm\n   - O'quvchilar soni: {count} ta\n   - Topic ID: {branch.topic_id}\n\n"
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
    
    # YANGI: Topic ID so'rash
    update.message.reply_text(
        "Ushbu filial uchun guruhdagi Topic ID (Thread ID) ni kiriting:\n"
        "(Masalan: 12 yoki 453. Agar Topic bo'lmasa 0 kiriting)", 
        reply_markup=get_back_keyboard()
    )
    return states.BRANCH_TOPIC_ID

def get_branch_topic_id(update: Update, context: CallbackContext):
    if update.message.text == "⬅️ Orqaga": return cancel(update, context)
    
    try:
        topic_id = int(update.message.text)
        
        branch_data = {
            'name': context.user_data['branch_name'],
            'monthly_fee': int(context.user_data['branch_fee']),
            'mfo_code': context.user_data['branch_mfo'],
            'account_number': context.user_data['branch_account'],
            'merchant_id': context.user_data['branch_merchant'],
            'topic_id': topic_id # YANGI
        }
        
        new_branch, error = grpc_client.create_branch(branch_data)
        if error:
            update.message.reply_text(f"Xatolik yuz berdi: {error}")
        else:
            update.message.reply_text(f"✅ Muvaffaqiyatli! '{new_branch.name}' nomli yangi filial qo'shildi (Topic ID: {topic_id}).")
            
    except ValueError:
        update.message.reply_text("Iltimos, Topic ID uchun faqat raqam kiriting.")
        return states.BRANCH_TOPIC_ID
    except Exception as e:
        update.message.reply_text(f"Xatolik: {e}")

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

# --- O'QUVCHILAR ---
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