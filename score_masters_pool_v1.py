# File: score_masters_pool_structured_v2.py

import sys
import traceback
import time
import re
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

# --- Configuration ---
URL = "https://www.cbssports.com/golf/leaderboard/"

# --- Pool Structure and Your Picks ---
# Define the entire pool structure with your selection marked in 'selected'.
POOL_STRUCTURE = {
    "Box 1: Top of the Charts": {
        "players": ["Scottie Scheffler", "Rory McIlroy", "Xander Schauffele", "Collin Morikawa", "Ludvig Aberg", "Jon Rahm"],
        "selected": "Collin Morikawa"
    },
    "Box 2: The next 5": {
        "players": ["Hideki Matsuyama", "Russell Henley", "Viktor Hovland", "Justin Thomas", "Wyndham Clark"],
        "selected": "Viktor Hovland"
    },
    "Box 3: On The Cusp": {
        "players": ["Cameron Young", "Patrick Cantlay", "Min Woo Lee", "Tom Kim", "Tommy Fleetwood", "Joaquin Niemann", "Tyrell Hatton"],
        "selected": "Patrick Cantlay"
    },
    "Box 4: O Canada": {
        "players": ["Corey Conners", "Taylor Pendrith", "Nick Taylor"],
        "selected": "Corey Conners"
    },
    "Box 5: Long Bombers": {
        "players": ["Byeong Hun An", "Daniel Berger", "Sam Burns", "Will Zalatoris", "Tony Finau", "J.T. Poston", "Sahith Theegala"],
        "selected": "Tony Finau"
    },
    "Box 6: Past Champs": {
        "players": ["Patrick Reed", "Charl Schwartzel", "Bubba Watson", "Adam Scott", "Sergio Garcia", "Zach Johnson"],
        "selected": "Adam Scott"
    },
    "Box 7: UK and Beyond": {
        "players": ["Robert MacIntyre", "Aaron Rai", "Justin Rose", "Danny Willett", "Sepp Straka", "Sungjae Im"],
        "selected": "Sepp Straka"
    },
    "Box 8: Elder Statesmen": {
        "players": ["Angel Cabrera", "Mike Weir", "Vijay Singh", "Jose Maria Olazabal", "Bernhard Langer", "Fred Couples"],
        "selected": "Mike Weir"
    },
    "Box 9: Major Winners": {
        "players": ["Brooks Koepka", "Bryson DeChambeau", "Matt Fitzpatrick", "Cameron Smith", "Shane Lowry", "Jordan Spieth", "Dustin Johnson", "Phil Mickelson"],
        "selected": "Bryson DeChambeau"
    },
    "Box 10: First Masters": {
        "players": ["Davis Thompson", "Brian Campbell", "Rafael Campos", "Laurie Canter", "Thomas Detry", "Nico Echavarría", "Matt McCarty", "Maverick McNealy"],
        "selected": "Davis Thompson"
    },
    "Box 11: The Amateurs": {
        "players": ["Jose Luis Ballester Barrio", "Evan Beck", "Hiroshi Tai", "Noah Kent", "Justin Hastings"], #
        "selected": "Jose Luis Ballester Barrio"
    },
    "Box 12: World Team": {
        "players": ["Matthieu Pavon", "Cameron Davis", "Thriston Lawrence", "Jhonattan Vegas", "Stephan Jaeger", "Christiaan Bezuidenhout"],
        "selected": "Matthieu Pavon"
    },
    "Box 13: Longest of Shots": {
        "players": ["J.J. Spaun", "Michael Kim", "Adam Schenk", "Davis Riley", "Patton Kizzire", "Austin Eckroat", "Tom Hoge", "Denny McCarthy"],
        "selected": "J.J. Spaun"
    },
    "Box 14: Cagey Veterans": {
        "players": ["Max Homa", "Keegan Bradley", "Jason Day", "Harris English", "Lucas Glover", "Billy Horschel", "Brian Harman", "Chris Kirk"],
        "selected": "Max Homa"
    },
    "Box 15: Young Guns": {
        "players": ["Akshay Bhatia", "Max Greyserman", "Nicolai Hojgaard", "Nick Dunlap", "Joe Highsmith", "Kevin Yu", "Rasmus Hojgaard"],
        "selected": "Nicolai Hojgaard"
    }
}
# --- End Configuration ---

