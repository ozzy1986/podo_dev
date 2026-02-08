/**
 * App Core - Initialization, Routes, and Startup
 * Methods are added to App.prototype (class defined in js/app-class.js)
 * Module files (js/*.js) extend App.prototype with additional methods.
 * This file loads LAST and handles init, routing, refresh, and instantiation.
 */
(function() {
    'use strict';

    App.prototype.init = async function() {
        if (this.initialized) {
            return;
        }
        
        try {
            // Initialize theme first (before any rendering)
            this.initTheme();
            
            // Determine initial language - check user language first, then localStorage, then default to 'en'
            let initialLanguage = 'en';
            
            // Check if user is logged in
            if (api.token) {
                try {
                    this.user = await api.getCurrentUser();
                    
                    // Load user's language preference from database
                    try {
                        const langData = await api.getLanguage();
                        if (langData && langData.language) {
                            initialLanguage = langData.language;
                        }
                    } catch (error) {
                        console.warn('[App] Failed to load user language from API:', error);
                    }
                } catch (error) {
                    console.error('[App] Failed to get current user - token may be invalid');
                    console.error('[App] Error:', error);
                    console.error('[App] Clearing invalid token');
                    api.setToken(null);
                    this.user = null;
                }
            } else {
                this.user = null;
            }

            // Load config first (for token name)
            try {
                this.config = await api.getConfig();
            } catch (error) {
                console.warn('[App] Failed to load config, using defaults:', error);
            }
            
            // Load subscription frequencies
            try {
                const freqData = await api.getSubscriptionFrequencies();
                this.frequencies = freqData.frequencies || [];
            } catch (error) {
                console.warn('[App] Failed to load subscription frequencies:', error);
                this.frequencies = [];
            }
            
            // Initialize i18n with the determined language
            await i18n.setLanguage(initialLanguage);
            
            // Setup language selector
            this.setupLanguageSelector();
            
            // Setup routes FIRST
            this.setupRoutes();
            
            // Initialize router AFTER routes are registered
            router.init();
            
            // Setup navigation visibility
            this.updateNavigation();
            
            // Setup navigation link event handlers
            this.setupNavigationHandlers();
            
            // Initialize withdrawal fix notice
            this.initWithdrawalFixNotice();
            
            // Listen for language changes
            window.addEventListener('languageChanged', (e) => {
                // Multiple updates to catch all DOM changes
                setTimeout(() => this.updateI18n(), 10);
                setTimeout(() => this.updateI18n(), 100);
                setTimeout(() => this.updateI18n(), 300);
            });
            
            // Check for WX Network auth callback
            // WX Network returns with s=signature&p=publicKey&a=address parameters
            const currentUrl = window.location.href;
            const hasWXParams = currentUrl.includes('?s=') || currentUrl.includes('&s=') || 
                               currentUrl.includes('?p=') || currentUrl.includes('&p=') ||
                               currentUrl.includes('?a=') || currentUrl.includes('&a=');
            
            if (hasWXParams) {
                // Small delay to ensure everything is initialized
                setTimeout(() => {
                    this.handleWXNetworkCallback();
                }, 100);
            }
            
            this.initialized = true;
            return Promise.resolve(); // Explicitly return resolved promise
        } catch (error) {
            console.error('[App] ===== INIT ERROR =====');
            console.error('[App] Initialization error:', error);
            console.error('[App] Error stack:', error.stack);
            const main = document.getElementById('main-content');
            if (main) {
                main.innerHTML = `
                    <div class="alert alert-danger">
                        <h4>Initialization Error</h4>
                        <p>${error.message}</p>
                        <pre>${error.stack}</pre>
                        <p>Check browser console (F12) for details.</p>
                    </div>
                `;
            }
            return Promise.reject(error); // Reject so .catch() in DOMContentLoaded works
        }
    };

    App.prototype.loadUserLanguage = async function() {
        if (!this.user) return;
        
        try {
            const langData = await api.getLanguage();
            if (langData && langData.language) {
                await i18n.setLanguage(langData.language);
            } else {
                console.warn('[App] No language in langData:', langData);
            }
        } catch (error) {
            console.error('[App] Failed to load user language:', error);
            console.error('[App] Error details:', error.message, error.stack);
        }
    };

    App.prototype.setupRoutes = function() {
        // Public routes
        router.register('/login', () => {
            // showLogin will check auth and redirect if already logged in
            this.showLogin();
        });
        
        router.register('/rating', () => {
            // Public route - no auth required
            this.showRating();
        });
        
        router.register('/wallets-rating', () => {
            this.showWalletsRating();
        });
        router.register('/rating/by-registration-date', () => {
            router.navigate('/rating?sort_by=creation_date&sort_order=asc');
        });
        router.register('/registrars-rating', () => {
            this.showRegistrarsRating();
        });
        router.register('/hosters-rating', () => {
            this.showHostersRating();
        });
        router.register('/zones-rating', () => {
            this.showZonesRating();
        });

        // Domain page - public route, handled dynamically
        // We'll check for /domain/ pattern in catch-all

        // Root: dashboard when authenticated, rating when not
        router.register('/', () => {
            if (api.token) {
                this.showDashboard();
            } else {
                this.showRating();
            }
        });
        router.register('/domains', () => {
            router.requireAuth(() => this.showDomains());
        });
        router.register('/wallet', () => {
            router.requireAuth(() => this.showWallet());
        });
        router.register('/withdraw', () => {
            router.requireAuth(() => this.showWithdraw());
        });
        router.register('/widgets', () => {
            router.requireAuth(() => this.showWidgets());
        });

        // Catch-all
        router.register('*', () => {
            const path = router.getCurrentPath();
            
            // Check if this is a domain page
            if (path.startsWith('/domain/')) {
                let domain = path.substring('/domain/'.length);
                if (domain) {
                    // Decode URL-encoded domain (e.g., %D0%BA%D1%96%D1%82.%D1%80%D1%84 -> кіт.рф)
                    try {
                        domain = decodeURIComponent(domain);
                    } catch (e) {
                        console.warn('[App] Failed to decode domain from URL:', e);
                        // Use as-is if decoding fails
                    }
                    this.showDomainPage(domain);
                    return;
                }
            }
            
            // Default behavior: unauthenticated -> rating (landing), authenticated -> dashboard
            if (!api.token) {
                router.navigate('/');
            } else {
                router.navigate('/');
            }
        });
    };

    App.prototype.refresh = async function() {
        // Check if user is authenticated
        if (!api.token) {
            router.navigate('/login');
            return;
        }

        const refreshBtn = document.getElementById('refresh-btn');
        const refreshIcon = document.getElementById('refresh-icon');
        
        if (!refreshBtn || !refreshIcon) {
            console.error('[App] Refresh button not found');
            return;
        }

        // Disable button and show spinning animation
        refreshBtn.classList.add('disabled');
        refreshIcon.classList.add('spinning');
        
        try {
            const currentPath = router.getCurrentPath();
            
            // Reload data based on current route
            switch (currentPath) {
                case '/':
                case '':
                    // Dashboard
                    await this.loadDashboard();
                    break;
                case '/domains':
                    // Domains page
                    await this.loadDomains();
                    break;
                case '/wallet':
                    // Wallet page - reload the page
                    await this.showWallet();
                    break;
                case '/withdraw':
                    // Withdraw page - reload the page
                    await this.showWithdraw();
                    break;
                default:
                    // For unknown routes, try to reload dashboard
                    await this.loadDashboard();
            }
            
            this.showToast('success', i18n.t('refresh_success', 'Page refreshed'));
        } catch (error) {
            console.error('[App] Refresh error:', error);
            this.showToast('error', error.message || i18n.t('error'));
        } finally {
            // Re-enable button and remove spinning animation
            refreshBtn.classList.remove('disabled');
            refreshIcon.classList.remove('spinning');
        }
    };

})();

