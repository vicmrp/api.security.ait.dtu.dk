// MSAL Configuration for Microsoft Authentication
// This file sets up the configuration for Microsoft Authentication Library

import { Configuration, PopupRequest, LogLevel } from '@azure/msal-browser';

// MSAL configuration object
export const msalConfig: Configuration = {
  auth: {
    // Client ID from your Azure App Registration
    clientId: import.meta.env.VITE_MSAL_CLIENT_ID || 'your_client_id_here',
    
    // Authority URL - DTU specific
    authority: import.meta.env.VITE_MSAL_AUTHORITY || 'https://login.microsoftonline.com/dtu.dk',
    
    // Redirect URI - where users are sent after authentication
    redirectUri: import.meta.env.VITE_MSAL_REDIRECT_URI || 'http://localhost:3030',
    
    // Post logout redirect URI
    postLogoutRedirectUri: import.meta.env.VITE_MSAL_POST_LOGOUT_REDIRECT_URI || 'http://localhost:3030',
    
    // Navigation to login page when unauthenticated
    navigateToLoginRequestUrl: false,
    
    // Additional security settings
    knownAuthorities: ['login.microsoftonline.com'],
  },
  cache: {
    // Where to store tokens (sessionStorage is more secure for single-tab apps)
    cacheLocation: 'sessionStorage',
    
    // Set to true to store auth state in cookies (helps with IE/Edge issues)
    storeAuthStateInCookie: false,
    
    // Secure cache settings
    secureCookies: true,
  },
  system: {
    // Enable logging for debugging
    loggerOptions: {
      loggerCallback: (level, message, containsPii) => {
        if (containsPii) {
          return;
        }
        switch (level) {
          case LogLevel.Error:
            console.error('MSAL Error:', message);
            return;
          case LogLevel.Info:
            console.info('MSAL Info:', message);
            return;
          case LogLevel.Verbose:
            console.debug('MSAL Verbose:', message);
            return;
          case LogLevel.Warning:
            console.warn('MSAL Warning:', message);
            return;
          default:
            return;
        }
      },
    },
    // Set popup timeout to prevent hanging
    windowHashTimeout: 20000, // 20 seconds
    iframeHashTimeout: 10000,  // 10 seconds
    loadFrameTimeout: 10000,   // 10 seconds
  },
};

// Simple API scope configuration (like your .NET Core setup)
const apiClientId = import.meta.env.VITE_API_CLIENT_ID;
const apiScope = apiClientId ? `api://${apiClientId}/access_as_user` : 'User.Read';

// Scopes for login request - what permissions we're asking for
export const loginRequest: PopupRequest = {
  scopes: [apiScope], // Request scope for your Django API
  prompt: 'select_account', // Always show account selection
  
  // Additional popup configuration - center the popup
  popupWindowAttributes: {
    popupSize: {
      height: 700,
      width: 600,
    },
    popupPosition: {
      top: Math.max(0, (window.screen.height - 700) / 2),
      left: Math.max(0, (window.screen.width - 600) / 2),
    },
  },
};

// Export the API scope for token requests
export const apiRequest = {
  scopes: [apiScope],
};

// Configuration for logout
export const logoutRequest = {
  postLogoutRedirectUri: import.meta.env.VITE_MSAL_POST_LOGOUT_REDIRECT_URI || 'http://localhost:3030',
};