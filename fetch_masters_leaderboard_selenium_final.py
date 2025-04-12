# File: fetch_masters_leaderboard_selenium_final.py

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
    waits for the leaderboard table to load, then parses the HTML using the CORRECTED selectors.

    Args:
        target_url (str): The URL of the CBS leaderboard page.
    """
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
        leaderboard_table_selector = (By.CSS_SELECTOR, 'table.TableBase-table') # This worked

        print(f"Waiting up to {wait_timeout}s for leaderboard element ('{leaderboard_table_selector[1]}') to be present...")
        wait = WebDriverWait(driver, wait_timeout)
        leaderboard_element = wait.until(EC.presence_of_element_located(leaderboard_table_selector))
        print("Leaderboard element found.")

        time.sleep(3) # Small wait just in case

        print("Getting page source...")
        page_source = driver.page_source
        print("Page source retrieved.")

        soup = BeautifulSoup(page_source, 'html.parser')
        print("Page source parsed successfully.")

        leaderboard_table = soup.select_one(leaderboard_table_selector[1])

        if not leaderboard_table:
            print("\nError: Could not re-find the table with BeautifulSoup.")
            return

        # Find ALL table rows within the body
        player_rows = leaderboard_table.select('tbody > tr')
        if not player_rows: player_rows = leaderboard_table.find_all('tr') # Fallback

        print(f"Found {len(player_rows)} total rows in table body. Filtering for player data...")

        # --- Extract Data with CORRECTED LOGIC ---
        print("\n--- Masters Leaderboard ---")
        extracted_count = 0
        for i, row in enumerate(player_rows):
            # Skip rows used for scorecards (they often have colspan or different class)
            if row.find('td', colspan=True) or 'GolfLeaderboardScorecard-row' in row.get('class', []):
                continue

            cells = row.find_all('td')

            # Expecting 10 cells for player data rows based on HTML structure
            if len(cells) < 10:
                # print(f"Skipping row {i+1}: Incorrect cell count ({len(cells)})") # Optional debug
                continue

            try:
                # Indices based on debugged HTML structure:
                pos_el = cells[1]
                name_container_el = cells[3] # Cell containing name structure
                topar_el = cells[4]
                r1_el = cells[5]
                thru_el = cells[6] # This seems to be Thru/Status/TeeTime
                r2_el = cells[7]
                r3_el = cells[8]
                r4_el = cells[9]

                # Extract text carefully
                pos = pos_el.text.strip()

                # Extract full player name from nested span/link
                name_link = name_container_el.select_one('span.CellPlayerName--long a')
                name = name_link.text.strip() if name_link else 'Unknown' # Find the specific span/link

                to_par = topar_el.text.strip()
                r1 = r1_el.text.strip()
                thru = thru_el.text.strip() # Use this as 'Thru' status
                r2 = r2_el.text.strip()
                r3 = r3_el.text.strip()
                r4 = r4_el.text.strip()

                # Filter out potential header rows missed by initial filter
                if pos in ['POS', ''] or name == 'Unknown':
                    continue

                # Today/Total are not separate columns; Use Thru and To Par respectively
                today = "N/A" # No specific cell for Today's score vs par
                total = to_par # To Par is the total score relative to par

                # Handle amateur "(a)" - check name cell text content directly
                if '(a)' in name_container_el.text:
                     name = name + ' (a)'

                print(f"{str(pos).ljust(5)} {name.ljust(25)} To Par: {str(to_par).ljust(4)} Thru: {str(thru).ljust(8)} Today: {str(today).ljust(4)} R1: {str(r1).ljust(3)} R2: {str(r2).ljust(3)} R3: {str(r3).ljust(3)} R4: {str(r4).ljust(3)}")
                extracted_count += 1

            except IndexError:
                 print(f"Skipping row {i+1} due to IndexError (unexpected structure).")
            except Exception as parse_err:
                 print(f"Error parsing row {i+1}: {parse_err}")
                 # print(row.prettify()) # Uncomment to debug specific row if needed

        if extracted_count == 0:
            print("\nError: Filtered rows but failed to extract data from any remaining valid rows.")
            print(" ---> ACTION: Double-check the selectors inside the loop and cell indices against the row HTML.")
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
    # Needs: pip install selenium webdriver-manager beautifulsoup4
    fetch_leaderboard_with_selenium(url)