import os
import nest_asyncio
import logging
import whisper
import textwrap
from gtts import gTTS
from langdetect import detect

from telethon import TelegramClient, events
from telethon.tl.custom import Button
from pydub import AudioSegment

api_id = int(os.getenv("API_ID"))
api_hash = os.getenv("API_HASH")
bot_token = os.getenv("BOT_TOKEN")

nest_asyncio.apply()
logging.basicConfig(level=logging.INFO)

client = TelegramClient('bot', api_id, api_hash)
model = whisper.load_model("base")

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# Store user settings in memory (can be moved to Redis/db)
user_settings = {}

async def main():
    await client.start(bot_token=bot_token)

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
    
            Welcome to your personal voice assistant 🤖🎙️
    
            This bot uses **OpenAI Whisper** to accurately transcribe your voice messages into text, and **gTTS** (Google Text-to-Speech) to turn your written text into natural-sounding audio.
    
            💡 **Main features:**
            - 🎙️ **Voice to Text** in multiple languages
            - 🎵 **Voice to MP3** conversion
            - 🗣️ **Text to Speech** generator
            - 🌍 **Language selection** on the fly
            - 💾 **Fast and private** — works in DMs
    
            Ideal for journaling, interviews, notes, podcasts, accessibility — or just having fun.
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
        await event.respond("🎙️ Please send your voice message now.")

    @client.on(events.NewMessage(pattern='/mp3'))
    async def mp3_prompt(event):
        user_settings.setdefault(event.sender_id, {})["mode"] = "mp3"
        await event.respond("🎵 Please send a voice or audio message to convert to MP3.")
    
    @client.on(events.NewMessage(pattern='/t2s'))
    async def t2s_prompt(event):
        user_settings.setdefault(event.sender_id, {})["mode"] = "t2s"
        await event.respond("🗣️ Send text and I will turn it into speech..")

    async def handle_voice_transcription(event):
        sender_id = event.sender_id
        lang = user_settings.get(sender_id, {}).get("lang", "auto")
    
        file_path = os.path.join(DOWNLOAD_DIR, f"{event.id}.ogg")
        await client.download_media(event.media, file=file_path)
    
        wav_path = file_path.replace(".ogg", ".wav")
        AudioSegment.from_file(file_path).export(wav_path, format="wav")
    
        await event.respond(f"🔍 Transcribing (language: {lang})...")
        try:
            result = model.transcribe(wav_path) if lang == "auto" else model.transcribe(wav_path, language=lang)
            transcription = result["text"].strip()
            await event.respond(f"📝 Transcription:\n{transcription}")
        except Exception as e:
            logging.error(f"Transcription error: {e}")
            await event.respond("❌ Failed to transcribe.")

    async def handle_mp3_conversion(event):
        file_path = os.path.join(DOWNLOAD_DIR, f"{event.id}.ogg")
        await client.download_media(event.media, file=file_path)
    
        mp3_path = file_path.replace(".ogg", ".mp3")
        AudioSegment.from_file(file_path).export(mp3_path, format="mp3")
    
        await event.respond("🎵 Here's your MP3:", file=mp3_path)

    async def handle_text_to_speech(event):
        sender_id = event.sender_id
        lang = user_settings.get(sender_id, {}).get("lang", "auto")
        text = event.text.strip()
    
        await event.respond("🎧 Generating speech...")
    
        try:
            if lang == "auto":
                try:
                    tts_lang = detect(text)
                    logging.info(f"Detected text language: {tts_lang}")
                except Exception as e:
                    logging.warning(f"Language detection failed: {e}")
                    tts_lang = "en"
            else:
                tts_lang = lang
    
            tts = gTTS(text=text, lang=tts_lang)
            tts_path = os.path.join(DOWNLOAD_DIR, f"{event.id}.mp3")
            tts.save(tts_path)
    
            await event.respond(f"🔊 Language: **{tts_lang.upper()}**", file=tts_path, parse_mode="Markdown")
        except Exception as e:
            logging.error(f"TTS error: {e}")
            await event.respond("❌ Failed to generate audio.")

    @client.on(events.NewMessage())
    async def message_handler(event):
        sender_id = event.sender_id
        mode = user_settings.get(sender_id, {}).get("mode", "v2t")
        
        if event.voice or event.audio:
            if mode == "mp3":
                await handle_mp3_conversion(event)
            else:
                await handle_voice_transcription(event)
    
        elif event.text and not event.text.startswith("/"):
            await handle_text_to_speech(event)
   

    @client.on(events.CallbackQuery)
    async def callback_handler(event):
        sender_id = event.sender_id
        data = event.data.decode("utf-8")

        if data.startswith("lang_"):
            lang_code = data.split("_")[1]
            user_settings.setdefault(sender_id, {})["lang"] = lang_code
            if lang_code == "auto":
                await event.respond("🧠 Language detection set to **automatic**", parse_mode="Markdown")
            else:
                await event.respond(f"🌍 Language set to **{lang_code.upper()}**", parse_mode="Markdown")
                
        elif data == "info":  
            await info_handler(event)

        elif data == "help":
            await help_handler(event) 

        elif data == "v2t":
            user_settings.setdefault(sender_id, {})["mode"] = "v2t"
            await event.respond("🎙 Voice-to-text mode activated. Please send a voice message.")
    
        elif data == "mp3":
            user_settings.setdefault(sender_id, {})["mode"] = "mp3"
            await event.respond("🎵 MP3 conversion mode activated. Please send a voice message.")
    
        elif data == "t2s":
            user_settings.setdefault(sender_id, {})["mode"] = "t2s"
            await event.respond("🗣 Text-to-speech mode activated. Please send a text message.")

        elif data == "lang":
            await lang_handler(event)

    print("Bot is up and running...")
    await client.run_until_disconnected()
    
await main()