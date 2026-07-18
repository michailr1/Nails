# WEB-001D — production edge preflight

Run on `de.funti.cc` as root before choosing or installing the public HTTPS listener. This is read-only and must not print secrets or complete environment files.

```bash
set -Eeuo pipefail

REPO=/opt/nails/repo
PROFILE=/root/.hermes/profiles/nails

printf 'hostname=%s\n' "$(hostname -f)"
printf 'checkout_sha=%s\n' "$(git -C "$REPO" rev-parse HEAD)"
printf 'branch=%s\n' "$(git -C "$REPO" branch --show-current)"
printf 'tree_clean=%s\n' "$(test -z "$(git -C "$REPO" status --porcelain)" && echo true || echo false)"
printf 'api_health=%s\n' "$(curl -fsS http://127.0.0.1:8210/health | tr -d '\n')"
printf 'api_readiness=%s\n' "$(curl -fsS http://127.0.0.1:8210/ready | tr -d '\n')"
printf 'gateway_state=%s\n' "$(XDG_RUNTIME_DIR=/run/user/0 systemctl --user is-active hermes-gateway-nails.service || true)"

printf '%s\n' '--- listeners ---'
ss -H -lntp | awk '{print $1, $4, $6}' | sort

printf '%s\n' '--- candidate edge services ---'
for unit in nginx.service caddy.service apache2.service haproxy.service traefik.service; do
  if systemctl list-unit-files "$unit" --no-legend 2>/dev/null | grep -q .; then
    systemctl show "$unit" -p LoadState -p ActiveState -p SubState -p FragmentPath --no-pager
  fi
done

printf '%s\n' '--- edge executables ---'
for binary in nginx caddy apache2 haproxy traefik certbot; do
  if command -v "$binary" >/dev/null 2>&1; then
    printf '%s=%s\n' "$binary" "$(command -v "$binary")"
  fi
done

printf '%s\n' '--- certificate metadata only ---'
if command -v certbot >/dev/null 2>&1; then
  certbot certificates 2>/dev/null \
    | sed -n -E '/Certificate Name:|Domains:|Expiry Date:|Certificate Path:|Private Key Path:/p'
fi

printf '%s\n' '--- firewall status ---'
if command -v ufw >/dev/null 2>&1; then
  ufw status numbered
elif command -v firewall-cmd >/dev/null 2>&1; then
  firewall-cmd --list-all
else
  nft list ruleset 2>/dev/null | sed -n '1,240p'
fi

printf '%s\n' '--- docker surface ---'
docker compose --project-directory "$REPO" --file "$REPO/compose.yaml" --env-file /opt/nails/.env ps

printf '%s\n' '--- safe WEB env presence ---'
for key in WEB_AUTH_ENABLED WEB_AUTH_HMAC_KEY WEB_ALLOWED_HOSTS WEB_ALLOWED_ORIGINS NAILS_WEB_BIND NAILS_WEB_PORT; do
  if grep -qE "^${key}=" /opt/nails/.env; then
    printf '%s=present\n' "$key"
  else
    printf '%s=absent\n' "$key"
  fi
done

printf 'profile_mode=%s\n' "$(stat -c '%a %U:%G' "$PROFILE")"
printf 'EDGE_PREFLIGHT_OK=true\n'
```

Stop and report without modifying the host if any of these are false:

- hostname is `de.funti.cc`;
- checkout is `main` and clean;
- `/health` and `/ready` succeed;
- gateway is active;
- the production API remains bound to loopback;
- no listener already occupies the proposed high HTTPS port.

The report must include only the command output above. Do not include certificate contents, private keys, tokens, identifiers, passwords, or the contents of either `.env` file.
