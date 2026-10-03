"""Private API for the bot, plus a free GPU runtime diagnostic."""
import asyncio
import hmac
import os
from pathlib import Path
import subprocess
import tempfile
import time
import uuid

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import FileResponse
import gradio as gr
import requests
import spaces

from backend import download, video_id

TOKEN = os.environ.get('NELLO_TOKEN', '')
if len(TOKEN) < 32:
    raise RuntimeError('NELLO_TOKEN must be configured as a Space secret')
SERVER = Path('/tmp/nello-bgutil/server')
if not (SERVER / 'build/main.js').exists():
    subprocess.run(['git', 'clone', '--depth', '1', '--branch', '2.0.0',
                    'https://github.com/Brainicism/bgutil-ytdlp-pot-provider.git', str(SERVER.parent)],
                   check=True, timeout=60)
    subprocess.run(['npm', 'ci'], cwd=SERVER, check=True, timeout=120)
    subprocess.run(['npx', 'tsc'], cwd=SERVER, check=True, timeout=60)
provider = subprocess.Popen(['node', 'build/main.js', '--port', '4416'], cwd=SERVER,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
for _ in range(150):
    try:
        if requests.get('http://127.0.0.1:4416/ping', timeout=1).ok:
            break
    except requests.RequestException:
        pass
    time.sleep(.1)
else:
    raise RuntimeError('YouTube token provider did not start')

app = FastAPI()
artifacts = {}
lock = asyncio.Lock()


def authenticate(request):
    if not hmac.compare_digest(request.headers.get('x-nello-token', ''), TOKEN):
        raise HTTPException(401, 'Unauthorized')


def cleanup():
    for ident, item in list(artifacts.items()):
        if time.monotonic() - item['created'] > 600:
            artifacts.pop(ident)['directory'].cleanup()


@app.get('/api/healthz')
async def health():
    return {'status': 'ok', 'provider': provider.poll() is None}


@app.post('/api/youtube')
async def extract(request: Request):
    authenticate(request)
    data = await request.body()
    if len(data) > 2 * 1024 * 1024:
        raise HTTPException(413, 'Request too large')
    import json
    body = json.loads(data)
    if not video_id(body.get('url', '')) or body.get('kind', 'video') not in ('video', 'audio'):
        raise HTTPException(400, 'Invalid request')
    cookies = body.get('cookies', '')
    if not isinstance(cookies, str) or len(cookies.encode()) > 512 * 1024:
        raise HTTPException(400, 'Invalid cookies')
    async with lock:
        cleanup()
        if len(artifacts) >= 8:
            raise HTTPException(429, 'Media queue full')
        directory = tempfile.TemporaryDirectory(prefix='youtube_')
        try:
            result, path = await asyncio.to_thread(download, body['url'], cookies, directory.name,
                                                  body.get('kind', 'video'), body.get('max_duration', 180))
            if path is None:
                directory.cleanup()
                return result
            ident = str(uuid.uuid4())
            artifacts[ident] = {'directory': directory, 'path': path, 'created': time.monotonic()}
            return dict(result, artifact=ident)
        except Exception as exc:
            directory.cleanup()
            message = str(exc).lower()
            issue = ('access_check' if 'bot' in message or 'sign in' in message or 'reload' in message
                     else 'download_failed')
            # Expose only fixed diagnostic codes, never URLs, cookies or raw exceptions.
            import re
            known = ('youtube_media_identity', 'youtube_duration_unknown', 'youtube_duration_changed',
                     'youtube_invalid_media_file', 'youtube_missing_media_stream')
            code = next((value for value in known if value in message), None)
            status = re.search(r'http error (\d{3})', message)
            code = code or ('http_' + status[1] if status else
                            'format_unavailable' if 'format' in message and 'available' in message else
                            'media_unavailable' if 'unavailable' in message else 'extractor_failure')
            return {'success': False, 'auth_issue': issue, 'error_code': code,
                    'error': 'YouTube download unavailable'}


@app.get('/api/media/{ident}')
async def media(ident: str, request: Request):
    authenticate(request)
    cleanup()
    if ident not in artifacts:
        raise HTTPException(404, 'Not found')
    return FileResponse(artifacts[ident]['path'])


@app.delete('/api/media/{ident}')
async def remove(ident: str, request: Request):
    authenticate(request)
    item = artifacts.pop(ident, None)
    if item:
        item['directory'].cleanup()
    return {'ok': True}


@spaces.GPU(duration=10)
def gpu_diagnostic(key):
    if not hmac.compare_digest(key, TOKEN):
        return 'Unauthorized'
    import torch
    return torch.cuda.get_device_name(0)


with gr.Blocks(title='Nello YouTube Media') as demo:
    gr.Markdown('NelloTok YouTube media service. The bot uses a private authenticated API.')
    gr.Interface(gpu_diagnostic, gr.Textbox(type='password'), 'text', api_name='gpu_diagnostic')
demo.launch(server_name='0.0.0.0', server_port=7860, prevent_thread_lock=True, ssr_mode=False)
# Keep the Gradio launch hooks required by ZeroGPU, and expose authenticated
# CPU endpoints before Gradio's frontend routes.
demo.app.router.routes[0:0] = app.router.routes
demo.block_thread()
