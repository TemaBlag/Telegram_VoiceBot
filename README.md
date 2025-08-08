# 🎙️ Voice Assistant Telegram Bot

A fast and lightweight **Telegram bot** that can:
- 🎙 **Transcribe** voice messages into text (powered by OpenAI Whisper)
- 🎵 **Convert** voice messages to MP3
- 🗣 **Generate speech** from text (Text-to-Speech using Google TTS)
- 🌍 **Work in multiple languages** with auto-detection

**Live bot available here:** [@AudioScriptorBot](https://t.me/AudioScriptorBot)

🚀 Deployed on [Railway](https://railway.app/) for fast and reliable hosting.

All processing is done **privately** and **on-the-fly** – no files are stored after sending the result.

---

## ✨ Features
- **Voice → Text**: Accurate transcription using Whisper
- **Voice → MP3**: Convert voice/audio messages into high-quality MP3 files
- **Text → Speech**: Generate natural-sounding speech from your text
- **Language Detection**: Choose your language or let the bot detect it automatically
- **No Storage**: Files are deleted immediately after processing to save disk space

---

## 🛠 Commands

| Command | Description |
|---------|-------------|
| `/start` | Start the bot and see menu |
| `/help` | Show usage instructions |
| `/info` | Learn more about the bot |
| `/v2t` | Voice → Text mode |
| `/mp3` | Voice → MP3 mode |
| `/t2s` | Text → Speech mode |
| `/lang` | Change recognition language |

---

## 📸 Bot Menu

The bot supports inline menu buttons for:
- ℹ️ About
- ❓ Help
- 🎙️ Voice to Text
- 🎵 Voice to MP3
- 🗣️ Text to Speech
- 🌍 Language Selection

---

## ⚡ Performance Notes
- Default model is **`base`** for balanced speed and accuracy
- You can use `tiny` for maximum speed or `small`/`medium` for higher accuracy (slower)
- All audio is processed in-memory and deleted after sending the result
- Large audio files are rejected if over `MAX_FILE_MB`

---

## 🧩 Tech Stack
- **[Telethon](https://github.com/LonamiWebs/Telethon)** — Telegram API client
- **[OpenAI Whisper](https://github.com/openai/whisper)** — Speech recognition
- **[pydub](https://github.com/jiaaro/pydub)** — Audio format conversion
- **[gTTS](https://github.com/pndurette/gTTS)** — Text-to-Speech
- **[langdetect](https://github.com/Mimino666/langdetect)** — Language detection

---

## 📝 License
This project is licensed under the MIT License.

---

### 💡 Ideas & Contributions
Pull requests, feature requests, and suggestions are welcome!  
If you build something cool with this bot — let me know! 🚀
