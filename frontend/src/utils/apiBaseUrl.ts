export const resolveApiBaseUrl = (): string => {
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

export const buildBearerToken = (token: string): string => {
  const trimmed = token.trim();
  if (/^Bearer\s+/i.test(trimmed)) {
    return trimmed;
  }
  return `Bearer ${trimmed}`;
};
