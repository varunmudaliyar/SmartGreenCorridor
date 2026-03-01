/**
 * Phase 3: Ambulance Spawn & Basic Routing (No Green Corridor)
 */

import React, { useEffect, useState } from 'react';
import { MapContainer, TileLayer, CircleMarker, Marker, Popup, Polyline } from 'react-leaflet';
import L from 'leaflet';
import io from 'socket.io-client';
import 'leaflet/dist/leaflet.css';
import apiService from '../services/apiService';
import VehicleLayer from './VehicleLayer';

// Add CSS animations
const styles = `
  @keyframes slideInRight {
    from {
      opacity: 0;
      transform: translateX(20px);
    }
    to {
      opacity: 1;
      transform: translateX(0);
    }
  }
  
  @keyframes slideInLeft {
    from {
      opacity: 0;
      transform: translateX(-20px);
    }
    to {
      opacity: 1;
      transform: translateX(0);
    }
  }
  
  @keyframes pulse {
    0%, 100% {
      opacity: 1;
      transform: scale(1);
    }
    50% {
      opacity: 0.7;
      transform: scale(1.1);
    }
  }
`;

// Inject styles
if (typeof document !== 'undefined') {
  const styleSheet = document.createElement('style');
  styleSheet.textContent = styles;
  document.head.appendChild(styleSheet);
}

// Fix Leaflet icons
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: require('leaflet/dist/images/marker-icon-2x.png'),
  iconUrl: require('leaflet/dist/images/marker-icon.png'),
  shadowUrl: require('leaflet/dist/images/marker-shadow.png'),
});

const hospitalIcon = new L.Icon({
  iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-red.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/0.7.7/images/marker-shadow.png',
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41]
});

