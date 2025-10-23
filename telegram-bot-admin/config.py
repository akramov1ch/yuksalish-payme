from pydantic_settings import BaseSettings


EXCEL_CONFIGS = [
    {
        "sheet_index": 0,
        "start_row": 4,  # Ma'lumotlar 5-qatordan boshlanadi (indeks: 4)
        "columns": {
            "branch_name": 1,   # 'B' ustuni - Maktab (filial nomi)
            "student_name": 10, # 'K' ustuni - F.I.Sh. (O'quvchi)
            "class": 11,        # 'L' ustuni - Sinf
            "parent_name": 12,  # 'M' ustuni - Ota yoki onasining F.I.Sh.
            "phone": 14,        # 'O' ustuni - Otasi yoki onasining telefon raqami
            "discount": 5,      # 'F' ustuni - chegirma (foizda)
            "status": 7,        # 'H' ustuni - statusi
        }
    },
    # --- 2-jadval (1-indeks) ---
    {
        "sheet_index": 1,
        "start_row": 4, # <-- BU YERNI O'ZINGIZNING 2-JADVALINGIZGA MOSLAB O'ZGARTIRING
        "columns": {
            "branch_name": 1, "student_name": 10, "class": 11, "parent_name": 12,
            "phone": 14, "discount": 5, "status": 7
        }
    },
    # --- 3-jadval (2-indeks) ---
    {
        "sheet_index": 2,
        "start_row": 4, # <-- BU YERNI O'ZINGIZNING 3-JADVALINGIZGA MOSLAB O'ZGARTIRING
        "columns": {
            "branch_name": 1, "student_name": 10, "class": 11, "parent_name": 12,
            "phone": 14, "discount": 5, "status": 7
        }
    },
    # --- 4-jadval (3-indeks) ---
    {
        "sheet_index": 3,
        "start_row": 4, # <-- BU YERNI O'ZINGIZNING 4-JADVALINGIZGA MOSLAB O'ZGARTIRING
        "columns": {
            "branch_name": 1, "student_name": 10, "class": 11, "parent_name": 12,
            "phone": 14, "discount": 5, "status": 7
        }
    },
    # --- 5-jadval (4-indeks) ---
    {
        "sheet_index": 4,
        "start_row": 4, # <-- BU YERNI O'ZINGIZNING 5-JADVALINGIZGA MOSLAB O'ZGARTIRING
        "columns": {
            "branch_name": 1, "student_name": 10, "class": 11, "parent_name": 12,
            "phone": 14, "discount": 5, "status": 7
        }
    },
    # --- 6-jadval (5-indeks) ---
    {
        "sheet_index": 5,
        "start_row": 4, # <-- BU YERNI O'ZINGIZNING 6-JADVALINGIZGA MOSLAB O'ZGARTIRING
        "columns": {
            "branch_name": 1, "student_name": 10, "class": 11, "parent_name": 12,
            "phone": 14, "discount": 5, "status": 7
        }
    },
    # --- 7-jadval (6-indeks) ---
    {
        "sheet_index": 6,
        "start_row": 4, # <-- BU YERNI O'ZINGIZNING 7-JADVALINGIZGA MOSLAB O'ZGARTIRING
        "columns": {
            "branch_name": 1, "student_name": 10, "class": 11, "parent_name": 12,
            "phone": 14, "discount": 5, "status": 7
        }
    },
    # --- 8-jadval (7-indeks) ---
    {
        "sheet_index": 7,
        "start_row": 4, # <-- BU YERNI O'ZINGIZNING 8-JADVALINGIZGA MOSLAB O'ZGARTIRING
        "columns": {
            "branch_name": 1, "student_name": 10, "class": 11, "parent_name": 12,
            "phone": 14, "discount": 5, "status": 7
        }
    },
    # --- 9-jadval (8-indeks) ---
    {
        "sheet_index": 8,
        "start_row": 4, # <-- BU YERNI O'ZINGIZNING 9-JADVALINGIZGA MOSLAB O'ZGARTIRING
        "columns": {
            "branch_name": 1, "student_name": 10, "class": 11, "parent_name": 12,
            "phone": 14, "discount": 5, "status": 7
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