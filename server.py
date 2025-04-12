# File: server.py
import sqlite3
from flask import Flask, jsonify
from flask_cors import CORS # Import CORS
import os

app = Flask(__name__)
CORS(app) # Enable CORS for all routes, allowing React dev server to connect

DB_FILE = "/app/data/masters_scores.db"

def get_db():
    """Connects to the specific database."""
    # Check if DB exists before trying to connect
    if not os.path.exists(DB_FILE):
         return None # Return None if DB file is not found
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row # Return rows as dictionary-like objects
        return conn
    except sqlite3.Error as e:
        print(f"Database connection error: {e}")
        return None # Return None on connection error

@app.route('/api/scores', methods=['GET'])
def get_scores():
    conn = get_db()
    if conn is None:
         # Handle case where DB doesn't exist or connection failed
         return jsonify({
             "error": "Database not found or connection failed. Run the scraper script first.",
             "scores": [],
             "total_score": 0,
             "last_updated": "N/A"
         }), 503 # Service Unavailable status

    try:
        cursor = conn.cursor()

        # Fetch player scores
        cursor.execute("SELECT box_name, player_name, position, thru, to_par, points FROM player_scores ORDER BY id") # Use ID order which reflects box order
        scores_raw = cursor.fetchall()
        # Convert Row objects to plain dictionaries
        scores = [dict(row) for row in scores_raw]

        # Fetch metadata
        cursor.execute("SELECT total_score, last_updated FROM leaderboard_meta WHERE id = 1")
        meta_raw = cursor.fetchone()
        meta = dict(meta_raw) if meta_raw else {"total_score": 0, "last_updated": "N/A"}

        conn.close()

        return jsonify({
            "scores": scores,
            "total_score": meta.get("total_score", 0),
            "last_updated": meta.get("last_updated", "N/A")
        })
    except sqlite3.Error as e:
        print(f"Database query error: {e}")
        if conn: conn.close()
        return jsonify({"error": f"Database query failed: {e}", "scores": [], "total_score": 0, "last_updated": "N/A"}), 500 # Internal Server Error
    except Exception as e:
        print(f"Unexpected server error: {e}")
        if conn: conn.close()
        return jsonify({"error": f"An unexpected server error occurred: {e}", "scores": [], "total_score": 0, "last_updated": "N/A"}), 500

if __name__ == '__main__':
    print(f"Starting Flask server. API endpoint: http://localhost:5000/api/scores")
    print(f"Ensure '{DB_FILE}' exists by running the scraper script first.")
    app.run(debug=True, host='0.0.0.0', port=8443) # Use debug=False for production, host='0.0.0.0' makes it accessible on your network