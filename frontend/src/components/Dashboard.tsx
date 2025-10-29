// Dashboard Component - Clean and Simple
// Simple interface for API Security tools using Azure AD authentication

import React, { useState, useEffect } from 'react';
import { useAuth } from '../hooks/useAuth';
import ApiTestPage from './ApiTestPage';
import ResetMFAModal from './ResetMFAModal';
import UnfamiliarLoginPage from './UnfamiliarLoginPage';
import './Dashboard.css';

const BACKEND_API_TOKEN_KEY = 'myview.backendApiToken';

const Dashboard: React.FC = () => {
  // Use our custom authentication hook
  const { user, logout, isLoading, getAccessToken } = useAuth();

  // State management
  const [showApiTestPage, setShowApiTestPage] = useState<boolean>(false);
  const [showUnfamiliarLogin, setShowUnfamiliarLogin] = useState<boolean>(false);
  const [showMFAModal, setShowMFAModal] = useState<boolean>(false);
  const [authStatus, setAuthStatus] = useState<'ready' | 'checking' | 'expired'>('checking');
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [backendApiToken, setBackendApiToken] = useState<string | null>(null);
  const [tokenInput, setTokenInput] = useState('');
  const [isTokenVisible, setIsTokenVisible] = useState(false);
  const [tokenFeedback, setTokenFeedback] = useState<string | null>(null);

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

  useEffect(() => {
    if (typeof window === 'undefined') {
      return;
    }
    const storedToken = window.localStorage.getItem(BACKEND_API_TOKEN_KEY);
    if (storedToken) {
      setBackendApiToken(storedToken);
      setTokenInput(storedToken);
    }
  }, []);

  const persistBackendToken = (token: string | null) => {
    if (typeof window === 'undefined') {
      return;
    }
    if (token) {
      window.localStorage.setItem(BACKEND_API_TOKEN_KEY, token);
    } else {
      window.localStorage.removeItem(BACKEND_API_TOKEN_KEY);
    }
  };

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

  const handleTokenSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const trimmed = tokenInput.trim();
    if (trimmed) {
      persistBackendToken(trimmed);
      setBackendApiToken(trimmed);
      setTokenFeedback('Token saved to this browser.');
    } else {
      persistBackendToken(null);
      setBackendApiToken(null);
      setTokenFeedback('Token cleared.');
    }
  };

  const handleTokenClear = () => {
    setTokenInput('');
    persistBackendToken(null);
    setBackendApiToken(null);
    setTokenFeedback('Token cleared.');
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
            <h3>Backend API Token</h3>
            <span className={`token-status-pill ${backendApiToken ? 'token-status-pill--ready' : 'token-status-pill--missing'}`}>
              {backendApiToken ? 'Saved locally' : 'Not saved'}
            </span>
          </div>
          <p className="token-section-hint">
            Paste the API token from the admin frontpage. It stays in this browser&apos;s local storage only.
          </p>
          <form className="token-form" onSubmit={handleTokenSubmit}>
            <div className="token-input-row">
              <input
                type={isTokenVisible ? 'text' : 'password'}
                className="token-input"
                value={tokenInput}
                onChange={event => {
                  setTokenInput(event.target.value);
                  if (tokenFeedback) {
                    setTokenFeedback(null);
                  }
                }}
                placeholder="Enter backend API token"
                autoComplete="off"
                spellCheck={false}
              />
              <button
                type="button"
                className="token-toggle"
                onClick={() => setIsTokenVisible(visible => !visible)}
                aria-label={isTokenVisible ? 'Hide token' : 'Show token'}
              >
                {isTokenVisible ? 'Hide' : 'Show'}
              </button>
            </div>
            <div className="token-actions">
              <button type="submit" className="token-button primary">
                Save token
              </button>
              <button
                type="button"
                className="token-button secondary"
                onClick={handleTokenClear}
                disabled={!backendApiToken && !tokenInput}
              >
                Clear
              </button>
            </div>
          </form>
          {backendApiToken && (
            <div className="token-preview">
              <span className="token-preview-label">Preview:</span>
              <span className="token-preview-value">
                {backendApiToken.length > 12
                  ? `${backendApiToken.slice(0, 6)}…${backendApiToken.slice(-6)}`
                  : backendApiToken}
              </span>
              <span className="token-preview-length">({backendApiToken.length} chars)</span>
            </div>
          )}
          {tokenFeedback && <div className="token-feedback">{tokenFeedback}</div>}
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
          backendApiToken={backendApiToken}
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
