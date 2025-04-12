# File: score_masters_pool_db_v1.py
# Updated for Docker container execution with periodic scraping
# --- FINAL REVISED PARSING LOGIC --

import sys
import traceback
import time
import re
import sqlite3
# Make sure datetime and timezone are imported
from datetime import datetime, timezone # <-- Added timezone import
import os # Required for DB path check

from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException # Keep TimeoutException
# from webdriver_manager.chrome import ChromeDriverManager # Not needed when using system chromedriver
from bs4 import BeautifulSoup

# --- Configuration --
URL = "https://www.cbssports.com/golf/leaderboard/"
DB_FILE = "/app/data/masters_scores.db" # Path inside the container

# --- Pool Structure and Your Picks ---
# (Pool structure remains the same - omitted for brevity but included in the actual file content)
POOL_STRUCTURE = {
    "Box 1: Top of the Charts": {"players": ["Scottie Scheffler", "Rory McIlroy", "Xander Schauffele", "Collin Morikawa", "Ludvig Aberg", "Jon Rahm"], "selected": "Collin Morikawa"},
    "Box 2: The next 5": {"players": ["Hideki Matsuyama", "Russell Henley", "Viktor Hovland", "Justin Thomas", "Wyndham Clark"], "selected": "Viktor Hovland"},
    "Box 3: On The Cusp": {"players": ["Cameron Young", "Patrick Cantlay", "Min Woo Lee", "Tom Kim", "Tommy Fleetwood", "Joaquin Niemann", "Tyrell Hatton"], "selected": "Patrick Cantlay"},
    "Box 4: O Canada": {"players": ["Corey Conners", "Taylor Pendrith", "Nick Taylor"], "selected": "Corey Conners"},
    "Box 5: Long Bombers": {"players": ["Byeong Hun An", "Daniel Berger", "Sam Burns", "Will Zalatoris", "Tony Finau", "J.T. Poston", "Sahith Theegala"], "selected": "Tony Finau"},
    "Box 6: Past Champs": {"players": ["Patrick Reed", "Charl Schwartzel", "Bubba Watson", "Adam Scott", "Sergio Garcia", "Zach Johnson"], "selected": "Adam Scott"},
    "Box 7: UK and Beyond": {"players": ["Robert MacIntyre", "Aaron Rai", "Justin Rose", "Danny Willett", "Sepp Straka", "Sungjae Im"], "selected": "Sepp Straka"},
    "Box 8: Elder Statesmen": {"players": ["Angel Cabrera", "Mike Weir", "Vijay Singh", "Jose Maria Olazabal", "Bernhard Langer", "Fred Couples"], "selected": "Mike Weir"},
    "Box 9: Major Winners": {"players": ["Brooks Koepka", "Bryson DeChambeau", "Matt Fitzpatrick", "Cameron Smith", "Shane Lowry", "Jordan Spieth", "Dustin Johnson", "Phil Mickelson"], "selected": "Bryson DeChambeau"},
    "Box 10: First Masters": {"players": ["Davis Thompson", "Brian Campbell", "Rafael Campos", "Laurie Canter", "Thomas Detry", "Nicolás Echavarría", "Matt McCarty", "Maverick McNealy"], "selected": "Davis Thompson"},
    "Box 11: The Amateurs": {"players": ["Jose Luis Ballester Barrio", "Evan Beck", "Hiroshi Tai", "Noah Kent", "Justin Hastings"], "selected": "Jose Luis Ballester Barrio"},
    "Box 12: World Team": {"players": ["Matthieu Pavon", "Cameron Davis", "Thriston Lawrence", "Jhonattan Vegas", "Stephan Jaeger", "Christiaan Bezuidenhout"], "selected": "Matthieu Pavon"},
    "Box 13: Longest of Shots": {"players": ["J.J. Spaun", "Michael Kim", "Adam Schenk", "Davis Riley", "Patton Kizzire", "Austin Eckroat", "Tom Hoge", "Denny McCarthy"], "selected": "J.J. Spaun"},
    "Box 14: Cagey Veterans": {"players": ["Max Homa", "Keegan Bradley", "Jason Day", "Harris English", "Lucas Glover", "Billy Horschel", "Brian Harman", "Chris Kirk"], "selected": "Max Homa"},
    "Box 15: Young Guns": {"players": ["Akshay Bhatia", "Max Greyserman", "Nicolai Hojgaard", "Nick Dunlap", "Joe Highsmith", "Kevin Yu", "Rasmus Hojgaard"], "selected": "Nicolai Hojgaard"}
}
# --- End Configuration ---

