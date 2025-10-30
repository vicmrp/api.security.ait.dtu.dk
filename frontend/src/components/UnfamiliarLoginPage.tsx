import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import MapComponent, { Layer, MapRef, Popup, Source } from 'react-map-gl/maplibre';
import type { Feature, FeatureCollection, Point } from 'geojson';
import type { Map as MaplibreMap } from 'maplibre-gl';
import { LngLatBounds } from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import './UnfamiliarLoginPage.css';
import { buildBearerToken, resolveApiBaseUrl } from '../utils/apiBaseUrl';

type LayerProps = React.ComponentProps<typeof Layer>;

interface UnfamiliarLoginPageProps {
  accessToken?: string | null;
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
  geo?: GeoLookupResult;
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

const DTU_CAMPUS_COORDINATES: CountryCoordinate = {
  latitude: 55.786545,
  longitude: 12.521999,
  label: 'DTU Campus, Lyngby'
};

const PRIVATE_IPV4_PATTERNS = [
  /^10\./,
  /^127\./,
  /^169\.254\./,
  /^172\.(1[6-9]|2[0-9]|3[0-1])\./,
  /^192\.168\./,
  /^100\.(6[4-9]|[7-9][0-9]|1[0-1][0-9]|12[0-7])\./
];

const PRIVATE_IPV6_PATTERNS = [/^::1$/, /^fc/i, /^fd/i, /^fe80/i];

const isPrivateIpAddress = (ip: string): boolean => {
  if (!ip) {
    return false;
  }

  const trimmed = ip.trim();
  if (trimmed.includes(':')) {
    return PRIVATE_IPV6_PATTERNS.some(pattern => pattern.test(trimmed));
  }

  return PRIVATE_IPV4_PATTERNS.some(pattern => pattern.test(trimmed));
};

interface GeoLookupResult {
  ip: string;
  latitude?: number;
  longitude?: number;
  label: string;
  city?: string;
  region?: string;
  country?: string;
  isp?: string;
  source: 'private' | 'ipwhois' | 'unresolved';
  isPrivate: boolean;
  raw?: unknown;
}

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
  const events: SignInEvent[] = [];

  rawEvents.forEach((raw, index) => {
    const timestamp = getFirstTimestamp(raw);
    if (!timestamp) {
      return;
    }

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
      `${timestamp}-${index}`;

    const event: SignInEvent = {
      id: idCandidate,
      timestamp,
      displayLocation: coordinateResolution.labelOverride ?? displayLocation,
      ipAddress: ipAddress ?? undefined,
      latitude,
      longitude,
      protocol: protocol ?? undefined,
      status: status ?? undefined,
      raw
    };

    events.push(event);
  });

  return events.sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());
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

