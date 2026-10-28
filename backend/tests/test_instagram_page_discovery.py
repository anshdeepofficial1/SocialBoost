"""Regression tests for Instagram OAuth Page discovery permissions."""

import pytest

from app.services import oauth_service


def _mock_empty_page_discovery(monkeypatch, permissions):
    def fake_graph_get(path, params, access_token):  # noqa: ARG001
        if path == "me":
            return {"id": "fb-user-test", "name": "Test user"}
        if path == "me/accounts":
            return {"data": []}
        if path == "me/permissions":
            return {
                "data": [
                    {"permission": name, "status": status}
                    for name, status in permissions.items()
                ]
            }
        raise AssertionError(f"Unexpected Graph API path: {path}")

    monkeypatch.setattr(oauth_service, "_graph_get", fake_graph_get)


def test_empty_pages_without_page_list_permission_is_distinguished(monkeypatch):
    _mock_empty_page_discovery(
        monkeypatch,
        {"pages_show_list": "declined", "business_management": "granted"},
    )

    with pytest.raises(oauth_service.InstagramPagePermissionMissing):
        oauth_service.fetch_identity("instagram", "fake-user-token")


def test_empty_pages_without_business_management_is_distinguished(monkeypatch):
    _mock_empty_page_discovery(
        monkeypatch,
        {"pages_show_list": "granted", "business_management": "declined"},
    )

    with pytest.raises(oauth_service.InstagramBusinessManagementPermissionMissing):
        oauth_service.fetch_identity("instagram", "fake-user-token")


def test_empty_pages_with_both_permissions_reports_page_assignment(monkeypatch):
    _mock_empty_page_discovery(
        monkeypatch,
        {"pages_show_list": "granted", "business_management": "granted"},
    )

    with pytest.raises(oauth_service.InstagramPagesNotFound):
        oauth_service.fetch_identity("instagram", "fake-user-token")
