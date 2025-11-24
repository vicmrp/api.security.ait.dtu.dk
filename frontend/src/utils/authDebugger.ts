// Authentication debugging and cache clearing utilities

export const clearAllAuthenticationData = () => {
  console.log('🧹 Clearing all authentication data...');
  
  // Clear all localStorage
  const keysToRemove = [];
  for (let i = 0; i < localStorage.length; i++) {
    const key = localStorage.key(i);
    if (key?.includes('msal') || key?.includes('microsoft') || key?.includes('auth')) {
      keysToRemove.push(key);
    }
  }
  keysToRemove.forEach(key => localStorage.removeItem(key));
  
  // Clear all sessionStorage
  const sessionKeysToRemove = [];
  for (let i = 0; i < sessionStorage.length; i++) {
    const key = sessionStorage.key(i);
    if (key?.includes('msal') || key?.includes('microsoft') || key?.includes('auth')) {
      sessionKeysToRemove.push(key);
    }
  }
  sessionKeysToRemove.forEach(key => sessionStorage.removeItem(key));
  
  console.log(`✅ Cleared ${keysToRemove.length} localStorage items and ${sessionKeysToRemove.length} sessionStorage items`);
};

export const debugAuthenticationState = () => {
  console.log('🔍 Authentication Debug Information:');
  console.log('📍 Current URL:', window.location.href);
  console.log('🌐 Current Port:', window.location.port);
  
  console.log('💾 LocalStorage MSAL entries:');
  for (let i = 0; i < localStorage.length; i++) {
    const key = localStorage.key(i);
    if (key?.includes('msal')) {
      console.log(`  ${key}:`, localStorage.getItem(key));
    }
  }
  
  console.log('🗂️ SessionStorage MSAL entries:');
  for (let i = 0; i < sessionStorage.length; i++) {
    const key = sessionStorage.key(i);
    if (key?.includes('msal')) {
      console.log(`  ${key}:`, sessionStorage.getItem(key));
    }
  }
};

export const validateRedirectURI = () => {
  const currentURL = `${window.location.protocol}//${window.location.host}`;
  const expectedURL = 'http://localhost:3030';
  
  console.log('🔗 Redirect URI Validation:');
  console.log('📍 Current URL:', currentURL);
  console.log('✅ Expected URL:', expectedURL);
  console.log('✔️ Match:', currentURL === expectedURL ? 'YES' : 'NO');
  
  if (currentURL !== expectedURL) {
    console.warn('⚠️ URL mismatch detected! This may cause authentication issues.');
    console.warn('💡 Make sure your Azure app registration has the correct redirect URI.');
  }
  
  return currentURL === expectedURL;
};