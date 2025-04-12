# File: score_masters_pool_db_v1.py
# Purpose: Periodically scrape Masters leaderboard data and store raw golfer scores
#          in a persistent SQLite database table (`golfer_scores`).
#          This script does NOT handle participant picks or score calculations.

import time
import re
import sqlite3
from datetime import datetime, timezone
import os
import traceback  # Keep for robust error logging in the loop

from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from bs4 import BeautifulSoup

# --- Configuration --
URL = "https://www.cbssports.com/golf/leaderboard/"
DB_FILE = "/app/data/masters_scores.db"  # Path inside the container
RUN_INTERVAL_SECONDS = 300  # 5 minutes


# --- End Configuration ---

# --- Leaderboard Scraping Function (v13 - unchanged) ---
def get_leaderboard_data(target_url: str) -> list[dict]:
    """ Fetches leaderboard data using Selenium, waits for rows, finds ALL tbodies. """
    print(f"Attempting to fetch leaderboard via Selenium: {target_url}")
    leaderboard = []
    driver = None
    options = webdriver.ChromeOptions();
    options.add_argument('--headless=new');
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage');
    options.add_argument('--disable-gpu');
    options.add_argument('--window-size=1920,1080');
    options.add_argument('--log-level=3')
    chromedriver_path = "/usr/bin/chromedriver"

    try:
        print("Initializing WebDriver...");
        service = ChromeService(executable_path=chromedriver_path);
        driver = webdriver.Chrome(service=service, options=options)
        print("WebDriver initialized.");
        print(f"Loading page: {target_url}...");
        driver.get(target_url);
        print("Page loading initiated.")

        wait_timeout = 90;
        tbody_selector = (By.CSS_SELECTOR, 'table.TableBase-table tbody');
        player_row_selector = (By.CSS_SELECTOR, 'tr.TableBase-bodyTr');
        min_expected_rows = 50  # Lowered expectation slightly
        print(f"Waiting up to {wait_timeout}s for initial table body...");
        wait = WebDriverWait(driver, wait_timeout)
        try:
            wait.until(EC.presence_of_element_located(tbody_selector)); print("Initial table body found.")
        except TimeoutException:
            print(f"Error: Timed out waiting for table body."); return []
        except Exception as e:
            print(f"Error finding initial table body: {e}"); return []

        print(f"Now waiting up to {wait_timeout}s for >= {min_expected_rows} player rows...");
        final_row_count = 0
        try:
            wait.until(lambda d: len(d.find_elements(*player_row_selector)) >= min_expected_rows)
            final_row_count = len(driver.find_elements(*player_row_selector));
            print(f"Sufficient player rows found ({final_row_count}).")
        except TimeoutException:
            final_row_count = len(driver.find_elements(*player_row_selector));
            print(f"WARN: Timed out waiting for rows. Found {final_row_count}.")
            if final_row_count == 0:  # If we timed out AND found zero rows, it's likely an error
                print("ERROR: Timed out and found 0 player rows. Aborting scrape attempt.")
                return []
        except Exception as e:
            print(f"Error waiting for player rows: {e}."); return []  # Treat other exceptions as errors
        time.sleep(2)  # Brief pause after waiting

        print("Getting page source...");
        page_source = driver.page_source;
        print("Page source retrieved.")
        soup = BeautifulSoup(page_source, 'html.parser');
        print("Page source parsed.")

        print("Searching for main leaderboard table...")
        main_table = soup.select_one('table.TableBase-table')
        if not main_table: print("\nError: Could not find the main table ('table.TableBase-table')."); return []
        print("Main table found.")

        all_tbodies = main_table.find_all('tbody', recursive=False)
        print(f"Found {len(all_tbodies)} tbody element(s) within the main table.")
        if not all_tbodies: print("No tbody elements found within the main table."); return []

        all_player_rows = [];
        for tbody_index, current_tbody in enumerate(all_tbodies):
            rows_in_tbody = current_tbody.find_all('tr', recursive=False);
            # print(f" Found {len(rows_in_tbody)} total TR rows in tbody #{tbody_index+1}.") # Reduced logging verbosity
            all_player_rows.extend(rows_in_tbody)

        print(f"Total TR rows found across all tbodies: {len(all_player_rows)}. Filtering/extracting...")
        if not all_player_rows: print("No TR rows found in any tbody."); return []

        extracted_count = 0;
        skipped_row_count = 0;
        processed_player_rows = 0
        for i, row in enumerate(all_player_rows):
            row_classes = row.get('class', []);
            if 'TableBase-bodyTr' not in row_classes: skipped_row_count += 1; continue  # Skip non-player rows silently
            processed_player_rows += 1;
            cells = row.find_all('td')
            expected_cells = 10
            if len(cells) < expected_cells: skipped_row_count += 1; continue  # Skip incomplete rows silently
            try:
                pos_el = cells[1];
                name_el = cells[3];
                topar_el = cells[4];
                r1_el = cells[5];
                r2_el = cells[6];
                r3_el = cells[7];
                r4_el = cells[8]
                pos = pos_el.get_text(strip=True);
                long_name_span = name_el.find('span', class_='CellPlayerName--long')
                if long_name_span:
                    name = long_name_span.get_text(strip=True)
                else:
                    name = name_el.get_text(strip=True); print(
                        f"WARN: No span.CellPlayerName--long for player in row {i + 1}")

                to_par = topar_el.get_text(strip=True);
                r1 = r1_el.get_text(strip=True);
                r2 = r2_el.get_text(strip=True);
                r3 = r3_el.get_text(strip=True);
                r4 = r4_el.get_text(strip=True)

                if not pos or not name or name.lower() == 'name': skipped_row_count += 1; continue  # Skip header-like rows
                if not re.match(r"^(T?\d+|CUT|WD|DQ)$", pos, re.IGNORECASE): print(
                    f"WARN: Skipping row {i + 1}, unhandled pos: {pos}"); skipped_row_count += 1; continue

                is_amateur = '(a)' in name_el.get_text();
                name = name.replace('(a)', '').strip()  # Clean name
                if not name: skipped_row_count += 1; continue  # Skip if name becomes empty after cleaning

                # Simplified Thru Logic (Good enough for now)
                thru = "N/A"
                if pos in ["CUT", "WD", "DQ"]:
                    thru = pos
                elif r4 and r4 != '-' and ':' not in r4:
                    thru = "F"  # Assume Finished if R4 has a score
                elif r3 and r3 != '-' and r4 == '-':
                    thru = "54"
                elif r2 and r2 != '-' and r3 == '-':
                    thru = "36"
                elif r1 and r1 != '-' and r2 == '-':
                    thru = "18"
                elif r1 == '-':
                    thru = "0"  # Not started

                # Basic data validation
                to_par = to_par if re.match(r"^(E|\+?\-?\d+)$", to_par) else "N/A"
                r1 = r1 if re.match(r"^\d+$", r1) else "-"
                r2 = r2 if re.match(r"^\d+$", r2) else "-"
                r3 = r3 if re.match(r"^\d+$", r3) else "-"
                r4 = r4 if re.match(r"^\d+$", r4) else "-"

                player_data = {"pos": pos, "name": name, "to_par": to_par, "thru": thru, "r1": r1, "r2": r2, "r3": r3,
                               "r4": r4, "is_amateur": is_amateur}
                leaderboard.append(player_data);
                extracted_count += 1
            except IndexError:
                skipped_row_count += 1  # Skip rows with unexpected structure
            except Exception as inner_e:
                print(f"Error processing row {i + 1}: {inner_e}"); skipped_row_count += 1

        print(
            f"Extraction complete. Processed {processed_player_rows} potential player rows. Extracted: {extracted_count}, Skipped: {skipped_row_count} rows.")
        if extracted_count == 0 and processed_player_rows > 0:
            print("WARNING: Processed player rows but extracted 0 valid data points.")
        elif extracted_count == 0:
            print("WARNING: Found no processable player rows.")

        return leaderboard

    except Exception as e:
        print(f"\nError during Selenium fetch: {e}"); traceback.print_exc(); return []  # Return empty on major error
    finally:
        if driver:
            driver.quit();
            print("WebDriver closed.")


