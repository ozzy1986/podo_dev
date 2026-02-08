/**
 * App Class Definition
 * Defines the App class with constructor only.
 * Methods are added via prototype extensions in separate module files.
 */

class App {
    constructor() {
        this.user = null;
        this.initialized = false;
        this.config = { token_name: 'DOMAIN' }; // Default fallback
        this.frequencies = []; // Available subscription frequencies
        this.languageSelectorSetup = false;
        
        // Widget management
        this.coreWidgets = ['mining_balance', 'total_domains', 'total_earned']; // Always visible
        this.availableWidgets = [
            'account_info',
            'your_statistics',
            'domain_health_warnings',
            'quick_alerts',
            'system_wide_statistics',
            'mining_performance',
            'top_earning_domains',
            'earnings_charts',
            'payout_settings',
            'payout_history',
            'recent_rewards',
            'recent_domains'
        ];
        
        // Widget width definitions: 'full' or 'half'
        this.widgetWidths = {
            'mining_balance': 'half',
            'total_domains': 'half',
            'total_earned': 'half',
            'account_info': 'half',
            'your_statistics': 'half',
            'domain_health_warnings': 'full',
            'quick_alerts': 'full',
            'system_wide_statistics': 'full',
            'mining_performance': 'half',
            'top_earning_domains': 'half',
            'earnings_charts': 'full',
            'payout_settings': 'half',
            'payout_history': 'half',
            'recent_rewards': 'full',
            'recent_domains': 'full'
        };
        
        // Rating page sort state (default: newest first - promoted and new domains mixed by recency)
        this.ratingSortBy = 'newest';
        this.ratingSortOrder = 'desc';
        
        // Wallets rating page sort state
        this.walletsRatingSortBy = 'rating';
        this.walletsRatingSortOrder = 'desc';
    }
}
