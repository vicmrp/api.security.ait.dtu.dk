import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Map, { Layer, MapRef, Popup, Source } from 'react-map-gl/maplibre';
import type { Feature, FeatureCollection, Point } from 'geojson';
import type { Map as MaplibreMap } from 'maplibre-gl';
import { LngLatBounds } from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import './UnfamiliarLoginPage.css';

interface UnfamiliarLoginPageProps {
  accessToken?: string | null;
  backendApiToken?: string | null;
  onClose: () => void;
}

type RawIdentityEvent = Record<string, unknown>;

interface SignInEvent {
  id: string;
  timestamp: string;
  displayLocation: string;
  ipAddress?: string;
  latitude?: number;
  longitude?: number;
  protocol?: string;
  status?: string;
  raw: RawIdentityEvent;
}

interface IdentityLogonResponse {
  results?: RawIdentityEvent[];
}

const LATITUDE_KEYS = [
  'LocationLatitude',
  'LocationLat',
  'Latitude',
  'LatitudeDegrees',
  'GeoLatitude',
  'Lat',
  'lat'
] as const;

const LONGITUDE_KEYS = [
  'LocationLongitude',
  'LocationLong',
  'Longitude',
  'LongitudeDegrees',
  'GeoLongitude',
  'Lon',
  'Long',
  'lon'
] as const;

const TIMESTAMP_KEYS = ['Timestamp', 'TimeGenerated', 'EventTime', 'CreatedDateTime'] as const;

const LOCATION_KEYS = [
  'Location',
  'LocationCity',
  'City',
  'LocationState',
  'State',
  'LocationCountryOrRegion',
  'CountryOrRegion',
  'Country'
] as const;

const IP_ADDRESS_KEYS = [
  'IPAddress',
  'IpAddress',
  'ClientIP',
  'ClientIpAddress',
  'SourceIp',
  'SourceIpAddress'
] as const;

const PROTOCOL_KEYS = ['Protocol', 'AuthenticationProtocol', 'ClientAppUsed'] as const;
const STATUS_KEYS = ['AuthenticationRequirement', 'ResultType', 'Status'] as const;

const DEFAULT_VIEW = {
  longitude: 12,
  latitude: 40,
  zoom: 1.2,
  pitch: 30,
  bearing: 0
};

type CountryCoordinate = {
  latitude: number;
  longitude: number;
  label: string;
};

