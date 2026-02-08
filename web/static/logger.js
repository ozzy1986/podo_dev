/**
 * Client-side Logger
 * Logs to browser console and optionally to server endpoint
 */

class Logger {
    constructor() {
        this.logs = [];
        this.maxLogs = 1000; // Keep last 1000 logs in memory
        this.enableServerLogging = false; // Can be enabled via API
    }

    log(level, message, data = null) {
        const timestamp = new Date().toISOString();
        const logEntry = {
            timestamp,
            level,
            message,
            data,
            url: window.location.href,
            userAgent: navigator.userAgent
        };

        // Add to memory buffer
        this.logs.push(logEntry);
        if (this.logs.length > this.maxLogs) {
            this.logs.shift(); // Remove oldest
        }

        // Console logging
        const consoleMethod = level === 'error' ? 'error' : 
                             level === 'warn' ? 'warn' : 'log';
        console[consoleMethod](`[${level.toUpperCase()}] ${message}`, data || '');

        // Server logging (if enabled)
        if (this.enableServerLogging) {
            this.sendToServer(logEntry).catch(err => {
                console.error('Failed to send log to server:', err);
            });
        }
    }

    async sendToServer(logEntry) {
        try {
            await fetch('/api/logs', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(logEntry)
            });
        } catch (error) {
            // Silently fail - don't spam console
        }
    }

    info(message, data) {
        this.log('info', message, data);
    }

    error(message, data) {
        this.log('error', message, data);
    }

    warn(message, data) {
        this.log('warn', message, data);
    }

    debug(message, data) {
        this.log('debug', message, data);
    }

    getLogs(level = null) {
        if (level) {
            return this.logs.filter(log => log.level === level);
        }
        return [...this.logs];
    }

    clearLogs() {
        this.logs = [];
    }

    downloadLogs() {
        const logsJson = JSON.stringify(this.logs, null, 2);
        const blob = new Blob([logsJson], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `donl-logs-${Date.now()}.json`;
        a.click();
        URL.revokeObjectURL(url);
    }
}

// Export singleton
const logger = new Logger();
window.logger = logger; // For debugging - can call logger.downloadLogs() in console

