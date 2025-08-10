# court-app

# ⚖️ Court-Data Fetcher Mini-Dashboard

A Python-based tool to fetch case metadata and judgments from the eCourts portal for the Gaya District Court. This project is a submission for Task 1 of the internship selection process.

![Streamlit UI](<<img width="1919" height="872" alt="Screenshot 2025-08-10 143241" src="https://github.com/user-attachments/assets/723d1c75-0f45-4e0d-a2c0-230f7b59bbe1" />
>
)


---

## 📋 Objective

The goal of this task is to build a small application that allows a user to select a Case Type and Case Number for a specific Indian court, then fetches and displays the case metadata and the latest orders or judgments.

## ✨ Key Features

-   **Browser Automation:** Uses Playwright to reliably navigate the JavaScript-heavy eCourts portal.
-   **Data Scraping:** Parses the results page to extract key case details.
-   **PDF Generation:** Clicks through to the details page and saves the final case status as a PDF document.
-   **Database Logging:** Logs every successful query into an SQLite database (`queries.db`) for record-keeping.
-   **UI Mockup:** A well-designed Streamlit UI (`app.py`) was created to demonstrate the intended user experience.

## 🛠️ Project Approach & Technical Challenges

My initial approach was to build a fully interactive web application using Streamlit (`app.py`). The UI for this is included in the repository.

However, during development, I encountered a persistent and unresolvable technical issue with Streamlit's `session_state` management on my local machine. This prevented the Playwright browser session from persisting between user interactions, which is critical for a multi-step process like filling a form and then entering a CAPTCHA.

To meet the deadline and still demonstrate the core technical competency of the task, I pivoted to a **semi-automated script (`scraper.py`)**. This script successfully implements the required browser automation, handles the form submission (with manual CAPTCHA input), navigates to the details page, and saves the final report as a PDF.

This two-file approach demonstrates both my UI design skills (`app.py`) and my ability to overcome technical obstacles to deliver a functional backend solution (`scraper.py`).

## 🚀 Technology Stack

-   **Language:** Python 3.11
-   **Web Scraping:** Playwright (Async)
-   **UI Framework:** Streamlit (for the UI mockup)
-   **Database:** SQLite3

## ⚙️ Setup and Usage

To run this project, please follow these steps:

1.  **Clone the repository:**
    ```bash
    git clone [https://github.com/YourUsername/court-app.git](https://github.com/YourUsername/court-app.git)
    cd court-app
    ```

2.  **Create and activate a virtual environment (Python 3.11 recommended):**
    ```bash
    py -3.11 -m venv venv
    venv\Scripts\activate
    ```

3.  **Install the required libraries:**
    ```bash
    pip install streamlit playwright pandas
    ```

4.  **Install Playwright's browsers:**
    ```bash
    playwright install
    ```

5.  **Run the script:**
    -   Open the `scraper.py` file.
    -   Manually update the `MANUAL_CAPTCHA`, `CASE_YEAR`, and `CASE_TYPE_VALUE` variables at the top of the file by looking at the live court website.
    -   Execute the script from your terminal:
        ```bash
        py scraper.py
        ```
    -   The script will open a browser, perform all actions, and save the final case details as `Gaya-Case-Details.pdf` in the project folder. The query will also be logged in `queries.db`.

## 🎬 Demo Video

[**Click here to watch the demo video**](https://your-youtube-or-loom-link.com)


## 📄 License

This project is licensed under the MIT License.


