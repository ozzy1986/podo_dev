/**
 * Ratings Module
 * Rating pages, sorting, pagination, promote/subscribe
 */
(function() {
    'use strict';

    App.prototype.showRating = function() {
        const main = document.getElementById('main-content');
        if (!main) {
            console.error('[App] Main content element not found!');
            return;
        }
        
        // Get filters from URL query parameters
        const urlParams = new URLSearchParams(window.location.search);
        const walletFilter = urlParams.get('wallet');
        const sldLengthParam = urlParams.get('sld_length');
        const sldLength = (sldLengthParam === 'all' || sldLengthParam === null || sldLengthParam === '') ? 'all' : (parseInt(sldLengthParam, 10) || 18);
        const registrarIdParam = urlParams.get('registrar_id');
        const registrarId = (registrarIdParam && parseInt(registrarIdParam, 10)) ? parseInt(registrarIdParam, 10) : null;
        const registrarName = urlParams.get('registrar_name') || null;
        const hosterIdParam = urlParams.get('hoster_id');
        const hosterId = (hosterIdParam && parseInt(hosterIdParam, 10)) ? parseInt(hosterIdParam, 10) : null;
        const hosterName = urlParams.get('hoster_name') || null;
        const zoneFilter = urlParams.get('zone') || null;
        const sortByParam = urlParams.get('sort_by');
        const sortOrderParam = urlParams.get('sort_order');
        const sortBy = (sortByParam && ['weight', 'rating', 'age', 'length', 'newest', 'creation_date'].includes(sortByParam)) ? sortByParam : this.ratingSortBy;
        const sortOrder = (sortOrderParam === 'asc' || sortOrderParam === 'desc') ? sortOrderParam : this.ratingSortOrder;
        this.ratingSortBy = sortBy;
        this.ratingSortOrder = sortOrder;
        
        // Show loading state
        const filterAlerts = this.buildRatingFilterAlerts(walletFilter, registrarId, registrarName, hosterId, hosterName, zoneFilter);
        main.innerHTML = `
            <div class="rating-page">
                <div class="d-flex justify-content-between align-items-center mb-4">
                    <h2 data-i18n="domains_rating">Ratings</h2>
                    ${api.token ? '' : `<a href="/login" class="btn btn-primary btn-sm" onclick="event.preventDefault(); router.navigate('/login');" data-i18n="login">Login</a>`}
                </div>
                ${filterAlerts}
                <div class="text-center py-5">
                    <div class="spinner-border text-primary" role="status">
                        <span class="visually-hidden" data-i18n="loading">Loading...</span>
                    </div>
                    <p class="mt-3" data-i18n="loading_rating">Loading domains rating...</p>
                </div>
            </div>
        `;
        this.updateI18n();
        
        // Load rating data with filters
        this.loadRating(1, sortBy, sortOrder, walletFilter, sldLength, registrarId, hosterId, zoneFilter);
    };

    App.prototype.buildRatingsNav = function() {
        const path = window.location.pathname.replace(/\/$/, '') || '/';
        const routes = [
            { path: '/rating', key: 'rating_nav_domains', fallback: 'Domains' },
            { path: '/registrars-rating', key: 'rating_nav_registrars', fallback: 'Registrars' },
            { path: '/hosters-rating', key: 'rating_nav_hosters', fallback: 'Hosters' },
            { path: '/zones-rating', key: 'rating_nav_zones', fallback: 'Zones' },
            { path: '/wallets-rating', key: 'rating_nav_wallets', fallback: 'Wallets' }
        ];
        return routes.map(r => {
            const isActive = (r.path === '/rating' && (path === '/rating' || path === '/')) ||
                (r.path !== '/rating' && path.includes(r.path.replace('/', '')));
            if (isActive) {
                return `<span class="ratings-nav-item active me-2 fw-bold" data-i18n="${r.key}">${r.fallback}</span>`;
            }
            return `<a href="${r.path}" class="ratings-nav-item me-2" onclick="event.preventDefault(); router.navigate('${r.path}');" data-i18n="${r.key}">${r.fallback}</a>`;
        }).join('');
    };

    App.prototype.buildRatingFilterAlerts = function(wallet, registrarId, registrarName, hosterId, hosterName, zone) {
        const clearLink = `<a href="/rating" class="ms-2" onclick="event.preventDefault(); window.history.replaceState({}, '', '/rating'); app.showRating();" data-i18n="clear_filter">Clear filter</a>`;
        const alerts = [];
        if (wallet) {
            alerts.push(`<div class="alert alert-info mb-3"><i class="bi bi-info-circle me-2"></i><span data-i18n="filtered_by_wallet">Filtered by wallet:</span> <strong>${this.escapeHtml(wallet)}</strong> ${clearLink}</div>`);
        }
        if (registrarId != null && registrarName) {
            alerts.push(`<div class="alert alert-info mb-3"><i class="bi bi-info-circle me-2"></i><span data-i18n="filtered_by_registrar">Filtered by registrar:</span> <strong>${this.escapeHtml(registrarName)}</strong> ${clearLink}</div>`);
        }
        if (hosterId != null && hosterName) {
            alerts.push(`<div class="alert alert-info mb-3"><i class="bi bi-info-circle me-2"></i><span data-i18n="filtered_by_hoster">Filtered by hoster:</span> <strong>${this.escapeHtml(hosterName)}</strong> ${clearLink}</div>`);
        }
        if (zone) {
            const zoneDisplay = zone.startsWith('.') ? zone : '.' + zone;
            alerts.push(`<div class="alert alert-info mb-3"><i class="bi bi-info-circle me-2"></i><span data-i18n="filtered_by_zone">Filtered by zone:</span> <strong>${this.escapeHtml(zoneDisplay)}</strong> ${clearLink}</div>`);
        }
        return alerts.join('');
    };

    App.prototype.loadRating = async function(page, sortBy, sortOrder, wallet, sldLength, registrarId, hosterId, zone) {
        if (page === undefined) page = 1;
        if (sldLength === undefined) sldLength = 18;
        const main = document.getElementById('main-content');
        if (!main) {
            console.error('[App] Main content element not found!');
            return;
        }
        
        // Use provided sort params or fall back to stored state
        const currentSortBy = sortBy !== null && sortBy !== undefined ? sortBy : this.ratingSortBy;
        const currentSortOrder = sortOrder !== null && sortOrder !== undefined ? sortOrder : this.ratingSortOrder;
        
        // Update stored state
        this.ratingSortBy = currentSortBy;
        this.ratingSortOrder = currentSortOrder;
        
        try {
            const data = await api.getDomainsRating(page, 100, currentSortBy, currentSortOrder, wallet, sldLength, registrarId, hosterId, zone);
            
            this.renderRating(data, page, wallet, sldLength, registrarId, hosterId, zone);
            
        } catch (error) {
            console.error('[App] Error loading rating:', error);
            const urlParams = new URLSearchParams(window.location.search);
            const walletFilter = urlParams.get('wallet') || wallet;
            const sldLengthRetry = urlParams.get('sld_length');
            const sldLengthVal = (sldLengthRetry === 'all' || !sldLengthRetry) ? 'all' : (parseInt(sldLengthRetry, 10) || 18);
            const registrarIdRetry = urlParams.get('registrar_id') ? parseInt(urlParams.get('registrar_id'), 10) : null;
            const hosterIdRetry = urlParams.get('hoster_id') ? parseInt(urlParams.get('hoster_id'), 10) : null;
            const zoneRetry = urlParams.get('zone') || null;
            const filterAlerts = this.buildRatingFilterAlerts(walletFilter, registrarIdRetry, urlParams.get('registrar_name'), hosterIdRetry, urlParams.get('hoster_name'), zoneRetry);
            main.innerHTML = `
                <div class="rating-page">
                    <div class="d-flex justify-content-between align-items-center mb-4">
                        <h2 data-i18n="domains_rating">Ratings</h2>
                        ${api.token ? '' : `<a href="/login" class="btn btn-primary btn-sm" onclick="event.preventDefault(); router.navigate('/login');" data-i18n="login">Login</a>`}
                    </div>
                    ${filterAlerts}
                    <div class="alert alert-danger" role="alert">
                        <i class="bi bi-exclamation-triangle me-2"></i>
                        <span data-i18n="error_loading_rating">Failed to load domains rating. Please try again later.</span>
                    </div>
                    <button class="btn btn-primary" id="rating-retry-btn" data-i18n="retry">Retry</button>
                </div>
            `;
            const retryBtn = document.getElementById('rating-retry-btn');
            if (retryBtn) {
                retryBtn.addEventListener('click', () => {
                    this.loadRating(1, this.ratingSortBy, this.ratingSortOrder, walletFilter, sldLengthVal, registrarIdRetry, hosterIdRetry, zoneRetry);
                });
            }
            
            this.updateI18n();
        }
    };

    App.prototype.getSortIndicator = function(sortField) {
        if (this.ratingSortBy !== sortField) {
            return '<i class="bi bi-arrow-down-up sort-indicator"></i>';
        }
        if (this.ratingSortOrder === 'asc') {
            return '<i class="bi bi-arrow-up sort-indicator sort-active"></i>';
        } else {
            return '<i class="bi bi-arrow-down sort-indicator sort-active"></i>';
        }
    };

    App.prototype.renderRating = function(data, currentPage, wallet, sldLength, registrarId, hosterId, zone) {
        const main = document.getElementById('main-content');
        if (!main) return;
        
        const urlParams = new URLSearchParams(window.location.search);
        if (wallet == null) wallet = urlParams.get('wallet');
        if (sldLength == null) sldLength = (urlParams.get('sld_length') === 'all' || !urlParams.get('sld_length')) ? 'all' : (parseInt(urlParams.get('sld_length'), 10) || 18);
        if (registrarId == null && urlParams.get('registrar_id')) registrarId = parseInt(urlParams.get('registrar_id'), 10);
        if (hosterId == null && urlParams.get('hoster_id')) hosterId = parseInt(urlParams.get('hoster_id'), 10);
        if (zone == null) zone = urlParams.get('zone');
        
        const { domains, total, page, per_page, total_pages } = data;
        
        // Calculate rank offset based on current page
        const rankOffset = (page - 1) * per_page;
        
        // Build domain rows
        let domainRows = '';
        if (domains && domains.length > 0) {
            domains.forEach((d, index) => {
                const rank = rankOffset + index + 1;
                // Only apply special styling to actual ranks 1, 2, 3
                let rankClass = '';
                if (rank === 1) {
                    rankClass = 'rank-gold';
                } else if (rank === 2) {
                    rankClass = 'rank-silver';
                } else if (rank === 3) {
                    rankClass = 'rank-bronze';
                }
                
                // Check if user owns this domain
                const isUserDomain = this.user && d.user_id === this.user.id;
                
                // Render domain as link if clickable, otherwise as text
                let domainDisplay = d.is_clickable 
                    ? `<a href="http://${this.escapeHtml(d.domain)}" target="_blank" rel="noopener noreferrer" class="text-decoration-none">${this.escapeHtml(d.domain)}</a>`
                    : this.escapeHtml(d.domain);
                
                // Add subscription badge if domain has subscription
                if (d.has_subscription) {
                    domainDisplay += ` <span class="badge bg-success text-white ms-2" data-i18n="subscribed">Subscribed</span>`;
                }
                
                // Short description teaser (truncate with ellipsis to encourage clicking to domain page)
                const maxDescLen = 80;
                let shortDescriptionHtml = '';
                if (d.description && typeof d.description === 'string') {
                    const trimmed = d.description.trim();
                    if (trimmed) {
                        const truncated = trimmed.length > maxDescLen
                            ? trimmed.substring(0, maxDescLen).trim() + '…'
                            : trimmed;
                        shortDescriptionHtml = `<small class="text-muted d-block mt-1">${this.escapeHtml(truncated)}</small>`;
                    }
                }
                
                // Format creation date (prefer Russian format DD.MM.YYYY if available)
                let creationDateDisplay = d.creation_date_ru || 'N/A';
                if (creationDateDisplay === 'N/A' && d.creation_date) {
                    try {
                        const date = new Date(d.creation_date);
                        creationDateDisplay = date.toLocaleDateString('en-US', { 
                            year: 'numeric', 
                            month: 'short', 
                            day: 'numeric' 
                        });
                    } catch (e) {
                        creationDateDisplay = 'N/A';
                    }
                }
                
                const domainPagePath = '/domain/' + encodeURIComponent(d.domain);
                const viewDomainPageLabel = (typeof i18n !== 'undefined' && i18n.t) ? i18n.t('view_domain_page') : 'Domain page';
                const ratingVal = (d.rating != null && d.rating !== undefined) ? d.rating : d.total_earnings;
                const lengthVal = (d.length != null && d.length !== undefined) ? d.length : d.sld_length;
                const karmaVal = typeof d.karma === 'number' ? d.karma : 0;
                const uv = d.user_vote;
                const upActive = uv === 1 ? ' active' : '';
                const downActive = uv === -1 ? ' active' : '';
                const isOwnDomain = this.user && d.user_id === this.user.id;
                const commentsCountVal = typeof d.comments_count === 'number' ? d.comments_count : 0;
                const likesCell = api.token
                    ? `<div class="d-inline-flex align-items-center justify-content-end flex-wrap">
                        <div class="d-inline-flex align-items-center">
                            <button type="button" class="btn btn-sm btn-outline-secondary rating-vote-up${upActive}" data-domain-id="${d.id}" data-value="1" title="Like" aria-label="Like"><i class="bi bi-arrow-up"></i></button>
                            <span class="d-inline-block text-center px-1 rating-karma-val" style="min-width: 1.5rem;">${karmaVal}</span>
                            ${isOwnDomain ? '' : `<button type="button" class="btn btn-sm btn-outline-secondary rating-vote-down${downActive}" data-domain-id="${d.id}" data-value="-1" title="Dislike" aria-label="Dislike"><i class="bi bi-arrow-down"></i></button>`}
                        </div>
                        <span class="text-muted small ms-1" title="${(typeof i18n !== 'undefined' && i18n.t) ? i18n.t('comments') : 'Comments'}">· <span class="rating-comments-count">${commentsCountVal}</span></span>
                       </div>`
                    : `<span class="rating-karma-val">${karmaVal}</span><span class="text-muted small ms-1">· <span class="rating-comments-count">${commentsCountVal}</span></span><small class="text-muted ms-1" data-i18n="login_to_vote">Log in to vote</small>`;
                domainRows += `
                    <tr data-domain-id="${d.id}">
                        <td class="text-center rank-col ${rankClass}">${rank}</td>
                        <td class="domain-col">${domainDisplay}${shortDescriptionHtml}</td>
                        <td class="text-center domain-page-col">
                            <a href="${domainPagePath}" class="btn btn-sm btn-outline-primary" data-domain-page-path="${this.escapeHtml(domainPagePath)}" onclick="event.preventDefault(); router.navigate(this.getAttribute('data-domain-page-path'));" title="${this.escapeHtml(viewDomainPageLabel)}" aria-label="${this.escapeHtml(viewDomainPageLabel)}">
                                <i class="bi bi-box-arrow-up-right" aria-hidden="true"></i>
                            </a>
                        </td>
                        <td class="text-center newest-col"></td>
                        <td class="text-center length-col">${lengthVal != null && lengthVal !== '' ? lengthVal : 'N/A'}</td>
                        <td class="text-center age-col">${d.age != null && d.age !== '' ? d.age : 'N/A'}</td>
                        <td class="text-center creation-date-col">${creationDateDisplay}</td>
                        <td class="text-end rating-col"><strong>${this.formatNumber(ratingVal != null ? ratingVal : 0, 2)}</strong></td>
                        <td class="text-end weight-col">${this.formatNumber(d.weight, 2)}</td>
                        <td class="text-end karma-col">${likesCell}</td>
                    </tr>
                `;
            });
        } else {
            domainRows = `
                <tr>
                    <td colspan="10" class="text-center text-muted py-4" data-i18n="no_domains_found">No mining domains found</td>
                </tr>
            `;
        }
        
        // Build pagination
        let pagination = '';
        if (total_pages > 1) {
            pagination = `
                <nav aria-label="Domains rating pagination" class="mt-4">
                    <ul class="pagination justify-content-center flex-wrap" id="rating-pagination">
                        <li class="page-item ${page <= 1 ? 'disabled' : ''}">
                            <a class="page-link" href="#" data-rating-page="${page - 1}" data-i18n="previous">Previous</a>
                        </li>
                        ${this.buildPaginationItems(page, total_pages)}
                        <li class="page-item ${page >= total_pages ? 'disabled' : ''}">
                            <a class="page-link" href="#" data-rating-page="${page + 1}" data-i18n="next">Next</a>
                        </li>
                    </ul>
                </nav>
            `;
        }
        
        main.innerHTML = `
            <div class="rating-page">
                <div class="d-flex justify-content-between align-items-center mb-4 flex-wrap gap-2">
                    <h2 class="mb-0" data-i18n="domains_rating">Ratings</h2>
                    <div class="d-flex align-items-center gap-3">
                        <span class="text-muted">
                            <span data-i18n="total_domains">Total domains</span>: <strong>${total}</strong>
                        </span>
                        ${api.token ? '' : `<a href="/login" class="btn btn-primary btn-sm" onclick="event.preventDefault(); router.navigate('/login');" data-i18n="login">Login</a>`}
                    </div>
                </div>
                
                ${this.buildRatingFilterAlerts(wallet, registrarId, urlParams.get('registrar_name'), hosterId, urlParams.get('hoster_name'), zone)}
                
                <div class="rating-info alert alert-info mb-4 d-none"><!-- Hidden for now; remove d-none to show -->
                    <i class="bi bi-info-circle me-2"></i>
                    <span data-i18n="rating_info">Rating is based on total earnings. Higher rating means the domain has earned more tokens.</span>
                </div>
                
                <div class="mb-3 ratings-nav-wrap">
                    <span class="text-muted me-2" data-i18n="ratings">Ratings:</span>
                    ${this.buildRatingsNav()}
                </div>
                
                <div class="table-responsive">
                    <table class="table table-hover rating-table">
                        <thead class="table-dark">
                            <tr>
                                <th class="text-center rank-col" data-i18n="rank">#</th>
                                <th class="domain-col" data-i18n="domain_name">Domain</th>
                                <th class="text-center domain-page-col" scope="col"><span class="visually-hidden" data-i18n="view_domain_page">Domain page</span></th>
                                <th class="text-center newest-col sortable" data-sort="newest">
                                    <span data-i18n="newest">Newest</span> ${this.getSortIndicator('newest')}
                                </th>
                                <th class="text-center length-col">
                                    <span data-i18n="length">Length</span>
                                    <select class="form-select form-select-sm d-inline-block w-auto ms-1" id="rating-length-filter" title="Filter by domain length">
                                        <option value="18" ${(sldLength === 18 || sldLength === '18') ? 'selected' : ''}>18+</option>
                                        ${[17,16,15,14,13,12,11,10,9,8,7,6,5,4,3,2,1].map(n => `<option value="${n}" ${sldLength === n ? 'selected' : ''}>${n}</option>`).join('')}
                                        <option value="all" ${sldLength === 'all' ? 'selected' : ''}>All</option>
                                    </select>
                                </th>
                                <th class="text-center age-col sortable" data-sort="age">
                                    <span data-i18n="age">Age</span> ${this.getSortIndicator('age')}
                                </th>
                                <th class="text-center creation-date-col sortable" data-sort="creation_date">
                                    <span data-i18n="registration_date">Registration Date</span> ${this.getSortIndicator('creation_date')}
                                </th>
                                <th class="text-end rating-col sortable" data-sort="rating">
                                    <span data-i18n="rating_col">Rating</span> ${this.getSortIndicator('rating')}
                                </th>
                                <th class="text-end weight-col sortable" data-sort="weight">
                                    <span data-i18n="weight">Weight</span> ${this.getSortIndicator('weight')}
                                </th>
                                <th class="text-end karma-col" data-i18n="likes">Likes</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${domainRows}
                        </tbody>
                    </table>
                </div>
                
                ${pagination}
                
                <div class="text-center text-muted mt-3">
                    <small><span data-i18n="page">Page</span> ${page} / ${total_pages}</small>
                </div>
            </div>
        `;
        
        // Setup pagination event listeners
        this.setupPaginationListeners();
        
        // Setup sort event listeners
        this.setupSortListeners();
        
        // Setup length filter (carousel)
        this.setupLengthFilterListener();
        
        // Setup domain vote (like/dislike) buttons
        this.setupRatingVoteListeners();
        
        this.updateI18n();
    };

    App.prototype.setupRatingVoteListeners = function() {
        const main = document.getElementById('main-content');
        if (!main) return;
        main.querySelectorAll('.rating-vote-up, .rating-vote-down').forEach(function(btn) {
            btn.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                if (!api.token) return;
                const domainId = parseInt(btn.getAttribute('data-domain-id'), 10);
                const value = parseInt(btn.getAttribute('data-value'), 10);
                if (isNaN(domainId)) return;
                const row = btn.closest('tr[data-domain-id]');
                const karmaEl = row ? row.querySelector('.rating-karma-val') : null;
                const currentKarma = parseInt(karmaEl ? karmaEl.textContent : '0', 10) || 0;
                const currentUserVote = row && row.querySelector('.rating-vote-up.active') ? 1 : (row && row.querySelector('.rating-vote-down.active') ? -1 : 0);
                main.querySelectorAll('.paid-vote-form-wrap').forEach(function(f) {
                    var tr = f.closest ? f.closest('tr[data-paid-vote-row]') : null;
                    if (f.parentNode) f.parentNode.removeChild(f);
                    if (tr && tr.parentNode) tr.parentNode.removeChild(tr);
                });
                api.setVote('domain', domainId, null, value).then(function(res) {
                    const newKarma = res && res.karma != null ? res.karma : (currentKarma + value - currentUserVote);
                    if (karmaEl) karmaEl.textContent = newKarma;
                    if (row) {
                        row.querySelectorAll('.rating-vote-up, .rating-vote-down').forEach(function(b) {
                            const v = parseInt(b.getAttribute('data-value'), 10);
                            b.classList.toggle('active', v === value);
                        });
                    }
                }).catch(function(err) {
                    var isPaidVoteRequired = err && err.status === 409 && (
                        (err.responseData && err.responseData.details && err.responseData.details.code === 'PAID_VOTE_REQUIRED') ||
                        (err.responseData && err.responseData.detail && err.responseData.detail.code === 'PAID_VOTE_REQUIRED') ||
                        (err.responseData && err.responseData.error && String(err.responseData.error).indexOf('Paid vote') !== -1)
                    );
                    if (isPaidVoteRequired) {
                        var domainCol = row ? row.querySelector('.domain-col') : null;
                        var domainName = (domainCol && domainCol.textContent) ? domainCol.textContent.trim() : ('domain #' + domainId);
                        var domainLabel = (typeof i18n !== 'undefined' && i18n.t ? i18n.t('domain') : 'Domain');
                        if (typeof showPaidVoteForm === 'function') {
                            showPaidVoteForm({
                                anchorEl: row ? row.querySelector('.karma-col') || row : document.getElementById('main-content'),
                                targetLabel: domainLabel + ': ' + domainName,
                                targetType: 'domain',
                                targetId: domainId,
                                targetKey: null,
                                value: value,
                                onSuccess: function(res) {
                                    if (karmaEl && res && res.karma != null) karmaEl.textContent = res.karma;
                                    if (row) {
                                        row.querySelectorAll('.rating-vote-up, .rating-vote-down').forEach(function(b) {
                                            const v = parseInt(b.getAttribute('data-value'), 10);
                                            b.classList.toggle('active', v === value);
                                        });
                                    }
                                }
                            });
                        } else {
                            if (typeof app !== 'undefined' && app.showToast) app.showToast('danger', 'Vote failed');
                        }
                    } else {
                        if (typeof app !== 'undefined' && app.showToast) app.showToast('danger', 'Vote failed');
                    }
                });
            });
        });
    };

    App.prototype.setupLengthFilterListener = function() {
        const sel = document.getElementById('rating-length-filter');
        if (!sel) return;
        sel.addEventListener('change', () => {
            const val = sel.value;
            const urlParams = new URLSearchParams(window.location.search);
            if (val === 'all') urlParams.set('sld_length', 'all');
            else urlParams.set('sld_length', val);
            urlParams.delete('page');
            const newUrl = window.location.pathname + (urlParams.toString() ? '?' + urlParams.toString() : '');
            window.history.replaceState({}, '', newUrl);
            const wallet = urlParams.get('wallet');
            const registrarId = urlParams.get('registrar_id') ? parseInt(urlParams.get('registrar_id'), 10) : null;
            const hosterId = urlParams.get('hoster_id') ? parseInt(urlParams.get('hoster_id'), 10) : null;
            const zone = urlParams.get('zone') || null;
            this.loadRating(1, this.ratingSortBy, this.ratingSortOrder, wallet, val === 'all' ? 'all' : parseInt(val, 10), registrarId, hosterId, zone);
        });
    };

    App.prototype.setupSortListeners = function() {
        const sortableHeaders = document.querySelectorAll('.rating-table th.sortable');
        sortableHeaders.forEach(header => {
            header.style.cursor = 'pointer';
            header.addEventListener('click', (e) => {
                e.preventDefault();
                const sortField = header.getAttribute('data-sort');
                if (!sortField) return;
                
                // Toggle sort order if clicking the same field, otherwise set to desc
                let newSortOrder = 'desc';
                if (this.ratingSortBy === sortField) {
                    newSortOrder = this.ratingSortOrder === 'desc' ? 'asc' : 'desc';
                }
                
                const urlParams = new URLSearchParams(window.location.search);
                const wallet = urlParams.get('wallet');
                const sldLength = urlParams.get('sld_length');
                const sld = (sldLength === 'all' || !sldLength) ? 'all' : (parseInt(sldLength, 10) || 18);
                const registrarId = urlParams.get('registrar_id') ? parseInt(urlParams.get('registrar_id'), 10) : null;
                const hosterId = urlParams.get('hoster_id') ? parseInt(urlParams.get('hoster_id'), 10) : null;
                const zone = urlParams.get('zone') || null;
                
                this.loadRating(1, sortField, newSortOrder, wallet, sld, registrarId, hosterId, zone);
            });
        });
    };

    App.prototype.buildPaginationItems = function(currentPage, totalPages) {
        let items = '';
        const maxVisible = 5;
        
        let startPage = Math.max(1, currentPage - Math.floor(maxVisible / 2));
        let endPage = Math.min(totalPages, startPage + maxVisible - 1);
        
        if (endPage - startPage < maxVisible - 1) {
            startPage = Math.max(1, endPage - maxVisible + 1);
        }
        
        if (startPage > 1) {
            items += `<li class="page-item"><a class="page-link" href="#" data-rating-page="1">1</a></li>`;
            if (startPage > 2) {
                items += `<li class="page-item disabled"><span class="page-link">...</span></li>`;
            }
        }
        
        for (let i = startPage; i <= endPage; i++) {
            items += `
                <li class="page-item ${i === currentPage ? 'active' : ''}">
                    <a class="page-link" href="#" data-rating-page="${i}">${i}</a>
                </li>
            `;
        }
        
        if (endPage < totalPages) {
            if (endPage < totalPages - 1) {
                items += `<li class="page-item disabled"><span class="page-link">...</span></li>`;
            }
            items += `<li class="page-item"><a class="page-link" href="#" data-rating-page="${totalPages}">${totalPages}</a></li>`;
        }
        
        return items;
    };

    App.prototype.setupPaginationListeners = function() {
        // Use event delegation on the pagination container
        const pagination = document.getElementById('rating-pagination');
        if (!pagination) return;
        
        pagination.addEventListener('click', (e) => {
            const link = e.target.closest('a.page-link[data-rating-page]');
            if (!link) return;
            
            const pageStr = link.getAttribute('data-rating-page');
            if (!pageStr) return;
            
            const page = parseInt(pageStr, 10);
            if (isNaN(page) || page < 1) return;
            
            // Check if disabled
            const listItem = link.closest('.page-item');
            if (listItem && listItem.classList.contains('disabled')) return;
            
            e.preventDefault();
            e.stopPropagation();
            
            const urlParams = new URLSearchParams(window.location.search);
            const wallet = urlParams.get('wallet');
            const sldLength = urlParams.get('sld_length');
            const sld = (sldLength === 'all' || !sldLength) ? 'all' : (parseInt(sldLength, 10) || 18);
            const registrarId = urlParams.get('registrar_id') ? parseInt(urlParams.get('registrar_id'), 10) : null;
            const hosterId = urlParams.get('hoster_id') ? parseInt(urlParams.get('hoster_id'), 10) : null;
            const zone = urlParams.get('zone') || null;
            
            this.loadRating(page, null, null, wallet, sld, registrarId, hosterId, zone);
            
            return false;
        });
    };

    // --- Wallets Rating ---

    App.prototype.showWalletsRating = function() {
        const main = document.getElementById('main-content');
        if (!main) return;
        
        // Show loading state
        main.innerHTML = `
            <div class="rating-page">
                <div class="d-flex justify-content-between align-items-center mb-4">
                    <h2 data-i18n="wallets_rating">Wallets Rating</h2>
                    ${api.token ? '' : `<a href="/login" class="btn btn-primary btn-sm" onclick="event.preventDefault(); router.navigate('/login');" data-i18n="login">Login</a>`}
                </div>
                <div class="text-center py-5">
                    <div class="spinner-border text-primary" role="status">
                        <span class="visually-hidden" data-i18n="loading">Loading...</span>
                    </div>
                    <p class="mt-3" data-i18n="loading_wallets_rating">Loading wallets rating...</p>
                </div>
            </div>
        `;
        this.updateI18n();
        
        // Load wallets rating data
        this.loadWalletsRating(1, this.walletsRatingSortBy, this.walletsRatingSortOrder);
    };

    App.prototype.loadWalletsRating = async function(page, sortBy, sortOrder) {
        if (page === undefined) page = 1;
        const main = document.getElementById('main-content');
        if (!main) {
            console.error('[App] Main content element not found!');
            return;
        }
        
        // Use provided sort params or fall back to stored state
        const currentSortBy = sortBy !== null && sortBy !== undefined ? sortBy : this.walletsRatingSortBy;
        const currentSortOrder = sortOrder !== null && sortOrder !== undefined ? sortOrder : this.walletsRatingSortOrder;
        
        // Update stored state
        this.walletsRatingSortBy = currentSortBy;
        this.walletsRatingSortOrder = currentSortOrder;
        
        try {
            const data = await api.getWalletsRating(page, 100, currentSortBy, currentSortOrder);
            
            this.renderWalletsRating(data, page);
            
        } catch (error) {
            console.error('[App] Error loading wallets rating:', error);
            main.innerHTML = `
                <div class="rating-page">
                    <div class="d-flex justify-content-between align-items-center mb-4">
                        <h2 data-i18n="wallets_rating">Wallets Rating</h2>
                        ${api.token ? '' : `<a href="/login" class="btn btn-primary btn-sm" onclick="event.preventDefault(); router.navigate('/login');" data-i18n="login">Login</a>`}
                    </div>
                    <div class="alert alert-danger" role="alert">
                        <i class="bi bi-exclamation-triangle me-2"></i>
                        <span data-i18n="error_loading_wallets_rating">Failed to load wallets rating. Please try again later.</span>
                    </div>
                    <button class="btn btn-primary" id="wallets-rating-retry-btn" data-i18n="retry">Retry</button>
                </div>
            `;
            // Setup retry button listener
            const retryBtn = document.getElementById('wallets-rating-retry-btn');
            if (retryBtn) {
                retryBtn.addEventListener('click', () => {
                    this.loadWalletsRating(1, this.walletsRatingSortBy, this.walletsRatingSortOrder);
                });
            }
            
            this.updateI18n();
        }
    };

    App.prototype.getWalletsSortIndicator = function(sortField) {
        if (this.walletsRatingSortBy !== sortField) {
            return '<i class="bi bi-arrow-down-up sort-indicator"></i>';
        }
        if (this.walletsRatingSortOrder === 'asc') {
            return '<i class="bi bi-arrow-up sort-indicator sort-active"></i>';
        } else {
            return '<i class="bi bi-arrow-down sort-indicator sort-active"></i>';
        }
    };

    App.prototype.renderWalletsRating = function(data, currentPage) {
        const main = document.getElementById('main-content');
        if (!main) return;
        
        const { wallets, total, page, per_page, total_pages } = data;
        
        // Calculate rank offset based on current page
        const rankOffset = (page - 1) * per_page;
        
        // Build wallet rows
        let walletRows = '';
        if (wallets && wallets.length > 0) {
            wallets.forEach((w, index) => {
                const rank = rankOffset + index + 1;
                let rankClass = '';
                if (rank === 1) rankClass = 'rank-gold';
                else if (rank === 2) rankClass = 'rank-silver';
                else if (rank === 3) rankClass = 'rank-bronze';
                walletRows += `
                    <tr class="wallet-row-clickable" data-wallet="${this.escapeHtml(w.wallet)}" style="cursor: pointer;">
                        <td class="text-center rank-col ${rankClass}">${rank}</td>
                        <td class="wallet-col">${this.escapeHtml(w.wallet)}</td>
                        <td class="text-center domains-count-col">${w.domains_count || 0}</td>
                        <td class="text-end rating-col"><strong>${this.formatNumber(w.rating, 2)}</strong></td>
                    </tr>
                `;
            });
        } else {
            walletRows = `<tr><td colspan="4" class="text-center text-muted py-4" data-i18n="no_wallets_found">No wallets found</td></tr>`;
        }
        
        // Build pagination
        let pagination = '';
        if (total_pages > 1) {
            pagination = `
                <nav aria-label="Wallets rating pagination" class="mt-4">
                    <ul class="pagination justify-content-center flex-wrap" id="wallets-rating-pagination">
                        <li class="page-item ${page <= 1 ? 'disabled' : ''}">
                            <a class="page-link" href="#" data-wallets-rating-page="${page - 1}" data-i18n="previous">Previous</a>
                        </li>
                        ${this.buildWalletsPaginationItems(page, total_pages)}
                        <li class="page-item ${page >= total_pages ? 'disabled' : ''}">
                            <a class="page-link" href="#" data-wallets-rating-page="${page + 1}" data-i18n="next">Next</a>
                        </li>
                    </ul>
                </nav>
            `;
        }
        
        main.innerHTML = `
            <div class="rating-page">
                <div class="mb-3 ratings-nav-wrap">
                    <span class="text-muted me-2" data-i18n="ratings">Ratings:</span>
                    ${this.buildRatingsNav()}
                </div>
                <div class="d-flex justify-content-between align-items-center mb-4 flex-wrap gap-2">
                    <h2 class="mb-0" data-i18n="wallets_rating">Wallets Rating</h2>
                    <div class="d-flex align-items-center gap-3">
                        <span class="text-muted">
                            <span data-i18n="total_wallets">Total wallets</span>: <strong>${total}</strong>
                        </span>
                        ${api.token ? '' : `<a href="/login" class="btn btn-primary btn-sm" onclick="event.preventDefault(); router.navigate('/login');" data-i18n="login">Login</a>`}
                    </div>
                </div>
                
                <div class="rating-info alert alert-info mb-4">
                    <i class="bi bi-info-circle me-2"></i>
                    <span data-i18n="wallets_rating_info">Rating is based on total earnings from all domains. Higher rating means the wallet has earned more tokens.</span>
                </div>
                
                <div class="table-responsive">
                    <table class="table table-hover rating-table">
                        <thead class="table-dark">
                            <tr>
                                <th class="text-center rank-col" data-i18n="rank">#</th>
                                <th class="wallet-col" data-i18n="wallet_address">Wallet</th>
                                <th class="text-center domains-count-col sortable" data-sort="domains_count">
                                    <span data-i18n="domains_count">Domains</span> ${this.getWalletsSortIndicator('domains_count')}
                                </th>
                                <th class="text-end rating-col sortable" data-sort="rating">
                                    <span data-i18n="rating_col">Rating</span> ${this.getWalletsSortIndicator('rating')}
                                </th>
                            </tr>
                        </thead>
                        <tbody>
                            ${walletRows}
                        </tbody>
                    </table>
                </div>
                
                ${pagination}
                
                <div class="text-center text-muted mt-3">
                    <small><span data-i18n="page">Page</span> ${page} / ${total_pages}</small>
                </div>
            </div>
        `;
        
        this.setupWalletsPaginationListeners();
        this.setupWalletsSortListeners();
        this.setupWalletsRowClickListeners();
        this.updateI18n();
    };

    App.prototype.setupWalletsRowClickListeners = function() {
        const walletRows = document.querySelectorAll('.wallet-row-clickable');
        walletRows.forEach(row => {
            row.addEventListener('click', (e) => {
                if (e.target.closest('th') || e.target.closest('.pagination') || e.target.closest('button') || e.target.closest('a')) return;
                const wallet = row.getAttribute('data-wallet');
                if (wallet) router.navigate(`/rating?wallet=${encodeURIComponent(wallet)}`);
            });
        });
    };

    App.prototype.setupWalletsSortListeners = function() {
        const sortableHeaders = document.querySelectorAll('.rating-table th.sortable');
        sortableHeaders.forEach(header => {
            header.style.cursor = 'pointer';
            header.addEventListener('click', (e) => {
                e.preventDefault();
                const sortField = header.getAttribute('data-sort');
                if (!sortField) return;
                let newSortOrder = 'desc';
                if (this.walletsRatingSortBy === sortField) {
                    newSortOrder = this.walletsRatingSortOrder === 'desc' ? 'asc' : 'desc';
                }
                this.loadWalletsRating(1, sortField, newSortOrder);
            });
        });
    };

    App.prototype.buildWalletsPaginationItems = function(currentPage, totalPages) {
        let items = '';
        const maxVisible = 5;
        let startPage = Math.max(1, currentPage - Math.floor(maxVisible / 2));
        let endPage = Math.min(totalPages, startPage + maxVisible - 1);
        if (endPage - startPage < maxVisible - 1) startPage = Math.max(1, endPage - maxVisible + 1);
        if (startPage > 1) {
            items += `<li class="page-item"><a class="page-link" href="#" data-wallets-rating-page="1">1</a></li>`;
            if (startPage > 2) items += `<li class="page-item disabled"><span class="page-link">...</span></li>`;
        }
        for (let i = startPage; i <= endPage; i++) {
            items += `<li class="page-item ${i === currentPage ? 'active' : ''}"><a class="page-link" href="#" data-wallets-rating-page="${i}">${i}</a></li>`;
        }
        if (endPage < totalPages) {
            if (endPage < totalPages - 1) items += `<li class="page-item disabled"><span class="page-link">...</span></li>`;
            items += `<li class="page-item"><a class="page-link" href="#" data-wallets-rating-page="${totalPages}">${totalPages}</a></li>`;
        }
        return items;
    };

    App.prototype.setupWalletsPaginationListeners = function() {
        const pagination = document.getElementById('wallets-rating-pagination');
        if (!pagination) return;
        pagination.addEventListener('click', (e) => {
            const link = e.target.closest('a.page-link[data-wallets-rating-page]');
            if (!link) return;
            const pageStr = link.getAttribute('data-wallets-rating-page');
            if (!pageStr) return;
            const page = parseInt(pageStr, 10);
            if (isNaN(page) || page < 1) return;
            const listItem = link.closest('.page-item');
            if (listItem && listItem.classList.contains('disabled')) return;
            e.preventDefault();
            e.stopPropagation();
            this.loadWalletsRating(page);
            return false;
        });
    };

    // --- Registrars, Hosters, Zones Ratings ---

    App.prototype.showRegistrarsRating = async function() {
        const main = document.getElementById('main-content');
        if (!main) return;
        main.innerHTML = `<div class="rating-page"><h2 data-i18n="registrars_rating">Registrars Rating</h2><div class="text-center py-5"><div class="spinner-border text-primary" role="status"></div><p class="mt-3" data-i18n="loading">Loading...</p></div></div>`;
        this.updateI18n();
        try {
            const data = await api.getRegistrarsRating(1, 100);
            this.renderRegistrarsRating(data);
        } catch (e) {
            console.error('[App] Error loading registrars rating:', e);
            main.innerHTML = `<div class="rating-page"><h2 data-i18n="registrars_rating">Registrars Rating</h2><div class="alert alert-danger" data-i18n="error_loading_rating">Failed to load.</div></div>`;
            this.updateI18n();
        }
    };

    App.prototype.renderRegistrarsRating = function(data) {
        const main = document.getElementById('main-content');
        if (!main) return;
        const { registrars = [], total } = data;
        let rows = registrars.map((r, i) => {
            const name = this.escapeHtml(r.name);
            const url = `/rating?registrar_id=${r.id}&registrar_name=${encodeURIComponent(r.name || '')}`;
            return `<tr class="rating-row-clickable" data-rating-url="${this.escapeHtml(url)}"><td class="text-center">${i + 1}</td><td>${name}</td><td class="text-end">${this.formatNumber(r.total_earnings, 2)}</td><td class="text-center">${r.domains_count || 0}</td></tr>`;
        }).join('');
        if (!rows) rows = `<tr><td colspan="4" class="text-center text-muted py-4" data-i18n="no_domains_found">No data</td></tr>`;
        main.innerHTML = `
            <div class="rating-page">
                <div class="mb-3 ratings-nav-wrap">
                    <span class="text-muted me-2" data-i18n="ratings">Ratings:</span>
                    ${this.buildRatingsNav()}
                </div>
                <div class="d-flex justify-content-between align-items-center mb-4"><h2 class="mb-0" data-i18n="registrars_rating">Registrars Rating</h2>${api.token ? '' : `<a href="/login" class="btn btn-primary btn-sm" onclick="event.preventDefault(); router.navigate('/login');" data-i18n="login">Login</a>`}</div>
                <div class="table-responsive">
                    <table class="table table-hover rating-table"><thead class="table-dark"><tr><th class="text-center" data-i18n="rank">#</th><th data-i18n="registrar_name">Registrar</th><th class="text-end" data-i18n="rating_col">Rating</th><th class="text-center" data-i18n="domains_count">Domains</th></tr></thead><tbody>${rows}</tbody></table>
                </div>
                <div class="text-center text-muted mt-3"><small><span data-i18n="total">Total</span>: ${total || 0}</small></div>
            </div>`;
        this.setupRatingRowClickListeners();
        this.updateI18n();
    };

    App.prototype.showHostersRating = async function() {
        const main = document.getElementById('main-content');
        if (!main) return;
        main.innerHTML = `<div class="rating-page"><h2 data-i18n="hosters_rating">Hosters Rating</h2><div class="text-center py-5"><div class="spinner-border text-primary" role="status"></div><p class="mt-3" data-i18n="loading">Loading...</p></div></div>`;
        this.updateI18n();
        try {
            const data = await api.getHostersRating(1, 100);
            this.renderHostersRating(data);
        } catch (e) {
            console.error('[App] Error loading hosters rating:', e);
            main.innerHTML = `<div class="rating-page"><h2 data-i18n="hosters_rating">Hosters Rating</h2><div class="alert alert-danger" data-i18n="error_loading_rating">Failed to load.</div></div>`;
            this.updateI18n();
        }
    };

    App.prototype.renderHostersRating = function(data) {
        const main = document.getElementById('main-content');
        if (!main) return;
        const { hosters = [], total } = data;
        let rows = hosters.map((h, i) => {
            const name = this.escapeHtml(h.name);
            const url = `/rating?hoster_id=${h.id}&hoster_name=${encodeURIComponent(h.name || '')}`;
            return `<tr class="rating-row-clickable" data-rating-url="${this.escapeHtml(url)}"><td class="text-center">${i + 1}</td><td>${name}</td><td class="text-end">${this.formatNumber(h.total_earnings, 2)}</td><td class="text-center">${h.domains_count || 0}</td></tr>`;
        }).join('');
        if (!rows) rows = `<tr><td colspan="4" class="text-center text-muted py-4" data-i18n="no_domains_found">No data</td></tr>`;
        main.innerHTML = `
            <div class="rating-page">
                <div class="mb-3 ratings-nav-wrap">
                    <span class="text-muted me-2" data-i18n="ratings">Ratings:</span>
                    ${this.buildRatingsNav()}
                </div>
                <div class="d-flex justify-content-between align-items-center mb-4"><h2 class="mb-0" data-i18n="hosters_rating">Hosters Rating</h2>${api.token ? '' : `<a href="/login" class="btn btn-primary btn-sm" onclick="event.preventDefault(); router.navigate('/login');" data-i18n="login">Login</a>`}</div>
                <div class="table-responsive">
                    <table class="table table-hover rating-table"><thead class="table-dark"><tr><th class="text-center" data-i18n="rank">#</th><th data-i18n="hoster_name">Hoster</th><th class="text-end" data-i18n="rating_col">Rating</th><th class="text-center" data-i18n="domains_count">Domains</th></tr></thead><tbody>${rows}</tbody></table>
                </div>
                <div class="text-center text-muted mt-3"><small><span data-i18n="total">Total</span>: ${total || 0}</small></div>
            </div>`;
        this.setupRatingRowClickListeners();
        this.updateI18n();
    };

    App.prototype.showZonesRating = async function() {
        const main = document.getElementById('main-content');
        if (!main) return;
        main.innerHTML = `<div class="rating-page"><h2 data-i18n="zones_rating">Domain zones rating</h2><div class="text-center py-5"><div class="spinner-border text-primary" role="status"></div><p class="mt-3" data-i18n="loading">Loading...</p></div></div>`;
        this.updateI18n();
        try {
            const data = await api.getDomainZonesRating(1, 100);
            this.renderZonesRating(data);
        } catch (e) {
            console.error('[App] Error loading zones rating:', e);
            main.innerHTML = `<div class="rating-page"><h2 data-i18n="zones_rating">Domain zones rating</h2><div class="alert alert-danger" data-i18n="error_loading_rating">Failed to load.</div></div>`;
            this.updateI18n();
        }
    };

    App.prototype.renderZonesRating = function(data) {
        const main = document.getElementById('main-content');
        if (!main) return;
        const { zones = [], total } = data;
        let rows = zones.map((z, i) => {
            const zoneName = this.escapeHtml(z.zone);
            const url = `/rating?zone=${encodeURIComponent(z.zone || '')}`;
            return `<tr class="rating-row-clickable" data-rating-url="${this.escapeHtml(url)}"><td class="text-center">${i + 1}</td><td><strong>${zoneName}</strong></td><td class="text-end">${this.formatNumber(z.total_earnings, 2)}</td><td class="text-center">${z.domains_count || 0}</td></tr>`;
        }).join('');
        if (!rows) rows = `<tr><td colspan="4" class="text-center text-muted py-4" data-i18n="no_domains_found">No data</td></tr>`;
        main.innerHTML = `
            <div class="rating-page">
                <div class="mb-3 ratings-nav-wrap">
                    <span class="text-muted me-2" data-i18n="ratings">Ratings:</span>
                    ${this.buildRatingsNav()}
                </div>
                <div class="d-flex justify-content-between align-items-center mb-4"><h2 class="mb-0" data-i18n="zones_rating">Domain zones rating</h2>${api.token ? '' : `<a href="/login" class="btn btn-primary btn-sm" onclick="event.preventDefault(); router.navigate('/login');" data-i18n="login">Login</a>`}</div>
                <div class="table-responsive">
                    <table class="table table-hover rating-table"><thead class="table-dark"><tr><th class="text-center" data-i18n="rank">#</th><th data-i18n="zone">Zone</th><th class="text-end" data-i18n="rating_col">Rating</th><th class="text-center" data-i18n="domains_count">Domains</th></tr></thead><tbody>${rows}</tbody></table>
                </div>
                <div class="text-center text-muted mt-3"><small><span data-i18n="total">Total</span>: ${total || 0}</small></div>
            </div>`;
        this.setupRatingRowClickListeners();
        this.updateI18n();
    };

    App.prototype.setupRatingRowClickListeners = function() {
        document.querySelectorAll('.rating-row-clickable[data-rating-url]').forEach(row => {
            row.addEventListener('click', (e) => {
                if (e.target.closest('a') || e.target.closest('button')) return;
                const url = row.getAttribute('data-rating-url');
                if (url) router.navigate(url);
            });
        });
    };

    // --- Promote / Subscribe / Cancel ---

    App.prototype.setupPromoteButtonListeners = function() {
        const tbody = document.querySelector('.rating-table tbody');
        if (!tbody) return;
        tbody.addEventListener('click', async (e) => {
            const promoteBtn = e.target.closest('.promote-btn');
            if (promoteBtn) {
                e.preventDefault(); e.stopPropagation();
                const domainId = promoteBtn.getAttribute('data-domain-id');
                const domainName = promoteBtn.getAttribute('data-domain-name');
                if (domainId) this.showPromoteConfirmModal(domainId, domainName);
                return;
            }
            const subscribeBtn = e.target.closest('.subscribe-btn');
            if (subscribeBtn) {
                e.preventDefault(); e.stopPropagation();
                const domainId = subscribeBtn.getAttribute('data-domain-id');
                const domainName = subscribeBtn.getAttribute('data-domain-name');
                if (domainId) this.showSubscribeConfirmModal(domainId, domainName);
                return;
            }
            const cancelBtn = e.target.closest('.cancel-subscription-btn');
            if (cancelBtn) {
                e.preventDefault(); e.stopPropagation();
                const subscriptionId = cancelBtn.getAttribute('data-subscription-id');
                const domainName = cancelBtn.getAttribute('data-domain-name');
                if (subscriptionId) this.showCancelSubscriptionModal(subscriptionId, domainName);
                return;
            }
        });
    };

    App.prototype.showPromoteConfirmModal = async function(domainId, domainName) {
        let currentBalance = 0;
        try { const balanceData = await api.getBalance(); currentBalance = balanceData.accumulated_balance || 0; } catch (error) { console.error('Failed to get user balance:', error); }
        const promotionCost = 1.0;
        const hasEnoughBalance = currentBalance >= promotionCost;
        const modalHtml = `
            <div class="modal fade" id="promoteModal" tabindex="-1" aria-labelledby="promoteModalLabel" aria-hidden="true">
                <div class="modal-dialog"><div class="modal-content">
                    <div class="modal-header"><h5 class="modal-title" id="promoteModalLabel" data-i18n="promote_domain">Promote Domain</h5><button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button></div>
                    <div class="modal-body">
                        <p data-i18n="promote_confirm_message">Are you sure you want to promote this domain to the top of the ratings?</p>
                        <div class="alert alert-info"><strong data-i18n="domain">Domain</strong>: ${this.escapeHtml(domainName)}<br><strong data-i18n="promotion_cost">Cost</strong>: ${promotionCost} ${this.config.token_name}<br><strong data-i18n="your_balance">Your balance</strong>: ${currentBalance.toFixed(2)} ${this.config.token_name}</div>
                        ${!hasEnoughBalance ? `<div class="alert alert-danger"><i class="bi bi-exclamation-triangle me-2"></i><span data-i18n="insufficient_balance_message">Insufficient balance. You need at least ${promotionCost} ${this.config.token_name} tokens.</span></div>` : ''}
                        <p class="text-muted small" data-i18n="promotion_info_detail">Promoted domains appear at the top of the ratings, ordered by promotion time. Your domain will stay at the top until another domain is promoted.</p>
                    </div>
                    <div class="modal-footer"><button type="button" class="btn btn-secondary" data-bs-dismiss="modal" data-i18n="cancel">Cancel</button><button type="button" class="btn btn-primary" id="confirmPromoteBtn" ${!hasEnoughBalance ? 'disabled' : ''}><span data-i18n="confirm_promote">Confirm Promotion</span></button></div>
                </div></div>
            </div>`;
        const existingModal = document.getElementById('promoteModal');
        if (existingModal) existingModal.remove();
        document.body.insertAdjacentHTML('beforeend', modalHtml);
        this.updateI18n();
        const modal = new bootstrap.Modal(document.getElementById('promoteModal'));
        modal.show();
        const confirmBtn = document.getElementById('confirmPromoteBtn');
        if (confirmBtn && hasEnoughBalance) {
            confirmBtn.addEventListener('click', async () => { await this.handlePromoteDomain(domainId, domainName, modal); });
        }
        document.getElementById('promoteModal').addEventListener('hidden.bs.modal', () => { document.getElementById('promoteModal').remove(); });
    };

    App.prototype.handlePromoteDomain = async function(domainId, domainName, modal) {
        const confirmBtn = document.getElementById('confirmPromoteBtn');
        if (!confirmBtn) return;
        confirmBtn.disabled = true;
        confirmBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span><span data-i18n="processing">Processing...</span>';
        try {
            const result = await api.promoteDomain(domainId);
            if (result.success) {
                modal.hide();
                this.showToast('success', result.message || 'Domain promoted successfully!');
                await this.loadDomains();
            } else throw new Error(result.message || 'Failed to promote domain');
        } catch (error) {
            console.error('Error promoting domain:', error);
            const errorMsg = error.message || error.error || 'Failed to promote domain. Please try again.';
            this.showToast('error', errorMsg);
            confirmBtn.disabled = false;
            confirmBtn.innerHTML = '<span data-i18n="confirm_promote">Confirm Promotion</span>';
            this.updateI18n();
        }
    };

    App.prototype.showSubscribeConfirmModal = async function(domainId, domainName) {
        let currentBalance = 0;
        try { const balanceData = await api.getBalance(); currentBalance = balanceData.accumulated_balance || 0; } catch (error) { console.error('Failed to get user balance:', error); }
        const subscriptionCost = 1.0;
        const hasEnoughBalance = currentBalance >= subscriptionCost;
        let frequencyOptions = '';
        if (this.frequencies && this.frequencies.length > 0) {
            for (const freq of this.frequencies) {
                const selected = freq.value === '1hour' ? 'selected' : '';
                const currentLang = i18n.currentLanguage || 'en';
                let label = freq.label_en;
                if (currentLang === 'ru') label = freq.label_ru;
                else if (currentLang === 'ar') label = freq.label_ar;
                frequencyOptions += `<option value="${freq.value}" ${selected}>${this.escapeHtml(label)} (${freq.price} ${this.config.token_name})</option>`;
            }
        } else {
            frequencyOptions = '<option value="1hour">Every hour (1 DOMAIN)</option>';
        }
        const modalHtml = `
            <div class="modal fade" id="subscribeModal" tabindex="-1" aria-labelledby="subscribeModalLabel" aria-hidden="true">
                <div class="modal-dialog"><div class="modal-content">
                    <div class="modal-header"><h5 class="modal-title" id="subscribeModalLabel" data-i18n="subscribe_domain">Subscribe Domain</h5><button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button></div>
                    <div class="modal-body">
                        <p data-i18n="subscribe_confirm_message">Enable auto-promotion for this domain?</p>
                        <div class="mb-3"><label for="subscriptionFrequency" class="form-label" data-i18n="promotion_frequency">Promotion Frequency</label><select class="form-select" id="subscriptionFrequency">${frequencyOptions}</select><div class="form-text" data-i18n="frequency_help">Choose how often your domain will be promoted</div></div>
                        <div class="alert alert-info"><strong data-i18n="domain">Domain</strong>: ${this.escapeHtml(domainName)}<br><strong data-i18n="subscription_cost">Cost per renewal</strong>: <span id="selectedFreqCost">${subscriptionCost}</span> ${this.config.token_name}<br><strong data-i18n="your_balance">Your balance</strong>: ${currentBalance.toFixed(2)} ${this.config.token_name}</div>
                        ${!hasEnoughBalance ? `<div class="alert alert-danger"><i class="bi bi-exclamation-triangle me-2"></i><span data-i18n="insufficient_balance_message">Insufficient balance. You need at least ${subscriptionCost} ${this.config.token_name} tokens.</span></div>` : ''}
                        <p class="text-muted small" data-i18n="subscription_info">Your domain will be automatically promoted at the selected frequency. You can cancel anytime. If your balance is insufficient, renewals will pause until you add funds.</p>
                    </div>
                    <div class="modal-footer"><button type="button" class="btn btn-secondary" data-bs-dismiss="modal" data-i18n="cancel">Cancel</button><button type="button" class="btn btn-success" id="confirmSubscribeBtn" ${!hasEnoughBalance ? 'disabled' : ''}><span data-i18n="confirm_subscribe">Enable Subscription</span></button></div>
                </div></div>
            </div>`;
        const existingModal = document.getElementById('subscribeModal');
        if (existingModal) existingModal.remove();
        document.body.insertAdjacentHTML('beforeend', modalHtml);
        this.updateI18n();
        const modal = new bootstrap.Modal(document.getElementById('subscribeModal'));
        modal.show();
        const freqSelect = document.getElementById('subscriptionFrequency');
        const costDisplay = document.getElementById('selectedFreqCost');
        if (freqSelect && costDisplay) {
            freqSelect.addEventListener('change', () => {
                const selectedValue = freqSelect.value;
                const selectedFreq = this.frequencies.find(f => f.value === selectedValue);
                if (selectedFreq) costDisplay.textContent = selectedFreq.price.toFixed(2);
            });
        }
        const confirmBtn = document.getElementById('confirmSubscribeBtn');
        if (confirmBtn && hasEnoughBalance) {
            confirmBtn.addEventListener('click', async () => {
                const selectedFrequency = freqSelect ? freqSelect.value : '1hour';
                await this.handleCreateSubscription(domainId, domainName, selectedFrequency, modal);
            });
        }
        document.getElementById('subscribeModal').addEventListener('hidden.bs.modal', () => { document.getElementById('subscribeModal').remove(); });
    };

    App.prototype.handleCreateSubscription = async function(domainId, domainName, frequency, modal) {
        const confirmBtn = document.getElementById('confirmSubscribeBtn');
        if (!confirmBtn) return;
        confirmBtn.disabled = true;
        confirmBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span><span data-i18n="processing">Processing...</span>';
        try {
            const result = await api.createSubscription(domainId, frequency);
            if (result.success) {
                modal.hide();
                this.showToast('success', result.message || 'Subscription created successfully!');
                await this.loadDomains();
            } else throw new Error(result.message || 'Failed to create subscription');
        } catch (error) {
            console.error('Error creating subscription:', error);
            const errorMsg = error.message || error.error || 'Failed to create subscription. Please try again.';
            this.showToast('error', errorMsg);
            confirmBtn.disabled = false;
            confirmBtn.innerHTML = '<span data-i18n="confirm_subscribe">Enable Subscription</span>';
            this.updateI18n();
        }
    };

    App.prototype.showCancelSubscriptionModal = async function(subscriptionId, domainName) {
        const modalHtml = `
            <div class="modal fade" id="cancelSubscriptionModal" tabindex="-1" aria-labelledby="cancelSubscriptionModalLabel" aria-hidden="true">
                <div class="modal-dialog"><div class="modal-content">
                    <div class="modal-header"><h5 class="modal-title" id="cancelSubscriptionModalLabel" data-i18n="cancel_subscription">Cancel Subscription</h5><button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button></div>
                    <div class="modal-body">
                        <p data-i18n="cancel_subscription_confirm">Are you sure you want to cancel the subscription for this domain?</p>
                        <div class="alert alert-warning"><strong data-i18n="domain">Domain</strong>: ${this.escapeHtml(domainName)}<br><span data-i18n="cancel_subscription_warning">Auto-promotion will stop. The domain will gradually fall in rankings as others promote.</span></div>
                    </div>
                    <div class="modal-footer"><button type="button" class="btn btn-secondary" data-bs-dismiss="modal" data-i18n="keep_subscription">Keep Subscription</button><button type="button" class="btn btn-danger" id="confirmCancelBtn"><span data-i18n="confirm_cancel">Cancel Subscription</span></button></div>
                </div></div>
            </div>`;
        const existingModal = document.getElementById('cancelSubscriptionModal');
        if (existingModal) existingModal.remove();
        document.body.insertAdjacentHTML('beforeend', modalHtml);
        this.updateI18n();
        const modal = new bootstrap.Modal(document.getElementById('cancelSubscriptionModal'));
        modal.show();
        const confirmBtn = document.getElementById('confirmCancelBtn');
        if (confirmBtn) {
            confirmBtn.addEventListener('click', async () => { await this.handleCancelSubscription(subscriptionId, domainName, modal); });
        }
        document.getElementById('cancelSubscriptionModal').addEventListener('hidden.bs.modal', () => { document.getElementById('cancelSubscriptionModal').remove(); });
    };

    App.prototype.handleCancelSubscription = async function(subscriptionId, domainName, modal) {
        const confirmBtn = document.getElementById('confirmCancelBtn');
        if (!confirmBtn) return;
        if (!subscriptionId || isNaN(subscriptionId)) { this.showToast('error', 'Invalid subscription ID'); return; }
        confirmBtn.disabled = true;
        confirmBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span><span data-i18n="processing">Processing...</span>';
        try {
            const result = await api.cancelSubscription(subscriptionId);
            if (result.success) {
                modal.hide();
                this.showToast('success', result.message || 'Subscription cancelled successfully!');
                await this.loadDomains();
            } else throw new Error(result.message || 'Failed to cancel subscription');
        } catch (error) {
            console.error('Error cancelling subscription:', error);
            const errorMsg = error.message || error.error || 'Failed to cancel subscription. Please try again.';
            this.showToast('error', errorMsg);
            confirmBtn.disabled = false;
            confirmBtn.innerHTML = '<span data-i18n="confirm_cancel">Cancel Subscription</span>';
            this.updateI18n();
        }
    };

})();