// ============================================================
// App Instantiation and Startup
// ============================================================

// Initialize app when DOM is ready
const app = new App();
window.app = app; // For debugging

// Function to start initialization (can be called immediately or on DOMContentLoaded)
function startApp() {
    // Check if all required modules are loaded
    if (typeof router === 'undefined') {
        console.error('[App] Router not loaded!');
        const main = document.getElementById('main-content');
        if (main) {
            main.innerHTML = `
                <div class="alert alert-danger">
                    <h4>JavaScript Error</h4>
                    <p><strong>Router not loaded!</strong></p>
                    <p>Failed to load router.js. Check:</p>
                    <ul>
                        <li>Is <code>static/router.js</code> file uploaded?</li>
                        <li>Check browser console (F12) for 404 errors</li>
                        <li>Check Network tab to see if router.js loaded</li>
                    </ul>
                    <p>Current path: <code>${window.location.pathname}</code></p>
                </div>
            `;
        }
        return;
    }
    
    if (typeof api === 'undefined') {
        console.error('[App] API not loaded!');
        const main = document.getElementById('main-content');
        if (main) {
            main.innerHTML = `<div class="alert alert-danger">API module not loaded. Check static/api.js</div>`;
        }
        return;
    }
    
    if (typeof i18n === 'undefined') {
        console.error('[App] i18n not loaded!');
        const main = document.getElementById('main-content');
        if (main) {
            main.innerHTML = `<div class="alert alert-danger">i18n module not loaded. Check static/i18n.js</div>`;
        }
        return;
    }
    
    app.init().then(() => {
        if (typeof router !== 'undefined') {
            // Routes should be registered by now, safe to render
            // Check if user is on login/register page but already logged in
            const currentPath = window.location.pathname;
            if (currentPath === '/login' && api.token && app.user) {
                router.navigate('/');
            } else {
                // Render immediately
                router.render();
            }
        } else {
            console.error('[App] Router still undefined after init!');
            const main = document.getElementById('main-content');
            if (main) {
                main.innerHTML = '<div class="alert alert-danger">Router not available</div>';
            }
        }
    }).catch(error => {
        console.error('[App] ===== INIT PROMISE REJECTED =====');
        console.error('[App] Fatal initialization error:', error);
        console.error('[App] Error stack:', error.stack);
        const main = document.getElementById('main-content');
        if (main) {
            main.innerHTML = `
                <div class="alert alert-danger">
                    <h4>Fatal Error</h4>
                    <p>${error.message}</p>
                    <pre>${error.stack}</pre>
                    <p>Check browser console for more details.</p>
                </div>
            `;
        }
    });
}

// Prevent double initialization
let appStarted = false;

// Try to start immediately (if DOM already loaded)
if (document.readyState === 'loading') {
    // DOM is still loading, wait for DOMContentLoaded
    document.addEventListener('DOMContentLoaded', () => {
        if (!appStarted) {
            appStarted = true;
            startApp();
        }
    });
} else {
    // DOM already loaded, but wait a bit for scripts to fully initialize
    // (index.html will call startApp after scripts load)
}

// Make startApp globally available for index.html to call
window.startApp = startApp;
