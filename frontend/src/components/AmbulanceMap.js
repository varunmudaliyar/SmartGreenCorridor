import React, { memo, useRef, useEffect } from 'react';
import { MapContainer, TileLayer, Marker, Popup, CircleMarker, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

// Fix Leaflet default marker icon issue
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
});

// Hospital icon
const hospitalIcon = new L.Icon({
  iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-red.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41]
});

// CREATE AMBULANCE SVG ICON
const createAmbulanceIcon = (isGreenCorridor) => {
  const color = isGreenCorridor ? '#10b981' : '#ef4444';
  const pulseColor = isGreenCorridor ? '16, 185, 129' : '239, 68, 68';
  
  return L.divIcon({
    className: 'custom-ambulance-icon',
    html: `
      <div style="position: relative; width: 40px; height: 40px;">
        <div style="
          position: absolute;
          top: 50%;
          left: 50%;
          transform: translate(-50%, -50%);
          width: 40px;
          height: 40px;
          background: rgba(${pulseColor}, 0.3);
          border-radius: 50%;
          animation: ambulance-pulse 1.5s infinite;
        "></div>
        
        <svg style="
          position: absolute;
          top: 50%;
          left: 50%;
          transform: translate(-50%, -50%);
          filter: drop-shadow(0 2px 4px rgba(0,0,0,0.3));
        " width="32" height="32" viewBox="0 0 24 24" fill="none">
          <rect x="3" y="10" width="18" height="8" rx="1" fill="${color}"/>
          <rect x="14" y="11" width="6" height="4" fill="#fff" opacity="0.8"/>
          <g transform="translate(7, 12)">
            <rect x="1.5" y="0" width="1" height="4" fill="#fff"/>
            <rect x="0" y="1.5" width="4" height="1" fill="#fff"/>
          </g>
          <circle cx="7" cy="18" r="1.5" fill="#333"/>
          <circle cx="17" cy="18" r="1.5" fill="#333"/>
          <rect x="8" y="8" width="8" height="1" rx="0.5" fill="${isGreenCorridor ? '#10b981' : '#ff0000'}" opacity="0.9">
            <animate attributeName="opacity" values="0.9;0.3;0.9" dur="0.8s" repeatCount="indefinite"/>
          </rect>
        </svg>
      </div>
    `,
    iconSize: [40, 40],
    iconAnchor: [20, 20],
    popupAnchor: [0, -20]
  });
};

// ✅ NEW: Component to handle map zoom/pan
const MapController = ({ zoomToAmbulance }) => {
  const map = useMap();
  
  useEffect(() => {
    if (zoomToAmbulance && zoomToAmbulance.lat && zoomToAmbulance.lon) {
      // Fly to ambulance with smooth animation
      map.flyTo([zoomToAmbulance.lat, zoomToAmbulance.lon], 17, {
        duration: 1.5,
        easeLinearity: 0.25
      });
    }
  }, [zoomToAmbulance, map]);
  
  return null;
};

// Memoize hospital markers
const HospitalMarkers = memo(({ hospitals }) => (
  <>
    {hospitals.map((hospital, idx) => (
      <Marker
        key={`hospital-${hospital.id}-${idx}`}
        position={[hospital.lat, hospital.lon]}
        icon={hospitalIcon}
      >
        <Popup>
          <div style={{ minWidth: '150px' }}>
            <strong>{hospital.name}</strong>
            <hr style={{ margin: '8px 0' }} />
            <div style={{ fontSize: '11px' }}>
              <strong>Hospital ID:</strong> {idx}<br />
              <strong>Type:</strong> Emergency Medical Center<br />
              <strong>Coordinates:</strong><br />
              {hospital.lat.toFixed(6)}, {hospital.lon.toFixed(6)}
            </div>
          </div>
        </Popup>
      </Marker>
    ))}
  </>
));

