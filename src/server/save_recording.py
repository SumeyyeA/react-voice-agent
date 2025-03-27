import os 
import subprocess
from starlette.requests import Request
from starlette.responses import JSONResponse 

async def save_recording(request: Request):
    form = await request.form()
    audio_file = form["recording"]
    filename = audio_file.filename

    # "recordings" klasörünü oluştur (zaten varsa hata vermez)
    os.makedirs("recordings", exist_ok=True)

    # Dosya yolunu oluştur ve kaydet
    save_path = os.path.join("recordings", filename)
    with open(save_path, "wb") as f:
        f.write(await audio_file.read())

    # ffmpeg ile yüksek kaliteli dosyaya dönüştürme (aynı dosya üzerine yazılarak):
    temp_path = os.path.join("recordings", "temp_" + filename)
    command = [
        "ffmpeg",
        "-y",             # otomatik olarak üzerine yaz
        "-i", save_path,
        "-ar", "48000",   # örnekleme hızı: 48000 Hz
        "-ac", "2",       # stereo (2 kanal)
        "-b:a", "192k",   # ses bitrate: 192 kbps
        temp_path
    ]
    try:
        subprocess.run(command, check=True)
        # Geçici dosyayı orijinal dosya adıyla yeniden adlandırarak üzerine yazıyoruz.
        os.replace(temp_path, save_path)
        message = f"Kayıt başarıyla kaydedildi ve yüksek kaliteli dosya üzerine yazıldı: {save_path}"
    except subprocess.CalledProcessError as e:
        message = f"Kayıt kaydedildi ancak ffmpeg dönüşümünde hata oluştu: {e}"
    except Exception as ex:
        message = f"Kayıt kaydedildi ancak dosya üzerine yazılırken hata oluştu: {ex}"

    return JSONResponse({
        "status": "success",
        "message": message
    })
