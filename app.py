# app.py
# Court Case Data Fetcher 
# Streamlit + Playwright + SQLite

import asyncio
import os
import re
import sqlite3
import time
from datetime import datetime
import pandas as pd

import streamlit as st
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

# Windows fix
try:
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
except (AttributeError, NotImplementedError):
    pass

# --- Playwright in streamlint ---
if "playwright" not in st.session_state:
    try:
        st.session_state.playwright = sync_playwright().start()
        st.session_state.browser = st.session_state.playwright.chromium.launch(headless=False)
        st.session_state.page = st.session_state.browser.new_page()
    except Exception as e:
        st.error(f"Playwright shuru nahi ho saka: {e}")
        st.stop()

# ---------- Constants ----------
ECOURTS_START_URL = "https://services.ecourts.gov.in/ecourtindia_v6/"
DB_PATH = "queries.db"
CASE_TYPES = ["CR", "CS", "CIVIL", "CRIMINAL", "MISC", "M.A.", "EA", "EX", "FA", "SA"]
EMBLEM_URL = "https://upload.wikimedia.org/wikipedia/commons/thumb/5/55/Emblem_of_India.svg/120px-Emblem_of_India.svg.png"

# ---------- Utilities (Backend Logic) ----------
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS queries (
            id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, court TEXT NOT NULL,
            case_type TEXT NOT NULL, case_number TEXT NOT NULL, filing_year TEXT NOT NULL,
            captcha_used TEXT, result_ok INTEGER NOT NULL, latest_pdf TEXT, html TEXT
        )
        """
    )
    conn.commit()
    conn.close()

def log_query(court, case_type, case_number, filing_year, captcha_used, result_ok, latest_pdf, html):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO queries (ts, court, case_type, case_number, filing_year, captcha_used, result_ok, latest_pdf, html) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (datetime.now().isoformat(timespec="seconds"), court, case_type, case_number, filing_year, captcha_used or "", 1 if result_ok else 0, latest_pdf or "", html or ""),
    )
    conn.commit()
    conn.close()

def get_browser_page():
    if "page" not in st.session_state or st.session_state.page.is_closed():
        if "browser" not in st.session_state or not st.session_state.browser.is_connected():
            reset_browser()
        st.session_state.page = st.session_state.browser.new_page()
    return st.session_state.page

def goto_case_number_page(page):
    page.goto(ECOURTS_START_URL, timeout=60000, wait_until="load")
    possible_texts = ["Case Status", "Case Number"]
    for t in possible_texts:
        try:
            page.get_by_text(t, exact=False).first.click(timeout=3000)
        except Exception:
            pass

def select_state_and_district(page, state_name="Bihar", district_name="Gaya"):
    try:
        page.select_option("select[id*='state']", label=state_name, timeout=5000)
        time.sleep(1)
        page.select_option("select[id*='district']", label=district_name, timeout=5000)
        time.sleep(1)
    except Exception:
        pass

def capture_captcha_image(page):
    loc = page.locator("img#captcha_image, img[id*='captcha']").first
    return loc.screenshot(timeout=5000)

def fill_form_and_submit(page, case_type, case_number, filing_year, captcha_text):
    page.select_option("select[id*='caseType'], select[id*='ctype']", label=case_type)
    page.fill("input[id*='caseNo'], input[placeholder*='Case Number' i]", case_number)
    year_selector = "select[id*='year']"
    if page.locator(year_selector).count() > 0:
        page.select_option(year_selector, value=str(filing_year))
    else:
        page.fill("input[id*='year']", str(filing_year))
    page.fill("input[id*='captcha']", captcha_text.strip())
    page.click("button:has-text('Search'), button:has-text('Get Status')")
    page.wait_for_timeout(3000)
    body = page.content()
    return "Invalid CAPTCHA" not in body and "Invalid Case Details" not in body

def parse_results(page):
    html = page.content()
    def extract_text(pattern):
        m = re.search(pattern, html, flags=re.I | re.S)
        return re.sub(r"<[^>]+>|\s+", " ", m.group(1)).strip() if m else ""

    petitioner = extract_text(r"Petitioner\s*</[^>]+>\s*<[^>]+>\s*(.*?)</")
    respondent = extract_text(r"Respondent\s*</[^>]+>\s*<[^>]+>\s*(.*?)</")
    filing_date = extract_text(r"Filing\s*Date\s*[:\-]\s*(.*?)</")
    next_hearing = extract_text(r"Next\s*Hearing\s*Date\s*[:\-]\s*(.*?)</")
    pdf_link_match = re.search(r'href\s*=\s*"([^"]+\.pdf[^"]*)"', html, flags=re.I)
    pdf_link = ""
    if pdf_link_match:
        pdf_link = pdf_link_match.group(1)
        if pdf_link.startswith("/"):
            pdf_link = "https://services.ecourts.gov.in" + pdf_link

    success = any([petitioner, respondent, filing_date])
    return {"success": success, "petitioner": petitioner, "respondent": respondent, "filing_date": filing_date, "next_hearing": next_hearing, "latest_pdf": pdf_link, "html": html}

def reset_browser():
    for k in ("page", "browser", "playwright", "captcha_png"):
        if k in st.session_state:
            try:
                if hasattr(st.session_state[k], 'close'): st.session_state[k].close()
                elif hasattr(st.session_state[k], 'stop'): st.session_state[k].stop()
            except Exception: pass
            del st.session_state[k]

def get_query_log():
    if not os.path.exists(DB_PATH):
        return pd.DataFrame()
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT ts as Timestamp, case_type, case_number, filing_year, result_ok, latest_pdf FROM queries ORDER BY id DESC", conn)
    conn.close()
    return df

# ---------- Streamlit App ----------
st.set_page_config(page_title="Court Case Data Fetcher", page_icon="⚖️", layout="wide", initial_sidebar_state="expanded")

# --- CUSTOM CSS ---
st.markdown("""
<style>
    /* Main app styling */
    .stApp {
        background-color: #F8F9FA;
    }
    /* Sidebar styling */
    [data-testid="stSidebar"] {
        background-color: #FFFFFF;
        border-right: 1px solid #E6E9EF;
    }
    /* Header styling */
    .app-header {
        background-color: #FFFFFF;
        padding: 1rem;
        border-radius: 10px;
        border: 1px solid #E6E9EF;
        margin-bottom: 1rem;
    }
    .app-header h2 {
        margin: 0;
        color: #B92B27;
    }
    .app-header p {
        margin: 0;
        color: #555;
    }
    .breadcrumb {
        color: #888;
        font-size: 0.9rem;
    }
    /* Footer Styling */
    .footer {
        position: fixed;
        left: 0;
        bottom: 0;
        width: 100%;
        background-color: #212529; /* Dark background */
        color: #A9A9A9; /* Light grey text */
        text-align: center;
        padding: 20px 10px;
        font-size: 0.8rem;
    }
    .footer a {
        color: #FFFFFF; /* White links */
        text-decoration: none;
        margin: 0 10px;
    }
    .footer a:hover {
        text-decoration: underline;
    }
    .footer-logos img {
        height: 35px;
        margin: 10px 15px;
        filter: grayscale(100%); /* Grayscale logos */
        opacity: 0.6;
    }
