# File: score_masters_pool_db_v1.py
# Updated for Docker container execution with periodic scraping

import sys
import traceback
import time
import re
import sqlite3
import datetime # Make sure datetime is imported
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

# --- Configuration ---
URL = "https://www.cbssports.com/golf/leaderboard/"
# --- Path for Docker Volume Mount ---
DB_FILE = "/app/data/masters_scores.db" # Path inside the container

# --- Pool Structure and Your Picks ---
# (Keep your existing POOL_STRUCTURE dictionary here - unchanged)
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

# In score_masters_pool_db_v1.py
def get_leaderboard_data(target_url: str) -> list[dict]:
    """ Fetches leaderboard data using Selenium and returns it as a list of dicts. """
    print(f"Attempting to fetch leaderboard via Selenium: {target_url}")
    leaderboard = []
    driver = None
    options = webdriver.ChromeOptions()
    options.add_argument('--headless=new')
    options.add_argument('--no-sandbox') # Important in containers
    options.add_argument('--disable-dev-shm-usage') # Important in containers
    options.add_argument('--disable-gpu') # Often needed in headless
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--log-level=3')
    # You might need to add this if Chromium complains about the user agent
    # options.add_argument("user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/XXX.YYY") # Check Chromium version if needed

    # --- Change for Docker with pre-installed chromium-driver ---
    # Point directly to the driver installed by apt-get in the Dockerfile
    chromedriver_path = "/usr/bin/chromedriver"
    # --- End Change ---

    try:
        print("Initializing WebDriver...")
        # --- Change for Docker ---
        # Provide the explicit path to the ChromeService
        service = ChromeService(executable_path=chromedriver_path)
        # --- End Change ---
        driver = webdriver.Chrome(service=service, options=options)
        print("WebDriver initialized.")
        print(f"Loading page: {target_url}...")
        driver.get(target_url)
        print("Page loading initiated.")

        wait_timeout = 60
        leaderboard_table_selector = (By.CSS_SELECTOR, 'table.TableBase-table')
        print(f"Waiting up to {wait_timeout}s for leaderboard element ('{leaderboard_table_selector[1]}') to be present...")
        wait = WebDriverWait(driver, wait_timeout)
        wait.until(EC.presence_of_element_located(leaderboard_table_selector))
        print("Leaderboard element found.")

        time.sleep(4) # Allow time for dynamic content rendering

        print("Getting page source...")
        page_source = driver.page_source
        print("Page source retrieved.")

        soup = BeautifulSoup(page_source, 'html.parser')
        print("Page source parsed successfully.")

        leaderboard_table = soup.select_one(leaderboard_table_selector[1])
        if not leaderboard_table:
            print("\nError: Could not re-find the table with BeautifulSoup.")
            return []

        player_rows = leaderboard_table.select('tbody > tr')
        if not player_rows:
            player_rows = leaderboard_table.find_all('tr', recursive=False)
            print("Using fallback row selection (direct tr children).")

        print(f"Found {len(player_rows)} potential player rows. Extracting player data...")
        extracted_count = 0
        skipped_count = 0

        # --- Row processing logic (remains the same) ---
        for i, row in enumerate(player_rows):
            if row.find('th') or 'GolfLeaderboardScorecard-row' in row.get('class', []):
                skipped_count += 1
                continue
            cells = row.find_all('td')
            if len(cells) < 11:
                skipped_count += 1
                continue
            try:
                pos_el = cells[1]
                name_container_el = cells[3]
                topar_el = cells[4]
                thru_el = cells[5]
                r1_el = cells[7]
                r2_el = cells[8]
                r3_el = cells[9]
                r4_el = cells[10]

                pos = pos_el.text.strip()
                name_span = name_container_el.select_one('span.CellPlayerName--long')
                name_link = name_span.find('a') if name_span else None
                name = name_link.text.strip() if name_link else (name_span.text.strip() if name_span else 'Unknown Player')

                if pos in ['POS', ''] or name == 'Unknown Player' or not pos or not name:
                     skipped_count += 1
                     continue
                if not re.match(r"(T?\d+|CUT|WD|DQ)", pos, re.IGNORECASE):
                     skipped_count += 1
                     continue

                is_amateur = '(a)' in name_container_el.text

                player_data = {
                    "pos": pos,
                    "name": name.replace('(a)', '').strip(),
                    "to_par": topar_el.text.strip(),
                    "thru": thru_el.text.strip(),
                    "r1": r1_el.text.strip(),
                    "r2": r2_el.text.strip(),
                    "r3": r3_el.text.strip(),
                    "r4": r4_el.text.strip(),
                    "is_amateur": is_amateur
                }
                leaderboard.append(player_data)
                extracted_count += 1

            except IndexError:
                skipped_count += 1
            except Exception as inner_e:
                # Log inner exception details if needed during debugging
                # print(f"Error processing row {i+1}: {inner_e}")
                skipped_count += 1
        # --- End Row processing ---

        print(f"Extraction complete. Extracted: {extracted_count}, Skipped: {skipped_count} rows.")
        return leaderboard
    except Exception as e:
        print(f"\nAn unexpected error occurred during Selenium fetch: {e}")
        # traceback.print_exc() # Uncomment only if needed for deep debugging
        raise # Re-raise the exception to be caught by the main loop
    finally:
        if driver:
            print("Closing WebDriver...")
            driver.quit()
            print("WebDriver closed.")


