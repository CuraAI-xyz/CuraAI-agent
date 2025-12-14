import wave
import av
import io
from app.config.settings import settings

def webm_bytes_to_wav(webm_bytes: bytes, rate: int = None) -> io.BytesIO:
    """Convierte bytes de WebM a formato WAV"""
    if rate is None:
        rate = settings.AUDIO_SAMPLE_RATE
    
    try:
        container = av.open(io.BytesIO(webm_bytes), mode="r", format="webm")
        audio_stream = next((s for s in container.streams if s.type == "audio"), None)
        if audio_stream is None:
            raise RuntimeError("No se encontró stream de audio en el WebM.")

        resampler = av.audio.resampler.AudioResampler(format="s16", layout="mono", rate=rate)
        pcm_chunks = []

        for packet in container.demux(audio_stream):
            try:
                for frame in packet.decode():
                    out = resampler.resample(frame)
                    if not out: 
                        continue
                    frames = out if isinstance(out, list) else [out]
                    for f in frames:
                        arr = f.to_ndarray() 
                        if arr.ndim == 2: 
                            arr = arr[0]      
                        pcm_chunks.append(arr.tobytes())
            except Exception as decode_error:
                # Ignorar errores de decodificación de frames individuales
                print(f"Warning: Error decodificando frame: {decode_error}")
                continue

        out = resampler.resample(None)
        if out:
            frames = out if isinstance(out, list) else [out]
            for f in frames:
                arr = f.to_ndarray()
                if arr.ndim == 2: 
                    arr = arr[0]
                pcm_chunks.append(arr.tobytes())

        container.close()

        if not pcm_chunks:
            raise RuntimeError("No se pudo decodificar ningún frame de audio del WebM.")

        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)   
            wf.setframerate(rate)
            wf.writeframes(b"".join(pcm_chunks))
        
        wav_buffer.seek(0)
        wav_buffer.name = "audio.wav" 
        return wav_buffer
    
    except Exception as e:
        error_msg = f"Error decodificando WebM/Opus: {e}"
        print(error_msg)
        raise RuntimeError(error_msg) from e

