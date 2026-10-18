import os
import tempfile
from pathlib import Path
from urllib.parse import urlparse

import requests
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, Response

app = FastAPI(title='Awaaz AI')
BASE = Path(__file__).resolve().parent
MAX_BYTES = 20 * 1024 * 1024
# Configure this in Render when a compatible self-hosted RVC inference service is available.
VOICE_CONVERSION_URL = os.getenv('VOICE_CONVERSION_URL', '').strip()
VOICE_CONVERSION_TOKEN = os.getenv('VOICE_CONVERSION_TOKEN', '').strip()

@app.get('/', response_class=HTMLResponse)
def home():
    return (BASE / 'static' / 'index.html').read_text(encoding='utf-8')

@app.get('/api/status')
def status():
    configured = bool(VOICE_CONVERSION_URL)
    return {
        'mode': 'free-only',
        'local_model_ready': False,
        'conversion_backend_configured': configured,
        'message': 'Conversion backend configured.' if configured else 'AI conversion backend is not configured yet.'
    }

def _valid_backend_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in {'https', 'http'} and bool(parsed.netloc)

@app.post('/api/convert')
async def convert(
    audio: UploadFile = File(...),
    voice_choice: str = 'default',
    conversion_mode: str = 'speech'
):
    if conversion_mode not in {'speech', 'singing'}:
        raise HTTPException(400, 'Mode valid nahi hai.')
    if not VOICE_CONVERSION_URL or not _valid_backend_url(VOICE_CONVERSION_URL):
        raise HTTPException(503, 'AI voice conversion backend configure nahi hai. Render mein VOICE_CONVERSION_URL set karna zaroori hai.')
    data = await audio.read(MAX_BYTES + 1)
    filename = audio.filename or 'recording.wav'
    content_type = audio.content_type or 'application/octet-stream'
    await audio.close()
    if not data:
        raise HTTPException(400, 'Audio file khaali hai.')
    if len(data) > MAX_BYTES:
        raise HTTPException(413, 'Audio 20 MB se badi hai.')

    headers = {}
    if VOICE_CONVERSION_TOKEN:
        headers['Authorization'] = f'Bearer {VOICE_CONVERSION_TOKEN}'
    try:
        # The configured inference service must accept multipart fields `audio`,
        # `voice_choice`, and `conversion_mode`, and return converted audio bytes.
        upstream = requests.post(
            VOICE_CONVERSION_URL,
            files={'audio': (filename, data, content_type)},
            data={'voice_choice': voice_choice, 'conversion_mode': conversion_mode},
            headers=headers,
            timeout=(10, 240),
        )
    except requests.Timeout:
        raise HTTPException(504, 'Voice conversion service ne time par jawab nahi diya. Thodi der baad try karo.')
    except requests.RequestException:
        raise HTTPException(502, 'Voice conversion service se connection nahi ho paaya.')

    if upstream.status_code >= 400:
        detail = 'Voice conversion service conversion nahi kar paayi.'
        try:
            payload = upstream.json()
            detail = str(payload.get('detail') or payload.get('message') or detail)[:500]
        except ValueError:
            pass
        raise HTTPException(upstream.status_code if upstream.status_code < 500 else 502, detail)

    media_type = upstream.headers.get('content-type', 'audio/wav').split(';', 1)[0]
    if not media_type.startswith('audio/') and media_type != 'application/octet-stream':
        raise HTTPException(502, 'Backend ne audio file ke bajay invalid response diya.')
    return Response(
        content=upstream.content,
        media_type=media_type,
        headers={'Content-Disposition': 'attachment; filename="awaaz-ai-converted.wav"'}
    )