def get_points_for_position(position_str: str) -> int:
    """ Calculates pool points based on the scoring rubric. """
    position_str = position_str.upper().strip()
    if position_str in ["CUT", "WD", "DQ", "--", ""]: return 0

    match = re.match(r"T?(\d+)", position_str)
    if not match: return 0

    try: rank = int(match.group(1))
    except (ValueError, IndexError): return 0

    if rank == 1: return 15
    elif 2 <= rank <= 5: return 9
    elif 6 <= rank <= 15: return 6
    elif 16 <= rank <= 29: return 4
    elif rank >= 30: return 2
    else: return 0


def save_results_to_db(results_list: list[dict], total_score: int):
    """Saves the calculated results and total score to the SQLite database."""
    conn = None
    try:
        # Ensure the directory exists (Docker volume should handle this, but defensive check)
        db_dir = os.path.dirname(DB_FILE)
        if not os.path.exists(db_dir):
            os.makedirs(db_dir) # Create directory if it doesn't exist

        print(f"\nConnecting to database: {DB_FILE}")
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        print("Setting up tables (dropping existing)...")
        cursor.execute('''DROP TABLE IF EXISTS player_scores''')
        cursor.execute('''DROP TABLE IF EXISTS leaderboard_meta''')

        cursor.execute('''
            CREATE TABLE player_scores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                box_name TEXT NOT NULL,
                player_name TEXT NOT NULL,
                position TEXT,
                thru TEXT,
                to_par TEXT,
                points INTEGER NOT NULL
            )
        ''')
        cursor.execute('''
            CREATE TABLE leaderboard_meta (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                total_score INTEGER,
                last_updated TEXT NOT NULL
            )
        ''')
        print("Tables created.")

        if results_list:
            print(f"Inserting {len(results_list)} player results...")
            insert_sql = '''
                INSERT INTO player_scores (box_name, player_name, position, thru, to_par, points)
                VALUES (?, ?, ?, ?, ?, ?)
            '''
            data_to_insert = [
                (p['box'], p['name'], p['pos'], p['thru'], p['to_par'], p['points'])
                for p in results_list
            ]
            cursor.executemany(insert_sql, data_to_insert)
            print("Player results inserted.")
        else:
             print("No player results to insert.")

        print("Inserting metadata (total score and timestamp)...")
        # Ensure datetime is imported
        last_updated_ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute('''
            INSERT OR REPLACE INTO leaderboard_meta (id, total_score, last_updated)
            VALUES (1, ?, ?)
        ''', (total_score, last_updated_ts)) # Use INSERT OR REPLACE for simplicity
        print("Metadata inserted/updated.")

        conn.commit()
        print("Database commit successful.")

    except sqlite3.Error as e:
        print(f"\nDatabase error: {e}")
        traceback.print_exc()
        if conn:
            conn.rollback()
    except Exception as e:
         print(f"\nAn unexpected error occurred during DB save: {e}")
         traceback.print_exc()
    finally:
        if conn:
            print("Closing database connection.")
            conn.close()


# --- Required for save_results_to_db directory check ---
import os

