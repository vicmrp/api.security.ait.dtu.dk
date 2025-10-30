// Dashboard Component - Clean and Simple
// Simple interface for API Security tools using Azure AD authentication

import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../hooks/useAuth';
import ApiTestPage from './ApiTestPage';
import ResetMFAModal from './ResetMFAModal';
import UnfamiliarLoginPage from './UnfamiliarLoginPage';
import './Dashboard.css';
import { buildBearerToken, resolveApiBaseUrl } from '../utils/apiBaseUrl';

const Dashboard: React.FC = () => {
  // Use our custom authentication hook
  const { user, logout, isLoading, getAccessToken } = useAuth();

  // State management
  const [showApiTestPage, setShowApiTestPage] = useState<boolean>(false);
  const [showUnfamiliarLogin, setShowUnfamiliarLogin] = useState<boolean>(false);
  const [showMFAModal, setShowMFAModal] = useState<boolean>(false);
  const [authStatus, setAuthStatus] = useState<'ready' | 'checking' | 'expired'>('checking');
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [apiToken, setApiToken] = useState<string | null>(null);
  const [isApiTokenVisible, setIsApiTokenVisible] = useState(false);
  const [isFetchingApiToken, setIsFetchingApiToken] = useState(false);
  const [isRotatingApiToken, setIsRotatingApiToken] = useState(false);
  const [apiTokenFeedback, setApiTokenFeedback] = useState<
    { message: string; tone: 'success' | 'error' | 'info' } | null
  >(null);

  // Check authentication status when component mounts
  useEffect(() => {
    const checkAuthStatus = async () => {
      if (user) {
        setAuthStatus('checking');
        try {
          const token = await getAccessToken();
          if (token) {
            setAuthStatus('ready');
            setAccessToken(token);
          } else {
            setAuthStatus('expired');
          }
        } catch (error) {
          console.error('❌ Failed to get access token:', error);
          setAuthStatus('expired');
        }
      }
    };

    checkAuthStatus();
  }, [user, getAccessToken]);

  // Handlers
  const handleSignOut = async () => {
    try {
      await logout();
    } catch (error) {
      console.error('Sign out failed:', error);
    }
  };

  const handleTestApi = () => {
    if (authStatus !== 'ready') {
      alert('Authentication not ready. Please wait or try signing in again.');
      return;
    }
    setShowApiTestPage(true);
  };

  const handleUnfamiliarLogin = () => {
    if (authStatus !== 'ready') {
      alert('Authentication not ready. Please wait or try signing in again.');
      return;
    }
    setShowUnfamiliarLogin(true);
  };

  const ensureAccessToken = useCallback(async (): Promise<string | null> => {
    try {
      const freshToken = await getAccessToken();
      if (freshToken) {
        setAccessToken(freshToken);
        return freshToken;
      }
    } catch (error) {
      console.error('❌ Failed to refresh access token:', error);
    }

    if (accessToken) {
      return accessToken;
    }

    return null;
  }, [accessToken, getAccessToken]);

  const handleFetchApiToken = useCallback(async () => {
    setApiTokenFeedback(null);

    const activeAccessToken = await ensureAccessToken();
    if (!activeAccessToken) {
      setApiToken(null);
      setApiTokenFeedback({
        message: 'No access token available. Please sign in again.',
        tone: 'error'
      });
      return;
    }

    setIsFetchingApiToken(true);
    try {
      const baseUrl = resolveApiBaseUrl();
      const response = await fetch(`${baseUrl}/myview/api/token/`, {
        method: 'GET',
        headers: {
          Authorization: buildBearerToken(activeAccessToken),
          Accept: 'application/json'
        },
        credentials: 'include'
      });

      if (!response.ok) {
        const message = await response.text();
        throw new Error(message || `Request failed with status ${response.status}`);
      }

      const payload = (await response.json()) as { api_token?: string | null };
      const token = payload?.api_token ?? null;

      if (token) {
        setApiToken(token);
        setApiTokenFeedback({ message: 'API token loaded.', tone: 'success' });
      } else {
        setApiToken(null);
        setApiTokenFeedback({
          message: 'No API token found for your account.',
          tone: 'info'
        });
      }
    } catch (error) {
      console.error('❌ Failed to load API token:', error);
      setApiTokenFeedback({
        message: 'Failed to load API token. Please try again.',
        tone: 'error'
      });
    } finally {
      setIsFetchingApiToken(false);
    }
  }, [ensureAccessToken]);

  const handleRotateApiToken = useCallback(async () => {
    setApiTokenFeedback(null);

    const confirmed = window.confirm(
      'Rotating your API token will immediately invalidate the previous token. Do you want to continue?'
    );

    if (!confirmed) {
      return;
    }

    const activeAccessToken = await ensureAccessToken();
    if (!activeAccessToken) {
      setApiTokenFeedback({
        message: 'No access token available. Please sign in again.',
        tone: 'error'
      });
      return;
    }

    setIsRotatingApiToken(true);
    try {
      const baseUrl = resolveApiBaseUrl();
      const response = await fetch(`${baseUrl}/myview/api/token/rotate/`, {
        method: 'POST',
        headers: {
          Authorization: buildBearerToken(activeAccessToken),
          Accept: 'application/json'
        },
        credentials: 'include'
      });

      if (!response.ok) {
        const message = await response.text();
        throw new Error(message || `Request failed with status ${response.status}`);
      }

      const payload = (await response.json()) as { api_token?: string | null };
      const token = payload?.api_token ?? null;
      setApiToken(token);
      setApiTokenFeedback({
        message: 'API token rotated successfully.',
        tone: 'success'
      });
    } catch (error) {
      console.error('❌ Failed to rotate API token:', error);
      setApiTokenFeedback({
        message: 'Failed to rotate API token. Please try again.',
        tone: 'error'
      });
    } finally {
      setIsRotatingApiToken(false);
    }
  }, [ensureAccessToken]);

  const handleToggleApiTokenVisibility = () => {
    setIsApiTokenVisible(visible => !visible);
  };

  const handleMFAReset = () => {
    setShowMFAModal(true);
  };

  const handleViewDocs = () => {
    // Pass token as parameter for automatic authentication
    if (accessToken) {
      const swaggerUrl = `https://api.security.ait.dtu.dk/myview/swagger/?access_token=${encodeURIComponent(accessToken)}`;
      window.open(swaggerUrl, '_blank');
    } else {
      window.open('https://api.security.ait.dtu.dk/myview/swagger/', '_blank');
    }
  };

  const handleShowToken = () => {
    if (accessToken) {
      // Show a formatted preview without logging the full token
      const preview = `${accessToken.substring(0, 20)}...${accessToken.substring(accessToken.length - 20)}`;
      alert(`Access token (${accessToken.length} chars):\n${preview}\n\nToken available for API calls`);
    } else {
      alert('No access token available');
    }
  };

  useEffect(() => {
    if (authStatus === 'ready') {
      handleFetchApiToken();
    }
  }, [authStatus, handleFetchApiToken]);

  const isApiTokenBusy = isFetchingApiToken || isRotatingApiToken;
  const apiTokenStatusClass = isApiTokenBusy
    ? 'token-status-pill--loading'
    : apiToken
      ? 'token-status-pill--ready'
      : 'token-status-pill--missing';
  const apiTokenStatusText = isRotatingApiToken
    ? 'Rotating…'
    : isFetchingApiToken
      ? 'Loading…'
      : apiToken
        ? 'Ready'
        : 'Not loaded';

  return (
    <div className="dashboard-container">
      {/* Animated background */}
      <div className="dashboard-bg"></div>
      
      {/* Header with user info */}
      <div className="dashboard-header">
        <div className="header-content">
          <h1>API Security AIT DTU</h1>
          <div className="user-section">
            <div className="user-avatar">
              {user?.name?.charAt(0) || user?.username?.charAt(0) || 'U'}
            </div>
            <div className="user-details">
              <span className="user-name">{user?.name || user?.username || 'User'}</span>
              <span className="user-email">{user?.username || 'No email available'}</span>
            </div>
            <button 
              className="sign-out-btn" 
              onClick={handleSignOut}
              disabled={isLoading}
            >
              {isLoading ? '...' : '🚪'}
            </button>
          </div>
        </div>
      </div>
      
      {/* Main content */}
      <div className="dashboard-main">
        <div className="welcome-section">
          <div className="shield-animation">
            <div className="shield">🛡️</div>
          </div>
          <h2>Velkommen {user?.name || user?.username || 'User'}!</h2>
          <p>Authenticated with Azure AD - Ready for secure API access</p>
        </div>

        <section className="token-section">
          <div className="token-section-header">
            <h3>API Token</h3>
            <span className={`token-status-pill ${apiTokenStatusClass}`}>
              {apiTokenStatusText}
            </span>
          </div>
          <p className="token-section-hint">
            Use this token in the Authorization header as <code>Token &lt;key&gt;</code> when calling the API. The token is fetched
            using your Azure AD sign-in and is never stored in your browser.
          </p>
          <div className="token-input-row">
            <input
              type={isApiTokenVisible ? 'text' : 'password'}
              className="token-input"
              value={apiToken ?? ''}
              readOnly
              placeholder={isApiTokenBusy ? 'Loading API token…' : 'Load API token to display'}
              autoComplete="off"
              spellCheck={false}
            />
            <button
              type="button"
              className="token-toggle"
              onClick={handleToggleApiTokenVisibility}
              aria-label={isApiTokenVisible ? 'Hide API token' : 'Show API token'}
              disabled={!apiToken}
            >
              {isApiTokenVisible ? 'Hide' : 'Show'}
            </button>
          </div>
          <div className="token-actions">
            <button
              type="button"
              className="token-button primary"
              onClick={handleFetchApiToken}
              disabled={isFetchingApiToken}
            >
              {isFetchingApiToken ? 'Loading…' : 'Refresh token'}
            </button>
            <button
              type="button"
              className="token-button danger"
              onClick={handleRotateApiToken}
              disabled={isApiTokenBusy}
            >
              {isRotatingApiToken ? 'Rotating…' : 'Rotate token'}
            </button>
          </div>
          {apiToken && (
            <div className="token-preview">
              <span className="token-preview-label">Length:</span>
              <span className="token-preview-length">{apiToken.length} chars</span>
            </div>
          )}
          {apiTokenFeedback && (
            <div className={`token-feedback token-feedback--${apiTokenFeedback.tone}`}>
              {apiTokenFeedback.message}
            </div>
          )}
        </section>

        {/* Action Cards Section */}
        <div className="actions-section">
          <h3 className="section-title">Security Tools</h3>
          
          <div className="cards-grid">
            {/* API Documentation Card */}
            <div className="card" onClick={handleViewDocs}>
              <div className="card-icon">📋</div>
              <h3>API Documentation</h3>
              <p>Browse complete API documentation and examples</p>
            </div>

            {/* Check Unfamiliar Login Card */}
            <div className={`card ${authStatus !== 'ready' ? 'disabled' : ''}`} onClick={handleUnfamiliarLogin}>
              <div className="card-icon">🔍</div>
              <h3>Check Unfamiliar<br />Login</h3>
              <p>View login locations and diagnosed unfamiliar sign-ins</p>
            </div>

            {/* Breach Check Card */}
            <div className={`card ${authStatus !== 'ready' ? 'disabled' : ''}`} onClick={handleTestApi}>
              <div className="card-icon">⚠️</div>
              <h3>Breach Check</h3>
              <p>Search for breached accounts and security incidents</p>
            </div>

            {/* MFA Reset Card */}
            <div className="card" onClick={handleMFAReset}>
              <div className="card-icon">🔐</div>
              <h3>MFA Reset</h3>
              <p>Reset multi-factor authentication for users</p>
            </div>

            {/* Access Token Card */}
            <div className="card" onClick={handleShowToken}>
              <div className="card-icon">🎫</div>
              <h3>Access Token</h3>
              <p>View current Azure AD access token</p>
            </div>
          </div>
        </div>
      </div>
      
      {/* API Test Page Modal */}
      {showApiTestPage && (
        <ApiTestPage
          accessToken={accessToken}
          onClose={() => setShowApiTestPage(false)}
        />
      )}

      {/* Unfamiliar Login Page Modal */}
      {showUnfamiliarLogin && (
        <UnfamiliarLoginPage
          accessToken={accessToken}
          onClose={() => setShowUnfamiliarLogin(false)}
        />
      )}

      {/* MFA Reset Modal */}
      {showMFAModal && (
        <ResetMFAModal
          accessToken={accessToken}
          onClose={() => setShowMFAModal(false)}
        />
      )}
    </div>
  );
};

export default Dashboard;
