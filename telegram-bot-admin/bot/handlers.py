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
    from .core import PROCESSING_EXCEL_FILE
    update.message.reply_text("O'quvchilarni ommaviy qo'shish/o'chirish uchun Excel faylini yuboring.", reply_markup=get_back_keyboard())
    return PROCESSING_EXCEL_FILE

def process_excel_file(update: Update, context: CallbackContext):
    if update.message.text and update.message.text == "⬅️ Orqaga":
        return cancel(update, context)

    try:
        file = context.bot.get_file(update.message.document.file_id)
        file_content = file.download_as_bytearray()
        
        file_path = "Reestr.xlsx"
        with open(file_path, "wb") as f:
            f.write(file_content)
        
        update.message.reply_text("⏳ Fayl qabul qilindi. Barcha jadvallar qayta ishlanmoqda...")
        logger.info(f"Excel fayl '{file_path}' sifatida saqlandi va o'qilmoqda.")

        workbook = openpyxl.load_workbook(file_path, data_only=True)
        
        students_from_excel = []
        
        for config in EXCEL_CONFIGS:
            sheet_index = config["sheet_index"]
            start_row = config["start_row"]
            col_indices = config["columns"]

            if len(workbook.worksheets) <= sheet_index:
                logger.warning(f"Konfiguratsiyada ko'rsatilgan {sheet_index}-indeksdagi jadval faylda mavjud emas. O'tkazib yuborildi.")
                continue
                
            sheet = workbook.worksheets[sheet_index]
            logger.info(f"'{sheet.title}' nomli {sheet_index}-indeksdagi jadval o'qilmoqda...")

            for row_index in range(start_row + 1, sheet.max_row + 1):
                row_values = [cell.value for cell in sheet[row_index]]
                
                if not any(row_values):
                    continue
                
                student_name_cell = row_values[col_indices["student_name"]]
                if not student_name_cell or not str(student_name_cell).strip():
                    continue

                discount_value = row_values[col_indices["discount"]]
                try:
                    if isinstance(discount_value, str):
                        discount_str = discount_value.replace('%', '').strip()
                        final_discount = float(discount_str or 0)
                    else:
                        final_discount = float(discount_value or 0)
                except (ValueError, TypeError):
                    final_discount = 0.0

                processed_row = {
                    'branch_name': str(row_values[col_indices["branch_name"]] or '').strip(),
                    'student_name': str(student_name_cell).strip(),
                    'class': str(row_values[col_indices["class"]] or '').strip(),
                    'parent_name': str(row_values[col_indices["parent_name"]] or '').strip(),
                    'phone': str(row_values[col_indices["phone"]] or '').strip(),
                    'discount': final_discount,
                    'status': str(row_values[col_indices["status"]] or '').strip().lower(),
                }
                students_from_excel.append(processed_row)
        
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
        existing_students_map = {
            (s.branch_id, s.full_name.strip(), s.parent_name.strip(), s.group_name.strip(), s.phone.strip()): s.account_id
            for s in all_students
        }

        students_to_add = []
        account_ids_to_delete = []
        report_data = []

        for student_row in students_from_excel:
            report_row = {
                "Maktab (fillial nomi)": student_row['branch_name'],
                "O'quvchi F.I.Sh.": student_row['student_name'],
                "O'quvchi Sinf": student_row['class'],
                "Ota-onasi F.I.Sh.": student_row['parent_name'],
                "Ota-onasi Telefon": student_row['phone'],
                "Shartnoma Chegirma": student_row['discount'],
                "Shartnoma Status": student_row['status']
            }
            
            branch_name = student_row.get("branch_name", "")
            student_name = student_row.get("student_name", "")
            parent_name = student_row.get("parent_name", "")
            class_num = student_row.get("class", "")
            phone = student_row.get("phone", "")
            status = student_row.get("status", "")
            discount = student_row.get("discount", 0.0)

            branch_id = branch_map_by_name.get(branch_name.lower())
            if not branch_id:
                report_row["Qayta ishlash statusi"] = f"Xatolik: '{branch_name}' filiali topilmadi"
                report_data.append(report_row)
                continue

            group_name = f"{class_num}-sinf"
            student_key = (branch_id, student_name, parent_name, group_name, phone)
            student_exists = student_key in existing_students_map

            if status == 'amalda':
                if not student_exists:
                    students_to_add.append({
                        'branch_id': branch_id, 
                        'full_name': student_name, 
                        'parent_name': parent_name,
                        'group_name': group_name, 
                        'phone': phone, 
                        'discount_percent': discount
                    })
                    report_row["Qayta ishlash statusi"] = "Qo'shishga tayyorlandi"
                else:
                    report_row["Account ID"] = existing_students_map.get(student_key, '')
                    report_row["Qayta ishlash statusi"] = "O'zgarishsiz (allaqachon mavjud)"
            elif status == 'bekor':
                if student_exists:
                    account_id_to_del = existing_students_map[student_key]
                    account_ids_to_delete.append(account_id_to_del)
                    report_row["Account ID"] = account_id_to_del
                    report_row["Qayta ishlash statusi"] = "O'chirishga tayyorlandi"
                else:
                    report_row["Qayta ishlash statusi"] = "O'zgarishsiz (o'chirish uchun topilmadi)"
            else:
                report_row["Account ID"] = existing_students_map.get(student_key, '')
                report_row["Qayta ishlash statusi"] = f"O'zgarishsiz (status '{status}' noto'g'ri)"
            
            report_data.append(report_row)
        
        logger.info(f"Fayl tahlili yakunlandi. Qo'shish uchun: {len(students_to_add)} ta. O'chirish uchun: {len(account_ids_to_delete)} ta.")

        if students_to_add:
            created_students, err = grpc_client.create_students_batch(students_to_add)
            if err:
                update.message.reply_text(f"❌ O'quvchilarni ommaviy qo'shishda xatolik: {err}")
            else:
                created_map = {
                    (s.branch_id, s.full_name.strip(), s.parent_name.strip(), s.group_name.strip(), s.phone.strip()): s.account_id
                    for s in created_students
                }
                for row_dict in report_data:
                    if row_dict.get("Qayta ishlash statusi") == "Qo'shishga tayyorlandi":
                        class_num_val = row_dict.get("O'quvchi Sinf")
                        key = (
                            branch_map_by_name.get(row_dict.get("Maktab (fillial nomi)", "").lower()),
                            row_dict.get("O'quvchi F.I.Sh."),
                            row_dict.get("Ota-onasi F.I.Sh."),
                            f"{class_num_val}-sinf" if class_num_val else "",
                            row_dict.get("Ota-onasi Telefon")
                        )
                        if key in created_map:
                            row_dict["Account ID"] = created_map[key]
                            row_dict["Qayta ishlash statusi"] = "✅ Muvaffaqiyatli qo'shildi"
                        else:
                            row_dict["Qayta ishlash statusi"] = "❌ Qo'shishda xatolik"
        
        if account_ids_to_delete:
            success, err = grpc_client.delete_students_batch(account_ids_to_delete)
            if err:
                update.message.reply_text(f"❌ O'quvchilarni ommaviy o'chirishda xatolik: {err}")
            else:
                for row_dict in report_data:
                    if row_dict.get("Qayta ishlash statusi") == "O'chirishga tayyorlandi":
                        row_dict["Qayta ishlash statusi"] = "✅ Muvaffaqiyatli o'chirildi"

        if not report_data:
            update.message.reply_text("Faylda qayta ishlash uchun yangi ma'lumotlar topilmadi yoki barcha ma'lumotlar allaqachon bazada mavjud.")
            return cancel(update, context)
        
        final_columns = [
            "Maktab (fillial nomi)",
            "O'quvchi F.I.Sh.",
            "O'quvchi Sinf",
            "Account ID",
        ]
        full_df = pd.DataFrame(report_data)
        result_df = full_df.reindex(columns=final_columns)
        
        output_file = io.BytesIO()
        with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
            result_df.to_excel(writer, index=False, sheet_name='Natijalar')
        
        output_file.seek(0)

        update.message.reply_document(
            document=output_file,
            filename='qayta_ishlash_natijalari.xlsx',
            caption="✅ Bajarildi! Natijalar bilan tanishish uchun quyidagi faylni yuklab oling."
        )
    
    except Exception as e:
        logger.error(f"Excel faylni qayta ishlashda kutilmagan xatolik: {e}", exc_info=True)
        update.message.reply_text(f"❌ Faylni qayta ishlashda kutilmagan xatolik yuz berdi: {e}")
    
    start(update, context)
    return ConversationHandler.END



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
    from .core import BRANCH_NAME
    update.message.reply_text("Yangi filial nomini kiriting:", reply_markup=get_back_keyboard())
    return BRANCH_NAME

