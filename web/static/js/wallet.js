/**
 * Wallet Module
 * Wallet and withdrawal pages
 */
(function() {
    'use strict';

    App.prototype.showWallet = async function() {
        const main = document.getElementById('main-content');
        
        // Get current user data
        let wallet = null;
        try {
            if (this.user && this.user.wallet) {
                wallet = this.user.wallet;
            } else {
                // Try to get fresh user data
                const user = await api.getCurrentUser();
                if (user && user.wallet) {
                    wallet = user.wallet;
                    this.user = user; // Update cached user data
                }
            }
        } catch (error) {
            console.error('Failed to load wallet:', error);
        }
        
        main.innerHTML = `
            <div class="row justify-content-center">
                <div class="col-md-8">
                    <div class="card">
                        <div class="card-header">
                            <h3 data-i18n="wallet_address">Wallet Address</h3>
                        </div>
                        <div class="card-body">
                            ${wallet ? `
                                <div class="alert alert-info">
                                    <i class="bi bi-info-circle me-2"></i>
                                    <span data-i18n="wallet_readonly_info">Your wallet address is automatically set from your wx.network account and cannot be changed.</span>
                                </div>
                                <div class="mb-3">
                                    <label class="form-label" data-i18n="wallet_address">Wallet Address</label>
                                    <div class="input-group">
                                        <input type="text" class="form-control" id="wallet-display" 
                                               value="${wallet}" readonly>
                                        <button class="btn btn-outline-secondary" type="button" id="copy-wallet-btn" 
                                                onclick="navigator.clipboard.writeText('${wallet}'); app.showToast('success', i18n.t('copied', 'Copied!'));">
                                            <i class="bi bi-clipboard"></i>
                                        </button>
                                    </div>
                                    <small class="form-text text-muted" data-i18n="wallet_from_wx_network">This wallet is linked to your wx.network account</small>
                                </div>
                            ` : `
                                <div class="alert alert-warning">
                                    <i class="bi bi-exclamation-triangle me-2"></i>
                                    <span data-i18n="wallet_not_set_wx_login">No wallet address found. Please log in using wx.network to automatically set your wallet address.</span>
                                </div>
                                <a href="/login" class="btn btn-primary" onclick="event.preventDefault(); router.navigate('/login');">
                                    <i class="bi bi-wallet2 me-2"></i>
                                    <span data-i18n="login_with_wx_network">Login with WX Network</span>
                                </a>
                            `}
                        </div>
                    </div>
                    <div id="wallet-wall-container" class="mt-4"></div>
                </div>
            </div>
        `;
        this.updateI18n();
        if (wallet) {
            this.renderWallSection('wallet-wall-container', 'wallet', null, wallet, { title: (typeof i18n !== 'undefined' && i18n.t) ? (i18n.t('wallet_wall_title') || 'Wall') : 'Wall' });
        }
    };

    App.prototype.showWithdraw = async function() {
        try {
            const [balance, domainsData] = await Promise.all([
                api.getBalance(),
                api.getDomains()
            ]);
            
            const hasDomains = domainsData.domains && domainsData.domains.length > 0;
            const hasBalance = balance.accumulated_balance > 0;
            
            const main = document.getElementById('main-content');
            main.innerHTML = `
                <div class="row justify-content-center">
                    <div class="col-md-6">
                        <div class="card">
                            <div class="card-header">
                                <h3 data-i18n="request_withdrawal">Request Withdrawal</h3>
                            </div>
                            <div class="card-body">
                                <div class="mb-4">
                                    <h5 data-i18n="your_mining_balance">Your Mining Balance</h5>
                                    <h2 class="text-primary">${balance.accumulated_balance.toFixed(2)} <small class="text-muted" data-i18n="tokens">tokens</small></h2>
                                    ${balance.pending_payout > 0 ? 
                                        `<p class="text-warning"><i class="bi bi-exclamation-triangle"></i> <span data-i18n="pending_payout">Pending payout:</span> ${balance.pending_payout.toFixed(2)}</p>` : 
                                        ''
                                    }
                                </div>
                                
                                ${hasBalance ? 
                                    `<form id="withdraw-form">
                                        <button type="submit" class="btn btn-primary btn-lg w-100" data-i18n="request_withdrawal">Request Withdrawal</button>
                                    </form>` :
                                    (!hasDomains ? `<div class="alert alert-info" data-i18n="no_balance_to_withdraw">No balance to withdraw</div>` : '')
                                }
                            </div>
                        </div>
                    </div>
                </div>
            `;
            this.updateI18n();
            
            if (hasBalance) {
                document.getElementById('withdraw-form').addEventListener('submit', async (e) => {
                    e.preventDefault();
                    try {
                        const data = await api.requestWithdrawal();
                        this.showToast('success', i18n.t('withdrawal_request_created'));
                        setTimeout(() => router.navigate('/'), 2000);
                    } catch (error) {
                        this.showToast('error', error.message || i18n.t('error'));
                    }
                });
            }
        } catch (error) {
            this.showToast('error', error.message || i18n.t('error'));
        }
    };

})();
