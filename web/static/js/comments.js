/**
 * Comments and votes UI (social layer).
 * Renders comment list, reply form, vote buttons, karma.
 */
(function() {
    'use strict';

    App.prototype.renderCommentsBlock = function(containerId, entityType, entityId, entityKey) {
        const container = document.getElementById(containerId);
        if (!container) return;
        const auth = !!api.token;
        container.innerHTML = `
            <div class="card">
                <div class="card-header d-flex justify-content-between align-items-center">
                    <h5 class="mb-0" data-i18n="comments">Comments</h5>
                    ${auth ? `<span class="badge bg-secondary" id="comments-karma-badge"></span>` : ''}
                </div>
                <div class="card-body">
                    ${auth ? `
                        <div class="mb-3">
                            <textarea class="form-control" id="comment-body-input" rows="2" placeholder="${(typeof i18n !== 'undefined' && i18n.t('write_comment')) ? i18n.t('write_comment') : 'Write a comment...'}" maxlength="10000"></textarea>
                            <button type="button" class="btn btn-primary btn-sm mt-2" id="comment-submit-btn" data-i18n="send">Send</button>
                        </div>
                    ` : '<p class="text-muted small" data-i18n="login_to_comment">Log in to comment.</p>'}
                    <div id="comments-list"></div>
                </div>
            </div>
        `;
        if (typeof app !== 'undefined' && app.updateI18n) app.updateI18n();
        this.loadCommentsInto(containerId, entityType, entityId, entityKey);
        if (auth) {
            const self = this;
            const submitBtn = document.getElementById('comment-submit-btn');
            const bodyInput = document.getElementById('comment-body-input');
            if (submitBtn && bodyInput) {
                submitBtn.addEventListener('click', function() {
                    const body = bodyInput.value.trim();
                    if (!body) return;
                    submitBtn.disabled = true;
                    api.createComment(entityType, entityId, entityKey, body, null).then(function() {
                        bodyInput.value = '';
                        self.loadCommentsInto(containerId, entityType, entityId, entityKey);
                    }).catch(function(err) {
                        if (typeof app !== 'undefined' && app.showToast) app.showToast((err && err.message) || 'Failed to post', 'danger');
                    }).finally(function() { submitBtn.disabled = false; });
                });
            }
        }
    };

    App.prototype.loadCommentsInto = function(containerId, entityType, entityId, entityKey, page) {
        page = page || 1;
        const listEl = document.getElementById('comments-list');
        if (!listEl) return;
        listEl.innerHTML = '<div class="text-muted small">Loading...</div>';
        const self = this;
        api.getComments(entityType, entityId, entityKey, page, 50).then(function(data) {
            const comments = data.comments || [];
            if (comments.length === 0) {
                listEl.innerHTML = '<p class="text-muted small mb-0" data-i18n="no_comments">No comments yet.</p>';
                if (typeof app !== 'undefined' && app.updateI18n) app.updateI18n();
                return;
            }
            listEl.innerHTML = comments.map(function(c) {
                return self.renderOneComment(c, entityType, entityId, entityKey);
            }).join('');
            if (typeof app !== 'undefined' && app.updateI18n) app.updateI18n();
            self.attachCommentVoteHandlers(containerId, entityType, entityId, entityKey);
        }).catch(function() {
            listEl.innerHTML = '<p class="text-muted small mb-0">Failed to load comments.</p>';
        });
    };

    App.prototype.renderOneComment = function(c, entityType, entityId, entityKey) {
        const wallet = (c.author_wallet || '').substring(0, 8) + '…';
        const body = (typeof this !== 'undefined' && this.escapeHtml) ? this.escapeHtml(c.body) : c.body.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
        const karma = c.karma_score != null ? c.karma_score : 0;
        const uv = c.user_vote != null ? c.user_vote : null;
        const upActive = uv === 1 ? ' active' : '';
        const downActive = uv === -1 ? ' active' : '';
        const isOwnComment = (typeof app !== 'undefined' && app.user && c.author_id === app.user.id);
        return `
            <div class="comment-item border-bottom pb-2 mb-2" data-comment-id="${c.id}">
                <div class="d-flex">
                    <div class="vote-buttons me-2">
                        <button type="button" class="btn btn-sm btn-outline-secondary vote-up${upActive}" data-value="1" title="Like"><i class="bi bi-arrow-up"></i></button>
                        <span class="d-block text-center small karma-val">${karma}</span>
                        ${isOwnComment ? '' : `<button type="button" class="btn btn-sm btn-outline-secondary vote-down${downActive}" data-value="-1" title="Dislike"><i class="bi bi-arrow-down"></i></button>`}
                    </div>
                    <div class="flex-grow-1">
                        <small class="text-muted">${wallet}</small>
                        <p class="mb-1 mt-0 small" style="white-space: pre-wrap;">${body}</p>
                        <small class="text-muted">${c.created_at ? new Date(c.created_at).toLocaleString() : ''}</small>
                    </div>
                </div>
            </div>
        `;
    };

    App.prototype.attachCommentVoteHandlers = function(containerId, entityType, entityId, entityKey) {
        const listEl = document.getElementById('comments-list');
        if (!listEl) return;
        listEl.querySelectorAll('.vote-up, .vote-down').forEach(function(btn) {
            btn.addEventListener('click', function() {
                if (!api.token) return;
                const commentId = parseInt(btn.closest('.comment-item').getAttribute('data-comment-id'), 10);
                const value = parseInt(btn.getAttribute('data-value'), 10);
                const row = btn.closest('.comment-item');
                const karmaEl = row.querySelector('.karma-val');
                const currentKarma = parseInt(karmaEl ? karmaEl.textContent : '0', 10) || 0;
                const currentUserVote = row.querySelector('.vote-up.active') ? 1 : (row.querySelector('.vote-down.active') ? -1 : 0);
                api.setVote('comment', commentId, null, value).then(function() {
                    const newKarma = currentKarma + value - currentUserVote;
                    if (karmaEl) karmaEl.textContent = newKarma;
                    row.querySelectorAll('.vote-up, .vote-down').forEach(function(b) {
                        const v = parseInt(b.getAttribute('data-value'), 10);
                        b.classList.toggle('active', v === value);
                    });
                }).catch(function() {
                    if (typeof app !== 'undefined' && app.showToast) app.showToast('Vote failed', 'danger');
                });
            });
        });
    };
})();
