import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import MapComponent, { Layer, MapRef, Popup, Source } from 'react-map-gl/maplibre';
import type { MapLayerMouseEvent } from 'react-map-gl/maplibre';
import type { Feature, FeatureCollection, Point } from 'geojson';
import type { Map as MaplibreMap } from 'maplibre-gl';
import { LngLatBounds } from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import './UnfamiliarLoginPage.css';
import { buildBearerToken, resolveApiBaseUrl } from '../utils/apiBaseUrl';

type LayerProps = React.ComponentProps<typeof Layer>;

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
  geo?: GeoLookupResult;
  raw: RawIdentityEvent;
}

interface ContextMenuState {
  eventId: string;
  position: {
    x: number;
    y: number;
  };
  source: 'map' | 'timeline';
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

const buildBackendTokenHeader = (token: string): string => {
  const trimmed = token.trim();
  if (/^(Token|Bearer)\s+/i.test(trimmed)) {
    return trimmed;
  }
  return `Token ${trimmed}`;
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
    .map((event, index) => {
      // Placeholder: Mark every 3rd event as warning for demo purposes
      // Replace this logic with actual API warning data
      const isWarning = index % 3 === 0;
      return {
        type: 'Feature',
        geometry: {
          type: 'Point',
          coordinates: [event.longitude as number, event.latitude as number]
        },
        properties: {
          id: event.id,
          location: event.displayLocation,
          timestamp: event.timestamp,
          ipAddress: event.ipAddress ?? '',
          isWarning: isWarning ? 1 : 0
        }
      };
    });

  return {
    type: 'FeatureCollection',
    features
  };
};

const LOCATION_LAYER_ID = 'identity-events';

const locationLayer: LayerProps = {
  id: LOCATION_LAYER_ID,
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
    'circle-color': [
      'case',
      ['==', ['get', 'isWarning'], 1],
      '#ef4444',
      '#10b981'
    ],
    'circle-stroke-color': '#111827',
    'circle-stroke-width': 1.5,
    'circle-opacity': 0.85
  }
};

const DEFAULT_STYLE = 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json';

const TIMELINE_SPLIT_STORAGE_KEY = 'signinTimelineSplit';
const DETAILS_EXPANDED_STORAGE_KEY = 'signinDetailsExpanded';
const TIMELINE_SPLIT_DEFAULT = 44;
const TIMELINE_SPLIT_MIN = 28;
const TIMELINE_SPLIT_MAX = 72;

const clampTimelineSplit = (value: number): number =>
  Math.min(Math.max(value, TIMELINE_SPLIT_MIN), TIMELINE_SPLIT_MAX);

const readStoredTimelineSplit = (): number => {
  if (typeof window === 'undefined') {
    return TIMELINE_SPLIT_DEFAULT;
  }

  try {
    const stored = window.localStorage.getItem(TIMELINE_SPLIT_STORAGE_KEY);
    const parsed = stored ? Number.parseFloat(stored) : NaN;
    return Number.isFinite(parsed) ? clampTimelineSplit(parsed) : TIMELINE_SPLIT_DEFAULT;
  } catch {
    return TIMELINE_SPLIT_DEFAULT;
  }
};

const readStoredDetailsExpanded = (): boolean => {
  if (typeof window === 'undefined') {
    return false;
  }

  try {
    return window.localStorage.getItem(DETAILS_EXPANDED_STORAGE_KEY) === 'true';
  } catch {
    return false;
  }
};

