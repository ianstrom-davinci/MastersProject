# File: fetch_masters_leaderboard_selenium_v1.py

import sys
import traceback
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

# URL for CBS Sports Golf Leaderboard
url = "https://www.cbssports.com/golf/leaderboard/"

def fetch_leaderboard_with_selenium(target_url: str):
    """
    Fetches the CBS leaderboard page using Selenium to control a Chrome browser,
    waits for the leaderboard table to load, then parses the HTML.

    Args:
        target_url (str): The URL of the CBS leaderboard page.
    """
    print(f"Attempting to fetch via Selenium: {target_url}")
    driver = None  # Initialize driver to None for finally block

    # Setup Chrome options (optional, but can be useful)
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')  # Run headless (no browser window visible)
    options.add_argument('--no-sandbox') # Often needed in certain environments
    options.add_argument('--disable-dev-shm-usage') # Overcome resource limits
    options.add_argument('--log-level=3') # Suppress console logs from Chrome itself
    options.add_argument("user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36") # Set user agent


    try:
        # Initialize WebDriver (webdriver-manager handles driver download/path)
        print("Initializing WebDriver...")
        service = ChromeService(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        print("WebDriver initialized.")

        # Set implicit wait (fallback if explicit waits fail, waits for elements globally)
        # driver.implicitly_wait(10) # Wait up to 10 seconds for elements by default

        # Load the page
        print(f"Loading page: {target_url}...")
        driver.get(target_url)
        print("Page loading initiated.")

        # --- Explicit Wait for Leaderboard Table ---
        # Wait up to 60 seconds for an element that indicates the leaderboard is loaded.
        # ADJUST THE SELECTOR based on inspecting the table in your browser.
        wait_timeout = 60
        # Option 1: Wait for the table itself (preferred if stable ID/class exists)
        # leaderboard_table_selector = (By.ID, 'leaderboardTable') # Example ID
        leaderboard_table_selector = (By.CSS_SELECTOR, 'table.TableBase-table') # Inspect to find the right CSS selector for the table
        # Option 2: Wait for a specific, known player row or cell (if table ID is dynamic)
        # leaderboard_table_selector = (By.XPATH, "//td[contains(text(), 'Scheffler')]") # Example: Wait for cell containing 'Scheffler'

        print(f"Waiting up to {wait_timeout}s for leaderboard element ('{leaderboard_table_selector[1]}') to be present...")
        wait = WebDriverWait(driver, wait_timeout)
        leaderboard_element = wait.until(EC.presence_of_element_located(leaderboard_table_selector))
        print("Leaderboard element found.")

        # Optional: Add a small fixed wait just in case data populates slightly after table appears
        time.sleep(3)

        # Get the page source AFTER JavaScript has loaded
        print("Getting page source...")
        page_source = driver.page_source
        print("Page source retrieved.")

        # --- Parse with BeautifulSoup ---
        soup = BeautifulSoup(page_source, 'html.parser')
        print("Page source parsed successfully.")

        # Find the table using the same selector strategy as the wait
        leaderboard_table = soup.select_one(leaderboard_table_selector[1]) # Use the CSS selector from above

        if not leaderboard_table:
             # Fallback search if the primary selector worked for waiting but not for BS4
             all_tables = soup.find_all('table')
             for table in all_tables:
                 if 'Scheffler' in table.get_text() or 'Rose' in table.get_text():
                     leaderboard_table = table
                     print("Found potential leaderboard table via fallback content search.")
                     break

        if not leaderboard_table:
            print("\nError: Leaderboard element was located by Selenium, but couldn't re-find the table with BeautifulSoup.")
            # print(page_source[:5000]) # Print beginning of source
            return

        # --- Find Player Rows ---
        player_rows = leaderboard_table.select('tbody > tr')
        if not player_rows: player_rows = leaderboard_table.find_all('tr') # Fallback

        if not player_rows:
            print("\nError: Found table, but couldn't find player rows (<tr>) within it.")
            return

        print(f"Found {len(player_rows)} potential player rows in the table.")

        # --- Extract Data (same logic as v3) ---
        print("\n--- Masters Leaderboard (from Selenium) ---")
        extracted_count = 0
        for i, row in enumerate(player_rows):
            cells = row.find_all('td')
            if len(cells) < 5: continue

            try:
                pos = cells[0].text.strip()
                # Ctry might be in cell 1
                ctry_el = cells[1]
                ctry = ' '.join(ctry_el.stripped_strings) if ctry_el else 'N/A'

                # Name often inside a link in cell 2
                name_el = cells[2].find('a')
                name = name_el.text.strip() if name_el else cells[2].text.strip()

                to_par = cells[3].text.strip()
                r1 = cells[4].text.strip()
                r2 = cells[5].text.strip() if len(cells) > 5 else '-'
                r3 = cells[6].text.strip() if len(cells) > 6 else '-'
                r4 = cells[7].text.strip() if len(cells) > 7 else '-'
                total = cells[8].text.strip() if len(cells) > 8 else '-'

                if pos == 'POS' or not pos or name == '': continue

                if '(a)' in name:
                    name = name.replace('(a)', '').strip() + ' (a)'
                elif '(a)' in ctry:
                     name = name + ' (a)'

                print(f"{str(pos).ljust(5)} {name.ljust(25)} To Par: {str(to_par).ljust(4)} R1: {str(r1).ljust(3)} R2: {str(r2).ljust(3)} R3: {str(r3).ljust(3)} R4: {str(r4).ljust(3)} Total: {str(total).ljust(4)}")
                extracted_count += 1

            except IndexError:
                print(f"Skipping row {i+1}: Not enough cells found.")
            except Exception as parse_err:
                print(f"Error parsing row {i+1}: {parse_err}")

        if extracted_count == 0:
            print("\nWarning: Found player rows but failed to extract data from any.")
        else:
            print(f"\nData extraction complete. Extracted {extracted_count} players.")

    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")
        traceback.print_exc()
    finally:
        # Ensure the browser is closed even if errors occur
        if driver:
            print("Closing WebDriver...")
            driver.quit()
            print("WebDriver closed.")

# --- Run the extraction function ---
if __name__ == "__main__":
    # Needs: pip install selenium webdriver-manager beautifulsoup4
    fetch_leaderboard_with_selenium(url)