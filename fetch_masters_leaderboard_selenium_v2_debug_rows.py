# File: fetch_masters_leaderboard_selenium_v2_debug_rows.py

# ... (keep all imports and setup from previous Selenium script) ...
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

url = "https://www.cbssports.com/golf/leaderboard/"

def fetch_leaderboard_with_selenium(target_url: str):
    print(f"Attempting to fetch via Selenium: {target_url}")
    driver = None
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--log-level=3')
    options.add_argument("user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")

    try:
        print("Initializing WebDriver...")
        service = ChromeService(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        print("WebDriver initialized.")

        print(f"Loading page: {target_url}...")
        driver.get(target_url)
        print("Page loading initiated.")

        wait_timeout = 60
        # This selector worked! Keep it.
        leaderboard_table_selector = (By.CSS_SELECTOR, 'table.TableBase-table')

        print(f"Waiting up to {wait_timeout}s for leaderboard element ('{leaderboard_table_selector[1]}') to be present...")
        wait = WebDriverWait(driver, wait_timeout)
        leaderboard_element = wait.until(EC.presence_of_element_located(leaderboard_table_selector))
        print("Leaderboard element found.")

        time.sleep(3)

        print("Getting page source...")
        page_source = driver.page_source
        print("Page source retrieved.")

        soup = BeautifulSoup(page_source, 'html.parser')
        print("Page source parsed successfully.")

        leaderboard_table = soup.select_one(leaderboard_table_selector[1])

        if not leaderboard_table:
             # Fallback just in case
             all_tables = soup.find_all('table')
             for table in all_tables:
                 if 'Scheffler' in table.get_text() or 'Rose' in table.get_text():
                     leaderboard_table = table
                     break

        if not leaderboard_table:
            print("\nError: Could not re-find the table with BeautifulSoup.")
            return

        # --- Find Player Rows ---
        # Let's try to be slightly more specific if possible, otherwise stick to tr
        # Inspect Element: Do rows have a class like 'PlayerRow'?
        player_rows = leaderboard_table.select('tbody > tr') # Prefer selecting from tbody
        if not player_rows: player_rows = leaderboard_table.find_all('tr') # Fallback

        if not player_rows:
            print("\nError: Found table, but couldn't find player rows (<tr>) within it.")
            return

        print(f"Found {len(player_rows)} potential player rows in the table.")

        # --- !!! DEBUG: PRINT FIRST FEW ROWS' HTML !!! ---
        print("\n--- HTML of first 5 rows found ---")
        for i, row in enumerate(player_rows[:5]): # Print first 5 rows
            print(f"\n--- Row {i+1} ---")
            print(row.prettify()) # prettify() makes it readable
        print("--- End Debug Rows ---\n")

        # --- Extract Data (KEEP OLD LOGIC FOR NOW, WE'LL FIX IT BASED ON DEBUG OUTPUT) ---
        print("\n--- Masters Leaderboard (Attempting Extraction) ---")
        extracted_count = 0
        for i, row in enumerate(player_rows):
            cells = row.find_all('td')
            if len(cells) < 5: continue # Keep basic cell count check

            try:
                # --- SUSPECT AREA: Check indices and structure based on printed HTML ---
                pos = cells[0].text.strip()
                ctry_el = cells[1]
                ctry = ' '.join(ctry_el.stripped_strings) if ctry_el else 'N/A'

                name_el = cells[2].find('a') # Still assuming name is in a link in 3rd cell
                name = name_el.text.strip() if name_el else cells[2].text.strip()

                to_par = cells[3].text.strip()
                r1 = cells[4].text.strip()
                r2 = cells[5].text.strip() if len(cells) > 5 else '-'
                r3 = cells[6].text.strip() if len(cells) > 6 else '-'
                r4 = cells[7].text.strip() if len(cells) > 7 else '-'
                total = cells[8].text.strip() if len(cells) > 8 else '-'

                if pos == 'POS' or not pos or name == '': continue # Keep basic filter

                if '(a)' in name: name = name.replace('(a)', '').strip() + ' (a)'
                elif '(a)' in ctry: name = name + ' (a)'

                # This print might not happen if extraction logic above fails silently
                print(f"{str(pos).ljust(5)} {name.ljust(25)} To Par: {str(to_par).ljust(4)} R1: {str(r1).ljust(3)} R2: {str(r2).ljust(3)} R3: {str(r3).ljust(3)} R4: {str(r4).ljust(3)} Total: {str(total).ljust(4)}")
                extracted_count += 1

            except IndexError:
                # This is less likely now if len(cells) check passes, unless R2+ access fails
                # print(f"Skipping row {i+1} due to IndexError.") # Optional debug
                pass
            except Exception as parse_err:
                # Catch other potential errors during .text or .find()
                # print(f"Error parsing row {i+1}: {parse_err}") # Optional debug
                pass # Fail silently for now to avoid spamming errors

        if extracted_count == 0:
            print("\nWarning: Found player rows but failed to extract data from any.")
            print(" ---> ACTION: Examine the 'HTML of first 5 rows' printed above to fix the extraction logic (cell indices, finding elements within cells).")
        else:
            print(f"\nData extraction complete. Extracted {extracted_count} players.")

    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")
        traceback.print_exc()
    finally:
        if driver:
            print("Closing WebDriver...")
            driver.quit()
            print("WebDriver closed.")

if __name__ == "__main__":
    fetch_leaderboard_with_selenium(url)