const COUNTRY_COORDINATES: Record<string, CountryCoordinate> = {
  DK: { latitude: 56.2639, longitude: 9.5018, label: 'Denmark' },
  DENMARK: { latitude: 56.2639, longitude: 9.5018, label: 'Denmark' },
  SE: { latitude: 60.1282, longitude: 18.6435, label: 'Sweden' },
  SWEDEN: { latitude: 60.1282, longitude: 18.6435, label: 'Sweden' },
  NO: { latitude: 60.472, longitude: 8.4689, label: 'Norway' },
  NORWAY: { latitude: 60.472, longitude: 8.4689, label: 'Norway' },
  FI: { latitude: 61.9241, longitude: 25.7482, label: 'Finland' },
  FINLAND: { latitude: 61.9241, longitude: 25.7482, label: 'Finland' },
  IS: { latitude: 64.9631, longitude: -19.0208, label: 'Iceland' },
  ICELAND: { latitude: 64.9631, longitude: -19.0208, label: 'Iceland' },
  DE: { latitude: 51.1657, longitude: 10.4515, label: 'Germany' },
  GERMANY: { latitude: 51.1657, longitude: 10.4515, label: 'Germany' },
  NL: { latitude: 52.1326, longitude: 5.2913, label: 'Netherlands' },
  NETHERLANDS: { latitude: 52.1326, longitude: 5.2913, label: 'Netherlands' },
  UK: { latitude: 55.3781, longitude: -3.436, label: 'United Kingdom' },
  GB: { latitude: 55.3781, longitude: -3.436, label: 'United Kingdom' },
  'UNITED KINGDOM': { latitude: 55.3781, longitude: -3.436, label: 'United Kingdom' },
  FR: { latitude: 46.2276, longitude: 2.2137, label: 'France' },
  FRANCE: { latitude: 46.2276, longitude: 2.2137, label: 'France' },
  ES: { latitude: 40.4637, longitude: -3.7492, label: 'Spain' },
  SPAIN: { latitude: 40.4637, longitude: -3.7492, label: 'Spain' },
  IT: { latitude: 41.8719, longitude: 12.5674, label: 'Italy' },
  ITALY: { latitude: 41.8719, longitude: 12.5674, label: 'Italy' },
  US: { latitude: 37.0902, longitude: -95.7129, label: 'United States' },
  USA: { latitude: 37.0902, longitude: -95.7129, label: 'United States' },
  'UNITED STATES': { latitude: 37.0902, longitude: -95.7129, label: 'United States' },
  CA: { latitude: 56.1304, longitude: -106.3468, label: 'Canada' },
  CANADA: { latitude: 56.1304, longitude: -106.3468, label: 'Canada' },
  BR: { latitude: -14.235, longitude: -51.9253, label: 'Brazil' },
  BRAZIL: { latitude: -14.235, longitude: -51.9253, label: 'Brazil' },
  AU: { latitude: -25.2744, longitude: 133.7751, label: 'Australia' },
  AUSTRALIA: { latitude: -25.2744, longitude: 133.7751, label: 'Australia' },
  NZ: { latitude: -40.9006, longitude: 174.886, label: 'New Zealand' },
  'NEW ZEALAND': { latitude: -40.9006, longitude: 174.886, label: 'New Zealand' },
  IN: { latitude: 20.5937, longitude: 78.9629, label: 'India' },
  INDIA: { latitude: 20.5937, longitude: 78.9629, label: 'India' },
  CN: { latitude: 35.8617, longitude: 104.1954, label: 'China' },
  CHINA: { latitude: 35.8617, longitude: 104.1954, label: 'China' },
  JP: { latitude: 36.2048, longitude: 138.2529, label: 'Japan' },
  JAPAN: { latitude: 36.2048, longitude: 138.2529, label: 'Japan' },
  SG: { latitude: 1.3521, longitude: 103.8198, label: 'Singapore' },
  SINGAPORE: { latitude: 1.3521, longitude: 103.8198, label: 'Singapore' },
  AE: { latitude: 23.4241, longitude: 53.8478, label: 'United Arab Emirates' },
  'UNITED ARAB EMIRATES': { latitude: 23.4241, longitude: 53.8478, label: 'United Arab Emirates' },
  ZA: { latitude: -30.5595, longitude: 22.9375, label: 'South Africa' },
  'SOUTH AFRICA': { latitude: -30.5595, longitude: 22.9375, label: 'South Africa' },
  NG: { latitude: 9.082, longitude: 8.6753, label: 'Nigeria' },
  NIGERIA: { latitude: 9.082, longitude: 8.6753, label: 'Nigeria' },
  RU: { latitude: 61.524, longitude: 105.3188, label: 'Russia' },
  RUSSIA: { latitude: 61.524, longitude: 105.3188, label: 'Russia' },
  MX: { latitude: 23.6345, longitude: -102.5528, label: 'Mexico' },
  MEXICO: { latitude: 23.6345, longitude: -102.5528, label: 'Mexico' }
};

const normalizeLookupKey = (value: string): string => value.trim().toUpperCase();

const resolveCountry = (value: string | undefined) => {
  if (!value) {
    return undefined;
  }
  const key = normalizeLookupKey(value);
  return COUNTRY_COORDINATES[key];
};

const getFirstString = (record: RawIdentityEvent, keys: readonly string[]): string | undefined => {
  for (const key of keys) {
    const value = record[key];
    if (typeof value === 'string' && value.trim().length > 0) {
      return value.trim();
    }
  }
  return undefined;
};

