/**
 * Client-side Router using History API
 * Handles navigation and page rendering
 */

class Router {
    constructor() {
        this.routes = {};
        this.currentRoute = null;
        this.initialized = false;
        this.rendering = false; // Flag to prevent recursive renders
        
        // Root-only router - no support for subdirectories like /web
        this.basePath = '';
        
        // Don't auto-init - wait for routes to be registered
    }

    init() {
        if (this.initialized) return;
        
        // Handle browser back/forward
        window.addEventListener('popstate', () => {
            // Only render if routes are registered
            if (Object.keys(this.routes).length > 0) {
                this.render();
            }
        });

        this.initialized = true;
        // Don't render immediately - app will call render() after routes are registered
    }

    register(path, handler) {
        this.routes[path] = handler;
    }

    navigate(path, replace = false) {
        // Don't navigate if no routes registered (prevents infinite loop)
        if (Object.keys(this.routes).length === 0) {
            return;
        }
        
        // Don't navigate if already rendering (prevents recursive calls)
        if (this.rendering) {
            return;
        }
        
        // Normalize the target path
        let targetPath = path;
        if (targetPath === '' || targetPath === '/') {
            targetPath = '/';
        } else if (!targetPath.startsWith('/')) {
            targetPath = '/' + targetPath;
        }
        
        // Check if we're already on this path
        const currentPath = this.getCurrentPath();
        if (currentPath === targetPath && !replace) {
            return;
        }
        
        // Add base path if needed
        // Always use at least '/' for root path, never empty string
        let fullPath = this.basePath + (targetPath === '/' ? '/' : targetPath);
        // Ensure it starts with / if basePath is empty
        if (!fullPath.startsWith('/')) {
            fullPath = '/' + fullPath;
        }
        
        if (replace) {
            window.history.replaceState({}, '', fullPath);
        } else {
            window.history.pushState({}, '', fullPath);
        }
        this.render();
    }

    getCurrentPath() {
        let path = window.location.pathname;
        
        // Remove base path if present
        if (this.basePath && path.startsWith(this.basePath)) {
            path = path.substring(this.basePath.length);
        }
        
        // Normalize path
        if (path === '' || path === '/') {
            path = '/';
        } else if (!path.startsWith('/')) {
            path = '/' + path;
        }
        
        // Remove trailing slash (except for root)
        if (path.length > 1 && path.endsWith('/')) {
            path = path.slice(0, -1);
        }
        
        return path;
    }

    render() {
        // Prevent recursive renders
        if (this.rendering) {
            return;
        }
        
        // Don't render if no routes registered yet
        if (Object.keys(this.routes).length === 0) {
            const main = document.getElementById('main-content');
            if (main) {
                const currentContent = main.innerHTML.trim();
                if (currentContent === '' || currentContent.includes('spinner-border')) {
                    main.innerHTML = `
                        <div class="text-center py-5">
                            <div class="spinner-border text-primary" role="status">
                                <span class="visually-hidden" data-i18n="loading">Loading...</span>
                            </div>
                            <p class="mt-3" data-i18n="initializing_application">Initializing application...</p>
                        </div>
                    `;
                    // Update translations for loading message
                    if (window.app && typeof window.app.updateI18n === 'function') {
                        setTimeout(() => {
                            window.app.updateI18n();
                        }, 10);
                    }
                }
            }
            return;
        }
        
        this.rendering = true;
        
        try {
            const path = this.getCurrentPath();
            
            // First check for exact match
            let route = this.routes[path];
            
            // If no exact match, check for pattern routes (like /domain/*)
            if (!route) {
                // Check for domain pages pattern
                if (path.startsWith('/domain/')) {
                    route = this.routes['*']; // Use catch-all for pattern matching
                } else {
                    // Fall back to root or catch-all
                    route = this.routes['/'] || this.routes['*'];
                }
            }

            if (route) {
                // Clear main content
                const main = document.getElementById('main-content');
                if (main) {
                    main.innerHTML = '';
                }

                // Call route handler
                try {
                    if (typeof route === 'function') {
                        route();
                    } else if (route.render) {
                        route.render();
                    }
                    
                    // Update translations after route handler executes
                    if (window.app && typeof window.app.updateI18n === 'function') {
                        setTimeout(() => {
                            window.app.updateI18n();
                        }, 50);
                    }
                } catch (error) {
                    console.error('[Router] Error in route handler:', error);
                    const main = document.getElementById('main-content');
                    if (main) {
                        main.innerHTML = `<div class="alert alert-danger">Route error: ${error.message}</div>`;
                    }
                }

                this.currentRoute = path;
            } else {
                console.error(`[Router] No route found for: ${path}`);
                console.error(`[Router] Available routes:`, Object.keys(this.routes));
                
                // Show error - DO NOT navigate (prevents infinite loop)
                const main = document.getElementById('main-content');
                if (main) {
                    main.innerHTML = `
                        <div class="alert alert-danger">
                            <h4>Route Not Found</h4>
                            <p>Path: <code>${path}</code></p>
                            <p>Available routes: ${Object.keys(this.routes).join(', ')}</p>
                            <p><small>This should not happen. Check console for errors.</small></p>
                        </div>
                    `;
                }
            }
        } finally {
            this.rendering = false;
        }
    }

    // Helper to check if user is authenticated
    requireAuth(callback) {
        // Check both api.token and localStorage as fallback
        const token = api.token || localStorage.getItem('auth_token');
        if (!token) {
            // Use direct redirect to avoid render-in-progress issues
            // Use setTimeout to allow current render to complete
            setTimeout(() => {
                window.location.href = '/login';
            }, 0);
            return;
        }
        // Ensure api.token is set if it's in localStorage but not in api object
        if (!api.token && token) {
            api.token = token;
        }
        callback();
    }
}

// Export singleton instance
const router = new Router();
window.router = router; // For debugging

// Don't auto-init - app will call router.init() after registering routes

