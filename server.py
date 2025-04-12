# File: server.py
# Rewritten to support multiple participants via config.json
# and calculate scores dynamically from the 'golfer_scores' DB table.

import sqlite3
import json
import os
import re # Needed for scoring logic
from flask import Flask, jsonify
from flask_cors import CORS
from datetime import datetime, timezone # For handling timestamps

app = Flask(__name__)
CORS(app) # Enable CORS for all routes

# --- Configuration ---
# Assume config.json and the DB are in specific paths relative to the app
# or use absolute paths depending on your Docker setup.
CONFIG_FILE = "/app/config.json" # Path inside the container where config.json is mounted/copied
DB_FILE = "/app/data/masters_scores.db" # Path inside the container to the SQLite DB

# --- Global variable to hold config data ---
CONFIG_DATA = None

# --- Helper Functions ---

def load_config():
    """Loads the configuration from config.json."""
    global CONFIG_DATA
    if not os.path.exists(CONFIG_FILE):
        print(f"CRITICAL ERROR: Configuration file not found at {CONFIG_FILE}")
        return False # Indicate failure
    try:
        with open(CONFIG_FILE, 'r') as f:
            CONFIG_DATA = json.load(f)
        print(f"Configuration loaded successfully from {CONFIG_FILE}")
        # Basic validation
        if "participants" not in CONFIG_DATA or not isinstance(CONFIG_DATA["participants"], list):
             print("CRITICAL ERROR: Config missing 'participants' list.")
             CONFIG_DATA = None # Invalidate config
             return False
        if "pool_structure" not in CONFIG_DATA:
             print("CRITICAL ERROR: Config missing 'pool_structure'.")
             CONFIG_DATA = None
             return False
        print(f"Found {len(CONFIG_DATA['participants'])} participants in config.")
        return True # Indicate success
    except json.JSONDecodeError as e:
        print(f"CRITICAL ERROR: Failed to parse {CONFIG_FILE}: {e}")
        CONFIG_DATA = None
        return False
    except Exception as e:
        print(f"CRITICAL ERROR: Unexpected error loading config: {e}")
        CONFIG_DATA = None
        return False

def get_db():
    """Connects to the SQLite database."""
    if not os.path.exists(DB_FILE):
         print(f"Warning: Database file {DB_FILE} not found.")
         return None # Return None if DB file is not found
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row # Return rows as dictionary-like objects
        # Check if the required table exists
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='golfer_scores';")
        if cursor.fetchone() is None:
            print(f"Warning: Database exists, but 'golfer_scores' table not found. Run scraper.")
            conn.close()
            return None
        return conn
    except sqlite3.Error as e:
        print(f"Database connection or check error: {e}")
        return None # Return None on connection error

def get_points_for_position(position_str: str) -> int:
    """Calculates points based on golfer's position string (copied from scraper)."""
    if position_str is None: return 0 # Handle None case
    position_str = position_str.upper().strip();
    if position_str in ["CUT", "WD", "DQ", "--", "", "N/A"]: return 0 # Added N/A
    match = re.match(r"T?(\d+)", position_str);
    if not match: return 0
    try: rank = int(match.group(1))
    except (ValueError, IndexError): return 0

    # --- SCORING RULES ---
    if rank == 1: return 15
    elif 2 <= rank <= 5: return 9
    elif 6 <= rank <= 15: return 6
    elif 16 <= rank <= 29: return 4
    elif rank >= 30: return 2
    else: return 0
    # --- END SCORING RULES ---

def get_latest_golfer_scores() -> tuple[dict | None, str | None]:
    """Fetches all golfer scores from the DB and the latest update time."""
    conn = get_db()
    if conn is None:
        return None, None

    scores_map = {}
    last_updated = "N/A"
    try:
        cursor = conn.cursor()
        # Fetch all players
        cursor.execute("SELECT name, pos, to_par, thru, last_updated, is_amateur FROM golfer_scores")
        rows = cursor.fetchall()
        if not rows:
            print("Warning: 'golfer_scores' table is empty.")
            conn.close()
            return {}, "Never" # Return empty map and placeholder time

        # Find the most recent timestamp
        # Querying MAX(last_updated) might be slightly cleaner if the timestamp format is consistent
        cursor.execute("SELECT MAX(last_updated) as latest_update FROM golfer_scores")
        latest_update_row = cursor.fetchone()
        if latest_update_row and latest_update_row['latest_update']:
            last_updated = latest_update_row['latest_update']
            # Optional: Format the timestamp nicely if needed later
            # try:
            #     dt_obj = datetime.fromisoformat(last_updated.replace('Z', '+00:00')) # Handle Z for UTC
            #     last_updated = dt_obj.strftime("%Y-%m-%d %H:%M:%S %Z")
            # except ValueError:
            #     pass # Keep original string if parsing fails

        # Build the map for quick lookups (lowercase names)
        for row in rows:
            player_data = dict(row)
            # Ensure name is present before lowercasing
            if player_data.get('name'):
                 scores_map[player_data['name'].strip().lower()] = player_data
            else:
                 print(f"Warning: DB row found with missing name: {player_data}")


        conn.close()
        print(f"Fetched {len(scores_map)} golfer scores from DB. Last updated: {last_updated}")
        return scores_map, last_updated

    except sqlite3.Error as e:
        print(f"Database query error in get_latest_golfer_scores: {e}")
        if conn: conn.close()
        return None, None # Indicate failure
    except Exception as e:
        print(f"Unexpected error in get_latest_golfer_scores: {e}")
        if conn: conn.close()
        return None, None

