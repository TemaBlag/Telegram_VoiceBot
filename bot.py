import os
import io
import asyncio
import logging
import tempfile
import textwrap

import nest_asyncio
from faster_whisper import WhisperModel
from gtts import gTTS
from langdetect import detect
from telethon import TelegramClient, events
from telethon.tl.custom import Button
from pydub import AudioSegment

# ===== Config =====
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base")
MAX_FILE_MB = float(os.getenv("MAX_FILE_MB", "25"))  

# ===== Init =====
nest_asyncio.apply()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

client = TelegramClient('bot', API_ID, API_HASH)
# Faster-Whisper runs on CPU by default; we set compute_type for memory efficiency
model = WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8")

user_settings = {}  # {user_id: {"mode": "v2t"/"mp3"/"t2s", "lang": "en"/"auto"/...}}

# ===== Utils =====
def _get_media_size_mb(event) -> float:
    try:
        if event.message and event.message.media and getattr(event.message.media, "document", None):
            size = event.message.media.document.size or 0
            return size / (1024 * 1024)
        if event.message and event.voice:
            # voice как правило тоже document
            return _get_media_size_mb(type("E", (), {"message": event.message}))
    except Exception:
        pass
    return 0.0

async def _download_to_bytes(event) -> bytes:
    bio = io.BytesIO()
    await client.download_media(event.media, file=bio)
    bio.seek(0)
    return bio.getvalue()

async def _export_audio_bytes(input_bytes: bytes, out_format: str) -> bytes:
    def _work():
        audio = AudioSegment.from_file(io.BytesIO(input_bytes))
        out = io.BytesIO()
        audio.export(out, format=out_format)
        return out.getvalue()
    return await asyncio.to_thread(_work)

async def _whisper_transcribe(wav_bytes: bytes, lang: str) -> str:
    def _work():
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_wav:
            tmp_wav.write(wav_bytes)
            tmp_wav.flush()
            path = tmp_wav.name
        try:
            # faster-whisper returns (segments, info)
            if lang == "auto":
                segments, _ = model.transcribe(path)
            else:
                segments, _ = model.transcribe(path, language=lang)
            text = " ".join(seg.text for seg in segments).strip()
            return text
        finally:
            try:
                os.remove(path)
            except Exception:
                pass
    return await asyncio.to_thread(_work)

async def _gtts_synthesize(text: str, lang_hint: str) -> bytes:
    def _detect_lang():
        try:
            return detect(text)
        except Exception:
            return "en"

    def _work():
        lang = _detect_lang() if lang_hint == "auto" else lang_hint
        tts = gTTS(text=text, lang=lang)
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp_mp3:
            tts.save(tmp_mp3.name)
            tmp_mp3.flush()
            tmp_path = tmp_mp3.name
        try:
            with open(tmp_path, "rb") as f:
                data = f.read()
        finally:
            try:
                os.remove(tmp_path)
            except Exception:
                pass
        return lang, data

    return await asyncio.to_thread(_work)

def _too_large(event) -> bool:
    size_mb = _get_media_size_mb(event)
    return size_mb and size_mb > MAX_FILE_MB