def get_leaderboard_data(target_url: str) -> list[dict]:
    """ Fetches leaderboard data using Selenium and returns it as a list of dicts. """
    print(f"Attempting to fetch leaderboard via Selenium: {target_url}")
    leaderboard = []
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
        leaderboard_table_selector = (By.CSS_SELECTOR, 'table.TableBase-table')
        print(f"Waiting up to {wait_timeout}s for leaderboard element ('{leaderboard_table_selector[1]}') to be present...")
        wait = WebDriverWait(driver, wait_timeout)
        wait.until(EC.presence_of_element_located(leaderboard_table_selector))
        print("Leaderboard element found.")
        # Adding a small explicit wait AFTER element is found, sometimes needed for dynamic content rendering
        time.sleep(3)
        print("Getting page source...")
        page_source = driver.page_source
        print("Page source retrieved.")
        soup = BeautifulSoup(page_source, 'html.parser')
        print("Page source parsed successfully.")
        leaderboard_table = soup.select_one(leaderboard_table_selector[1])
        if not leaderboard_table:
            print("\nError: Could not re-find the table with BeautifulSoup.")
            return []

        # Find all table rows, attempt tbody first, fallback to all trs
        player_rows = leaderboard_table.select('tbody > tr')
        if not player_rows:
            player_rows = leaderboard_table.find_all('tr') # Fallback if tbody selector fails

        print(f"Found {len(player_rows)} total rows. Extracting player data...")

        for i, row in enumerate(player_rows):
            # Skip header rows or special rows like scorecards if they are identified by specific classes or colspan
            if row.find('td', colspan=True) or 'GolfLeaderboardScorecard-row' in row.get('class', []):
                continue

            cells = row.find_all('td')

            # Increase minimum cell count check to accommodate the corrected indices
            if len(cells) < 11: # Need at least 11 cells for pos, name, topar, thru, r1, r2, r3, r4
                # print(f"Skipping row {i+1}, not enough cells ({len(cells)}). Row content: {row.text[:100]}...") # Uncomment for debugging
                continue

            try:
                # *** CORRECTED INDICES ***
                # Based on CBS Sports layout (0-indexed):
                # 0: (hidden/checkbox?)
                # 1: POS
                # 2: Country Flag
                # 3: NAME
                # 4: TO PAR
                # 5: THRU  <- This is the key change
                # 6: TODAY
                # 7: R1
                # 8: R2
                # 9: R3
                # 10: R4
                # 11: TOTAL
                pos_el = cells[1]
                name_container_el = cells[3]
                topar_el = cells[4]
                thru_el = cells[5]    # Corrected from 6
                r1_el = cells[7]      # Corrected from 5
                r2_el = cells[8]      # Corrected from 7
                r3_el = cells[9]      # Corrected from 8
                r4_el = cells[10]     # Corrected from 9

                pos = pos_el.text.strip()
                name_link = name_container_el.select_one('span.CellPlayerName--long a')
                name = name_link.text.strip() if name_link else 'Unknown'

                # Skip header/irrelevant rows missed by earlier checks
                if pos in ['POS', ''] or name == 'Unknown' or not re.match(r"T?\d+|CUT|WD|DQ", pos, re.IGNORECASE):
                    continue

                is_amateur = '(a)' in name_container_el.text # Check for amateur status indicator

                # Extract text content, stripping whitespace
                player_data = {
                    "pos": pos,
                    "name": name,
                    "to_par": topar_el.text.strip(),
                    "thru": thru_el.text.strip(), # Use the corrected element
                    "r1": r1_el.text.strip(),
                    "r2": r2_el.text.strip(),
                    "r3": r3_el.text.strip(),
                    "r4": r4_el.text.strip(),
                    "is_amateur": is_amateur
                }
                leaderboard.append(player_data)

            except IndexError:
                # Catch potential errors if a row has an unexpected structure (fewer cells than expected after the initial check)
                # print(f"Skipping row {i+1} due to IndexError during cell access.") # Uncomment for debugging
                pass # Continue to the next row
            except Exception as inner_e:
                # Catch other potential errors during individual row processing
                print(f"Error processing row {i+1}: {inner_e}")
                # traceback.print_exc() # Uncomment for detailed debugging of row errors
                pass # Continue to the next row

        print(f"Extracted data for {len(leaderboard)} players.")
        return leaderboard
    except Exception as e:
        print(f"\nAn unexpected error occurred during Selenium fetch: {e}")
        traceback.print_exc()
        return []
    finally:
        if driver:
            print("Closing WebDriver...")
            driver.quit()
            print("WebDriver closed.")