// Traffic Light Signals with DYNAMIC COLORS
const TrafficLightSignals = ({ trafficLightStates }) => {
  const signals = Object.values(trafficLightStates || {});
  
  const getSignalColor = (colorStr) => {
    switch (colorStr) {
      case 'red': return '#ef4444';
      case 'yellow': return '#fbbf24';
      case 'green': return '#10b981';
      default: return '#6b7280';
    }
  };

  return (
    <>
      {signals.map(signal => {
        const currentColor = getSignalColor(signal.color);
        
        return (
          <CircleMarker
            key={`${signal.id}-${signal.color}`}
            center={[signal.lat, signal.lon]}
            radius={6}
            fillColor={currentColor}
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
                  <strong>Link Index:</strong> {signal.link_index}
                  <br /><br />
                  <strong>Current Status:</strong>{' '}
                  <span style={{
                    color: currentColor,
                    fontWeight: 'bold',
                    fontSize: '14px',
                    textTransform: 'uppercase',
                    padding: '2px 6px',
                    borderRadius: '4px',
                    background: `${currentColor}20`
                  }}>
                    {signal.color}
                  </span>
                  <br /><br />
                  <strong>Signal Code:</strong> <code>{signal.state}</code>
                  <br /><br />
                </div>
                <div style={{
                  marginTop: '8px',
                  padding: '6px',
                  background: '#f3f4f6',
                  borderRadius: '4px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px'
                }}>
                  <div style={{
                    width: '16px',
                    height: '16px',
                    borderRadius: '50%',
                    background: currentColor,
                    border: '2px solid white',
                    boxShadow: '0 0 4px rgba(0,0,0,0.2)'
                  }}></div>
                  <span style={{ fontSize: '10px', color: '#6b7280' }}>
                    Live Status
                  </span>
                </div>
              </div>
            </Popup>
          </CircleMarker>
        );
      })}
    </>
  );
};

// VEHICLE MARKERS WITH SVG AMBULANCE ICONS
const VehicleMarkers = memo(({ vehicles }) => {
  return (
    <>
      {vehicles.slice(0, 500).map(vehicle => {
        const isAmbulance = vehicle.is_ambulance;
        const isGreenCorridor = isAmbulance && vehicle.color && vehicle.color.g > 200;

        if (isAmbulance) {
          return (
            <Marker
              key={vehicle.id}
              position={[vehicle.lat, vehicle.lon]}
              icon={createAmbulanceIcon(isGreenCorridor)}
            >
              <Popup>
                <div style={{ fontFamily: 'Arial, sans-serif', minWidth: '180px' }}>
                  <h4 style={{
                    margin: '0 0 8px 0',
                    color: isGreenCorridor ? '#10b981' : '#ef4444',
                    fontSize: '14px'
                  }}>
                    🚑 AMBULANCE
                  </h4>
                  <p style={{ fontSize: '11px', margin: '4px 0' }}>
                    <strong>ID:</strong> {vehicle.id}
                  </p>
                  <p style={{ fontSize: '11px', margin: '4px 0' }}>
                    <strong>Speed:</strong> {vehicle.speed} km/h
                  </p>
                  <p style={{ fontSize: '11px', margin: '4px 0' }}>
                    <strong>Mode:</strong> {isGreenCorridor ? 'Green Corridor 🟢' : 'Normal 🔴'}
                  </p>
                  <p style={{
                    fontSize: '10px',
                    margin: '6px 0 0 0',
                    padding: '4px',
                    backgroundColor: isGreenCorridor ? '#d1fae5' : '#ffebee',
                    borderRadius: '3px',
                    color: isGreenCorridor ? '#065f46' : '#c62828',
                    fontWeight: 'bold',
                    textAlign: 'center'
                  }}>
                    {isGreenCorridor ? '✓ PRIORITY ROUTE ACTIVE' : '⚠ EMERGENCY VEHICLE'}
                  </p>
                </div>
              </Popup>
            </Marker>
          );
        } else {
          return (
            <CircleMarker
              key={vehicle.id}
              center={[vehicle.lat, vehicle.lon]}
              radius={5}
              fillColor="#3b82f6"
              color="white"
              weight={1.5}
              fillOpacity={0.8}
            >
              <Popup>
                <div style={{ minWidth: '150px' }}>
                  <strong>🚗 Vehicle</strong>
                  <hr style={{ margin: '8px 0' }} />
                  <div style={{ fontSize: '11px' }}>
                    <strong>ID:</strong> {vehicle.id}<br />
                    <strong>Speed:</strong> {vehicle.speed} km/h<br />
                  </div>
                </div>
              </Popup>
            </CircleMarker>
          );
        }
      })}
    </>
  );
});