# --- UPDATED FUNCTION v13 (Find ALL tbodies) ---
def get_leaderboard_data(target_url: str) -> list[dict]:
    """ Fetches leaderboard data using Selenium, waits for rows, finds ALL tbodies. """
    print(f"Attempting to fetch leaderboard via Selenium: {target_url}")
    leaderboard = []
    driver = None
    options = webdriver.ChromeOptions(); options.add_argument('--headless=new'); options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage'); options.add_argument('--disable-gpu'); options.add_argument('--window-size=1920,1080'); options.add_argument('--log-level=3')
    chromedriver_path = "/usr/bin/chromedriver"

    try:
        print("Initializing WebDriver..."); service = ChromeService(executable_path=chromedriver_path); driver = webdriver.Chrome(service=service, options=options)
        print("WebDriver initialized."); print(f"Loading page: {target_url}..."); driver.get(target_url); print("Page loading initiated.")

        wait_timeout = 90; tbody_selector = (By.CSS_SELECTOR, 'table.TableBase-table tbody'); player_row_selector = (By.CSS_SELECTOR, 'tr.TableBase-bodyTr'); min_expected_rows = 50
        print(f"Waiting up to {wait_timeout}s for initial table body..."); wait = WebDriverWait(driver, wait_timeout)
        try: wait.until(EC.presence_of_element_located(tbody_selector)); print("Initial table body found.")
        except TimeoutException: print(f"Error: Timed out waiting for table body."); return []
        except Exception as e: print(f"Error finding initial table body: {e}"); return []

        # --- Wait Logic (Wait for minimum row count - same as v12) ---
        print(f"Now waiting up to {wait_timeout}s for >= {min_expected_rows} player rows..."); final_row_count = 0
        try:
            wait.until(lambda d: len(d.find_elements(*player_row_selector)) >= min_expected_rows)
            final_row_count = len(driver.find_elements(*player_row_selector)); print(f"Sufficient player rows found ({final_row_count}).")
        except TimeoutException:
            final_row_count = len(driver.find_elements(*player_row_selector)); print(f"WARN: Timed out waiting for rows. Found {final_row_count}.")
        except Exception as e: print(f"Error waiting for player rows: {e}."); final_row_count = 0
        time.sleep(2)
        # --- End Wait Logic ---

        print("Getting page source..."); page_source = driver.page_source; print("Page source retrieved.")
        soup = BeautifulSoup(page_source, 'html.parser'); print("Page source parsed.")

        # --- PARSING CHANGE: Find ALL tbodies within the table ---
        print("Searching for main leaderboard table...")
        main_table = soup.select_one('table.TableBase-table')
        if not main_table: print("\nError: Could not find the main table ('table.TableBase-table')."); return []
        print("Main table found.")

        all_tbodies = main_table.find_all('tbody', recursive=False)
        print(f"Found {len(all_tbodies)} tbody element(s) within the main table.")

        if not all_tbodies: print("No tbody elements found within the main table."); return []

        all_player_rows = []
        for tbody_index, current_tbody in enumerate(all_tbodies):
            rows_in_tbody = current_tbody.find_all('tr', recursive=False)
            print(f" Found {len(rows_in_tbody)} total TR rows in tbody #{tbody_index+1}.")
            all_player_rows.extend(rows_in_tbody)

        print(f"Total TR rows found across all tbodies: {len(all_player_rows)}. Filtering/extracting...")
        # --- End Parsing Change ---

        if not all_player_rows: print("No TR rows found in any tbody."); return []

        extracted_count = 0; skipped_row_count = 0; processed_player_rows = 0
        for i, row in enumerate(all_player_rows):
            row_classes = row.get('class', []);
            if 'TableBase-bodyTr' not in row_classes: skipped_row_count += 1; continue
            processed_player_rows += 1; cells = row.find_all('td')
            expected_cells = 10 # Keep this at 10
            if len(cells) < expected_cells: print(f"Skip row {i+1}: {len(cells)}/{expected_cells} cells"); skipped_row_count += 1; continue
            try:
                pos_el=cells[1]; name_el=cells[3]; topar_el=cells[4]; r1_el=cells[5]; r2_el=cells[6]; r3_el=cells[7]; r4_el=cells[8]
                pos = pos_el.get_text(strip=True); long_name_span = name_el.find('span', class_='CellPlayerName--long')
                if long_name_span: name = long_name_span.get_text(strip=True)
                else: name = name_el.get_text(strip=True); print(f"WARN: No span.CellPlayerName--long row {i+1}")
                to_par = topar_el.get_text(strip=True); r1 = r1_el.get_text(strip=True); r2 = r2_el.get_text(strip=True); r3 = r3_el.get_text(strip=True); r4 = r4_el.get_text(strip=True)
                if not pos or not name or name.lower() == 'name': print(f"Skip row {i+1} no pos/name"); skipped_row_count += 1; continue
                if not re.match(r"^(T?\d+|CUT|WD|DQ)$", pos, re.IGNORECASE): print(f"Skip row {i+1} bad pos: {pos}"); skipped_row_count += 1; continue
                print(f"DEBUG: Extracted potential player - Name: '{name}', Pos: '{pos}'")
                is_amateur = '(a)' in name_el.get_text(); name = name.replace('(a)', '').strip()
                thru = "N/A"
                if pos in ["CUT", "WD", "DQ"]: thru = pos
                elif r4 and r4 != '-' and ':' not in r4 and not r4.upper().startswith("TRUE"): thru = "F"
                elif r4 and r4.upper().startswith("TRUE"): match = re.search(r'TRUE\s*(\d+)', r4, re.IGNORECASE); thru = match.group(1) if match else thru; not match and print(f"WARN: TRUE R4? {name}: {r4}")
                elif r4 and ':' in r4: thru = "54"
                elif r3 and r3.upper().startswith("TRUE"): match = re.search(r'TRUE\s*(\d+)', r3, re.IGNORECASE); thru = match.group(1) if match else thru; not match and print(f"WARN: TRUE R3? {name}: {r3}")
                elif r3 and ':' in r3: thru = "36"
                elif r3 and r3 != '-' and r4 == '-': thru = "54"
                elif r2 and r2 != '-' and r3 == '-': thru = "36"
                elif r1 and r1 != '-' and r2 == '-': thru = "18"
                elif r1 == '-': thru = "0"
                if thru == "N/A": print(f"WARN: Thru? {name} (Pos: {pos}, R1:{r1}, R2:{r2}, R3:{r3}, R4:{r4}).")
                player_data = {"pos": pos, "name": name, "to_par": to_par, "thru": thru, "r1": r1, "r2": r2, "r3": r3, "r4": r4, "is_amateur": is_amateur}
                leaderboard.append(player_data); extracted_count += 1
            except IndexError as idx_e: print(f"IndexError row {i+1}"); skipped_row_count += 1
            except Exception as inner_e: print(f"Error row {i+1}: {inner_e}"); skipped_row_count += 1

        print(f"Extraction complete. Processed {processed_player_rows} player rows across all tbodies. Extracted: {extracted_count}, Skipped: {skipped_row_count} rows.")
        if extracted_count == 0 and processed_player_rows > 0: print("WARNING: Processed player rows but extracted 0 valid data points.")
        elif extracted_count == 0: print("WARNING: Found no processable player rows in any tbody.") # Modified warning

        return leaderboard

    except Exception as e: print(f"\nError during Selenium fetch: {e}"); raise
    finally: driver and driver.quit(); print("WebDriver closed.")
