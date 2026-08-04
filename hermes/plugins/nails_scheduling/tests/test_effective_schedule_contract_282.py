from nails_scheduling import schemas


def test_work_hour_answers_use_effective_day_view_not_defaults():
    description = schemas.NAILS_SCHEDULING["description"]

    assert "call action=day_view" in description
    assert "effective client-visible work window" in description
    assert "service duration" in description
    assert "preparation and cleanup buffers" in description
    assert "existing bookings" in description
    assert "Default work intervals are only a reusable template" in description
    assert "ask for the date" in description
    assert "working hours are not saved" in description
