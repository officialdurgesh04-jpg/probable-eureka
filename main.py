import os
import tempfile
from pathlib import Path
import requests
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, FileResponse
from starlette.background import BackgroundTask

app = FastAPI(title='Awaaz AI')
BASE = Path(__file__).resolve().parent
MAX_BYTES = 20 * 1024 * 1024

@app.get('/', response_class=HTMLResponse)
def home():
    return (BASE / 'static' / 'index.html').read_text(encoding='utf-8')

@app.get('/api/status')
def status():
    return {'api_key_configured': bool(os.getenv('HUME_API_KEY')), 'target_voice_configured': bool(os.getenv('HUME_TARGET_VOICE_ID')), 'original_voice_configured': bool(os.getenv('HUME_ORIGINAL_VOICE_ID'))}

def remove_file(path):
    try: os.remove(path)
    except FileNotFoundError: pass

@app.post('/api/convert')
async def convert(audio: UploadFile = File(...), voice_choice: str = 'default', conversion_mode: str = 'speech'):
    if conversion_mode not in {'speech', 'singing'}:
        raise HTTPException(400, 'Mode valid nahi hai.')
    if conversion_mode == 'singing':
        raise HTTPException(503, 'Singing conversion abhi enabled nahi hai. Current Hume voice-conversion endpoint singing ke liye reliable support guarantee nahi karta; singing-compatible model configure hone ke baad yeh mode enable hoga. Filhaal Speech mode use karo.')
    key = os.getenv('HUME_API_KEY', '').strip()
    if voice_choice == 'original':
        voice = os.getenv('HUME_ORIGINAL_VOICE_ID', '').strip()
        provider = os.getenv('HUME_ORIGINAL_VOICE_PROVIDER', 'CUSTOM_VOICE').strip().upper()
        if not voice:
            raise HTTPException(503, 'Aapki sample voice abhi Hume mein custom voice ke roop mein configure nahi hui. HUME_ORIGINAL_VOICE_ID set karna hoga.')
    elif voice_choice == 'default':
        voice = os.getenv('HUME_TARGET_VOICE_ID', '').strip()
        provider = os.getenv('HUME_TARGET_VOICE_PROVIDER', 'HUME_AI').strip().upper()
    else:
        raise HTTPException(400, 'Voice option valid nahi hai.')
    if not key:
        raise HTTPException(503, 'Hume AI API key missing hai. Render Environment mein HUME_API_KEY add karna hoga.')
    if not voice:
        raise HTTPException(503, 'Target voice ID missing hai. Render Environment mein HUME_TARGET_VOICE_ID add karna hoga.')
    if provider not in {'HUME_AI', 'CUSTOM_VOICE'}:
        raise HTTPException(503, 'HUME_TARGET_VOICE_PROVIDER HUME_AI ya CUSTOM_VOICE hona chahiye.')
    data = await audio.read(MAX_BYTES + 1)
    await audio.close()
    if not data: raise HTTPException(400, 'Audio file khaali hai.')
    if len(data) > MAX_BYTES: raise HTTPException(413, 'Audio 20 MB se badi hai.')
    name = Path(audio.filename or 'recording.webm').name
    ext = Path(name).suffix.lower()
    if ext not in {'.webm','.wav','.mp3','.m4a','.ogg','.aac','.flac','.mp4'}: ext = '.webm'
    src = out = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as f:
            f.write(data); src = f.name
        with open(src, 'rb') as f:
            r = requests.post('https://api.hume.ai/v0/tts/voice_conversion/file', headers={'X-Hume-Api-Key': key}, files={'audio': (name, f, audio.content_type or 'application/octet-stream')}, data={'voice[id]': voice, 'voice[provider]': provider}, timeout=(15,180))
        if r.status_code >= 400: raise HTTPException(502, 'Hume voice service error (' + str(r.status_code) + '): ' + r.text[:400])
        if not r.content: raise HTTPException(502, 'AI service ne audio return nahi kiya.')
        with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as f:
            f.write(r.content); out = f.name
        return FileResponse(out, media_type='audio/wav', filename='awaaz-ai-converted.wav', background=BackgroundTask(remove_file, out))
    except requests.Timeout: raise HTTPException(504, 'Conversion timeout hua. Chhoti recording try karo.')
    except requests.RequestException as e: raise HTTPException(502, 'AI service se connection nahi hua: ' + type(e).__name__)
    finally:
        if src: remove_file(src)
