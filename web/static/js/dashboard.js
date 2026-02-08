/**
 * Dashboard Module
 * Dashboard page rendering and data loading
 */
(function() {
    'use strict';

    App.prototype.showDashboard = function() {
        // Check auth, but don't use requireAuth (it tries to navigate during render)
        if (!api.token) {
            // Show login page directly instead of navigating
            this.showLogin();
            return;
        }
        
        // Show dashboard
        const main = document.getElementById('main-content');
        if (!main) {
            console.error('[App] Main content element not found!');
            return;
        }
        
        main.innerHTML = `
            <div class="text-center py-5">
                <div class="spinner-border text-primary" role="status">
                    <span class="visually-hidden" data-i18n="loading">Loading...</span>
                </div>
                <p class="mt-3" data-i18n="loading_dashboard">Loading dashboard...</p>
            </div>
        `;
        // Update i18n for loading message immediately
        this.updateI18n();
        
        // Load dashboard data
        this.loadDashboard();
    };

    App.prototype.loadDashboard = async function() {
        
        if (!api.token) {
            console.error('[App] No token in loadDashboard, redirecting to login');
            router.navigate('/login');
            return;
        }
        
        const main = document.getElementById('main-content');
        if (!main) {
            console.error('[App] Main content element not found when loading dashboard!');
            return;
        }
        
        // Initialize defaults
        let balance = { accumulated_balance: 0, accumulated_units: 0, payout_mode: 'manual', pending_payout: 0 };
        let stats = { domains_count: 0, active_mining: 0, total_earned: 0, accumulated_balance: 0 };
        let domains = { domains: [], count: 0 };
        let rewards = { rewards: [], count: 0 };
        let payouts = { payouts: [], payouts_count: 0, payout_mode: 'manual', payout_threshold: null, last_payout_at: null, pending_payout: 0 };
        let domainHealth = { expiring_soon: [], failed_checks: [], needs_verification: [], healthy: [], total_domains: 0 };
        let earnings = { daily_earnings: {}, weekly_earnings: {}, avg_daily: 0, avg_weekly: 0, earnings_by_domain: {}, total_confirmed: 0, total_pending: 0, total_failed: 0 };
        let systemStats = { total_domains: 0, active_domains: 0, verified_domains: 0, total_users: 0, total_rewards_distributed: 0, successful_transactions: 0, failed_transactions: 0 };
        let enabledWidgets = [...this.coreWidgets]; // Default fallback
        
        try {
            // Try combined dashboard endpoint first (faster: 1 request instead of 9)
            let usedCombinedEndpoint = false;
            
            try {
                const dashboardData = await api.getDashboard();
                
                if (dashboardData && !dashboardData.error) {
                    // Successfully fetched combined data
                    usedCombinedEndpoint = true;
                    const queryTime = dashboardData._meta?.query_time_ms || 'N/A';
                    const totalTime = dashboardData._meta?.processing_time_ms || 'N/A';
                    console.log(`[App] Dashboard loaded via combined endpoint (queries: ${queryTime}ms, total: ${totalTime}ms)`);
                    
                // Distribute data from combined response
                balance = dashboardData.balance || balance;
                stats = dashboardData.stats || stats;
                domains = dashboardData.domains || domains;
                rewards = dashboardData.rewards || rewards;
                payouts = dashboardData.payouts || payouts;
                domainHealth = dashboardData.domain_health || domainHealth;
                earnings = dashboardData.earnings || earnings;
                systemStats = dashboardData.system_stats || systemStats;
                    
                    if (dashboardData.widget_preferences?.enabled_widgets) {
                        enabledWidgets = dashboardData.widget_preferences.enabled_widgets;
                    }
                    // Populate widget cache so toggling doesn't re-fetch
                    this._cachedEnabledWidgets = [...enabledWidgets];
                }
            } catch (combinedError) {
                console.warn('[App] Combined dashboard endpoint failed, falling back to individual calls:', combinedError.message);
            }
            
            // Fallback to individual API calls if combined endpoint failed
            if (!usedCombinedEndpoint) {
                console.log('[App] Using fallback: 9 individual API calls');
                
                const results = await Promise.allSettled([
                    api.getBalance().catch(e => { console.error('[App] Balance fetch failed:', e); return null; }),
                    api.getUserStats().catch(e => { console.error('[App] Stats fetch failed:', e); return null; }),
                    api.getDomains().catch(e => { console.error('[App] Domains fetch failed:', e); return null; }),
                    api.getRewards().catch(e => { console.error('[App] Rewards fetch failed:', e); return null; }),
                    api.getPayouts().catch(e => { console.error('[App] Payouts fetch failed:', e); return null; }),
                    api.getDomainHealth().catch(e => { console.error('[App] Domain health fetch failed:', e); return null; }),
                    api.getEarnings().catch(e => { console.error('[App] Earnings fetch failed:', e); return null; }),
                    api.getStats().catch(e => { console.error('[App] System stats fetch failed:', e); return null; }),
                    api.getWidgetPreferences().catch(e => { console.error('[App] Widget preferences fetch failed:', e); return null; })
                ]);
                
                if (results[0].status === 'fulfilled' && results[0].value) balance = results[0].value;
                if (results[1].status === 'fulfilled' && results[1].value) stats = results[1].value;
                if (results[2].status === 'fulfilled' && results[2].value) domains = results[2].value;
                if (results[3].status === 'fulfilled' && results[3].value) rewards = results[3].value;
                if (results[4].status === 'fulfilled' && results[4].value) payouts = results[4].value;
                if (results[5].status === 'fulfilled' && results[5].value) domainHealth = results[5].value;
                if (results[6].status === 'fulfilled' && results[6].value) earnings = results[6].value;
                if (results[7].status === 'fulfilled' && results[7].value) systemStats = results[7].value;
                if (results[8].status === 'fulfilled' && results[8].value?.enabled_widgets) {
                    enabledWidgets = results[8].value.enabled_widgets;
                }
                // Populate widget cache
                this._cachedEnabledWidgets = [...enabledWidgets];
            }
            
            // Get user info for display
            const username = this.user?.username || 'User';
            const wallet = this.user?.wallet || null;
            const email = this.user?.email || null;
            
            // Format domains list for quick view
            const domainsList = domains.domains && domains.domains.length > 0
                ? domains.domains.slice(0, 5).map(d => `
                    <div class="list-group-item d-flex justify-content-between align-items-center">
                        <div>
                            <strong>${d.domain}</strong>
                            ${d.verified ? '<span class="badge bg-success ms-2" data-i18n="domain_status_verified">Verified</span>' : '<span class="badge bg-warning ms-2" data-i18n="domain_status_not_verified">Not Verified</span>'}
                            ${d.is_mining ? '<span class="badge bg-info ms-2" data-i18n="domain_status_mining">Mining</span>' : ''}
                        </div>
                    </div>
                `).join('')
                : `<div class="list-group-item text-muted" data-i18n="you_have_no_domains">You don't have any domains yet.</div>`;
            
            // Helper function to render widget title with info icon
            const renderWidgetTitle = (widgetId, titleKey, titleText) => {
                const infoKey = `widget_info_${widgetId}`;
                return `
                    <h5 class="mb-0">
                        <span data-i18n="${titleKey}">${titleText}</span>
                        <i class="bi bi-info-circle ms-2" 
                           data-bs-toggle="tooltip" 
                           data-bs-placement="top" 
                           data-bs-html="true"
                           data-i18n-tooltip="${infoKey}"
                           style="cursor: help; font-size: 0.9em; opacity: 0.7;"></i>
                    </h5>
                `;
            };
            
            // Helper function to render a widget
            const renderWidget = (widgetId) => {
                const width = this.widgetWidths[widgetId] || 'half';
                const colClass = width === 'full' ? 'col-12' : 'col-md-6';
                
                switch(widgetId) {
                    case 'account_info':
                        return `
                            <div class="${colClass} mb-3">
                                <div class="card">
                                    <div class="card-header">
                                        ${renderWidgetTitle('account_info', 'account_info', 'Account Info')}
                                    </div>
                                    <div class="card-body">
                                        <p class="mb-2"><strong data-i18n="username">Username</strong>: ${username}</p>
                                        ${email ? `<p class="mb-2"><strong data-i18n="email">Email</strong>: ${email}</p>` : ''}
                                        ${wallet ? `<p class="mb-2"><strong data-i18n="wallet_address">Wallet</strong>: <code class="small">${wallet}</code></p>` : `<p class="text-warning mb-2" data-i18n="please_set_wallet">Please set your wallet first</p>`}
                                        ${!wallet ? `<a href="/wallet" class="btn btn-sm btn-primary" onclick="event.preventDefault(); router.navigate('/wallet');" data-i18n="set_wallet">Set Wallet</a>` : ''}
                                    </div>
                                </div>
                            </div>
                        `;
                    case 'your_statistics':
                        return `
                            <div class="${colClass} mb-3">
                                <div class="card">
                                    <div class="card-header">
                                        ${renderWidgetTitle('your_statistics', 'your_statistics', 'Your Statistics')}
                                    </div>
                                    <div class="card-body">
                                        <div class="row text-center">
                                            <div class="col-6 mb-2">
                                                <div class="border rounded p-2">
                                                    <div class="h4 mb-0 text-success">${stats.domains_count || 0}</div>
                                                    <small class="text-muted" data-i18n="domains_total">Total</small>
                                                </div>
                                            </div>
                                            <div class="col-6 mb-2">
                                                <div class="border rounded p-2">
                                                    <div class="h4 mb-0 text-info">${stats.active_mining || 0}</div>
                                                    <small class="text-muted" data-i18n="domains_mining">Mining</small>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        `;
                    case 'domain_health_warnings':
                        if (!(domainHealth.expiring_count > 0 || domainHealth.failed_count > 0 || domainHealth.needs_verification_count > 0)) return '';
                        return `
                            <div class="${colClass} mb-3">
                                <div class="card border-warning">
                                    <div class="card-header bg-warning text-dark">
                                        <h5 class="mb-0">
                                            <i class="bi bi-exclamation-triangle"></i> 
                                            <span data-i18n="domain_health_alerts">Domain Health Alerts</span>
                                            <i class="bi bi-info-circle ms-2" 
                                               data-bs-toggle="tooltip" 
                                               data-bs-placement="top" 
                                               data-bs-html="true"
                                               data-i18n-tooltip="widget_info_domain_health_warnings"
                                               style="cursor: help; font-size: 0.9em; opacity: 0.8;"></i>
                                        </h5>
                                    </div>
                                    <div class="card-body">
                                        ${domainHealth.expiring_count > 0 ? `
                                            <div class="alert alert-warning mb-2">
                                                <strong data-i18n="domains_expiring_soon">Domains Expiring Soon</strong> (${domainHealth.expiring_count})
                                                <ul class="mb-0 mt-2">
                                                    ${domainHealth.expiring_soon.slice(0, 5).map(d => `
                                                        <li>${d.domain} - <span>${i18n.t('expires_in_days').replace('{days}', d.days_until_expiry)}</span></li>
                                                    `).join('')}
                                                </ul>
                                            </div>
                                        ` : ''}
                                        ${domainHealth.failed_count > 0 ? `
                                            <div class="alert alert-danger mb-2">
                                                <strong data-i18n="domains_with_failed_checks">Domains with Failed Checks</strong> (${domainHealth.failed_count})
                                                <ul class="mb-0 mt-2">
                                                    ${domainHealth.failed_checks.slice(0, 5).map(d => `
                                                        <li>${d.domain} - <span>${i18n.t('failed_checks_count').replace('{count}', d.failed_checks)}</span></li>
                                                    `).join('')}
                                                </ul>
                                            </div>
                                        ` : ''}
                                        ${domainHealth.needs_verification_count > 0 ? `
                                            <div class="alert alert-info mb-2">
                                                <strong data-i18n="domains_needing_verification">Domains Needing Verification</strong> (${domainHealth.needs_verification_count})
                                                <ul class="mb-0 mt-2">
                                                    ${domainHealth.needs_verification.slice(0, 5).map(d => `
                                                        <li>${d.domain}</li>
                                                    `).join('')}
                                                </ul>
                                            </div>
                                        ` : ''}
                                        <a href="/domains" class="btn btn-sm btn-primary" onclick="event.preventDefault(); router.navigate('/domains');" data-i18n="manage_domains">Manage Domains</a>
                                    </div>
                                </div>
                            </div>
                        `;
                    case 'quick_alerts':
                        if (!(payouts.pending_payout > 0 || domainHealth.expiring_count > 0 || domainHealth.failed_count > 0 || domainHealth.needs_verification_count > 0 || !wallet)) return '';
                        return `
                            <div class="${colClass} mb-3">
                                <div class="card border-primary">
                                    <div class="card-header bg-primary text-white">
                                        <h5 class="mb-0">
                                            <i class="bi bi-bell"></i> 
                                            <span data-i18n="quick_alerts">Quick Alerts</span>
                                            <i class="bi bi-info-circle ms-2" 
                                               data-bs-toggle="tooltip" 
                                               data-bs-placement="top" 
                                               data-bs-html="true"
                                               data-i18n-tooltip="widget_info_quick_alerts"
                                               style="cursor: help; font-size: 0.9em; opacity: 0.8;"></i>
                                        </h5>
                                    </div>
                                    <div class="card-body">
                                        ${!wallet ? `
                                            <div class="alert alert-warning mb-2">
                                                <i class="bi bi-exclamation-triangle"></i> <strong data-i18n="wallet_not_set">Wallet not set</strong> - <a href="/wallet" onclick="event.preventDefault(); router.navigate('/wallet');" data-i18n="set_wallet">Set your wallet</a> to receive payouts
                                            </div>
                                        ` : ''}
                                        ${payouts.pending_payout > 0 ? `
                                            <div class="alert alert-info mb-2">
                                                <i class="bi bi-clock-history"></i> <strong data-i18n="pending_payout_alert">Pending Payout</strong>: ${payouts.pending_payout.toFixed(2)} <span data-i18n="tokens">tokens</span> - <span data-i18n="processing">Processing</span>
                                            </div>
                                        ` : ''}
                                        ${domainHealth.expiring_count > 0 ? `
                                            <div class="alert alert-warning mb-2">
                                                <i class="bi bi-calendar-x"></i> <strong data-i18n="domains_expiring_soon">Domains Expiring Soon</strong>: ${domainHealth.expiring_count} <span data-i18n="domains">domains</span> need attention
                                            </div>
                                        ` : ''}
                                        ${domainHealth.failed_count > 0 ? `
                                            <div class="alert alert-danger mb-2">
                                                <i class="bi bi-x-circle"></i> <strong data-i18n="domains_with_failed_checks">Domains with Failed Checks</strong>: ${domainHealth.failed_count} <span data-i18n="domains">domains</span> need verification
                                            </div>
                                        ` : ''}
                                        ${domainHealth.needs_verification_count > 0 ? `
                                            <div class="alert alert-info mb-2">
                                                <i class="bi bi-check-circle"></i> <strong data-i18n="domains_needing_verification">Domains Needing Verification</strong>: ${domainHealth.needs_verification_count} <span data-i18n="domains">domains</span> pending verification
                                            </div>
                                        ` : ''}
                                        ${(payouts.pending_payout === 0 && domainHealth.expiring_count === 0 && domainHealth.failed_count === 0 && domainHealth.needs_verification_count === 0 && wallet) ? `
                                            <div class="alert alert-success mb-0">
                                                <i class="bi bi-check-circle"></i> <span data-i18n="all_good">All good! No alerts at this time.</span>
                                            </div>
                                        ` : ''}
                                    </div>
                                </div>
                            </div>
                        `;
                    case 'system_wide_statistics':
                        return `
                            <div class="${colClass} mb-3">
                                <div class="card">
                                    <div class="card-header">
                                        <h5 class="mb-0">
                                            <i class="bi bi-globe"></i> 
                                            <span data-i18n="system_wide_statistics">System-Wide Statistics</span>
                                            <i class="bi bi-info-circle ms-2" 
                                               data-bs-toggle="tooltip" 
                                               data-bs-placement="top" 
                                               data-bs-html="true"
                                               data-i18n-tooltip="widget_info_system_wide_statistics"
                                               style="cursor: help; font-size: 0.9em; opacity: 0.7;"></i>
                                        </h5>
                                    </div>
                                    <div class="card-body">
                                        <div class="row text-center">
                                            <div class="col-6 col-md-3 mb-3">
                                                <div class="border rounded p-3">
                                                    <div class="h4 mb-1 text-primary">${systemStats.total_users || 0}</div>
                                                    <small class="text-muted" data-i18n="total_users">Total Users</small>
                                                </div>
                                            </div>
                                            <div class="col-6 col-md-3 mb-3">
                                                <div class="border rounded p-3">
                                                    <div class="h4 mb-1 text-success">${systemStats.total_domains || 0}</div>
                                                    <small class="text-muted" data-i18n="total_domains">Total Domains</small>
                                                </div>
                                            </div>
                                            <div class="col-6 col-md-3 mb-3">
                                                <div class="border rounded p-3">
                                                    <div class="h4 mb-1 text-info">${systemStats.active_domains || 0}</div>
                                                    <small class="text-muted" data-i18n="active_mining">Active Mining</small>
                                                </div>
                                            </div>
                                            <div class="col-6 col-md-3 mb-3">
                                                <div class="border rounded p-3">
                                                    <div class="h4 mb-1 text-warning">${systemStats.total_rewards_distributed ? systemStats.total_rewards_distributed.toFixed(2) : '0.00'}</div>
                                                    <small class="text-muted" data-i18n="total_distributed">Total Distributed</small>
                                                </div>
                                            </div>
                                        </div>
                                        <hr>
                                        <div class="row text-center">
                                            <div class="col-6 col-md-4 mb-2">
                                                <small class="text-muted" data-i18n="verified_domains">Verified Domains</small>
                                                <div class="h6 mb-0">${systemStats.verified_domains || 0}</div>
                                            </div>
                                            <div class="col-6 col-md-4 mb-2">
                                                <small class="text-muted" data-i18n="successful_txs">Successful TXs</small>
                                                <div class="h6 mb-0 text-success">${systemStats.successful_transactions || 0}</div>
                                            </div>
                                            <div class="col-6 col-md-4 mb-2">
                                                <small class="text-muted" data-i18n="failed_txs">Failed TXs</small>
                                                <div class="h6 mb-0 text-danger">${systemStats.failed_transactions || 0}</div>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        `;
                    case 'mining_performance':
                        return `
                            <div class="${colClass} mb-3">
                                <div class="card">
                                    <div class="card-header">
                                        ${renderWidgetTitle('mining_performance', 'mining_performance', 'Mining Performance')}
                                    </div>
                                    <div class="card-body">
                                        <div class="row text-center mb-3">
                                            <div class="col-6 mb-2">
                                                <div class="border rounded p-2">
                                                    <div class="h5 mb-0 text-primary">${earnings.avg_daily ? earnings.avg_daily.toFixed(2) : '0.00'}</div>
                                                    <small class="text-muted" data-i18n="avg_daily_earnings">Avg Daily</small>
                                                </div>
                                            </div>
                                            <div class="col-6 mb-2">
                                                <div class="border rounded p-2">
                                                    <div class="h5 mb-0 text-info">${earnings.avg_weekly ? earnings.avg_weekly.toFixed(2) : '0.00'}</div>
                                                    <small class="text-muted" data-i18n="avg_weekly_earnings">Avg Weekly</small>
                                                </div>
                                            </div>
                                        </div>
                                        <hr>
                                        <div class="small">
                                            <p class="mb-1"><strong data-i18n="total_confirmed">Total Confirmed</strong>: ${earnings.total_confirmed ? earnings.total_confirmed.toFixed(2) : '0.00'} <span data-i18n="tokens">tokens</span></p>
                                            <p class="mb-1"><strong data-i18n="total_pending">Total Pending</strong>: ${earnings.total_pending ? earnings.total_pending.toFixed(2) : '0.00'} <span data-i18n="tokens">tokens</span></p>
                                            <p class="mb-0"><strong data-i18n="total_failed">Total Failed</strong>: ${earnings.total_failed ? earnings.total_failed.toFixed(2) : '0.00'} <span data-i18n="tokens">tokens</span></p>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        `;
                    case 'top_earning_domains':
                        return `
                            <div class="${colClass} mb-3">
                                <div class="card">
                                    <div class="card-header">
                                        ${renderWidgetTitle('top_earning_domains', 'top_earning_domains', 'Top Earning Domains')}
                                    </div>
                                    <div class="card-body p-0">
                                        ${Object.keys(earnings.earnings_by_domain || {}).length > 0 ? `
                                            <div class="list-group list-group-flush">
                                                ${Object.entries(earnings.earnings_by_domain).slice(0, 5).map(([domain, amount]) => `
                                                    <div class="list-group-item">
                                                        <div class="d-flex justify-content-between align-items-center">
                                                            <div>
                                                                <strong>${domain}</strong>
                                                            </div>
                                                            <div class="text-end">
                                                                <strong class="text-success">${amount.toFixed(2)}</strong> <span class="text-muted small" data-i18n="tokens">tokens</span>
                                                            </div>
                                                        </div>
                                                    </div>
                                                `).join('')}
                                            </div>
                                        ` : `
                                            <div class="card-body text-center text-muted">
                                                <p data-i18n="no_earnings_yet">No earnings yet</p>
                                            </div>
                                        `}
                                    </div>
                                </div>
                            </div>
                        `;
                    case 'earnings_charts':
                        return `
                            <div class="${colClass} mb-3">
                                <div class="card">
                                    <div class="card-header">
                                        <h5 class="mb-0">
                                            <span data-i18n="earnings_over_time">Earnings Over Time</span>
                                            <i class="bi bi-info-circle ms-2" 
                                               data-bs-toggle="tooltip" 
                                               data-bs-placement="top" 
                                               data-bs-html="true"
                                               data-i18n-tooltip="widget_info_earnings_charts"
                                               style="cursor: help; font-size: 0.9em; opacity: 0.7;"></i>
                                        </h5>
                                    </div>
                                    <div class="card-body">
                                        <div class="mb-4">
                                            <h6 class="mb-3" data-i18n="daily_earnings_chart">Daily Earnings (Last 30 Days)</h6>
                                            <div class="earnings-chart-container" style="height: 200px; position: relative;">
                                                ${this.renderDailyEarningsChart(earnings.daily_earnings || {})}
                                            </div>
                                        </div>
                                        <hr>
                                        <div>
                                            <h6 class="mb-3" data-i18n="weekly_earnings_chart">Weekly Earnings (Last 12 Weeks)</h6>
                                            <div class="earnings-chart-container" style="height: 200px; position: relative;">
                                                ${this.renderWeeklyEarningsChart(earnings.weekly_earnings || {})}
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        `;
                    case 'payout_settings':
                        return `
                            <div class="${colClass} mb-3">
                                <div class="card">
                                    <div class="card-header">
                                        ${renderWidgetTitle('payout_settings', 'payout_settings', 'Payout Settings')}
                                    </div>
                                    <div class="card-body">
                                        <p class="mb-2">
                                            <strong data-i18n="payout_mode">Payout Mode</strong>: 
                                            <span class="badge ${payouts.payout_mode === 'auto' ? 'bg-success' : 'bg-secondary'}" data-i18n-dynamic="${payouts.payout_mode === 'auto' ? 'payout_mode_auto' : 'payout_mode_manual'}"></span>
                                        </p>
                                        ${payouts.payout_threshold ? `
                                            <p class="mb-2">
                                                <strong data-i18n="auto_payout_threshold">Auto Payout Threshold</strong>: 
                                                ${payouts.payout_threshold.toFixed(2)} <span data-i18n="tokens">tokens</span>
                                            </p>
                                        ` : ''}
                                        ${payouts.last_payout_at ? `
                                            <p class="mb-2">
                                                <strong data-i18n="last_payout">Last Payout</strong>: 
                                                ${new Date(payouts.last_payout_at).toLocaleDateString()}
                                            </p>
                                        ` : '<p class="text-muted mb-2" data-i18n="no_payouts_yet">No payouts yet</p>'}
                                        ${payouts.pending_payout > 0 ? `
                                            <p class="mb-2 text-warning">
                                                <strong data-i18n="pending_payout">Pending Payout</strong>: 
                                                ${payouts.pending_payout.toFixed(2)} <span data-i18n="tokens">tokens</span>
                                            </p>
                                        ` : ''}
                                    </div>
                                </div>
                            </div>
                        `;
                    case 'payout_history':
                        return `
                            <div class="${colClass} mb-3">
                                <div class="card">
                                    <div class="card-header">
                                        <h5 class="mb-0" data-i18n="payout_history">Payout History</h5>
                                    </div>
                                    <div class="card-body p-0">
                                        ${payouts.payouts && payouts.payouts.length > 0 ? `
                                            <div class="list-group list-group-flush">
                                                ${payouts.payouts.slice(0, 5).map(p => `
                                                    <div class="list-group-item">
                                                        <div class="d-flex justify-content-between align-items-center">
                                                            <div>
                                                                <strong>${p.amount.toFixed(2)}</strong> <span data-i18n="tokens">tokens</span>
                                                                <br>
                                                                <small class="text-muted">${p.created_at ? new Date(p.created_at).toLocaleString() : ''}</small>
                                                                ${p.triggered_by ? `<br><small class="text-muted" data-i18n="triggered_by">Triggered by</small>: <span data-i18n-dynamic="${p.triggered_by === 'auto' ? 'payout_mode_auto' : 'payout_mode_manual'}"></span>` : ''}
                                                            </div>
                                                            <div class="text-end">
                                                                <span class="badge ${p.status === 'completed' ? 'bg-success' : p.status === 'failed' ? 'bg-danger' : p.status === 'processing' ? 'bg-warning' : 'bg-secondary'}" data-i18n-dynamic="${p.status === 'completed' ? 'status_completed' : p.status === 'failed' ? 'status_failed' : p.status === 'processing' ? 'status_processing' : 'status_pending'}"></span>
                                                                ${p.tx_id ? `<br><small><a href="https://wavesexplorer.com/tx/${p.tx_id}" target="_blank" class="text-decoration-none" title="View on Waves Explorer"><i class="bi bi-box-arrow-up-right"></i> <code class="small">${p.tx_id.substring(0, 10)}...</code></a></small>` : ''}
                                                            </div>
                                                        </div>
                                                    </div>
                                                `).join('')}
                                            </div>
                                        ` : `
                                            <div class="card-body text-center text-muted">
                                                <p data-i18n="no_payouts_yet">No payouts yet</p>
                                            </div>
                                        `}
                                    </div>
                                </div>
                            </div>
                        `;
                    case 'recent_rewards':
                        return `
                            <div class="${colClass} mb-3">
                                <div class="card">
                                    <div class="card-header">
                                        ${renderWidgetTitle('recent_rewards', 'recent_rewards', 'Recent Rewards')}
                                    </div>
                                    <div class="card-body p-0">
                                        ${rewards.rewards && rewards.rewards.length > 0 ? `
                                            <div class="list-group list-group-flush">
                                                ${rewards.rewards.slice(0, 10).map(r => `
                                                    <div class="list-group-item">
                                                        <div class="d-flex justify-content-between align-items-center">
                                                            <div>
                                                                <strong>${r.is_lottery ? '<span data-i18n="lottery_bonus">Solo Random Drop</span>' : (r.domain || 'N/A')}</strong>
                                                                ${r.is_lottery ? '<br><small class="text-muted">🎲</small>' : ''}
                                                                <br>
                                                                <small class="text-muted">${r.created_at ? new Date(r.created_at).toLocaleString() : ''}</small>
                                                            </div>
                                                            <div class="text-end">
                                                                <span class="badge ${r.status === 'confirmed' ? 'bg-success' : r.status === 'failed' ? 'bg-danger' : r.status === 'accumulated' ? 'bg-info' : 'bg-warning'}" data-i18n-dynamic="${r.status === 'confirmed' ? 'status_confirmed' : r.status === 'failed' ? 'status_failed' : r.status === 'accumulated' ? 'status_accumulated' : 'status_pending'}"></span>
                                                                <br>
                                                                <strong class="text-success">+${r.amount.toFixed(4)}</strong>
                                                            </div>
                                                        </div>
                                                    </div>
                                                `).join('')}
                                            </div>
                                        ` : `
                                            <div class="card-body text-center text-muted">
                                                <p data-i18n="no_rewards_yet">No rewards yet</p>
                                            </div>
                                        `}
                                    </div>
                                </div>
                            </div>
                        `;
                    case 'recent_domains':
                        return `
                            <div class="${colClass} mb-3">
                                <div class="card">
                                    <div class="card-header d-flex justify-content-between align-items-center">
                                        <h5 class="mb-0">
                                            <span data-i18n="your_domains">Your Domains</span>
                                            <i class="bi bi-info-circle ms-2" 
                                               data-bs-toggle="tooltip" 
                                               data-bs-placement="top" 
                                               data-bs-html="true"
                                               data-i18n-tooltip="widget_info_recent_domains"
                                               style="cursor: help; font-size: 0.9em; opacity: 0.7;"></i>
                                        </h5>
                                        <a href="/domains" class="btn btn-sm btn-outline-primary" onclick="event.preventDefault(); router.navigate('/domains');" data-i18n="view_all_domains">View All</a>
                                    </div>
                                    <div class="card-body p-0">
                                        <div class="list-group list-group-flush">
                                            ${domainsList}
                                        </div>
                                        ${domains.domains && domains.domains.length === 0 ? `
                                            <div class="card-body text-center">
                                                <p class="text-muted mb-3" data-i18n="you_have_no_domains">You don't have any domains yet.</p>
                                                <a href="/domains" class="btn btn-primary" onclick="event.preventDefault(); router.navigate('/domains');" data-i18n="add_domain">Add Domain</a>
                                            </div>
                                        ` : ''}
                                    </div>
                                </div>
                            </div>
                        `;
                    default:
                        return '';
                }
            };
            
            // Group widgets by width and render them
            const widgetOrder = ['account_info', 'your_statistics', 'domain_health_warnings', 'quick_alerts', 
                                'system_wide_statistics', 'mining_performance', 'top_earning_domains', 
                                'earnings_charts', 'payout_settings', 'payout_history', 'recent_rewards', 'recent_domains'];
            
            let widgetHTML = '';
            let currentRow = [];
            
            for (const widgetId of widgetOrder) {
                if (!enabledWidgets.includes(widgetId)) continue;
                
                const widgetContent = renderWidget(widgetId);
                if (!widgetContent) continue; // Skip if widget returns empty (e.g., conditional widgets)
                
                const width = this.widgetWidths[widgetId] || 'half';
                
                if (width === 'full') {
                    // Close current row if any
                    if (currentRow.length > 0) {
                        widgetHTML += `<div class="row mb-4">${currentRow.join('')}</div>`;
                        currentRow = [];
                    }
                    // Full-width widget gets its own row
                    widgetHTML += `<div class="row mb-4">${widgetContent}</div>`;
                } else {
                    // Half-width widget - add to current row
                    currentRow.push(widgetContent);
                    // If row is full (2 widgets), close it
                    if (currentRow.length >= 2) {
                        widgetHTML += `<div class="row mb-4">${currentRow.join('')}</div>`;
                        currentRow = [];
                    }
                }
            }
            
            // Close any remaining widgets in current row
            if (currentRow.length > 0) {
                widgetHTML += `<div class="row mb-4">${currentRow.join('')}</div>`;
            }
            
            main.innerHTML = `
                <div class="mb-4">
                    <h2 class="mb-3" data-i18n="dashboard">Dashboard</h2>
                    <p class="text-muted" data-i18n="welcome_description">Start earning tokens by owning domains.</p>
                </div>
                
                <!-- Stats Cards (Core Widgets - Always Visible) -->
                <div class="row mb-4">
                    <div class="col-md-4 mb-3">
                        <div class="card h-100">
                            <div class="card-body">
                                <h5 class="card-title">
                                    <span data-i18n="your_mining_balance">Your Mining Balance</span>
                                    <i class="bi bi-info-circle ms-2" 
                                       data-bs-toggle="tooltip" 
                                       data-bs-placement="top" 
                                       data-bs-html="true"
                                       data-i18n-tooltip="widget_info_mining_balance"
                                       style="cursor: help; font-size: 0.9em; opacity: 0.7;"></i>
                                </h5>
                                <h2 class="text-primary">${balance.accumulated_balance ? balance.accumulated_balance.toFixed(2) : '0.00'}</h2>
                                <p class="text-muted mb-2" data-i18n="tokens">tokens</p>
                                ${balance.pending_payout > 0 ? `<small class="text-warning d-block"><span data-i18n="pending_payout">Pending Payout</span>: ${balance.pending_payout.toFixed(2)}</small>` : ''}
                                <div class="mt-3">
                                    <a href="/withdraw" class="btn btn-sm btn-primary" onclick="event.preventDefault(); router.navigate('/withdraw');" data-i18n="request_withdrawal">Withdraw</a>
                                </div>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-4 mb-3">
                        <div class="card h-100">
                            <div class="card-body">
                                <h5 class="card-title">
                                    <span data-i18n="domains_total">Total Domains</span>
                                    <i class="bi bi-info-circle ms-2" 
                                       data-bs-toggle="tooltip" 
                                       data-bs-placement="top" 
                                       data-bs-html="true"
                                       data-i18n-tooltip="widget_info_total_domains"
                                       style="cursor: help; font-size: 0.9em; opacity: 0.7;"></i>
                                </h5>
                                <h2 class="text-success">${stats.domains_count || 0}</h2>
                                <p class="text-muted mb-2">
                                    ${stats.active_mining || 0} <span data-i18n="domains_mining">mining</span>
                                    ${stats.domains_count > 0 ? ` / ${stats.domains_count - (stats.active_mining || 0)} <span data-i18n="domain_status_not_verified">not verified</span>` : ''}
                                </p>
                                <div class="mt-3">
                                    <a href="/domains" class="btn btn-sm btn-success" onclick="event.preventDefault(); router.navigate('/domains');" data-i18n="your_domains">View Domains</a>
                                </div>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-4 mb-3">
                        <div class="card h-100">
                            <div class="card-body">
                                <h5 class="card-title">
                                    <span data-i18n="rewards_earned">Total Earned</span>
                                    <i class="bi bi-info-circle ms-2" 
                                       data-bs-toggle="tooltip" 
                                       data-bs-placement="top" 
                                       data-bs-html="true"
                                       data-i18n-tooltip="widget_info_total_earned"
                                       style="cursor: help; font-size: 0.9em; opacity: 0.7;"></i>
                                </h5>
                                <h2 class="text-info">${stats.total_earned ? stats.total_earned.toFixed(2) : '0.00'}</h2>
                                <p class="text-muted" data-i18n="tokens">tokens</p>
                            </div>
                        </div>
                    </div>
                </div>
                
                ${widgetHTML}
            `;
            // Wait a bit to ensure DOM is ready and translations are loaded
            // Call updateI18n multiple times to catch any delayed DOM updates
            setTimeout(() => {
                this.updateI18n();
                this.initializeTooltips();
            }, 10);
            setTimeout(() => {
                this.updateI18n();
                this.initializeTooltips();
            }, 100);
            setTimeout(() => {
                this.updateI18n();
                this.initializeTooltips();
            }, 300);
        } catch (error) {
            console.error('[App] ===== LOAD DASHBOARD ERROR =====');
            console.error('[App] Unexpected error loading dashboard:', error);
            console.error('[App] Error message:', error.message);
            console.error('[App] Error stack:', error.stack);
            
            main.innerHTML = `
                <div class="alert alert-danger">
                    <h4 data-i18n="failed_to_load_dashboard">Failed to Load Dashboard</h4>
                    <p>${error.message || i18n.t('unknown_error') || 'Unknown error occurred'}</p>
                    <button class="btn btn-primary" onclick="location.reload()" data-i18n="reload">Reload</button>
                </div>
            `;
        }
    };

})();
