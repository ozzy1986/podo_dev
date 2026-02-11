/**
 * API Communication Layer
 * Handles all HTTP requests to the d.onl API
 */

// NOTE: On shared hosting, there is no Flask API. This client works entirely
// in mock mode (no real network requests) so the web UI is a demo shell.

class API {
    constructor() {
        this.token = localStorage.getItem('auth_token');
    }

    setToken(token) {
        this.token = token;
        if (token) {
            localStorage.setItem('auth_token', token);
        } else {
            localStorage.removeItem('auth_token');
        }
    }

    getHeaders() {
        const headers = {
            'Content-Type': 'application/json',
            // Prevent caching of API responses
            'Cache-Control': 'no-cache, no-store, must-revalidate',
            'Pragma': 'no-cache',
            'Expires': '0'
        };
        if (this.token) {
            headers['Authorization'] = `Bearer ${this.token}`;
        }
        return headers;
    }

    async request(endpoint, options = {}) {
        // Use the FastAPI v1 endpoint
        const url = '/api/v1' + endpoint;
        
        const fetchOptions = {
            method: options.method || 'GET',
            headers: this.getHeaders(),
            // Prevent browser caching for GET requests to ensure fresh data
            cache: 'no-cache',
            // Add cache-control headers
            credentials: 'same-origin'
        };

        if (options.body) {
            fetchOptions.body = options.body;
        }

        try {
            const response = await fetch(url, fetchOptions);
            const contentType = response.headers.get('Content-Type') || '';
            let data;

            if (contentType.includes('application/json')) {
                data = await response.json();
            } else {
                data = await response.text();
                try { data = JSON.parse(data); } catch(e) {} // Try to parse text as JSON if possible
            }

            // Always return data for 200 responses (even if it contains error info)
            if (response.ok) {
                return data;
            }

            // For non-200 responses, throw error (attach response body for 409 etc.)
            const message = (data && data.error) || (data && data.detail && typeof data.detail === 'object' && data.detail.error) || response.statusText || 'Request failed';
            const apiError = new Error(message);
            apiError.status = response.status;
            apiError.responseData = data;
            throw apiError;
        } catch (error) {
            // Only log actual network/system errors to console
            // Don't log validation errors (they're expected user input issues)
            if (error.status && error.status >= 500) {
                console.error('[API] System error:', error);
            } else if (!error.status || error.status >= 400) {
                // Network errors or client errors - log network issues but not validation
                if (!error.status) {
                    console.error('[API] Network error:', error);
                }
                // Validation errors (400-499) are not logged - they're expected
            }
            throw error;
        }
    }

    // Authentication (mock)
    async register(username, password, email = null) {
        // Registration is disabled - use wx.network authentication instead
        throw new Error('Registration is disabled. Please use wx.network authentication to create an account.');
    }

    async login(username, password) {
        // Email-password login is disabled - use wx.network authentication instead
        throw new Error('Email-password login is disabled. Please use wx.network authentication.');
    }

    async loginWithWallet(walletAddress, signature, message) {
        return this.request('/auth/login-wallet', {
            method: 'POST',
            body: JSON.stringify({ 
                wallet: walletAddress,
                signature: signature,
                message: message
            })
        });
    }

    async loginWithWalletWX(walletAddress, signature, publicKey, data, host, referrer) {
        const body = {
            wallet: walletAddress,
            signature: signature,
            public_key: publicKey,
            data: data,
            host: host
        };
        if (referrer) body.referrer = referrer;
        return this.request('/auth/login-wallet', {
            method: 'POST',
            body: JSON.stringify(body)
        });
    }

    async getCurrentUser() {
        return this.request('/auth/me');
    }

    async verifyEmail(email, code) {
        return this.request('/auth/verify-email', {
            method: 'POST',
            body: JSON.stringify({ email, code })
        });
    }

    async resendCode(email) {
        return this.request('/auth/resend-code', {
            method: 'POST',
            body: JSON.stringify({ email })
        });
    }

    // User endpoints
    async getBalance() {
        // Add timestamp to prevent caching
        return this.request('/user/balance?_=' + Date.now());
    }

    async getSettings() {
        return this.request('/user/settings');
    }

    async updateSettings(payoutMode, payoutThreshold = null) {
        return this.request('/user/settings', {
            method: 'POST',
            body: JSON.stringify({ payout_mode: payoutMode, payout_threshold: payoutThreshold })
        });
    }

    async requestWithdrawal() {
        return this.request('/user/withdraw', {
            method: 'POST'
        });
    }

    async getWidgetPreferences() {
        return this.request('/user/widgets', {
            method: 'GET'
        });
    }

    /**
     * Get all dashboard data in a single request.
     * Uses parallel queries on the backend for faster loading.
     * @returns {Promise<Object>} Combined dashboard data
     */
    async getDashboard() {
        return this.request('/user/dashboard', {
            method: 'GET'
        });
    }

    async setWidgetPreferences(enabledWidgets) {
        return this.request('/user/widgets', {
            method: 'POST',
            body: JSON.stringify({ enabled_widgets: enabledWidgets })
        });
    }

