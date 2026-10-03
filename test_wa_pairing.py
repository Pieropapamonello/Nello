import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from wa_pairing import PairingCodes, phone_number


class PairingTests(unittest.IsolatedAsyncioTestCase):
    def make(self):
        pairing = SimpleNamespace(admin=AsyncMock(return_value=123), connected=False,
                                  lock=asyncio.Lock(), message=None)
        return PairingCodes(pairing)

    def test_phone_format_requires_international_digits(self):
        self.assertEqual(phone_number('+39 333-1234567'), '393331234567')
        for value in ('0039 3331234567', 'abc', '1234', '+39test3331234567', '１２３４５６７８９'):
            with self.assertRaises(ValueError):
                phone_number(value)

    async def test_without_login_or_when_connected_no_request_is_queued(self):
        codes = self.make()
        self.assertEqual((await codes.request(456, '393331234567'))['reason'], 'not_admin')
        codes.pairing.connected = True
        self.assertEqual((await codes.request(123, '393331234567'))['reason'], 'connected')
        self.assertIsNone(codes.pending)

    async def test_single_flight_and_nonce_deliver_code_only_once(self):
        codes = self.make()
        task = asyncio.create_task(codes.request(123, '+39 3331234567'))
        await asyncio.sleep(0)
        self.assertEqual((await codes.request(123, '393331234567'))['reason'], 'busy')
        job = await codes.take()
        self.assertEqual(job['phone'], '393331234567')
        self.assertEqual(await codes.take(), {})
        self.assertFalse((await codes.finish({'id': 'wrong', 'code': 'ABCD1234'}))['ok'])
        self.assertTrue((await codes.finish({'id': job['id'], 'code': 'ABCD1234'}))['ok'])
        self.assertEqual(await task, {'ok': True, 'code': 'ABCD1234'})
        self.assertIsNone(codes.pending)

    async def test_logout_during_request_prevents_code_delivery(self):
        codes = self.make()
        task = asyncio.create_task(codes.request(123, '393331234567'))
        await asyncio.sleep(0)
        job = await codes.take()
        codes.pairing.admin.return_value = None
        await codes.finish({'id': job['id'], 'code': 'ABCD1234'})
        self.assertEqual((await task)['reason'], 'not_admin')
        self.assertIsNone(codes.pending)

    async def test_cancellation_cleans_request_and_resumes_qr(self):
        codes = self.make()
        task = asyncio.create_task(codes.request(123, '393331234567'))
        await asyncio.sleep(0)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertIsNone(codes.pending)
        self.assertEqual(codes.pause_qr_until, 0)


if __name__ == '__main__':
    unittest.main()
