from app.services.qemu_manager import ConsoleBuffer


def test_write_resize_stores_dimensions():
    sent: list[bytes] = []

    class FakeWriter:
        def write(self, data: bytes):
            sent.append(data)

        async def drain(self):
            return None

    cb = ConsoleBuffer("inst_test", "/tmp/fake.sock")
    cb.writer = FakeWriter()
    cb.write_resize(120, 40)

    assert cb.cols == 120
    assert cb.rows == 40
    assert sent == []


def test_write_resize_clamps_dimensions():
    cb = ConsoleBuffer("inst_test", "/tmp/fake.sock")
    cb.write_resize(9999, 0)

    assert cb.cols == 500
    assert cb.rows == 1
