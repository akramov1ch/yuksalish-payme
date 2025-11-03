from pydantic_settings import BaseSettings
from typing import List

SHEET_COLUMNS_CONFIG = {
    "branch_name": 1,       # 'B' ustuni - Maktab (filial nomi)
    "contract_number": 2,   # 'C' ustuni - Shartnoma raqami
    "discount": 5,          # 'F' ustuni - Chegirma (foizda)
    "status": 7,            # 'H' ustuni - Statusi ('amalda' yoki 'bekor')
    "student_name": 10,     # 'K' ustuni - F.I.Sh. (O'quvchi)
    "class": 11,            # 'L' ustuni - Sinf
    "parent_name": 12,      # 'M' ustuni - Ota yoki onasining F.I.Sh.
    "phone": 14,            # 'O' ustuni - Otasi yoki onasining telefon raqami
    "account_id": 15,       # 'P' ustuni - Account ID (bot tomonidan to'ldiriladi)
    "uuid": 16,             # 'Q' ustuni - UUID (bot tomonidan to'ldiriladi)
}

# Ma'lumotlar boshlanadigan qator raqami
START_ROW = 3

class Settings(BaseSettings):
    telegram_bot_token: str
    super_admin_id: int
    grpc_go_server_address: str
    grpc_bot_server_port: int
    
    # <<< O'ZGARTIRILGAN QISM BOSHI >>>
    google_spreadsheet_id: str
    google_worksheet_names: str
    google_creds_file: str

    @property
    def google_worksheet_name_list(self) -> List[str]:
        """Varaq nomlari satrini toza ro'yxatga o'giradi."""
        return [name.strip() for name in self.google_worksheet_names.split(',') if name.strip()]
    # <<< O'ZGARTIRILGAN QISM TUGADI >>>

    class Config:
        env_file = '.env'
        env_file_encoding = 'utf-8'

settings = Settings()