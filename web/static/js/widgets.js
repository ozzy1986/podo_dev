/**
 * Widgets Module
 * Widget management, preferences, toggle UI
 */
(function() {
    'use strict';

    App.prototype.getEnabledWidgets = async function() {
        // Return cached value if available
        if (this._cachedEnabledWidgets) {
            return [...this._cachedEnabledWidgets];
        }
        try {
            const response = await api.getWidgetPreferences();
            if (response && response.enabled_widgets) {
                this._cachedEnabledWidgets = response.enabled_widgets;
                return [...response.enabled_widgets];
            }
        } catch (e) {
            console.error('[App] Error fetching widget preferences:', e);
        }
        // Default: only core widgets enabled
        return [...this.coreWidgets];
    };

    App.prototype.invalidateWidgetCache = function() {
        this._cachedEnabledWidgets = null;
    };

    App.prototype.setWidgetEnabled = async function(widgetId, enabled) {
        const enabledWidgets = await this.getEnabledWidgets();
        if (enabled) {
            if (!enabledWidgets.includes(widgetId)) {
                enabledWidgets.push(widgetId);
            }
        } else {
            const index = enabledWidgets.indexOf(widgetId);
            if (index > -1 && !this.coreWidgets.includes(widgetId)) {
                enabledWidgets.splice(index, 1);
            }
        }
        
        try {
            await api.setWidgetPreferences(enabledWidgets);
            // Update cache with the new value
            this._cachedEnabledWidgets = [...enabledWidgets];
            return enabledWidgets;
        } catch (e) {
            console.error('[App] Error saving widget preferences:', e);
            // Invalidate cache on error so next read fetches fresh data
            this.invalidateWidgetCache();
            throw e;
        }
    };

    App.prototype.isWidgetEnabled = async function(widgetId) {
        const enabledWidgets = await this.getEnabledWidgets();
        return enabledWidgets.includes(widgetId);
    };

    App.prototype.showWidgets = async function() {
        const main = document.getElementById('main-content');
        if (!main) {
            console.error('[App] Main content element not found!');
            return;
        }
        
        // Ensure translations are loaded before rendering
        await i18n.loadLanguage(i18n.getCurrentLanguage());

        // Show loading state
        main.innerHTML = `
            <div class="text-center">
                <div class="spinner-border text-primary" role="status">
                    <span class="visually-hidden" data-i18n="loading">Loading...</span>
                </div>
            </div>
        `;
        this.updateI18n();

        // Initialize defaults
        let balance = { accumulated_balance: 0, accumulated_units: 0, payout_mode: 'manual', pending_payout: 0 };
        let stats = { domains_count: 0, active_mining: 0, total_earned: 0, accumulated_balance: 0 };
        let domains = { domains: [], count: 0 };
        let rewards = { rewards: [], count: 0 };
        let payouts = { payouts: [], payouts_count: 0, payout_mode: 'manual', payout_threshold: null, last_payout_at: null, pending_payout: 0 };
        let domainHealth = { expiring_soon: [], failed_checks: [], needs_verification: [], healthy: [], total_domains: 0 };
        let earnings = { daily_earnings: {}, weekly_earnings: {}, avg_daily: 0, avg_weekly: 0, earnings_by_domain: {}, total_confirmed: 0, total_pending: 0, total_failed: 0 };
        let systemStats = { total_domains: 0, active_domains: 0, verified_domains: 0, total_users: 0, total_rewards_distributed: 0, successful_transactions: 0, failed_transactions: 0 };

        try {
            // Try combined dashboard endpoint first (1 request instead of 9)
            let usedCombinedEndpoint = false;
            let enabledWidgets = [...this.coreWidgets];

            try {
                const dashboardData = await api.getDashboard();
                if (dashboardData && !dashboardData.error) {
                    usedCombinedEndpoint = true;
                    console.log('[App] Widgets page loaded via combined endpoint');
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
                }
            } catch (combinedError) {
                console.warn('[App] Combined endpoint failed for widgets, falling back:', combinedError.message);
            }

            // Fallback to individual API calls if combined endpoint failed
            if (!usedCombinedEndpoint) {
                console.log('[App] Widgets page using fallback: individual API calls');
                const results = await Promise.allSettled([
                    api.getBalance().catch(e => { console.error('[App] Balance fetch failed:', e); return null; }),
                    api.getUserStats().catch(e => { console.error('[App] Stats fetch failed:', e); return null; }),
                    api.getDomains().catch(e => { console.error('[App] Domains fetch failed:', e); return null; }),
                    api.getRewards().catch(e => { console.error('[App] Rewards fetch failed:', e); return null; }),
                    api.getPayouts().catch(e => { console.error('[App] Payouts fetch failed:', e); return null; }),
                    api.getDomainHealth().catch(e => { console.error('[App] Domain health fetch failed:', e); return null; }),
                    api.getEarnings().catch(e => { console.error('[App] Earnings fetch failed:', e); return null; }),
                    api.getStats().catch(e => { console.error('[App] System stats fetch failed:', e); return null; })
                ]);

                if (results[0].status === 'fulfilled' && results[0].value) balance = results[0].value;
                if (results[1].status === 'fulfilled' && results[1].value) stats = results[1].value;
                if (results[2].status === 'fulfilled' && results[2].value) domains = results[2].value;
                if (results[3].status === 'fulfilled' && results[3].value) rewards = results[3].value;
                if (results[4].status === 'fulfilled' && results[4].value) payouts = results[4].value;
                if (results[5].status === 'fulfilled' && results[5].value) domainHealth = results[5].value;
                if (results[6].status === 'fulfilled' && results[6].value) earnings = results[6].value;
                if (results[7].status === 'fulfilled' && results[7].value) systemStats = results[7].value;
                enabledWidgets = await this.getEnabledWidgets();
            }

            // Update widget cache with fetched data
            this._cachedEnabledWidgets = [...enabledWidgets];

            const username = this.user?.username || 'User';
            const wallet = this.user?.wallet || null;
            const email = this.user?.email || null;

            // Format domains list
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

            // Helper function to render widget header with toggle
            const renderWidgetHeader = (widgetId, titleKey, titleText) => {
                const isEnabled = enabledWidgets.includes(widgetId);
                const isCore = this.coreWidgets.includes(widgetId);
                const bgClass = isEnabled ? 'bg-success' : 'bg-warning';
                const icon = isEnabled ? 'bi-check-circle-fill' : 'bi-x-circle-fill';
                const clickable = isCore ? '' : `onclick="app.toggleWidget('${widgetId}')" style="cursor: pointer;"`;
                const disabled = isCore ? 'opacity: 0.6; cursor: not-allowed;' : '';
                
                const styleAttr = disabled ? `style="${disabled}"` : '';
                const infoKey = `widget_info_${widgetId}`;
                return `
                    <div class="card-header ${bgClass} text-white d-flex justify-content-between align-items-center" ${clickable} ${styleAttr} data-widget-id="${widgetId}">
                        <h5 class="mb-0">
                            <i class="bi ${icon}"></i> 
                            <span data-i18n="${titleKey}">${titleText}</span>
                            <i class="bi bi-info-circle ms-2" 
                               data-bs-toggle="tooltip" 
                               data-bs-placement="top" 
                               data-bs-html="true"
                               data-i18n-tooltip="${infoKey}"
                               style="cursor: help; font-size: 0.9em; opacity: 0.8;"></i>
                        </h5>
                        <small>${isCore ? '<span data-i18n="core_widget">Core Widget</span>' : '<span data-i18n="dashboard">Dashboard</span>'}</small>
                    </div>
                `;
            };

            main.innerHTML = `
                <div class="mb-4">
                    <h2 class="mb-3" data-i18n="widgets">Widgets</h2>
                    <p class="text-muted" data-i18n="widgets_description">Manage which widgets appear on your dashboard. Click the header to toggle.</p>
                </div>

                <!-- Account Info Widget -->
                <div class="row mb-4">
                    <div class="${this.widgetWidths['account_info'] === 'full' ? 'col-12' : 'col-md-6'} mb-3">
                        <div class="card">
                            ${renderWidgetHeader('account_info', 'account_info', 'Account Info')}
                            <div class="card-body">
                                <p class="mb-2"><strong data-i18n="username">Username</strong>: ${username}</p>
                                ${email ? `<p class="mb-2"><strong data-i18n="email">Email</strong>: ${email}</p>` : ''}
                                ${wallet ? `<p class="mb-2"><strong data-i18n="wallet_address">Wallet</strong>: <code class="small">${wallet}</code></p>` : `<p class="text-warning mb-2" data-i18n="please_set_wallet">Please set your wallet first</p>`}
                                ${!wallet ? `<a href="/wallet" class="btn btn-sm btn-primary" onclick="event.preventDefault(); router.navigate('/wallet');" data-i18n="set_wallet">Set Wallet</a>` : ''}
                            </div>
                        </div>
                    </div>
                    <div class="${this.widgetWidths['your_statistics'] === 'full' ? 'col-12' : 'col-md-6'} mb-3">
                        <div class="card">
                            ${renderWidgetHeader('your_statistics', 'your_statistics', 'Your Statistics')}
                            <div class="card-body">
                                <div class="row text-center">
                                    <div class="col-6 mb-2"><div class="border rounded p-2"><div class="h4 mb-0 text-success">${stats.domains_count || 0}</div><small class="text-muted" data-i18n="domains_total">Total</small></div></div>
                                    <div class="col-6 mb-2"><div class="border rounded p-2"><div class="h4 mb-0 text-info">${stats.active_mining || 0}</div><small class="text-muted" data-i18n="domains_mining">Mining</small></div></div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Domain Health Warnings Widget -->
                <div class="row mb-4">
                    <div class="${this.widgetWidths['domain_health_warnings'] === 'full' ? 'col-12' : 'col-md-6'} mb-3">
                        <div class="card border-warning">
                            ${renderWidgetHeader('domain_health_warnings', 'domain_health_alerts', 'Domain Health Alerts')}
                            <div class="card-body">
                                ${(domainHealth.expiring_count > 0 || domainHealth.failed_count > 0 || domainHealth.needs_verification_count > 0) ? `
                                    ${domainHealth.expiring_count > 0 ? `<div class="alert alert-warning mb-2"><strong data-i18n="domains_expiring_soon">Domains Expiring Soon</strong> (${domainHealth.expiring_count})<ul class="mb-0 mt-2">${domainHealth.expiring_soon.slice(0, 5).map(d => `<li>${d.domain} - <span>${i18n.t('expires_in_days').replace('{days}', d.days_until_expiry)}</span></li>`).join('')}</ul></div>` : ''}
                                    ${domainHealth.failed_count > 0 ? `<div class="alert alert-danger mb-2"><strong data-i18n="domains_with_failed_checks">Domains with Failed Checks</strong> (${domainHealth.failed_count})<ul class="mb-0 mt-2">${domainHealth.failed_checks.slice(0, 5).map(d => `<li>${d.domain} - <span>${i18n.t('failed_checks_count').replace('{count}', d.failed_checks)}</span></li>`).join('')}</ul></div>` : ''}
                                    ${domainHealth.needs_verification_count > 0 ? `<div class="alert alert-info mb-2"><strong data-i18n="domains_needing_verification">Domains Needing Verification</strong> (${domainHealth.needs_verification_count})<ul class="mb-0 mt-2">${domainHealth.needs_verification.slice(0, 5).map(d => `<li>${d.domain}</li>`).join('')}</ul></div>` : ''}
                                    <a href="/domains" class="btn btn-sm btn-primary" onclick="event.preventDefault(); router.navigate('/domains');" data-i18n="manage_domains">Manage Domains</a>
                                ` : `<p class="text-muted mb-0" data-i18n="no_domain_issues">No domain health issues at this time.</p>`}
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Quick Alerts Widget -->
                <div class="row mb-4">
                    <div class="${this.widgetWidths['quick_alerts'] === 'full' ? 'col-12' : 'col-md-6'} mb-3">
                        <div class="card border-primary">
                            ${renderWidgetHeader('quick_alerts', 'quick_alerts', 'Quick Alerts')}
                            <div class="card-body">
                                ${!wallet ? `<div class="alert alert-warning mb-2"><i class="bi bi-exclamation-triangle"></i> <strong data-i18n="wallet_not_set">Wallet not set</strong> - <a href="/wallet" onclick="event.preventDefault(); router.navigate('/wallet');" data-i18n="set_wallet">Set your wallet</a> to receive payouts</div>` : ''}
                                ${payouts.pending_payout > 0 ? `<div class="alert alert-info mb-2"><i class="bi bi-clock-history"></i> <strong data-i18n="pending_payout_alert">Pending Payout</strong>: ${payouts.pending_payout.toFixed(2)} <span data-i18n="tokens">tokens</span> - <span data-i18n="processing">Processing</span></div>` : ''}
                                ${domainHealth.expiring_count > 0 ? `<div class="alert alert-warning mb-2"><i class="bi bi-calendar-x"></i> <strong data-i18n="domains_expiring_soon">Domains Expiring Soon</strong>: ${domainHealth.expiring_count} <span data-i18n="domains">domains</span> need attention</div>` : ''}
                                ${domainHealth.failed_count > 0 ? `<div class="alert alert-danger mb-2"><i class="bi bi-x-circle"></i> <strong data-i18n="domains_with_failed_checks">Domains with Failed Checks</strong>: ${domainHealth.failed_count} <span data-i18n="domains">domains</span> need verification</div>` : ''}
                                ${domainHealth.needs_verification_count > 0 ? `<div class="alert alert-info mb-2"><i class="bi bi-check-circle"></i> <strong data-i18n="domains_needing_verification">Domains Needing Verification</strong>: ${domainHealth.needs_verification_count} <span data-i18n="domains">domains</span> pending verification</div>` : ''}
                                ${(payouts.pending_payout === 0 && domainHealth.expiring_count === 0 && domainHealth.failed_count === 0 && domainHealth.needs_verification_count === 0 && wallet) ? `<div class="alert alert-success mb-0"><i class="bi bi-check-circle"></i> <span data-i18n="all_good">All good! No alerts at this time.</span></div>` : ''}
                            </div>
                        </div>
                    </div>
                </div>

                <!-- System-Wide Statistics Widget -->
                <div class="row mb-4">
                    <div class="${this.widgetWidths['system_wide_statistics'] === 'full' ? 'col-12' : 'col-md-6'} mb-3">
                        <div class="card">
                            ${renderWidgetHeader('system_wide_statistics', 'system_wide_statistics', 'System-Wide Statistics')}
                            <div class="card-body">
                                <div class="row text-center">
                                    <div class="col-6 col-md-3 mb-3"><div class="border rounded p-3"><div class="h4 mb-1 text-primary">${systemStats.total_users || 0}</div><small class="text-muted" data-i18n="total_users">Total Users</small></div></div>
                                    <div class="col-6 col-md-3 mb-3"><div class="border rounded p-3"><div class="h4 mb-1 text-success">${systemStats.total_domains || 0}</div><small class="text-muted" data-i18n="total_domains">Total Domains</small></div></div>
                                    <div class="col-6 col-md-3 mb-3"><div class="border rounded p-3"><div class="h4 mb-1 text-info">${systemStats.active_domains || 0}</div><small class="text-muted" data-i18n="active_mining">Active Mining</small></div></div>
                                    <div class="col-6 col-md-3 mb-3"><div class="border rounded p-3"><div class="h4 mb-1 text-warning">${systemStats.total_rewards_distributed ? systemStats.total_rewards_distributed.toFixed(2) : '0.00'}</div><small class="text-muted" data-i18n="total_distributed">Total Distributed</small></div></div>
                                </div>
                                <hr>
                                <div class="row text-center">
                                    <div class="col-6 col-md-4 mb-2"><small class="text-muted" data-i18n="verified_domains">Verified Domains</small><div class="h6 mb-0">${systemStats.verified_domains || 0}</div></div>
                                    <div class="col-6 col-md-4 mb-2"><small class="text-muted" data-i18n="successful_txs">Successful TXs</small><div class="h6 mb-0 text-success">${systemStats.successful_transactions || 0}</div></div>
                                    <div class="col-6 col-md-4 mb-2"><small class="text-muted" data-i18n="failed_txs">Failed TXs</small><div class="h6 mb-0 text-danger">${systemStats.failed_transactions || 0}</div></div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Mining Performance Widgets -->
                <div class="row mb-4">
                    <div class="${this.widgetWidths['mining_performance'] === 'full' ? 'col-12' : 'col-md-6'} mb-3">
                        <div class="card">
                            ${renderWidgetHeader('mining_performance', 'mining_performance', 'Mining Performance')}
                            <div class="card-body">
                                <div class="row text-center mb-3">
                                    <div class="col-6 mb-2"><div class="border rounded p-2"><div class="h5 mb-0 text-primary">${earnings.avg_daily ? earnings.avg_daily.toFixed(2) : '0.00'}</div><small class="text-muted" data-i18n="avg_daily_earnings">Avg Daily</small></div></div>
                                    <div class="col-6 mb-2"><div class="border rounded p-2"><div class="h5 mb-0 text-info">${earnings.avg_weekly ? earnings.avg_weekly.toFixed(2) : '0.00'}</div><small class="text-muted" data-i18n="avg_weekly_earnings">Avg Weekly</small></div></div>
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
                    <div class="${this.widgetWidths['top_earning_domains'] === 'full' ? 'col-12' : 'col-md-6'} mb-3">
                        <div class="card">
                            ${renderWidgetHeader('top_earning_domains', 'top_earning_domains', 'Top Earning Domains')}
                            <div class="card-body p-0">
                                ${Object.keys(earnings.earnings_by_domain || {}).length > 0 ? `<div class="list-group list-group-flush">${Object.entries(earnings.earnings_by_domain).slice(0, 5).map(([domain, amount]) => `<div class="list-group-item"><div class="d-flex justify-content-between align-items-center"><div><strong>${domain}</strong></div><div class="text-end"><strong class="text-success">${amount.toFixed(2)}</strong> <span class="text-muted small" data-i18n="tokens">tokens</span></div></div></div>`).join('')}</div>` : `<div class="card-body text-center text-muted"><p data-i18n="no_earnings_yet">No earnings yet</p></div>`}
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Earnings Charts Widget -->
                <div class="row mb-4">
                    <div class="${this.widgetWidths['earnings_charts'] === 'full' ? 'col-12' : 'col-md-6'} mb-3">
                        <div class="card">
                            ${renderWidgetHeader('earnings_charts', 'earnings_over_time', 'Earnings Over Time')}
                            <div class="card-body">
                                <div class="mb-4"><h6 class="mb-3" data-i18n="daily_earnings_chart">Daily Earnings (Last 30 Days)</h6><div class="earnings-chart-container" style="height: 200px; position: relative;">${this.renderDailyEarningsChart(earnings.daily_earnings || {})}</div></div>
                                <hr>
                                <div><h6 class="mb-3" data-i18n="weekly_earnings_chart">Weekly Earnings (Last 12 Weeks)</h6><div class="earnings-chart-container" style="height: 200px; position: relative;">${this.renderWeeklyEarningsChart(earnings.weekly_earnings || {})}</div></div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Payout Widgets -->
                <div class="row mb-4">
                    <div class="${this.widgetWidths['payout_settings'] === 'full' ? 'col-12' : 'col-md-6'} mb-3">
                        <div class="card">
                            ${renderWidgetHeader('payout_settings', 'payout_settings', 'Payout Settings')}
                            <div class="card-body">
                                <p class="mb-2"><strong data-i18n="payout_mode">Payout Mode</strong>: <span class="badge ${payouts.payout_mode === 'auto' ? 'bg-success' : 'bg-secondary'}" data-i18n-dynamic="${payouts.payout_mode === 'auto' ? 'payout_mode_auto' : 'payout_mode_manual'}"></span></p>
                                ${payouts.payout_threshold ? `<p class="mb-2"><strong data-i18n="auto_payout_threshold">Auto Payout Threshold</strong>: ${payouts.payout_threshold.toFixed(2)} <span data-i18n="tokens">tokens</span></p>` : ''}
                                ${payouts.last_payout_at ? `<p class="mb-2"><strong data-i18n="last_payout">Last Payout</strong>: ${new Date(payouts.last_payout_at).toLocaleDateString()}</p>` : '<p class="text-muted mb-2" data-i18n="no_payouts_yet">No payouts yet</p>'}
                                ${payouts.pending_payout > 0 ? `<p class="mb-2 text-warning"><strong data-i18n="pending_payout">Pending Payout</strong>: ${payouts.pending_payout.toFixed(2)} <span data-i18n="tokens">tokens</span></p>` : ''}
                            </div>
                        </div>
                    </div>
                    <div class="${this.widgetWidths['payout_history'] === 'full' ? 'col-12' : 'col-md-6'} mb-3">
                        <div class="card">
                            ${renderWidgetHeader('payout_history', 'payout_history', 'Payout History')}
                            <div class="card-body p-0">
                                ${payouts.payouts && payouts.payouts.length > 0 ? `<div class="list-group list-group-flush">${payouts.payouts.slice(0, 5).map(p => `<div class="list-group-item"><div class="d-flex justify-content-between align-items-center"><div><strong>${p.amount.toFixed(2)}</strong> <span data-i18n="tokens">tokens</span><br><small class="text-muted">${p.created_at ? new Date(p.created_at).toLocaleString() : ''}</small>${p.triggered_by ? `<br><small class="text-muted" data-i18n="triggered_by">Triggered by</small>: <span data-i18n-dynamic="${p.triggered_by === 'auto' ? 'payout_mode_auto' : 'payout_mode_manual'}"></span>` : ''}</div><div class="text-end"><span class="badge ${p.status === 'completed' ? 'bg-success' : p.status === 'failed' ? 'bg-danger' : p.status === 'processing' ? 'bg-warning' : 'bg-secondary'}" data-i18n-dynamic="${p.status === 'completed' ? 'status_completed' : p.status === 'failed' ? 'status_failed' : p.status === 'processing' ? 'status_processing' : 'status_pending'}"></span>${p.tx_id ? `<br><small><a href="https://wavesexplorer.com/tx/${p.tx_id}" target="_blank" class="text-decoration-none" title="View on Waves Explorer"><i class="bi bi-box-arrow-up-right"></i> <code class="small">${p.tx_id.substring(0, 10)}...</code></a></small>` : ''}</div></div></div>`).join('')}</div>` : `<div class="card-body text-center text-muted"><p data-i18n="no_payouts_yet">No payouts yet</p></div>`}
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Recent Rewards Widget -->
                <div class="row mb-4">
                    <div class="${this.widgetWidths['recent_rewards'] === 'full' ? 'col-12' : 'col-md-6'} mb-3">
                        <div class="card">
                            ${renderWidgetHeader('recent_rewards', 'recent_rewards', 'Recent Rewards')}
                            <div class="card-body p-0">
                                ${rewards.rewards && rewards.rewards.length > 0 ? `<div class="list-group list-group-flush">${rewards.rewards.slice(0, 10).map(r => `<div class="list-group-item"><div class="d-flex justify-content-between align-items-center"><div><strong>${r.domain}</strong><br><small class="text-muted">${r.created_at ? new Date(r.created_at).toLocaleString() : ''}</small></div><div class="text-end"><span class="badge ${r.status === 'confirmed' ? 'bg-success' : r.status === 'failed' ? 'bg-danger' : r.status === 'accumulated' ? 'bg-info' : 'bg-warning'}" data-i18n-dynamic="${r.status === 'confirmed' ? 'status_confirmed' : r.status === 'failed' ? 'status_failed' : r.status === 'accumulated' ? 'status_accumulated' : 'status_pending'}"></span><br><strong class="text-success">+${r.amount.toFixed(4)}</strong></div></div></div>`).join('')}</div>` : `<div class="card-body text-center text-muted"><p data-i18n="no_rewards_yet">No rewards yet</p></div>`}
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Recent Domains Widget -->
                <div class="row">
                    <div class="${this.widgetWidths['recent_domains'] === 'full' ? 'col-12' : 'col-md-6'} mb-3">
                        <div class="card">
                            ${renderWidgetHeader('recent_domains', 'your_domains', 'Your Domains')}
                            <div class="card-body p-0">
                                <div class="list-group list-group-flush">${domainsList}</div>
                                ${domains.domains && domains.domains.length === 0 ? `<div class="card-body text-center"><p class="text-muted mb-3" data-i18n="you_have_no_domains">You don't have any domains yet.</p><a href="/domains" class="btn btn-primary" onclick="event.preventDefault(); router.navigate('/domains');" data-i18n="add_domain">Add Domain</a></div>` : ''}
                            </div>
                        </div>
                    </div>
                </div>
            `;

            // Ensure translations are loaded before updating
            await i18n.loadLanguage(i18n.getCurrentLanguage());
            
            setTimeout(() => { this.updateI18n(); this.initializeTooltips(); }, 10);
            setTimeout(() => { this.updateI18n(); this.initializeTooltips(); }, 100);
            setTimeout(() => { this.updateI18n(); this.initializeTooltips(); }, 300);
        } catch (error) {
            console.error('[App] ===== SHOW WIDGETS ERROR =====');
            console.error('[App] Error:', error);
            main.innerHTML = `
                <div class="alert alert-danger">
                    <h4 data-i18n="failed_to_load_widgets">Failed to Load Widgets</h4>
                    <p>${error.message || i18n.t('unknown_error') || 'Unknown error occurred'}</p>
                    <button class="btn btn-primary" onclick="location.reload()" data-i18n="reload">Reload</button>
                </div>
            `;
        }
    };

    App.prototype.toggleWidget = async function(widgetId) {
        if (this.coreWidgets.includes(widgetId)) return;
        this.showTopLoading();
        // Read current state once from cache/API
        const currentlyEnabled = await this.isWidgetEnabled(widgetId);
        const newState = !currentlyEnabled;
        // Optimistic UI update
        this.updateWidgetHeaderUI(widgetId, newState);
        try {
            await this.setWidgetEnabled(widgetId, newState);
            this.hideTopLoading();
            const enabledMsg = i18n.t('widget_enabled');
            const disabledMsg = i18n.t('widget_disabled');
            this.showToast('success', newState ? 
                (enabledMsg && !enabledMsg.startsWith('[') ? enabledMsg : 'Widget enabled on dashboard') : 
                (disabledMsg && !disabledMsg.startsWith('[') ? disabledMsg : 'Widget disabled from dashboard'));
        } catch (e) {
            console.error('[App] Error toggling widget:', e);
            this.hideTopLoading();
            // Revert optimistic UI update
            this.updateWidgetHeaderUI(widgetId, currentlyEnabled);
            this.showToast('error', i18n.t('error_saving_widgets') || 'Failed to save widget preferences');
        }
    };

    App.prototype.showTopLoading = function() {
        let loader = document.getElementById('top-loading-indicator');
        if (loader) loader.remove();
        loader = document.createElement('div');
        loader.id = 'top-loading-indicator';
        loader.style.cssText = 'position: fixed; top: 0; left: 0; right: 0; height: 3px; background: linear-gradient(90deg, #0d6efd, #0dcaf0, #0d6efd); background-size: 200% 100%; animation: loading-slide 1.5s ease-in-out infinite; z-index: 9999; box-shadow: 0 2px 4px rgba(0,0,0,0.2);';
        if (!document.getElementById('loading-animation-style')) {
            const style = document.createElement('style');
            style.id = 'loading-animation-style';
            style.textContent = '@keyframes loading-slide { 0% { background-position: 200% 0; } 100% { background-position: -200% 0; } }';
            document.head.appendChild(style);
        }
        document.body.appendChild(loader);
    };

    App.prototype.hideTopLoading = function() {
        const loader = document.getElementById('top-loading-indicator');
        if (loader) {
            loader.style.transition = 'opacity 0.3s ease-out';
            loader.style.opacity = '0';
            setTimeout(() => { if (loader.parentNode) loader.remove(); }, 300);
        }
    };

    App.prototype.updateWidgetHeaderUI = function(widgetId, isEnabled) {
        const headers = document.querySelectorAll(`[data-widget-id="${widgetId}"]`);
        headers.forEach(header => {
            if (isEnabled) {
                header.classList.remove('bg-warning');
                header.classList.add('bg-success');
                const icon = header.querySelector('i');
                if (icon) { icon.classList.remove('bi-x-circle-fill'); icon.classList.add('bi-check-circle-fill'); }
            } else {
                header.classList.remove('bg-success');
                header.classList.add('bg-warning');
                const icon = header.querySelector('i');
                if (icon) { icon.classList.remove('bi-check-circle-fill'); icon.classList.add('bi-x-circle-fill'); }
            }
        });
    };

})();
