/**
 * UI Module
 * Theme, toast, loading, i18n, navigation, tooltips, utility functions
 */
(function() {
    'use strict';

    App.prototype.initTheme = function() {
        // Check for user's saved preference first
        const savedTheme = localStorage.getItem('theme');
        
        if (savedTheme) {
            // User has manually set a theme, use it
            this.setTheme(savedTheme, false); // false = don't save (already saved)
        } else {
            // No saved preference, detect system theme
            const systemTheme = this.getSystemTheme();
            this.setTheme(systemTheme, false); // false = don't save (system preference, not user choice)
            
            // Listen for system theme changes (only if user hasn't set a preference)
            this.watchSystemTheme();
        }
    };

    App.prototype.getSystemTheme = function() {
        if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
            return 'dark';
        }
        return 'light';
    };

    App.prototype.watchSystemTheme = function() {
        // Only watch system theme if user hasn't manually set a preference
        if (localStorage.getItem('theme')) {
            return; // User has a preference, don't watch system changes
        }

        if (window.matchMedia) {
            const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
            
            // Handle change event
            const handleChange = (e) => {
                // Only update if user hasn't set a preference
                if (!localStorage.getItem('theme')) {
                    const newTheme = e.matches ? 'dark' : 'light';
                    this.setTheme(newTheme, false); // false = don't save
                }
            };

            // Modern browsers
            if (mediaQuery.addEventListener) {
                mediaQuery.addEventListener('change', handleChange);
            } else {
                // Fallback for older browsers
                mediaQuery.addListener(handleChange);
            }
        }
    };

    App.prototype.setTheme = function(theme, saveToStorage = true) {
        // Validate theme
        if (theme !== 'light' && theme !== 'dark') {
            theme = 'light';
        }
        
        // Apply theme to document
        document.documentElement.setAttribute('data-theme', theme);
        
        // Save to localStorage only if user manually changed it
        if (saveToStorage) {
            localStorage.setItem('theme', theme);
            // Stop watching system theme changes since user has set a preference
        }
        
        // Update toggle UI
        this.updateThemeToggle(theme);
    };

    App.prototype.toggleTheme = function() {
        const currentTheme = document.documentElement.getAttribute('data-theme') || 'light';
        const newTheme = currentTheme === 'light' ? 'dark' : 'light';
        // Save to storage = true because user is manually changing theme
        this.setTheme(newTheme, true);
    };

    App.prototype.updateThemeToggle = function(theme) {
        const iconClass = theme === 'dark' ? 'bi bi-moon-fill theme-toggle-icon' : 'bi bi-sun-fill theme-toggle-icon';
        const themeIcon = document.getElementById('theme-icon');
        if (themeIcon) themeIcon.className = iconClass;
        const guestThemeIcon = document.getElementById('guest-theme-icon');
        if (guestThemeIcon) guestThemeIcon.className = iconClass;
    };

    App.prototype.setupLanguageSelector = function() {
        // Use event delegation since menu might not exist yet
        // Attach to document so it works even if menu is created later
        // But only attach once - check if already attached
        if (this.languageSelectorSetup) {
            return;
        }
        
        const languageHandler = async (e) => {
            // Only handle clicks on language menu items
            const langItem = e.target.closest('[data-lang]');
            
            if (!langItem) {
                // Not a language item click, ignore
                return;
            }
            
            // This is a language item click - prevent default and stop propagation
            e.preventDefault();
            e.stopPropagation();
            e.stopImmediatePropagation();
            
            const lang = langItem.getAttribute('data-lang');
            if (!lang) {
                console.warn('[App] Language item has no data-lang attribute');
                return;
            }
            
            try {
                await i18n.setLanguage(lang);
                
                // Close Bootstrap dropdown if open (main and guest nav)
                [document.querySelector('#languageDropdown'), document.querySelector('#guest-languageDropdown')].forEach(dropdown => {
                    if (dropdown) {
                        const bsDropdown = bootstrap.Dropdown.getInstance(dropdown);
                        if (bsDropdown) bsDropdown.hide();
                    }
                });
                
                // Save to API if logged in
                if (this.user) {
                    try {
                        await api.setLanguage(lang);
                    } catch (error) {
                        console.error('[App] Failed to save language:', error);
                    }
                }
            } catch (error) {
                console.error('[App] Failed to change language:', error);
                console.error('[App] Error details:', error.message, error.stack);
            }
        };
        
        // Attach to language menu specifically, using event delegation
        // This ensures it works even if menu is not in DOM yet
        const attachLanguageHandler = () => {
            const languageMenu = document.querySelector('#language-menu');
            const guestLanguageMenu = document.querySelector('#guest-language-menu');
            if (languageMenu) languageMenu.addEventListener('click', languageHandler);
            if (guestLanguageMenu) guestLanguageMenu.addEventListener('click', languageHandler);
            if (!languageMenu && !guestLanguageMenu) {
                setTimeout(attachLanguageHandler, 100);
            }
        };
        
        // Also use document-level delegation as fallback (main and guest language menus)
        document.addEventListener('click', (e) => {
            if (e.target.closest('#language-menu') || e.target.closest('#guest-language-menu')) {
                languageHandler(e);
            }
        });
        
        // Try to attach directly to menu
        attachLanguageHandler();
        this.languageSelectorSetup = true;
    };

    App.prototype.updateI18n = function() {
        // Check if translations are loaded
        const currentLang = i18n.getCurrentLanguage();
        const translations = i18n.translations[currentLang];
        if (!translations || Object.keys(translations).length === 0) {
            console.warn(`[App] updateI18n: No translations loaded for language: ${currentLang}`);
            return;
        }
        
        console.log(`[App] updateI18n: Updating translations for language: ${currentLang}, ${Object.keys(translations).length} keys available`);

        // Update all elements with data-i18n attribute
        const i18nElements = document.querySelectorAll('[data-i18n]');
        console.log(`[App] updateI18n: Found ${i18nElements.length} elements with data-i18n attribute`);
        let updatedCount = 0;
        
        i18nElements.forEach(el => {
            const key = el.getAttribute('data-i18n');
            if (!key) return;
            
            // Special handling for welcome_description which needs token_name parameter
            let translation;
            if (key === 'welcome_description' && this.config && this.config.token_name) {
                translation = i18n.t(key, { token_name: this.config.token_name });
            } else {
                translation = i18n.t(key);
            }
            // Only update if translation is valid (not [key] format)
            // This prevents overwriting already-translated text with codenames
            if (translation && !(translation.startsWith('[') && translation.endsWith(']'))) {
                el.textContent = translation;
                updatedCount++;
            } else if (translation && translation.startsWith('[') && translation.endsWith(']')) {
                // Translation not found - keep existing text if it's already translated
                // Only update if current text is the same as the key (meaning it wasn't translated yet)
                const currentText = el.textContent.trim();
                if (currentText === key || currentText === translation) {
                    // Keep existing text or use fallback
                    // Don't overwrite with [key] if there's already translated text
                }
                console.warn(`[App] updateI18n: Translation not found for key: ${key}`);
            }
        });
        
        console.log(`[App] updateI18n: Updated ${updatedCount} elements`);

        // Update all elements with data-i18n-dynamic attribute (for dynamic translations)
        document.querySelectorAll('[data-i18n-dynamic]').forEach(el => {
            const key = el.getAttribute('data-i18n-dynamic');
            if (!key) return;
            const translation = i18n.t(key);
            // Always update, even if it's [key] - it's better than showing English
            if (translation) {
                el.textContent = translation;
            }
        });


        // Update current language display (main and guest nav)
        const langCode = i18n.getCurrentLanguage().toUpperCase();
        [document.getElementById('current-lang'), document.getElementById('guest-current-lang')].forEach(el => {
            if (el) el.textContent = langCode;
        });
        if (document.getElementById('current-lang') || document.getElementById('guest-current-lang')) {
            console.log(`[App] updateI18n: Updated current language display to: ${langCode}`);
        }
        
        // Update tooltip texts for elements with data-i18n-tooltip
        const aRecordTooltipParams = { ip: this.config && this.config.our_server_ip ? this.config.our_server_ip : '—' };
        document.querySelectorAll('[data-i18n-tooltip]').forEach(el => {
            const key = el.getAttribute('data-i18n-tooltip');
            if (!key) return;
            const translation = (key === 'a_record_option_tooltip') ? i18n.t(key, aRecordTooltipParams) : i18n.t(key);
            if (translation && !(translation.startsWith('[') && translation.endsWith(']'))) {
                el.setAttribute('data-bs-original-title', translation);
                // Reinitialize tooltip if it exists
                const tooltip = bootstrap.Tooltip.getInstance(el);
                if (tooltip) {
                    tooltip.setContent({ '.tooltip-inner': translation });
                } else {
                    // Initialize tooltip if it doesn't exist yet
                    new bootstrap.Tooltip(el, {
                        html: true,
                        placement: el.getAttribute('data-bs-placement') || 'top'
                    });
                }
            }
        });
    };

    App.prototype.initializeTooltips = function() {
        // Initialize Bootstrap tooltips for all elements with data-bs-toggle="tooltip"
        document.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(el => {
            // Destroy existing tooltip if any
            const existingTooltip = bootstrap.Tooltip.getInstance(el);
            if (existingTooltip) {
                existingTooltip.dispose();
            }
            
            // Get tooltip text from data-i18n-tooltip or data-bs-original-title
            let tooltipText = el.getAttribute('data-bs-original-title');
            if (!tooltipText && el.hasAttribute('data-i18n-tooltip')) {
                const key = el.getAttribute('data-i18n-tooltip');
                const aRecordParams = { ip: this.config && this.config.our_server_ip ? this.config.our_server_ip : '—' };
                tooltipText = (key === 'a_record_option_tooltip') ? (i18n.t(key, aRecordParams) || '') : (i18n.t(key) || '');
            }
            
            if (tooltipText) {
                el.setAttribute('data-bs-original-title', tooltipText);
                new bootstrap.Tooltip(el, {
                    html: true,
                    placement: 'top'
                });
            }
        });
    };

    App.prototype.updateNavigation = function() {
        const mainNav = document.getElementById('main-nav');
        const guestNav = document.getElementById('guest-nav');
        if (mainNav) {
            mainNav.style.display = api.token ? 'block' : 'none';
        }
        if (guestNav) {
            guestNav.style.display = api.token ? 'none' : 'block';
        }
        
        // Update withdrawal fix notice visibility
        this.initWithdrawalFixNotice();
    };

    App.prototype.setupNavigationHandlers = function() {
        const handleNavClick = (e) => {
            const link = e.target.closest('a[data-route]');
            if (!link) return;
            const targetPath = link.getAttribute('data-route');
            if (!targetPath) return;
            e.preventDefault();
            e.stopPropagation();
            e.stopImmediatePropagation();
            router.navigate(targetPath);
            return false;
        };
        const mainNav = document.getElementById('main-nav');
        if (mainNav) {
            mainNav.addEventListener('click', handleNavClick, true);
        }
        const guestNav = document.getElementById('guest-nav');
        if (guestNav) {
            guestNav.addEventListener('click', handleNavClick, true);
        }
    };

    App.prototype.initWithdrawalFixNotice = function() {
        // Initialize withdrawal fix notice
        const notice = document.getElementById('withdrawal-fix-notice');
        if (!notice) {
            return;
        }

        // Only show notice if user is logged in
        if (!api.token || !this.user) {
            notice.style.display = 'none';
            return;
        }

        // Check if user has dismissed this notice
        const dismissed = localStorage.getItem('withdrawal-fix-notice-dismissed');
        if (dismissed === 'true') {
            notice.style.display = 'none';
            return;
        }

        // Show notice and setup dismiss handler
        notice.style.display = 'block';
        
        // Listen for Bootstrap alert close event
        notice.addEventListener('closed.bs.alert', () => {
            localStorage.setItem('withdrawal-fix-notice-dismissed', 'true');
        });

        // Also handle manual close button click (fallback)
        const closeBtn = notice.querySelector('.btn-close');
        if (closeBtn) {
            closeBtn.addEventListener('click', () => {
                setTimeout(() => {
                    localStorage.setItem('withdrawal-fix-notice-dismissed', 'true');
                }, 300); // Wait for Bootstrap animation
            });
        }
    };

    App.prototype.showToast = function(type, message) {
        const container = document.getElementById('toast-container');
        if (!container) return;

        const toast = document.createElement('div');
        toast.className = `toast align-items-center text-white bg-${type === 'error' ? 'danger' : 'success'} border-0`;
        toast.setAttribute('role', 'alert');
        toast.innerHTML = `
            <div class="d-flex">
                <div class="toast-body">${message}</div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
            </div>
        `;

        container.appendChild(toast);
        const bsToast = new bootstrap.Toast(toast);
        bsToast.show();

        toast.addEventListener('hidden.bs.toast', () => {
            toast.remove();
        });
    };

    App.prototype.showLoading = function(message = null) {
        // Remove existing overlay if any
        this.hideLoading();
        
        const overlay = document.createElement('div');
        overlay.id = 'global-loading-overlay';
        overlay.className = 'position-fixed top-0 start-0 w-100 h-100 d-flex align-items-center justify-content-center';
        overlay.style.cssText = 'background-color: rgba(0, 0, 0, 0.5); z-index: 9999;';
        overlay.innerHTML = `
            <div class="text-center text-white">
                <div class="spinner-border mb-3" role="status" style="width: 3rem; height: 3rem;">
                    <span class="visually-hidden" data-i18n="loading">Loading...</span>
                </div>
                ${message ? `<div class="h5">${message}</div>` : ''}
            </div>
        `;
        document.body.appendChild(overlay);
    };

    App.prototype.hideLoading = function() {
        const overlay = document.getElementById('global-loading-overlay');
        if (overlay) {
            overlay.remove();
        }
    };

    App.prototype.escapeHtml = function(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    };

    App.prototype.formatNumber = function(num, decimals = 2) {
        if (num === null || num === undefined) return 'N/A';
        return Number(num).toLocaleString(undefined, { 
            minimumFractionDigits: decimals, 
            maximumFractionDigits: decimals 
        });
    };

    App.prototype.renderDailyEarningsChart = function(dailyEarnings) {
        if (!dailyEarnings || Object.keys(dailyEarnings).length === 0) {
            return '<div class="text-center text-muted py-4" data-i18n="no_data_available">No data available</div>';
        }
        
        // Get last 30 days data, reverse to show oldest to newest
        const dates = Object.keys(dailyEarnings).sort().slice(-30);
        const values = dates.map(date => dailyEarnings[date] || 0);
        const maxValue = Math.max(...values, 1); // Avoid division by zero
        
        // Create bar chart using CSS
        const bars = dates.map((date, index) => {
            const value = values[index];
            const height = maxValue > 0 ? (value / maxValue) * 100 : 0;
            const dateLabel = new Date(date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
            
            return `
                <div class="d-inline-block" style="width: calc(100% / ${Math.min(dates.length, 30)}); padding: 0 1px; display: flex; flex-direction: column; align-items: center;">
                    <div style="height: 150px; width: 100%; display: flex; align-items: flex-end; justify-content: center;">
                        <div class="bg-primary rounded-top" style="width: 90%; height: ${height}%; min-height: ${value > 0 ? '2px' : '0'}; transition: all 0.3s;" title="${dateLabel}: ${value.toFixed(2)}"></div>
                    </div>
                    <div style="height: 40px; width: 100%; display: flex; align-items: flex-start; justify-content: center; padding-top: 5px;">
                        <small class="text-muted" style="font-size: 0.7rem; transform: rotate(-45deg); transform-origin: center center; white-space: nowrap; display: inline-block;">${index % 5 === 0 ? dateLabel : ''}</small>
                    </div>
                </div>
            `;
        }).join('');
        
        return `
            <div class="d-flex align-items-end" style="overflow-x: auto; padding-bottom: 30px;">
                ${bars}
            </div>
            <div class="text-center mt-2">
                <small class="text-muted" data-i18n="hover_for_details">Hover over bars for details</small>
            </div>
        `;
    };

    App.prototype.renderWeeklyEarningsChart = function(weeklyEarnings) {
        if (!weeklyEarnings || Object.keys(weeklyEarnings).length === 0) {
            return '<div class="text-center text-muted py-4" data-i18n="no_data_available">No data available</div>';
        }
        
        // Get last 12 weeks data
        const weeks = Object.keys(weeklyEarnings).sort().slice(-12);
        const values = weeks.map(week => weeklyEarnings[week] || 0);
        const maxValue = Math.max(...values, 1);
        
        // Create bar chart using CSS
        const bars = weeks.map((week, index) => {
            const value = values[index];
            const height = maxValue > 0 ? (value / maxValue) * 100 : 0;
            const weekLabel = `Week ${index + 1}`;
            const weekDate = new Date(week).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
            
            return `
                <div class="d-inline-block" style="width: calc(100% / ${Math.min(weeks.length, 12)}); padding: 0 2px; display: flex; flex-direction: column; align-items: center;">
                    <div style="height: 150px; width: 100%; display: flex; align-items: flex-end; justify-content: center;">
                        <div class="bg-info rounded-top" style="width: 85%; height: ${height}%; min-height: ${value > 0 ? '2px' : '0'}; transition: all 0.3s;" title="${weekDate}: ${value.toFixed(2)}"></div>
                    </div>
                    <div style="height: 30px; width: 100%; display: flex; align-items: flex-start; justify-content: center; padding-top: 5px;">
                        <small class="text-muted" style="font-size: 0.75rem; text-align: center;">${weekLabel}</small>
                    </div>
                </div>
            `;
        }).join('');
        
        return `
            <div class="d-flex align-items-end" style="overflow-x: auto;">
                ${bars}
            </div>
            <div class="text-center mt-2">
                <small class="text-muted" data-i18n="hover_for_details">Hover over bars for details</small>
            </div>
        `;
    };

    App.prototype.copyToClipboard = function(elementId) {
        const el = document.getElementById(elementId);
        el.select();
        document.execCommand('copy');
        this.showToast('success', i18n.t('copied_to_clipboard') || 'Copied!');
    };

})();
