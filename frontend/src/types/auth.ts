// TypeScript types for authentication
// This helps us write better, type-safe code

import { AccountInfo } from '@azure/msal-browser';

// Type for user account information
export interface UserAccount extends AccountInfo {
  // Add any additional properties you might need
}

// Type for authentication state
export interface AuthState {
  isAuthenticated: boolean;
  user: UserAccount | null;
  isLoading: boolean;
  error: string | null;
}

// Type for login/logout functions
export interface AuthContextType {
  // Authentication state
  isAuthenticated: boolean;
  user: UserAccount | null;
  isLoading: boolean;
  error: string | null;
  
  // Authentication functions
  login: () => Promise<void>;
  logout: () => Promise<void>;
  getAccessToken: () => Promise<string | null>;
}