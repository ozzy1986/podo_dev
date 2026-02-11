/**
 * Domains Module
 * Domain management, verification, instructions, parking
 */
(function() {
    'use strict';

    App.prototype.showDomainPage = function(domain) {
        const main = document.getElementById('main-content');
        if (!main) {
            console.error('[App] Main content element not found!');
            return;
        }
        
        // Show loading state
        main.innerHTML = `
            <div class="domain-page">
                <div class="text-center py-5">
                    <div class="spinner-border text-primary" role="status">
                        <span class="visually-hidden" data-i18n="loading">Loading...</span>
                    </div>
                    <p class="mt-3" data-i18n="loading_domain_info">Loading domain information...</p>
                </div>
            </div>
        `;
        this.updateI18n();
        
        // Load domain data
        this.loadDomainPage(domain);
    };

    App.prototype.loadDomainPage = async function(domain) {
        const main = document.getElementById('main-content');
        if (!main) return;

        try {
            const data = await api.getDomainInfo(domain);
            
            // Format dates
            const creationDate = data.creation_date ? new Date(data.creation_date).toLocaleDateString() : null;
            const ageYears = data.creation_date ? ((new Date() - new Date(data.creation_date)) / (1000 * 60 * 60 * 24 * 365.25)).toFixed(1) : null;
            
            // Format numbers
            const weight = data.weight ? this.formatNumber(data.weight, 2) : '0.00';
            const totalEarnings = this.formatNumber(data.total_earnings || 0, 2);
            
            // Build status badges
            const statusBadges = [];
            if (data.verified) {
                statusBadges.push('<span class="badge bg-success me-1" data-i18n="verified">Verified</span>');
            }
            if (data.is_mining) {
                statusBadges.push('<span class="badge bg-info me-1" data-i18n="mining">Mining</span>');
            }
            
            // Owner wallet link
            const walletLink = data.owner_wallet ? 
                `<a href="/rating?wallet=${encodeURIComponent(data.owner_wallet)}" onclick="event.preventDefault(); router.navigate('/rating?wallet=' + encodeURIComponent('${this.escapeHtml(data.owner_wallet)}'));" class="text-break">${this.escapeHtml(data.owner_wallet)}</a>` :
                '<span class="text-muted" data-i18n="not_set">Not set</span>';
            
            main.innerHTML = `
                <div class="domain-page">
                    <div class="mb-4">
                        <h1 class="h2 mb-3">${this.escapeHtml(data.domain)}</h1>
                        <div class="mb-2">
                            ${statusBadges.join('')}
                        </div>
                    </div>
                    
                    <div class="row g-3">
                        <div class="col-12 col-md-6">
                            <div class="card h-100">
                                <div class="card-header">
                                    <h5 class="mb-0" data-i18n="domain_info">Domain Information</h5>
                                </div>
                                <div class="card-body">
                                    <dl class="row mb-0">
                                        <dt class="col-sm-5 col-md-4" data-i18n="owner_wallet">Owner Wallet</dt>
                                        <dd class="col-sm-7 col-md-8">${walletLink}</dd>
                                        
                                        ${data.sld_length ? `
                                            <dt class="col-sm-5 col-md-4" data-i18n="sld_length">SLD Length</dt>
                                            <dd class="col-sm-7 col-md-8">${data.sld_length}</dd>
                                        ` : ''}
                                        
                                        ${creationDate ? `
                                            <dt class="col-sm-5 col-md-4" data-i18n="creation_date">Creation Date</dt>
                                            <dd class="col-sm-7 col-md-8">${creationDate}${ageYears ? ` <small class="text-muted">(${ageYears} ${i18n.t('years') || 'years'})</small>` : ''}</dd>
                                        ` : ''}
                                    </dl>
                                </div>
                            </div>
                        </div>
                        
                        <div class="col-12 col-md-6">
                            <div class="card h-100">
                                <div class="card-header">
                                    <h5 class="mb-0" data-i18n="mining_stats">Mining Statistics</h5>
                                </div>
                                <div class="card-body">
                                    <dl class="row mb-0">
                                        <dt class="col-sm-5 col-md-4" data-i18n="weight">Weight</dt>
                                        <dd class="col-sm-7 col-md-8"><strong>${weight}</strong></dd>
                                        
                                        <dt class="col-sm-5 col-md-4" data-i18n="total_earnings">Total Earnings</dt>
                                        <dd class="col-sm-7 col-md-8"><strong class="text-success">${totalEarnings}</strong> <span data-i18n="tokens">tokens</span></dd>
                                    </dl>
                                </div>
                            </div>
                        </div>
                        
                        <div class="col-12">
                            <div class="card">
                                <div class="card-header d-flex justify-content-between align-items-center">
                                    <h5 class="mb-0" data-i18n="description">Description</h5>
                                    ${(data.parking_mode === 'non_redirect') ? '<span class="badge bg-info" data-i18n="super_parking">Super parking</span>' : ''}
                                </div>
                                <div class="card-body">
                                    ${(() => {
                                        const theme = (data.content_theme || 'light').toLowerCase();
                                        const isolateClass = theme === 'dark' ? 'user-content-isolate user-content-isolate--dark' : 'user-content-isolate user-content-isolate--light';
                                        if (data.parking_mode === 'non_redirect' && data.parking_content) {
                                            return `<div class="${isolateClass}"><div class="parking-content">${data.parking_content}</div></div>`;
                                        }
                                        if (data.description) {
                                            return `<div class="${isolateClass}"><p class="mb-0" style="white-space: pre-wrap; word-wrap: break-word;">${this.escapeHtml(data.description)}</p></div>`;
                                        }
                                        return `<p class="text-muted mb-0" data-i18n="no_description">No description provided.</p>`;
                                    })()}
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <div class="mt-4 domain-vote-block">
                        <div class="d-flex align-items-center gap-2 flex-wrap">
                            <span class="text-muted me-1" data-i18n="domain_likes">Likes:</span>
                            ${api.token ? `
                                <div class="d-inline-flex align-items-center">
                                    <button type="button" class="btn btn-sm btn-outline-secondary domain-vote-up ${(data.user_vote === 1) ? 'active' : ''}" data-value="1" title="Like" aria-label="Like"><i class="bi bi-arrow-up"></i></button>
                                    <span class="d-inline-block text-center px-2 domain-karma-val" style="min-width: 2rem;">${typeof data.karma === 'number' ? data.karma : 0}</span>
                                    ${(this.user && data.user_id === this.user.id) ? '' : `<button type="button" class="btn btn-sm btn-outline-secondary domain-vote-down ${(data.user_vote === -1) ? 'active' : ''}" data-value="-1" title="Dislike" aria-label="Dislike"><i class="bi bi-arrow-down"></i></button>`}
                                </div>
                            ` : `
                                <span class="domain-karma-val">${typeof data.karma === 'number' ? data.karma : 0}</span>
                                <small class="text-muted" data-i18n="login_to_vote">Log in to vote</small>
                            `}
                        </div>
                    </div>
                    
                    <div id="domain-comments-container" class="mt-4"></div>
                    
                    <div class="mt-4 text-center">
                        <a href="/rating" onclick="event.preventDefault(); router.navigate('/rating');" class="btn btn-outline-primary" data-i18n="view_all_domains">View All Domains</a>
                    </div>
                </div>
            `;
            
            this.updateI18n();
            if (data.id != null) {
                this.renderCommentsBlock('domain-comments-container', 'domain', data.id, null);
            }
            var self = this;
            var domainId = data.id;
            var domainName = data.domain || ('domain #' + domainId);
            var currentKarma = typeof data.karma === 'number' ? data.karma : 0;
            var currentUserVote = data.user_vote != null ? data.user_vote : null;
            var block = document.querySelector('.domain-vote-block');
            document.querySelectorAll('.domain-vote-up, .domain-vote-down').forEach(function(btn) {
                btn.addEventListener('click', function() {
                    if (!api.token) return;
                    var value = parseInt(btn.getAttribute('data-value'), 10);
                    var mainContent = document.getElementById('main-content');
                    if (mainContent) mainContent.querySelectorAll('.paid-vote-form-wrap').forEach(function(f) { if (f.parentNode) f.parentNode.removeChild(f); });
                    api.setVote('domain', domainId, null, value).then(function(res) {
                        if (res && res.karma != null) currentKarma = res.karma; else currentKarma = currentKarma + value - (currentUserVote || 0);
                        currentUserVote = value;
                        var karmaEl = block ? block.querySelector('.domain-karma-val') : null;
                        if (karmaEl) karmaEl.textContent = currentKarma;
                        block.querySelectorAll('.domain-vote-up, .domain-vote-down').forEach(function(b) {
                            var v = parseInt(b.getAttribute('data-value'), 10);
                            b.classList.toggle('active', v === value);
                        });
                    }).catch(function(err) {
                        if (err && err.status === 409 && err.responseData && (err.responseData.details && err.responseData.details.code === 'PAID_VOTE_REQUIRED')) {
                            if (typeof showPaidVoteForm === 'function') {
                                showPaidVoteForm({
                                    anchorEl: block || document.getElementById('main-content'),
                                    targetLabel: 'Domain: ' + domainName,
                                    targetType: 'domain',
                                    targetId: domainId,
                                    targetKey: null,
                                    value: value,
                                    onSuccess: function(res) {
                                        if (res && res.karma != null) currentKarma = res.karma;
                                        currentUserVote = value;
                                        var karmaEl = block ? block.querySelector('.domain-karma-val') : null;
                                        if (karmaEl) karmaEl.textContent = currentKarma;
                                        block.querySelectorAll('.domain-vote-up, .domain-vote-down').forEach(function(b) {
                                            var v = parseInt(b.getAttribute('data-value'), 10);
                                            b.classList.toggle('active', v === value);
                                        });
                                    }
                                });
                            } else {
                                if (typeof app !== 'undefined' && app.showToast) app.showToast('Vote failed', 'danger');
                            }
                        } else {
                            if (typeof app !== 'undefined' && app.showToast) app.showToast('Vote failed', 'danger');
                        }
                    });
                });
            });
            
        } catch (error) {
            console.error('[App] Error loading domain page:', error);
            
            if (error.status === 404) {
                main.innerHTML = `
                    <div class="domain-page">
                        <div class="alert alert-warning" role="alert">
                            <h4 class="alert-heading" data-i18n="domain_not_found">Domain Not Found</h4>
                            <p>${(i18n.t('domain_not_found_message') || 'The domain {domain} was not found in our system.').replace('{domain}', `<strong>${this.escapeHtml(domain)}</strong>`)}</p>
                            <hr>
                            <p class="mb-0">
                                <a href="/rating" onclick="event.preventDefault(); router.navigate('/rating');" class="btn btn-primary" data-i18n="view_all_domains">View All Domains</a>
                            </p>
                        </div>
                    </div>
                `;
            } else {
                main.innerHTML = `
                    <div class="domain-page">
                        <div class="alert alert-danger" role="alert">
                            <h4 class="alert-heading" data-i18n="error">Error</h4>
                            <p data-i18n="error_loading_domain">Failed to load domain information. Please try again later.</p>
                            <hr>
                            <button class="btn btn-primary" onclick="app.loadDomainPage('${this.escapeHtml(domain)}')" data-i18n="retry">Retry</button>
                        </div>
                    </div>
                `;
            }
            
            this.updateI18n();
        }
    };

    App.prototype.showDomains = async function() {
        const main = document.getElementById('main-content');
        main.innerHTML = `
            <div class="d-flex justify-content-between align-items-center mb-4">
                <h1 data-i18n="your_domains">Your Domains</h1>
                <button class="btn btn-primary" data-bs-toggle="modal" data-bs-target="#addDomainModal">
                    <i class="bi bi-plus-circle"></i> <span data-i18n="add_domain">Add Domain</span>
                </button>
            </div>
            <div id="domains-list" class="card">
                <div class="card-body">
                    <div class="text-center py-5">
                        <div class="spinner-border text-primary" role="status">
                            <span class="visually-hidden" data-i18n="loading">Loading...</span>
                        </div>
                    </div>
                </div>
            </div>
        `;
        this.updateI18n();
        await this.loadDomains();
        this.setupAddDomainModal();
    };

    App.prototype.loadDomains = async function() {
        try {
            const data = await api.getDomains();
            const listEl = document.getElementById('domains-list');
            
            if (data.domains.length === 0) {
                listEl.innerHTML = `
                    <div class="card-body">
                        <div class="empty-state">
                            <i class="bi bi-globe"></i>
                            <h3 data-i18n="you_have_no_domains">You don't have any domains yet</h3>
                        </div>
                    </div>
                `;
                this.updateI18n();
                return;
            }

            listEl.innerHTML = `
                <div class="card-body">
                    <div class="list-group list-group-flush">
                        ${data.domains.map(domain => `
                            <div class="list-group-item">
                                <div class="d-flex justify-content-between align-items-start">
                                    <div class="flex-grow-1">
                                        <h5 class="mb-1">${domain.domain}</h5>
                                        <div class="mb-2">
                                            ${domain.verified ? 
                                                '<span class="badge bg-success" data-i18n="domain_status_verified">Verified</span>' : 
                                                '<span class="badge bg-warning" data-i18n="domain_status_not_verified">Not Verified</span>'
                                            }
                                            ${domain.is_mining ? 
                                                '<span class="badge bg-info ms-2" data-i18n="domain_status_mining">Mining</span>' : 
                                                '<span class="badge bg-secondary ms-2" data-i18n="domain_status_not_mining">Not Mining</span>'
                                            }
                                            ${domain.is_clickable ? 
                                                `<span class="badge bg-primary ms-2"><span data-i18n="domain_status_clickable">Clickable</span></span>` : 
                                                ''
                                            }
                                            ${domain.is_promoted ? 
                                                '<span class="badge bg-warning text-dark ms-2" data-i18n="promoted">Promoted</span>' : 
                                                ''
                                            }
                                            ${domain.has_subscription ? 
                                                '<span class="badge bg-success text-white ms-2" data-i18n="subscribed">Subscribed</span>' : 
                                                ''
                                            }
                                        </div>
                                        ${domain.sld_length ? `<small class="text-muted">SLD Length: ${domain.sld_length}</small>` : ''}
                                        ${domain.is_clickable ? `<small class="text-muted d-block"><i class="bi bi-info-circle"></i> <span data-i18n="clickable_domain_info">This domain earns 5% less but is clickable in ratings</span></small>` : ''}
                                            ${(domain.a_record_points_to_us === true && domain.parking_mode !== 'non_redirect') ? `<small class="text-muted d-block"><i class="bi bi-info-circle"></i> <span>${i18n.t('a_record_bonus_info', { ip: this.config.our_server_ip || '—' })}</span></small>` : ''}
                                            ${(domain.parking_mode === 'non_redirect') ? `<small class="text-muted d-block"><i class="bi bi-info-circle"></i> <span data-i18n="super_parking_active">Super parking: custom page on your domain</span></small>` : ''}
                                    </div>
                                    <div class="btn-group" role="group">
                                        ${domain.verified && domain.is_mining && domain.has_subscription ? `
                                            <button class="btn btn-sm btn-primary domain-promote-btn" 
                                                    data-domain-id="${domain.id}"
                                                    data-domain-name="${this.escapeHtml(domain.domain)}"
                                                    title="Bump to top (1 DOMAIN)">
                                                <i class="bi bi-arrow-up-circle"></i> <span data-i18n="bump_to_top">Bump</span>
                                            </button>
                                            <button class="btn btn-sm btn-danger domain-cancel-subscription-btn" 
                                                    data-subscription-id="${domain.subscription_id || ''}"
                                                    data-domain-name="${this.escapeHtml(domain.domain)}"
                                                    title="Cancel subscription">
                                                <i class="bi bi-x-circle"></i> <span data-i18n="cancel_subscription">Cancel</span>
                                            </button>
                                        ` : ''}
                                        ${domain.verified && domain.is_mining && !domain.has_subscription ? `
                                            <button class="btn btn-sm btn-primary domain-promote-btn" 
                                                    data-domain-id="${domain.id}"
                                                    data-domain-name="${this.escapeHtml(domain.domain)}"
                                                    title="Promote once (1 DOMAIN)">
                                                <i class="bi bi-arrow-up-circle"></i> <span data-i18n="promote_once">Promote</span>
                                            </button>
                                            <button class="btn btn-sm btn-success domain-subscribe-btn" 
                                                    data-domain-id="${domain.id}"
                                                    data-domain-name="${this.escapeHtml(domain.domain)}"
                                                    title="Subscribe for recurring promotion">
                                                <i class="bi bi-star-fill"></i> <span data-i18n="subscribe">Subscribe</span>
                                            </button>
                                        ` : ''}
                                        ${!domain.verified ? 
                                            `<button class="btn btn-sm btn-primary" id="verify-btn-${domain.domain.replace(/\./g, '-')}" onclick="app.verifyDomain('${domain.domain}')">
                                                <span class="verify-btn-text" data-i18n="verify">Verify</span>
                                            </button>` : 
                                            ''
                                        }
                                        ${domain.verified ? `
                                            <button class="btn btn-sm btn-outline-primary" onclick="app.showEditDescriptionModal('${domain.domain}')" title="${i18n.t('edit_description') || 'Edit Description'}">
                                                <i class="bi bi-pencil"></i> <span class="d-none d-sm-inline" data-i18n="edit_description">Edit Description</span>
                                            </button>
                                        ` : ''}
                                        <button class="btn btn-sm btn-outline-secondary" onclick="app.showDomainInstructions('${domain.domain}')" title="${i18n.t('dns_instructions') || 'DNS Instructions'}">
                                            <i class="bi bi-info-circle"></i> <span data-i18n="dns_instructions">Instructions</span>
                                        </button>
                                        <button class="btn btn-sm btn-outline-danger" onclick="app.showDeleteDomainConfirmation('${domain.domain}')" title="${i18n.t('delete_domain') || 'Delete Domain'}">
                                            <i class="bi bi-trash"></i>
                                        </button>
                                    </div>
                                </div>
                                ${domain.verified && domain.is_mining ? `
                                    <div class="domain-options-container mt-3 pt-3">
                                        <div class="d-flex flex-wrap align-items-start gap-3">
                                            <div>
                                                <div class="form-check mb-2">
                                                    <input class="form-check-input" type="radio" 
                                                           name="domain-option-${domain.domain.replace(/\./g, '-')}" 
                                                           id="clickable-${domain.domain.replace(/\./g, '-')}" 
                                                           ${domain.is_clickable ? 'checked' : ''} 
                                                           onchange="app.toggleDomainClickable('${domain.domain}', true)"
                                                           onclick="event.stopPropagation()">
                                                    <label class="form-check-label" for="clickable-${domain.domain.replace(/\./g, '-')}" onclick="event.stopPropagation()">
                                                        <span data-i18n="make_clickable">Clickable</span> <small class="text-muted">(-5%)</small>
                                                        <i class="bi bi-question-circle ms-1" data-bs-toggle="tooltip" data-bs-placement="top" data-i18n-tooltip="clickable_option_tooltip" style="cursor: help; font-size: 0.875rem; color: #6c757d;"></i>
                                                    </label>
                                                </div>
                                                <div class="form-check mb-2">
                                                    <input class="form-check-input" type="radio" 
                                                           name="domain-option-${domain.domain.replace(/\./g, '-')}" 
                                                           id="a-record-${domain.domain.replace(/\./g, '-')}" 
                                                           ${(domain.a_record_points_to_us === true && domain.parking_mode !== 'non_redirect') ? 'checked' : ''} 
                                                           onchange="app.verifyAndSetParkingMode('${domain.domain}', 'redirect')"
                                                           onclick="event.stopPropagation()">
                                                    <label class="form-check-label" for="a-record-${domain.domain.replace(/\./g, '-')}" onclick="event.stopPropagation()">
                                                        <span data-i18n="a_record_to_server">A-record to server</span> <small class="text-muted">(+5%)</small>
                                                        <i class="bi bi-question-circle ms-1" data-bs-toggle="tooltip" data-bs-placement="top" data-i18n-tooltip="a_record_option_tooltip" style="cursor: help; font-size: 0.875rem; color: #6c757d;"></i>
                                                    </label>
                                                </div>
                                                <div class="form-check mb-2">
                                                    <input class="form-check-input" type="radio" 
                                                           name="domain-option-${domain.domain.replace(/\./g, '-')}" 
                                                           id="super-parking-${domain.domain.replace(/\./g, '-')}" 
                                                           ${(domain.parking_mode === 'non_redirect') ? 'checked' : ''} 
                                                           onchange="app.verifyAndSetParkingMode('${domain.domain}', 'non_redirect')"
                                                           onclick="event.stopPropagation()">
                                                    <label class="form-check-label" for="super-parking-${domain.domain.replace(/\./g, '-')}" onclick="event.stopPropagation()">
                                                        <span data-i18n="super_parking">Super parking</span> <small class="text-muted">(-50%)</small>
                                                        <i class="bi bi-question-circle ms-1" data-bs-toggle="tooltip" data-bs-placement="top" data-i18n-tooltip="super_parking_option_tooltip" style="cursor: help; font-size: 0.875rem; color: #6c757d;"></i>
                                                    </label>
                                                    ${(domain.parking_mode === 'non_redirect') ? `
                                                    <div class="mt-1 ms-4">
                                                        <button type="button" class="btn btn-sm btn-outline-secondary" onclick="event.stopPropagation(); app.showEditParkingContentModal('${domain.domain}')" data-i18n="edit_parking_content">Edit content</button>
                                                    </div>
                                                    ` : ''}
                                                </div>
                                                <div class="form-check mb-2">
                                                    <input class="form-check-input" type="radio" 
                                                           name="domain-option-${domain.domain.replace(/\./g, '-')}" 
                                                           id="none-${domain.domain.replace(/\./g, '-')}" 
                                                           ${!domain.is_clickable && !(domain.a_record_points_to_us === true) ? 'checked' : ''} 
                                                           onchange="app.toggleDomainClickable('${domain.domain}', false)"
                                                           onclick="event.stopPropagation()">
                                                    <label class="form-check-label" for="none-${domain.domain.replace(/\./g, '-')}" onclick="event.stopPropagation()">
                                                        <span data-i18n="neither_option">Neither</span> <small class="text-muted">(base)</small>
                                                        <i class="bi bi-question-circle ms-1" data-bs-toggle="tooltip" data-bs-placement="top" data-i18n-tooltip="neither_option_tooltip" style="cursor: help; font-size: 0.875rem; color: #6c757d;"></i>
                                                    </label>
                                                </div>
                                            </div>
                                            <div class="border-start ps-3">
                                                <button type="button" class="btn btn-sm btn-outline-info" onclick="app.showParkingInstructions('${domain.domain}')" title="${i18n.t('parking_instructions') || 'Parking Instructions'}">
                                                    <i class="bi bi-info-circle"></i> <span data-i18n="parking_instructions">Parking instructions</span>
                                                </button>
                                            </div>
                                        </div>
                                    </div>
                                    <div class="border-top mt-3"></div>
                                ` : ''}
                            </div>
                        `).join('')}
                    </div>
                </div>
            `;
            this.updateI18n();
            this.initializeTooltips();
            
            // Setup event listeners for promote/subscribe buttons
            this.setupDomainPromoteListeners();
        } catch (error) {
            this.showToast('error', error.message);
        }
    };

    App.prototype.setupDomainPromoteListeners = function() {
        // Handle promote button clicks
        document.querySelectorAll('.domain-promote-btn').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                e.preventDefault();
                e.stopPropagation();
                const domainId = btn.getAttribute('data-domain-id');
                const domainName = btn.getAttribute('data-domain-name');
                this.showPromoteConfirmModal(domainId, domainName);
            });
        });
        
        // Handle subscribe button clicks
        document.querySelectorAll('.domain-subscribe-btn').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                e.preventDefault();
                e.stopPropagation();
                const domainId = btn.getAttribute('data-domain-id');
                const domainName = btn.getAttribute('data-domain-name');
                this.showSubscribeConfirmModal(domainId, domainName);
            });
        });
        
        // Handle cancel subscription button clicks
        document.querySelectorAll('.domain-cancel-subscription-btn').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                e.preventDefault();
                e.stopPropagation();
                const subscriptionIdStr = btn.getAttribute('data-subscription-id');
                const domainName = btn.getAttribute('data-domain-name');
                // Convert to number and validate
                const subscriptionId = subscriptionIdStr ? parseInt(subscriptionIdStr, 10) : null;
                if (subscriptionId && !isNaN(subscriptionId)) {
                    this.showCancelSubscriptionModal(subscriptionId, domainName);
                } else {
                    console.error('Invalid subscription ID:', subscriptionIdStr);
                    this.showToast('error', 'Invalid subscription ID');
                }
            });
        });
    };

    App.prototype.setupAddDomainModal = function() {
        const modalHTML = `
            <div class="modal fade" id="addDomainModal" tabindex="-1">
                <div class="modal-dialog">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title" data-i18n="add_domain_title">Add Domain</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            <form id="add-domain-form">
                                <div class="mb-3">
                                    <label class="form-label" data-i18n="enter_domain_name">Domain Name</label>
                                    <input type="text" class="form-control" id="domain-input" placeholder="example.com" required>
                                    <small class="form-text text-muted" data-i18n="domain_example">e.g., example.com</small>
                                </div>
                            </form>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal" data-i18n="cancel">Cancel</button>
                            <button type="submit" form="add-domain-form" class="btn btn-primary" data-i18n="add_domain">Add Domain</button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        // Remove existing modal if any
        const existing = document.getElementById('addDomainModal');
        if (existing) existing.remove();
        
        document.body.insertAdjacentHTML('beforeend', modalHTML);
        this.updateI18n();
        
        document.getElementById('add-domain-form').addEventListener('submit', async (e) => {
            e.preventDefault();
            const domain = document.getElementById('domain-input').value.trim();
            
            try {
                const data = await api.addDomain(domain);
                const modal = bootstrap.Modal.getInstance(document.getElementById('addDomainModal'));
                modal.hide();
                
                // Store TXT record in localStorage for later retrieval
                if (data.txt_record && data.domain) {
                    const domainRecords = JSON.parse(localStorage.getItem('domain_txt_records') || '{}');
                    domainRecords[data.domain] = data.txt_record;
                    localStorage.setItem('domain_txt_records', JSON.stringify(domainRecords));
                }
                
                // Show TXT record instructions
                this.showTxtRecordModal(data);
                await this.loadDomains();
            } catch (error) {
                this.showToast('error', error.message);
            }
        });
    };

    App.prototype.showDomainInstructions = async function(domain) {
        try {
            // Always reconstruct from source of truth (domain nonce + user wallet)
            // localStorage is just a cache, but we always fetch fresh data
            
            // Ensure user data is loaded
            if (!this.user || !this.user.wallet) {
                // Try to refresh user data
                try {
                    this.user = await api.getCurrentUser();
                } catch (error) {
                    console.error('Failed to get user data:', error);
                    this.showToast('error', i18n.t('please_set_wallet') || 'Please set your wallet first.');
                    return;
                }
            }
            
            if (!this.user.wallet) {
                this.showToast('error', i18n.t('please_set_wallet') || 'Please set your wallet first.');
                return;
            }
            
            // Get domains list to find this domain's nonce
            const domainsData = await api.getDomains();
            const domainData = domainsData.domains.find(d => d.domain === domain);
            
            if (!domainData) {
                this.showToast('error', i18n.t('domain_not_found') || `Domain ${domain} not found.`);
                return;
            }
            
            if (!domainData.nonce) {
                this.showToast('error', i18n.t('txt_record_not_found') || `TXT record cannot be generated for ${domain}. Please contact support.`);
                return;
            }
            
            // Reconstruct TXT record from nonce and wallet (source of truth)
            const config = {
                TXT_RECORD_PREFIX: 'd.onl',
                TXT_FIELD_SEPARATOR: ';',
                TXT_KEY_VALUE_SEPARATOR: '='
            };
            const txtRecord = `${config.TXT_RECORD_PREFIX}${config.TXT_FIELD_SEPARATOR}wallet${config.TXT_KEY_VALUE_SEPARATOR}${this.user.wallet}`;
            
            // Cache it in localStorage for performance (optional)
            const domainRecords = JSON.parse(localStorage.getItem('domain_txt_records') || '{}');
            domainRecords[domain] = txtRecord;
            localStorage.setItem('domain_txt_records', JSON.stringify(domainRecords));
            
            this.showTxtRecordModal({ domain, txt_record: txtRecord });
        } catch (error) {
            console.error('Error showing domain instructions:', error);
            this.showToast('error', error.message || i18n.t('txt_record_not_found') || 'Failed to load domain instructions.');
        }
    };

    App.prototype.showTxtRecordModal = function(data) {
        const domainName = data.domain || '';
        // Ensure we have the actual TXT record value for the example
        const txtRecordValue = data.txt_record || '';
        const modalHTML = `
            <div class="modal fade" id="txtRecordModal" tabindex="-1">
                <div class="modal-dialog modal-lg">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title" data-i18n="dns_instructions">DNS Instructions</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            ${domainName ? `<p class="mb-2"><strong>${i18n.t('enter_domain_name') || 'Domain'}:</strong> <code>${domainName}</code></p>` : ''}
                            <p data-i18n="add_txt_record">Add this TXT record to your domain's DNS:</p>
                            <div class="input-group mb-3">
                                <input type="text" class="form-control" id="txt-record-value" value="${txtRecordValue.replace(/"/g, '&quot;')}" readonly>
                                <button class="btn btn-outline-secondary" type="button" onclick="app.copyToClipboard('txt-record-value')">
                                    <i class="bi bi-clipboard"></i> <span data-i18n="copy">Copy</span>
                                </button>
                            </div>
                            <div class="alert alert-info">
                                <strong data-i18n="instructions">Instructions:</strong>
                                <ol>
                                    <li data-i18n="dns_step_1">Go to your domain registrar's DNS settings</li>
                                    <li data-i18n="dns_step_2">Add a new TXT record</li>
                                    <li data-i18n="dns_step_3">Host: _mining</li>
                                    <li data-i18n="dns_step_4">Value: Copy the text above</li>
                                    <li data-i18n="dns_step_5">Wait 5-10 minutes for DNS propagation</li>
                                    <li data-i18n="dns_step_6">Click Verify button on domains page</li>
                                </ol>
                                <div class="mt-3">
                                    <strong data-i18n="dns_example_title">Example:</strong>
                                    <p class="mb-1" data-i18n="dns_example_description">The record should look like this:</p>
                                    <div class="table-responsive">
                                        <table class="table table-sm table-bordered">
                                            <thead>
                                                <tr>
                                                    <th data-i18n="dns_example_field">Field</th>
                                                    <th data-i18n="dns_example_value">Value</th>
                                                </tr>
                                            </thead>
                                            <tbody>
                                                <tr>
                                                    <td><strong data-i18n="dns_example_host">Host</strong></td>
                                                    <td><code>_mining</code></td>
                                                </tr>
                                                <tr>
                                                    <td><strong data-i18n="dns_example_type">Type</strong></td>
                                                    <td><code>TXT</code></td>
                                                </tr>
                                                <tr>
                                                    <td><strong data-i18n="dns_example_value_field">Value</strong></td>
                                                    <td><code>${txtRecordValue.replace(/</g, '&lt;').replace(/>/g, '&gt;')}</code></td>
                                                </tr>
                                            </tbody>
                                        </table>
                                    </div>
                                </div>
                            </div>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-primary" data-bs-dismiss="modal" data-i18n="got_it">Got it</button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        const existing = document.getElementById('txtRecordModal');
        if (existing) existing.remove();
        
        document.body.insertAdjacentHTML('beforeend', modalHTML);
        this.updateI18n();
        
        const modal = new bootstrap.Modal(document.getElementById('txtRecordModal'));
        modal.show();
    };

    App.prototype.showParkingInstructions = function(domain) {
        const serverIp = this.config && this.config.our_server_ip ? this.config.our_server_ip : '—';
        const modalHTML = `
            <div class="modal fade" id="parkingInstructionsModal" tabindex="-1">
                <div class="modal-dialog modal-lg">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title" data-i18n="parking_instructions">Parking instructions</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            <p class="mb-2"><strong data-i18n="domain">Domain</strong>: <code>${this.escapeHtml(domain)}</code></p>
                            <p data-i18n="parking_instructions_intro">Point your domain's A-record to our server. Visitors will be redirected to our site, or with Super parking you get a custom page on your domain.</p>
                            <div class="alert alert-info">
                                <strong data-i18n="parking_instructions_steps">Steps:</strong>
                                <ol class="mb-0">
                                    <li data-i18n="parking_step_1">Go to your domain registrar's DNS settings</li>
                                    <li data-i18n="parking_step_2">Add or edit the A record</li>
                                    <li data-i18n="parking_step_3">Host: <code>@</code> (or leave blank for root domain)</li>
                                    <li>Value / Points to: <code>${this.escapeHtml(serverIp)}</code></li>
                                    <li data-i18n="parking_step_5">Wait 5-10 minutes for DNS propagation</li>
                                    <li data-i18n="parking_step_6">Select A-record (+5%) or Super parking (-50%) option above</li>
                                </ol>
                            </div>
                            <div class="table-responsive">
                                <table class="table table-sm table-bordered">
                                    <thead>
                                        <tr>
                                            <th data-i18n="dns_example_field">Field</th>
                                            <th data-i18n="dns_example_value">Value</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        <tr>
                                            <td><strong data-i18n="dns_example_host">Host</strong></td>
                                            <td><code>@</code></td>
                                        </tr>
                                        <tr>
                                            <td><strong data-i18n="dns_example_type">Type</strong></td>
                                            <td><code>A</code></td>
                                        </tr>
                                        <tr>
                                            <td><strong data-i18n="dns_example_value_field">Value</strong></td>
                                            <td><code>${this.escapeHtml(serverIp)}</code></td>
                                        </tr>
                                    </tbody>
                                </table>
                            </div>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-primary" data-bs-dismiss="modal" data-i18n="got_it">Got it</button>
                        </div>
                    </div>
                </div>
            </div>`;
        const existing = document.getElementById('parkingInstructionsModal');
        if (existing) existing.remove();
        document.body.insertAdjacentHTML('beforeend', modalHTML);
        this.updateI18n();
        new bootstrap.Modal(document.getElementById('parkingInstructionsModal')).show();
    };

    App.prototype.showDeleteDomainConfirmation = function(domain) {
        const modalHTML = `
            <div class="modal fade" id="deleteDomainModal" tabindex="-1">
                <div class="modal-dialog">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title" data-i18n="delete_domain">Delete Domain</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            <p data-i18n="delete_domain_confirmation">Are you sure you want to delete this domain?</p>
                            <p class="mb-0"><strong data-i18n="enter_domain_name">Domain</strong>: <code>${domain}</code></p>
                            <div class="alert alert-warning mt-3" role="alert">
                                <i class="bi bi-exclamation-triangle"></i> <span data-i18n="delete_domain_warning">This action cannot be undone. The domain will be removed from your account and mining will stop.</span>
                            </div>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal" data-i18n="cancel">Cancel</button>
                            <button type="button" class="btn btn-danger" id="confirm-delete-domain-btn" data-i18n="delete">Delete</button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        const existing = document.getElementById('deleteDomainModal');
        if (existing) existing.remove();
        
        document.body.insertAdjacentHTML('beforeend', modalHTML);
        this.updateI18n();
        
        const modal = new bootstrap.Modal(document.getElementById('deleteDomainModal'));
        modal.show();
        
        // Handle confirmation
        document.getElementById('confirm-delete-domain-btn').addEventListener('click', () => {
            this.removeDomain(domain);
            modal.hide();
        });
    };

    App.prototype.removeDomain = async function(domain) {
        try {
            this.showToast('info', i18n.t('deleting_domain') || 'Deleting domain...');
            
            const result = await api.removeDomain(domain);
            
            if (result.success) {
                this.showToast('success', i18n.t('domain_deleted_success') || 'Domain deleted successfully');
                // Reload domains list
                await this.loadDomains();
            } else {
                this.showToast('error', result.error || i18n.t('delete_domain_error') || 'Failed to delete domain');
            }
        } catch (error) {
            console.error('Error deleting domain:', error);
            this.showToast('error', error.message || i18n.t('delete_domain_error') || 'Failed to delete domain');
        }
    };

    App.prototype.showEditDescriptionModal = async function(domain) {
        // Remove existing modal if any
        const existingModal = document.getElementById('editDescriptionModal');
        if (existingModal) {
            existingModal.remove();
        }

        // Show loading state
        const modalHTML = `
            <div class="modal fade" id="editDescriptionModal" tabindex="-1" aria-labelledby="editDescriptionModalLabel" aria-hidden="true">
                <div class="modal-dialog modal-fullscreen-sm-down modal-dialog-centered modal-dialog-scrollable">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title" id="editDescriptionModalLabel" data-i18n="edit_domain_description">Edit Domain Description</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                        </div>
                        <div class="modal-body">
                            <div class="mb-3">
                                <label for="domainDescriptionTextarea" class="form-label">
                                    <strong data-i18n="domain">Domain</strong>: <code>${this.escapeHtml(domain)}</code>
                                </label>
                                <textarea 
                                    class="form-control" 
                                    id="domainDescriptionTextarea" 
                                    rows="8" 
                                    maxlength="500"
                                    placeholder="${i18n.t('description_placeholder') || 'Enter domain description (optional, max 500 characters)...'}"
                                    style="min-height: 150px; resize: vertical;"
                                ></textarea>
                                <div class="form-text">
                                    <span id="descriptionCharCount">0</span>/500 <span data-i18n="characters">characters</span>
                                </div>
                            </div>
                            <div id="descriptionError" class="alert alert-danger d-none" role="alert"></div>
                            <div class="alert alert-info">
                                <i class="bi bi-info-circle"></i> 
                                <span data-i18n="description_info">The description will be displayed on the public domain page. You can leave it empty to remove the description.</span>
                            </div>
                        </div>
                        <div class="modal-footer d-flex flex-column flex-sm-row gap-2">
                            <button type="button" class="btn btn-secondary flex-fill" data-bs-dismiss="modal" data-i18n="cancel">Cancel</button>
                            <button type="button" class="btn btn-primary flex-fill" id="saveDescriptionBtn" data-i18n="save">Save</button>
                        </div>
                    </div>
                </div>
            </div>
        `;

        document.body.insertAdjacentHTML('beforeend', modalHTML);
        this.updateI18n();

        const modal = new bootstrap.Modal(document.getElementById('editDescriptionModal'));
        const textarea = document.getElementById('domainDescriptionTextarea');
        const charCount = document.getElementById('descriptionCharCount');
        const errorDiv = document.getElementById('descriptionError');
        const saveBtn = document.getElementById('saveDescriptionBtn');

        // Load current description
        try {
            const data = await api.getDomainDescription(domain);
            const currentDescription = data.description || '';
            textarea.value = currentDescription;
            charCount.textContent = currentDescription.length;
        } catch (error) {
            console.error('Error loading description:', error);
            errorDiv.textContent = error.message || i18n.t('error_loading_description') || 'Failed to load description';
            errorDiv.classList.remove('d-none');
        }

        // Character counter
        textarea.addEventListener('input', () => {
            const length = textarea.value.length;
            charCount.textContent = length;
            if (length > 500) {
                charCount.classList.add('text-danger');
            } else {
                charCount.classList.remove('text-danger');
            }
        });

        // Save handler
        saveBtn.addEventListener('click', async () => {
            const description = textarea.value.trim();
            
            // Disable button during save
            saveBtn.disabled = true;
            saveBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>' + (i18n.t('saving') || 'Saving...');
            errorDiv.classList.add('d-none');

            try {
                const contentTheme = document.documentElement.getAttribute('data-theme') || localStorage.getItem('theme') || 'light';
                const result = await api.updateDomainDescription(domain, description, contentTheme);
                
                if (result.success) {
                    modal.hide();
                    this.showToast('success', i18n.t('description_saved') || 'Description saved successfully');
                    // Reload domains list to show updated description if needed
                    await this.loadDomains();
                } else {
                    throw new Error(result.error || i18n.t('save_error') || 'Failed to save description');
                }
            } catch (error) {
                console.error('Error saving description:', error);
                errorDiv.textContent = error.message || i18n.t('save_error') || 'Failed to save description';
                errorDiv.classList.remove('d-none');
                // Scroll to error
                errorDiv.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            } finally {
                saveBtn.disabled = false;
                saveBtn.innerHTML = i18n.t('save') || 'Save';
            }
        });

        // Focus textarea when modal is shown (with delay for mobile keyboard)
        modal._element.addEventListener('shown.bs.modal', () => {
            setTimeout(() => {
                textarea.focus();
            }, 300);
        });

        modal.show();
    };

    App.prototype.verifyAndSetParkingMode = async function(domain, parkingMode) {
        const domainSafe = domain.replace(/\./g, '-');
        const radios = document.querySelectorAll(`input[name="domain-option-${domainSafe}"]`);
        radios.forEach(r => { r.disabled = true; });
        try {
            this.showToast('info', i18n.t('verifying_a_record') || 'Verifying A-record...');
            const data = await api.verifyARecord(domain);
            if (data.success && data.points_to_us) {
                await api.updateDomainParkingMode(domain, parkingMode);
                const msg = parkingMode === 'non_redirect'
                    ? (i18n.t('super_parking_enabled') || 'Super parking enabled. You can now edit the page content.')
                    : (i18n.t('a_record_verified') || 'A-record verified successfully');
                this.showToast('success', msg);
                if (data.warnings && data.warnings.length) {
                    const tr = i18n.translations[i18n.currentLanguage] || {};
                    const translated = data.warnings.map(w => {
                        if (w.includes('clickability is enabled')) return tr.a_record_bonus_disabled_clickable || w;
                        if (w.includes('A-record points to our server')) return tr.clickability_disabled_arecord || w;
                        if (w.includes('A-record bonus has been disabled')) return tr.a_record_bonus_disabled || w;
                        return w;
                    });
                    this.showToast('info', translated.join('. '));
                }
                await this.loadDomains();
            } else {
                const noneRadio = document.getElementById(`none-${domainSafe}`);
                if (noneRadio) noneRadio.checked = true;
                throw new Error(data.error || data.message || (i18n.t('a_record_verification_failed') || 'A-record does not point to our server'));
            }
        } catch (error) {
            this.showToast('error', error.message || (i18n.t('a_record_verification_failed') || 'Verification failed'));
            const noneRadio = document.getElementById(`none-${domainSafe}`);
            const superRadio = document.getElementById(`super-parking-${domainSafe}`);
            const aRecordRadio = document.getElementById(`a-record-${domainSafe}`);
            if (parkingMode === 'non_redirect' && superRadio) superRadio.checked = false;
            else if (parkingMode === 'redirect' && aRecordRadio) aRecordRadio.checked = false;
            if (noneRadio) noneRadio.checked = true;
        } finally {
            radios.forEach(r => { r.disabled = false; });
        }
    };

    App.prototype.showEditParkingContentModal = async function(domain) {
        const existingModal = document.getElementById('editParkingContentModal');
        if (existingModal) existingModal.remove();
        const modalHTML = `
            <div class="modal fade" id="editParkingContentModal" tabindex="-1">
                <div class="modal-dialog modal-xl modal-dialog-centered modal-dialog-scrollable">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title" data-i18n="edit_parking_content">Edit Parking Content</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            <p class="text-muted small mb-2" data-i18n="parking_content_info">HTML content for your domain landing page. You can use links, ad codes, etc. Max 20000 characters.</p>
                            <textarea class="form-control font-monospace" id="parkingContentTextarea" rows="12" maxlength="20000" style="min-height: 200px;"></textarea>
                            <div class="form-text"><span id="parkingContentCharCount">0</span>/20000</div>
                            <div id="parkingContentError" class="alert alert-danger d-none mt-2"></div>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal" data-i18n="cancel">Cancel</button>
                            <button type="button" class="btn btn-primary" id="saveParkingContentBtn" data-i18n="save">Save</button>
                        </div>
                    </div>
                </div>
            </div>`;
        document.body.insertAdjacentHTML('beforeend', modalHTML);
        this.updateI18n();
        const modal = new bootstrap.Modal(document.getElementById('editParkingContentModal'));
        const textarea = document.getElementById('parkingContentTextarea');
        const charCount = document.getElementById('parkingContentCharCount');
        const errorDiv = document.getElementById('parkingContentError');
        const saveBtn = document.getElementById('saveParkingContentBtn');
        try {
            const data = await api.getDomainParkingContent(domain);
            const content = data.parking_content || '';
            textarea.value = content;
            charCount.textContent = content.length;
        } catch (e) {
            errorDiv.textContent = e.message || 'Failed to load';
            errorDiv.classList.remove('d-none');
        }
        textarea.addEventListener('input', () => { charCount.textContent = textarea.value.length; });
        saveBtn.addEventListener('click', async () => {
            const content = textarea.value;
            if (content.length > 20000) {
                errorDiv.textContent = i18n.t('content_too_long') || 'Content too long (max 20000 characters)';
                errorDiv.classList.remove('d-none');
                return;
            }
            saveBtn.disabled = true;
            errorDiv.classList.add('d-none');
            try {
                const contentTheme = document.documentElement.getAttribute('data-theme') || localStorage.getItem('theme') || 'light';
                const result = await api.updateDomainParkingContent(domain, content, contentTheme);
                if (result.success) {
                    modal.hide();
                    this.showToast('success', i18n.t('description_saved') || 'Saved successfully');
                    await this.loadDomains();
                } else throw new Error(result.error);
            } catch (e) {
                errorDiv.textContent = e.message || 'Failed to save';
                errorDiv.classList.remove('d-none');
            } finally {
                saveBtn.disabled = false;
            }
        });
        modal.show();
    };

    App.prototype.toggleDomainClickable = async function(domain, isClickable) {
        // Find radio buttons for this domain
        const clickableRadioId = `clickable-${domain.replace(/\./g, '-')}`;
        const aRecordRadioId = `a-record-${domain.replace(/\./g, '-')}`;
        const noneRadioId = `none-${domain.replace(/\./g, '-')}`;
        const clickableRadio = document.getElementById(clickableRadioId);
        const aRecordRadio = document.getElementById(aRecordRadioId);
        const noneRadio = document.getElementById(noneRadioId);
        
        // Disable all radios while processing
        if (clickableRadio) clickableRadio.disabled = true;
        if (aRecordRadio) aRecordRadio.disabled = true;
        if (noneRadio) noneRadio.disabled = true;
        
        try {
            const data = await api.toggleDomainClickable(domain, isClickable);
            if (data.success) {
                // Get translation with fallback
                const translations = i18n.translations[i18n.currentLanguage] || i18n.translations['en'] || {};
                let message = isClickable 
                    ? (translations['domain_made_clickable'] || 'Domain is now clickable in ratings (5% less rewards)')
                    : (translations['domain_made_not_clickable'] || 'Domain is no longer clickable in ratings');
                
                // Show warning if A-record bonus was disabled (translate known backend messages)
                if (data.a_record_bonus_disabled && data.warnings && data.warnings.length > 0) {
                    const tr = i18n.translations[i18n.currentLanguage] || {};
                    const translated = data.warnings.map(w => {
                        if (w.includes('clickability is enabled')) return tr.a_record_bonus_disabled_clickable || w;
                        if (w.includes('A-record points to our server')) return tr.clickability_disabled_arecord || w;
                        if (w.includes('A-record bonus has been disabled')) return tr.a_record_bonus_disabled || w;
                        return w;
                    });
                    message += '. ' + translated.join('. ');
                }
                
                this.showToast('success', message);
                await this.loadDomains();
            } else {
                const translations = i18n.translations[i18n.currentLanguage] || i18n.translations['en'] || {};
                this.showToast('error', data.error || translations['toggle_clickable_failed'] || 'Failed to update domain clickability');
                // Revert radio button state on error
                if (isClickable && clickableRadio) {
                    clickableRadio.checked = false;
                    if (noneRadio) noneRadio.checked = true;
                } else if (!isClickable && noneRadio) {
                    noneRadio.checked = false;
                }
            }
        } catch (error) {
            const translations = i18n.translations[i18n.currentLanguage] || i18n.translations['en'] || {};
            this.showToast('error', error.message || translations['toggle_clickable_failed'] || 'Failed to update domain clickability');
            // Revert radio button state on error
            if (isClickable && clickableRadio) {
                clickableRadio.checked = false;
                if (noneRadio) noneRadio.checked = true;
            } else if (!isClickable && noneRadio) {
                noneRadio.checked = false;
            }
        } finally {
            // Re-enable radios
            if (clickableRadio) clickableRadio.disabled = false;
            if (aRecordRadio) aRecordRadio.disabled = false;
            if (noneRadio) noneRadio.disabled = false;
        }
    };

    App.prototype.verifyDomainARecord = async function(domain) {
        const radioId = `a-record-${domain.replace(/\./g, '-')}`;
        const radio = document.getElementById(radioId);
        
        try {
            this.showToast('info', i18n.t('verifying_a_record') || 'Verifying A-record...');
            const data = await api.verifyARecord(domain);
            if (data.success && data.points_to_us) {
                const translations = i18n.translations[i18n.currentLanguage] || i18n.translations['en'] || {};
                let message = translations['a_record_verified'] || 'A-record verified successfully';
                if (data.warnings && data.warnings.length > 0) {
                    const translated = data.warnings.map(w => {
                        if (w.includes('clickability is enabled')) return translations.a_record_bonus_disabled_clickable || w;
                        if (w.includes('A-record points to our server')) return translations.clickability_disabled_arecord || w;
                        if (w.includes('A-record bonus has been disabled')) return translations.a_record_bonus_disabled || w;
                        return w;
                    });
                    message += '. ' + translated.join('. ');
                }
                this.showToast('success', message);
                await this.loadDomains();
            } else {
                // A-record does not point to us or verification failed
                const translations = i18n.translations[i18n.currentLanguage] || i18n.translations['en'] || {};
                this.showToast('error', data.error || data.message || translations['a_record_verification_failed'] || 'A-record does not point to our server');
                // Reset radio button to "Neither" option
                if (radio) {
                    radio.checked = false;
                    const noneRadio = document.getElementById(`none-${domain.replace(/\./g, '-')}`);
                    if (noneRadio) {
                        noneRadio.checked = true;
                    }
                }
            }
        } catch (error) {
            const translations = i18n.translations[i18n.currentLanguage] || i18n.translations['en'] || {};
            this.showToast('error', error.message || translations['a_record_verification_failed'] || 'Failed to verify A-record');
            // Reset radio button on error
            if (radio) {
                radio.checked = false;
                const noneRadio = document.getElementById(`none-${domain.replace(/\./g, '-')}`);
                if (noneRadio) {
                    noneRadio.checked = true;
                }
            }
        }
    };

    App.prototype.verifyDomain = async function(domain) {
        // Find the verify button for this domain
        const buttonId = `verify-btn-${domain.replace(/\./g, '-')}`;
        const verifyBtn = document.getElementById(buttonId);
        
        // Save original button state
        const originalDisabled = verifyBtn ? verifyBtn.disabled : false;
        
        // Disable button and show global loading overlay
        if (verifyBtn) {
            verifyBtn.disabled = true;
        }
        this.showLoading(i18n.t('verifying_domain') || 'Verifying domain...');
        
        try {
            const data = await api.verifyDomain(domain);
            this.hideLoading();
            
            if (data.success && data.verified) {
                this.showToast('success', i18n.t('domain_verified_success') || 'Domain verified successfully!');
                await this.loadDomains();
            } else {
                // Get translated error message
                let errorMsg = i18n.t('verification_failed') || 'Verification failed';
                if (data.error_code) {
                    const errorKey = `error_${data.error_code}`;
                    const translatedError = i18n.t(errorKey);
                    // Check if translation was found (i18n.t returns [key] when not found)
                    if (translatedError && !translatedError.startsWith('[') && translatedError !== errorKey) {
                        errorMsg = translatedError;
                    } else {
                        // Fallback: use a generic message
                        errorMsg = i18n.t('verification_failed') || 'Verification failed';
                    }
                } else if (data.error) {
                    errorMsg = data.error;
                }
                
                // Only log system errors to console, not validation errors
                if (data.error_type === 'system') {
                    console.error('[App] Verification system error:', data);
                }
                
                this.showToast('error', errorMsg);
            }
            
            // Restore button state
            if (verifyBtn) {
                verifyBtn.disabled = originalDisabled;
            }
        } catch (error) {
            this.hideLoading();
            // Network/system errors - log to console
            console.error('[App] Verification error:', error);
            this.showToast('error', error.message || i18n.t('verification_failed') || 'Verification failed');
            // Restore button state on error
            if (verifyBtn) {
                verifyBtn.disabled = originalDisabled;
            }
        }
    };

})();
