from app.services.client_linking import normalize_phone


def test_russian_phone_formats_share_one_canonical_key():
    variants = [
        "+7 999 111-22-33",
        "7 (999) 111 22 33",
        "8 999 111 22 33",
        "89991112233",
        "9991112233",
        "+7 (999) 111-22-33 доб. 45",
    ]
    assert {normalize_phone(value) for value in variants} == {"79991112233"}


def test_international_00_prefix_matches_explicit_plus():
    assert normalize_phone("+33 6 12 34 56 78") == "33612345678"
    assert normalize_phone("00 33 6 12 34 56 78") == "33612345678"


def test_explicit_foreign_country_code_is_not_rewritten_as_russian():
    assert normalize_phone("+33 6 12 34 56 78") != normalize_phone("8 612 345 67 8")


def test_invalid_phone_values_do_not_produce_match_keys():
    assert normalize_phone(None) is None
    assert normalize_phone("") is None
    assert normalize_phone("12345") is None
    assert normalize_phone("0000000000") is None


def test_formatting_characters_do_not_affect_matching():
    assert normalize_phone("+7(999)1112233") == normalize_phone("+7 999 111 22 33")