</style>
""", unsafe_allow_html=True)

# --- SIDEBAR: INPUTS AND CONTROLS ---
with st.sidebar:
    st.header("⚖️ Control Panel")
    st.markdown("---")

    st.subheader("Browser Actions")
    if st.button("Initialize / Refresh Portal", use_container_width=True):
        with st.spinner("Initializing portal..."):
            try:
                page = get_browser_page()
                goto_case_number_page(page)
                select_state_and_district(page, "Bihar", "Gaya")
                st.success(" Portal initialized.")
                st.rerun()
            except Exception as e:
                st.error(f" Failed to initialize: {e}")

    if st.button("Reset Browser Session", use_container_width=True, type="secondary"):
        reset_browser()
        st.info("Browser session reset.")
        st.rerun()

    st.markdown("---")
    
    with st.form(key="case_form"):
        st.subheader("Search Parameters")
        case_type = st.selectbox("Case Type", CASE_TYPES, index=0)
        case_number = st.text_input("Case Number", placeholder="e.g., 123")
        filing_year = st.selectbox("Filing Year", options=range(datetime.now().year, 1990, -1))
        st.divider()
        captcha_text = st.text_input("Enter CAPTCHA from main panel", placeholder="Text from the image")
        submitted = st.form_submit_button(" Fetch Case Details", use_container_width=True, type="primary")

# --- MAIN PAGE: HEADER, CAPTCHA, AND RESULTS ---
with st.container():
    st.markdown("<p style='text-align:center; color:#555;'>ई-कमेटी, उच्चतम न्यायालय, भारत | E-COMMITTEE, SUPREME COURT OF INDIA</p>", unsafe_allow_html=True)
    st.divider()
    
    header_cols = st.columns([1, 4])
    with header_cols[0]:
        st.image(EMBLEM_URL, width=100)
    with header_cols[1]:
        st.markdown("<div class='app-header'><h2>जिला अदालत गया | District Court Gaya</h2><p>e-Courts Mission Mode Project</p></div>", unsafe_allow_html=True)
    
    st.markdown("<p class='breadcrumb'>Home > Services > Case Status</p>", unsafe_allow_html=True)
    st.divider()

col_display1, col_display2 = st.columns(2, gap="large")

with col_display1:
    with st.container(border=True):
        st.subheader("CAPTCHA Image")
        try:
            page = get_browser_page()
            captcha_png = capture_captcha_image(page)
            if captcha_png:
                st.image(captcha_png, use_column_width=True)
                st.session_state.captcha_png = captcha_png
            elif "captcha_png" in st.session_state:
                 st.image(st.session_state.captcha_png, use_column_width=True)
            else:
                st.info("Click 'Initialize / Refresh Portal' in the sidebar to load CAPTCHA.")
        except Exception:
             st.info("Click 'Initialize / Refresh Portal' to load CAPTCHA.")

if submitted:
    # Results will be displayed in the second column
    with col_display2:
        with st.container(border=True):
            st.subheader("Case Results")
            if not all([case_number, str(filing_year), captcha_text]):
                st.error("Please fill all fields in the sidebar.")
            else:
                with st.spinner("Submitting details and fetching case data..."):
                    try:
                        page = get_browser_page()
                        ok = fill_form_and_submit(page, case_type, case_number.strip(), str(filing_year), captcha_text.strip())
                        if not ok:
                            st.error("Invalid details or CAPTCHA. Please try again.")
                        else:
                            st.session_state.parsed_results = parse_results(page)
                            try:
                                init_db()
                                log_query(
                                    court="Gaya District Court (eCourts)", case_type=case_type,
                                    case_number=case_number.strip(), filing_year=str(filing_year),
                                    captcha_used=captcha_text.strip(), result_ok=True,
                                    latest_pdf=st.session_state.parsed_results.get("latest_pdf", ""),
                                    html=st.session_state.parsed_results.get("html", ""),
                                )
                            except Exception as dbe:
                                st.warning(f"Could not log to database: {dbe}")
                    except Exception as e:
                        st.error(f"An error occurred during fetching: {e}")

            # Display results if they exist in session state
            if "parsed_results" in st.session_state and st.session_state.parsed_results:
                parsed = st.session_state.parsed_results
                if not parsed["success"]:
                    st.error("Case not found or page structure changed.")
                else:
                    st.success("Case Details Fetched!")
                    dates_col1, dates_col2 = st.columns(2)
                    with dates_col1:
                        st.metric(label="Filing Date", value=parsed.get("filing_date", "N/A"))
                    with dates_col2:
                        st.metric(label="Next Hearing Date", value=parsed.get("next_hearing", "N/A"))
                    st.divider()
                    if parsed.get("petitioner") or parsed.get("respondent"):
                        st.write("**Parties**")
                        st.text(f"Petitioner: {parsed.get('petitioner', 'N/A')}")
                        st.text(f"Respondent: {parsed.get('respondent', 'N/A')}")
                    if parsed.get("latest_pdf"):
                        st.divider()
                        st.write("**Documents**")
                        st.markdown(f"📄 [Download Latest Order/Judgment PDF]({parsed['latest_pdf']})")
                    st.info("Query has been logged to the database.")
            else:
                st.info("Results will be displayed here after a successful search.")

# Extra Feature: Query Log Display
st.divider()
st.header("🗂️ Previous Search Log")
try:
    log_df = get_query_log()
    if not log_df.empty:
        st.dataframe(log_df, use_container_width=True)
    else:
        st.info("No searches have been logged to the database yet.")
except Exception as e:
    st.warning(f"Could not load query log from database: {e}")

# --- Footer ---
footer_html = """
<div class="footer">
    <div class="footer-links">
        <a href="#">Feedback</a> |
        <a href="#">Website Policies</a> |
        <a href="#">Contact Us</a> |
        <a href="#">Help</a> |
        <a href="#">Disclaimer</a>
    </div>
    <p>
        Content Owned by Gaya District Court<br>
        Developed and hosted by National Informatics Centre,
        Ministry of Electronics & Information Technology, Government of India<br>
        Last Updated: Jul 21, 2025
    </p>
    <div class="footer-logos">
        <img src="https://www.swaas.gov.in/assets/images/Swaas_final_logo.png" alt="Swaas Logo">
        <img src="https://upload.wikimedia.org/wikipedia/en/thumb/9/9a/Digital_India_logo.svg/200px-Digital_India_logo.svg.png" alt="Digital India Logo">
        <img src="https://doj.gov.in/wp-content/uploads/2022/12/logo-dark.png" alt="Department of Justice Logo">
        <img src="https://cdnbbsr.s3waas.gov.in/s3d3d9446802a44259755d38e6d163e820/uploads/2018/05/2018050186.png" alt="eCommittee Logo">
        <img src="https://www.indiacode.nic.in/images/nic-logo-nic-logo-text-fina-16.png" alt="India Code Logo">
        <img src="https://upload.wikimedia.org/wikipedia/commons/thumb/a/a2/National_Informatics_Centre_logo.svg/150px-National_Informatics_Centre_logo.svg.png" alt="NIC Logo">
    </div>
</div>
"""

st.markdown(footer_html, unsafe_allow_html=True)
