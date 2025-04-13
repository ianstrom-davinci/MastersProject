# File: server.py
# Rewritten to load config at module level for Gunicorn

import sqlite3
import json
import os
import re
from flask import Flask, jsonify
from flask_cors import CORS
from datetime import datetime, timezone

app = Flask(__name__)
CORS(app) # Enable CORS for all routes

# --- Configuration Paths ---
CONFIG_FILE = "/app/config.json" # Path inside the container
DB_FILE = "/app/data/masters_scores.db" # Path inside the container

# --- Global variable to hold config data ---
CONFIG_DATA = None

# --- Helper Functions ---

def load_config():
    """Loads the configuration from config.json."""
    global CONFIG_DATA
    config_status_message = ""
    if not os.path.exists(CONFIG_FILE):
        config_status_message = f"CRITICAL ERROR: Configuration file not found at {CONFIG_FILE}"
        print(config_status_message)
        CONFIG_DATA = None # Ensure it's None on failure
        return False, config_status_message

    try:
        with open(CONFIG_FILE, 'r') as f:
            loaded_data = json.load(f)

        # Basic validation
        if "participants" not in loaded_data or not isinstance(loaded_data["participants"], list):
             config_status_message = "CRITICAL ERROR: Config missing 'participants' list or is not a list."
             print(config_status_message)
             CONFIG_DATA = None # Invalidate config
             return False, config_status_message
        if "pool_structure" not in loaded_data:
             config_status_message = "CRITICAL ERROR: Config missing 'pool_structure'."
             print(config_status_message)
             CONFIG_DATA = None
             return False, config_status_message

        CONFIG_DATA = loaded_data # Assign only after successful load and validation
        config_status_message = f"Configuration loaded successfully from {CONFIG_FILE}. Found {len(CONFIG_DATA['participants'])} participants."
        print(config_status_message)
        return True, config_status_message

    except json.JSONDecodeError as e:
        config_status_message = f"CRITICAL ERROR: Failed to parse {CONFIG_FILE}: {e}"
        print(config_status_message)
        CONFIG_DATA = None
        return False, config_status_message
    except Exception as e:
        config_status_message = f"CRITICAL ERROR: Unexpected error loading config: {e}"
        print(config_status_message)
        CONFIG_DATA = None
        return False, config_status_message

# --- Load Configuration Attempt on Module Import ---
# This code runs when Gunicorn imports the 'server:app' module
print("--- Initializing server module ---")
config_loaded, load_message = load_config()
if not config_loaded:
   print(f"WARNING: Initial configuration load failed: {load_message}")
   # The app will still start, but endpoints will return errors until config is fixed/reloaded.
print("--- Server module initialization complete ---")


# --- Database Helper ---
def get_db():
    """Connects to the SQLite database."""
    if not os.path.exists(DB_FILE):
         print(f"Warning: Database file {DB_FILE} not found.")
         return None
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='golfer_scores';")
        if cursor.fetchone() is None:
            print(f"Warning: Database exists, but 'golfer_scores' table not found. Run scraper.")
            conn.close()
            return None
        return conn
    except sqlite3.Error as e:
        print(f"Database connection or check error: {e}")
        return None

# --- Scoring Logic ---
def get_points_for_position(position_str: str) -> int:
    """Calculates points based on golfer's position string (copied from scraper)."""
    if position_str is None: return 0
    position_str = position_str.upper().strip()
    if position_str in ["CUT", "WD", "DQ", "--", "", "N/A"]: return 0
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

# --- Score Fetching ---
def get_latest_golfer_scores() -> tuple[dict | None, str | None]:
    """Fetches all golfer scores from the DB and the latest update time."""
    conn = get_db()
    if conn is None:
        return None, None

    scores_map = {}
    last_updated = "N/A"
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT name, pos, to_par, thru, last_updated, is_amateur FROM golfer_scores")
        rows = cursor.fetchall()
        if not rows:
            print("Warning: 'golfer_scores' table is empty.")
            conn.close()
            return {}, "Never"

        cursor.execute("SELECT MAX(last_updated) as latest_update FROM golfer_scores")
        latest_update_row = cursor.fetchone()
        if latest_update_row and latest_update_row['latest_update']:
            last_updated = latest_update_row['latest_update']

        for row in rows:
            player_data = dict(row)
            if player_data.get('name'):
                 scores_map[player_data['name'].strip().lower()] = player_data
            else:
                 print(f"Warning: DB row found with missing name: {player_data}")

        conn.close()
        # Reduce log noise, only print if necessary or in debug mode
        # print(f"Fetched {len(scores_map)} golfer scores from DB. Last updated: {last_updated}")
        return scores_map, last_updated

    except sqlite3.Error as e:
        print(f"Database query error in get_latest_golfer_scores: {e}")
        if conn: conn.close()
        return None, None
    except Exception as e:
        print(f"Unexpected error in get_latest_golfer_scores: {e}")
        if conn: conn.close()
        return None, None