def calculate_participant_score(participant_config: dict, golfer_scores_map: dict) -> dict:
    """Calculates score for one participant based on their picks and live scores."""
    total_score = 0
    detailed_picks = []
    participant_name = participant_config.get("name", "Unknown Participant")
    participant_picks = participant_config.get("picks", {})

    if not golfer_scores_map: # Handle case where DB fetch failed or was empty
        print(f"Warning: Cannot calculate score for {participant_name}, golfer scores map is empty/None.")
        for box_name, picked_golfer_original in participant_picks.items():
             detailed_picks.append({
                "box": box_name,
                "player_name": picked_golfer_original,
                "status": "Error: Score data unavailable",
                "position": "N/A",
                "to_par": "N/A",
                "thru": "N/A",
                "points": 0
             })
        return {"total_score": 0, "picks": detailed_picks}

    # Iterate through the participant's picks defined in config.json
    for box_name, picked_golfer_original in participant_picks.items():
        picked_golfer_lower = picked_golfer_original.strip().lower()
        golfer_data = golfer_scores_map.get(picked_golfer_lower) # Lookup using lowercase name

        if golfer_data:
            position = golfer_data.get('pos', 'N/A')
            points = get_points_for_position(position)
            total_score += points
            display_name = picked_golfer_original # Use original casing for display
            if golfer_data.get('is_amateur'):
                 display_name += " (a)"

            detailed_picks.append({
                "box": box_name,
                "player_name": display_name,
                "status": "Found",
                "position": position,
                "to_par": golfer_data.get('to_par', 'N/A'),
                "thru": golfer_data.get('thru', 'N/A'),
                "points": points
            })
        else:
            # Player picked by participant not found in the scraped data
            detailed_picks.append({
                "box": box_name,
                "player_name": picked_golfer_original,
                "status": "Not Found", # Indicate player wasn't in scraped results
                "position": "N/A",
                "to_par": "N/A",
                "thru": "N/A",
                "points": 0 # No points if not found
            })

    # Optional: Sort picks by box number if needed (requires parsing box name)
    # def get_box_num(pick): ...
    # detailed_picks.sort(key=get_box_num)

    return {"total_score": total_score, "picks": detailed_picks}


# --- API Endpoints ---

@app.route('/api/participants', methods=['GET'])
def get_participants():
    """Returns a list of participant names from the config."""
    if CONFIG_DATA is None or "participants" not in CONFIG_DATA:
        return jsonify({"error": "Server configuration not loaded or invalid."}), 500

    participant_names = [p.get("name", f"Unnamed Participant #{i+1}") for i, p in enumerate(CONFIG_DATA["participants"])]
    return jsonify({"participants": participant_names})


@app.route('/api/participant/<name>', methods=['GET'])
def get_participant_details(name):
    """Returns the picks and calculated score for a specific participant."""
    if CONFIG_DATA is None:
        return jsonify({"error": "Server configuration not loaded."}), 500

    # Find participant in config (case-sensitive match for simplicity)
    participant_config = None
    for p in CONFIG_DATA["participants"]:
        if p.get("name") == name:
            participant_config = p
            break

    if participant_config is None:
        return jsonify({"error": f"Participant '{name}' not found in configuration."}), 404

    # Get latest scores from DB
    golfer_scores_map, last_updated = get_latest_golfer_scores()

    if golfer_scores_map is None: # Indicates DB error
        return jsonify({"error": "Failed to retrieve scores from the database."}), 503 # Service Unavailable

    # Calculate score
    score_details = calculate_participant_score(participant_config, golfer_scores_map)

    return jsonify({
        "name": name,
        "score_details": score_details,
        "last_updated": last_updated or "N/A" # Use timestamp from score fetch
    })


@app.route('/api/leaderboard', methods=['GET'])
def get_leaderboard():
    """Calculates scores for all participants and returns a sorted leaderboard."""
    if CONFIG_DATA is None:
        return jsonify({"error": "Server configuration not loaded."}), 500

    # Get latest scores from DB (fetch once for all participants)
    golfer_scores_map, last_updated = get_latest_golfer_scores()

    if golfer_scores_map is None: # Indicates DB error
        return jsonify({"error": "Failed to retrieve scores from the database."}), 503

    leaderboard = []
    for participant_config in CONFIG_DATA["participants"]:
        participant_name = participant_config.get("name", "Unnamed Participant")
        if not participant_name: continue # Skip if config entry is malformed

        score_details = calculate_participant_score(participant_config, golfer_scores_map)
        leaderboard.append({
            "name": participant_name,
            "total_score": score_details["total_score"]
            # Add more details if needed, e.g., thru status of their top player?
        })

    # Sort leaderboard by total_score descending
    leaderboard.sort(key=lambda x: x["total_score"], reverse=True)

    return jsonify({
        "leaderboard": leaderboard,
        "last_updated": last_updated or "N/A" # Use timestamp from score fetch
    })

# --- Main Execution ---
if __name__ == '__main__':
    print("--- Starting Flask Server ---")
    # Attempt to load config on startup
    if not load_config():
        print("Halting server startup due to configuration errors.")
        # Depending on deployment, might want sys.exit(1) here
    else:
        # Check if DB exists initially, just as a warning
        if not os.path.exists(DB_FILE):
            print(f"Warning: Database file '{DB_FILE}' not found at startup. Scraper needs to run.")
        elif get_db() is None: # Check if table exists within DB
             print(f"Warning: DB file '{DB_FILE}' exists, but 'golfer_scores' table might be missing or connection failed.")

        print("Server attempting to start...")
        # Bind to 0.0.0.0 to be accessible within Docker network
        # Change debug=False for production
        # Note: Default Flask port is 5000, you had 8443 before, adjust as needed
        app.run(debug=True, host='0.0.0.0', port=5000)