import wave
import av
import io
from app.config.settings import settings

def webm_bytes_to_wav(webm_bytes: bytes, rate: int = None) -> io.BytesIO:
    """Convierte bytes de WebM a formato WAV"""
    if rate is None:
        rate = settings.AUDIO_SAMPLE_RATE
    
    # Validar que el buffer tenga datos
    if not webm_bytes or len(webm_bytes) == 0:
        raise ValueError("Buffer de audio vacío")
    
    # Validar tamaño mínimo (WebM necesita al menos ~100 bytes para headers básicos)
    if len(webm_bytes) < 100:
        raise ValueError(f"Buffer de audio demasiado pequeño: {len(webm_bytes)} bytes (mínimo ~100 bytes)")
    
    # Validar headers de WebM (EBML: 0x1A 0x45 0xDF 0xA3)
    # WebM puede empezar con diferentes variantes, pero generalmente tiene estos bytes
    webm_signatures = [
        b'\x1a\x45\xdf\xa3',  # EBML header estándar
        b'\x1a\x45\xdf\xa7',  # Variante EBML
    ]
    
    is_valid_webm = any(webm_bytes.startswith(sig) for sig in webm_signatures)
    if not is_valid_webm:
        # Intentar buscar el header más adelante (algunos streams pueden tener prefijos)
        found_header = False
        for sig in webm_signatures:
            if sig in webm_bytes[:1024]:  # Buscar en los primeros 1KB
                found_header = True
                break
        
        if not found_header:
            # Log para debugging pero intentar procesar de todas formas
            # (algunos codecs pueden tener headers diferentes)
            print(f"Warning: No se encontró header WebM estándar en los primeros bytes. Tamaño buffer: {len(webm_bytes)} bytes")
            print(f"Primeros 20 bytes (hex): {webm_bytes[:20].hex()}")
    
    try:
        # Intentar abrir como WebM primero
        try:
            container = av.open(io.BytesIO(webm_bytes), mode="r", format="webm")
        except Exception as format_error:
            # Si falla con formato webm, intentar detección automática
            print(f"Warning: Error abriendo como WebM, intentando detección automática: {format_error}")
            try:
                container = av.open(io.BytesIO(webm_bytes), mode="r")
                print(f"Formato detectado automáticamente: {container.format.name if container.format else 'desconocido'}")
            except Exception as auto_error:
                raise RuntimeError(f"No se pudo abrir el contenedor de audio. Error WebM: {format_error}, Error auto-detección: {auto_error}")
        
        audio_stream = next((s for s in container.streams if s.type == "audio"), None)
        if audio_stream is None:
            raise RuntimeError("No se encontró stream de audio en el contenedor.")

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

