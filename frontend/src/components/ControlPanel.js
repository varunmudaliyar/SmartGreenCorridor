import React, { useState } from 'react';

function ControlPanel({ 
  hospitals, 
  simulationRunning, 
  readyForAmbulances, 
  onStartSimulation, 
  onSpawnAmbulance 
}) {
  const [source, setSource] = useState(0);
  const [destination, setDestination] = useState(1);
  const [mode, setMode] = useState('normal');

  const handleSpawn = () => {
    if (source === destination) {
      alert('Source and destination cannot be the same!');
      return;
    }
    onSpawnAmbulance(source, destination, mode);
  };

  return (
    <div className="control-panel">
      <h2>Control Panel</h2>

      {/* Simulation Control */}
      <div className="control-section">
        <h3>Simulation</h3>
        {!simulationRunning ? (
          <button className="btn btn-primary" onClick={onStartSimulation}>
            ▶️ Start Simulation
          </button>
        ) : (
          <div>
            <p style={{ fontSize: 12, color: '#10b981', marginBottom: 10 }}>
              ✅ Simulation Running
            </p>
            {!readyForAmbulances && (
              <p style={{ fontSize: 11, color: '#f59e0b' }}>
                ⏳ Building traffic... (need 100 vehicles)
              </p>
            )}
          </div>
        )}
      </div>

      {/* Ambulance Spawn */}
      <div className="control-section">
        <h3>Spawn Ambulance</h3>

        <div className="form-group">
          <label>Source Hospital</label>
          <select value={source} onChange={(e) => setSource(Number(e.target.value))}>
            {hospitals.map((h, i) => (
              <option key={i} value={i}>
                {i}. {h.name}
              </option>
            ))}
          </select>
        </div>

        <div className="form-group">
          <label>Destination Hospital</label>
          <select value={destination} onChange={(e) => setDestination(Number(e.target.value))}>
            {hospitals.map((h, i) => (
              <option key={i} value={i}>
                {i}. {h.name}
              </option>
            ))}
          </select>
        </div>

        <div className="form-group">
          <label>Mode</label>
          <div className="mode-selector">
            <button
              className={`mode-button ${mode === 'normal' ? 'active' : ''}`}
              onClick={() => setMode('normal')}
            >
              🔴 Normal<br />
              <small>Stops at red</small>
            </button>
            <button
              className={`mode-button ${mode === 'green_corridor' ? 'active' : ''}`}
              onClick={() => setMode('green_corridor')}
            >
              🟢 Green Corridor<br />
              <small>Ignores red</small>
            </button>
          </div>
        </div>

        <button
          className="btn btn-success"
          onClick={handleSpawn}
          disabled={!readyForAmbulances}
        >
          🚑 Spawn Ambulance
        </button>
      </div>
    </div>
  );
}

export default ControlPanel;
