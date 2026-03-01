import React from 'react';
import { Marker, Popup } from 'react-leaflet';
import L from 'leaflet';

const VehicleLayer = ({ vehicles }) => {
  // Create ambulance icon (Green Corridor - Green, Normal - Red)
  const createAmbulanceIcon = (isGreenCorridor) => {
    const color = isGreenCorridor ? '#10b981' : '#ef4444'; // Green or Red
    const pulseColor = isGreenCorridor ? '16, 185, 129' : '239, 68, 68';
    
    return L.divIcon({
      className: 'custom-ambulance-icon',
      html: `
        <div style="position: relative; width: 40px; height: 40px;">
          <!-- Pulsing circle animation -->
          <div style="
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            width: 40px;
            height: 40px;
            background: rgba(${pulseColor}, 0.3);
            border-radius: 50%;
            animation: pulse 1.5s infinite;
          "></div>
          
          <!-- Ambulance SVG -->
          <svg style="
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            filter: drop-shadow(0 2px 4px rgba(0,0,0,0.3));
          " width="32" height="32" viewBox="0 0 24 24" fill="none">
            <!-- Ambulance body -->
            <rect x="3" y="10" width="18" height="8" rx="1" fill="${color}"/>
            <!-- Windshield -->
            <rect x="14" y="11" width="6" height="4" fill="#fff" opacity="0.8"/>
            <!-- Medical cross -->
            <g transform="translate(7, 12)">
              <rect x="1.5" y="0" width="1" height="4" fill="#fff"/>
              <rect x="0" y="1.5" width="4" height="1" fill="#fff"/>
            </g>
            <!-- Wheels -->
            <circle cx="7" cy="18" r="1.5" fill="#333"/>
            <circle cx="17" cy="18" r="1.5" fill="#333"/>
            <!-- Light bar -->
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

  // Regular vehicle icon (smaller circles)
  const getVehicleColor = (vehicle) => {
    const colors = {
      'car': '#9C27B0',     // Purple
      'taxi': '#FF9800',    // Orange
      'bus': '#2196F3',     // Blue
      'truck': '#607D8B',   // Gray
      'motorcycle': '#00BCD4' // Cyan
    };
    return colors[vehicle.type] || '#000000';
  };

  const createVehicleIcon = (color) => {
    return L.divIcon({
      className: 'custom-vehicle-icon',
      html: `
        <div style="
          width: 12px;
          height: 12px;
          background: ${color};
          border: 2px solid #fff;
          border-radius: 50%;
          box-shadow: 0 1px 3px rgba(0,0,0,0.3);
        "></div>
      `,
      iconSize: [12, 12],
      iconAnchor: [6, 6],
      popupAnchor: [0, -6]
    });
  };

  return (
    <>
      {vehicles.map(vehicle => {
        const isAmbulance = vehicle.is_ambulance;
        
        // Check if ambulance is in green corridor mode (green color indicator)
        const isGreenCorridor = isAmbulance && vehicle.color && vehicle.color.g > 200;
        
        const icon = isAmbulance 
          ? createAmbulanceIcon(isGreenCorridor)
          : createVehicleIcon(getVehicleColor(vehicle));

        return (
          <Marker
            key={vehicle.id}
            position={[vehicle.lat, vehicle.lon]}
            icon={icon}
          >
            <Popup>
              <div style={{ fontFamily: 'Arial, sans-serif', minWidth: '180px' }}>
                <h4 style={{ 
                  margin: '0 0 8px 0', 
                  color: isAmbulance ? (isGreenCorridor ? '#10b981' : '#ef4444') : getVehicleColor(vehicle),
                  fontSize: '14px'
                }}>
                  {isAmbulance ? '🚑 AMBULANCE' : vehicle.type.toUpperCase()}
                </h4>
                <p style={{ fontSize: '11px', margin: '4px 0' }}>
                  <strong>ID:</strong> {vehicle.id}
                </p>
                <p style={{ fontSize: '11px', margin: '4px 0' }}>
                  <strong>Speed:</strong> {vehicle.speed} km/h
                </p>
                <p style={{ fontSize: '11px', margin: '4px 0' }}>
                  <strong>Road:</strong> {vehicle.road}
                </p>
                {isAmbulance && (
                  <>
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
                  </>
                )}
              </div>
            </Popup>
          </Marker>
        );
      })}
    </>
  );
};

export default VehicleLayer;
