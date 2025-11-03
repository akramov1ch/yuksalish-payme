# test_gspread.py
import gspread
from google.oauth2.service_account import Credentials
from config import settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_connection():
    logger.info("Testing Google Sheets connection...")
    try:
        # 1. Ulanishni sozlash
        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        creds = Credentials.from_service_account_file(settings.google_creds_file, scopes=scopes)
        client = gspread.authorize(creds)
        
        logger.info(f"Successfully authorized with service account: {creds.service_account_email}")

        # 2. Faylni ID orqali ochish
        spreadsheet_id = settings.google_spreadsheet_id
        logger.info(f"Opening spreadsheet with ID: {spreadsheet_id}")
        spreadsheet = client.open_by_key(spreadsheet_id)
        logger.info(f"Successfully opened spreadsheet: '{spreadsheet.title}'")

        # 3. Barcha varaqlar ro'yxatini olish
        worksheets = spreadsheet.worksheets()
        worksheet_titles = [ws.title for ws in worksheets]
        logger.info(f"Found worksheets: {worksheet_titles}")

        # 4. Kerakli varaqlar mavjudligini tekshirish
        required_sheets = settings.google_worksheet_name_list
        logger.info(f"Checking for required worksheets: {required_sheets}")
        
        all_found = True
        for sheet_name in required_sheets:
            if sheet_name in worksheet_titles:
                logger.info(f"  -> SUCCESS: Worksheet '{sheet_name}' found!")
            else:
                logger.error(f"  -> FAILED: Worksheet '{sheet_name}' NOT FOUND!")
                all_found = False
        
        if all_found:
            print("\n✅ SUCCESS: All required worksheets were found in the spreadsheet.")
        else:
            print("\n❌ FAILED: One or more required worksheets were not found. Please check names and sharing settings.")

    except gspread.exceptions.SpreadsheetNotFound:
        logger.error("SpreadsheetNotFound: The spreadsheet with the given ID was not found.")
        print("\n❌ FAILED: Spreadsheet not found. Please check GOOGLE_SPREADSHEET_ID in your .env file and ensure the service account has access.")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}", exc_info=True)
        print(f"\n❌ FAILED: An unexpected error occurred: {e}")

if __name__ == "__main__":
    test_connection()