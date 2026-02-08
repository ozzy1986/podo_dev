/**
 * Client-side Internationalization (i18n)
 * Loads locale JSON files and provides translation function
 */

class I18n {
    constructor() {
        this.currentLanguage = 'en';
        this.translations = {};
        this.loadedLanguages = new Set();
    }

    async loadLanguage(lang) {
        if (this.loadedLanguages.has(lang)) {
            return; // Already loaded
        }

        // Load via API endpoint (which serves from root locales directory)
        try {
            let localeData;
            
            // Use API client if available, otherwise fallback to direct fetch
            if (window.api && typeof window.api.getLocale === 'function') {
                localeData = await window.api.getLocale(lang);
            } else {
                // Fallback: try API endpoint directly
                const url = `${window.location.origin}/api?endpoint=/locales/${lang}.json`;
                
                const response = await fetch(url);
                if (!response.ok) {
                    throw new Error(`Failed to load locale: ${lang} (${response.status})`);
                }
                
                localeData = await response.json();
            }
            
            // Ensure we have valid translation data (object with keys)
            if (!localeData || typeof localeData !== 'object' || Array.isArray(localeData)) {
                throw new Error(`Invalid locale data format for ${lang}`);
            }
            
            // Check if response is an error response (has error field but is not a valid locale file)
            // Note: locale files may contain "error" as a translation key, so we distinguish between:
            // - Error response: {error: "message"} or {error: "message", ...} with very few keys
            // - Valid locale: {error: "Ошибка", welcome_title: "...", ...} with many translation keys
            const keys = Object.keys(localeData);
            if (localeData.error && keys.length <= 3 && !localeData.welcome_title && !localeData.welcome_description) {
                // This looks like an error response, not a locale file
                throw new Error(localeData.error);
            }
            
            // Store translations
            this.translations[lang] = localeData;
            this.loadedLanguages.add(lang);
            
            console.log(`[i18n] Loaded ${Object.keys(localeData).length} translations for ${lang}`);

            if (window.app && typeof window.app.updateI18n === 'function') {
                window.app.updateI18n();
            }
        } catch (error) {
            console.error(`[i18n] Error loading language ${lang} from API:`, error);
            
            // Fallback: try loading from static file directly
            try {
                const staticUrl = `/locales/${lang}.json`;
                const response = await fetch(staticUrl);
                if (response.ok) {
                    const localeData = await response.json();
                    if (localeData && typeof localeData === 'object' && !Array.isArray(localeData)) {
                        this.translations[lang] = localeData;
                        this.loadedLanguages.add(lang);
                        console.log(`[i18n] Loaded ${Object.keys(localeData).length} translations for ${lang} from static file`);
                        
                        if (window.app && typeof window.app.updateI18n === 'function') {
                            window.app.updateI18n();
                        }
                        return; // Successfully loaded from static file
                    }
                }
            } catch (staticError) {
                console.error(`[i18n] Also failed to load from static file:`, staticError);
            }
            
            // Final fallback: empty translations
            console.warn(`[i18n] Using empty translations for ${lang} - translations will show as [key]`);
            this.translations[lang] = {};
            this.loadedLanguages.add(lang);
        }
    }

    async setLanguage(lang) {
        console.log(`[i18n] Setting language to: ${lang}`);
        await this.loadLanguage(lang);
        this.currentLanguage = lang;
        console.log(`[i18n] Language set to: ${lang}, translations loaded: ${Object.keys(this.translations[lang] || {}).length} keys`);
        
        // Update HTML lang attribute
        document.documentElement.lang = lang;
        
        // Trigger language change event
        window.dispatchEvent(new CustomEvent('languageChanged', { detail: { language: lang } }));
        console.log(`[i18n] Language change event dispatched`);
        
        // Re-render current page
        if (window.router) {
            console.log(`[i18n] Triggering router render`);
            window.router.render();
        } else {
            console.warn(`[i18n] Router not available for re-render`);
        }
    }

    t(key, params = {}) {
        const translations = this.translations[this.currentLanguage] || {};
        
        // Debug: log if translations are missing
        if (!translations || Object.keys(translations).length === 0) {
            console.warn(`[i18n] No translations loaded for language: ${this.currentLanguage}. Available languages:`, Object.keys(this.translations));
        }
        
        let text = translations[key];
        
        // If translation not found, try to find it in other loaded languages as fallback
        if (!text) {
            // Try English as fallback
            if (this.currentLanguage !== 'en' && this.translations['en'] && this.translations['en'][key]) {
                text = this.translations['en'][key];
                console.warn(`[i18n] Translation key "${key}" not found for ${this.currentLanguage}, using English fallback`);
            } else {
                text = `[${key}]`;
                // Only log missing keys in development (not for every missing key to avoid spam)
                if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
                    console.warn(`[i18n] Translation key "${key}" not found for language ${this.currentLanguage}`);
                }
            }
        }

        // Replace parameters
        if (Object.keys(params).length > 0) {
            try {
                text = text.replace(/\{(\w+)\}/g, (match, paramKey) => {
                    return params[paramKey] !== undefined ? params[paramKey] : match;
                });
            } catch (e) {
                console.error(`Error formatting translation key "${key}":`, e);
            }
        }

        return text;
    }

    getCurrentLanguage() {
        return this.currentLanguage;
    }

    getSupportedLanguages() {
        return ['en', 'ru', 'ar'];
    }

    getLanguageName(lang) {
        const names = {
            'en': { 'en': 'English', 'ru': 'Английский', 'ar': 'الإنجليزية' },
            'ru': { 'en': 'Russian', 'ru': 'Русский', 'ar': 'الروسية' },
            'ar': { 'en': 'Arabic', 'ru': 'Арабский', 'ar': 'العربية' }
        };
        return names[lang]?.[this.currentLanguage] || lang;
    }
}

// Export singleton instance
const i18n = new I18n();
window.i18n = i18n; // For debugging

