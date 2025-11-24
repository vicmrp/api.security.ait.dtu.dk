// Enhanced Custom React hook for MSAL authentication
// This hook manages all the authentication logic with proper error handling and token management

import { useState, useEffect, useCallback } from 'react';
import { useMsal } from '@azure/msal-react';
import { AccountInfo, InteractionStatus, AuthenticationResult } from '@azure/msal-browser';
import { loginRequest, logoutRequest } from '../config/msalConfig';
import { AuthContextType } from '../types/auth';

export const useAuth = (): AuthContextType => {
  // Get MSAL instance and accounts from the MSAL React hook
  const { instance, accounts, inProgress } = useMsal();
  
  // Local state for our authentication
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
  const [user, setUser] = useState<AccountInfo | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [loginInProgress, setLoginInProgress] = useState<boolean>(false);

  // Check if token is expired with proper MSAL methods
  const isTokenExpired = useCallback(async (account: AccountInfo): Promise<boolean> => {
    if (!account) return true;
    
    try {
      console.log('🔍 Checking token expiration for:', account.username);
      
      // Import API scope from config
      const { apiRequest } = await import('../config/msalConfig');
      
      // Try to get a token silently - this will fail if token is expired
      const silentRequest = {
        scopes: apiRequest.scopes, // Use API scope
        account: account,
        forceRefresh: false, // Don't force refresh, just check cache
      };

      // This will throw an error if token is expired or invalid
      const result = await instance.acquireTokenSilent(silentRequest);
      
      if (result && result.accessToken) {
        console.log('✅ Token is valid');
        return false; // Token is NOT expired
      } else {
        console.log('⚠️ No valid token found');
        return true; // Token IS expired
      }
      
    } catch (error: any) {
      console.log('❌ Token check failed:', error.message);
      
      // Check specific error types
      if (error.message?.includes('interaction_required') || 
          error.message?.includes('token_expired') ||
          error.message?.includes('no_tokens_found')) {
        console.log('🔄 Token is expired or missing');
        return true; // Token IS expired
      }
      
      // For other errors, assume token is expired to be safe
      console.log('⚠️ Unknown error, assuming token expired');
      return true;
    }
  }, [instance]);

  // Silent token refresh
  const refreshTokenSilently = useCallback(async (account: AccountInfo): Promise<boolean> => {
    try {
      console.log('🔄 Refreshing token silently...');
      
      // Import API scope from config
      const { apiRequest } = await import('../config/msalConfig');
      
      const silentRequest = {
        scopes: apiRequest.scopes, // Use API scope
        account: account,
        forceRefresh: false, // Try cache first
      };

      await instance.acquireTokenSilent(silentRequest);
      console.log('✅ Token refreshed successfully');
      return true;
    } catch (error) {
      console.error('❌ Silent token refresh failed:', error);
      return false;
    }
  }, [instance]);

  // Effect to check authentication state and manage tokens
  useEffect(() => {
    const checkAuthState = async () => {
      try {
        // Wait for MSAL to finish initialization
        if (inProgress !== InteractionStatus.None) {
          return; // Still processing
        }

        console.log('🔍 Checking authentication state...');
        console.log('📊 Accounts found:', accounts.length);

        if (accounts.length > 0) {
          const account = accounts[0];
          console.log('👤 Account found:', account.username);

          // Check if token is expired
          const tokenExpired = await isTokenExpired(account);
          
          if (tokenExpired) {
            console.log('⚠️ Token is expired, attempting refresh...');
            
            const refreshSuccess = await refreshTokenSilently(account);
            
            if (!refreshSuccess) {
              // If silent refresh fails, user needs to re-authenticate
              console.log('🚫 Token refresh failed, clearing authentication');
              setIsAuthenticated(false);
              setUser(null);
              setError('Session expired. Please sign in again.');
              setIsLoading(false);
              return;
            }
          }

          // Authentication successful
          setIsAuthenticated(true);
          setUser(account);
          setError(null);
          console.log('✅ User authenticated successfully');
        } else {
          // No accounts found
          console.log('❌ No authenticated accounts found');
          setIsAuthenticated(false);
          setUser(null);
          setError(null);
        }
      } catch (error) {
        console.error('💥 Error in auth state check:', error);
        setError('Authentication check failed');
        setIsAuthenticated(false);
        setUser(null);
      } finally {
        setIsLoading(false);
      }
    };

    checkAuthState();
  }, [accounts, inProgress, isTokenExpired, refreshTokenSilently]);

  // Login function with enhanced error handling
  const login = async (): Promise<void> => {
    try {
      // Prevent multiple login attempts
      if (loginInProgress || inProgress !== InteractionStatus.None) {
        console.log('⏳ Login already in progress, skipping...');
        return;
      }

      // Check if user is already authenticated
      if (accounts.length > 0 && isAuthenticated) {
        console.log('✅ User already authenticated');
        return;
      }

      console.log('🚀 Starting login process...');
      setLoginInProgress(true);
      setIsLoading(true);
      setError(null);

      // Create timeout promise
      const timeoutPromise = new Promise<never>((_, reject) => {
        setTimeout(() => {
          reject(new Error('Login timeout - please try again'));
        }, 30000); // 30 seconds timeout
      });

      // Race between login and timeout
      const loginPromise = instance.loginPopup(loginRequest);
      
      console.log('🔑 Opening login popup...');
      const response: AuthenticationResult = await Promise.race([
        loginPromise,
        timeoutPromise
      ]);

      console.log('✅ Login successful:', response.account?.username);

      // Update state after successful login
      if (response.account) {
        setIsAuthenticated(true);
        setUser(response.account);
        setError(null);
      } else {
        throw new Error('No account information received');
      }

    } catch (error: any) {
      console.error('❌ Login failed:', error);
      
      // Handle specific error types
      let errorMessage = 'Login failed. Please try again.';
      
      if (error.message?.includes('timeout')) {
        errorMessage = 'Login timed out. Please check your connection and try again.';
      } else if (error.message?.includes('user_cancelled')) {
        errorMessage = 'Login was cancelled.';
      } else if (error.message?.includes('invalid_client')) {
        errorMessage = 'Invalid client configuration. Please contact support.';
      } else if (error.message?.includes('network')) {
        errorMessage = 'Network error. Please check your connection.';
      }

      setError(errorMessage);
      setIsAuthenticated(false);
      setUser(null);
    } finally {
      setIsLoading(false);
      setLoginInProgress(false);
    }
  };

  // Logout function with cleanup
  const logout = async (): Promise<void> => {
    try {
      console.log('🚪 Starting logout process...');
      setIsLoading(true);
      setError(null);
      
      // Use logout popup for better UX
      await instance.logoutPopup(logoutRequest);
      
      // Clear local state
      setIsAuthenticated(false);
      setUser(null);
      setError(null);
      
      console.log('✅ Logout successful');
    } catch (error: any) {
      console.error('❌ Logout failed:', error);
      setError('Logout failed. Please try again.');
      
      // Even if logout fails, clear local state
      setIsAuthenticated(false);
      setUser(null);
    } finally {
      setIsLoading(false);
    }
  };

  // Get access token for API calls
  const getAccessToken = useCallback(async (): Promise<string | null> => {
    if (!isAuthenticated || !user) {
      return null;
    }

    try {
      
      // Import API scope from config
      const { apiRequest } = await import('../config/msalConfig');
      
      const silentRequest = {
        scopes: apiRequest.scopes, // Use API scope instead of User.Read
        account: user,
        forceRefresh: false,
      };

      const result = await instance.acquireTokenSilent(silentRequest);
      
      if (result && result.accessToken) {
        return result.accessToken;
      } else {
        return null;
      }
      
    } catch (error: any) {
      console.error('❌ Failed to get access token:', error);
      
      // If silent token acquisition fails, user might need to re-authenticate
      if (error.message?.includes('interaction_required')) {
        setError('Session expired. Please sign in again.');
        setIsAuthenticated(false);
        setUser(null);
      }
      
      return null;
    }
  }, [instance, isAuthenticated, user]);

  // Return the authentication state and functions
  return {
    isAuthenticated,
    user,
    isLoading,
    error,
    login,
    logout,
    getAccessToken,
  };
};