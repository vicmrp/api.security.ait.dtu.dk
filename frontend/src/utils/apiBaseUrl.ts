export const resolveApiBaseUrl = (): string => {
  const explicit = import.meta.env.VITE_API_BASE_URL;
  if (typeof explicit === 'string' && explicit.trim()) {
    return explicit.trim().replace(/\/$/, '');
  }

  if (typeof window !== 'undefined') {
    const { protocol, hostname, port } = window.location;
    if (hostname.includes('localhost')) {
      return 'http://localhost:6081';
    }

    let candidateHost = hostname;

    if (candidateHost.includes('-view.')) {
      candidateHost = candidateHost.replace('-view.', '-api.');
    } else if (candidateHost.startsWith('view.')) {
      candidateHost = candidateHost.replace('view.', 'api.');
    }

    const derivedOrigin = `${protocol}//${candidateHost}${port ? `:${port}` : ''}`;
    return derivedOrigin.replace(/\/$/, '');
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
