// API Testing Utility
// This utility helps test API endpoints using the authenticated access token

export interface ApiTestResult {
  success: boolean;
  status: number;
  message: string;
  data?: unknown;
  error?: string;
}

const DEFAULT_BASE_URL = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000').replace(/\/$/, '');

export class ApiTester {
  private accessToken: string;
  private baseUrl: string;

  constructor(accessToken: string, baseUrl: string = DEFAULT_BASE_URL) {
    this.accessToken = accessToken;
    this.baseUrl = baseUrl.replace(/\/$/, '');
  }

  private get authorizationHeader(): Record<string, string> {
    return {
      Authorization: `Bearer ${this.accessToken}`,
      'Content-Type': 'application/json',
    };
  }

  private getPreferredUsername(): string | null {
    try {
      const [, payload] = this.accessToken.split('.');
      if (!payload) {
        return null;
      }

      const decoded = JSON.parse(atob(payload.replace(/-/g, '+').replace(/_/g, '/')));
      return decoded.preferred_username || decoded.upn || decoded.email || null;
    } catch (error) {
      console.warn('Unable to read preferred username from token payload', error);
      return null;
    }
  }

  // Test basic API connectivity
  async testConnection(): Promise<ApiTestResult> {
    try {
      const response = await fetch(`${this.baseUrl}/healthz/`, {
        method: 'GET',
        headers: this.authorizationHeader,
      });

      const data = await response.json().catch(() => null);

      if (response.ok) {
        return {
          success: true,
          status: response.status,
          message: 'API connection successful',
          data,
        };
      }

      return {
        success: false,
        status: response.status,
        message: 'API connection failed',
        error: (data as Record<string, string> | null)?.message || response.statusText,
      };
    } catch (error: any) {
      console.error('API test failed:', error);
      return {
        success: false,
        status: 0,
        message: 'Network error',
        error: error?.message ?? 'Unknown error',
      };
    }
  }

  // Test Microsoft Graph proxy endpoint by requesting the current user
  async testUserProfile(): Promise<ApiTestResult> {
    const preferredUsername = this.getPreferredUsername();
    if (!preferredUsername) {
      return {
        success: false,
        status: 0,
        message: 'Unable to determine username from access token',
        error: 'Token payload missing preferred_username/upn/email claim',
      };
    }

    try {
      const encodedUser = encodeURIComponent(preferredUsername);
      const response = await fetch(`${this.baseUrl}/graph/v1.0/get-user/${encodedUser}`, {
        method: 'GET',
        headers: this.authorizationHeader,
      });

      const data = await response.json().catch(() => null);

      if (response.ok) {
        return {
          success: true,
          status: response.status,
          message: 'User profile retrieved successfully',
          data,
        };
      }

      return {
        success: false,
        status: response.status,
        message: 'Failed to retrieve user profile',
        error: (data as Record<string, string> | null)?.message || response.statusText,
      };
    } catch (error: any) {
      return {
        success: false,
        status: 0,
        message: 'Network error',
        error: error?.message ?? 'Unknown error',
      };
    }
  }

  // Run a comprehensive test suite
  async runTestSuite(): Promise<ApiTestResult[]> {
    const tests = [
      { name: 'Connection Test', test: () => this.testConnection() },
      { name: 'User Profile Test', test: () => this.testUserProfile() },
    ];

    const results: ApiTestResult[] = [];

    for (const test of tests) {
      // eslint-disable-next-line no-await-in-loop
      const result = await test.test();
      results.push(result);
      // eslint-disable-next-line no-await-in-loop
      await new Promise((resolve) => setTimeout(resolve, 500));
    }

    return results;
  }
}
