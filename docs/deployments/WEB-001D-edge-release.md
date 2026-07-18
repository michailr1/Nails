# WEB-001D — TLS, trusted proxy and public edge release gate

This document defines the release gate for the master WEB read-only interface. It does not authorize a production deployment by itself.

## Fixed production topology

```text
Internet
  -> Caddy de.funti.cc:8446
  -> 127.0.0.1:8220 nails-web (nginx)
  -> nails-edge network nails-api:8000
```

The internal Booking API remains published only on `127.0.0.1:8210`. Caddy must never proxy `/api/v1/*` to a browser.

## TLS issuance strategy

The selected strategy is Caddy automatic HTTPS using the existing certificate identity for `de.funti.cc`.

The read-only production preflight established:

- `de.funti.cc` resolves to the production VPS;
- Caddy owns public TCP port 80 and returns an HTTP redirect;
- Caddy ACME storage already contains certificate material for `de.funti.cc`;
- TCP port 8446 is free;
- the active Caddy configuration validates successfully.

Caddy may therefore reuse or renew the existing domain certificate while serving HTTPS on 8446. HTTP-01 validation is performed through Caddy's existing port 80 listener. Port 443 is not assumed to be available to this service.

Before enabling the route, validate the complete candidate Caddyfile with `caddy validate`. After reload, verify the certificate presented by `de.funti.cc:8446`, its hostname, issuer and expiry. Never print certificate private keys or ACME account files.

If automatic issuance or reuse fails, stop. Do not publish a plaintext listener and do not bypass certificate validation. DNS-01 or an explicitly managed certificate requires a separate reviewed change.

## Proxy-level kill-switch

The public route is disabled by default.

- `ops/edge/nails-web.Caddyfile` is the disabled state and returns HTTP 503.
- `ops/edge/nails-web.enabled.Caddyfile` is the enabled state and proxies to `127.0.0.1:8220`.

The active host fragment must be a root-owned file outside the repository checkout. Switching state is performed by atomically replacing that fragment, validating the complete Caddy configuration, and then using `caddy reload`. It does not require rebuilding or redeploying the application.

Rollback is the same operation in reverse: restore the disabled fragment, validate, reload, and confirm public HTTP 503.

## Forwarded client address contract

The forwarding chain is strict and fail-closed:

1. Caddy replaces `X-Real-IP` and `X-Forwarded-For` with one normalized remote address.
2. nginx accepts `X-Real-IP` only from the verified Docker bridge gateway and keeps `real_ip_recursive off`.
3. nginx applies auth rate limiting after real-IP normalization.
4. nginx replaces both forwarding headers before proxying to FastAPI.
5. FastAPI accepts forwarding headers only when its immediate peer is inside `WEB_TRUSTED_PROXY_CIDRS`.
6. malformed, inconsistent or multi-hop values fall back to the immediate TCP peer.

For the observed production network, `nails-edge` is `172.18.0.0/16` and its host gateway is expected at `172.18.0.1`. These values must be re-read after the candidate container starts. Do not enable the public route if they differ from the nginx and application trust configuration.

## Candidate gate

A candidate may start `nails-web` on loopback while both public and application switches remain disabled. It must not change the production checkout.

Required candidate evidence:

- API and WEB images contain the exact approved candidate SHA;
- API `/health` and `/ready` succeed on `127.0.0.1:8210`;
- WEB `/web-health` succeeds on `127.0.0.1:8220`;
- `nails-web` is connected only to `nails-edge`;
- `nails-api` remains connected to `nails-edge` and `nails-internal`;
- `nails-db` remains connected only to `nails-internal`;
- `nails-edge` gateway and subnet match the trusted proxy configuration;
- direct spoofed `X-Forwarded-For` does not alter the application client scope;
- nginx rate limiting distinguishes two normalized client addresses and limits repeated auth requests from one address;
- no `/api/v1/*` route is reachable through `127.0.0.1:8220`;
- `WEB_AUTH_ENABLED=false` still returns the unavailable response for browser auth;
- disabled Caddy state returns HTTP 503 on 8446;
- certificate hostname and validity checks succeed.

Only after the exact candidate is green may a separate approved operation set the production WEB auth variables and switch the Caddy fragment to the enabled state.

## Safe diagnostics

Do not print `docker compose config` when it is rendered with `/opt/nails/.env`: Compose interpolation can expose database passwords and other secrets even when selected WEB fields are later redacted.

Use only targeted presence checks:

```bash
for key in \
  WEB_AUTH_ENABLED \
  WEB_AUTH_HMAC_KEY \
  WEB_ALLOWED_HOSTS \
  WEB_ALLOWED_ORIGINS \
  WEB_TRUSTED_PROXY_CIDRS \
  NAILS_WEB_BIND \
  NAILS_WEB_PORT
do
  if grep -qE "^${key}=" /opt/nails/.env; then
    printf '%s=present\n' "$key"
  else
    printf '%s=absent\n' "$key"
  fi
done
```

Never output values from `/opt/nails/.env`, certificate contents, private keys, tokens, Telegram identifiers or database connection strings.
