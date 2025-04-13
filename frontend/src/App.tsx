// src/App.tsx
import { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import './App.css'; // Keep your existing styles

// --- New TypeScript Interfaces ---

// For a single pick's details (from /api/participant/<name>)
interface ParticipantPickDetail {
  box: string;
  player_name: string;
  status: string; // "Found", "Not Found", "Error"
  position: string;
  to_par: string;
  thru: string;
  points: number;
}

// For the response from /api/participant/<name>
interface ParticipantDetailData {
  name: string;
  score_details: {
    total_score: number;
    picks: ParticipantPickDetail[];
  };
  last_updated: string;
}

// For an entry in the leaderboard (from /api/leaderboard)
interface LeaderboardEntry {
  name: string;
  total_score: number;
}

// For the response from /api/leaderboard
interface LeaderboardData {
  leaderboard: LeaderboardEntry[];
  last_updated: string;
}

// --- Helper Function (Unchanged) ---
const formatTimestamp = (timestamp: string): string => {
  try {
    // Handle "N/A" or "Never" gracefully
    if (!timestamp || timestamp === "N/A" || timestamp === "Never") {
        return "N/A";
    }
    const date = new Date(timestamp);
    // Check if the date is valid before formatting
    if (isNaN(date.getTime())) {
      return timestamp; // Return original if invalid date
    }
    return date.toLocaleString('en-CA', {
      timeZone: 'America/Denver',
      dateStyle: 'medium',
      timeStyle: 'short',
    });
  } catch (e) {
    console.error("Error formatting timestamp:", e);
    return timestamp;
  }
};

// --- Main App Component ---

function App() {
  // State for participants list and selected view
  const [participants, setParticipants] = useState<string[]>([]);
  const [selectedView, setSelectedView] = useState<string | null>(null); // 'Leaderboard' or participant name

  // State for the currently displayed data (participant or leaderboard)
  const [viewData, setViewData] = useState<ParticipantDetailData | LeaderboardData | null>(null);
  const [lastUpdated, setLastUpdated] = useState<string>('N/A');

  // General loading/error state
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // --- Data Fetching Logic ---

  // Fetch the list of participants on initial load
  // Fetch the list of participants on initial load
  const fetchParticipants = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      // --- IMPORTANT: Update API Host if needed ---
      // Use '/api/participants' assuming proxy or same-origin deployment
      const response = await axios.get<{ participants: string[] }>('/api/participants');
      const fetchedParticipants = response.data.participants;
      setParticipants(fetchedParticipants);

      // --- CHANGE HERE: Always default to Leaderboard ---
      setSelectedView('Leaderboard'); // Set Leaderboard as the default view

    } catch (err) {
      console.error("Error fetching participants:", err);
      handleFetchError(err, "fetch participants");
      setParticipants([]);
      setSelectedView('Leaderboard'); // Fallback on error still makes sense
    } finally {
      // Don't setLoading(false) here, let the subsequent view fetch handle it
    }
  }, []); // Empty dependency array, runs once on mount

    } catch (err) {
      console.error("Error fetching participants:", err);
      handleFetchError(err, "fetch participants");
      setParticipants([]);
      setSelectedView('Leaderboard'); // Fallback on error
    } finally {
      // Don't setLoading(false) here, let the subsequent view fetch handle it
    }
  }, []); // Empty dependency array, runs once on mount

  // Fetch data for the currently selected view (participant or leaderboard)
  const fetchViewData = useCallback(async (view: string | null) => {
    if (!view) return; // Don't fetch if no view is selected

    setLoading(true);
    setError('');
    setViewData(null); // Clear previous data

    try {
      let response;
      // --- IMPORTANT: Update API Host if needed ---
      const baseURL = ''; // Use 'http://localhost:5000' or similar if needed, else '' for proxy
      if (view === 'Leaderboard') {
        response = await axios.get<LeaderboardData>(`${baseURL}/api/leaderboard`);
        setLastUpdated(response.data.last_updated);
      } else {
        // Assume view is a participant name
        response = await axios.get<ParticipantDetailData>(`${baseURL}/api/participant/${encodeURIComponent(view)}`);
        setLastUpdated(response.data.last_updated);
      }
      setViewData(response.data);
      // Check for backend-reported errors within the data (if applicable)
      // if(response.data.error) { setError(response.data.error); }

    } catch (err) {
      console.error(`Error fetching data for view '${view}':`, err);
      handleFetchError(err, `fetch ${view} data`);
      setViewData(null);
      setLastUpdated('N/A');
    } finally {
      setLoading(false);
    }
  }, []); // Re-run if fetchViewData definition changes (shouldn't often)

  // Helper for consistent error message handling
  const handleFetchError = (err: unknown, context: string) => {
      let errorMsg = `Failed to ${context}.`;
      if (axios.isAxiosError(err)) {
        if (err.response) {
          errorMsg = `Server error during ${context}: ${err.response.status} - ${err.response.data?.error || err.message}`;
          console.error("Error response data:", err.response.data);
        } else if (err.request) {
          errorMsg = `No response received during ${context}. Server down?`;
          console.error("Error request:", err.request);
        } else {
          errorMsg = `Request setup error during ${context}: ${err.message}`;
        }
      } else if (err instanceof Error) {
          errorMsg = `Unexpected error during ${context}: ${err.message}`;
      }
      setError(errorMsg);
  }

  // --- Effects ---

  // Initial effect to fetch participants
  useEffect(() => {
    fetchParticipants();
  }, [fetchParticipants]); // Depends on fetchParticipants callback

  // Effect to fetch data when the selected view changes
  useEffect(() => {
    if (selectedView) {
      fetchViewData(selectedView);
    }
  }, [selectedView, fetchViewData]); // Depends on selected view and the fetch callback

  // Effect for periodic refresh of the *current* view's data
  useEffect(() => {
    const intervalId = setInterval(() => {
      if (selectedView) {
          console.log(`Refreshing data for view: ${selectedView}`);
          fetchViewData(selectedView); // Re-fetch data for the current view
      }
    }, 300000); // Refresh every 5 minutes (300,000 ms)

    return () => clearInterval(intervalId); // Cleanup on unmount
  }, [selectedView, fetchViewData]); // Re-create interval if view changes

  // --- Rendering Logic ---

  const renderContent = () => {
    if (loading) return <p>Loading...</p>;
    if (error) return <p style={{ color: 'red' }}>Error: {error}</p>;
    if (!viewData) return <p>No data available for {selectedView || 'the selected view'}.</p>;

    // --- Leaderboard View ---
    if (selectedView === 'Leaderboard' && 'leaderboard' in viewData) {
      const leaderboardData = viewData as LeaderboardData;
      return (
        <table>
          <thead>
            <tr>
              <th>Rank</th>
              <th>Name</th>
              <th>Total Score</th>
            </tr>
          </thead>
          <tbody>
            {leaderboardData.leaderboard && leaderboardData.leaderboard.length > 0 ? (
              leaderboardData.leaderboard.map((entry, index) => (
                <tr key={entry.name}>
                  <td>{index + 1}</td>
                  <td>{entry.name}</td>
                  <td>{entry.total_score}</td>
                </tr>
              ))
            ) : (
              <tr><td colSpan={3}>Leaderboard data is not available.</td></tr>
            )}
          </tbody>
        </table>
      );
    }

    // --- Participant Detail View ---
    if (selectedView !== 'Leaderboard' && 'score_details' in viewData) {
      const participantData = viewData as ParticipantDetailData;
      return (
        <>
          <h2>{participantData.name}'s Picks</h2>
          <p><strong>Total Score: {participantData.score_details.total_score}</strong></p>
          <table>
            <thead>
              <tr>
                <th>Box</th>
                <th>Player</th>
                <th>Pos</th>
                <th>Thru</th>
                <th>To Par</th>
                <th>Points</th>
                <th>Status</th>{/* Added Status */}
              </tr>
            </thead>
            <tbody>
              {participantData.score_details.picks && participantData.score_details.picks.length > 0 ? (
                participantData.score_details.picks.map((pick, index) => (
                  <tr key={pick.player_name + index}>
                    <td>{pick.box}</td>
                    <td>{pick.player_name}</td>
                    <td>{pick.position}</td>
                    <td>{pick.thru}</td>
                    <td>{pick.to_par}</td>
                    <td>{pick.points}</td>
                    <td>{pick.status}</td> {/* Display status */}
                  </tr>
                ))
              ) : (
                 <tr><td colSpan={7}>No pick data available for this participant.</td></tr>
              )}
            </tbody>
          </table>
        </>
      );
    }

    // Fallback if data structure doesn't match expected types
    return <p>Could not display data for {selectedView}. Unexpected format.</p>;
  };

  return (
    <div className="App">
      <h1>Masters Pool Standings</h1>

      {/* --- View Selection --- */}
      <div className="view-selector" style={{ marginBottom: '1rem' }}>
        {participants.map(name => (
          <button
            key={name}
            onClick={() => setSelectedView(name)}
            disabled={loading || selectedView === name}
            style={{ marginRight: '0.5rem', fontWeight: selectedView === name ? 'bold' : 'normal' }}
          >
            {name}
          </button>
        ))}
        <button
          onClick={() => setSelectedView('Leaderboard')}
          disabled={loading || selectedView === 'Leaderboard'}
          style={{ fontWeight: selectedView === 'Leaderboard' ? 'bold' : 'normal' }}
        >
          Leaderboard
        </button>
      </div>

      {/* --- Timestamp and Refresh --- */}
      <div style={{ marginBottom: '1rem' }}>
          <em>Last Updated: {formatTimestamp(lastUpdated)} (MT)</em>
          <button onClick={() => fetchViewData(selectedView)} disabled={loading} style={{ marginLeft: '1rem' }}>
            {loading ? 'Refreshing...' : 'Refresh Now'}
          </button>
      </div>

      {/* --- Dynamic Content Area --- */}
      {renderContent()}

      {/* --- Scoring Legend (Optional - keep or remove) --- */}
      <div className="scoring-legend" style={{ marginTop: '2rem', textAlign: 'left', paddingLeft: '1rem' }}>
        <h2>Scoring Legend</h2>
         <ul style={{ listStyleType: 'disc', paddingLeft: '20px' }}>
            <li><strong>Winner:</strong> 15 points</li>
            <li><strong>Top 5 Finish:</strong> 9 points</li>
            <li><strong>6th - 15th Place:</strong> 6 points</li>
            <li><strong>16th - 29th Place:</strong> 4 points</li>
            <li><strong>30th Place or Worse:</strong> 2 points</li>
            <li><strong>Missed Cut (MC) / WD / DQ:</strong> 0 points</li>
          </ul>
      </div>
    </div>
  );
}

export default App;