const getFirstNumber = (record: RawIdentityEvent, keys: readonly string[]): number | undefined => {
  for (const key of keys) {
    const value = record[key];
    if (typeof value === 'number' && Number.isFinite(value)) {
      return value;
    }
    if (typeof value === 'string') {
      const parsed = Number(value);
      if (Number.isFinite(parsed)) {
        return parsed;
      }
    }
  }
  return undefined;
};

const getFirstTimestamp = (record: RawIdentityEvent): string | undefined => {
  const stringTimestamp = getFirstString(record, TIMESTAMP_KEYS);
  if (stringTimestamp) {
    return stringTimestamp;
  }
  for (const key of TIMESTAMP_KEYS) {
    const value = record[key];
    if (value instanceof Date && !Number.isNaN(value.getTime())) {
      return value.toISOString();
    }
  }
  return undefined;
};

const buildDisplayLocation = (record: RawIdentityEvent): string => {
  const city = getFirstString(record, ['LocationCity', 'City']);
  const country = getFirstString(record, ['LocationCountryOrRegion', 'CountryOrRegion', 'Country']);
  const location = getFirstString(record, LOCATION_KEYS);

  const locationCandidates = [location, country, city].filter((value): value is string => Boolean(value));
  for (const candidate of locationCandidates) {
    const resolved = resolveCountry(candidate);
    if (resolved) {
      return resolved.label;
    }
  }

  if (city && country) {
    return `${city}, ${country}`;
  }
  if (location) {
    return location;
  }
  if (city) {
    return city;
  }
  if (country) {
    return country;
  }
  return 'Unknown location';
};

const resolveCoordinates = (
  record: RawIdentityEvent,
  displayLocation: string,
  explicitLatitude?: number,
  explicitLongitude?: number
): { latitude?: number; longitude?: number; labelOverride?: string } => {
  if (typeof explicitLatitude === 'number' && typeof explicitLongitude === 'number') {
    return { latitude: explicitLatitude, longitude: explicitLongitude };
  }

  const locationValue = getFirstString(record, LOCATION_KEYS);
  const countryCandidates = new Set<string>();
  if (locationValue) {
    countryCandidates.add(locationValue);
    locationValue.split(/[,\-]/).forEach(part => {
      const trimmed = part.trim();
      if (trimmed) {
        countryCandidates.add(trimmed);
      }
    });
  }

  if (displayLocation) {
    countryCandidates.add(displayLocation);
    displayLocation.split(',').forEach(part => {
      const trimmed = part.trim();
      if (trimmed) {
        countryCandidates.add(trimmed);
      }
    });
  }

  const isp = getFirstString(record, ['ISP']);
  if (isp) {
    countryCandidates.add(isp);
  }

  for (const candidate of countryCandidates) {
    const resolved = resolveCountry(candidate);
    if (resolved) {
      return {
        latitude: resolved.latitude,
        longitude: resolved.longitude,
        labelOverride: resolved.label
      };
    }
  }

  return {};
};

const formatTimestamp = (timestamp: string): string => {
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) {
    return timestamp;
  }
  return date.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  });
};

const transformEvents = (rawEvents: RawIdentityEvent[]): SignInEvent[] => {
  return rawEvents
    .map((raw, index) => {
      const timestamp = getFirstTimestamp(raw);
      const ipAddress = getFirstString(raw, IP_ADDRESS_KEYS);
      const protocol = getFirstString(raw, PROTOCOL_KEYS);
      const status = getFirstString(raw, STATUS_KEYS);
      const displayLocation = buildDisplayLocation(raw);
      const explicitLatitude = getFirstNumber(raw, LATITUDE_KEYS);
      const explicitLongitude = getFirstNumber(raw, LONGITUDE_KEYS);
      const coordinateResolution = resolveCoordinates(raw, displayLocation, explicitLatitude, explicitLongitude);
      const latitude = explicitLatitude ?? coordinateResolution.latitude;
      const longitude = explicitLongitude ?? coordinateResolution.longitude;
      const idCandidate =
        getFirstString(raw, ['EventId', 'Id', 'ActivityId', 'LogonId']) ??
        `${timestamp ?? 'event'}-${index}`;

      if (!timestamp) {
        return null;
      }

      return {
        id: idCandidate,
        timestamp,
        displayLocation: coordinateResolution.labelOverride ?? displayLocation,
        ipAddress: ipAddress ?? undefined,
        latitude,
        longitude,
        protocol: protocol ?? undefined,
        status: status ?? undefined,
        raw
      } satisfies SignInEvent;
    })
    .filter((event): event is SignInEvent => event !== null)
    .sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());
};

