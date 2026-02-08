-- SSL Certificate Loader for Nginx
-- Dynamically loads SSL certificates based on SNI (Server Name Indication)
-- This allows nginx to serve HTTPS for thousands of domains without reloading config

local _M = {}

local ssl_certs = ngx.shared.ssl_certs
-- Check standard location, user certbot dir, and /tmp (when certbot runs as non-root)
-- Order: /etc first, then /tmp (glob once at startup via env or fixed uids), then ubuntu home
local cert_base_paths = {
    "/etc/letsencrypt/live",
    "/home/ubuntu/.certbot/config/live",
    "/tmp/certbot-1000/config/live",  -- ubuntu batch/cron
    "/tmp/certbot-33/config/live"     -- www-data (CGI) typical uid
}

-- Initialize shared dictionary (called once at nginx startup)
function _M.init()
    if not ssl_certs then
        ngx.log(ngx.ERR, "ssl_certs shared dictionary not found")
        return
    end
    
    ngx.log(ngx.INFO, "SSL certificate loader initialized")
end

-- Load certificate for current request
function _M.load_certificate()
    local sni_name = ngx.var.ssl_server_name
    
    if not sni_name or sni_name == "" then
        -- No SNI, use default certificate
        return
    end
    
    -- Normalize domain (remove www. prefix for lookup)
    local domain = sni_name:gsub("^www%.", "")
    
    -- Check cache first
    local cache_key = "cert:" .. domain
    local cached = ssl_certs:get(cache_key)
    
    if cached == "exists" then
        -- Certificate exists, nginx will use it from default location
        return
    elseif cached == "missing" then
        -- Certificate doesn't exist, skip SSL (will fall back to HTTP)
        return
    end
    
    -- Check if certificate files exist in any of the base paths
    local cert_path = nil
    local key_path = nil
    
    for _, base_path in ipairs(cert_base_paths) do
        local test_cert_path = base_path .. "/" .. domain .. "/fullchain.pem"
        local test_key_path = base_path .. "/" .. domain .. "/privkey.pem"
        
        local file = io.open(test_cert_path, "r")
        if file then
            file:close()
            -- Certificate exists at this path
            cert_path = test_cert_path
            key_path = test_key_path
            break
        end
    end
    
    if cert_path and key_path then
        -- Certificate exists
        ssl_certs:set(cache_key, "exists", 3600)  -- Cache for 1 hour
        
        -- Set certificate paths for nginx
        ngx.var.ssl_certificate = cert_path
        ngx.var.ssl_certificate_key = key_path
        
        ngx.log(ngx.INFO, "SSL certificate loaded for: " .. domain .. " from " .. cert_path)
    else
        -- Certificate doesn't exist in any location
        ssl_certs:set(cache_key, "missing", 300)  -- Cache for 5 minutes
        
        ngx.log(ngx.DEBUG, "SSL certificate not found for: " .. domain)
        
        -- For user domains without certificates, nginx will use default certificate (d.onl)
        -- This allows HTTPS to work but browser will show certificate mismatch warning
    end
end

-- Clear cache for a domain (useful after certificate renewal)
function _M.clear_cache(domain)
    if ssl_certs then
        ssl_certs:delete("cert:" .. domain)
        ngx.log(ngx.INFO, "Cleared SSL cache for: " .. domain)
    end
end

return _M
