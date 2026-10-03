"""Retrieve YouTube media from the private free Hugging Face service."""
import asyncio
import os
from pathlib import Path
from urllib.parse import urlsplit
import uuid

import aiohttp

from cookie_health import read_content
from youtube_duration import video_id

MAX_BYTES = 100 * 1024 * 1024


async def download_youtube(url, directory, kind='video', max_duration=180):
    expected = video_id(url)
    base = os.environ['HF_YOUTUBE_URL'].rstrip('/')
    endpoint = urlsplit(base)
    if endpoint.scheme != 'https' or not (endpoint.hostname or '').endswith('.hf.space'):
        raise ValueError('invalid Hugging Face service URL')
    if not expected:
        return {'success': False, 'error': 'Link YouTube non valido.'}
    headers = {'X-Nello-Token': os.environ['HF_YOUTUBE_TOKEN']}
    timeout = aiohttp.ClientTimeout(total=240, sock_connect=20, sock_read=180)
    artifact = None
    path = None
    done = False
    async with aiohttp.ClientSession(headers=headers, timeout=timeout) as session:
        try:
            for _ in range(30):
                try:
                    async with session.get(base + '/api/healthz', timeout=aiohttp.ClientTimeout(total=10)) as response:
                        if response.status == 200 and (await response.json()).get('provider'):
                            break
                except (aiohttp.ClientError, asyncio.TimeoutError, ValueError):
                    pass
                await asyncio.sleep(3)
            else:
                raise RuntimeError('Hugging Face service unavailable')
            body = {'url': url, 'kind': kind, 'cookies': read_content('youtube'),
                    'max_duration': min(180, int(max_duration))}
            async with session.post(base + '/api/youtube', json=body) as response:
                response.raise_for_status()
                result = await response.json()
            if not result.get('success'):
                return result
            artifact = str(uuid.UUID(result['artifact']))
            duration = float(result.get('duration', 0))
            if result.get('id') != expected or not 0 < duration <= min(180, int(max_duration)):
                raise ValueError('unexpected YouTube media')
            suffix = result['suffix']
            if suffix not in ('.mp4', '.webm', '.mkv', '.m4a', '.opus', '.mp3'):
                raise ValueError('invalid YouTube media suffix')
            expected_size = int(result['size'])
            if not 0 < expected_size <= MAX_BYTES:
                raise ValueError('YouTube media too large')
            path = Path(directory) / ('youtube_' + uuid.uuid4().hex + suffix)
            size = 0
            with path.open('wb') as output:
                async with session.get(base + '/api/media/' + artifact) as response:
                    response.raise_for_status()
                    async for chunk in response.content.iter_chunked(256 * 1024):
                        size += len(chunk)
                        if size > expected_size or size > MAX_BYTES:
                            raise ValueError('YouTube transfer exceeds limit')
                        output.write(chunk)
            if size != expected_size:
                raise ValueError('incomplete YouTube transfer')
            result.pop('artifact', None)
            result['file_path'] = str(path)
            done = True
            return result
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError, KeyError, RuntimeError):
            return {'success': False, 'error': 'YouTube non ha completato il download. Riprova tra poco.'}
        finally:
            if path and not done:
                path.unlink(missing_ok=True)
            if artifact:
                try:
                    async with session.delete(base + '/api/media/' + artifact,
                                              timeout=aiohttp.ClientTimeout(total=10)):
                        pass
                except (aiohttp.ClientError, asyncio.TimeoutError):
                    pass