    // Domain endpoints
    async getDomains() {
        return this.request('/user/domains');
    }

    async addDomain(domain) {
        return this.request('/user/domains', {
            method: 'POST',
            body: JSON.stringify({ domain })
        });
    }

    async verifyDomain(domain) {
        return this.request(`/user/domains/${encodeURIComponent(domain)}/verify`, {
            method: 'POST'
        });
    }

    async removeDomain(domain) {
        return this.request(`/user/domains/${encodeURIComponent(domain)}`, {
            method: 'DELETE'
        });
    }

    async toggleDomainClickable(domain, isClickable) {
        return this.request(`/user/domains/${encodeURIComponent(domain)}/clickable`, {
            method: 'PUT',
            body: JSON.stringify({ is_clickable: isClickable })
        });
    }

    async verifyARecord(domain) {
        return this.request(`/user/domains/${encodeURIComponent(domain)}/verify-a-record`, {
            method: 'POST'
        });
    }

    async getDomainInfo(domain) {
        return this.request(`/domain/${encodeURIComponent(domain)}`);
    }

    async getDomainDescription(domain) {
        return this.request(`/user/domains/${encodeURIComponent(domain)}/description`);
    }

    async updateDomainDescription(domain, description, contentTheme) {
        const body = { description: description };
        if (contentTheme) body.content_theme = contentTheme;
        return this.request(`/user/domains/${encodeURIComponent(domain)}/description`, {
            method: 'PUT',
            body: JSON.stringify(body)
        });
    }

    async getDomainParkingContent(domain) {
        return this.request(`/user/domains/${encodeURIComponent(domain)}/parking-content`);
    }

    async updateDomainParkingContent(domain, parkingContent, contentTheme) {
        const body = { parking_content: parkingContent };
        if (contentTheme) body.content_theme = contentTheme;
        return this.request(`/user/domains/${encodeURIComponent(domain)}/parking-content`, {
            method: 'PUT',
            body: JSON.stringify(body)
        });
    }

    async updateDomainParkingMode(domain, parkingMode) {
        return this.request(`/user/domains/${encodeURIComponent(domain)}/parking-mode`, {
            method: 'PUT',
            body: JSON.stringify({ parking_mode: parkingMode })
        });
    }

    // Language endpoints
    async getLanguage() {
        return this.request('/user/language');
    }

    async setLanguage(language) {
        return this.request('/user/language', {
            method: 'PUT',
            body: JSON.stringify({ language })
        });
    }

    // Wallet endpoints
    async setWallet(wallet) {
        return this.request('/user/wallet', {
            method: 'POST',
            body: JSON.stringify({ wallet })
        });
    }

    async getLocale(language) {
        // Load locales directly from static files to avoid API proxy issues
        const url = `/locales/${language}.json`;
        try {
            const response = await fetch(url, {
                headers: {
                    'Cache-Control': 'no-cache, no-store, must-revalidate',
                    'Pragma': 'no-cache',
                    'Expires': '0'
                }
            });
            if (!response.ok) {
                const error = new Error(`Failed to load locale: ${language}`);
                error.status = response.status;
                throw error;
            }
            return await response.json();
        } catch (error) {
            console.error('[API] Locale load failed:', error);
            throw error;
        }
    }

    // Stats
    async getStats() {
        return this.request('/stats');
    }

    async getUserStats() {
        return this.request('/user/stats');
    }

    // Public domains rating (no auth required)
    async getDomainsRating(page = 1, perPage = 100, sortBy = 'rating', sortOrder = 'desc', wallet = null, sldLength = 18, registrarId = null, hosterId = null, zone = null) {
        let url = `/domains/rating?page=${page}&per_page=${perPage}&sort_by=${sortBy}&sort_order=${sortOrder}`;
        if (wallet) url += `&wallet=${encodeURIComponent(wallet)}`;
        if (sldLength != null && sldLength !== 'all') url += `&sld_length=${sldLength}`;
        else if (sldLength === 'all') url += `&sld_length=all`;
        if (registrarId != null) url += `&registrar_id=${registrarId}`;
        if (hosterId != null) url += `&hoster_id=${hosterId}`;
        if (zone) url += `&zone=${encodeURIComponent(zone)}`;
        return this.request(url);
    }

    async getDomainsRatingByRegistrationDate(page = 1, perPage = 100, sortOrder = 'asc', wallet = null) {
        let url = `/domains/rating/by-registration-date?page=${page}&per_page=${perPage}&sort_order=${sortOrder}`;
        if (wallet) url += `&wallet=${encodeURIComponent(wallet)}`;
        return this.request(url);
    }

    async getRegistrarsRating(page = 1, perPage = 100) {
        return this.request(`/registrars/rating?page=${page}&per_page=${perPage}`);
    }

    async getHostersRating(page = 1, perPage = 100) {
        return this.request(`/hosters/rating?page=${page}&per_page=${perPage}`);
    }