# --- END UPDATED FUNCTION v13 ---

# --- Function v8 (get_points_for_position - fixed syntax) ---
def get_points_for_position(position_str: str) -> int:
    position_str = position_str.upper().strip();
    if position_str in ["CUT", "WD", "DQ", "--", ""]: return 0
    match = re.match(r"T?(\d+)", position_str);
    if not match: return 0
    try: rank = int(match.group(1))
    except (ValueError, IndexError): return 0
    if rank == 1: return 15
    elif 2 <= rank <= 5: return 9
    elif 6 <= rank <= 15: return 6
    elif 16 <= rank <= 29: return 4
    elif rank >= 30: return 2
    else: return 0

# --- Function v8 (save_results_to_db - minor condensing) ---
def save_results_to_db(results_list: list[dict], total_score: int):
    conn = None
    try:
        db_dir = os.path.dirname(DB_FILE); not os.path.exists(db_dir) and os.makedirs(db_dir)
        print(f"\nConnecting to database: {DB_FILE}"); conn = sqlite3.connect(DB_FILE); cursor = conn.cursor()
        print("Setting up tables (dropping existing)..."); cursor.execute('''DROP TABLE IF EXISTS player_scores'''); cursor.execute('''DROP TABLE IF EXISTS leaderboard_meta''')
        cursor.execute('''CREATE TABLE player_scores (id INTEGER PRIMARY KEY AUTOINCREMENT, box_name TEXT NOT NULL, player_name TEXT NOT NULL, position TEXT, thru TEXT, to_par TEXT, points INTEGER NOT NULL)''')
        cursor.execute('''CREATE TABLE leaderboard_meta (id INTEGER PRIMARY KEY CHECK (id = 1), total_score INTEGER, last_updated TEXT NOT NULL)'''); print("Tables created.")
        if results_list:
            print(f"Inserting {len(results_list)} player results..."); insert_sql = '''INSERT INTO player_scores (box_name, player_name, position, thru, to_par, points) VALUES (?, ?, ?, ?, ?, ?)'''
            data_to_insert = [(p['box'], p['name'], p['pos'], p['thru'], p['to_par'], p['points']) for p in results_list]
            cursor.executemany(insert_sql, data_to_insert); print("Player results inserted.")
        else: print("No player results to insert.")

        # --- TIMESTAMP FIX ---
        print("Inserting/updating metadata...")
        # Use datetime.now() with timezone.utc and .isoformat() for compatibility
        last_updated_ts = datetime.now(timezone.utc).isoformat()
        # --- END TIMESTAMP FIX ---

        cursor.execute('''INSERT OR REPLACE INTO leaderboard_meta (id, total_score, last_updated) VALUES (1, ?, ?)''', (total_score, last_updated_ts)); print("Metadata updated.")
        conn.commit(); print("Database commit successful.")
    except sqlite3.Error as e: print(f"\nDatabase error: {e}"); conn and conn.rollback()
    except Exception as e: print(f"\nUnexpected DB error: {e}"); conn and conn.rollback()
    finally: conn and conn.close(); print("Closed DB connection.")

