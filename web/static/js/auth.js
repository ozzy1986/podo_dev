/**
 * Auth Module
 * Login, registration, wallet authentication
 */
(function() {
    'use strict';

    App.prototype.login = async function(username, password) {
        try {
            const data = await api.login(username, password);
            
            api.setToken(data.token);
            
            this.user = data;
            
            await this.loadUserLanguage();
            
            this.updateNavigation();
            
            router.navigate('/');
            
            this.showToast('success', i18n.t('login_success') || 'Login successful');
        } catch (error) {
            console.error('[App] ===== LOGIN ERROR =====');
            console.error('[App] Login error:', error);
            console.error('[App] Error message:', error.message);
            console.error('[App] Error stack:', error.stack);
            this.showToast('error', error.message || i18n.t('error') || 'Login failed');
            throw error;
        }
    };

    App.prototype.register = async function(username, password, email) {
        try {
            const data = await api.register(username, password, email);
            // Don't auto-login - proceed to email verification
            this.showToast('success', 'Registration data saved! Check your email for verification code.');
            return data;
        } catch (error) {
            this.showToast('error', error.message || 'Registration failed');
            throw error;
        }
    };

    App.prototype.loginWithWXNetwork = async function() {
        try {
            // Use WX Network Web Auth API (redirect-based, no libraries needed)
            // Documentation: https://docs.waves.exchange/en/waves-exchange/waves-exchange-client-api/waves-exchange-web-auth-api
            
            // Generate random data for user to sign
            const randomData = Array.from(crypto.getRandomValues(new Uint8Array(16)))
                .map(b => b.toString(16).padStart(2, '0'))
                .join('');
            
            // Store the data in sessionStorage for verification after redirect
            sessionStorage.setItem('wx_auth_data', randomData);
            sessionStorage.setItem('wx_auth_timestamp', Date.now().toString());
            
            // Get referrer URL - use current origin (whatever it is - HTTP, HTTPS, IP, domain, etc.)
            // Optional override available via window.WX_AUTH_REFERRER
            const referrerOverride = window.WX_AUTH_REFERRER;
            const referrerValue = referrerOverride || window.location.origin;
            let referrerUrl;
            try {
                referrerUrl = new URL(referrerValue);
                
                // Validate hostname - only allow whitelisted domains/IPs
                const allowedHostnames = ['d.onl', 'www.d.onl', 'dev.d.onl', '193.33.170.175', 'localhost', '127.0.0.1'];
                const hostname = referrerUrl.hostname.toLowerCase();
                const isAllowed = allowedHostnames.some(allowed => {
                    // Exact match or subdomain match (e.g., www.d.onl matches d.onl)
                    return hostname === allowed || hostname.endsWith('.' + allowed);
                });
                
                if (!isAllowed) {
                    const errorMsg = `WX Network auth is only allowed from whitelisted domains: ${allowedHostnames.filter(h => !['localhost', '127.0.0.1'].includes(h)).join(', ')}. Current origin: ${referrerUrl.origin}`;
                    console.error('[App]', errorMsg);
                    this.showToast('error', errorMsg);
                    throw new Error(errorMsg);
                }
                
                console.log('[App] Using referrer origin (validated):', referrerUrl.origin);
            } catch (e) {
                if (e.message && e.message.includes('WX Network auth is only allowed')) {
                    throw e; // Re-throw validation errors
                }
                console.error('[App] Failed to parse referrer URL:', referrerValue, e);
                throw new Error(`Invalid WX_AUTH_REFERRER value: ${referrerValue}`);
            }
            
            // Service name - manually encode to ensure spaces become %20 (not +)
            const defaultServiceName = `${window.location.hostname} - Proof of Domain Ownership`;
            const serviceName = window.WX_AUTH_SERVICE_NAME || defaultServiceName;
            
            // Success path - use simple path without query params (WX Network will append its params)
            const successPath = window.WX_AUTH_SUCCESS_PATH || '/login';
            
            // Host to use for signature verification (must match referrer host)
            const authHost = referrerUrl.hostname;
            
            // Store referrer/host for callback verification
            sessionStorage.setItem('wx_auth_referrer', referrerUrl.origin);
            sessionStorage.setItem('wx_auth_host', authHost);
            
            // Debug logging removed for production
            
            // Build the WX Network auth URL
            // Format: https://wx.network#gateway/auth?r=REFERRER&n=SERVICE_NAME&d=DATA&s=SUCCESS_PATH
            // Note: Query parameters must be INSIDE the hash fragment, not as URL search params
            // We manually encode to ensure spaces become %20 (not +)
            const hashString = `r=${encodeURIComponent(referrerUrl.origin)}&n=${encodeURIComponent(serviceName)}&d=${encodeURIComponent(randomData)}&s=${encodeURIComponent(successPath)}`;
            
            // Build the full URL with hash containing query parameters
            const authUrl = `https://wx.network#gateway/auth?${hashString}`;
            
            // Warn if using HTTP - wx.network may reject it
            if (referrerUrl.protocol === 'http:' && referrerUrl.hostname !== 'localhost' && referrerUrl.hostname !== '127.0.0.1') {
                console.warn('[App] ⚠️ WARNING: Using HTTP referrer. wx.network may require HTTPS and reject this request.');
                console.warn('[App] If you see "Something went wrong" on wx.network, it\'s likely because HTTP is not allowed.');
                console.warn('[App] Consider using HTTPS or configure SSL certificate for your domain.');
            }
            
            // Debug logging - log the exact URL being sent
            console.log('[App] ===== WX.NETWORK AUTH REDIRECT =====');
            console.log('[App] Referrer origin:', referrerUrl.origin);
            console.log('[App] Service name:', serviceName);
            console.log('[App] Success path:', successPath);
            console.log('[App] Host for signature:', authHost);
            console.log('[App] Full auth URL:', authUrl);
            console.log('[App] Hash string:', hashString);
            
            // Debug logging removed for production
            
            // Store a flag to detect if we're coming back from wx.network error
            sessionStorage.setItem('wx_auth_attempt_timestamp', Date.now().toString());
            
            // Redirect to WX Network
            window.location.href = authUrl;
            
            // Note: This function will not return - user will be redirected
            // The callback will be handled in the route handler when user returns
        } catch (error) {
            console.error('[App] ===== WX.NETWORK LOGIN ERROR =====');
            console.error('[App] Error:', error);
            this.showToast('error', error.message || i18n.t('wx_login_failed') || 'WX Network login failed');
            throw error;
        }
    };
    
    App.prototype.handleWXNetworkCallback = async function() {
        // This is called when user returns from WX Network auth
        try {
            // Debug logging
            console.log('[App] ===== WX.NETWORK CALLBACK HANDLER =====');
            console.log('[App] Current URL:', window.location.href);
            console.log('[App] Origin:', window.location.origin);
            console.log('[App] Hostname:', window.location.hostname);
            
            // Check if we're still on wx.network domain (error page)
            if (window.location.hostname === 'wx.network' || window.location.hostname.includes('wx.network')) {
                console.error('[App] Still on wx.network domain - likely an error page');
                console.error('[App] This usually means wx.network rejected the request (e.g., HTTP not allowed, invalid referrer)');
                // Try to detect if there's an error message on the page
                setTimeout(() => {
                    const errorText = document.body?.innerText || '';
                    if (errorText.includes('Something went wrong') || errorText.includes('error') || errorText.includes('Error')) {
                        console.error('[App] Detected error on wx.network page');
                        // Redirect back to login with error message
                        const errorMsg = 'wx.network rejected the authentication request. This may be because HTTP is not allowed - HTTPS is typically required.';
                        sessionStorage.setItem('wx_auth_error', errorMsg);
                        window.location.href = '/login?error=wx_network_rejected';
                    }
                }, 1000);
                return false;
            }
            
            // WX Network returns parameters in the URL query string
            // Handle both cases: /login?s=...&p=...&a=... or /login/?wx_auth?s=...&p=...&a=...
            const currentUrl = window.location.href;
            
            // Parse URL - handle malformed URLs like /login/?wx_auth?s=...
            // Extract parameters using regex to handle malformed query strings
            let signature = null;
            let publicKey = null;
            let address = null;
            
            // Try normal URL parsing first
            try {
                const url = new URL(currentUrl);
                const urlParams = url.searchParams;
                signature = urlParams.get('s');
                publicKey = urlParams.get('p');
                address = urlParams.get('a');
            } catch (e) {
                // URL parsing failed, use regex fallback
            }
            
            // If not found, use regex to extract from malformed URLs like /login/?wx_auth?s=...
            if (!signature || !publicKey || !address) {
                const sMatch = currentUrl.match(/[?&]s=([^&]+)/);
                if (sMatch) signature = decodeURIComponent(sMatch[1]);
                
                const pMatch = currentUrl.match(/[?&]p=([^&]+)/);
                if (pMatch) publicKey = decodeURIComponent(pMatch[1]);
                
                const aMatch = currentUrl.match(/[?&]a=([^&]+)/);
                if (aMatch) address = decodeURIComponent(aMatch[1]);
            }
            
            // Check for error parameters from wx.network
            let errorParam = null;
            let errorDescription = null;
            try {
                const url = new URL(currentUrl);
                errorParam = url.searchParams.get('error');
                errorDescription = url.searchParams.get('error_description');
            } catch (e) {
                // Try regex fallback
                const errorMatch = currentUrl.match(/[?&]error=([^&]+)/);
                if (errorMatch) errorParam = decodeURIComponent(errorMatch[1]);
                const descMatch = currentUrl.match(/[?&]error_description=([^&]+)/);
                if (descMatch) errorDescription = decodeURIComponent(descMatch[1]);
            }
            
            if (errorParam) {
                console.error('[App] ===== WX.NETWORK ERROR RETURNED =====');
                console.error('[App] Error code:', errorParam);
                console.error('[App] Error description:', errorDescription);
                const errorMsg = errorDescription || errorParam || 'Authentication failed';
                this.showToast('error', `WX Network error: ${errorMsg}`);
                return false;
            }
            
            if (!signature || !publicKey || !address) {
                console.warn('[App] Missing auth parameters in callback URL');
                console.warn('[App] Signature:', signature ? 'present' : 'missing');
                console.warn('[App] Public key:', publicKey ? 'present' : 'missing');
                console.warn('[App] Address:', address ? 'present' : 'missing');
                console.warn('[App] Full URL:', currentUrl);
                return false;
            }
            
            // Get the original data that was sent
            const originalData = sessionStorage.getItem('wx_auth_data');
            const timestamp = sessionStorage.getItem('wx_auth_timestamp');
            
            // Debug logging removed for production
            
            if (!originalData) {
                console.error('[App] Original auth data not found in sessionStorage');
                this.showToast('error', 'Authentication session expired. Please try again.');
                return false;
            }
            
            // Read referrer and host BEFORE clearing (needed for WX signature verification)
            const referrer = sessionStorage.getItem('wx_auth_referrer') || window.location.origin;
            const host = sessionStorage.getItem('wx_auth_host') || window.location.hostname;
            
            // Clean up sessionStorage
            sessionStorage.removeItem('wx_auth_data');
            sessionStorage.removeItem('wx_auth_timestamp');
            sessionStorage.removeItem('wx_auth_referrer');
            sessionStorage.removeItem('wx_auth_host');
            
            // Remove auth parameters from URL
            const newUrl = new URL(window.location.href);
            newUrl.searchParams.delete('s');
            newUrl.searchParams.delete('p');
            newUrl.searchParams.delete('a');
            newUrl.searchParams.delete('wx_auth');
            window.history.replaceState({}, '', newUrl.toString());
            
            // Send to backend: referrer (full origin) and host (hostname) for WX Web Auth format
            const data = await api.loginWithWalletWX(address, signature, publicKey, originalData, host, referrer);
            
            // Verify we got a token
            if (!data || !data.token) {
                throw new Error('Login failed: No token received from server');
            }
            
            // Set token and user BEFORE navigation
            api.setToken(data.token);
            this.user = data;
            
            // Verify token is set (should be immediate, but double-check)
            if (!api.token) {
                console.error('[App] Token was not set properly after login');
                throw new Error('Failed to set authentication token');
            }
            
            // Load user language
            await this.loadUserLanguage();
            
            // Update navigation
            this.updateNavigation();
            
            // Small delay to ensure token is fully set before navigation
            // This prevents race condition where requireAuth() checks before token is available
            await new Promise(resolve => setTimeout(resolve, 50));
            
            // Ensure translations are loaded before showing toast
            await i18n.loadLanguage(i18n.getCurrentLanguage());
            
            // Navigate to dashboard - use replace to avoid back button issues
            router.navigate('/', true);
            
            // Show success message with proper translation
            const successMessage = i18n.t('login_success');
            this.showToast('success', successMessage || 'Login successful');
            return true;
        } catch (error) {
            console.error('[App] ===== WX.NETWORK CALLBACK ERROR =====');
            console.error('[App] Error:', error);
            this.showToast('error', error.message || i18n.t('wx_login_failed') || 'WX Network authentication failed');
            return false;
        }
    };

    App.prototype.logout = function() {
        api.setToken(null);
        this.user = null;
        this.updateNavigation();
        router.navigate('/login');
    };

    App.prototype.showLogin = function() {
        // Check if user is already logged in
        if (api.token && this.user) {
            router.navigate('/');
            return;
        }
        
        // Check for wx.network error in URL or sessionStorage
        const urlParams = new URLSearchParams(window.location.search);
        const urlError = urlParams.get('error');
        const storedError = sessionStorage.getItem('wx_auth_error');
        let errorMessage = null;
        
        if (urlError === 'wx_network_rejected' || storedError) {
            errorMessage = storedError || 'wx.network rejected the authentication request. This may be because HTTP is not allowed - HTTPS is typically required for production domains.';
            sessionStorage.removeItem('wx_auth_error');
            // Clean up URL
            const newUrl = new URL(window.location.href);
            newUrl.searchParams.delete('error');
            window.history.replaceState({}, '', newUrl.toString());
        }
        
        const main = document.getElementById('main-content');
        main.innerHTML = `
            <div class="row justify-content-center">
                <div class="col-md-6 col-lg-4">
                    <div class="card">
                        <div class="card-body">
                            <h2 class="card-title text-center mb-4" data-i18n="login">Login</h2>
                            
                            ${errorMessage ? `
                            <div class="alert alert-warning mb-3" role="alert">
                                <i class="bi bi-exclamation-triangle me-2"></i>
                                <strong>Authentication Error:</strong><br>
                                ${this.escapeHtml(errorMessage)}
                                <br><small class="text-muted mt-2 d-block">If you're using HTTP, please use HTTPS or wait for SSL certificate installation.</small>
                            </div>
                            ` : ''}
                            
                            <!-- WX Network Login Button -->
                            <div class="mb-3">
                                <button type="button" class="btn btn-primary w-100 mb-3" id="wx-login-btn" onclick="app.loginWithWXNetwork()">
                                    <i class="bi bi-wallet2 me-2"></i>
                                    <span data-i18n="login_with_wx_network">Login with WX Network</span>
                                </button>
                                <div class="text-center">
                                    <small class="text-muted" data-i18n="wx_network_description">Connect your Waves wallet to login</small>
                                </div>
                            </div>
                            
                            <!-- Rating Links -->
                            <div class="mt-3">
                                <a href="#" class="btn btn-outline-primary w-100 mb-2" onclick="event.preventDefault(); router.navigate('/rating');" data-i18n="view_domains_rating">
                                    <i class="bi bi-trophy me-2"></i>
                                    <span data-i18n="domains_rating">Ratings</span>
                                </a>
                                <a href="#" class="btn btn-outline-secondary w-100" onclick="event.preventDefault(); router.navigate('/wallets-rating');" data-i18n="view_wallets_rating">
                                    <i class="bi bi-wallet2 me-2"></i>
                                    <span data-i18n="wallets_rating">Wallets Rating</span>
                                </a>
                            </div>
                            
                            <!-- About Section -->
                            <div class="mt-4 pt-3 border-top text-center">
                                <small class="text-muted">
                                    <span data-i18n="about_text">About</span> - 
                                    <a href="https://so.su/domain" target="_blank" rel="noopener noreferrer" class="text-decoration-none">https://so.su/domain</a>
                                </small>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;

        this.updateI18n();
    };

    App.prototype.showEmailVerification = function(username, email) {
        const main = document.getElementById('main-content');
        main.innerHTML = `
            <div class="row justify-content-center">
                <div class="col-md-6 col-lg-4">
                    <div class="card">
                        <div class="card-body text-center">
                            <h2 class="card-title mb-4" data-i18n="check_your_email">Check Your Email</h2>
                            <div class="alert alert-success mb-4">
                                <strong data-i18n="verification_code_sent">Verification code sent!</strong><br>
                                We've sent a 6-digit code to:<br>
                                <code>${email}</code>
                            </div>
                            <form id="verification-form">
                                <div class="mb-3">
                                    <label class="form-label" data-i18n="verification_code">Verification Code</label>
                                    <input type="text" class="form-control text-center" id="verification-code" placeholder="000000" maxlength="6" required>
                                    <small class="form-text text-muted" data-i18n="enter_verification_code">Enter the 6-digit code from your email</small>
                                </div>
                                <button type="submit" class="btn btn-primary w-100 mb-2" data-i18n="verify_email">Verify Email</button>
                                <button type="button" class="btn btn-outline-secondary w-100 mb-3" id="resend-code-btn" data-i18n="resend_code">Resend Code</button>
                            </form>
                            <div class="alert alert-info small">
                                <strong>Check your email!</strong> The code was sent to:<br>
                                <code>${email}</code>
                            </div>
                            <div class="mt-2">
                                <small class="text-muted">
                                    Didn't receive the email? Check your spam folder.
                                </small>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;

        document.getElementById('verification-form').addEventListener('submit', async (e) => {
            e.preventDefault();
            const code = document.getElementById('verification-code').value.trim();

            if (!code) {
                this.showToast('error', i18n.t('invalid_verification_code'));
                return;
            }

            try {
                const data = await api.verifyEmail(email, code);

                if (!data.success) {
                    throw new Error(data.error || i18n.t('invalid_verification_code'));
                }

                // Show success message
                this.showToast('success', i18n.t('email_verified') || 'Email verified successfully! Please login.');

                // Redirect to login page after successful verification
                router.navigate('/login');
            } catch (error) {
                this.showToast('error', error.message || i18n.t('invalid_verification_code'));
            }
        });

        // Resend code handler
        document.getElementById('resend-code-btn').addEventListener('click', async () => {
            try {
                await api.resendCode(email);
                this.showToast('success', i18n.t('verification_code_sent'));
            } catch (error) {
                this.showToast('error', error.message || i18n.t('error'));
            }
        });
    };

})();
