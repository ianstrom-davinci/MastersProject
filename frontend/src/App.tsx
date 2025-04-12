// src/App.tsx
import { useState, useEffect } from 'react';
import axios from 'axios'; // or use built-in fetch
import './App.css'; // Basic styling

// Define TypeScript interface if using TS
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
  error?: string; // Optional error message from backend
}

function App() {
  // Use ScoreData interface for state typing
  const [data, setData] = useState<ScoreData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const fetchData = async () => {
    setLoading(true);
    setError(''); // Clear previous errors
    try {
      // Replace with your Flask server's address if not default
      // Make sure your Flask server (server.py) is running!
      const response = await axios.get<ScoreData>('/api/scores');
      setData(response.data);
      // Check if the backend itself sent an error message
      if(response.data.error) {
          setError(response.data.error);
          console.error("Backend error:", response.data.error);
      }
    } catch (err) {
      console.error("Error fetching data:", err);
      let errorMsg = 'Failed to fetch data from the server. Is it running?';
      if (axios.isAxiosError(err)) {
        if (err.response) {
          // The request was made and the server responded with a status code
          // that falls out of the range of 2xx
          errorMsg = `Server responded with error: ${err.response.status}`;
          console.error("Error response data:", err.response.data);
        } else if (err.request) {
          // The request was made but no response was received
          errorMsg = 'No response received from server. Check network or if server is running.';
          console.error("Error request:", err.request);
        } else {
          // Something happened in setting up the request that triggered an Error
          errorMsg = `Error setting up request: ${err.message}`;
        }
      } else if (err instanceof Error) {
          errorMsg = `An unexpected error occurred: ${err.message}`;
      }
      setError(errorMsg);
      setData(null); // Clear data on error
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData(); // Fetch data on initial load

    // Optional: Auto-refresh every 5 minutes (300000 ms)
    const intervalId = setInterval(fetchData, 300000);

    // Cleanup function to clear the interval when the component unmounts
    return () => clearInterval(intervalId);
  }, []); // Empty dependency array means run only on mount and unmount

  return (
    <div className="App">
      <h1>Masters Pool Standings</h1>

      {loading && <p>Loading scores...</p>}
      {error && <p style={{ color: 'red' }}>Error: {error}</p>}

      {/* Only render the table section if data exists and there's no top-level fetch error */}
      {data && !error && (
        <>
          <p>
            <strong>Total Score: {data.total_score}</strong>
            <br />
            <em>Last Updated: {data.last_updated}</em>
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
              {/* Check if data.scores is actually an array and has items */}
              {data.scores && data.scores.length > 0 ? (
                data.scores.map((player, index) => (
                  // Using index as key is okay for this simple list if players don't reorder often
                  // but using player_name or a unique ID would be better if available
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
                   {/* Display message based on whether backend reported an error or just empty data */}
                   <td colSpan={6}>{data.error ? 'Error loading scores from backend.' : 'No scores available yet. Run the scraper.'}</td>
                 </tr>
              )}
            </tbody>
          </table>
        </>
      )}
      {/* Show message if data is null after initial load attempt and no specific error was set */}
      {!loading && !data && !error && <p>Could not load data. Ensure the scraper has run and the server is running.</p>}
    </div>
  );
}

export default App;