/**
 * Wallet/Domain wall module.
 * Handles listing wall posts, creating new posts with HTML, voting, and comments.
 */
(function() {
    'use strict';

    var WALL_POSTS_PER_PAGE = 10;

    function shortenWallet(wallet) {
        if (!wallet) return '';
        if (wallet.length <= 12) return wallet;
        return wallet.substring(0, 6) + '...' + wallet.substring(wallet.length - 6);
    }

    function formatWallDate(isoString) {
        if (!isoString) return '';
        var d = new Date(isoString);
        if (isNaN(d.getTime())) return '';
        var pad = function(n) { return (n < 10 ? '0' : '') + n; };
        return pad(d.getDate()) + '.' + pad(d.getMonth() + 1) + '.' + d.getFullYear() + ' ' +
            pad(d.getHours()) + ':' + pad(d.getMinutes());
    }

    App.prototype.renderWallSection = function(containerId, entityType, entityId, entityKey, options) {
        options = options || {};
        var container = typeof containerId === 'string' ? document.getElementById(containerId) : containerId;
        if (!container) return;

        var auth = !!api.token;
        var title = options.title || ((typeof i18n !== 'undefined' && i18n.t) ? i18n.t('wall_title') : 'Wall');
        var placeholder = (typeof i18n !== 'undefined' && i18n.t) ? (i18n.t('wall_placeholder') || 'Share HTML (images allowed)...') : 'Share HTML (images allowed)...';
        var themeLightLabel = (typeof i18n !== 'undefined' && i18n.t) ? (i18n.t('wall_theme_light') || 'Light') : 'Light';
        var themeDarkLabel = (typeof i18n !== 'undefined' && i18n.t) ? (i18n.t('wall_theme_dark') || 'Dark') : 'Dark';

        container.dataset.entityType = entityType;
        container.dataset.entityId = (entityId != null) ? String(entityId) : '';
        container.dataset.entityKey = entityKey ? String(entityKey) : '';
        container.dataset.page = '1';

        container.innerHTML = `
            <div class="card wall-card">
                <div class="card-header d-flex justify-content-between align-items-center">
                    <h5 class="mb-0">${title}</h5>
                    <div class="d-flex align-items-center gap-2">
                        <span class="badge bg-secondary wall-posts-count" style="display:none"></span>
                    </div>
                </div>
                <div class="card-body">
                    ${auth ? `
                        <div class="wall-post-form mb-4">
                            <label class="form-label fw-semibold" data-i18n="wall_new_post_label">New post</label>
                            <textarea class="form-control wall-post-body-input" rows="4" maxlength="20000" placeholder="${placeholder}"></textarea>
                            <div class="d-flex flex-wrap align-items-center gap-3 mt-2">
                                <div class="btn-group btn-group-sm wall-theme-toggle" role="group" aria-label="Wall theme">
                                    <input type="radio" class="btn-check" name="wall-theme-${containerId}" id="wall-theme-light-${containerId}" value="light" autocomplete="off" checked>
                                    <label class="btn btn-outline-secondary" for="wall-theme-light-${containerId}">${themeLightLabel}</label>
                                    <input type="radio" class="btn-check" name="wall-theme-${containerId}" id="wall-theme-dark-${containerId}" value="dark" autocomplete="off">
                                    <label class="btn btn-outline-secondary" for="wall-theme-dark-${containerId}">${themeDarkLabel}</label>
                                </div>
                                <button type="button" class="btn btn-primary btn-sm wall-submit-btn" data-i18n="wall_submit">Post</button>
                                <div class="text-muted small flex-grow-1" data-i18n="wall_html_hint">HTML is sanitized. IMG tags are allowed.</div>
                            </div>
                        </div>
                    ` : '<p class="text-muted small" data-i18n="wall_login_hint">Log in to share posts on the wall.</p>'}
                    <div class="wall-posts-list"></div>
                    <div class="wall-pagination text-center mt-3"></div>
                </div>
            </div>
        `;

        if (typeof app !== 'undefined' && app.updateI18n) app.updateI18n();

        var self = this;
        if (auth) {
            var submitBtn = container.querySelector('.wall-submit-btn');
            var bodyInput = container.querySelector('.wall-post-body-input');
            if (submitBtn && bodyInput) {
                submitBtn.addEventListener('click', function() {
                    var body = bodyInput.value.trim();
                    if (!body) {
                        if (typeof app !== 'undefined' && app.showToast) app.showToast('warning', (typeof i18n !== 'undefined' && i18n.t) ? i18n.t('wall_empty_body') : 'Post cannot be empty');
                        return;
                    }
                    submitBtn.disabled = true;
                    var selectedTheme = container.querySelector('input[name="wall-theme-' + containerId + '"]:checked');
                    var theme = selectedTheme ? selectedTheme.value : 'light';
                    api.createWallPost(entityType, entityId, entityKey, body, theme).then(function() {
                        bodyInput.value = '';
                        container.dataset.page = '1';
                        self.loadWallPosts(container, entityType, entityId, entityKey, 1);
                        if (typeof app !== 'undefined' && app.showToast) app.showToast('success', (typeof i18n !== 'undefined' && i18n.t) ? i18n.t('wall_post_created') : 'Post published');
                    }).catch(function(err) {
                        if (typeof app !== 'undefined' && app.showToast) app.showToast('danger', (err && err.message) || 'Failed to publish post');
                    }).finally(function() {
                        submitBtn.disabled = false;
                    });
                });
            }
        }

        this.loadWallPosts(container, entityType, entityId, entityKey, 1);
    };

    App.prototype.loadWallPosts = function(container, entityType, entityId, entityKey, page) {
        container = typeof container === 'string' ? document.getElementById(container) : container;
        if (!container) return;

        var listEl = container.querySelector('.wall-posts-list');
        if (!listEl) return;

        page = page || parseInt(container.dataset.page || '1', 10) || 1;
        container.dataset.page = String(page);

        listEl.innerHTML = '<div class="text-muted small" data-i18n="loading">Loading...</div>';
        var self = this;
        api.getWallPosts(entityType, entityId, entityKey, page, WALL_POSTS_PER_PAGE).then(function(data) {
            var posts = data.posts || [];
            var total = data.total || posts.length;
            var totalPages = data.total_pages || 1;
            var countBadge = container.querySelector('.wall-posts-count');
            if (countBadge) {
                countBadge.textContent = total;
                countBadge.style.display = 'inline-block';
            }

            if (posts.length === 0) {
                listEl.innerHTML = '<p class="text-muted mb-0" data-i18n="wall_empty_state">No posts yet.</p>';
                if (typeof app !== 'undefined' && app.updateI18n) app.updateI18n();
                self.renderWallPagination(container, entityType, entityId, entityKey, page, totalPages);
                return;
            }

            listEl.innerHTML = posts.map(function(post) {
                return self.renderWallPost(post);
            }).join('');
            if (typeof app !== 'undefined' && app.updateI18n) app.updateI18n();

            self.attachWallVoteHandlers(container, entityType, entityId, entityKey);
            self.attachWallCommentHandlers(container, entityType, entityId, entityKey);
            self.attachWallDeleteHandlers(container, entityType, entityId, entityKey);

            self.renderWallPagination(container, entityType, entityId, entityKey, page, totalPages);
        }).catch(function(err) {
            console.error('[Wall] Failed to load posts:', err);
            listEl.innerHTML = '<p class="text-danger mb-0" data-i18n="wall_load_failed">Failed to load wall posts.</p>';
        });
    };

    App.prototype.renderWallPost = function(post) {
        var walletDisplay = shortenWallet(post.author_wallet || '');
        var createdAt = formatWallDate(post.created_at);
        var themeClass = (post.content_theme === 'dark') ? 'user-content-isolate user-content-isolate--dark' : 'user-content-isolate user-content-isolate--light';
        var karma = typeof post.karma_score === 'number' ? post.karma_score : 0;
        var upActive = post.user_vote === 1 ? ' active' : '';
        var downActive = post.user_vote === -1 ? ' active' : '';
        var isOwn = (typeof app !== 'undefined' && app.user && post.author_id === app.user.id);
        var commentsLabel = (typeof i18n !== 'undefined' && i18n.t) ? (i18n.t('wall_view_comments') || 'Comments') : 'Comments';
        var hiddenMessage = (typeof i18n !== 'undefined' && i18n.t) ? (i18n.t('wall_post_hidden_message') || 'Post hidden due to negative karma') : 'Post hidden due to negative karma';

        var bodyHtml = '';
        if (post.is_hidden) {
            bodyHtml = `<div class="alert alert-warning wall-post-hidden mb-0" role="alert">${hiddenMessage}</div>`;
        } else {
            bodyHtml = `<div class="${themeClass} wall-post-body">${post.body_html || ''}</div>`;
        }

        return `
            <div class="wall-post-item card mb-3" data-post-id="${post.id}" data-hidden="${post.is_hidden ? '1' : '0'}">
                <div class="card-body">
                    <div class="d-flex">
                        <div class="wall-vote-buttons me-3 text-center">
                            <button type="button" class="btn btn-sm btn-outline-secondary wall-vote-up${upActive}" data-value="1" title="Like"><i class="bi bi-arrow-up"></i></button>
                            <span class="d-block small fw-semibold wall-karma">${karma}</span>
                            ${isOwn ? '' : `<button type="button" class="btn btn-sm btn-outline-secondary wall-vote-down${downActive}" data-value="-1" title="Dislike"><i class="bi bi-arrow-down"></i></button>`}
                        </div>
                        <div class="flex-grow-1">
                            <div class="d-flex justify-content-between align-items-start flex-wrap gap-2 mb-2">
                                <small class="text-muted wall-post-author" ${post.author_wallet ? 'data-wallet="' + post.author_wallet.replace(/"/g, '&quot;') + '"' : ''}>${walletDisplay}</small>
                                <small class="text-muted">${createdAt}</small>
                            </div>
                            ${bodyHtml}
                            <div class="d-flex flex-wrap align-items-center gap-3 mt-3">
                                <button type="button" class="btn btn-link p-0 wall-comments-toggle" data-post-id="${post.id}">
                                    <i class="bi bi-chat-left-text"></i>
                                    <span class="ms-1">${commentsLabel} (${post.comments_count || 0})</span>
                                </button>
                                ${isOwn ? `<button type="button" class="btn btn-outline-danger btn-sm wall-delete-btn" data-post-id="${post.id}" data-i18n="wall_delete">Delete</button>` : ''}
                            </div>
                            <div class="wall-comments-container d-none mt-3"></div>
                        </div>
                    </div>
                </div>
            </div>
        `;
    };

    App.prototype.renderWallPagination = function(container, entityType, entityId, entityKey, page, totalPages) {
        var paginationEl = container.querySelector('.wall-pagination');
        if (!paginationEl) return;
        if (totalPages <= 1) {
            paginationEl.innerHTML = '';
            return;
        }

        var self = this;
        var prevDisabled = page <= 1 ? ' disabled' : '';
        var nextDisabled = page >= totalPages ? ' disabled' : '';

        paginationEl.innerHTML = `
            <div class="btn-group" role="group">
                <button type="button" class="btn btn-outline-secondary btn-sm wall-page-prev${prevDisabled}" ${prevDisabled ? 'disabled' : ''} data-i18n="previous">Previous</button>
                <button type="button" class="btn btn-light btn-sm wall-page-indicator" disabled>${page} / ${totalPages}</button>
                <button type="button" class="btn btn-outline-secondary btn-sm wall-page-next${nextDisabled}" ${nextDisabled ? 'disabled' : ''} data-i18n="next">Next</button>
            </div>
        `;
        if (typeof app !== 'undefined' && app.updateI18n) app.updateI18n();

        var prevBtn = paginationEl.querySelector('.wall-page-prev');
        var nextBtn = paginationEl.querySelector('.wall-page-next');
        if (prevBtn && !prevBtn.disabled) {
            prevBtn.addEventListener('click', function() {
                self.loadWallPosts(container, entityType, entityId, entityKey, page - 1);
            });
        }
        if (nextBtn && !nextBtn.disabled) {
            nextBtn.addEventListener('click', function() {
                self.loadWallPosts(container, entityType, entityId, entityKey, page + 1);
            });
        }
    };

    App.prototype.attachWallVoteHandlers = function(container, entityType, entityId, entityKey) {
        container = typeof container === 'string' ? document.getElementById(container) : container;
        if (!container) return;
        container.querySelectorAll('.wall-vote-up, .wall-vote-down').forEach(function(btn) {
            btn.addEventListener('click', function() {
                if (!api.token) return;
                var postEl = btn.closest('.wall-post-item');
                if (!postEl) return;
                var postId = parseInt(postEl.getAttribute('data-post-id'), 10);
                if (!postId) return;
                var value = parseInt(btn.getAttribute('data-value'), 10);
                var karmaEl = postEl.querySelector('.wall-karma');
                var currentKarma = parseInt(karmaEl ? karmaEl.textContent : '0', 10) || 0;
                var currentVote = postEl.querySelector('.wall-vote-up.active') ? 1 : (postEl.querySelector('.wall-vote-down.active') ? -1 : 0);

                api.setVote('wall_post', postId, null, value).then(function(res) {
                    var newKarma = (res && typeof res.karma === 'number') ? res.karma : (currentKarma + value - currentVote);
                    if (karmaEl) karmaEl.textContent = newKarma;
                    postEl.querySelectorAll('.wall-vote-up, .wall-vote-down').forEach(function(b) {
                        var v = parseInt(b.getAttribute('data-value'), 10);
                        b.classList.toggle('active', v === value);
                    });
                }).catch(function(err) {
                    var isPaidVoteRequired = err && err.status === 409 && (
                        (err.responseData && err.responseData.details && err.responseData.details.code === 'PAID_VOTE_REQUIRED') ||
                        (err.responseData && err.responseData.detail && err.responseData.detail.code === 'PAID_VOTE_REQUIRED') ||
                        (err.responseData && err.responseData.error && String(err.responseData.error).indexOf('Paid vote') !== -1)
                    );
                    if (isPaidVoteRequired && typeof showPaidVoteForm === 'function') {
                        showPaidVoteForm({
                            anchorEl: postEl.querySelector('.wall-vote-buttons') || postEl,
                            targetLabel: (typeof i18n !== 'undefined' && i18n.t ? i18n.t('wall_post') : 'Wall post') + ' #' + postId,
                            targetType: 'wall_post',
                            targetId: postId,
                            targetKey: null,
                            value: value,
                            onSuccess: function(res) {
                                if (karmaEl && res && typeof res.karma === 'number') {
                                    karmaEl.textContent = res.karma;
                                }
                                postEl.querySelectorAll('.wall-vote-up, .wall-vote-down').forEach(function(b) {
                                    var v = parseInt(b.getAttribute('data-value'), 10);
                                    b.classList.toggle('active', v === value);
                                });
                            }
                        });
                    } else if (typeof app !== 'undefined' && app.showToast) {
                        app.showToast('danger', (err && err.message) || 'Vote failed');
                    }
                });
            });
        });
    };

    App.prototype.attachWallCommentHandlers = function(container, entityType, entityId, entityKey) {
        container = typeof container === 'string' ? document.getElementById(container) : container;
        if (!container) return;
        var self = this;
        container.querySelectorAll('.wall-comments-toggle').forEach(function(btn) {
            btn.addEventListener('click', function() {
                var postEl = btn.closest('.wall-post-item');
                if (!postEl) return;
                var postId = parseInt(postEl.getAttribute('data-post-id'), 10);
                if (!postId) return;
                var commentsContainer = postEl.querySelector('.wall-comments-container');
                if (!commentsContainer) return;

                var isHidden = commentsContainer.classList.contains('d-none');
                container.querySelectorAll('.wall-comments-container').forEach(function(el) {
                    if (el !== commentsContainer) el.classList.add('d-none');
                });

                if (isHidden) {
                    commentsContainer.classList.remove('d-none');
                    commentsContainer.innerHTML = '<div class="mb-2 fw-semibold" data-i18n="comments">Comments</div>';
                    var commentsBlockId = 'wall-comments-' + postId;
                    var inner = document.createElement('div');
                    inner.id = commentsBlockId;
                    commentsContainer.appendChild(inner);
                    self.renderCommentsBlock(inner, 'wall_post', postId, null, {});
                } else {
                    commentsContainer.classList.add('d-none');
                    commentsContainer.innerHTML = '';
                }
            });
        });
    };

    App.prototype.attachWallDeleteHandlers = function(container, entityType, entityId, entityKey) {
        container = typeof container === 'string' ? document.getElementById(container) : container;
        if (!container) return;
        container.querySelectorAll('.wall-delete-btn').forEach(function(btn) {
            btn.addEventListener('click', function() {
                var postEl = btn.closest('.wall-post-item');
                if (!postEl) return;
                var postId = parseInt(postEl.getAttribute('data-post-id'), 10);
                if (!postId) return;
                var confirmText = (typeof i18n !== 'undefined' && i18n.t) ? (i18n.t('wall_delete_confirm') || 'Delete this post?') : 'Delete this post?';
                if (!window.confirm(confirmText)) return;
                api.deleteWallPost(postId).then(function() {
                    if (typeof app !== 'undefined' && app.showToast) app.showToast('success', (typeof i18n !== 'undefined' && i18n.t) ? i18n.t('wall_post_deleted') : 'Post deleted');
                    postEl.remove();
                }).catch(function(err) {
                    if (typeof app !== 'undefined' && app.showToast) app.showToast('danger', (err && err.message) || 'Failed to delete post');
                });
            });
        });
    };
})();
