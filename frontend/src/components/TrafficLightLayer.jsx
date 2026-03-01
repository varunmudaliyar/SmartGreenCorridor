import React, { memo } from 'react';
import { CircleMarker, Popup } from 'react-leaflet';

const TrafficLightSignal = memo(({ signal }) => {
  // DYNAMIC COLOR based on signal status
  const getSignalColor = (color) => {
    switch (color) {
      case 'red': return '#ef4444';
      case 'yellow': return '#fbbf24';
      case 'green': return '#10b981';
      default: return '#6b7280';
    }
  };

  const color = getSignalColor(signal.color); // This is already dynamic!

  return (
    <CircleMarker
      key={signal.id}
      center={[signal.lat, signal.lon]}
      radius={6}
      fillColor={color} // DYNAMIC COLOR - changes with signal state
      color="white"
      weight={2}
      fillOpacity={1}
      className="traffic-signal-dot"
    >
      <Popup>
        <div style={{ minWidth: '150px' }}>
          <strong>🚦 Traffic Signal</strong>
          <hr style={{ margin: '8px 0' }} />
          <div style={{ fontSize: '11px' }}>
            <strong>Cluster ID:</strong><br />
            <code>{signal.cluster_id}</code>
            <br /><br />
            <strong>Link Index:</strong> #{signal.link_index}
            <br /><br />
            <strong>Current State:</strong>{' '}
            <span style={{ 
              color: color, 
              fontWeight: 'bold',
              fontSize: '13px'
            }}>
              {signal.color.toUpperCase()}
            </span>
            <br /><br />
            <strong>Signal Code:</strong> <code>{signal.state}</code>
          </div>
        </div>
      </Popup>
    </CircleMarker>
  );
});

const TrafficLightLayer = ({ trafficLightStates }) => {
  // Convert to array
  const signals = Object.values(trafficLightStates || {});

  return (
    <>
      {signals.map((signal) => (
        <TrafficLightSignal key={signal.id} signal={signal} />
      ))}
    </>
  );
};

export default memo(TrafficLightLayer);
