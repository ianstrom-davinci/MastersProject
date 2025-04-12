// src/App.tsx
import { useState, useEffect } from 'react';
import axios from 'axios';
import './App.css';

interface Score {
  box_name: string;
  player_name: string;
  position: string;
  thru: string;
  to_par: string;
  points: number;
}

interface ScoreData {
  scores: Score[];
  total_score: number;
  last_updated: string;
  error?: string;
}

// Helper function to format the date/time
const formatTimestamp = (timestamp: string): string => {
  try {
    const date = new Date(timestamp);
    return date.toLocaleString('en-CA', { // Use Canadian English locale
      timeZone: 'America/Denver',       // Timezone for Calgary/Mountain Time
      dateStyle: 'medium',              // e.g., "Sep 21, 2023"
      timeStyle: 'short',               // e.g., "1:35 PM"
    });
  } catch (e) {
    console.error("Error formatting timestamp:", e);
    return timestamp; // Fallback to original string
  }
};


function App() {
  const [data, setData] = useState<ScoreData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const fetchData = async () => {
    setLoading(true);
    setError('');
    try {
      const response = await axios.get<ScoreData>('/api/scores');
      setData(response.data);
      if(response.data.error) {
          setError(response.data.error);
          console.error("Backend error:", response.data.error);
      }
    } catch (err) {
      console.error("Error fetching data:", err);
      let errorMsg = 'Failed to fetch data from the server. Is it running?';
      if (axios.isAxiosError(err)) {
        if (err.response) {
          errorMsg = `Server responded with error: ${err.response.status}`;
          console.error("Error response data:", err.response.data);
        } else if (err.request) {
          errorMsg = 'No response received from server. Check network or if server is running.';
          console.error("Error request:", err.request);
        } else {
          errorMsg = `Error setting up request: ${err.message}`;
        }
      } else if (err instanceof Error) {
          errorMsg = `An unexpected error occurred: ${err.message}`;
      }
      setError(errorMsg);
      setData(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    const intervalId = setInterval(fetchData, 300000); // Refresh every 5 mins
    return () => clearInterval(intervalId);
  }, []);

  return (
    <div className="App">
      <h1>Masters Pool Standings</h1>

      {loading && <p>Loading scores...</p>}
      {error && <p style={{ color: 'red' }}>Error: {error}</p>}

      {data && !error && (
        <>
          <p>
            <strong>Total Score: {data.total_score}</strong>
            <br />
            <em>Last Updated: {formatTimestamp(data.last_updated)} (MT)</em>
          </p>
          <button onClick={fetchData} disabled={loading}>
            {loading ? 'Refreshing...' : 'Refresh Now'}
          </button>
          <table>
            <thead>
              <tr>
                <th>Box</th>
                <th>Player</th>
                <th>Pos</th>
                <th>Thru</th>
                <th>To Par</th>
                <th>Points</th>
              </tr>
            </thead>
            <tbody>
              {data.scores && data.scores.length > 0 ? (
                data.scores.map((player, index) => (
                  <tr key={player.player_name + index}>
                    <td>{player.box_name}</td>
                    <td>{player.player_name}</td>
                    <td>{player.position}</td>
                    <td>{player.thru}</td>
                    <td>{player.to_par}</td>
                    <td>{player.points}</td>
                  </tr>
                ))
              ) : (
                 <tr>
                   <td colSpan={6}>{data.error ? 'Error loading scores from backend.' : 'No scores available yet. Run the scraper.'}</td>
                 </tr>
              )}
            </tbody>
          </table>

          {/* --- Scoring Legend Section --- */}
          <div className="scoring-legend" style={{ marginTop: '2rem', textAlign: 'left', paddingLeft: '1rem' }}>
            <h2>Scoring Legend (Based on Final Placement)</h2>
            <ul style={{ listStyleType: 'disc', paddingLeft: '20px' }}>
              <li><strong>Winner:</strong> 15 points</li>
              <li><strong>Top 5 Finish:</strong> 9 points</li>
              <li><strong>6th - 15th Place:</strong> 6 points</li>
              <li><strong>16th - 29th Place:</strong> 4 points</li>
              <li><strong>30th Place or Worse:</strong> 2 points</li>
              <li><strong>Missed Cut (MC):</strong> 0 points</li>
            </ul>
          </div>
          {/* --- End Scoring Legend Section --- */}

        </>
      )}
      {!loading && !data && !error && <p>Could not load data. Ensure the scraper has run and the server is running.</p>}
    </div>
  );
}

export default App;