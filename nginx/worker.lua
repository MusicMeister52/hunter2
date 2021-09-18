local client = require("resty.dns.client")
client.init()

backend_servers = {}

local function update_dns_function(hostname)
    return function()
        local answers, err = client.resolve(hostname)
        if not answers then
            ngx.log(ngx.ERR, "failed to query resolver: ", err)
            return
        end
        if answers.errcode then
            ngx.log(ngx.ERR, "server returned error code: ", answers.errcode, ": ", answers.errstr)
            return
        end

        new_backend_servers = {}
        for i, ans in ipairs(answers) do
            table.insert(new_backend_servers, ans.address)
        end
        ngx.log(ngx.INFO, "updating "..hostname.." upstream with "..#new_backend_servers.." backends")
        backend_servers[hostname] = new_backend_servers
    end
end

app_hostname = os.getenv("H2_APP_HOSTNAME") or "app"
backend_servers[app_hostname] = {}
local app_update_function = update_dns_function(app_hostname)
ngx.timer.at(0, app_update_function)
ngx.timer.every(10, app_update_function)

websocket_hostname = os.getenv("H2_WEBSOCKET_HOSTNAME") or "websocket"
backend_servers[websocket_hostname] = {}
local websocket_update_function = update_dns_function(websocket_hostname)
ngx.timer.at(0, websocket_update_function)
ngx.timer.every(10, websocket_update_function)

function balancer(hostname, port)
    local balancer = require("ngx.balancer")

    if #backend_servers[hostname] == 0 then
        ngx.log(ngx.ERR, "no backend servers available")
        return ngx.exit(500)
    end

    -- This block will only trigger if ngx.ctx.retry is not true or is
    -- unset.
    -- We set this to true during the initial request so future
    -- requests within this context will not go down this path.
    if not ngx.ctx.retry then
        ngx.ctx.retry = true
        -- Pick a random backend to start with
        server = backend_servers[hostname][math.random(#backend_servers[hostname])]

        -- Kinda messy but, create a context table we dump tried
        -- backends to.
        ngx.ctx.tried = {}
        ngx.ctx.tried[server] = true

        -- set up more tries using the length of the server list minus 1.
        ok, err = balancer.set_more_tries(#backend_servers[hostname] - 1)
        if not ok then
            ngx.log(ngx.ERR, "set_more_tries failed: ", err)
        end

    else
        -- This block will trigger on a retry
        -- Here we'll run through the backends and pick one we haven't
        -- tried yet.
        for i, ip in ipairs(backend_servers[hostname]) do
            in_ctx = ngx.ctx.tried[ip] ~= nil
            if in_ctx == false then
                ngx.ctx.tried[ip] = true
                server = ip
                break
            end
        end
    end

    -- Hardcoded port again to make example easier
    ok, err = balancer.set_current_peer(server, port)
    if not ok then
        ngx.log(ngx.ERR, "set_current_peer failed: ", err)
        return ngx.exit(500)
    end
end

prometheus = require("prometheus").init("prometheus_metrics")
metric_requests = prometheus:counter("nginx_http_requests_total", "Number of HTTP requests", {"host", "status"})
metric_latency = prometheus:histogram("nginx_http_request_duration_seconds", "HTTP request latency", {"host"})
metric_connections = prometheus:gauge("nginx_http_connections", "Number of HTTP connections", {"state"})