const MapView = () => {
  const [trafficLights, setTrafficLights] = useState([]);
  const [hospitals, setHospitals] = useState([]);
  const [vehicles, setVehicles] = useState([]);
  const [trafficLightStates, setTrafficLightStates] = useState({});
  const [loading, setLoading] = useState(true);
  const [center, setCenter] = useState([19.1171, 72.8467]);
  const [error, setError] = useState(null);
  
  // Simulation state
  const [simulationRunning, setSimulationRunning] = useState(false);
  const [simTime, setSimTime] = useState(0);
  const [vehicleCount, setVehicleCount] = useState(0);
  const [socket, setSocket] = useState(null);
  
  // Panel visibility state
  const [controlPanelOpen, setControlPanelOpen] = useState(true);
  const [legendOpen, setLegendOpen] = useState(true);
  
  // Phase 3: Ambulance state
  const [ambulances, setAmbulances] = useState([]);
  const [sourceHospital, setSourceHospital] = useState('');
  const [destHospital, setDestHospital] = useState('');
  const [spawningAmbulance, setSpawningAmbulance] = useState(false);

  // Load static data on mount
  useEffect(() => {
    loadStaticData();
    connectWebSocket();
    
    return () => {
      if (socket) {
        socket.disconnect();
      }
    };
  }, []);

  const loadStaticData = async () => {
    setLoading(true);
    try {
      const [tls, hosps] = await Promise.all([
        apiService.getTrafficLights(),
        apiService.getHospitals()
      ]);

      setTrafficLights(tls);
      setHospitals(hosps);

      if (hosps.length > 0) {
        setCenter([hosps[0].lat, hosps[0].lon]);
        // Set default hospitals
        if (hosps.length >= 2) {
          setSourceHospital(hosps[0].id);
          setDestHospital(hosps[1].id);
        }
      }

      setLoading(false);
    } catch (err) {
      console.error('Error loading data:', err);
      setError('Failed to load map data');
      setLoading(false);
    }
  };

  const connectWebSocket = () => {
    const newSocket = io('http://localhost:5000', {
      transports: ['websocket', 'polling']
    });

    newSocket.on('connect', () => {
      console.log('✅ WebSocket connected');
    });

    newSocket.on('connection_response', (data) => {
      console.log('Backend response:', data);
      setSimulationRunning(data.simulation_running);
    });

    newSocket.on('simulation_update', (data) => {
      setSimTime(data.sim_time);
      setVehicleCount(data.vehicle_count);
      setVehicles(data.vehicles);
      
      // Update individual traffic light signals
      if (data.traffic_lights) {
        setTrafficLightStates(data.traffic_lights);
      }
      
      // Update ambulances
      if (data.ambulances) {
        setAmbulances(data.ambulances);
      }
    });

    newSocket.on('simulation_started', () => {
      setSimulationRunning(true);
      console.log('🚗 Simulation started');
    });

    newSocket.on('simulation_ended', () => {
      setSimulationRunning(false);
      console.log('⏹️ Simulation ended');
    });

    newSocket.on('ambulance_spawned', (data) => {
      console.log('🚑 Ambulance spawned:', data);
      alert(`🚑 Ambulance dispatched!\nFrom: ${data.source}\nTo: ${data.destination}`);
    });

    newSocket.on('disconnect', () => {
      console.log('❌ WebSocket disconnected');
    });

    setSocket(newSocket);
  };

  const startSimulation = () => {
    if (socket) {
      socket.emit('request_simulation_start');
    }
  };

  const stopSimulation = () => {
    if (socket) {
      socket.emit('request_simulation_stop');
    }
  };

  const spawnAmbulance = async () => {
    if (!sourceHospital || !destHospital) {
      alert('Please select both source and destination hospitals');
      return;
    }

    if (sourceHospital === destHospital) {
      alert('Source and destination must be different');
      return;
    }

    if (!simulationRunning) {
      alert('Please start the simulation first');
      return;
    }

    setSpawningAmbulance(true);

    try {
      const response = await fetch('http://localhost:5000/api/spawn-ambulance', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          source: sourceHospital,
          destination: destHospital
        })
      });

      const data = await response.json();

      if (response.ok) {
        console.log('✅ Ambulance spawned:', data);
      } else {
        alert('Error: ' + data.error);
      }
    } catch (err) {
      console.error('Error spawning ambulance:', err);
      alert('Failed to spawn ambulance');
    } finally {
      setSpawningAmbulance(false);
    }
  };

  if (loading) {
    return (
      <div style={{
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        height: '100vh',
        backgroundColor: '#f5f5f5',
        flexDirection: 'column'
      }}>
        <div style={{ fontSize: '48px', marginBottom: '20px' }}>🚑</div>
        <h2>Loading Phase 3...</h2>
        <p>Ambulance Routing System</p>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        height: '100vh',
        backgroundColor: '#ffebee'
      }}>
        <div style={{ textAlign: 'center', padding: '40px', backgroundColor: 'white', borderRadius: '8px' }}>
          <h2 style={{ color: '#c62828' }}>⚠️ Error</h2>
          <p>{error}</p>
          <button onClick={loadStaticData} style={{
            padding: '12px 24px',
            backgroundColor: '#2196F3',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            cursor: 'pointer'
          }}>
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div style={{ height: '100vh', width: '100%', position: 'relative' }}>
      <MapContainer
        center={center}
        zoom={14}
        style={{ height: '100%', width: '100%' }}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />

        {/* Individual Traffic Signals */}
        {Object.entries(trafficLightStates).map(([signalId, signal]) => {
          if (!signal.lat || !signal.lon) return null;
          
          const currentColor = signal.color;
          let fillColor, borderColor;
          
          if (currentColor === 'red') {
            fillColor = '#FF0000';
            borderColor = '#8B0000';
          } else if (currentColor === 'yellow') {
            fillColor = '#FFEB3B';
            borderColor = '#F57F17';
          } else if (currentColor === 'green') {
            fillColor = '#4CAF50';
            borderColor = '#2E7D32';
          } else {
            fillColor = '#9E9E9E';
            borderColor = '#424242';
          }
          
          return (
            <CircleMarker
              key={`signal-${signalId}`}
              center={[signal.lat, signal.lon]}
              radius={6}
              pathOptions={{
                fillColor: fillColor,
                color: borderColor,
                weight: 2,
                opacity: 1,
                fillOpacity: 1
              }}
            >
              <Popup closeButton={true} autoClose={false} closeOnClick={false}>
                <div style={{ fontFamily: 'Arial, sans-serif', minWidth: '200px' }}>
                  <h4 style={{ margin: '0 0 10px 0', color: fillColor }}>
                    🚦 Traffic Signal
                  </h4>
                  <p style={{ fontSize: '11px', margin: '5px 0', color: '#666' }}>
                    <strong>Cluster ID:</strong><br />
                    <span style={{ fontSize: '9px', wordBreak: 'break-all' }}>
                      {signal.cluster_id}
                    </span>
                  </p>
                  <p style={{ fontSize: '12px', margin: '5px 0' }}>
                    <strong>Link Index:</strong> #{signal.link_index}
                  </p>
                  <p style={{ fontSize: '14px', margin: '10px 0', fontWeight: 'bold' }}>
                    <strong>Status:</strong>{' '}
                    <span style={{ 
                      color: fillColor,
                      backgroundColor: 'rgba(0,0,0,0.1)',
                      padding: '3px 10px',
                      borderRadius: '4px'
                    }}>
                      {currentColor.toUpperCase()}
                    </span>
                  </p>
                </div>
              </Popup>
            </CircleMarker>
          );
        })}

        {/* Hospitals */}
        {hospitals.map((hospital) => (
          <Marker
            key={`hospital-${hospital.id}`}
            position={[hospital.lat, hospital.lon]}
            icon={hospitalIcon}
          >
            <Popup>
              <div>
                <h3 style={{ margin: '0 0 10px 0', color: '#d32f2f' }}>
                  🏥 {hospital.name}
                </h3>
                <p style={{ margin: '5px 0' }}><strong>Type:</strong> {hospital.type}</p>
                <p style={{ fontSize: '11px', color: '#666' }}>
                  <strong>ID:</strong> {hospital.id}
                </p>
              </div>
            </Popup>
          </Marker>
        ))}

        {/* REAL-TIME VEHICLES */}
        <VehicleLayer vehicles={vehicles} />
      </MapContainer>

      {/* Control Panel - Collapsible */}
      <div style={{
        position: 'absolute',
        top: '20px',
        right: '20px',
        zIndex: 1000
      }}>
        {!controlPanelOpen && (
          <button
            onClick={() => setControlPanelOpen(true)}
            style={{
              padding: '12px 16px',
              backgroundColor: '#1976d2',
              color: 'white',
              border: 'none',
              borderRadius: '8px',
              cursor: 'pointer',
              fontSize: '20px',
              boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
              display: 'flex',
              alignItems: 'center',
              gap: '8px'
            }}
          >
            🚑 <span style={{ fontSize: '14px' }}>Controls</span>
          </button>
        )}

        {controlPanelOpen && (
          <div style={{
            backgroundColor: 'white',
            padding: '20px',
            borderRadius: '8px',
            boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
            maxWidth: '350px',
            animation: 'slideInRight 0.3s ease-out'
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '15px' }}>
              <h3 style={{ margin: 0, fontSize: '18px', color: '#1976d2' }}>
                🚑 Phase 3: Ambulance
              </h3>
              <button
                onClick={() => setControlPanelOpen(false)}
                style={{
                  background: 'none',
                  border: 'none',
                  fontSize: '20px',
                  cursor: 'pointer',
                  color: '#666'
                }}
              >
                ✕
              </button>
            </div>
            
            {/* Simulation Stats */}
            <div style={{ fontSize: '14px', lineHeight: '1.8', marginBottom: '15px', paddingBottom: '15px', borderBottom: '1px solid #eee' }}>
              <p style={{ margin: '8px 0' }}>
                <strong>Status:</strong> {simulationRunning ? '🟢 Running' : '⚪ Stopped'}
              </p>
              <p style={{ margin: '8px 0' }}>
                <strong>Sim Time:</strong> {Math.floor(simTime)}s
              </p>
              <p style={{ margin: '8px 0' }}>
                <strong>Vehicles:</strong> {vehicleCount}
              </p>
              <p style={{ margin: '8px 0' }}>
                <strong>🚑 Ambulances:</strong> {ambulances.length}
              </p>
            </div>

            {/* Simulation Controls */}
            <div style={{ display: 'flex', gap: '10px', flexDirection: 'column', marginBottom: '15px' }}>
              <button
                onClick={startSimulation}
                disabled={simulationRunning}
                style={{
                  padding: '12px',
                  backgroundColor: simulationRunning ? '#ccc' : '#4CAF50',
                  color: 'white',
                  border: 'none',
                  borderRadius: '4px',
                  cursor: simulationRunning ? 'not-allowed' : 'pointer',
                  fontSize: '14px',
                  fontWeight: 'bold'
                }}
              >
                ▶️ Start Simulation
              </button>
              
              <button
                onClick={stopSimulation}
                disabled={!simulationRunning}
                style={{
                  padding: '12px',
                  backgroundColor: !simulationRunning ? '#ccc' : '#f44336',
                  color: 'white',
                  border: 'none',
                  borderRadius: '4px',
                  cursor: !simulationRunning ? 'not-allowed' : 'pointer',
                  fontSize: '14px',
                  fontWeight: 'bold'
                }}
              >
                ⏹️ Stop Simulation
              </button>
            </div>

            {/* Ambulance Spawn Section */}
            <div style={{
              backgroundColor: '#fff3e0',
              padding: '15px',
              borderRadius: '6px',
              marginTop: '15px'
            }}>
              <h4 style={{ margin: '0 0 12px 0', fontSize: '15px', color: '#e65100' }}>
                🚑 Spawn Ambulance
              </h4>

              <div style={{ marginBottom: '12px' }}>
                <label style={{ display: 'block', fontSize: '13px', fontWeight: 'bold', marginBottom: '6px' }}>
                  Source Hospital:
                </label>
                <select
                  value={sourceHospital}
                  onChange={(e) => setSourceHospital(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '8px',
                    borderRadius: '4px',
                    border: '1px solid #ddd',
                    fontSize: '13px'
                  }}
                >
                  <option value="">Select source...</option>
                  {hospitals.map(h => (
                    <option key={h.id} value={h.id}>{h.name}</option>
                  ))}
                </select>
              </div>

              <div style={{ marginBottom: '12px' }}>
                <label style={{ display: 'block', fontSize: '13px', fontWeight: 'bold', marginBottom: '6px' }}>
                  Destination Hospital:
                </label>
                <select
                  value={destHospital}
                  onChange={(e) => setDestHospital(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '8px',
                    borderRadius: '4px',
                    border: '1px solid #ddd',
                    fontSize: '13px'
                  }}
                >
                  <option value="">Select destination...</option>
                  {hospitals.map(h => (
                    <option key={h.id} value={h.id}>{h.name}</option>
                  ))}
                </select>
              </div>

              <button
                onClick={spawnAmbulance}
                disabled={!simulationRunning || spawningAmbulance || !sourceHospital || !destHospital}
                style={{
                  width: '100%',
                  padding: '12px',
                  backgroundColor: (!simulationRunning || spawningAmbulance || !sourceHospital || !destHospital) ? '#ccc' : '#ff5722',
                  color: 'white',
                  border: 'none',
                  borderRadius: '4px',
                  cursor: (!simulationRunning || spawningAmbulance || !sourceHospital || !destHospital) ? 'not-allowed' : 'pointer',
                  fontSize: '14px',
                  fontWeight: 'bold'
                }}
              >
                {spawningAmbulance ? '⏳ Spawning...' : '🚑 Dispatch Ambulance'}
              </button>

              <p style={{ fontSize: '11px', color: '#666', margin: '10px 0 0 0', textAlign: 'center' }}>
                ℹ️ No green corridor (Phase 3)
              </p>
            </div>

            {/* Active Ambulances List */}
            {ambulances.length > 0 && (
              <div style={{
                marginTop: '15px',
                padding: '12px',
                backgroundColor: '#e8f5e9',
                borderRadius: '6px'
              }}>
                <h4 style={{ margin: '0 0 10px 0', fontSize: '14px', color: '#2e7d32' }}>
                  Active Ambulances ({ambulances.length})
                </h4>
                {ambulances.map((amb, idx) => (
                  <div key={idx} style={{
                    padding: '8px',
                    backgroundColor: 'white',
                    borderRadius: '4px',
                    marginBottom: '8px',
                    fontSize: '12px',
                    border: '1px solid #4CAF50'
                  }}>
                    <p style={{ margin: '2px 0', fontWeight: 'bold' }}>
                      🚑 {amb.id}
                    </p>
                    <p style={{ margin: '2px 0', fontSize: '11px' }}>
                      {amb.source} → {amb.destination}
                    </p>
                    <p style={{ margin: '2px 0', fontSize: '11px', color: '#666' }}>
                      Status: {amb.status} | Speed: {amb.speed || 0} km/h
                    </p>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Legend - Collapsible */}
      <div style={{
        position: 'absolute',
        bottom: '30px',
        left: '20px',
        zIndex: 1000
      }}>
        {!legendOpen && (
          <button
            onClick={() => setLegendOpen(true)}
            style={{
              padding: '12px 16px',
              backgroundColor: 'white',
              color: '#333',
              border: 'none',
              borderRadius: '8px',
              cursor: 'pointer',
              fontSize: '20px',
              boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
              display: 'flex',
              alignItems: 'center',
              gap: '8px'
            }}
          >
            🗺️ <span style={{ fontSize: '14px' }}>Legend</span>
          </button>
        )}

        {legendOpen && (
          <div style={{
            backgroundColor: 'white',
            padding: '15px',
            borderRadius: '8px',
            boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
            fontSize: '13px',
            animation: 'slideInLeft 0.3s ease-out',
            maxWidth: '280px'
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
              <h4 style={{ margin: 0, fontSize: '14px', fontWeight: 'bold' }}>Legend</h4>
              <button
                onClick={() => setLegendOpen(false)}
                style={{
                  background: 'none',
                  border: 'none',
                  fontSize: '16px',
                  cursor: 'pointer',
                  color: '#666'
                }}
              >
                ✕
              </button>
            </div>
            
            {/* Traffic Signals */}
            <div style={{ marginBottom: '12px' }}>
              <p style={{ margin: '0 0 8px 0', fontSize: '12px', fontWeight: 'bold', color: '#666' }}>
                Traffic Signals:
              </p>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <div style={{ width: '14px', height: '14px', borderRadius: '50%', backgroundColor: '#FF0000', border: '2px solid #8B0000' }}></div>
                  <span>Red (Stop)</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <div style={{ width: '14px', height: '14px', borderRadius: '50%', backgroundColor: '#FFEB3B', border: '2px solid #F57F17' }}></div>
                  <span>Yellow (Caution)</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <div style={{ width: '14px', height: '14px', borderRadius: '50%', backgroundColor: '#4CAF50', border: '2px solid #2E7D32' }}></div>
                  <span>Green (Go)</span>
                </div>
              </div>
            </div>
            
            {/* Vehicles */}
            <div style={{ marginBottom: '12px' }}>
              <p style={{ margin: '0 0 8px 0', fontSize: '12px', fontWeight: 'bold', color: '#666' }}>Vehicles:</p>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <div style={{ width: '12px', height: '12px', borderRadius: '50%', backgroundColor: '#FF0000' }}></div>
                  <span>🚑 Ambulance</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <div style={{ width: '12px', height: '12px', borderRadius: '50%', backgroundColor: '#9C27B0' }}></div>
                  <span>🚗 Car</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <div style={{ width: '12px', height: '12px', borderRadius: '50%', backgroundColor: '#FF9800' }}></div>
                  <span>🚕 Taxi</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <div style={{ width: '12px', height: '12px', borderRadius: '50%', backgroundColor: '#2196F3' }}></div>
                  <span>🚌 Bus</span>
                </div>
              </div>
            </div>
            
            <div style={{
              padding: '8px',
              backgroundColor: '#e3f2fd',
              borderRadius: '4px',
              fontSize: '11px',
              color: '#1565c0'
            }}>
              <strong>Phase 3:</strong> Basic ambulance routing without green corridor
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default MapView;
