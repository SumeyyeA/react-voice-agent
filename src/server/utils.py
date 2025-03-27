from typing import AsyncIterator
from starlette.websockets import WebSocket
import webrtcvad


async def websocket_stream(websocket: WebSocket) -> AsyncIterator[str]:
    while True:
        data = await websocket.receive_text()
        yield data

vad = webrtcvad.Vad(3)

def is_speech(audio_bytes: bytes, sample_rate: int = 16000) -> bool:

    frame_duration = 0.02  # 20ms
    frame_size = int(sample_rate * frame_duration) * 2  # 2 byte per sample
    if len(audio_bytes) < frame_size:
        return False
    frame = audio_bytes[:frame_size]
    if len(frame) != frame_size:
        return False
    return vad.is_speech(frame, sample_rate)

