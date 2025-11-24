// Login Component
// This component shows the login page with a sign-in button

import React, { useEffect } from 'react';
import { useAuth } from '../hooks/useAuth';
import { clearMsalCache } from '../utils/clearCache';
import { clearAllAuthenticationData, debugAuthenticationState, validateRedirectURI } from '../utils/authDebugger';
import './LoginPage.css';

const LoginPage: React.FC = () => {
  // Use our custom authentication hook
  const { login, isLoading, error } = useAuth();

  // Debug authentication state on component mount
  useEffect(() => {
    debugAuthenticationState();
    validateRedirectURI();
  }, []);

  // Handle sign-in button click
  const handleSignIn = async () => {
    try {
      await login();
    } catch (error) {
      console.error('Sign in failed:', error);
    }
  };

  // Handle clearing cache with enhanced debugging
  const handleClearCache = () => {
    if (window.confirm('Clear all authentication cache? This will sign you out and reset everything.')) {
      clearMsalCache();
      clearAllAuthenticationData();
      window.location.reload();
    }
  };

  return (
    <div className="login-container">
      <div className="login-card">
        {/* Application Title */}
        <div className="login-header">
          <h1>Welcome to API Security AIT DTU</h1>
          <p>Please sign in to access the application</p>
        </div>

        {/* Sign In Button */}
        <div className="login-actions">
          <button 
            className="sign-in-btn" 
            onClick={handleSignIn}
            disabled={isLoading}
          >
            {isLoading ? (
              <span className="loading-spinner">Signing in...</span>
            ) : (
              <>
                <svg className="microsoft-icon" viewBox="0 0 23 23">
                  <path fill="#f35325" d="M1 1h10v10H1z"/>
                  <path fill="#81bc06" d="M12 1h10v10H12z"/>
                  <path fill="#05a6f0" d="M1 12h10v10H1z"/>
                  <path fill="#ffba08" d="M12 12h10v10H12z"/>
                </svg>
                Sign in with Microsoft
              </>
            )}
          </button>
        </div>

        {/* Error Message */}
        {error && (
          <div className="error-message">
            <p>{error}</p>
          </div>
        )}

        {/* Privacy Notice */}
        <div className="privacy-notice">
          <p>
            By logging in, you agree to our{' '}
            <a href="#" className="privacy-link">Privacy Policy</a>, where
            we explain how we collect your username and user 
            groups to control your access rights.
          </p>
        </div>

        {/* Debug Section - Only show if there are errors */}
        {error && (
          <div className="debug-section">
            <h4>🔧 Troubleshooting</h4>
            <p>If you're having login issues, try clearing the cache:</p>
            <button 
              className="debug-btn"
              onClick={handleClearCache}
            >
              Clear Authentication Cache
            </button>
            <div className="debug-info">
              <p><strong>Current Config:</strong></p>
              <p>Client ID: {import.meta.env.VITE_MSAL_CLIENT_ID?.substring(0, 8)}...</p>
              <p>Authority: {import.meta.env.VITE_MSAL_AUTHORITY}</p>
              <p>Redirect URI: {import.meta.env.VITE_MSAL_REDIRECT_URI}</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default LoginPage;