# --- End Leaderboard Scraping Function ---


# --- NEW Database Saving Function ---
def save_golfer_scores_to_db(leaderboard_data: list[dict]):
    """
    Saves the raw golfer scores to the `golfer_scores` table in the SQLite DB.
    Creates the table if it doesn't exist. Uses INSERT OR REPLACE to update existing golfers.
    """
    if not leaderboard_data:
        print("No leaderboard data provided to save.")
        return

    conn = None
    try:
        db_dir = os.path.dirname(DB_FILE)
        if not os.path.exists(db_dir):
            print(f"Creating data directory: {db_dir}")
            os.makedirs(db_dir)

        print(f"\nConnecting to database: {DB_FILE}");
        conn = sqlite3.connect(DB_FILE);
        cursor = conn.cursor()

        # Create table if it doesn't exist - ensures persistence
        print("Ensuring 'golfer_scores' table exists...")
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS golfer_scores (
                name TEXT PRIMARY KEY,
                pos TEXT,
                to_par TEXT,
                thru TEXT,
                r1 TEXT,
                r2 TEXT,
                r3 TEXT,
                r4 TEXT,
                is_amateur INTEGER,
                last_updated TEXT NOT NULL
            )
        ''')
        print("'golfer_scores' table ready.")

        print(f"Preparing {len(leaderboard_data)} golfer records for DB update...")
        insert_sql = '''
            INSERT OR REPLACE INTO golfer_scores
            (name, pos, to_par, thru, r1, r2, r3, r4, is_amateur, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        '''

        data_to_insert = []
        current_timestamp = datetime.now(timezone.utc).isoformat()
        for player in leaderboard_data:
            # Ensure all keys exist, providing defaults if necessary (although scraper should provide them)
            data_tuple = (
                player.get('name'),
                player.get('pos', 'N/A'),
                player.get('to_par', 'N/A'),
                player.get('thru', 'N/A'),
                player.get('r1', '-'),
                player.get('r2', '-'),
                player.get('r3', '-'),
                player.get('r4', '-'),
                1 if player.get('is_amateur', False) else 0,  # Convert boolean to integer
                current_timestamp
            )
            # Basic validation: Ensure primary key (name) is present
            if data_tuple[0]:
                data_to_insert.append(data_tuple)
            else:
                print(f"WARN: Skipping record with missing name: {player}")

        if data_to_insert:
            print(f"Updating/inserting {len(data_to_insert)} golfer records...")
            cursor.executemany(insert_sql, data_to_insert)
            conn.commit()
            print(f"Database commit successful. {len(data_to_insert)} records updated/inserted.")
        else:
            print("No valid data tuples prepared for database insertion.")

    except sqlite3.Error as e:
        print(f"\nDatabase error: {e}")
        if conn:
            conn.rollback()
    except Exception as e:
        print(f"\nUnexpected error during DB save: {e}")
        traceback.print_exc()
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()
            print("Closed DB connection.")


# --- End Database Saving Function ---


# --- Main Execution Loop ---
if __name__ == "__main__":
    print(f"--- Scraper starting. Will run every {RUN_INTERVAL_SECONDS / 60:.1f} minutes. ---")
    print(f"--- Target URL: {URL} ---")
    print(f"--- Database File: {DB_FILE} ---")

    while True:
        start_time_iso = datetime.now(timezone.utc).isoformat()
        print(f"\n--- {start_time_iso} --- Starting Scrape Cycle ---")

        live_leaderboard_data = []  # Ensure it's empty before scrape attempt
        try:
            # Step 1: Get the latest leaderboard data
            live_leaderboard_data = get_leaderboard_data(URL)

            # Step 2: If data was retrieved, save it to the database
            if live_leaderboard_data:
                print(f"\nSuccessfully scraped {len(live_leaderboard_data)} player records.")
                save_golfer_scores_to_db(live_leaderboard_data)
                print("Scrape data saved to database.")
            else:
                print("\nWarning: Failed to retrieve valid leaderboard data from URL. Database not updated.")

        except Exception as e:
            # Catch any unexpected errors during the cycle
            print(f"\n--- ERROR during main scrape cycle ---")
            print(f"Error: {e}")
            traceback.print_exc()  # Print full traceback for debugging
            print("--------------------------------------")

        # Step 3: Wait for the next interval
        print(
            f"\n--- Cycle Complete. Sleeping for {RUN_INTERVAL_SECONDS} seconds ({RUN_INTERVAL_SECONDS / 60:.1f} minutes) ---")
        time.sleep(RUN_INTERVAL_SECONDS)