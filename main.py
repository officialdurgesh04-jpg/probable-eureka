import os
import tempfile
from pathlib import Path
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
    return {'mode': 'free-only', 'local_model_ready': False}

def remove_file(path):
    try: os.remove(path)
    except FileNotFoundError: pass

@app.post('/api/convert')
async def convert(audio: UploadFile = File(...), voice_choice: str = 'default', conversion_mode: str = 'speech'):
    if conversion_mode not in {'speech', 'singing'}:
        raise HTTPException(400, 'Mode valid nahi hai.')
    if conversion_mode == 'singing':
        raise HTTPException(503, 'Free singing conversion model abhi install nahi hai.')
    data = await audio.read(MAX_BYTES + 1)
    await audio.close()
    if not data:
        raise HTTPException(400, 'Audio file khaali hai.')
    if len(data) > MAX_BYTES:
        raise HTTPException(413, 'Audio 20 MB se badi hai.')
    # Do not call any paid third-party API in free-only mode.
    raise HTTPException(503, 'Free-only mode active hai. Paid API call nahi ki gayi. Local open-source voice-conversion model abhi deploy karna baaki hai.')
