// API Testing Page Component - Azure AD Only
// Clean interface for testing breached account endpoint with Azure AD authentication

import React, { useState } from 'react';
import './ApiTestPage.css';

interface ApiTestPageProps {
  accessToken?: string | null;
  onClose: () => void;
}

interface ApiResponse {
  success: boolean;
  data?: any;
  error?: string;
}

const ApiTestPage: React.FC<ApiTestPageProps> = ({ accessToken, onClose }) => {
  const [email, setEmail] = useState('');
  const [response, setResponse] = useState<ApiResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const validateEmail = (email: string): boolean => {
    // DTU domain validation
    const dtuPattern = /^[a-zA-Z0-9._%+-]+@dtu\.dk$/;
    return dtuPattern.test(email);
  };

  const executeApiCall = async () => {
    if (!accessToken) {
      setResponse({ success: false, error: 'Please login first to get an access token.' });
      return;
    }

    if (!email.trim()) {
      setResponse({ success: false, error: 'Please enter an email address.' });
      return;
    }

    if (!validateEmail(email)) {
      setResponse({ success: false, error: 'Please enter a valid @dtu.dk email address.' });
      return;
    }

    setIsLoading(true);
    setResponse(null);

    try {
      const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000').replace(/\/$/, '');
      const fullUrl = `${apiBaseUrl}/hibp/v3/breachedaccount/${encodeURIComponent(email)}`;
      
      console.log('Calling API endpoint:', fullUrl);
      
      const response = await fetch(fullUrl, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${accessToken}`,
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`HTTP ${response.status}: ${errorText || response.statusText}`);
      }

      const data = await response.json();
      setResponse({ success: true, data });
    } catch (error) {
      console.error('API Call Error:', error);
      setResponse({ 
        success: false, 
        error: error instanceof Error ? error.message : 'Unknown error occurred'
      });
    } finally {
      setIsLoading(false);
    }
  };

  const renderResponse = () => {
    if (!response) return null;

    if (!response.success) {
      return (
        <div className="response error">
          <h4>Error</h4>
          <p>{response.error}</p>
        </div>
      );
    }

    return (
      <div className="response success">
        <h4>Response</h4>
        <pre>{JSON.stringify(response.data, null, 2)}</pre>
      </div>
    );
  };

  return (
    <div className="api-test-overlay" onClick={onClose}>
      <div className="api-test-container" onClick={(e) => e.stopPropagation()}>
        <div className="api-test-header">
          <h2>Breach Check API Test</h2>
          <button onClick={onClose} className="close-button">×</button>
        </div>

        <div className="status-section">
          <div className="status-info">
            <span>Status: {accessToken ? 'Azure AD Token Available' : 'Please login first'}</span>
          </div>
        </div>

        <div className="api-form">
          <div className="form-group">
            <label htmlFor="email">Email Address (@dtu.dk):</label>
            <input
              type="email"
              id="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="Enter DTU email address"
              disabled={isLoading}
            />
          </div>

          <button 
            onClick={executeApiCall}
            disabled={isLoading || !accessToken}
            className="test-button"
          >
            {isLoading ? 'Checking...' : 'Check Email'}
          </button>
        </div>

        {renderResponse()}
      </div>
    </div>
  );
};

export default ApiTestPage;