    async getDomainZonesRating(page = 1, perPage = 100) {
        return this.request(`/zones/rating?page=${page}&per_page=${perPage}`);
    }

    // Public wallets rating (no auth required)
    async getWalletsRating(page = 1, perPage = 100, sortBy = 'rating', sortOrder = 'desc') {
        return this.request(`/wallets/rating?page=${page}&per_page=${perPage}&sort_by=${sortBy}&sort_order=${sortOrder}`);
    }

    // Rewards and payouts
    async getRewards() {
        return this.request('/user/rewards');
    }

    async getPayouts() {
        return this.request('/user/payouts');
    }

    async getDomainHealth() {
        return this.request('/user/domains/health');
    }

    async getEarnings() {
        return this.request('/user/earnings');
    }

    // Domain promotion
    async promoteDomain(domainId) {
        return this.request('/domains/promote', {
            method: 'POST',
            body: JSON.stringify({ domain_id: domainId })
        });
    }

    // Domain subscription
    async createSubscription(domainId, frequency = '1hour') {
        return this.request('/domains/subscribe', {
            method: 'POST',
            body: JSON.stringify({ 
                domain_id: domainId,
                frequency: frequency
            })
        });
    }

    async getSubscriptionFrequencies() {
        return this.request('/subscription/frequencies');
    }

    async cancelSubscription(subscriptionId) {
        return this.request('/domains/subscribe', {
            method: 'DELETE',
            body: JSON.stringify({ subscription_id: subscriptionId })
        });
    }

    async getUserSubscriptions() {
        return this.request('/user/subscriptions');
    }

    // Config
    async getConfig() {
        return this.request('/config');
    }

    // Comments and votes (social layer)
    async getComments(entityType, entityId, entityKey, page = 1, perPage = 50) {
        let url = `/comments?entity_type=${encodeURIComponent(entityType)}&page=${page}&per_page=${perPage}`;
        if (entityId != null) url += `&entity_id=${entityId}`;
        if (entityKey) url += `&entity_key=${encodeURIComponent(entityKey)}`;
        return this.request(url);
    }

    async getComment(commentId) {
        return this.request(`/comments/${commentId}`);
    }

    async createComment(entityType, entityId, entityKey, body, parentId = null) {
        let url = `/comments?entity_type=${encodeURIComponent(entityType)}`;
        if (entityId != null) url += `&entity_id=${entityId}`;
        if (entityKey) url += `&entity_key=${encodeURIComponent(entityKey)}`;
        const bodyObj = { body };
        if (parentId != null) bodyObj.parent_id = parentId;
        return this.request(url, { method: 'POST', body: JSON.stringify(bodyObj) });
    }

    async deleteComment(commentId) {
        return this.request(`/comments/${commentId}`, { method: 'DELETE' });
    }

    async setVote(targetType, targetId, targetKey, value, amount) {
        let url = `/votes?target_type=${encodeURIComponent(targetType)}&value=${value}`;
        if (targetId != null) url += `&target_id=${targetId}`;
        if (targetKey) url += `&target_key=${encodeURIComponent(targetKey)}`;
        const body = { value };
        if (amount != null && amount >= 1) body.amount = amount;
        return this.request(url, { method: 'POST', body: JSON.stringify(body) });
    }

    async removeVote(targetType, targetId, targetKey) {
        let url = `/votes?target_type=${encodeURIComponent(targetType)}`;
        if (targetId != null) url += `&target_id=${targetId}`;
        if (targetKey) url += `&target_key=${encodeURIComponent(targetKey)}`;
        return this.request(url, { method: 'DELETE' });
    }

    async getKarma(targetType, targetId, targetKey) {
        let url = `/karma?target_type=${encodeURIComponent(targetType)}`;
        if (targetId != null) url += `&target_id=${targetId}`;
        if (targetKey) url += `&target_key=${encodeURIComponent(targetKey)}`;
        return this.request(url);
    }

    async getUserKarma() {
        return this.request('/user/karma');
    }

    // Wall posts
    async getWallPosts(entityType, entityId, entityKey, page = 1, perPage = 10) {
        let url = `/wall/posts?entity_type=${encodeURIComponent(entityType)}&page=${page}&per_page=${perPage}`;
        if (entityId != null) url += `&entity_id=${entityId}`;
        if (entityKey) url += `&entity_key=${encodeURIComponent(entityKey)}`;
        return this.request(url);
    }

    async createWallPost(entityType, entityId, entityKey, body, contentTheme = 'light') {
        let url = `/wall/posts?entity_type=${encodeURIComponent(entityType)}`;
        if (entityId != null) url += `&entity_id=${entityId}`;
        if (entityKey) url += `&entity_key=${encodeURIComponent(entityKey)}`;
        const payload = {
            body: body,
            content_theme: contentTheme
        };
        return this.request(url, { method: 'POST', body: JSON.stringify(payload) });
    }

    async deleteWallPost(postId) {
        return this.request(`/wall/posts/${postId}`, { method: 'DELETE' });
    }
}

// Export singleton instance
const api = new API();
window.api = api; // For debugging

