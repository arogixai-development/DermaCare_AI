/**
 * Auth Module - DermaCare AI Frontend
 * JWT token management with memory storage and auto-refresh
 */

class AuthManager {
  constructor() {
    this.accessToken = null;
    this.refreshToken = null;
    this.tokenExpiry = null;
    this.refreshTimer = null;
    this.isAuthenticated = false;
    this.user = null;
    this.API_BASE = this._getStoredApiBase() || 'https://dermacare-ai-f3rr.onrender.com';
    this.initFromStorage();
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
    const storedToken = localStorage.getItem('dermacare_access_token');
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
      }
    }
  }

  async tryAutoRefresh() {
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
    try {
      const response = await fetch(`${this.API_BASE}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ username, password })
      });

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
    if (this.accessToken) {
      headers['Authorization'] = `Bearer ${this.accessToken}`;
    }
    return headers;
  }

  /**
   * Check if user is authenticated
   */
  checkAuth() {
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
    const headers = this.getAuthHeaders();
    
    if (options.body && typeof options.body === 'object') {
      options.body = JSON.stringify(options.body);
    }

    let response = await fetch(url, {
      ...options,
      headers: { ...headers, ...options.headers },
      credentials: 'include'
    });

    if (response.status === 401 && this.refreshToken) {
      const refreshed = await this.refreshAccessToken();
      
      if (refreshed.success) {
        response = await fetch(url, {
          ...options,
          headers: this.getAuthHeaders(),
          credentials: 'include'
        });
      } else {
        window.auth.showLoginScreen();
        throw new Error('Authentication required');
      }
    }

    return response;
  }
}

window.auth = new AuthManager();
