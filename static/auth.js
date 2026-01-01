/**
 * Starscreen Authentication Utility
 *
 * Handles JWT token storage, retrieval, and automatic injection into API requests.
 *
 * Usage:
 *   - Auth.login(accessToken, refreshToken) - Store tokens after login/register
 *   - Auth.logout() - Clear tokens and redirect to login
 *   - Auth.isAuthenticated() - Check if user is logged in
 *   - Auth.getAccessToken() - Get current access token
 *   - Auth.getAuthHeaders() - Get Authorization header object for fetch()
 */

const Auth = {
    // Storage keys
    ACCESS_TOKEN_KEY: 'starscreen_access_token',
    REFRESH_TOKEN_KEY: 'starscreen_refresh_token',
    USER_KEY: 'starscreen_user',

    /**
     * Store authentication tokens after successful login/register
     */
    login(accessToken, refreshToken, user = null) {
        localStorage.setItem(this.ACCESS_TOKEN_KEY, accessToken);
        localStorage.setItem(this.REFRESH_TOKEN_KEY, refreshToken);

        if (user) {
            localStorage.setItem(this.USER_KEY, JSON.stringify(user));
        }

        console.log('[Auth] User logged in successfully');
    },

    /**
     * Clear all authentication data and redirect to login
     */
    logout() {
        localStorage.removeItem(this.ACCESS_TOKEN_KEY);
        localStorage.removeItem(this.REFRESH_TOKEN_KEY);
        localStorage.removeItem(this.USER_KEY);

        console.log('[Auth] User logged out');

        // Redirect to login page (only if not already there)
        if (!window.location.pathname.includes('login.html') &&
            !window.location.pathname.includes('register.html')) {
            window.location.href = '/static/login.html';
        }
    },

    /**
     * Check if user is authenticated (has valid access token)
     */
    isAuthenticated() {
        const token = localStorage.getItem(this.ACCESS_TOKEN_KEY);

        if (!token) {
            return false;
        }

        // Optional: Check if token is expired (JWT tokens have 'exp' field)
        try {
            const payload = this.parseJWT(token);
            const now = Math.floor(Date.now() / 1000);

            if (payload.exp && payload.exp < now) {
                console.log('[Auth] Token expired');
                return false;
            }

            return true;
        } catch (e) {
            console.error('[Auth] Invalid token:', e);
            return false;
        }
    },

    /**
     * Get the current access token
     */
    getAccessToken() {
        return localStorage.getItem(this.ACCESS_TOKEN_KEY);
    },

    /**
     * Get the refresh token
     */
    getRefreshToken() {
        return localStorage.getItem(this.REFRESH_TOKEN_KEY);
    },

    /**
     * Get stored user data
     */
    getUser() {
        const userJson = localStorage.getItem(this.USER_KEY);
        return userJson ? JSON.parse(userJson) : null;
    },

    /**
     * Get Authorization headers for API requests
     *
     * Usage:
     *   fetch('/api/v1/jobs', {
     *     headers: Auth.getAuthHeaders()
     *   })
     */
    getAuthHeaders() {
        const token = this.getAccessToken();

        if (!token) {
            return {};
        }

        return {
            'Authorization': `Bearer ${token}`
        };
    },

    /**
     * Refresh the access token using the refresh token
     */
    async refreshAccessToken() {
        const refreshToken = this.getRefreshToken();

        if (!refreshToken) {
            console.error('[Auth] No refresh token available');
            this.logout();
            return null;
        }

        try {
            const response = await fetch('/api/v1/auth/refresh', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    refresh_token: refreshToken
                })
            });

            if (!response.ok) {
                throw new Error('Token refresh failed');
            }

            const data = await response.json();

            // Update access token (refresh token stays the same)
            localStorage.setItem(this.ACCESS_TOKEN_KEY, data.access_token);

            console.log('[Auth] Access token refreshed successfully');
            return data.access_token;

        } catch (error) {
            console.error('[Auth] Failed to refresh token:', error);
            this.logout();
            return null;
        }
    },

    /**
     * Parse JWT token to extract payload (without validation)
     * WARNING: This does NOT validate the signature! Only use for reading claims.
     */
    parseJWT(token) {
        try {
            const base64Url = token.split('.')[1];
            const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
            const jsonPayload = decodeURIComponent(atob(base64).split('').map(function(c) {
                return '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2);
            }).join(''));

            return JSON.parse(jsonPayload);
        } catch (e) {
            throw new Error('Invalid JWT token');
        }
    },

    /**
     * Fetch wrapper that automatically includes auth headers and handles 401 errors
     *
     * Usage (replaces regular fetch):
     *   const data = await Auth.fetch('/api/v1/jobs');
     */
    async fetch(url, options = {}) {
        // Add auth headers
        const headers = {
            ...options.headers,
            ...this.getAuthHeaders()
        };

        const response = await fetch(url, {
            ...options,
            headers
        });

        // Handle 401 Unauthorized - try to refresh token once
        if (response.status === 401 && !options._tokenRefreshAttempted) {
            console.log('[Auth] Received 401, attempting token refresh...');

            const newToken = await this.refreshAccessToken();

            if (newToken) {
                // Retry the request with new token
                return this.fetch(url, {
                    ...options,
                    _tokenRefreshAttempted: true // Prevent infinite loop
                });
            } else {
                // Refresh failed, logout user
                this.logout();
                throw new Error('Authentication expired. Please log in again.');
            }
        }

        return response;
    }
};

/**
 * Initialize authentication on page load
 * Protects pages that require login
 */
document.addEventListener('DOMContentLoaded', function() {
    // List of pages that DON'T require authentication
    const publicPages = ['login.html', 'register.html', 'pricing.html', 'checkout.html'];

    const currentPage = window.location.pathname.split('/').pop();
    const isPublicPage = publicPages.some(page => currentPage.includes(page));

    // If not on a public page and not authenticated, redirect to login
    if (!isPublicPage && !Auth.isAuthenticated()) {
        console.log('[Auth] Unauthenticated user detected, redirecting to login');
        window.location.href = '/static/login.html';
    }
});

// Export for use in modules (if needed)
if (typeof module !== 'undefined' && module.exports) {
    module.exports = Auth;
}
