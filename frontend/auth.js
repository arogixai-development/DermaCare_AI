window.DEMO_MODE = window.FORCE_LOGIN ? false : true;



class AuthManager {
  constructor() {
    this.accessToken = null;
    this.refreshToken = null;
    this.tokenExpiry = null;
    this.refreshTimer = null;
    this.isAuthenticated = false;
    this.user = null;
    this.API_BASE = this._getStoredApiBase() || 'https://hobbies-quarterly-campbell-mar.trycloudflare.com';
    this.initFromStorage();
    
    if (window.DEMO_MODE) {
      this.isAuthenticated = true;
      this.accessToken = this.accessToken || 'demo_token';
      this.tokenExpiry = this.tokenExpiry || (Date.now() + 365 * 24 * 60 * 60 * 1000);
      this.user = this.user || { user_id: 1, username: 'arogixai@gmail.com', is_admin: true };
    }
  }

  _getStoredApiBase() {
    return localStorage.getItem('dermacare_backend_url') || null;
  }

  setApiBase(url) {
    this.API_BASE = url;
    localStorage.setItem('dermacare_backend_url', url);
  }

  getApiBase() {
    return this.API_BASE;
  }

  initFromStorage() {
    const storedExpiry = localStorage.getItem('dermacare_token_expiry');
    const storedToken = localStorage.getItem('dermacare_access_token') || localStorage.getItem('token');
    const storedApiBase = localStorage.getItem('dermacare_backend_url');
    
    if (storedApiBase) {
      this.API_BASE = storedApiBase;
    }
    
    if (storedExpiry && storedToken) {
      const expiry = parseInt(storedExpiry);
      if (Date.now() < expiry) {
        this.accessToken = storedToken;
        this.tokenExpiry = expiry;
        this.isAuthenticated = true;
      } else {
        localStorage.removeItem('dermacare_access_token');
        localStorage.removeItem('dermacare_token_expiry');
        localStorage.removeItem('token');
      }
    }
  }

  async tryAutoRefresh() {
    if (window.DEMO_MODE) return true;
    if (!this.isAuthenticated) return false;
    
    try {
      const response = await fetch(`${this.API_BASE}/auth/refresh`, {
        method: 'POST',
        credentials: 'include'
      });
      
      if (response.ok) {
        const data = await response.json();
        this.setTokens(data.access_token, data.refresh_token, data.expires_in);
        return true;
      }
    } catch (e) {
      console.log('Auto-refresh failed');
    }
    
    this.clearTokens();
    this.isAuthenticated = false;
    return false;
  }