const locationLayer: LayerProps = {
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

const UnfamiliarLoginPage: React.FC<UnfamiliarLoginPageProps> = ({ accessToken, onClose }) => {
  const [username, setUsername] = useState('');
  const [lookback, setLookback] = useState('7d');
  const [events, setEvents] = useState<SignInEvent[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedEventId, setSelectedEventId] = useState<string | null>(null);
  const [activeUser, setActiveUser] = useState<string>('');
  const [activeLookback, setActiveLookback] = useState<string>('7d');
  const [isMapReady, setIsMapReady] = useState(false);
  const geolocationCacheRef = useRef<Map<string, GeoLookupResult>>(new Map());

  const effectiveAuthToken = useMemo(() => {
    const azureToken = accessToken?.trim();
    return azureToken && azureToken.length > 0 ? azureToken : null;
  }, [accessToken]);


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
  const selectedEventRawJson = useMemo(
    () => (selectedEvent ? JSON.stringify(selectedEvent.raw, null, 2) : ''),
    [selectedEvent]
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

  useEffect(() => {
    if (!isMapReady) {
      return;
    }

    const mapInstance = mapRef.current?.getMap();
    if (!mapInstance) {
      return;
    }

    mapInstance.scrollZoom.enable({ around: 'center' });
    mapInstance.touchZoomRotate.enable({ around: 'center' });
  }, [isMapReady]);

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

  const resolveIpGeolocation = useCallback(
    async (ip: string): Promise<GeoLookupResult> => {
      const normalized = ip.trim();
      const cache = geolocationCacheRef.current;
      const cached = cache.get(normalized);
      if (cached) {
        return cached;
      }

      let result: GeoLookupResult;

      if (isPrivateIpAddress(normalized)) {
        result = {
          ip: normalized,
          latitude: DTU_CAMPUS_COORDINATES.latitude,
          longitude: DTU_CAMPUS_COORDINATES.longitude,
          label: DTU_CAMPUS_COORDINATES.label,
          city: 'Lyngby',
          region: 'Lyngby-Taarbæk',
          country: 'Denmark',
          isp: 'DTU Campus Network',
          source: 'private',
          isPrivate: true
        };
      } else {
        try {
          const controller = new AbortController();
          let timeoutId: ReturnType<typeof setTimeout> | undefined;
          let payload: any = null;

          try {
            timeoutId = setTimeout(() => controller.abort(), 6000);
            const response = await fetch(`https://ipwho.is/${encodeURIComponent(normalized)}`, {
              signal: controller.signal
            });

            if (!response.ok) {
              throw new Error(`ipwho.is responded with status ${response.status}`);
            }

            payload = await response.json();
          } finally {
            if (timeoutId) {
              clearTimeout(timeoutId);
            }
          }

          if (payload?.success) {
            const labelParts = [payload.city, payload.region, payload.country]
              .map((part: string | undefined) => (typeof part === 'string' && part.trim() ? part.trim() : null))
              .filter(Boolean) as string[];
            const label = labelParts.length > 0 ? labelParts.join(', ') : payload.country || 'Unknown location';

            result = {
              ip: normalized,
              latitude: typeof payload.latitude === 'number' ? payload.latitude : undefined,
              longitude: typeof payload.longitude === 'number' ? payload.longitude : undefined,
              city: payload.city || undefined,
              region: payload.region || payload.region_name || undefined,
              country: payload.country || undefined,
              isp: payload.connection?.isp || payload.isp || payload.org || undefined,
              label: label || 'Unknown location',
              source: 'ipwhois',
              isPrivate: false,
              raw: payload
            };
          } else {
            result = {
              ip: normalized,
              label: 'Unknown location',
              source: 'unresolved',
              isPrivate: false,
              raw: payload
            };
          }
        } catch (lookupError) {
          console.warn('Failed to resolve IP geolocation', normalized, lookupError);
          result = {
            ip: normalized,
            label: 'Unknown location',
            source: 'unresolved',
            isPrivate: false
          };
        }
      }

      cache.set(normalized, result);
      return result;
    },
    []
  );

  const enrichEventsWithGeolocation = useCallback(
    async (incomingEvents: SignInEvent[]): Promise<SignInEvent[]> => {
      if (incomingEvents.length === 0) {
        return incomingEvents;
      }

      const uniqueIps = Array.from(
        new Set(
          incomingEvents
            .map(event => event.ipAddress?.trim())
            .filter((value): value is string => Boolean(value))
        )
      );

      if (uniqueIps.length === 0) {
        return incomingEvents;
      }

      const lookups = await Promise.all(
        uniqueIps.map(async ip => {
          try {
            return await resolveIpGeolocation(ip);
          } catch (err) {
            console.warn('Geolocation lookup failed for', ip, err);
            return null;
          }
        })
      );

      const lookupMap = new Map<string, GeoLookupResult>();
      for (const entry of lookups) {
        if (entry) {
          lookupMap.set(entry.ip, entry);
        }
      }

      return incomingEvents.map(event => {
        const ip = event.ipAddress?.trim();
        if (!ip) {
          return event;
        }

        const geo = lookupMap.get(ip);
        if (!geo) {
          return event;
        }

        const latitude = typeof geo.latitude === 'number' ? geo.latitude : event.latitude;
        const longitude = typeof geo.longitude === 'number' ? geo.longitude : event.longitude;
        const locationLabel =
          geo.label && geo.label !== 'Unknown location' ? geo.label : event.displayLocation;

        return {
          ...event,
          latitude,
          longitude,
          displayLocation: locationLabel || event.displayLocation,
          geo
        };
      });
    },
    [resolveIpGeolocation]
  );

  const fetchIdentityEvents = async (targetUser: string, windowParam: string) => {
    if (!targetUser.trim()) {
      setError('Please enter a username to look up sign-ins.');
      return;
    }
    if (!effectiveAuthToken) {
      setError('API authorization token missing. Please sign in again.');
      return;
    }

    setLoading(true);
    setError(null);
    setSelectedEventId(null);

    try {
      const baseUrl = resolveApiBaseUrl();
      const endpoint = `${baseUrl}/graph/v1.0/identitylogonevents/${encodeURIComponent(targetUser)}`;
      const url = windowParam ? `${endpoint}?lookback=${encodeURIComponent(windowParam)}` : endpoint;

      const response = await fetch(url, {
        method: 'GET',
        headers: {
          Authorization: buildBearerToken(effectiveAuthToken),
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
      const enriched = await enrichEventsWithGeolocation(transformed);

      if (enriched.length === 0) {
        setEvents([]);
        setError('No sign-in activity found for this user in the selected window.');
        setActiveUser(targetUser);
        setActiveLookback(windowParam || '7d');
        return;
      }

      const primarySelection =
        enriched.find(event => typeof event.latitude === 'number' && typeof event.longitude === 'number') ??
        enriched[0];

      setEvents(enriched);
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
              ? 'Using Azure AD access token.'
              : 'No API token available. Please sign in again to continue.'}
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
            <MapComponent
              ref={mapRef}
              initialViewState={DEFAULT_VIEW}
              mapStyle={DEFAULT_STYLE}
              projection="globe"
              style={{ width: '100%', height: '100%' }}
              scrollZoom={{ around: 'center' }}
              touchZoomRotate={{ around: 'center' }}
              dragPan
              attributionControl={false}
              onLoad={() => setIsMapReady(true)}
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
                      {selectedEvent.geo?.isp && <p>ISP: {selectedEvent.geo.isp}</p>}
                      {selectedEvent.geo?.country && (
                        <p>
                          Region:{' '}
                          {[selectedEvent.geo.city, selectedEvent.geo.region, selectedEvent.geo.country]
                            .filter(Boolean)
                            .join(', ')}
                        </p>
                      )}
                      {selectedEvent.geo?.isPrivate && <p>Private network · DTU campus fallback</p>}
                      {selectedEvent.protocol && <p>Protocol: {selectedEvent.protocol}</p>}
                      {selectedEvent.status && <p>Status: {selectedEvent.status}</p>}
                    </div>
                  </Popup>
                )}
            </MapComponent>
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

            {selectedEvent && (
              <div className="timeline-details">
                <h4>Sign-in details</h4>
                <div className="details-grid">
                  <div>
                    <span className="details-label">Timestamp</span>
                    <span className="details-value">{formatTimestamp(selectedEvent.timestamp)}</span>
                  </div>
                  <div>
                    <span className="details-label">Location</span>
                    <span className="details-value">
                      {selectedEvent.displayLocation}
                      {selectedEvent.geo?.isPrivate ? ' · Private network' : ''}
                    </span>
                  </div>
                  <div>
                    <span className="details-label">Coordinates</span>
                    <span className="details-value">
                      {typeof selectedEvent.latitude === 'number' && typeof selectedEvent.longitude === 'number'
                        ? `${selectedEvent.latitude.toFixed(4)}, ${selectedEvent.longitude.toFixed(4)}`
                        : 'Not available'}
                    </span>
                  </div>
                  <div>
                    <span className="details-label">Region</span>
                    <span className="details-value">
                      {[selectedEvent.geo?.city, selectedEvent.geo?.region, selectedEvent.geo?.country]
                        .filter(Boolean)
                        .join(', ') || 'Unknown'}
                    </span>
                  </div>
                  <div>
                    <span className="details-label">IP address</span>
                    <span className="details-value">
                      {selectedEvent.ipAddress ?? 'Unknown'}
                      {selectedEvent.geo?.isp ? ` · ${selectedEvent.geo.isp}` : ''}
                    </span>
                  </div>
                  <div>
                    <span className="details-label">Geo source</span>
                    <span className="details-value">
                      {selectedEvent.geo?.source === 'ipwhois'
                        ? 'ipwho.is lookup'
                        : selectedEvent.geo?.source === 'private'
                        ? 'DTU campus fallback'
                        : 'Graph data'}
                    </span>
                  </div>
                  <div>
                    <span className="details-label">Protocol</span>
                    <span className="details-value">{selectedEvent.protocol ?? 'Unknown'}</span>
                  </div>
                  <div>
                    <span className="details-label">Status</span>
                    <span className="details-value">{selectedEvent.status ?? 'Unknown'}</span>
                  </div>
                  <div>
                    <span className="details-label">Application</span>
                    <span className="details-value">
                      {(selectedEvent.raw['Application'] as string) || 'Unknown'}
                    </span>
                  </div>
                  <div>
                    <span className="details-label">Logon type</span>
                    <span className="details-value">
                      {(selectedEvent.raw['LogonType'] as string) || 'Unknown'}
                    </span>
                  </div>
                  <div>
                    <span className="details-label">Failure reason</span>
                    <span className="details-value">
                      {(selectedEvent.raw['FailureReason'] as string) || 'None reported'}
                    </span>
                  </div>
                </div>
                <details className="raw-event-details">
                  <summary>Raw event payload</summary>
                  <pre>{selectedEventRawJson}</pre>
                </details>
              </div>
            )}
          </aside>
        </section>
      </div>
    </div>
  );
};

export default UnfamiliarLoginPage;
