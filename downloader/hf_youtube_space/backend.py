"""Bounded authenticated-service extraction; never accept non-YouTube URLs."""
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
from urllib.parse import parse_qs, urlsplit

import yt_dlp

MAX_BYTES = 100 * 1024 * 1024
MAX_DURATION = 180


def video_id(url):
    try:
        parts = urlsplit(str(url))
        port = parts.port
    except ValueError:
        return None
    if parts.scheme != 'https' or parts.username or parts.password or port not in (None, 443):
        return None
    host = (parts.hostname or '').lower()
    if host in ('youtu.be', 'www.youtu.be'):
        ident = parts.path.strip('/').split('/')[0]
    elif host in ('youtube.com', 'www.youtube.com', 'm.youtube.com', 'music.youtube.com'):
        segments = parts.path.strip('/').split('/')
        ident = (segments[1] if len(segments) >= 2 and segments[0] in ('shorts', 'embed', 'live')
                 else parse_qs(parts.query).get('v', [''])[0])
    else:
        return None
    return ident if re.fullmatch(r'[A-Za-z0-9_-]{11}', ident) else None


def check_info(info, expected):
    if not isinstance(info, dict) or info.get('id') != expected or info.get('_type') in ('playlist', 'multi_video'):
        raise ValueError('youtube_media_identity')
    duration = float(info.get('duration') or 0)
    if not math.isfinite(duration) or duration <= 0 or info.get('is_live') or info.get('live_status') == 'is_live':
        raise ValueError('youtube_duration_unknown')
    return duration <= MAX_DURATION


class QuietLogger:
    def debug(self, message):
        pass
    def warning(self, message):
        pass
    def error(self, message):
        pass


def caption_info(ydl, info):
    """Inline tracks so Render need not fetch captions using another IP."""
    selected = [{k: f[k] for k in ('language', 'acodec') if k in f}
                for f in info.get('requested_formats', [])]
    audio_languages = {f.get('language') for f in selected if f.get('acodec') not in (None, 'none') and f.get('language')}
    source = next(iter(audio_languages)) if len(audio_languages) == 1 else info.get('language')
    auto = info.get('automatic_captions') or {}
    if not source:
        original = [k.split('-')[0] for k in auto if k.endswith('-orig')]
        if len(set(original)) == 1:
            source = original[0]
    metadata = {'language': source, 'duration': info.get('duration'), 'requested_formats': selected}
    for group_name in ('subtitles', 'automatic_captions'):
        tracks = {}
        for code, candidates in (info.get(group_name) or {}).items():
            base = code.lower().split('-')[0]
            if base not in {'it', str(source or '').split('-')[0]}:
                continue
            for track in sorted(candidates or [], key=lambda t: t.get('ext') != 'vtt')[:2]:
                if track.get('ext') not in ('vtt', 'srt', 'json3') or not track.get('url'):
                    continue
                try:
                    with ydl.urlopen(track['url']) as response:
                        data = response.read(512 * 1024 + 1)
                    if len(data) <= 512 * 1024:
                        tracks[code] = [{'ext': track['ext'], 'data': data.decode('utf-8')}]
                        break
                except Exception:
                    continue
            if len(tracks) >= 4 or sum(len(t[0]['data']) for t in tracks.values()) > 768 * 1024:
                break
        metadata[group_name] = tracks
    return metadata


def download(url, cookies, directory, kind='video', max_duration=180):
    ident = video_id(url)
    if not ident:
        raise ValueError('invalid_youtube_url')
    directory = Path(directory).resolve()
    cookie_path = directory / 'cookies.txt'
    if cookies:
        cookie_path.write_text(cookies, encoding='utf-8')
        os.chmod(cookie_path, 0o600)
    options = {
        'format': ('bestaudio[language^=it]/bestaudio/best' if kind == 'audio' else
                   'best[language^=it]/bestvideo+bestaudio[language^=it]/best[ext=mp4][acodec!=none]/bestvideo+bestaudio/best'),
        'format_sort': ['res:480'], 'outtmpl': str(directory / '%(id)s.%(ext)s'),
        'merge_output_format': 'mp4', 'noplaylist': True, 'max_filesize': MAX_BYTES,
        'socket_timeout': 15, 'retries': 1, 'fragment_retries': 1,
        'concurrent_fragment_downloads': 1,
        'js_runtimes': {'node': {'path': shutil.which('node')}},
        'extractor_args': {'youtube': {'player_client': ['mweb'], 'fetch_pot': ['always']},
                           'youtubepot-bgutilhttp': {'base_url': ['http://127.0.0.1:4416']}},
        'logger': QuietLogger(),
    }
    if cookies:
        options['cookiefile'] = str(cookie_path)
    if kind == 'audio':
        options['postprocessors'] = [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3',
                                      'preferredquality': '128'}]
    try:
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info('https://www.youtube.com/watch?v=' + ident, download=False)
            if not check_info(info, ident) or float(info['duration']) > min(MAX_DURATION, int(max_duration)):
                return {'success': False, 'skip_long': True}, None
            info = ydl.process_ie_result(info, download=True)
            if not check_info(info, ident):
                raise ValueError('youtube_duration_changed')
            candidates = [p for p in directory.iterdir() if p.stem == ident and p.suffix.lower()
                          in ('.mp4', '.webm', '.mkv', '.m4a', '.opus', '.mp3')]
            if len(candidates) != 1 or not 0 < candidates[0].stat().st_size <= MAX_BYTES:
                raise ValueError('youtube_invalid_media_file')
            path = candidates[0]
            # Confirm that the resulting file has the required streams.
            probe = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'stream=codec_type',
                                    '-of', 'csv=p=0', str(path)], capture_output=True, text=True, timeout=15)
            streams = probe.stdout.splitlines()
            if probe.returncode or (kind == 'audio' and 'audio' not in streams) or (kind != 'audio' and 'video' not in streams):
                raise ValueError('youtube_missing_media_stream')
            result = {'success': True, 'type': 'audio' if kind == 'audio' else 'video',
                      'platform': 'youtube', 'id': ident, 'url': 'https://www.youtube.com/watch?v=' + ident,
                      'title': info.get('title', 'YouTube'), 'uploader': info.get('uploader', ''),
                      'duration': info['duration'], 'size': path.stat().st_size,
                      'suffix': path.suffix, 'source_info': caption_info(ydl, info) if kind != 'audio' else {}}
            return result, path
    finally:
        cookie_path.unlink(missing_ok=True)
