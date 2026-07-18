from app.web_proxy import resolve_client_ip


def test_untrusted_peer_headers_are_ignored() -> None:
    result = resolve_client_ip(
        peer_ip="192.0.2.10",
        x_real_ip="192.0.2.20",
        x_forwarded_for="192.0.2.20",
        trusted_proxy_cidrs=("172.18.0.0/16",),
    )
    assert result == "192.0.2.10"


def test_trusted_peer_accepts_one_matching_address() -> None:
    result = resolve_client_ip(
        peer_ip="172.18.0.5",
        x_real_ip="192.0.2.20",
        x_forwarded_for="192.0.2.20",
        trusted_proxy_cidrs=("172.18.0.0/16",),
    )
    assert result == "192.0.2.20"


def test_trusted_peer_rejects_address_chain() -> None:
    result = resolve_client_ip(
        peer_ip="172.18.0.5",
        x_real_ip="192.0.2.20",
        x_forwarded_for="192.0.2.30, 192.0.2.20",
        trusted_proxy_cidrs=("172.18.0.0/16",),
    )
    assert result == "172.18.0.5"


def test_trusted_peer_rejects_mismatched_headers() -> None:
    result = resolve_client_ip(
        peer_ip="172.18.0.5",
        x_real_ip="192.0.2.20",
        x_forwarded_for="192.0.2.30",
        trusted_proxy_cidrs=("172.18.0.0/16",),
    )
    assert result == "172.18.0.5"


def test_invalid_proxy_ranges_fail_closed() -> None:
    result = resolve_client_ip(
        peer_ip="172.18.0.5",
        x_real_ip="192.0.2.20",
        x_forwarded_for="192.0.2.20",
        trusted_proxy_cidrs=("invalid",),
    )
    assert result == "172.18.0.5"