def get_points_for_position(position_str: str) -> int:
    """ Calculates pool points based on the scoring rubric. """
    position_str = position_str.upper().strip()
    if position_str in ["CUT", "WD", "DQ", "--", ""]: return 0 # Added DQ and blank check

    # Handle ties (e.g., "T3")
    match = re.match(r"T?(\d+)", position_str)
    if not match: return 0 # Not a valid position format

    try:
        rank = int(match.group(1))
    except (ValueError, IndexError):
        return 0 # Should not happen with regex, but safety first

    # Apply scoring rules
    if rank == 1: return 15
    elif 2 <= rank <= 5: return 9 # Note: CBS usually shows 1st place without a 'T'
    elif 6 <= rank <= 15: return 6
    elif 16 <= rank <= 29: return 4
    elif rank >= 30: return 2
    else: return 0 # Should not be reached if rank is positive

# --- Main Execution ---
if __name__ == "__main__":
    print("Starting Masters Pool Scorer...")

    # Extract your selected picks (convert to lowercase for case-insensitive matching)
    your_selected_players = {details["selected"].strip().lower() for details in POOL_STRUCTURE.values()}
    if not your_selected_players:
        print("Error: No players marked as 'selected' in POOL_STRUCTURE.")
        sys.exit(1)
    print(f"Tracking {len(your_selected_players)} selected players.")

    # Get Live Data
    live_leaderboard_data = get_leaderboard_data(URL)
    if not live_leaderboard_data:
        print("\nError: Failed to retrieve leaderboard data. Cannot calculate score.")
        sys.exit(1)

    # Create a quick lookup map (lowercase names for matching)
    leaderboard_map = {player['name'].strip().lower(): player for player in live_leaderboard_data}

    # Calculate Score
    print("\n--- Calculating Your Pool Score ---")
    total_score = 0
    results = []
    processed_picks_lower = set()

    # Create a reverse map to find the box for each selected player (used for display)
    pick_to_box_map = {}
    for box_name, details in POOL_STRUCTURE.items():
        pick_to_box_map[details["selected"].strip().lower()] = box_name

    # Iterate through the live leaderboard data we fetched
    for player_name_lower, player_data in leaderboard_map.items():
        # Check if this player from the leaderboard is one of your selections
        if player_name_lower in your_selected_players:
            position = player_data['pos']
            points = get_points_for_position(position)
            total_score += points
            box_name = pick_to_box_map.get(player_name_lower, "Unknown Box") # Find which box they belong to

            # Add (a) indicator back for display if player is an amateur
            display_name = player_data['name']
            if player_data['is_amateur']:
                display_name += " (a)"

            results.append({
                "box": box_name,
                "name": display_name,
                "pos": position,
                "to_par": player_data['to_par'],
                "thru": player_data['thru'], # Now uses the corrected 'thru' value
                "points": points
            })
            processed_picks_lower.add(player_name_lower) # Mark this pick as found on the leaderboard

    # Identify any of your selected picks that were *not* found on the live leaderboard
    # (Could be due to WD, CUT before the script ran, or name mismatch issues)
    missing_picks_lower = your_selected_players - processed_picks_lower
    for missing_pick_lower in missing_picks_lower:
        # Find the original casing and box name for the missing pick
        original_case_name = "Unknown Player"
        box_name = "Unknown Box"
        for b_name, details in POOL_STRUCTURE.items():
            if details["selected"].strip().lower() == missing_pick_lower:
                original_case_name = details["selected"] # Get the name as you typed it
                box_name = b_name
                break

        results.append({
            "box": box_name,
            "name": original_case_name,
            "pos": "Not Found", # Indicate they weren't on the current leaderboard
            "to_par": "N/A",
            "thru": "N/A",
            "points": 0 # No points if not found / potentially CUT/WD
        })

    # Display Results - Sort by Box Number for readability
    def get_box_num(box_name):
        match = re.match(r"Box (\d+)", box_name)
        return int(match.group(1)) if match else 999 # Put unknown/error boxes last
    results.sort(key=lambda x: get_box_num(x['box']))

    print("\n--- Your Picks Status ---")
    # Adjusted column widths slightly for better alignment
    print(f"{'Box'.ljust(25)} {'Player'.ljust(28)} {'Pos'.ljust(6)} {'Thru'.ljust(6)} {'To Par'.ljust(8)} {'Points'}")
    print("-" * 85)
    for player in results:
        # Ensure all parts are strings before formatting
        print(f"{str(player['box']).ljust(25)} {str(player['name']).ljust(28)} {str(player['pos']).ljust(6)} {str(player['thru']).ljust(6)} {str(player['to_par']).ljust(8)} {player['points']}")
    print("-" * 85)
    print(f"TOTAL SCORE: {total_score}")
    print("\nScoring based on current leaderboard snapshot.")
    print("Note: 'Thru' indicates hole number if in progress, 'F' if finished round, '-' or blank if not started.")