function AmbulanceMap({ hospitals, ambulances, vehicles, trafficLights, zoomToAmbulance }) {
  return (
    <div className="map-container">
      <MapContainer
        center={[19.110, 72.845]}
        zoom={14}
        style={{ height: '100%', width: '100%' }}
        preferCanvas={true}
      >
        <TileLayer
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          updateWhenIdle={true}
          updateWhenZooming={false}
          keepBuffer={2}
        />

        {/* ✅ NEW: Map Controller for zoom functionality */}
        <MapController zoomToAmbulance={zoomToAmbulance} />

        {/* Traffic Lights */}
        <TrafficLightSignals trafficLightStates={trafficLights} />

        {/* Hospitals */}
        <HospitalMarkers hospitals={hospitals} />

        {/* Vehicles (including ambulances with SVG icons) */}
        <VehicleMarkers vehicles={vehicles} />
      </MapContainer>

      {/* Map Legend */}
      <div style={{
        position: 'absolute',
        bottom: 30,
        right: 10,
        background: 'white',
        padding: '12px 15px',
        borderRadius: 8,
        boxShadow: '0 2px 10px rgba(0,0,0,0.15)',
        zIndex: 1000,
        fontSize: 12,
        maxWidth: 200
      }}>
        <div style={{ fontWeight: 'bold', marginBottom: 10, fontSize: 13 }}>
          Map Legend
        </div>

        {/* Traffic Signals */}
        <div style={{ marginBottom: 8, paddingBottom: 8, borderBottom: '1px solid #e5e5e5' }}>
          <div style={{ fontWeight: 600, marginBottom: 4, fontSize: 11 }}>Traffic Signals</div>
          <div style={{ display: 'flex', alignItems: 'center', marginBottom: 3 }}>
            <div style={{ width: 10, height: 10, background: '#ef4444', borderRadius: '50%', marginRight: 8, border: '2px solid white', boxShadow: '0 0 3px rgba(0,0,0,0.3)' }}></div>
            <span style={{ fontSize: 11 }}>Red (Stop)</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', marginBottom: 3 }}>
            <div style={{ width: 10, height: 10, background: '#fbbf24', borderRadius: '50%', marginRight: 8, border: '2px solid white', boxShadow: '0 0 3px rgba(0,0,0,0.3)' }}></div>
            <span style={{ fontSize: 11 }}>Yellow (Caution)</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', marginBottom: 3 }}>
            <div style={{ width: 10, height: 10, background: '#10b981', borderRadius: '50%', marginRight: 8, border: '2px solid white', boxShadow: '0 0 3px rgba(0,0,0,0.3)' }}></div>
            <span style={{ fontSize: 11 }}>Green (Go)</span>
          </div>
        </div>

        {/* Vehicles */}
        <div style={{ marginBottom: 8, paddingBottom: 8, borderBottom: '1px solid #e5e5e5' }}>
          <div style={{ fontWeight: 600, marginBottom: 4, fontSize: 11 }}>Vehicles</div>
          <div style={{ display: 'flex', alignItems: 'center', marginBottom: 3 }}>
            <span style={{ fontSize: 16, marginRight: 8 }}>🚑</span>
            <span style={{ fontSize: 11, color: '#ef4444', fontWeight: 'bold' }}>Normal Ambulance</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', marginBottom: 3 }}>
            <span style={{ fontSize: 16, marginRight: 8 }}>🚑</span>
            <span style={{ fontSize: 11, color: '#10b981', fontWeight: 'bold' }}>Green Corridor</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', marginBottom: 3 }}>
            <div style={{ width: 10, height: 10, background: '#3b82f6', borderRadius: '50%', marginRight: 10, border: '1.5px solid white' }}></div>
            <span style={{ fontSize: 11 }}>Regular Vehicle</span>
          </div>
        </div>

        {/* Hospitals */}
        <div>
          <div style={{ fontWeight: 600, marginBottom: 4, fontSize: 11 }}>Hospitals</div>
          <div style={{ display: 'flex', alignItems: 'center' }}>
            <span style={{ color: '#ef4444', fontSize: 16, marginRight: 8 }}>📍</span>
            <span style={{ fontSize: 11 }}>Hospital Location</span>
          </div>
        </div>
      </div>

      {/* Traffic Light Counter */}
      <div style={{
        position: 'absolute',
        top: 10,
        right: 10,
        background: 'white',
        padding: '8px 12px',
        borderRadius: 6,
        boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
        zIndex: 1000,
        fontSize: 12,
        fontWeight: 600
      }}>
        🚦 Signals: {Object.keys(trafficLights || {}).length}
      </div>
    </div>
  );
}

export default memo(AmbulanceMap);
