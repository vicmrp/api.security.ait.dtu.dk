// Clear MSAL Cache Utility
// This helps clear all MSAL-related storage when configuration changes

export const clearMsalCache = () => {
  try {
    console.log('🧹 Clearing MSAL cache and storage...');
    
    // Clear session storage (where MSAL stores tokens)
    sessionStorage.clear();
    
    // Clear local storage (where we store API keys)
    localStorage.clear();
    
    // Clear any MSAL-specific storage keys
    const msalKeys = [
      'msal.account.keys',
      'msal.token.keys.account',
      'msal.error',
      'msal.cache',
    ];
    
    msalKeys.forEach(key => {
      sessionStorage.removeItem(key);
      localStorage.removeItem(key);
    });
    
    // Clear cookies related to Microsoft
    document.cookie.split(";").forEach(cookie => {
      const eqPos = cookie.indexOf("=");
      const name = eqPos > -1 ? cookie.substr(0, eqPos) : cookie;
      if (name.trim().includes('msal') || name.trim().includes('microsoft')) {
        document.cookie = name + "=;expires=Thu, 01 Jan 1970 00:00:00 GMT;path=/";
      }
    });
    
    console.log('✅ MSAL cache cleared successfully');
    console.log('🔄 Please refresh the page to complete the reset');
    
    return true;
  } catch (error) {
    console.error('❌ Error clearing MSAL cache:', error);
    return false;
  }
};

// Call this function to clear everything
// clearMsalCache();