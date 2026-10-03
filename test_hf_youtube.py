import os
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch
import uuid

from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from hf_youtube import download_youtube
from hf_youtube_space.backend import check_info, download, video_id

IDENT = 'z9A1Wf695sQ'


class Guards(unittest.TestCase):
    def test_url_boundary(self):
        self.assertEqual(video_id('https://youtube.com/shorts/' + IDENT), IDENT)
        for url in ('http://youtube.com/watch?v=' + IDENT,
                    'https://youtube.com.evil.org/watch?v=' + IDENT,
                    'https://localhost/watch?v=' + IDENT,
                    'https://user@youtube.com/watch?v=' + IDENT,
                    'https://youtube.com:8443/watch?v=' + IDENT):
            self.assertIsNone(video_id(url))

    def test_long_video_stops_before_download_and_cookie_is_removed(self):
        with tempfile.TemporaryDirectory() as directory, patch('hf_youtube_space.backend.yt_dlp.YoutubeDL') as mock:
            ydl = mock.return_value.__enter__.return_value
            ydl.extract_info.return_value = {'id': IDENT, 'duration': 181}
            result, path = download('https://youtu.be/' + IDENT, 'private-cookie', directory)
            self.assertTrue(result['skip_long'])
            self.assertIsNone(path)
            ydl.process_ie_result.assert_not_called()
            self.assertFalse((Path(directory) / 'cookies.txt').exists())

    def test_wrong_identity_unknown_duration_and_live_are_rejected(self):
        for info in ({'id': 'a8D8awQaneo', 'duration': 10},
                     {'id': IDENT, 'duration': float('nan')},
                     {'id': IDENT, 'duration': 0},
                     {'id': IDENT, 'duration': 10, 'is_live': True}):
            with self.assertRaises(ValueError):
                check_info(info, IDENT)


class Transfer(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.artifact = str(uuid.uuid4())
        self.deleted = []
        self.payload = b'valid media bytes'
        self.info = {'success': True, 'artifact': self.artifact, 'id': IDENT, 'duration': 59,
                     'suffix': '.mp4', 'size': len(self.payload), 'source_info': {'language': 'it'}}
        self.received = None
        async def health(request):
            return web.json_response({'status': 'ok', 'provider': True})
        async def create(request):
            self.assertEqual(request.headers['X-Nello-Token'], 'test-private-token')
            self.received = await request.json()
            return web.json_response(self.info)
        async def media(request):
            return web.Response(body=self.payload)
        async def remove(request):
            self.deleted.append(request.match_info['ident'])
            return web.json_response({'ok': True})
        app = web.Application()
        app.add_routes([web.get('/api/healthz', health), web.post('/api/youtube', create),
                        web.get('/api/media/{ident}', media), web.delete('/api/media/{ident}', remove)])
        self.client = TestClient(TestServer(app))
        await self.client.start_server()
        self.directory = tempfile.TemporaryDirectory()

    async def asyncTearDown(self):
        self.directory.cleanup()
        await self.client.close()

    async def run_download(self):
        with patch.dict(os.environ, {'HF_YOUTUBE_URL': str(self.client.make_url('')).rstrip('/'),
                                     'HF_YOUTUBE_TOKEN': 'test-private-token'}), \
             patch('hf_youtube.urlsplit', return_value=SimpleNamespace(scheme='https', hostname='test.hf.space')), \
             patch('hf_youtube.read_content', return_value='updated-private-cookie'):
            return await download_youtube('https://youtu.be/' + IDENT, self.directory.name)

    async def test_transfers_native_language_and_latest_cookie_then_deletes_artifact(self):
        result = await self.run_download()
        self.assertTrue(result['success'])
        self.assertEqual(Path(result['file_path']).read_bytes(), self.payload)
        self.assertEqual(self.received['cookies'], 'updated-private-cookie')
        self.assertEqual(result['source_info']['language'], 'it')
        self.assertEqual(self.deleted, [self.artifact])

    async def test_wrong_media_is_never_transferred(self):
        self.info['id'] = 'a8D8awQaneo'
        result = await self.run_download()
        self.assertFalse(result['success'])
        self.assertEqual(list(Path(self.directory.name).iterdir()), [])
        self.assertEqual(self.deleted, [self.artifact])

    async def test_incomplete_transfer_is_removed(self):
        self.info['size'] += 1
        result = await self.run_download()
        self.assertFalse(result['success'])
        self.assertEqual(list(Path(self.directory.name).iterdir()), [])
        self.assertEqual(self.deleted, [self.artifact])


if __name__ == '__main__':
    unittest.main()
