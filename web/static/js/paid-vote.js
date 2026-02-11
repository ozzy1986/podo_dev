/**
 * Paid vote form: shown when user clicks like/dislike again (free vote already used).
 * Renders small form near anchor; amount input, "Use max", confirm, submit.
 */
(function() {
    'use strict';

    function t(key, fallback) {
        if (typeof i18n !== 'undefined' && i18n.t) return i18n.t(key) || fallback;
        return fallback;
    }

    function showPaidVoteForm(options) {
        var anchorEl = options.anchorEl;
        var targetLabel = options.targetLabel || '';
        var targetType = options.targetType;
        var targetId = options.targetId;
        var targetKey = options.targetKey || null;
        var value = options.value;
        var onSuccess = options.onSuccess || function() {};

        if (!anchorEl || !targetType || value === undefined) return;

        var isLike = value === 1;
        var titleKey = isLike ? 'paid_like' : 'paid_dislike';
        var title = t(titleKey, isLike ? 'Paid like' : 'Paid dislike');

        var wrap = document.createElement('div');
        wrap.className = 'paid-vote-form-wrap border rounded p-2 mt-2';
        wrap.setAttribute('data-paid-vote', '1');

        var balance = 0;
        var tokenName = (typeof app !== 'undefined' && app.config && app.config.token_name) ? app.config.token_name : 'DOMAIN';
        var maxAmount = 0;

        function renderForm() {
            var useMaxLabel = t('use_max_balance', 'Use max');
            var deductLabel = t('paid_vote_deduct', 'This will deduct {amount} tokens from your balance.');
            var confirmLabel = t('paid_vote_confirm', 'Confirm');
            var amountPlaceholder = t('paid_vote_amount_placeholder', 'Amount (votes)');
            var insufficientLabel = t('insufficient_balance_for_votes', 'Insufficient balance for this amount.');
            var votesLabel = t('votes', 'votes');

            maxAmount = Math.floor(balance);
            var canUseMax = maxAmount >= 1;

            wrap.innerHTML =
                '<div class="small">' +
                '<strong>' + (title + ': ' + targetLabel) + '</strong>' +
                '</div>' +
                '<div class="mt-2 d-flex flex-wrap align-items-center gap-2">' +
                '<input type="number" min="1" step="1" max="' + Math.max(1, maxAmount) + '" class="form-control form-control-sm paid-vote-amount" style="width:6rem" placeholder="' + amountPlaceholder + '" value="">' +
                '<span class="small text-muted">' + votesLabel + '</span>' +
                (canUseMax ? '<button type="button" class="btn btn-sm btn-outline-secondary paid-vote-use-max">' + useMaxLabel + ' (' + maxAmount + ')</button>' : '') +
                '</div>' +
                '<p class="small text-muted mt-1 mb-1 paid-vote-deduct-msg"></p>' +
                '<div class="small text-danger paid-vote-error mb-1" style="display:none"></div>' +
                '<div class="d-flex gap-2 mt-1">' +
                '<button type="button" class="btn btn-sm btn-primary paid-vote-submit">' + confirmLabel + '</button>' +
                '<button type="button" class="btn btn-sm btn-outline-secondary paid-vote-cancel">' + (t('cancel', 'Cancel')) + '</button>' +
                '</div>';

            var amountInput = wrap.querySelector('.paid-vote-amount');
            var deductMsg = wrap.querySelector('.paid-vote-deduct-msg');
            var errEl = wrap.querySelector('.paid-vote-error');
            var useMaxBtn = wrap.querySelector('.paid-vote-use-max');
            var submitBtn = wrap.querySelector('.paid-vote-submit');
            var cancelBtn = wrap.querySelector('.paid-vote-cancel');

            function updateDeductMsg(amt) {
                var n = parseInt(amt, 10);
                if (isNaN(n) || n < 1) {
                    deductMsg.textContent = '';
                    return;
                }
                deductMsg.textContent = deductLabel.replace('{amount}', n);
            }

            function showError(msg) {
                errEl.textContent = msg || '';
                errEl.style.display = msg ? 'block' : 'none';
            }

            amountInput.addEventListener('input', function() {
                updateDeductMsg(amountInput.value);
                showError('');
            });

            if (useMaxBtn) {
                useMaxBtn.addEventListener('click', function() {
                    amountInput.value = maxAmount;
                    updateDeductMsg(maxAmount);
                    showError('');
                });
            }

            function removeFormAndRow() {
                var tr = wrap.closest ? wrap.closest('tr[data-paid-vote-row]') : null;
                var parent = wrap.parentNode;
                if (parent) parent.removeChild(wrap);
                if (tr && tr.parentNode) tr.parentNode.removeChild(tr);
            }
            cancelBtn.addEventListener('click', removeFormAndRow);

            submitBtn.addEventListener('click', function() {
                var amt = parseInt(amountInput.value, 10);
                if (isNaN(amt) || amt < 1 || amt !== Number(amountInput.value)) {
                    showError(t('paid_vote_amount_placeholder', 'Enter a positive whole number (at least 1)'));
                    return;
                }
                if (amt > balance) {
                    showError(insufficientLabel);
                    return;
                }
                showError('');
                submitBtn.disabled = true;
                api.setVote(targetType, targetId, targetKey, value, amt).then(function(res) {
                    removeFormAndRow();
                    onSuccess(res);
                    if (typeof app !== 'undefined' && app.showToast) {
                        app.showToast(isLike ? (t('paid_like_done', 'Paid like applied')) : (t('paid_dislike_done', 'Paid dislike applied')), 'success');
                    }
                }).catch(function(err) {
                    submitBtn.disabled = false;
                    showError(err && err.message ? err.message : t('error', 'Request failed'));
                });
            });
        }

        // Insert after anchor. If anchor is inside a table row, insert a full-width row
        // so the form is not rendered out of bounds (invalid div-in-tr breaks layout).
        var row = anchorEl.closest ? anchorEl.closest('tr') : null;
        if (row) {
            var cells = row.querySelectorAll('td, th');
            var colspan = cells.length || 10;
            var newRow = document.createElement('tr');
            newRow.setAttribute('data-paid-vote-row', '1');
            var cell = document.createElement('td');
            cell.setAttribute('colspan', String(colspan));
            cell.className = 'paid-vote-form-cell align-top';
            cell.appendChild(wrap);
            newRow.appendChild(cell);
            if (row.nextSibling) {
                row.parentNode.insertBefore(newRow, row.nextSibling);
            } else {
                row.parentNode.appendChild(newRow);
            }
        } else {
            if (anchorEl.nextSibling) {
                anchorEl.parentNode.insertBefore(wrap, anchorEl.nextSibling);
            } else {
                anchorEl.parentNode.appendChild(wrap);
            }
        }

        wrap.innerHTML = '<span class="text-muted small">' + (t('loading', 'Loading...')) + '</span>';
        api.getBalance().then(function(data) {
            balance = parseFloat(data.accumulated_balance || 0) || 0;
            renderForm();
        }).catch(function() {
            balance = 0;
            renderForm();
        });
    }

    window.showPaidVoteForm = showPaidVoteForm;
})();