const buildGeoJson = (events: SignInEvent[]): FeatureCollection<Point> => {
  const features: Feature<Point>[] = events
    .filter(event => typeof event.latitude === 'number' && typeof event.longitude === 'number')
    .map(event => ({
      type: 'Feature',
      geometry: {
        type: 'Point',
        coordinates: [event.longitude as number, event.latitude as number]
      },
      properties: {
        id: event.id,
        location: event.displayLocation,
        timestamp: event.timestamp,
        ipAddress: event.ipAddress ?? ''
      }
    }));

  return {
    type: 'FeatureCollection',
    features
  };
};

const resolveApiBaseUrl = (): string => {
  const explicit = import.meta.env.VITE_API_BASE_URL;
  if (typeof explicit === 'string' && explicit.trim()) {
    return explicit.trim().replace(/\/$/, '');
  }

  if (typeof window !== 'undefined') {
    const origin = window.location.origin;
    if (origin.includes('localhost')) {
      return 'http://localhost:6081';
    }
    return origin.replace(/\/$/, '');
  }

  return 'http://localhost:6081';
};


const locationLayer: Layer = {
  id: 'identity-events',
  type: 'circle',
  paint: {
    'circle-radius': [
      'interpolate',
      ['linear'],
      ['zoom'],
      1,
      4,
      5,
      8
    ],
    'circle-color': '#f97316',
    'circle-stroke-color': '#111827',
    'circle-stroke-width': 1.5,
    'circle-opacity': 0.85
  }
};

const DEFAULT_STYLE = 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json';