# --- Score Calculation ---
def calculate_participant_score(participant_config: dict, golfer_scores_map: dict) -> dict:
    """Calculates score for one participant based on their picks and live scores."""
    total_score = 0
    detailed_picks = []
    participant_name = participant_config.get("name", "Unknown Participant")
    participant_picks = participant_config.get("picks", {})

    if not golfer_scores_map:
        print(f"Warning: Cannot calculate score for {participant_name}, golfer scores map is empty/None.")
        for box_name, picked_golfer_original in participant_picks.items():
             detailed_picks.append({
                "box": box_name, "player_name": picked_golfer_original,
                "status": "Error: Score data unavailable", "position": "N/A",
                "to_par": "N/A", "thru": "N/A", "points": 0
             })
        return {"total_score": 0, "picks": detailed_picks}

    for box_name, picked_golfer_original in participant_picks.items():
        picked_golfer_lower = picked_golfer_original.strip().lower()
        golfer_data = golfer_scores_map.get(picked_golfer_lower)

        if golfer_data:
            position = golfer_data.get('pos', 'N/A')
            points = get_points_for_position(position)
            total_score += points
            display_name = picked_golfer_original
            if golfer_data.get('is_amateur'):
                 display_name += " (a)"

            detailed_picks.append({
                "box": box_name, "player_name": display_name, "status": "Found",
                "position": position, "to_par": golfer_data.get('to_par', 'N/A'),
                "thru": golfer_data.get('thru', 'N/A'), "points": points
            })
        else:
            detailed_picks.append({
                "box": box_name, "player_name": picked_golfer_original,
                "status": "Not Found", "position": "N/A",
                "to_par": "N/A", "thru": "N/A", "points": 0
            })

    # Optional: Sort picks if needed
    # detailed_picks.sort(...)

    return {"total_score": total_score, "picks": detailed_picks}


# --- API Endpoints ---

@app.route('/api/participants', methods=['GET'])
def get_participants():
    """Returns a list of participant names from the config."""
    if CONFIG_DATA is None:
        # Optional: Add a config reload attempt here if desired
        # global config_loaded, load_message
        # config_loaded, load_message = load_config()
        # if not config_loaded:
        #    return jsonify({"error": f"Server configuration failed to load: {load_message}"}), 500
        return jsonify({"error": "Server configuration is not loaded."}), 500 # Consistent error

    participant_names = [p.get("name", f"Unnamed Participant #{i+1}") for i, p in enumerate(CONFIG_DATA["participants"])]
    return jsonify({"participants": participant_names})


@app.route('/api/participant/<name>', methods=['GET'])
def get_participant_details(name):
    """Returns the picks and calculated score for a specific participant."""
    if CONFIG_DATA is None:
        return jsonify({"error": "Server configuration is not loaded."}), 500

    participant_config = None
    for p in CONFIG_DATA["participants"]:
        if p.get("name") == name:
            participant_config = p
            break

    if participant_config is None:
        return jsonify({"error": f"Participant '{name}' not found in configuration."}), 404

    golfer_scores_map, last_updated = get_latest_golfer_scores()

    if golfer_scores_map is None:
        return jsonify({"error": "Failed to retrieve scores from the database."}), 503

    score_details = calculate_participant_score(participant_config, golfer_scores_map)

    return jsonify({
        "name": name,
        "score_details": score_details,
        "last_updated": last_updated or "N/A"
    })


@app.route('/api/leaderboard', methods=['GET'])
def get_leaderboard():
    """Calculates scores for all participants and returns a sorted leaderboard."""
    if CONFIG_DATA is None:
        return jsonify({"error": "Server configuration is not loaded."}), 500

    golfer_scores_map, last_updated = get_latest_golfer_scores()

    if golfer_scores_map is None:
        return jsonify({"error": "Failed to retrieve scores from the database."}), 503

    leaderboard = []
    for participant_config in CONFIG_DATA["participants"]:
        participant_name = participant_config.get("name", "Unnamed Participant")
        if not participant_name: continue

        score_details = calculate_participant_score(participant_config, golfer_scores_map)
        leaderboard.append({
            "name": participant_name,
            "total_score": score_details["total_score"]
        })

    leaderboard.sort(key=lambda x: x["total_score"], reverse=True)

    return jsonify({
        "leaderboard": leaderboard,
        "last_updated": last_updated or "N/A"
    })

# --- Main Execution (Only used for direct `python server.py` run) ---
if __name__ == '__main__':
    print("--- Starting Flask Server (direct execution via python server.py) ---")
    # Config is loaded at module level above, check if it succeeded
    if CONFIG_DATA is None:
         print("WARNING: Direct run started, but config was not loaded successfully.")
    else:
         print("Direct run started, config loaded.")

    # Check DB status for direct run
    db_conn = get_db()
    if db_conn:
        print(f"Database '{DB_FILE}' connected successfully.")
        db_conn.close()
    else:
        print(f"Warning: Database '{DB_FILE}' connection/check failed on startup.")

    print("Starting Flask development server on port 8443...")
    # Make direct run listen on the same port Gunicorn uses internally for consistency
    app.run(debug=True, host='0.0.0.0', port=8443)