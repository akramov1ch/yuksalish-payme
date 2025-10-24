from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import CallbackContext, ConversationHandler
from functools import wraps
from config import settings, EXCEL_CONFIGS
from database import db
from grpc_client import client as grpc_client
import logging
import io
import openpyxl
import pandas as pd
from . import states

logger = logging.getLogger(__name__)
super_admin_id = settings.super_admin_id


def get_back_keyboard():
    return ReplyKeyboardMarkup([["⬅️ Orqaga"]], resize_keyboard=True)

def create_dynamic_keyboard(items):
    keyboard = [[item] for item in items]
    keyboard.append(["⬅️ Orqaga"])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)


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


@admin_required
def start(update: Update, context: CallbackContext):
    keyboard = [
        ["🏢 Filiallar", "🎓 O'quvchilar"],
        ["➕ Filial qo'shish", "👤 O'quvchi qo'shish"],
        ["🗑 Filialni o'chirish", "🗑 O'quvchini o'chirish"],
        ["🔄 Statusni o'zgartirish"],
        ["📤 O'quvchilarni import qilish"],
        ["⚙️ Adminlar"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    update.message.reply_text("Boshqaruv paneliga xush kelibsiz!", reply_markup=reply_markup)

def cancel(update: Update, context: CallbackContext):
    update.message.reply_text("Amal bekor qilindi. Bosh menyuga qaytilmoqda...", reply_markup=ReplyKeyboardRemove())
    context.user_data.clear()
    start(update, context)
    return ConversationHandler.END


@admin_required
def upload_students_start(update: Update, context: CallbackContext):
    update.message.reply_text("O'quvchilarni ommaviy boshqarish uchun Excel faylini yuboring.", reply_markup=get_back_keyboard())
    return states.PROCESSING_EXCEL_FILE

def process_excel_file(update: Update, context: CallbackContext):
    if update.message.text and update.message.text == "⬅️ Orqaga":
        return cancel(update, context)

    try:
        file = context.bot.get_file(update.message.document.file_id)
        file_content = file.download_as_bytearray()
        
        update.message.reply_text("⏳ Fayl qabul qilindi. Ma'lumotlar tahlil qilinmoqda...")
        
        workbook = openpyxl.load_workbook(io.BytesIO(file_content), data_only=True)
        
        students_from_excel = []
        for config in EXCEL_CONFIGS:
            if len(workbook.worksheets) <= config["sheet_index"]:
                continue
            sheet = workbook.worksheets[config["sheet_index"]]
            logger.info(f"'{sheet.title}' nomli jadval o'qilmoqda...")
            
            col_indices = config["columns"]
            for row_index in range(config["start_row"] + 1, sheet.max_row + 1):
                row_values = [cell.value for cell in sheet[row_index]]
                if not any(row_values) or not row_values[col_indices["student_name"]]:
                    continue
                
                discount_value = row_values[col_indices["discount"]]
                try:
                    final_discount = float(str(discount_value).replace('%', '').strip() or 0)
                except (ValueError, TypeError):
                    final_discount = 0.0

                students_from_excel.append({
                    'branch_name': str(row_values[col_indices["branch_name"]] or '').strip(),
                    'contract_number': str(row_values[col_indices["contract_number"]] or '').strip(),
                    'student_name': str(row_values[col_indices["student_name"]]).strip(),
                    'class': str(row_values[col_indices["class"]] or '').strip(),
                    'parent_name': str(row_values[col_indices["parent_name"]] or '').strip(),
                    'phone': str(row_values[col_indices["phone"]] or '').strip(),
                    'discount': final_discount,
                    'status': str(row_values[col_indices["status"]] or '').strip().lower(),
                })
        
        logger.info(f"Barcha jadvallardan jami {len(students_from_excel)} ta yozuv o'qildi.")
        if not students_from_excel:
            update.message.reply_text("Faylda qayta ishlash uchun ma'lumotlar topilmadi.")
            return cancel(update, context)
        
        all_branches, branch_err = grpc_client.list_branches()
        all_students, student_err = grpc_client.list_students()

        if branch_err or student_err:
            update.message.reply_text(f"Bazadan ma'lumot olishda xatolik: {branch_err or student_err}")
            return cancel(update, context)

        branch_map_by_name = {b.name.strip().lower(): b.id for b in all_branches}
        existing_students_map = {(s.branch_id, s.full_name.strip(), s.parent_name.strip()): s for s in all_students}

        students_to_add = []
        students_to_update = []
        report_data = []

        for student_row in students_from_excel:
            report_row = student_row.copy()
            
            branch_id = branch_map_by_name.get(student_row['branch_name'].lower())
            if not branch_id:
                report_row["Qayta ishlash statusi"] = f"Xatolik: '{student_row['branch_name']}' filiali topilmadi"
                report_data.append(report_row)
                continue

            student_key = (branch_id, student_row['student_name'], student_row['parent_name'])
            existing_student = existing_students_map.get(student_key)
            
            is_active_in_excel = (student_row['status'] == 'amalda')

            if not existing_student:
                students_to_add.append({**student_row, 'branch_id': branch_id, 'group_name': f"{student_row['class']}-sinf"})
                report_row["Qayta ishlash statusi"] = "Qo'shishga tayyorlandi"
            elif existing_student.status != is_active_in_excel:
                students_to_update.append({'student': existing_student, 'new_status': is_active_in_excel})
                report_row["Account ID"] = existing_student.account_id
                report_row["Qayta ishlash statusi"] = "Statusni yangilashga tayyorlandi"
            else:
                report_row["Account ID"] = existing_student.account_id
                report_row["Qayta ishlash statusi"] = "O'zgarishsiz"
            
            report_data.append(report_row)
        
        logger.info(f"Tahlil yakunlandi. Qo'shish uchun: {len(students_to_add)}, Yangilash uchun: {len(students_to_update)}")

        if students_to_add:
            add_batch_data = [
                {
                    'branch_id': s['branch_id'], 'full_name': s['student_name'], 'parent_name': s['parent_name'],
                    'group_name': s['group_name'], 'phone': s['phone'], 'discount_percent': s['discount'],
                    'contract_number': s['contract_number']
                } for s in students_to_add
            ]
            created_students, err = grpc_client.create_students_batch(add_batch_data)
            if err:
                update.message.reply_text(f"❌ O'quvchilarni ommaviy qo'shishda xatolik: {err}")
            else:
                created_map = {(s.branch_id, s.full_name.strip(), s.parent_name.strip()): s for s in created_students}
                for i, report_row in enumerate(report_data):
                    if report_row.get("Qayta ishlash statusi") == "Qo'shishga tayyorlandi":
                        original_row = students_from_excel[i]
                        key = (branch_map_by_name.get(original_row['branch_name'].lower()), original_row['student_name'], original_row['parent_name'])
                        created = created_map.get(key)
                        if created:
                            report_row["Account ID"] = created.account_id
                            report_row["Qayta ishlash statusi"] = "✅ Muvaffaqiyatli qo'shildi"
                            if original_row['status'] == 'bekor':
                                students_to_update.append({'student': created, 'new_status': False})
                        else:
                            report_row["Qayta ishlash statusi"] = "❌ Qo'shishda xatolik"

        if students_to_update:
            update_count = 0
            for item in students_to_update:
                s_obj = item['student']
                s_data = {
                    'id': s_obj.id, 'account_id': s_obj.account_id, 'branch_id': s_obj.branch_id,
                    'parent_name': s_obj.parent_name, 'discount_percent': s_obj.discount_percent,
                    'balance': s_obj.balance, 'full_name': s_obj.full_name,
                    'group_name': s_obj.group_name, 'phone': s_obj.phone,
                    'contract_number': s_obj.contract_number, 'status': item['new_status']
                }
                updated, err = grpc_client.update_student(s_data)
                if err:
                    logger.error(f"O'quvchi {s_obj.account_id} statusini yangilashda xatolik: {err}")
                else:
                    update_count += 1
                    for report_row in report_data:
                        if report_row.get("Account ID") == updated.account_id:
                            status_text = "✅ Faollashtirildi" if updated.status else "✅ Nofaollashtirildi"
                            report_row["Qayta ishlash statusi"] = status_text
                            break
            logger.info(f"{update_count} ta o'quvchi statusi muvaffaqiyatli yangilandi.")

        update.message.reply_text(f"✅ Bajarildi! Qo'shildi: {len(students_to_add)}, Statusi yangilandi: {len(students_to_update)}.")
        
        if report_data:
            df = pd.DataFrame(report_data)
            output_file = io.BytesIO()
            with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Natijalar')
            output_file.seek(0)
            update.message.reply_document(
                document=output_file,
                filename='qayta_ishlash_natijalari.xlsx',
                caption="To'liq hisobot bilan tanishish uchun faylni yuklab oling."
            )

    except Exception as e:
        logger.error(f"Excel faylni qayta ishlashda kutilmagan xatolik: {e}", exc_info=True)
        update.message.reply_text(f"❌ Faylni qayta ishlashda kutilmagan xatolik yuz berdi: {e}")
    
    return cancel(update, context)


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
        message += f"▪️ *{branch.name}*\n"
        message += f"   - Oylik to'lov: {branch.monthly_fee:,} so'm\n".replace(',', ' ')
        message += f"   - O'quvchilar soni: {count} ta\n\n"
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
        branch_data = {
            'name': context.user_data['branch_name'],
            'monthly_fee': int(context.user_data['branch_fee']),
            'mfo_code': context.user_data['branch_mfo'],
            'account_number': context.user_data['branch_account'],
            'merchant_id': context.user_data['branch_merchant']
        }
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
    warning_text = (
        f"❗️ *DIQQAT!* ❗️\n\n"
        f"Siz *'{selected_branch.name}'* filialini o'chirmoqchisiz.\n\n"
        f"Bu amalni orqaga qaytarib bo'lmaydi. Agar bu filialda o'quvchilar mavjud bo'lsa, "
        f"ularni o'chirishda xatolik yuz berishi mumkin.\n\n"
        f"Haqiqatan ham davom etasizmi?"
    )
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
    message = "🎓 *Barcha o'quvchilar:*\n\n"
    for student in students:
        branch_name = branch_map.get(student.branch_id, "Noma'lum filial")
        status_text = "✅ Faol" if student.status else "❌ Nofaol"
        message += f"▪️ *{student.full_name}* ({status_text})\n"
        message += f"   - Hisob raqami: `{student.account_id}`\n"
        message += f"   - Filial: {branch_name}\n"
        message += f"   - Guruh: {student.group_name}\n\n"
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
    update.message.reply_text("O'quvchining guruh/sinf nomini kiriting (masalan, '7-sinf' yoki 'Frontend-dasturlash'):", reply_markup=get_back_keyboard())
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
        student_data = {
            'branch_id': context.user_data['student_branch_id'],
            'parent_name': context.user_data['student_parent_name'],
            'full_name': context.user_data['student_full_name'],
            'group_name': context.user_data['student_group_name'],
            'phone': context.user_data['student_phone'],
            'discount_percent': discount
        }
        new_student, error = grpc_client.create_student(student_data)
        if error:
            update.message.reply_text(f"Xatolik yuz berdi: {error}")
        else:
            success_message = (
                f"✅ Muvaffaqiyatli! Yangi o'quvchi qo'shildi.\n\n"
                f"👤 *F.I.Sh:* {new_student.full_name}\n"
                f"🆔 *Hisob raqami:* `{new_student.account_id}`\n\n"
                f"Ushbu hisob raqamini o'quvchiga taqdim eting."
            )
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
    update.message.reply_text(
        "Statusini o'zgartirmoqchi bo'lgan o'quvchining hisob raqamini (masalan, YM123456) kiriting:",
        reply_markup=get_back_keyboard()
    )
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
    
    message = (
        f"O'quvchi topildi:\n\n"
        f"👤 *F.I.Sh:* {student.full_name}\n"
        f"🆔 *Hisob raqami:* `{student.account_id}`\n"
        f"✳️ *Joriy holati:* {status_text}\n\n"
        f"Yangi holatni tanlang:"
    )
    
    keyboard = [
        ["✅ Faollashtirish", "❌ Nofaollashtirish"],
        ["⬅️ Orqaga"]
    ]
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

    new_status = None
    if "✅ Faollashtirish" in choice:
        new_status = True
    elif "❌ Nofaollashtirish" in choice:
        new_status = False
    
    if new_status is None:
        update.message.reply_text("Iltimos, tugmalardan birini tanlang.")
        return states.CONFIRM_STATUS_CHANGE

    student_data = {
        'id': student_to_update.id,
        'account_id': student_to_update.account_id,
        'branch_id': student_to_update.branch_id,
        'parent_name': student_to_update.parent_name,
        'discount_percent': student_to_update.discount_percent,
        'balance': student_to_update.balance,
        'full_name': student_to_update.full_name,
        'group_name': student_to_update.group_name,
        'phone': student_to_update.phone,
        'contract_number': student_to_update.contract_number,
        'status': new_status
    }

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