def get_branch_name(update: Update, context: CallbackContext):
    from .core import BRANCH_FEE
    if update.message.text == "⬅️ Orqaga": return cancel(update, context)
    context.user_data['branch_name'] = update.message.text
    update.message.reply_text("Filial uchun oylik to'lov miqdorini kiriting (faqat raqam, masalan: 300000):", reply_markup=get_back_keyboard())
    return BRANCH_FEE

def get_branch_fee(update: Update, context: CallbackContext):
    from .core import BRANCH_MFO
    if update.message.text == "⬅️ Orqaga": return cancel(update, context)
    context.user_data['branch_fee'] = update.message.text
    update.message.reply_text("Bank MFO kodini kiriting (masalan, 00450):", reply_markup=get_back_keyboard())
    return BRANCH_MFO

def get_branch_mfo(update: Update, context: CallbackContext):
    from .core import BRANCH_ACC
    if update.message.text == "⬅️ Orqaga": return cancel(update, context)
    context.user_data['branch_mfo'] = update.message.text
    update.message.reply_text("Bank hisob raqamini kiriting (masalan, 20206000100200300400):", reply_markup=get_back_keyboard())
    return BRANCH_ACC

def get_branch_account(update: Update, context: CallbackContext):
    from .core import BRANCH_MERCHANT
    if update.message.text == "⬅️ Orqaga": return cancel(update, context)
    context.user_data['branch_account'] = update.message.text
    update.message.reply_text("To'lov tizimi uchun Merchant ID'ni kiriting:", reply_markup=get_back_keyboard())
    return BRANCH_MERCHANT

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
    from .core import DELETE_BRANCH_SELECT
    branches, error = grpc_client.list_branches()
    if error or not branches:
        update.message.reply_text("Filiallar topilmadi yoki xatolik yuz berdi.")
        start(update, context)
        return ConversationHandler.END
    context.user_data['branches_list'] = branches
    branch_names = [branch.name for branch in branches]
    reply_markup = create_dynamic_keyboard(branch_names)
    update.message.reply_text("Qaysi filialni o'chirmoqchisiz?", reply_markup=reply_markup)
    return DELETE_BRANCH_SELECT