# --- Main Execution Loop (v9 - fixed syntax error) ---
if __name__ == "__main__":
    run_interval_seconds = 300
    print(f"--- Scraper starting. Will run every {run_interval_seconds/60:.1f} minutes. ---")
    while True:
        # --- TIMESTAMP FIX for log message ---
        print(f"\n--- {datetime.now(timezone.utc).isoformat()} --- Starting Scrape Cycle ---")
        # --- END TIMESTAMP FIX ---
        try:
            your_selected_players = {details["selected"].strip().lower() for details in POOL_STRUCTURE.values()}
            if not your_selected_players: print("Error: No players selected."); time.sleep(run_interval_seconds); continue
            print(f"Tracking {len(your_selected_players)} selected players.")
            live_leaderboard_data = get_leaderboard_data(URL)
            if not live_leaderboard_data: print("\nError: Failed to retrieve valid leaderboard data."); print(f"Retry in {run_interval_seconds/60:.1f} min.")
            else:
                leaderboard_map = {player['name'].strip().lower(): player for player in live_leaderboard_data}
                print("\n--- Calculating Your Pool Score ---"); print(f"DEBUG: Pool Names (lower): {sorted(list(your_selected_players))}"); print(f"DEBUG: Found Names (lower): {sorted(list(leaderboard_map.keys()))}")
                total_score = 0; results = []; processed_picks_lower = set()
                pick_to_box_map = {details["selected"].strip().lower(): box_name for box_name, details in POOL_STRUCTURE.items()}; pick_original_casing = {details["selected"].strip().lower(): details["selected"] for details in POOL_STRUCTURE.values()}
                for player_name_lower, player_data in leaderboard_map.items():
                    if player_name_lower in your_selected_players:
                        position = player_data['pos']; points = get_points_for_position(position); total_score += points; box_name = pick_to_box_map.get(player_name_lower, "Unknown Box")
                        display_name = pick_original_casing.get(player_name_lower, player_data['name'])
                        if player_data['is_amateur']: display_name += " (a)"
                        results.append({"box": box_name, "name": display_name, "pos": position, "to_par": player_data['to_par'], "thru": player_data['thru'], "points": points})
                        processed_picks_lower.add(player_name_lower); print(f"DEBUG: Matched player: {display_name} (Points: {points})")
                missing_picks_lower = your_selected_players - processed_picks_lower
                if missing_picks_lower:
                    print(f"\nNote: {len(missing_picks_lower)} selected player(s) not found. Assuming 0 points.")
                    missing_names_original_case = [pick_original_casing.get(p, p) for p in missing_picks_lower]; print(f"DEBUG: Missing players: {sorted(missing_names_original_case)}")
                for missing_pick_lower in missing_picks_lower:
                    original_case_name = pick_original_casing.get(missing_pick_lower, "Unknown"); box_name = pick_to_box_map.get(missing_pick_lower, "Unknown")
                    results.append({"box": box_name, "name": original_case_name, "pos": "Not Found", "to_par": "N/A", "thru": "N/A", "points": 0})
                def get_box_num(box_name): match = re.match(r"Box (\d+)", box_name); return int(match.group(1)) if match else 999
                results.sort(key=lambda x: get_box_num(x['box']))
                print("\n--- Current Scores Calculation ---"); print(f"TOTAL SCORE Calculated: {total_score}")
                save_results_to_db(results, total_score); print("Results saved.")
        except Exception as e: print(f"\n--- ERROR during scrape cycle ---"); print(f"Error: {e}"); traceback.print_exc(); print("---------------------------------")
        print(f"\n--- Cycle Complete. Sleep {run_interval_seconds}s ---")
        time.sleep(run_interval_seconds)