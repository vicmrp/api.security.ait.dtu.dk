// Reset MFA Modal Component
// Interface for resetting user's multi-factor authentication

import React, { useState } from 'react';
import './ResetMFAModal.css';

interface ResetMFAModalProps {
  onClose: () => void;
  accessToken: string | null;
}

const ResetMFAModal: React.FC<ResetMFAModalProps> = ({ onClose, accessToken }) => {
  const [username, setUsername] = useState<string>('');
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [message, setMessage] = useState<string>('');
  const [messageType, setMessageType] = useState<'success' | 'error' | ''>('');

  const handleResetMFA = async () => {
    if (!username.trim()) {
      setMessage('Please enter a username');
      setMessageType('error');
      return;
    }

    if (!accessToken) {
      setMessage('No access token available');
      setMessageType('error');
      return;
    }

    setIsLoading(true);
    setMessage('');

    try {
      console.log('🔄 Resetting MFA for user:', username);
      
      const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000').replace(/\/$/, '');
      const response = await fetch(`${apiBaseUrl}/api/auth/reset-mfa`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${accessToken}`,
        },
        body: JSON.stringify({ username: username.trim() }),
      });

      if (response.ok) {
        setMessage(`MFA reset successfully for user: ${username}`);
        setMessageType('success');
        setUsername('');
      } else {
        const error = await response.text();
        setMessage(`Failed to reset MFA: ${error}`);
        setMessageType('error');
      }
    } catch (error) {
      console.error('❌ MFA reset failed:', error);
      setMessage('Network error - please try again later');
      setMessageType('error');
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !isLoading) {
      handleResetMFA();
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>🔐 Reset MFA</h2>
          <button className="close-button" onClick={onClose}>✕</button>
        </div>

        <div className="modal-body">
          <p className="modal-description">
            Reset multi-factor authentication for a user account. 
            This will require the user to set up MFA again on their next login.
          </p>

          <div className="input-group">
            <label htmlFor="username">Username</label>
            <input
              id="username"
              type="text"
              placeholder="Enter username (e.g., user@dtu.dk)"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              onKeyPress={handleKeyPress}
              disabled={isLoading}
              autoFocus
            />
          </div>

          {message && (
            <div className={`message ${messageType}`}>
              {message}
            </div>
          )}

          <div className="modal-actions">
            <button 
              className="btn-secondary" 
              onClick={onClose}
              disabled={isLoading}
            >
              Cancel
            </button>
            <button 
              className="btn-primary" 
              onClick={handleResetMFA}
              disabled={isLoading || !username.trim()}
            >
              {isLoading ? 'Resetting...' : 'Reset MFA'}
            </button>
          </div>

          <div className="api-status">
            <small>
              <strong>Note:</strong> This feature requires API endpoint implementation. 
              The backend API should handle <code>POST /auth/reset-mfa</code> with Azure AD token validation.
            </small>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ResetMFAModal;