const UnfamiliarLoginPage: React.FC<UnfamiliarLoginPageProps> = ({
  accessToken,
  backendApiToken,
  onClose
}) => {
  const [username, setUsername] = useState('');
  const [lookback, setLookback] = useState('7d');
  const [events, setEvents] = useState<SignInEvent[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedEventId, setSelectedEventId] = useState<string | null>(null);
  const [activeUser, setActiveUser] = useState<string>('');
  const [activeLookback, setActiveLookback] = useState<string>('7d');
  const [contextMenuState, setContextMenuState] = useState<ContextMenuState | null>(null);
  const [isMapReady, setIsMapReady] = useState(false);
  const [rawCopyStatus, setRawCopyStatus] = useState<'idle' | 'success' | 'error'>('idle');
  const [timelineListWidthPercent, setTimelineListWidthPercent] = useState<number>(
    readStoredTimelineSplit
  );
  const [isDetailsExpanded, setIsDetailsExpanded] =
    useState<boolean>(readStoredDetailsExpanded);
  const [isTimelineResizing, setIsTimelineResizing] = useState(false);
  const [activeTab, setActiveTab] = useState<'signin' | 'hibp' | 'actions'>('signin');
  const [hibpData, setHibpData] = useState<any[]>([]);
  const [hibpLoading, setHibpLoading] = useState(false);
  const [hibpError, setHibpError] = useState<string | null>(null);
  const copyStatusTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const timelineBodyRef = useRef<HTMLDivElement | null>(null);
  const activeResizerPointerIdRef = useRef<number | null>(null);
  const geolocationCacheRef = useRef<Map<string, GeoLookupResult>>(new Map());

  const clearCopyStatusTimeout = useCallback(() => {
    if (copyStatusTimeoutRef.current) {
      clearTimeout(copyStatusTimeoutRef.current);
      copyStatusTimeoutRef.current = null;
    }
  }, []);

  const authContext = useMemo(() => {
    const manualToken = backendApiToken?.trim();
    if (manualToken) {
      return {
        header: buildBackendTokenHeader(manualToken),
        source: 'backend' as const
      };
    }

    const azureToken = accessToken?.trim();
    if (azureToken && azureToken.length > 0) {
      return {
        header: buildBearerToken(azureToken),
        source: 'azure' as const
      };
    }

    return null;
  }, [backendApiToken, accessToken]);

  const effectiveAuthToken = authContext?.header ?? null;
  const isUsingBackendToken = authContext?.source === 'backend';

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

  const contextMenuEvent = useMemo(
    () =>
      contextMenuState ? events.find(event => event.id === contextMenuState.eventId) ?? null : null,
    [contextMenuState, events]
  );

  const closeContextMenu = useCallback(() => {
    setContextMenuState(null);
  }, []);

  const openContextMenu = useCallback(
    (eventId: string, clientX: number, clientY: number, source: ContextMenuState['source']) => {
      const estimatedWidth = 220;
      const estimatedHeight = 96;

      let x = clientX;
      let y = clientY;

      if (typeof window !== 'undefined') {
        x = Math.min(clientX, window.innerWidth - estimatedWidth);
        y = Math.min(clientY, window.innerHeight - estimatedHeight);
      }

      setContextMenuState({
        eventId,
        position: { x, y },
        source
      });
    },
    []
  );

  const fetchHibpData = useCallback(async (email: string) => {
    if (!authContext?.header) {
      setHibpError('Authentication required. Please sign in with Azure AD or save a backend API token in the dashboard settings.');
      return;
    }

    setHibpLoading(true);
    setHibpError(null);

    try {
      // Use Vite proxy to call HIBP API directly
      const encodedEmail = encodeURIComponent(email.trim());
      const response = await fetch(
        `/hibp-api/api/v3/breachedaccount/${encodedEmail}?truncateResponse=false&includeUnverified=false`,
        {
          method: 'GET',
          headers: {
            'Accept': 'application/json'
          }
        }
      );

      if (response.status === 404) {
        // No breaches found
        setHibpData([]);
      } else if (response.ok) {
        const data = await response.json();
        console.log('HIBP data:', data);
        setHibpData(Array.isArray(data) ? data : []);
      } else {
        throw new Error(`HIBP API error: ${response.status}`);
      }
    } catch (err) {
      setHibpError(err instanceof Error ? err.message : 'Failed to fetch HIBP data');
      setHibpData([]);
    } finally {
      setHibpLoading(false);
    }
  }, [authContext]);

  useEffect(() => {
    if (!contextMenuState) {
      return;
    }

    const handleDismiss = () => {
      setContextMenuState(null);
    };

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setContextMenuState(null);
      }
    };

    window.addEventListener('click', handleDismiss);
    window.addEventListener('scroll', handleDismiss, true);
    window.addEventListener('resize', handleDismiss);
    window.addEventListener('keydown', handleKeyDown);

    return () => {
      window.removeEventListener('click', handleDismiss);
      window.removeEventListener('scroll', handleDismiss, true);
      window.removeEventListener('resize', handleDismiss);
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [contextMenuState]);

  useEffect(() => {
    if (typeof window === 'undefined') {
      return;
    }

    try {
      window.localStorage.setItem(TIMELINE_SPLIT_STORAGE_KEY, timelineListWidthPercent.toFixed(2));
    } catch {
      // Ignore storage write failures (e.g. private mode)
    }
  }, [timelineListWidthPercent]);

  useEffect(() => {
    if (typeof window === 'undefined') {
      return;
    }

    try {
      window.localStorage.setItem(DETAILS_EXPANDED_STORAGE_KEY, String(isDetailsExpanded));
    } catch {
      // Ignore storage write failures (e.g. private mode)
    }
  }, [isDetailsExpanded]);

  useEffect(() => {
    if (!isTimelineResizing) {
      return;
    }

    const handlePointerMove = (event: PointerEvent) => {
      if (event.pointerId !== activeResizerPointerIdRef.current) {
        return;
      }

      const container = timelineBodyRef.current;
      if (!container) {
        return;
      }

      const rect = container.getBoundingClientRect();
      if (rect.width <= 0) {
        return;
      }

      const rawPercent = ((event.clientX - rect.left) / rect.width) * 100;
      setTimelineListWidthPercent(clampTimelineSplit(rawPercent));
    };

    const handlePointerUp = (event: PointerEvent) => {
      if (event.pointerId !== activeResizerPointerIdRef.current) {
        return;
      }

      activeResizerPointerIdRef.current = null;
      setIsTimelineResizing(false);
    };

    window.addEventListener('pointermove', handlePointerMove);
    window.addEventListener('pointerup', handlePointerUp);
    window.addEventListener('pointercancel', handlePointerUp);

    return () => {
      window.removeEventListener('pointermove', handlePointerMove);
      window.removeEventListener('pointerup', handlePointerUp);
      window.removeEventListener('pointercancel', handlePointerUp);
    };
  }, [isTimelineResizing]);

  useEffect(() => {
    if (!isDetailsExpanded) {
      return;
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setIsDetailsExpanded(false);
      }
    };

    window.addEventListener('keydown', handleKeyDown);

    return () => {
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [isDetailsExpanded]);

  const handleTimelineResizerPointerDown = useCallback(
    (event: React.PointerEvent<HTMLDivElement>) => {
      if (!selectedEvent || !timelineBodyRef.current) {
        return;
      }

      event.preventDefault();
      event.stopPropagation();
      activeResizerPointerIdRef.current = event.pointerId;
      setIsTimelineResizing(true);
    },
    [selectedEvent]
  );

  const handleTimelineResizerKeyDown = useCallback(
    (event: React.KeyboardEvent<HTMLDivElement>) => {
      if (!selectedEvent) {
        return;
      }

      const adjust = (delta: number) => {
        setTimelineListWidthPercent(previous => clampTimelineSplit(previous + delta));
      };

      switch (event.key) {
        case 'ArrowLeft':
          event.preventDefault();
          adjust(-3);
          break;
        case 'ArrowRight':
          event.preventDefault();
          adjust(3);
          break;
        case 'Home':
          event.preventDefault();
          setTimelineListWidthPercent(TIMELINE_SPLIT_MIN);
          break;
        case 'End':
          event.preventDefault();
          setTimelineListWidthPercent(TIMELINE_SPLIT_MAX);
          break;
        default:
          break;
      }
    },
    [selectedEvent]
  );

  const handleTimelineResizerDoubleClick = useCallback(() => {
    if (!selectedEvent) {
      return;
    }

    setTimelineListWidthPercent(TIMELINE_SPLIT_DEFAULT);
  }, [selectedEvent]);

  const toggleDetailsExpanded = useCallback(() => {
    if (!selectedEvent) {
      return;
    }

    setIsDetailsExpanded(previous => !previous);
  }, [selectedEvent]);

  const closeExpandedDetails = useCallback(() => {
    setIsDetailsExpanded(false);
  }, []);

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

  const handleSelectEvent = useCallback((event: SignInEvent) => {
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
  }, []);

  const handleMapClick = useCallback(
    (event: MapLayerMouseEvent) => {
      const feature = event.features?.[0] as Feature<Point> | undefined;
      const featureId = (feature?.properties as { id?: string } | undefined)?.id;

      if (featureId === null || featureId === undefined) {
        return;
      }

      const eventId = String(featureId);
      const targetEvent = events.find(candidate => candidate.id === eventId);

      if (targetEvent) {
        handleSelectEvent(targetEvent);
        closeContextMenu();
      }
    },
    [closeContextMenu, events, handleSelectEvent]
  );

  const handleTimelineContextMenu = (
    event: React.MouseEvent<HTMLButtonElement, MouseEvent>,
    targetEvent: SignInEvent
  ) => {
    event.preventDefault();
    event.stopPropagation();
    openContextMenu(targetEvent.id, event.clientX, event.clientY, 'timeline');
  };

  const handleMapContextMenu = useCallback(
    (event: MapLayerMouseEvent) => {
      const originalEvent = event.originalEvent as MouseEvent | undefined;
      if (originalEvent) {
        originalEvent.preventDefault();
        originalEvent.stopPropagation();
      }

      const feature = event.features?.[0];
      const featureId = feature?.properties?.id;

      if (featureId === null || featureId === undefined) {
        closeContextMenu();
        return;
      }

      const clientX = originalEvent?.clientX ?? event.point.x;
      const clientY = originalEvent?.clientY ?? event.point.y;

      openContextMenu(String(featureId), clientX, clientY, 'map');
    },
    [closeContextMenu, openContextMenu]
  );

  const handleContextMenuDetails = useCallback(() => {
    if (!contextMenuEvent) {
      return;
    }

    handleSelectEvent(contextMenuEvent);
    closeContextMenu();
  }, [closeContextMenu, contextMenuEvent]);

  useEffect(() => {
    return () => {
      clearCopyStatusTimeout();
    };
  }, [clearCopyStatusTimeout]);

  useEffect(() => {
    clearCopyStatusTimeout();
    setRawCopyStatus('idle');
  }, [clearCopyStatusTimeout, selectedEventId]);

  const handleCopyRawEvent = useCallback(async () => {
    if (!selectedEventRawJson) {
      return;
    }

    clearCopyStatusTimeout();

    try {
      let didCopy = false;

      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(selectedEventRawJson);
        didCopy = true;
      } else {
        const textarea = document.createElement('textarea');
        textarea.value = selectedEventRawJson;
        textarea.setAttribute('readonly', '');
        textarea.style.position = 'absolute';
        textarea.style.left = '-9999px';
        document.body.appendChild(textarea);
        textarea.select();
        const successful = document.execCommand('copy');
        document.body.removeChild(textarea);
        didCopy = successful;
      }

      if (!didCopy) {
        throw new Error('Copy command was unsuccessful');
      }

      setRawCopyStatus('success');
    } catch {
      setRawCopyStatus('error');
    } finally {
      copyStatusTimeoutRef.current = setTimeout(() => {
        setRawCopyStatus('idle');
        copyStatusTimeoutRef.current = null;
      }, 2000);
    }
  }, [clearCopyStatusTimeout, selectedEventRawJson]);

  const detailsContent = useMemo(() => {
    if (!selectedEvent) {
      return null;
    }

    return (
      <>
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
            <span className="details-value">{(selectedEvent.raw['Application'] as string) || 'Unknown'}</span>
          </div>
          <div>
            <span className="details-label">Logon type</span>
            <span className="details-value">{(selectedEvent.raw['LogonType'] as string) || 'Unknown'}</span>
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
          <div className="raw-event-toolbar">
            <button
              type="button"
              className={`raw-event-copy-button${
                rawCopyStatus === 'success' ? ' success' : rawCopyStatus === 'error' ? ' error' : ''
              }`}
              onClick={handleCopyRawEvent}
            >
              {rawCopyStatus === 'success'
                ? 'Copied!'
                : rawCopyStatus === 'error'
                ? 'Copy failed'
                : 'Copy payload'}
            </button>
            {rawCopyStatus === 'error' && (
              <span className="raw-event-copy-feedback">Clipboard access unavailable</span>
            )}
          </div>
          <pre>{selectedEventRawJson}</pre>
        </details>
      </>
    );
  }, [handleCopyRawEvent, rawCopyStatus, selectedEvent, selectedEventRawJson]);

  const timelinePanelClassName = useMemo(() => {
    const classes = ['timeline-panel'];
    if (selectedEvent) {
      classes.push('has-details');
    }
    if (isDetailsExpanded) {
      classes.push('details-expanded');
    }
    if (isTimelineResizing) {
      classes.push('resizing');
    }
    return classes.join(' ');
  }, [isDetailsExpanded, isTimelineResizing, selectedEvent]);

  const timelineListStyle = useMemo(
    () => (selectedEvent ? { flexBasis: `${timelineListWidthPercent}%` } : undefined),
    [selectedEvent, timelineListWidthPercent]
  );

  const timelineDetailsStyle = useMemo(
    () => ({ flexBasis: `${100 - timelineListWidthPercent}%` }),
    [timelineListWidthPercent]
  );

  const resizerClassName = useMemo(
    () => `timeline-resizer${isTimelineResizing ? ' dragging' : ''}`,
    [isTimelineResizing]
  );

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
            // Try ip-api.com which supports CORS
            const response = await fetch(`http://ip-api.com/json/${encodeURIComponent(normalized)}`, {
              signal: controller.signal,
              mode: 'cors',
              headers: {
                'Accept': 'application/json'
              }
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

          if (payload?.status === 'success') {
            const labelParts = [payload.city, payload.regionName, payload.country]
              .map((part: string | undefined) => (typeof part === 'string' && part.trim() ? part.trim() : null))
              .filter(Boolean) as string[];
            const label = labelParts.length > 0 ? labelParts.join(', ') : payload.country || 'Unknown location';

            result = {
              ip: normalized,
              latitude: typeof payload.lat === 'number' ? payload.lat : undefined,
              longitude: typeof payload.lon === 'number' ? payload.lon : undefined,
              city: payload.city || undefined,
              region: payload.regionName || payload.region || undefined,
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
      setError('API authorization token missing. Save a backend token on the dashboard or sign in again.');
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
          Authorization: effectiveAuthToken,
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
      
      // Also load HIBP data alongside sign-ins
      fetchHibpData(targetUser);
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

        {/* Area 1: Alert banner for suspicious logins */}
        {/* Placeholder for future suspicious login alerts from API */}

        <form className="signin-controls" onSubmit={handleSubmit}>
          <div className={`token-status-banner ${effectiveAuthToken ? 'ready' : 'missing'}`}>
            {effectiveAuthToken
              ? isUsingBackendToken
                ? 'Using backend API token saved on the dashboard.'
                : 'Using Azure AD access token.'
              : 'No API token available. Save a backend token or sign in again to continue.'}
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

          {/* Area 4: Lookback dropdown with preset values */}
          <div className="input-group">
            <label htmlFor="signin-lookback">Lookback Window</label>
            <select
              id="signin-lookback"
              value={lookback}
              onChange={event => setLookback(event.target.value)}
              disabled={loading}
              className="lookback-select"
            >
              <option value="7d">7d (Last week)</option>
              <option value="30d">30d (Last month)</option>
              <option value="182d">182d (Last six months)</option>
              <option value="365d">365d (Last year)</option>
              <option value="custom">Custom</option>
            </select>
            {lookback === 'custom' && (
              <input
                id="signin-lookback-custom"
                type="text"
                value={lookback}
                onChange={event => setLookback(event.target.value)}
                placeholder="e.g., 14d"
                disabled={loading}
                className="lookback-custom-input"
              />
            )}
          </div>

          <div className="submit-button-wrapper">
            <button
              type="submit"
              className="submit-button"
              disabled={loading || !username.trim() || !effectiveAuthToken}
            >
              {loading ? 'Fetching…' : 'Load sign-ins'}
            </button>
          </div>
        </form>

        {/* Area 2: Action buttons */}
        <div className="action-buttons-wrapper">
          <div className="action-buttons-container expanded">
            <button className="action-button action-mfa" disabled={!selectedEvent}>
              Disable MFA
            </button>
            <button className="action-button action-email" disabled={!selectedEvent}>
              Alert Mail
            </button>
            <button className="action-button action-ad" disabled={!selectedEvent}>
              Disable in AD
            </button>
            <button className="action-button action-blacklist" disabled={!selectedEvent}>
              Blacklist on Network
            </button>
          </div>
        </div>

        <section className="signin-content">
          <div className={`globe-panel${selectedEvent && isDetailsExpanded ? ' details-overlay-active' : ''}`}>
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
              interactiveLayerIds={[LOCATION_LAYER_ID]}
              onClick={handleMapClick}
              onContextMenu={handleMapContextMenu}
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
                    closeButton={true}
                    closeOnClick={false}
                    onClose={() => setSelectedEventId(null)}
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
            {selectedEvent && isDetailsExpanded && (
              <div className="details-expanded-overlay" role="dialog" aria-modal="true">
                <div className="details-expanded-overlay__header">
                  <div className="details-expanded-overlay__titles">
                    <span className="details-expanded-overlay__title">Sign-in details</span>
                    <span className="details-expanded-overlay__subtitle">
                      {selectedEvent.displayLocation}
                      {' • '}
                      {formatTimestamp(selectedEvent.timestamp)}
                    </span>
                  </div>
                  <button
                    type="button"
                    className="details-expanded-overlay__close"
                    onClick={closeExpandedDetails}
                  >
                    Close expanded view
                  </button>
                </div>
                <div className="details-expanded-overlay__body">{detailsContent}</div>
              </div>
            )}
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

          <aside className={timelinePanelClassName}>
            {/* Area 3: Tabs for different data views */}
            <div className="data-tabs">
              <button 
                className={`tab-button ${activeTab === 'signin' ? 'active' : ''}`}
                onClick={() => setActiveTab('signin')}
              >
                Sign-in Locations
                <span className="tab-warning-badge">{events.filter((_, index) => index % 3 === 0).length}</span>
              </button>
              <button 
                className={`tab-button ${activeTab === 'hibp' ? 'active' : ''}`}
                onClick={() => {
                  setActiveTab('hibp');
                  if (activeUser) {
                    fetchHibpData(activeUser);
                  }
                }}
              >
                HaveIBeenPwned
                <span className="tab-warning-badge">{hibpData.length}</span>
              </button>
              <button 
                className={`tab-button ${activeTab === 'actions' ? 'active' : ''}`}
                onClick={() => setActiveTab('actions')}
              >
                Recommended Actions
              </button>
            </div>

            <div className="timeline-header">
              <div className="timeline-header-left">
                <h3>
                  {activeTab === 'signin' && 'Sign-ins'}
                  {activeTab === 'hibp' && 'Have I Been Pwned'}
                  {activeTab === 'actions' && 'Recommended Actions'}
                </h3>
                <span className="timeline-count">
                  {activeTab === 'signin' && events.length}
                  {activeTab === 'hibp' && hibpData.length}
                  {activeTab === 'actions' && '0'}
                </span>
              </div>
              {activeTab === 'signin' && (
                <label className="filter-warnings-checkbox">
                  <input type="checkbox" />
                  <span>Show warnings only</span>
                </label>
              )}
            </div>

            {/* Tab Content */}
            {activeTab === 'signin' && (
              <>
                {error && <div className="error-state">{error}</div>}
                {!error && !loading && events.length === 0 && (
                  <div className="empty-state">
                    Enter a user principal name and select "Load sign-ins" to review their activity.
                  </div>
                )}
                {loading && <div className="loading-indicator">Loading sign-ins…</div>}
              </>
            )}
            
            {activeTab === 'hibp' && (
              <>
                {hibpError && <div className="error-state">{hibpError}</div>}
                {!hibpError && !hibpLoading && hibpData.length === 0 && (
                  <div className="empty-state">
                    {activeUser ? 'No breaches found for this email address.' : 'Load sign-ins data first to check for breaches.'}
                  </div>
                )}
                {hibpLoading && <div className="loading-indicator">Checking Have I Been Pwned…</div>}
                <div className="timeline-body timeline-body--single">
                  <div className="timeline-list">
                    {hibpData.map((breach, index) => (
                      <div key={index} className="timeline-item">
                        <div className="event-location">{breach.Name}</div>
                        <div className="event-timestamp">Breach Date: {breach.BreachDate}</div>
                        <div className="event-meta">
                          Compromised: {breach.DataClasses?.join(', ') || 'Unknown'}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </>
            )}
            
            {activeTab === 'actions' && (
              <>
                <div className="empty-state">
                  Recommended actions will be displayed here based on sign-in analysis.
                </div>
              </>
            )}

            {activeTab === 'signin' && !error && !loading && events.length === 0 && (
              <div className="empty-state">
                Enter a user principal name and select “Load sign-ins” to review their activity.
              </div>
            )}

            {activeTab === 'signin' && loading && <div className="loading-indicator">Loading sign-ins…</div>}

            {activeTab === 'signin' && (
              <div
                className={`timeline-body${selectedEvent ? '' : ' timeline-body--single'}`}
                ref={timelineBodyRef}
              >
                <div className="timeline-list" style={timelineListStyle}>
                  {events.map((event, index) => {
                    // Placeholder: Mark every 3rd event as warning for demo purposes
                    // Replace this logic with actual API warning data
                    const isWarning = index % 3 === 0;
                    return (
                      <button
                        key={event.id}
                        onClick={() => handleSelectEvent(event)}
                        onContextMenu={mouseEvent => handleTimelineContextMenu(mouseEvent, event)}
                        className={`timeline-item${event.id === selectedEventId ? ' active' : ''}${isWarning ? ' warning' : ''}`}
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
                    );
                  })}
                </div>

                {selectedEvent && (
                  <>
                    <div
                      className={resizerClassName}
                      role="separator"
                      aria-orientation="vertical"
                      aria-label="Resize sign-in list and details"
                      aria-valuemin={TIMELINE_SPLIT_MIN}
                      aria-valuemax={TIMELINE_SPLIT_MAX}
                      aria-valuenow={Math.round(timelineListWidthPercent)}
                      tabIndex={0}
                      onPointerDown={handleTimelineResizerPointerDown}
                      onKeyDown={handleTimelineResizerKeyDown}
                      onDoubleClick={handleTimelineResizerDoubleClick}
                      title="Drag to resize the list and details. Double-click to reset."
                    />
                    <div className="timeline-details" style={timelineDetailsStyle}>
                      <div className="timeline-details__header">
                        <h4>Sign-in details</h4>
                        <button
                          type="button"
                          className={`timeline-details__expand-button${isDetailsExpanded ? ' active' : ''}`}
                          onClick={toggleDetailsExpanded}
                          aria-pressed={isDetailsExpanded}
                        >
                          {isDetailsExpanded ? 'Exit expanded view' : 'Expand view'}
                        </button>
                      </div>
                      <div className="timeline-details__body">{detailsContent}</div>
                    </div>
                  </>
                )}
              </div>
            )}
          </aside>
        </section>
        {contextMenuState && contextMenuEvent && (
          <div
            className="signin-context-menu"
            role="menu"
            style={{ left: `${contextMenuState.position.x}px`, top: `${contextMenuState.position.y}px` }}
          >
            <div className="signin-context-menu__meta" aria-hidden="true">
              <span className="signin-context-menu__location">{contextMenuEvent.displayLocation}</span>
              <span className="signin-context-menu__timestamp">
                {formatTimestamp(contextMenuEvent.timestamp)}
              </span>
            </div>
            <button type="button" onClick={handleContextMenuDetails} className="signin-context-menu__action">
              View details
            </button>
            <button type="button" onClick={closeContextMenu} className="signin-context-menu__dismiss">
              Cancel
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

export default UnfamiliarLoginPage;
