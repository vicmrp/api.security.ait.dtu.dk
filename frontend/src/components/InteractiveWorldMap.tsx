import React, { useRef, useState } from 'react';
import Map, { Marker, Layer, Source, Popup } from 'react-map-gl/maplibre';
import 'maplibre-gl/dist/maplibre-gl.css';

interface InteractiveWorldMapProps {
  loginLocations: Array<{
    id: string;
    location: string;
    city: string;
    country: string;
    isFamiliar: boolean;
    timestamp: Date;
    latitude?: number;
    longitude?: number;
  }>;
  diagnosedSignIns: Array<{
    id: string;
    location: string;
    riskLevel: string;
    timestamp: Date;
    latitude?: number;
    longitude?: number;
  }>;
  formatDate: (date: Date) => string;
}

export const InteractiveWorldMap: React.FC<InteractiveWorldMapProps> = ({
  loginLocations,
  diagnosedSignIns,
  formatDate
}) => {
  const mapRef = useRef<any>(null);
  const [viewState, setViewState] = useState({
    longitude: 12.5054, // DTU Lundtoftegårdsvej longitude
    latitude: 55.7859,  // DTU Lundtoftegårdsvej latitude
    zoom: 2,
    pitch: 0,
    bearing: 0
  });
  const [hoveredLocation, setHoveredLocation] = useState<any>(null);

  // Geographic coordinates for major cities
  const getCoordinates = (city: string, country: string): [number, number] => {
    const coordinates: { [key: string]: [number, number] } = {
      'New York': [-74.0059, 40.7128],
      'Beijing': [116.4074, 39.9042],
      'Tokyo': [139.6917, 35.6895],
      'São Paulo': [-46.6333, -23.5505],
      'Mumbai': [72.8777, 19.0760],
      'Moscow': [37.6173, 55.7558],
      'Sydney': [151.2093, -33.8688],
      'Lagos': [3.3792, 6.5244],
      'London': [-0.1278, 51.5074],
      'Paris': [2.3522, 48.8566],
    };
    
    return coordinates[city] || coordinates[country] || [0, 0];
  };

  // Combine all locations with coordinates
  const allLocations = [
    ...loginLocations.map(l => ({
      ...l,
      coordinates: getCoordinates(l.city, l.country),
      type: 'login' as const,
      riskLevel: l.isFamiliar ? 'safe' : 'medium'
    })),
    ...diagnosedSignIns.map(s => ({
      id: s.id + '_threat',
      location: s.location,
      city: s.location.split(', ')[0],
      country: s.location.split(', ')[1] || s.location,
      coordinates: getCoordinates(s.location.split(', ')[0], s.location.split(', ')[1] || s.location),
      type: 'threat' as const,
      riskLevel: s.riskLevel.toLowerCase(),
      timestamp: s.timestamp,
      isFamiliar: false
    }))
  ];

  // Create connection lines from DTU to each location
  const dtuCoordinates: [number, number] = [12.5054, 55.7859]; // DTU Lundtoftegårdsvej 93A, Kongens Lyngby
  
  const connectionLines = {
    type: 'FeatureCollection' as const,
    features: allLocations.map(location => ({
      type: 'Feature' as const,
      geometry: {
        type: 'LineString' as const,
        coordinates: [dtuCoordinates, location.coordinates]
      },
      properties: {
        type: location.type,
        riskLevel: location.riskLevel
      }
    }))
  };

  // Calculate statistics
  const trustedLocations = loginLocations.filter(l => l.isFamiliar).length;
  const totalLoginLocations = loginLocations.length;
  const securityThreats = diagnosedSignIns.length;

  return (
    <div style={{ width: '100%', fontFamily: 'system-ui, sans-serif' }}>
      {/* Header */}
      <div style={{ 
        display: 'flex', 
        alignItems: 'center', 
        marginBottom: '20px',
        fontSize: '24px',
        fontWeight: 'bold',
        color: '#1f2937',
        alignContent: 'center'
      }}>
        🗺️ Global Login Activity Map
      </div>

      {/* Statistics Boxes */}
      <div style={{ 
        display: 'grid', 
        gridTemplateColumns: '1fr 1fr 1fr', 
        gap: '16px', 
        marginBottom: '24px' 
      }}>
        <div style={{
          background: 'linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%)',
          border: '1px solid #0ea5e9',
          borderRadius: '12px',
          padding: '12px',
          textAlign: 'center',
          boxShadow: '0 2px 4px rgba(0, 0, 0, 0.05)'
        }}>
          <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#0369a1', marginBottom: '2px' }}>
            {totalLoginLocations}
          </div>
          <div style={{ fontSize: '13px', color: '#0369a1', fontWeight: '500' }}>
            Login Locations
          </div>
        </div>

        <div style={{
          background: 'linear-gradient(135deg, #fef2f2 0%, #fee2e2 100%)',
          border: '1px solid #f87171',
          borderRadius: '12px',
          padding: '12px',
          textAlign: 'center',
          boxShadow: '0 2px 4px rgba(0, 0, 0, 0.05)'
        }}>
          <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#dc2626', marginBottom: '2px' }}>
            {securityThreats}
          </div>
          <div style={{ fontSize: '13px', color: '#dc2626', fontWeight: '500' }}>
            Security Threats
          </div>
        </div>

        <div style={{
          background: 'linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%)',
          border: '1px solid #4ade80',
          borderRadius: '12px',
          padding: '12px',
          textAlign: 'center',
          boxShadow: '0 2px 4px rgba(0, 0, 0, 0.05)'
        }}>
          <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#16a34a', marginBottom: '2px' }}>
            {trustedLocations}
          </div>
          <div style={{ fontSize: '13px', color: '#16a34a', fontWeight: '500' }}>
            Trusted Locations
          </div>
        </div>
      </div>

      {/* Map Container */}
      <div style={{ width: '100%', height: '500px', borderRadius: '12px', overflow: 'hidden', marginBottom: '16px' }}>
      <Map
        ref={mapRef}
        {...viewState}
        onMove={evt => setViewState(evt.viewState)}
        style={{ width: '100%', height: '100%' }}
        mapStyle={{
          version: 8,
          sources: {
            osm: {
              type: 'raster',
              tiles: [
                'https://cartodb-basemaps-a.global.ssl.fastly.net/light_all/{z}/{x}/{y}.png',
                'https://cartodb-basemaps-b.global.ssl.fastly.net/light_all/{z}/{x}/{y}.png',
                'https://cartodb-basemaps-c.global.ssl.fastly.net/light_all/{z}/{x}/{y}.png'
              ],
              tileSize: 256,
              attribution: '© OpenStreetMap contributors © CartoDB'
            }
          },
          layers: [
            {
              id: 'osm',
              type: 'raster',
              source: 'osm'
            }
          ]
        }}
        attributionControl={false}
      >
        {/* Connection Lines */}
        <Source id="connections" type="geojson" data={connectionLines}>
          <Layer
            id="connection-lines-safe"
            type="line"
            filter={['==', ['get', 'type'], 'login']}
            paint={{
              'line-color': 'rgba(34, 197, 94, 0.4)',
              'line-width': 3,
              'line-opacity': 0.7
            }}
          />
          <Layer
            id="connection-lines-threat"
            type="line"
            filter={['==', ['get', 'type'], 'threat']}
            paint={{
              'line-color': 'rgba(239, 68, 68, 0.4)',
              'line-width': 3,
              'line-opacity': 0.8
            }}
          />
        </Source>

        {/* DTU Hub Marker */}
        <Marker longitude={dtuCoordinates[0]} latitude={dtuCoordinates[1]} anchor="center">
          <div style={{
            width: '38px',
            height: '38px',
            background: 'linear-gradient(45deg, rgba(59, 130, 246, 0.8), rgba(29, 78, 216, 0.8))',
            borderRadius: '50%',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: '16px',
            color: 'white',
            boxShadow: '0 0 12px rgba(59, 130, 246, 0.3)',
            border: '1px solid rgba(255, 255, 255, 0.8)',
            animation: 'hubPulse 2s ease-in-out infinite'
          }}>
            🏢
          </div>
        </Marker>

        {/* Country Labels */}
        {viewState.zoom <= 4 && [
          { name: 'USA', coord: [-95, 40] },
          { name: 'CHINA', coord: [105, 35] },
          { name: 'RUSSIA', coord: [37, 60] },
          { name: 'INDIA', coord: [77, 20] },
          { name: 'BRAZIL', coord: [-55, -10] },
          { name: 'AUSTRALIA', coord: [151, -27] },
          { name: 'CANADA', coord: [-106, 56] },
          { name: 'GERMANY', coord: [10, 51] }
        ].map((country, index) => (
          <Marker
            key={`country-${index}`}
            longitude={country.coord[0]}
            latitude={country.coord[1]}
            anchor="center"
          >
            <div style={{
              color: '#6b7280',
              fontWeight: '500',
              fontSize: '11px',
              textShadow: '1px 1px 2px white, -1px -1px 1px white, 1px -1px 1px white, -1px 1px 1px white',
              letterSpacing: '0.05em',
              pointerEvents: 'none',
              userSelect: 'none'
            }}>
              {country.name}
            </div>
          </Marker>
        ))}

        {/* Location Markers */}
        {allLocations.map((location) => (
          <Marker
            key={location.id}
            longitude={location.coordinates[0]}
            latitude={location.coordinates[1]}
            anchor="center"
          >
            <div
              style={{
                width: '24px',
                height: '24px',
                background: location.type === 'threat' 
                  ? 'rgba(239, 68, 68, 0.6)'
                  : 'rgba(34, 197, 94, 0.7)',
                borderRadius: '50%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '11px',
                color: 'white',
                boxShadow: location.type === 'threat'
                  ? '0 0 6px rgba(239, 68, 68, 0.3)'
                  : '0 0 4px rgba(34, 197, 94, 0.2)',
                border: location.type === 'threat' ? '1px solid rgba(220, 38, 38, 0.6)' : '1px solid rgba(255, 255, 255, 0.5)',
                cursor: 'pointer',
                transition: 'all 0.3s ease',
                animation: location.type === 'threat' ? 'threatPulse 2s ease-in-out infinite' : 'safeDot 1s ease-in-out'
              }}
              onMouseEnter={() => setHoveredLocation(location)}
              onMouseLeave={() => setHoveredLocation(null)}
            >
              {location.type === 'threat' ? '⚠' : '●'}
            </div>
          </Marker>
        ))}

        {/* Hover Popup */}
        {hoveredLocation && (
          <Popup
            longitude={hoveredLocation.coordinates[0]}
            latitude={hoveredLocation.coordinates[1]}
            closeButton={false}
            closeOnClick={false}
            anchor="bottom"
            offset={[0, -10]}
            className="custom-popup"
          >
            <div style={{
              background: 'rgba(255, 255, 255, 0.95)',
              backdropFilter: 'blur(10px)',
              padding: '12px',
              borderRadius: '8px',
              border: hoveredLocation.type === 'threat' 
                ? '2px solid rgba(239, 68, 68, 0.8)'
                : '2px solid rgba(34, 197, 94, 0.8)',
              boxShadow: hoveredLocation.type === 'threat'
                ? '0 4px 12px rgba(239, 68, 68, 0.3), 0 0 15px rgba(239, 68, 68, 0.2)'
                : '0 4px 12px rgba(34, 197, 94, 0.3), 0 0 15px rgba(34, 197, 94, 0.2)',
              minWidth: '200px',
              fontSize: '14px'
            }}>
              <div style={{ fontWeight: 'bold', marginBottom: '8px', color: '#1f2937' }}>
                📍 {hoveredLocation.city}, {hoveredLocation.country}
              </div>
              <div style={{ marginBottom: '4px', color: '#374151' }}>
                <strong>Type:</strong> {hoveredLocation.type === 'threat' ? '🚨 Security Threat' : '✅ Login Location'}
              </div>
              <div style={{ marginBottom: '4px', color: '#374151' }}>
                <strong>Status:</strong> {hoveredLocation.isFamiliar ? 'Familiar' : 'Unfamiliar'}
              </div>
              <div style={{ color: '#6b7280', fontSize: '12px' }}>
                <strong>Time:</strong> {formatDate(hoveredLocation.timestamp)}
              </div>
            </div>
          </Popup>
        )}
      </Map>
      </div>

      {/* Color Indicators */}
      <div style={{ 
        display: 'flex', 
        justifyContent: 'center', 
        gap: '24px', 
        marginTop: '16px',
        fontSize: '14px',
        color: '#6b7280'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div style={{
            width: '16px',
            height: '16px',
            borderRadius: '50%',
            background: 'rgba(34, 197, 94, 0.7)',
            border: '1px solid rgba(255, 255, 255, 0.5)'
          }}></div>
          <span>Trusted Locations</span>
        </div>
        
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div style={{
            width: '16px',
            height: '16px',
            borderRadius: '50%',
            background: 'rgba(239, 68, 68, 0.6)',
            border: '1px solid rgba(220, 38, 38, 0.6)'
          }}></div>
          <span>Security Threats</span>
        </div>
        
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div style={{
            width: '18px',
            height: '18px',
            borderRadius: '50%',
            background: 'linear-gradient(45deg, rgba(59, 130, 246, 0.8), rgba(29, 78, 216, 0.8))',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: '9px'
          }}>🏢</div>
          <span>DTU AIT-SOC, Lundtoftegårdsvej</span>
        </div>
      </div>

      <style>{`
        @keyframes hubPulse {
          0% { transform: scale(1); box-shadow: 0 0 20px rgba(59, 130, 246, 0.6); }
          50% { transform: scale(1.1); box-shadow: 0 0 30px rgba(59, 130, 246, 0.8); }
          100% { transform: scale(1); box-shadow: 0 0 20px rgba(59, 130, 246, 0.6); }
        }
        
        @keyframes threatPulse {
          0% { transform: scale(1); box-shadow: 0 0 15px rgba(239, 68, 68, 0.8), 0 0 5px rgba(239, 68, 68, 1); }
          50% { transform: scale(1.3); box-shadow: 0 0 25px rgba(239, 68, 68, 1), 0 0 10px rgba(239, 68, 68, 1); }
          100% { transform: scale(1); box-shadow: 0 0 15px rgba(239, 68, 68, 0.8), 0 0 5px rgba(239, 68, 68, 1); }
        }

        @keyframes safeDot {
          0% { transform: scale(0); opacity: 0; }
          100% { transform: scale(1); opacity: 1; }
        }

        .custom-popup .maplibregl-popup-content {
          padding: 0 !important;
          background: transparent !important;
          box-shadow: none !important;
        }
      `}</style>


    </div>
  );
};