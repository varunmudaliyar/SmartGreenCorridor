import React from 'react';

function AmbulanceList({ ambulances, onZoomToAmbulance }) {
  return (
    <div className="ambulance-list">
      <h2>Active Ambulances</h2>
      
      {ambulances.length === 0 ? (
        <p className="no-ambulances">No active ambulances</p>
      ) : (
        ambulances.map((ambulance) => (
          <div
            key={ambulance.id}
            className={`ambulance-card ${ambulance.mode === 'green_corridor' ? 'green-corridor' : 'normal'}`}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <h4 style={{ flex: 1 }}>
                {ambulance.mode === 'green_corridor' ? '🟢' : '🔴'} {ambulance.id}
              </h4>
              
              {/* ✅ NEW: Zoom Button */}
              <button
                onClick={() => onZoomToAmbulance(ambulance.id)}
                style={{
                  padding: '4px 8px',
                  background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                  color: 'white',
                  border: 'none',
                  borderRadius: '4px',
                  cursor: 'pointer',
                  fontSize: '11px',
                  fontWeight: '600',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px',
                  transition: 'all 0.2s'
                }}
                onMouseEnter={(e) => e.target.style.transform = 'scale(1.05)'}
                onMouseLeave={(e) => e.target.style.transform = 'scale(1)'}
                title="Zoom to ambulance"
              >
                🔍
              </button>
            </div>
            
            <div className="progress-bar">
              <div
                className="progress-fill"
                style={{ width: `${ambulance.progress_percent || 0}%` }}
              ></div>
            </div>
            
            <div className="info">
              <strong>Route:</strong> {ambulance.source} → {ambulance.destination}<br />
              <strong>Status:</strong> {ambulance.status}<br />
              <strong>Speed:</strong> {ambulance.speed} km/h<br />
              <strong>Progress:</strong> {ambulance.progress} ({ambulance.progress_percent}%)
            </div>
          </div>
        ))
      )}
    </div>
  );
}

export default AmbulanceList;
