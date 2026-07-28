def test_web_price_editor_reuses_open_new_draft(client, clean_database):
    response = client.get("/web/web-service-catalog.js")

    assert response.status_code == 200
    assert 'findIndex((service) => service.is_new === true)' in response.text
    assert 'existingDraftIndex !== -1' in response.text
    assert 'Сначала заполните или удалите открытую новую позицию' in response.text
    assert 'expandedServiceIndex = existingDraftIndex' in response.text
    assert 'focusCatalogDraft(existingDraftIndex)' in response.text


def test_web_price_editor_removes_local_draft_without_archive_copy(client, clean_database):
    response = client.get("/web/web-service-catalog.js")

    assert response.status_code == 200
    assert 'removedWasDraft = serviceCatalogDraft[index]?.is_new === true' in response.text
    assert 'renderServiceCatalogBody("Черновик удалён")' in response.text
    assert 'Убрать из прайса:' in response.text
    assert 'data-remove-service="${index}"' in response.text
