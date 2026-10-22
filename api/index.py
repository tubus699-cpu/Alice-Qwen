import json
import os
import requests
from http.server import BaseHTTPRequestHandler

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

TRACKS = {
    "тест": {
        "url": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3",
        "title": "Тестовая музыка",
    },
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

SYSTEM_PROMPT = (
    "Твое имя — Квен (Qwen). Ты передовой искусственный интеллект, голосовой"
    " помощник и добрый друг.\n"
    "СТРОГОЕ ПРАВИЛО: Ты НИКОГДА не называешь себя Алисой. Ты НЕ Алиса и не"
    " имеешь к ней отношения. Если спрашивают «Кто ты?» — ты искусственный"
    " интеллект Квен.\n\n"
    "ПРАВИЛА ОЗВУЧКИ:\n"
    "1. Никогда не используй списки, звездочки (*), решетки (#) и эмодзи —"
    " текст зачитывается вслух через динамик колонки, говори естественной живой"
    " речью.\n\n"
    "РЕЖИМЫ РЕЧИ И СМЕНА СТИЛЯ:\n"
    "1. СТИЛЬ ПО УМОЛЧАНИЮ: Если нет особых указаний, отвечай емко, просто и"
    " понятно для ребенка — ровно 1–3 предложения.\n"
    "2. АДАПТАЦИЯ (ПРИОРИТЕТ): Если пользователь явно просит сменить манеру"
    " речи (например: «говори длинно», «объясни подробно и в деталях»,"
    " «расскажи длинную сказку», «говори как пират», «отвечай стихами» и т.п.)"
    " — ТЫ ОБЯЗАН БЕЗОГОВОРОЧНО ПОДЧИНИТЬСЯ. В этом случае отменяй ограничение"
    " в 1–3 предложения и говори именно так и столько, сколько попросил"
    " собеседник."
)


def pick_best_active_model(api_key):
  try:
    res = requests.get(
        "https://api.groq.com/openai/v1/models",
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=1.5,
    )
    if res.status_code == 200:
      models_data = res.json().get("data", [])
      chat_ids = [
          m["id"]
          for m in models_data
          if not any(
              bad in m["id"].lower()
              for bad in ["whisper", "guard", "embed", "safeguard", "tool"]
          )
      ]
      for mid in chat_ids:
        if "qwen" in mid.lower():
          return mid
      for mid in chat_ids:
        if "llama" in mid.lower():
          return mid
      if chat_ids:
        return chat_ids[0]
  except Exception:
    pass
  return "llama-3.3-70b-versatile"


class handler(BaseHTTPRequestHandler):

  def do_POST(self):
    content_length = int(self.headers.get("Content-Length", 0))
    post_data = self.rfile.read(content_length)
    body = json.loads(post_data.decode("utf-8"))

    user_text = body.get("request", {}).get("command", "").lower().strip()
    response_payload = {}

    if body.get("session", {}).get("new", False) or not user_text:
      response_payload = {
          "text": (
              "Привет! На связи искусственный интеллект Квен. Спроси меня о чем"
              " угодно или назови песенку!"
          ),
          "end_session": False,
      }

    elif any(word in user_text for word in ["стоп", "хватит", "пауза"]):
      response_payload = {
          "text": "Останавливаю воспроизведение.",
          "directives": {"audio_player": {"action": "Stop"}},
          "end_session": False,
      }

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

      else:
        if not GROQ_API_KEY:
          answer = "В настройках Vercel не найден GROQ_API_KEY."
        else:
          active_model = pick_best_active_model(GROQ_API_KEY)
          try:
            groq_resp = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
                json={
                    "model": active_model,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_text},
                    ],
                    "max_tokens": 400,
                    "temperature": 0.7,
                },
                timeout=3.5,
            )

            if groq_resp.status_code == 200:
              answer = groq_resp.json()["choices"][0]["message"]["content"]
            else:
              answer = (
                  f"Сбой {active_model} ({groq_resp.status_code}):"
                  f" {groq_resp.text[:120]}"
              )
          except Exception as e:
            answer = f"Ошибка связи: {str(e)}"

        response_payload = {"text": answer, "end_session": False}

    self.send_response(200)
    self.send_header("Content-Type", "application/json")
    self.end_headers()
    self.wfile.write(
        json.dumps({"response": response_payload, "version": "1.0"}).encode(
            "utf-8"
        )
    )