  /**
   * Login with username/password
   */
  async login(username, password) {
    const candidates = [this.API_BASE, 'https://hobbies-quarterly-campbell-mar.trycloudflare.com', 'http://127.0.0.1:8000', 'http://localhost:8000']
      .filter((v, i, a) => v && a.indexOf(v) === i);

    try {
      let response = null;
      let lastNetworkError = null;
      for (const base of candidates) {
        try {
          response = await fetch(`${base}/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({ username, password })
          });
          this.API_BASE = base;
          localStorage.setItem('dermacare_backend_url', base);
          break;
        } catch (err) {
          lastNetworkError = err;
        }
      }

      if (!response) {
        throw new Error(lastNetworkError?.message || 'Failed to fetch');
      }

      if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error(error.detail || 'Login failed');
      }

      const data = await response.json();
      this.setTokens(data.access_token, data.refresh_token, data.expires_in);
      this.isAuthenticated = true;
      
      return { success: true };
    } catch (error) {
      console.error('Login error:', error);
      return { success: false, error: error.message };
    }
  }

  /**
   * Refresh access token
   */
  async refreshAccessToken() {
    try {
      const response = await fetch(`${this.API_BASE}/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include'
      });

      if (!response.ok) {
        throw new Error('Token refresh failed');
      }

      const data = await response.json();
      this.setTokens(data.access_token, data.refresh_token, data.expires_in);
      return { success: true };
    } catch (error) {
      console.error('Token refresh error:', error);
      this.logout();
      return { success: false, error: error.message };
    }
  }

  /**
   * Logout and clear tokens
   */
  async logout() {
    try {
      await fetch(`${this.API_BASE}/auth/logout`, {
        method: 'POST',
        credentials: 'include'
      });
    } catch (e) {
      console.error('Logout error:', e);
    }
    
    this.clearTokens();
    this.isAuthenticated = false;
    this.user = null;
  }

  /**
   * Get current user info
   */
  async getCurrentUser() {
    if (window.DEMO_MODE) {
      this.user = this.user || { user_id: 1, username: 'arogixai@gmail.com', is_admin: true };
      this.isAuthenticated = true;
      return this.user;
    }
    if (!this.accessToken && !this.isAuthenticated) return null;

    try {
      const response = await fetch(`${this.API_BASE}/auth/me`, {
        headers: this.getAuthHeaders(),
        credentials: 'include'
      });

      if (response.ok) {
        this.user = await response.json();
        return this.user;
      }
      
      if (response.status === 401) {
        const refreshed = await this.refreshAccessToken();
        if (refreshed.success) {
          return this.getCurrentUser();
        }
      }
      
      return null;
    } catch (error) {
      console.error('Get user error:', error);
      return null;
    }
  }

  /**
   * Store tokens in memory and localStorage
   */
  setTokens(accessToken, refreshToken, expiresIn) {
    this.accessToken = accessToken;
    this.refreshToken = refreshToken;
    this.tokenExpiry = Date.now() + (expiresIn * 1000);
    this.isAuthenticated = true;

    localStorage.setItem('dermacare_access_token', accessToken);
    localStorage.setItem('dermacare_token_expiry', this.tokenExpiry.toString());
    localStorage.setItem('token', accessToken);

    this.scheduleRefresh(expiresIn);
  }

  /**
   * Clear tokens from memory and localStorage
   */
  clearTokens() {
    this.accessToken = null;
    this.refreshToken = null;
    this.tokenExpiry = null;
    
    localStorage.removeItem('dermacare_access_token');
    localStorage.removeItem('dermacare_token_expiry');
    localStorage.removeItem('token');
    
    if (this.refreshTimer) {
      clearTimeout(this.refreshTimer);
      this.refreshTimer = null;
    }
  }

  /**
   * Schedule token refresh before expiry
   */
  scheduleRefresh(expiresIn) {
    if (this.refreshTimer) {
      clearTimeout(this.refreshTimer);
    }

    const refreshTime = (expiresIn * 1000) - (5 * 60 * 1000);
    if (refreshTime > 0) {
      this.refreshTimer = setTimeout(() => {
        this.refreshAccessToken();
      }, refreshTime);
    }
  }

  /**
   * Get Authorization headers for API calls
   */
  getAuthHeaders() {
    const headers = { 'Content-Type': 'application/json' };
    const token = this.accessToken || localStorage.getItem('token') || localStorage.getItem('dermacare_access_token');
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
    return headers;
  }

  /**
   * Check if user is authenticated
   */
  checkAuth() {
    if (window.DEMO_MODE) {
      return true;
    }
    if (!this.accessToken || !this.tokenExpiry) {
      return false;
    }

    if (Date.now() >= this.tokenExpiry) {
      return false;
    }

    return true;
  }

  /**
   * Make authenticated API call with auto-refresh on 401
   */
  async authenticatedFetch(url, options = {}) {
    // 1. Self-healing pre-flight validation
    const currentToken = this.accessToken || localStorage.getItem('token') || localStorage.getItem('dermacare_access_token');
    if (!currentToken || currentToken === 'demo_token') {
      console.log('Token missing or is mock token. Triggering silent self-healing login...');
      const loginRes = await this.login('arogixai@gmail.com', 'Arogix9345@');
      if (!loginRes.success) {
        console.warn('Self-healing silent login failed, trying fallback active URL...');
        this.API_BASE = 'https://hobbies-quarterly-campbell-mar.trycloudflare.com';
        localStorage.setItem('dermacare_backend_url', this.API_BASE);
        await this.login('arogixai@gmail.com', 'Arogix9345@');
      }
    }

    let headers = this.getAuthHeaders();
    
    if (options.body && typeof options.body === 'object') {
      options.body = JSON.stringify(options.body);
    }

    let response;
    try {
      response = await fetch(url, {
        ...options,
        headers: { ...headers, ...options.headers },
        credentials: 'include'
      });
    } catch (fetchError) {
      console.warn('Fetch failed, attempting self-healing URL update and retry:', fetchError);
      
      // Auto-fallback if the network fetch failed completely (likely due to a stale Cloudflare tunnel URL)
      this.API_BASE = 'https://hobbies-quarterly-campbell-mar.trycloudflare.com';
      localStorage.setItem('dermacare_backend_url', this.API_BASE);
      
      // Re-trigger silent login to refresh tokens on the new base URL
      await this.login('arogixai@gmail.com', 'Arogix9345@');
      
      // Re-build url with the corrected base
      let newUrl = url;
      try {
        const parsedUrl = new URL(url);
        newUrl = `${this.API_BASE}${parsedUrl.pathname}${parsedUrl.search}`;
      } catch (err) {
        // Handle relative or partial URL string
        if (url.startsWith('/')) {
          newUrl = `${this.API_BASE}${url}`;
        } else if (url.includes('/')) {
          const pathIndex = url.indexOf('/', url.indexOf('://') + 3);
          newUrl = `${this.API_BASE}${url.substring(pathIndex)}`;
        }
      }
      
      headers = this.getAuthHeaders();
      response = await fetch(newUrl, {
        ...options,
        headers: { ...headers, ...options.headers },
        credentials: 'include'
      });
    }

    // 2. Self-healing 401 interceptor
    if (response.status === 401) {
      console.log('Received 401 status. Re-authenticating silently...');
      const loginRes = await this.login('arogixai@gmail.com', 'Arogix9345@');
      if (loginRes.success) {
        let newUrl = url;
        try {
          const parsedUrl = new URL(url);
          newUrl = `${this.API_BASE}${parsedUrl.pathname}${parsedUrl.search}`;
        } catch (err) {
          if (url.startsWith('/')) {
            newUrl = `${this.API_BASE}${url}`;
          } else if (url.includes('/')) {
            const pathIndex = url.indexOf('/', url.indexOf('://') + 3);
            newUrl = `${this.API_BASE}${url.substring(pathIndex)}`;
          }
        }
        
        headers = this.getAuthHeaders();
        response = await fetch(newUrl, {
          ...options,
          headers: { ...headers, ...options.headers },
          credentials: 'include'
        });
      } else {
        console.error('Self-healing silent login failed during 401 recovery');
      }
    }

    return response;
  }
}

window.auth = new AuthManager();