# --- Main Execution Loop ---
if __name__ == "__main__":
    run_interval_seconds = 300 # 5 minutes (300 seconds)

    print(f"--- Scraper starting. Will run every {run_interval_seconds/60:.1f} minutes. ---")

    while True:
        print(f"\n--- {datetime.datetime.now()} --- Starting Scrape Cycle ---")
        try:
            # Prepare selected players set (lowercase for matching)
            your_selected_players = {details["selected"].strip().lower() for details in POOL_STRUCTURE.values()}
            if not your_selected_players:
                print("Error: No players marked as 'selected' in POOL_STRUCTURE. Skipping cycle.")
                time.sleep(run_interval_seconds)
                continue # Go to next iteration

            print(f"Tracking {len(your_selected_players)} selected players.")

            # Get Live Data
            live_leaderboard_data = get_leaderboard_data(URL) # Calls the function defined above
            if not live_leaderboard_data:
                print("\nError: Failed to retrieve leaderboard data. Skipping DB update for this cycle.")
                # Optional: implement retry logic here if desired
                time.sleep(run_interval_seconds)
                continue # Go to next iteration

            # Create a lookup map {lowercase_name: player_data_dict}
            leaderboard_map = {player['name'].strip().lower(): player for player in live_leaderboard_data}

            # Calculate Score and Prepare Results List
            print("\n--- Calculating Your Pool Score ---")
            total_score = 0
            results = [] # This list will be saved to the DB
            processed_picks_lower = set()

            # Map picks to boxes for easy lookup {lowercase_pick: box_name}
            pick_to_box_map = {details["selected"].strip().lower(): box_name for box_name, details in POOL_STRUCTURE.items()}
            pick_original_casing = {details["selected"].strip().lower(): details["selected"] for details in POOL_STRUCTURE.values()}

            # Iterate through the fetched leaderboard data
            for player_name_lower, player_data in leaderboard_map.items():
                if player_name_lower in your_selected_players:
                    position = player_data['pos']
                    points = get_points_for_position(position)
                    total_score += points
                    box_name = pick_to_box_map.get(player_name_lower, "Unknown Box")
                    display_name = pick_original_casing.get(player_name_lower, player_data['name'])
                    if player_data['is_amateur']:
                        display_name += " (a)"

                    results.append({
                        "box": box_name, "name": display_name, "pos": position,
                        "to_par": player_data['to_par'], "thru": player_data['thru'], "points": points
                    })
                    processed_picks_lower.add(player_name_lower)

            # Handle selected picks *not* found on the current leaderboard
            missing_picks_lower = your_selected_players - processed_picks_lower
            if missing_picks_lower:
                print(f"\nNote: {len(missing_picks_lower)} selected player(s) not found on the current leaderboard. Assuming 0 points.")
            for missing_pick_lower in missing_picks_lower:
                original_case_name = pick_original_casing.get(missing_pick_lower, "Unknown Player Name")
                box_name = pick_to_box_map.get(missing_pick_lower, "Unknown Box")
                results.append({
                    "box": box_name, "name": original_case_name, "pos": "Not Found",
                    "to_par": "N/A", "thru": "N/A", "points": 0
                })

            # Sort results
            def get_box_num(box_name):
                match = re.match(r"Box (\d+)", box_name)
                return int(match.group(1)) if match else 999
            results.sort(key=lambda x: get_box_num(x['box']))

            print("\n--- Current Scores ---")
            # Optional: Print table to docker logs if desired
            # print(f"{'Box'.ljust(25)} {'Player'.ljust(28)} ...")
            # for player in results: print(f"{str(player['box']).ljust(25)} ...")
            print(f"TOTAL SCORE: {total_score}")

            # Save to Database
            save_results_to_db(results, total_score) # Calls the function defined above
            print("Results saved to database.")

        except Exception as e:
            # Catch any exceptions during the scraping or processing
            print(f"\n--- ERROR during scrape cycle ---")
            print(f"An unexpected error occurred: {e}")
            traceback.print_exc() # Print detailed error to logs
            # Decide if you want to stop the loop on error or just log and continue
            print("---------------------------------")
            # Optional: Implement smarter backoff/retry logic here

        # Wait before the next cycle
        print(f"\n--- Scrape Cycle Complete. Sleeping for {run_interval_seconds} seconds ({run_interval_seconds/60:.1f} minutes)... ---")
        time.sleep(run_interval_seconds)