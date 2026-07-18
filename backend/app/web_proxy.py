from __future__ import annotations

from collections.abc import Iterable
from ipaddress import ip_address, ip_network


def _valid_ip(value: str | None) -> str | None:
    if value is None:
        return None
    candidate = value.strip()
    if not candidate:
        return None
    try:
        return str(ip_address(candidate))
    except ValueError:
        return None


def _peer_is_trusted(peer_ip: str, trusted_proxy_cidrs: Iterable[str]) -> bool:
    try:
        peer = ip_address(peer_ip)
    except ValueError:
        return False

    for raw_cidr in trusted_proxy_cidrs:
        try:
            network = ip_network(raw_cidr, strict=False)
        except ValueError:
            continue
        if peer in network:
            return True
    return False


def resolve_client_ip(
    *,
    peer_ip: str,
    x_real_ip: str | None,
    x_forwarded_for: str | None,
    trusted_proxy_cidrs: Iterable[str],
) -> str:
    """Return a normalized client IP without trusting arbitrary forwarding headers.

    The immediate TCP peer must be explicitly trusted. The trusted edge must replace
    both forwarding headers with one normalized client address. Any malformed,
    multi-hop, or inconsistent value fails closed to the immediate peer address.
    """

    normalized_peer = _valid_ip(peer_ip) or "unknown"
    if normalized_peer == "unknown" or not _peer_is_trusted(
        normalized_peer,
        trusted_proxy_cidrs,
    ):
        return normalized_peer

    real_ip = _valid_ip(x_real_ip)
    if real_ip is None or x_forwarded_for is None:
        return normalized_peer

    forwarded_parts = [part.strip() for part in x_forwarded_for.split(",")]
    if len(forwarded_parts) != 1:
        return normalized_peer
    forwarded_ip = _valid_ip(forwarded_parts[0])
    if forwarded_ip is None or forwarded_ip != real_ip:
        return normalized_peer

    return real_ip