const UnfamiliarLoginPage: React.FC<UnfamiliarLoginPageProps> = ({ accessToken, backendApiToken, onClose }) => {
  const [username, setUsername] = useState('');
  const [lookback, setLookback] = useState('7d');
  const [events, setEvents] = useState<SignInEvent[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedEventId, setSelectedEventId] = useState<string | null>(null);
  const [activeUser, setActiveUser] = useState<string>('');
  const [activeLookback, setActiveLookback] = useState<string>('7d');

  const effectiveAuthToken = useMemo(() => {
    const manualToken = backendApiToken?.trim();
    if (manualToken) {
      return manualToken;
    }
    const azureToken = accessToken?.trim();
    return azureToken && azureToken.length > 0 ? azureToken : null;
  }, [backendApiToken, accessToken]);

  const isUsingBackendToken = Boolean(backendApiToken?.trim());

  const mapRef = useRef<MapRef | null>(null);

  const eventsWithCoordinates = useMemo(
    () => events.filter(event => typeof event.latitude === 'number' && typeof event.longitude === 'number'),
    [events]
  );

  const geoJson = useMemo(() => buildGeoJson(events), [events]);

  const selectedEvent = useMemo(
    () => events.find(event => event.id === selectedEventId) ?? null,
    [events, selectedEventId]
  );

  const fitMapToEvents = useCallback(
    (map: MaplibreMap, targetEvents: SignInEvent[]) => {
      if (!map || targetEvents.length === 0) {
        return;
      }

      const bounds = new LngLatBounds();
      targetEvents.forEach(event => {
        if (typeof event.longitude === 'number' && typeof event.latitude === 'number') {
          bounds.extend([event.longitude, event.latitude]);
        }
      });

      if (!bounds.isEmpty()) {
        map.fitBounds(bounds, {
          padding: 60,
          duration: 1200
        });
      }
    },
    []
  );

  useEffect(() => {
    const mapInstance = mapRef.current?.getMap();
    if (mapInstance && eventsWithCoordinates.length > 0) {
      fitMapToEvents(mapInstance, eventsWithCoordinates);
    }
  }, [eventsWithCoordinates, fitMapToEvents]);

  const handleSelectEvent = (event: SignInEvent) => {
    setSelectedEventId(event.id);
    if (typeof event.longitude === 'number' && typeof event.latitude === 'number') {
      const mapInstance = mapRef.current?.getMap();
      mapInstance?.flyTo({
        center: [event.longitude, event.latitude],
        zoom: Math.max(mapInstance.getZoom(), 3.5),
        speed: 0.8,
        pitch: 45
      });
    }
  };

  const fetchIdentityEvents = async (targetUser: string, windowParam: string) => {
    if (!targetUser.trim()) {
      setError('Please enter a username to look up sign-ins.');
      return;
    }
    if (!effectiveAuthToken) {
      setError('API authorization token missing. Save a backend token on the dashboard before fetching.');
      return;
    }

    setLoading(true);
    setError(null);
    setSelectedEventId(null);

    try {
      const baseUrl = resolveApiBaseUrl();
      const endpoint = `${baseUrl}/graph/v1.0/identitylogonevents/${encodeURIComponent(targetUser)}`;
      const url = windowParam ? `${endpoint}?lookback=${encodeURIComponent(windowParam)}` : endpoint;

      const tokenForHeader = /^Bearer\s+/i.test(effectiveAuthToken) ? effectiveAuthToken : `Bearer ${effectiveAuthToken}`;

      const response = await fetch(url, {
        method: 'GET',
        headers: {
          Authorization: tokenForHeader,
          'Content-Type': 'application/json'
        }
      });

      if (!response.ok) {
        const message = await response.text();
        throw new Error(message || `Request failed with status ${response.status}`);
      }

      const payload = (await response.json()) as IdentityLogonResponse;
      const rawResults = Array.isArray(payload?.results) ? payload.results : [];
      const transformed = transformEvents(rawResults);

      if (transformed.length === 0) {
        setEvents([]);
        setError('No sign-in activity found for this user in the selected window.');
        setActiveUser(targetUser);
        setActiveLookback(windowParam || '7d');
        return;
      }

      const primarySelection =
        transformed.find(event => typeof event.latitude === 'number' && typeof event.longitude === 'number') ??
        transformed[0];

      setEvents(transformed);
      setSelectedEventId(primarySelection.id);
      setActiveUser(targetUser);
      setActiveLookback(windowParam || '7d');
    } catch (err) {
      console.error('Failed to load IdentityLogonEvents', err);
      const fallbackMessage =
        err instanceof Error ? err.message : 'An unexpected error occurred while loading sign-ins.';
      setError(fallbackMessage);
      setEvents([]);
      setActiveUser('');
      setActiveLookback(windowParam || '7d');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    void fetchIdentityEvents(username, lookback);
  };

  return (
    <div className="unfamiliar-login-overlay" role="dialog" aria-modal="true">
      <div className="signin-activity-modal">
        <header className="signin-activity-header">
          <div>
            <h2>Identity Sign-in Activity</h2>
            <p>Investigate sign-ins per user over a configurable lookback window.</p>
          </div>
          <button className="close-button" onClick={onClose} aria-label="Close">
            ×
          </button>
        </header>

        <form className="signin-controls" onSubmit={handleSubmit}>
          <div className={`token-status-banner ${effectiveAuthToken ? 'ready' : 'missing'}`}>
            {effectiveAuthToken
              ? isUsingBackendToken
                ? 'Using backend API token saved on the dashboard.'
                : 'Using Azure AD access token.'
              : 'No API token available. Save one on the dashboard to continue.'}
          </div>
          <div className="input-group">
            <label htmlFor="signin-username">User Principal Name</label>
            <input
              id="signin-username"
              type="text"
              value={username}
              onChange={event => setUsername(event.target.value)}
              placeholder="e.g. vicre@dtu.dk"
              autoFocus
              required
              disabled={loading}
            />
          </div>
          <div className="input-group">
            <label htmlFor="signin-lookback">Lookback Window</label>
            <input
              id="signin-lookback"
              type="text"
              value={lookback}
              onChange={event => setLookback(event.target.value)}
              placeholder="7d"
              disabled={loading}
            />
          </div>
          <button
            type="submit"
            className="submit-button"
            disabled={loading || !username.trim() || !effectiveAuthToken}
          >
            {loading ? 'Fetching…' : 'Load sign-ins'}
          </button>
        </form>

        <section className="signin-content">
          <div className="globe-panel">
            <Map
              ref={mapRef}
              initialViewState={DEFAULT_VIEW}
              mapStyle={DEFAULT_STYLE}
              projection="globe"
              style={{ width: '100%', height: '100%' }}
              scrollZoom
              dragPan
              attributionControl={false}
            >
              <Source id="identity-events-source" type="geojson" data={geoJson}>
                <Layer {...locationLayer} />
              </Source>

              {selectedEvent &&
                typeof selectedEvent.latitude === 'number' &&
                typeof selectedEvent.longitude === 'number' && (
                  <Popup
                    latitude={selectedEvent.latitude}
                    longitude={selectedEvent.longitude}
                    anchor="bottom"
                    closeButton={false}
                    closeOnClick={false}
                  >
                    <div className="popup-content">
                      <strong>{selectedEvent.displayLocation}</strong>
                      <p>{formatTimestamp(selectedEvent.timestamp)}</p>
                      {selectedEvent.ipAddress && <p>IP: {selectedEvent.ipAddress}</p>}
                      {selectedEvent.protocol && <p>Protocol: {selectedEvent.protocol}</p>}
                      {selectedEvent.status && <p>Status: {selectedEvent.status}</p>}
                    </div>
                  </Popup>
                )}
            </Map>
            {activeUser && events.length > 0 && (
              <div className="globe-caption">
                Highlighting sign-ins for <strong>{activeUser}</strong>
                {activeLookback ? ` • lookback ${activeLookback}` : ''}
              </div>
            )}
            {eventsWithCoordinates.length === 0 && !loading && !error && events.length > 0 && (
              <div className="no-coordinates">
                No geographic coordinates were returned for these sign-ins. Full details are available in the list.
              </div>
            )}
          </div>

          <aside className="timeline-panel">
            <div className="timeline-header">
              <h3>Sign-ins</h3>
              <span>{events.length}</span>
            </div>

            {error && <div className="error-state">{error}</div>}

            {!error && !loading && events.length === 0 && (
              <div className="empty-state">
                Enter a user principal name and select “Load sign-ins” to review their activity.
              </div>
            )}

            {loading && <div className="loading-indicator">Loading sign-ins…</div>}

            <div className="timeline-list">
              {events.map(event => (
                <button
                  key={event.id}
                  onClick={() => handleSelectEvent(event)}
                  className={`timeline-item${event.id === selectedEventId ? ' active' : ''}`}
                  type="button"
                >
                  <span className="event-location">{event.displayLocation}</span>
                  <span className="event-timestamp">{formatTimestamp(event.timestamp)}</span>
                  <span className="event-meta">
                    {event.ipAddress ? `IP ${event.ipAddress}` : 'IP unknown'}
                    {event.protocol ? ` · ${event.protocol}` : ''}
                    {event.status ? ` · ${event.status}` : ''}
                  </span>
                </button>
              ))}
            </div>
          </aside>
        </section>
      </div>
    </div>
  );
};

export default UnfamiliarLoginPage;