def get_branch_to_delete(update: Update, context: CallbackContext):
    from .core import DELETE_BRANCH_CONFIRM, DELETE_BRANCH_SELECT
    if update.message.text == "⬅️ Orqaga": return cancel(update, context)
    branch_name = update.message.text
    branches = context.user_data.get('branches_list', [])
    selected_branch = next((b for b in branches if b.name == branch_name), None)
    if not selected_branch:
        update.message.reply_text("Noto'g'ri filial tanlandi. Iltimos, qaytadan urinib ko'ring.")
        return DELETE_BRANCH_SELECT
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
    return DELETE_BRANCH_CONFIRM

def confirm_branch_delete(update: Update, context: CallbackContext):
    from .core import DELETE_BRANCH_CONFIRM
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
    return DELETE_BRANCH_CONFIRM


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
        message += f"▪️ *{student.full_name}*\n"
        message += f"   - Hisob raqami: `{student.account_id}`\n"
        message += f"   - Filial: {branch_name}\n"
        message += f"   - Guruh: {student.group_name}\n\n"
    update.message.reply_text(message, parse_mode='Markdown')

@admin_required
def add_student_start(update: Update, context: CallbackContext):
    from .core import STUDENT_BRANCH
    branches, error = grpc_client.list_branches()
    if error or not branches:
        update.message.reply_text("Filiallar topilmadi yoki xatolik yuz berdi. Avval filial qo'shing.")
        start(update, context)
        return ConversationHandler.END
    context.user_data['branches_list'] = branches
    branch_names = [branch.name for branch in branches]
    reply_markup = create_dynamic_keyboard(branch_names)
    update.message.reply_text("O'quvchi qaysi filialga tegishli ekanini tanlang:", reply_markup=reply_markup)
    return STUDENT_BRANCH

