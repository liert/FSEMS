from types import SimpleNamespace

import pytest

from app.services import instance_service


class _FakeSession:
    async def commit(self):
        pass

    async def refresh(self, instance, attribute_names=None):
        pass


@pytest.mark.asyncio
async def test_update_cpu_sets_instance_override():
    instance = SimpleNamespace(cpu=None, updated_at=None)
    session = _FakeSession()

    updated = await instance_service.update_cpu(session, instance, " max ")

    assert updated is instance
    assert instance.cpu == "max"


@pytest.mark.asyncio
async def test_update_cpu_empty_value_restores_template_default():
    instance = SimpleNamespace(cpu="max", updated_at=None)
    session = _FakeSession()

    await instance_service.update_cpu(session, instance, "")

    assert instance.cpu is None
