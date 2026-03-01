import React, { useState, useEffect } from 'react';
import axios from 'axios';
import io from 'socket.io-client';
import AmbulanceMap from './components/AmbulanceMap';
import ControlPanel from './components/ControlPanel';
import AmbulanceList from './components/AmbulanceList';
import AmbulanceHistory from './components/AmbulanceHistory';
import './App.css';

const BACKEND_URL = 'http://localhost:5000';

function App() {
  const [socket, setSocket] = useState(null);
  const [hospitals, setHospitals] = useState([]);
  const [simulationRunning, setSimulationRunning] = useState(false);
  const [vehicleCount, setVehicleCount] = useState(0);
  const [signalCount, setSignalCount] = useState(0);
  const [readyForAmbulances, setReadyForAmbulances] = useState(false);
  const [ambulances, setAmbulances] = useState([]);
  const [vehicles, setVehicles] = useState([]);
  const [trafficLights, setTrafficLights] = useState({});
  const [historyOpen, setHistoryOpen] = useState(false);
  const [historyRefresh, setHistoryRefresh] = useState(0);
  
  // ✅ NEW: State for zoom to ambulance
  const [zoomToAmbulance, setZoomToAmbulance] = useState(null);

  // Initialize
  useEffect(() => {
    // Load hospitals
    axios.get(`${BACKEND_URL}/api/hospitals`)
      .then(res => setHospitals(res.data))
      .catch(err => console.error('Failed to load hospitals:', err));

    // Connect WebSocket
    const newSocket = io(BACKEND_URL);
    setSocket(newSocket);

    newSocket.on('connect', () => {
      console.log('✅ Connected to backend');
    });

    newSocket.on('simulation_update', (data) => {
      setVehicleCount(data.vehicle_count);
      
      // Remove duplicate ambulances by ID
      const uniqueAmbulances = data.ambulances 
        ? Array.from(new Map(data.ambulances.map(amb => [amb.id, amb])).values())
        : [];
      
      setAmbulances(uniqueAmbulances);
      setVehicles(data.vehicles || []);
      setTrafficLights(data.traffic_lights || {});
      setSignalCount(Object.keys(data.traffic_lights || {}).length);
    });

    newSocket.on('ambulance_spawned', (data) => {
      console.log('🚑 Ambulance spawned:', data);
    });

    newSocket.on('ambulance_completed', (data) => {
      console.log('🏥 Ambulance completed:', data);
      
      // Filter out trips with duration < 11 seconds
      if (data.travel_time < 11) {
        console.warn(`⚠️ Rejected trip ${data.ambulance_id}: Duration too short (${data.travel_time}s)`);
        setAmbulances(prev => prev.filter(amb => amb.id !== data.ambulance_id));
        return;
      }
      
      // Check if this ambulance ID already exists in history
      const existing = localStorage.getItem('ambulance_history');
      const history = existing ? JSON.parse(existing) : [];
      const isDuplicate = history.some(item => item.id === data.ambulance_id);
      
      if (isDuplicate) {
        console.warn(`⚠️ Duplicate trip detected: ${data.ambulance_id} - Not saving again`);
        setAmbulances(prev => prev.filter(amb => amb.id !== data.ambulance_id));
        return;
      }
      
      const historyEntry = {
        id: data.ambulance_id,
        startTime: data.start_time,
        endTime: data.end_time,
        travelTime: data.travel_time,
        source: data.source,
        destination: data.destination,
        mode: data.mode,
        routeLength: data.route_length
      };
      
      console.log('💾 Saving to history:', historyEntry);
      
      saveToHistory(historyEntry);
      setAmbulances(prev => prev.filter(amb => amb.id !== data.ambulance_id));
      setHistoryRefresh(prev => prev + 1);
      
      const mins = Math.floor(data.travel_time / 60);
      const secs = Math.floor(data.travel_time % 60);
      alert(`🏥 Ambulance arrived at ${data.destination}!\nTravel time: ${mins}m ${secs}s`);
    });

    newSocket.on('simulation_started', () => {
      setSimulationRunning(true);
    });

    newSocket.on('simulation_ended', () => {
      setSimulationRunning(false);
    });

    // Check simulation status
    const checkStatus = setInterval(() => {
      axios.get(`${BACKEND_URL}/api/simulation/status`)
        .then(res => {
          setSimulationRunning(res.data.running);
          setVehicleCount(res.data.vehicle_count);
          setReadyForAmbulances(res.data.ready_for_ambulances);
        })
        .catch(err => console.error('Status check failed:', err));
    }, 2000);

    return () => {
      clearInterval(checkStatus);
      newSocket.disconnect();
    };
  }, []);

  const saveToHistory = (entry) => {
    try {
      const existing = localStorage.getItem('ambulance_history');
      const history = existing ? JSON.parse(existing) : [];
      
      history.push(entry);
      
      localStorage.setItem('ambulance_history', JSON.stringify(history));
      
      console.log('✅ Saved to localStorage. Total entries:', history.length);
    } catch (err) {
      console.error('❌ Failed to save history:', err);
    }
  };

  const startSimulation = async () => {
    try {
      await axios.post(`${BACKEND_URL}/api/simulation/start`);
      alert('Simulation started!');
    } catch (err) {
      alert(err.response?.data?.error || 'Failed to start simulation');
    }
  };

  const spawnAmbulance = async (source, destination, mode) => {
    try {
      const res = await axios.post(`${BACKEND_URL}/api/spawn-ambulance`, {
        source,
        destination,
        mode
      });
      console.log('Ambulance spawned:', res.data);
    } catch (err) {
      alert(err.response?.data?.error || 'Failed to spawn ambulance');
    }
  };

  // ✅ NEW: Function to zoom to ambulance
  const handleZoomToAmbulance = (ambulanceId) => {
    // Find the ambulance in the vehicles array
    const ambulance = vehicles.find(v => v.id === ambulanceId);
    
    if (ambulance) {
      setZoomToAmbulance({
        id: ambulanceId,
        lat: ambulance.lat,
        lon: ambulance.lon,
        timestamp: Date.now() // Force re-render
      });
      
      console.log(`🔍 Zooming to ambulance: ${ambulanceId} at (${ambulance.lat}, ${ambulance.lon})`);
    } else {
      console.warn(`⚠️ Ambulance ${ambulanceId} not found in vehicles`);
    }
  };

  return (
    <div className="App">
      <header className="App-header">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', width: '100%' }}>
          <h1>🚑 Ambulance Routing System</h1>
          <button
            onClick={() => setHistoryOpen(true)}
            style={{
              padding: '10px 20px',
              background: 'rgba(255,255,255,0.2)',
              border: '2px solid rgba(255,255,255,0.4)',
              color: 'white',
              borderRadius: '8px',
              fontSize: '14px',
              fontWeight: '600',
              cursor: 'pointer',
              transition: 'all 0.3s',
              display: 'flex',
              alignItems: 'center',
              gap: '8px'
            }}
            onMouseEnter={(e) => e.target.style.background = 'rgba(255,255,255,0.3)'}
            onMouseLeave={(e) => e.target.style.background = 'rgba(255,255,255,0.2)'}
          >
            📋 History
          </button>
        </div>
        <div className="status-bar">
          <span className={simulationRunning ? 'status-running' : 'status-stopped'}>
            {simulationRunning ? '🟢 Running' : '🔴 Stopped'}
          </span>
          <span>🚗 Vehicles: {vehicleCount}</span>
          <span>🚑 Ambulances: {ambulances.length}</span>
          <span>🚦 Signals: {signalCount}</span>
          {!readyForAmbulances && simulationRunning && (
            <span className="waiting">
              <span className="spinner-icon"></span>
              Building traffic...
            </span>
          )}
        </div>
      </header>

      <div className="main-container">
        <ControlPanel
          hospitals={hospitals}
          simulationRunning={simulationRunning}
          readyForAmbulances={readyForAmbulances}
          onStartSimulation={startSimulation}
          onSpawnAmbulance={spawnAmbulance}
        />

        <AmbulanceMap
          hospitals={hospitals}
          ambulances={ambulances}
          vehicles={vehicles}
          trafficLights={trafficLights}
          zoomToAmbulance={zoomToAmbulance}
        />

        <AmbulanceList 
          ambulances={ambulances}
          onZoomToAmbulance={handleZoomToAmbulance}
        />
      </div>

      <AmbulanceHistory 
        isOpen={historyOpen}
        onClose={() => setHistoryOpen(false)}
        refreshTrigger={historyRefresh}
      />
    </div>
  );
}

export default App;
