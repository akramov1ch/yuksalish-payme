from pydantic_settings import BaseSettings

# ====================================================================
# EXCEL FAYLNI O'QISH UCHUN KONFIGURATSIYA
# ====================================================================
# Har bir lug'at Excel faylidagi bitta list (sheet) uchun mas'ul.
# "sheet_index": Listning tartib raqami (0 dan boshlanadi).
# "start_row": Ma'lumotlar boshlanadigan qator raqami (1 dan boshlanadi, lekin kodda 0-indeksga o'giriladi).
# "columns": Kerakli ustunlarning tartib raqamlari (0 dan boshlanadi).
# Masalan, 'B' ustuni 1-indeksga, 'C' ustuni 2-indeksga to'g'ri keladi.

EXCEL_CONFIGS = [
    {
        "sheet_index": 0,
        "start_row": 4,  # Ma'lumotlar 5-qatordan boshlanadi (indeks: 4)
        "columns": {
            "branch_name": 1,   # 'B' ustuni - Maktab (filial nomi)
            "contract_number": 2, # 'C' ustuni - Shartnoma raqami
            "student_name": 10, # 'K' ustuni - F.I.Sh. (O'quvchi)
            "class": 11,        # 'L' ustuni - Sinf
            "parent_name": 12,  # 'M' ustuni - Ota yoki onasining F.I.Sh.
            "phone": 14,        # 'O' ustuni - Otasi yoki onasining telefon raqami
            "discount": 5,      # 'F' ustuni - chegirma (foizda)
            "status": 7,        # 'H' ustuni - statusi
        }
    },
    # --- Agar boshqa listlar ham xuddi shu formatda bo'lsa, ularni qo'shing ---
    {
        "sheet_index": 1,
        "start_row": 4,
        "columns": {
            "branch_name": 1, "contract_number": 2, "student_name": 10, "class": 11, 
            "parent_name": 12, "phone": 14, "discount": 5, "status": 7
        }
    },
    {
        "sheet_index": 2,
        "start_row": 4,
        "columns": {
            "branch_name": 1, "contract_number": 2, "student_name": 10, "class": 11, 
            "parent_name": 12, "phone": 14, "discount": 5, "status": 7
        }
    },
    {
        "sheet_index": 3,
        "start_row": 4,
        "columns": {
            "branch_name": 1, "contract_number": 2, "student_name": 10, "class": 11, 
            "parent_name": 12, "phone": 14, "discount": 5, "status": 7
        }
    },
    {
        "sheet_index": 4,
        "start_row": 4,
        "columns": {
            "branch_name": 1, "contract_number": 2, "student_name": 10, "class": 11, 
            "parent_name": 12, "phone": 14, "discount": 5, "status": 7
        }
    },
    {
        "sheet_index": 5,
        "start_row": 4,
        "columns": {
            "branch_name": 1, "contract_number": 2, "student_name": 10, "class": 11, 
            "parent_name": 12, "phone": 14, "discount": 5, "status": 7
        }
    },
    {
        "sheet_index": 6,
        "start_row": 4,
        "columns": {
            "branch_name": 1, "contract_number": 2, "student_name": 10, "class": 11, 
            "parent_name": 12, "phone": 14, "discount": 5, "status": 7
        }
    },
    {
        "sheet_index": 7,
        "start_row": 4,
        "columns": {
            "branch_name": 1, "contract_number": 2, "student_name": 10, "class": 11, 
            "parent_name": 12, "phone": 14, "discount": 5, "status": 7
        }
    },
    {
        "sheet_index": 8,
        "start_row": 4,
        "columns": {
            "branch_name": 1, "contract_number": 2, "student_name": 10, "class": 11, 
            "parent_name": 12, "phone": 14, "discount": 5, "status": 7
        }
    }
]
# ====================================================================


class Settings(BaseSettings):
    telegram_bot_token: str
    super_admin_id: int
    grpc_go_server_address: str
    grpc_bot_server_port: int

    class Config:
        env_file = '.env'
        env_file_encoding = 'utf-8'

settings = Settings()