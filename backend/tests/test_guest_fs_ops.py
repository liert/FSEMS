from app.services.ssh_service import GuestPathNotFoundError, normalize_guest_path
import pytest


def test_normalize_guest_path_root():
    assert normalize_guest_path("/") == "/"
    assert normalize_guest_path("") == "/"


def test_normalize_guest_path_subdir():
    assert normalize_guest_path("/etc/config") == "/etc/config"


def test_normalize_guest_path_rejects_traversal():
    with pytest.raises(GuestPathNotFoundError):
        normalize_guest_path("/etc/../passwd")
