"""Bounded, authenticated connectivity check; never returns upstream content."""
import asyncio
import hmac
import os
import time

from aiohttp import ClientSession, ClientTimeout, web

_last_check = 0.0


async def probe(request):
    global _last_check
    token = os.getenv('DOWNLOADER_TOKEN', '')
    if not token or not hmac.compare_digest(request.headers.get('Authorization', ''), 'Bearer ' + token):
        raise web.HTTPUnauthorized()
    now = time.monotonic()
    if now - _last_check < 60:
        raise web.HTTPTooManyRequests()
    _last_check = now
    payload = {'videoId': 'z9A1Wf695sQ', 'context': {'client': {
        'clientName': 'WEB', 'clientVersion': '2.20260928.01.00', 'hl': 'it'}}}
    try:
        async with ClientSession(timeout=ClientTimeout(total=15)) as session:
            async with session.post('https://www.youtube.com/youtubei/v1/player',
                                    json=payload, allow_redirects=False) as response:
                body = (await response.content.read(131072)).lower()
                return web.json_response({'http_status': response.status,
                    'automated_traffic': b'automated queries' in body,
                    'unusual_traffic': b'unusual traffic' in body})
    except (asyncio.TimeoutError, OSError):
        return web.json_response({'error': 'upstream_unavailable'}, status=502)
