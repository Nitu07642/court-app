import asyncio
from playwright.async_api import async_playwright
import os
import sqlite3
from datetime import datetime

# Windows + naye Python version ke liye zaroori fix
asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

DB_PATH = "queries.db"

# --- Database Functions ---
def setup_database():
    """Ek SQLite database aur table banata hai agar woh pehle se nahi hai."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS case_logs (
            id INTEGER PRIMARY KEY,
            timestamp TEXT NOT NULL,
            case_type_value TEXT,
            case_year TEXT,
            result_ok INTEGER NOT NULL,
            saved_pdf_path TEXT,
            raw_html TEXT
        )
    """)
    conn.commit()
    conn.close()

def log_query(case_type_value, case_year, result_ok, pdf_path, html):
    """Har safal fetch ko database mein log karta hai."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        "INSERT INTO case_logs (timestamp, case_type_value, case_year, result_ok, saved_pdf_path, raw_html) VALUES (?, ?, ?, ?, ?, ?)",
        (timestamp, case_type_value, case_year, 1 if result_ok else 0, pdf_path, html)
    )
    conn.commit()
    conn.close()


# --- FINAL SUBMISSION SCRIPT (Gaya - With All Features) ---
async def scrape_court_data():
    setup_database()

    # --- STEP 1: Script chalaane se pehle, in values ko manual रूप से bharein ---
    MANUAL_CAPTCHA = "4piyU" 
    CASE_YEAR = "2024"       
    CASE_TYPE_VALUE = "100" # Commercial Suit ke liye

    # --- STEP 2: Yahan 'View' button ka selector daalein ---
    VIEW_BUTTON_SELECTOR = ".viewCnrDetails" # Yeh result page par 'View' button ka selector hai
    
    print("--- Starting Gaya Court Scraper (Search by Case Type) ---")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()

        try:
            print(f"Fetching details for Year: {CASE_YEAR}...")
            await page.goto("https://gaya.dcourts.gov.in/case-status-search-by-case-type/", timeout=60000)

            # Dropdowns ke options load hone ke liye 8 second ka pause
            print("Page loaded. Waiting 8 seconds for dynamic content to load...")
            await page.wait_for_timeout(8000)

            print("Filling form details...")
            await page.select_option('#est_code', value="BRGA01,BRGA03,BRGA02,BRGA05")
            await page.select_option('#case_type', value=CASE_TYPE_VALUE)
            await page.fill('#year', CASE_YEAR)
            await page.click('#rad_pending') 
            await page.fill("#captcha", MANUAL_CAPTCHA)

            print("Submitting form...")
            await page.click("#search-button")
            
            print("Waiting 10 seconds for results list to load...")
            await page.wait_for_timeout(10000)

            print("--- Checking for Results ---")
            
            error_message_visible = await page.locator("text=Invalid Captcha, text=No records found").first.is_visible(timeout=2000)
            if error_message_visible:
                print("\n❌ ERROR: Invalid CAPTCHA ya 'No records found' message mila.")
            else:
                print("\n✅ SUCCESS: Case list found. Clicking 'View' button...")
                
                first_result_view_button = page.locator(f"#showList {VIEW_BUTTON_SELECTOR}").first
                
                if await first_result_view_button.count() > 0:
                    await first_result_view_button.click()
                    print("Waiting for details page...")
                    await page.wait_for_timeout(5000)

                    print("--- Saving Page as PDF ---")
                    pdf_path = "Gaya-Case-Details.pdf"
                    await page.pdf(path=pdf_path)
                    
                    # Database mein log karein
                    html_content = await page.content()
                    log_query(CASE_TYPE_VALUE, CASE_YEAR, True, os.path.abspath(pdf_path), html_content)
                    print(f"\n📄 SUCCESS! Page saved as '{pdf_path}' and query logged to database.")
                else:
                    print("❌ ERROR: 'View' button nahi mila.")
                    
        except Exception as e:
            print(f"\nAn error occurred: {e}")
        finally:
            print("\nBrowser 60 second mein band ho jayega...")
            await page.wait_for_timeout(60000)
            await browser.close()

if __name__ == "__main__":
    asyncio.run(scrape_court_data())