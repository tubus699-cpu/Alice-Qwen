import json
import os
import requests
from http.server import BaseHTTPRequestHandler

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

# Каталог любимых треков и сказок (ссылки заменим на постоянные позже)
TRACKS = {
    "морские животные": {
        "url": "https://example.com/morskie.mp3",
        "title": "Малышарики — Морские животные",
    },
    "таинственный тортоежка": {
        "url": "https://example.com/tortoedka.mp3",
        "title": "Три Кота — Таинственный тортоежка",
    },
    "умный дом": {
        "url": "https://example.com/umny_dom.mp3",
        "title": "Три Кота — Умный дом",
    },
    "компот": {
        "url": "https://example.com/kompot.mp3",
        "title": "Кукутики — На столе стоит компот",
    },
    "кузнечик": {
        "url": "https://example.com/kuznechik.mp3",
        "title": "В траве сидел кузнечик",
    },
    "колобок": {
        "url": "https://example.com/kolobok.mp3",
        "title": "Сказка Колобок",
    },
    "кот лиса и петух": {
        "url": "https://example.com/kot_lisa.mp3",
        "title": "Сказка Кот, петух и лиса",
    },
}


class handler(BaseHTTPRequestHandler):

  def do_POST(self):
    content_length = int(self.headers.get("Content-Length", 0))
    post_data = self.rfile.read(content_length)
    body = json.loads(post_data.decode("utf-8"))

    user_text = body.get("request", {}).get("command", "").lower().strip()
    response_payload = {}

    # 1. Первый запуск навыка
    if body.get("session", {}).get("new", False) or not user_text:
      response_payload = {
          "text": (
              "Привет! Я твой умный помощник. Спроси меня о чем угодно или"
              " попроси включить песенку!"
          ),
          "end_session": False,
      }

    # 2. Остановка музыки
    elif any(word in user_text for word in ["стоп", "хватит", "пауза"]):
      response_payload = {
          "text": "Останавливаю воспроизведение.",
          "directives": {"audio_player": {"action": "Stop"}},
          "end_session": False,
      }

    # 3. Поиск трека в каталоге
    else:
      matched_track = None
      for keyword, data in TRACKS.items():
        if keyword in user_text:
          matched_track = data
          break

      if matched_track:
        response_payload = {
            "text": f"Включаю: {matched_track['title']}!",
            "directives": {
                "audio_player": {
                    "action": "Play",
                    "item": {
                        "stream": {
                            "url": matched_track["url"],
                            "offset_ms": 0,
                            "token": matched_track["title"],
                        },
                        "metadata": {
                            "title": matched_track["title"],
                            "sub_title": "Любимые треки",
                        },
                    },
                }
            },
            "end_session": False,
        }

      # 4. Если трек не найден — отвечает нейросеть
      else:
        try:
          if not GROQ_API_KEY:
            raise ValueError("В Vercel не найдена переменная GROQ_API_KEY")

          groq_resp = requests.post(
              "https://api.groq.com/openai/v1/chat/completions",
              headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
              json={
                  "model": "llama-3.1-8b-instant",
                  "messages": [
                      {
                          "role": "system",
                          "content": (
                              "Ты дружелюбный детский голосовой помощник."
                              " Отвечай живо, интересно, простыми словами для"
                              " ребенка. Не пиши списков и спецсимволов. Длина"
                              " ответа — 1-3 предложения."
                          ),
                      },
                      {"role": "user", "content": user_text},
                  ],
                  "max_tokens": 150,
                  "temperature": 0.7,
              },
              timeout=3.5,
          )

          if groq_resp.status_code != 200:
            raise ValueError(
                f"Ошибка API ({groq_resp.status_code}): {groq_resp.text[:100]}"
            )

          answer = groq_resp.json()["choices"][0]["message"]["content"]
        except Exception as e:
          answer = f"Сбой: {str(e)}"

        response_payload = {"text": answer, "end_session": False}

    self.send_response(200)
    self.send_header("Content-Type", "application/json")
    self.end_headers()
    self.wfile.write(
        json.dumps({"response": response_payload, "version": "1.0"}).encode(
            "utf-8"
        )
    )