def get_student_branch(update: Update, context: CallbackContext):
    from .core import STUDENT_PARENT, STUDENT_BRANCH
    if update.message.text == "⬅️ Orqaga": return cancel(update, context)
    branch_name = update.message.text
    branches = context.user_data.get('branches_list', [])
    selected_branch = next((b for b in branches if b.name == branch_name), None)
    if not selected_branch:
        update.message.reply_text("Noto'g'ri filial tanlandi. Iltimos, qaytadan urinib ko'ring.")
        return STUDENT_BRANCH
    context.user_data['student_branch_id'] = selected_branch.id
    update.message.reply_text("Ota-onasining ismini kiriting (masalan, Olimov A.):", reply_markup=get_back_keyboard())
    return STUDENT_PARENT

def get_student_parent_name(update: Update, context: CallbackContext):
    from .core import STUDENT_FULLNAME
    if update.message.text == "⬅️ Orqaga": return cancel(update, context)
    context.user_data['student_parent_name'] = update.message.text
    update.message.reply_text("O'quvchining to'liq F.I.Sh. ni kiriting:", reply_markup=get_back_keyboard())
    return STUDENT_FULLNAME

def get_student_full_name(update: Update, context: CallbackContext):
    from .core import STUDENT_GROUP_NAME
    if update.message.text == "⬅️ Orqaga": return cancel(update, context)
    context.user_data['student_full_name'] = update.message.text
    update.message.reply_text("O'quvchining guruh/sinf nomini kiriting (masalan, '7-sinf' yoki 'Frontend-dasturlash'):", reply_markup=get_back_keyboard())
    return STUDENT_GROUP_NAME

def get_student_group_name(update: Update, context: CallbackContext):
    from .core import STUDENT_PHONE
    if update.message.text == "⬅️ Orqaga": return cancel(update, context)
    context.user_data['student_group_name'] = update.message.text
    update.message.reply_text("O'quvchining telefon raqamini kiriting (+998...):", reply_markup=get_back_keyboard())
    return STUDENT_PHONE

def get_student_phone(update: Update, context: CallbackContext):
    from .core import STUDENT_DISCOUNT
    if update.message.text == "⬅️ Orqaga": return cancel(update, context)
    context.user_data['student_phone'] = update.message.text
    update.message.reply_text("Chegirma foizini kiriting (agar yo'q bo'lsa, 0 kiriting):", reply_markup=get_back_keyboard())
    return STUDENT_DISCOUNT

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
    from .core import DELETE_STUDENT_ACCOUNT_ID
    update.message.reply_text("O'chiriladigan o'quvchining hisob raqamini kiriting (masalan, YM19857):", reply_markup=get_back_keyboard())
    return DELETE_STUDENT_ACCOUNT_ID

def get_student_account_id_to_delete(update: Update, context: CallbackContext):
    from .core import DELETE_STUDENT_ACCOUNT_ID
    if update.message.text == "⬅️ Orqaga": return cancel(update, context)
    account_id = update.message.text.strip()
    if not account_id.upper().startswith("YM"):
        update.message.reply_text("Noto'g'ri format. Hisob raqami 'YM' bilan boshlanishi kerak. Qaytadan kiriting:", reply_markup=get_back_keyboard())
        return DELETE_STUDENT_ACCOUNT_ID
    success, error = grpc_client.delete_student_by_account_id(account_id)
    if error:
        update.message.reply_text(f"❌ Xatolik: {error}")
    else:
        update.message.reply_text(f"✅ O'quvchi (hisob raqami: {account_id}) muvaffaqiyatli o'chirildi.")
    start(update, context)
    return ConversationHandler.END


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