# ===== Handlers =====
async def main():
    await client.start(bot_token=BOT_TOKEN)

    @client.on(events.NewMessage(pattern='/start'))
    async def start_handler(event):
        await event.respond(
            "🏠 **Welcome to your personal voice assistant!**\n\n"
            "Choose an option below to get started 👇",
            buttons=[
                [Button.inline("ℹ️ About", b"info"), Button.inline("❓ Help", b"help")],
                [Button.inline("🎙️ Voice → Text", b"v2t"), Button.inline("🎵 Voice → MP3", b"mp3")],
                [Button.inline("🗣️ Text → Speech", b"t2s"), Button.inline("🌍 Language", b"lang")]
            ],
            parse_mode="Markdown"
        )

    @client.on(events.NewMessage(pattern='/help'))
    async def help_handler(event):
        text = textwrap.dedent(
            "❓ **How to use this bot:**\n\n"
            "/info – Info about this bot\n"
            "/v2t – Send voice, get text\n"
            "/mp3 – Convert voice to MP3\n"
            "/t2s – Convert your text to speech\n"
            "/lang – Set language for recognition\n"
        )
        await event.respond(text, parse_mode="Markdown")

    @client.on(events.NewMessage(pattern='/info'))
    async def info_handler(event):
        text = textwrap.dedent("""\
            ℹ️ **About this bot**
    
            This bot uses **OpenAI Whisper** to transcribe voice messages and **gTTS** to synthesize speech.
            No permanent files: everything is processed in temp and deleted right away.
        """)
        await event.respond(text, parse_mode="Markdown")

    @client.on(events.NewMessage(pattern='/lang'))
    async def lang_handler(event):
        await event.respond(
            "🌍 Choose recognition language:",
            buttons=[
                [Button.inline("🇺🇸 English", b"lang_en"), Button.inline("🇷🇺 Russian", b"lang_ru")],
                [Button.inline("🇫🇷 French", b"lang_fr"), Button.inline("🇩🇪 German", b"lang_de")],
                [Button.inline("🇪🇸 Spanish", b"lang_es"), Button.inline("🧠 Auto-detect", b"lang_auto")]
            ]
        )

    @client.on(events.NewMessage(pattern='/v2t'))
    async def v2t_prompt(event):
        user_settings.setdefault(event.sender_id, {})["mode"] = "v2t"
        await event.respond("🎙️ Send a voice message and I’ll transcribe it.")

    @client.on(events.NewMessage(pattern='/mp3'))
    async def mp3_prompt(event):
        user_settings.setdefault(event.sender_id, {})["mode"] = "mp3"
        await event.respond("🎵 Send a voice/audio message to convert to MP3.")
    
    @client.on(events.NewMessage(pattern='/t2s'))
    async def t2s_prompt(event):
        user_settings.setdefault(event.sender_id, {})["mode"] = "t2s"
        await event.respond("🗣️ Send text and I will turn it into speech.")

    async def handle_voice_transcription(event):
        if _too_large(event):
            return await event.respond(f"⚠️ File is larger than {MAX_FILE_MB} MB. Please send a shorter one.")
        sender_id = event.sender_id
        lang = user_settings.get(sender_id, {}).get("lang", "auto")

        await event.respond(f"🔍 Transcribing (language: {lang})...")
        try:
            in_bytes = await _download_to_bytes(event)
            wav_bytes = await _export_audio_bytes(in_bytes, "wav")
            text = await _whisper_transcribe(wav_bytes, lang)
            await event.respond(f"📝 Transcription:\n{text if text else '(empty)'}")
        except Exception as e:
            logging.exception("Transcription error")
            await event.respond("❌ Failed to transcribe.")

    async def handle_mp3_conversion(event):
        if _too_large(event):
            return await event.respond(f"⚠️ File is larger than {MAX_FILE_MB} MB. Please send a shorter one.")
        try:
            in_bytes = await _download_to_bytes(event)
            mp3_bytes = await _export_audio_bytes(in_bytes, "mp3")

            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp_out:
                tmp_out.write(mp3_bytes)
                tmp_out.flush()
                tmp_path = tmp_out.name
            try:
                await event.respond("🎵 Here's your MP3:", file=tmp_path)
            finally:
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass
        except Exception:
            logging.exception("MP3 conversion error")
            await event.respond("❌ Failed to convert to MP3.")

    async def handle_text_to_speech(event):
        sender_id = event.sender_id
        lang = user_settings.get(sender_id, {}).get("lang", "auto")
        text = (event.text or "").strip()
        if not text:
            return await event.respond("✍️ Send some text first.")

        await event.respond("🎧 Generating speech...")
        try:
            detected_lang, mp3_bytes = await _gtts_synthesize(text, lang)
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp_out:
                tmp_out.write(mp3_bytes)
                tmp_out.flush()
                tmp_path = tmp_out.name
            try:
                await event.respond(
                    f"🔊 Language: **{detected_lang.upper()}**",
                    file=tmp_path,
                    parse_mode="Markdown"
                )
            finally:
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass
        except Exception:
            logging.exception("TTS error")
            await event.respond("❌ Failed to generate audio.")

    @client.on(events.NewMessage())
    async def message_handler(event):
        if event.text and event.text.startswith("/"):
            return

        sender_id = event.sender_id
        mode = user_settings.get(sender_id, {}).get("mode", "v2t")

        if event.voice or event.audio:
            if mode == "mp3":
                await handle_mp3_conversion(event)
            else:
                await handle_voice_transcription(event)
        elif event.text:
            if mode == "t2s":
                await handle_text_to_speech(event)
            else:
                await event.respond("💡 Send a voice message for transcription, or /t2s to synthesize your text.")

    @client.on(events.CallbackQuery)
    async def callback_handler(event):
        sender_id = event.sender_id
        data = event.data.decode("utf-8")

        if data.startswith("lang_"):
            lang_code = data.split("_", 1)[1]
            user_settings.setdefault(sender_id, {})["lang"] = lang_code
            if lang_code == "auto":
                await event.respond("🧠 Language detection set to **automatic**", parse_mode="Markdown")
            else:
                await event.respond(f"🌍 Language set to **{lang_code.upper()}**", parse_mode="Markdown")
        elif data == "info":
            await client.dispatch_event(events.NewMessage(pattern="/info"), event)
            await event.answer()
        elif data == "help":
            await client.dispatch_event(events.NewMessage(pattern="/help"), event)
            await event.answer()
        elif data == "v2t":
            user_settings.setdefault(sender_id, {})["mode"] = "v2t"
            await event.respond("🎙 Voice-to-text mode activated. Send a voice message.")
        elif data == "mp3":
            user_settings.setdefault(sender_id, {})["mode"] = "mp3"
            await event.respond("🎵 MP3 conversion mode activated. Send a voice message.")
        elif data == "t2s":
            user_settings.setdefault(sender_id, {})["mode"] = "t2s"
            await event.respond("🗣 Text-to-speech mode activated. Send a text message.")
        elif data == "lang":
            await lang_handler(event)

    logging.info("Bot is up and running...")
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
