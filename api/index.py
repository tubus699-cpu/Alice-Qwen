import base64
import json
import os
import re
import requests
import yt_dlp

# Настройки твоего репозитория
GITHUB_TOKEN = input("Вставь GitHub Token (ghp_...): ").strip()
REPO_OWNER = "tubus699-cpu"
REPO_NAME = "Alice-Qwen"
RELEASE_TAG = "v1.0-music"

# Список треков: ключевое слово для Алисы -> поисковый запрос на YouTube
TRACKS_TO_GET = [
    {
        "keyword": "морские животные",
        "title": "Малышарики — Морские животные",
        "query": "Малышарики Морские животные песня",
    },
    {
        "keyword": "таинственный тортоежка",
        "title": "Три Кота — Таинственный тортоежка",
        "query": "Три кота Таинственный тортоежка песня",
    },
    {
        "keyword": "умный дом",
        "title": "Три Кота — Умный дом",
        "query": "Три кота Умный дом песня",
    },
    {
        "keyword": "компот",
        "title": "Кукутики — На столе стоит компот",
        "query": "Кукутики На столе стоит компот",
    },
    {
        "keyword": "кузнечик",
        "title": "В траве сидел кузнечик",
        "query": "В траве сидел кузнечик песня детская",
    },
    {
        "keyword": "колобок",
        "title": "Сказка Колобок",
        "query": "Сказка Колобок аудиосказка",
    },
]

HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json",
}


def download_audio(query, output_filename):
  """Ищет на YouTube и скачивает чистую аудиодорожку AAC/M4A без перекодирования."""
  print(f"[1/4] Поиск и загрузка: {query}...")
  ydl_opts = {
      "format": "ba[ext=m4a]/bestaudio/best",
      "outtmpl": output_filename,
      "default_search": "ytsearch1:",
      "quiet": True,
      "no_warnings": True,
  }
  with yt_dlp.YoutubeDL(ydl_opts) as ydl:
    ydl.download([query])
  return output_filename


def get_or_create_release():
  """Находит или создает релиз на GitHub для хранения музыки."""
  print(f"[2/4] Подготовка GitHub Release ({RELEASE_TAG})...")
  url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/releases/tags/{RELEASE_TAG}"
  res = requests.get(url, headers=HEADERS)

  if res.status_code == 200:
    return res.json()["upload_url"].split("{")[0]

  # Если релиза нет — создаем новый
  create_url = (
      f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/releases"
  )
  payload = {
      "tag_name": RELEASE_TAG,
      "name": "Музыкальный каталог для Алисы",
      "body": "Прямые ссылки на аудиодорожки без подписки",
  }
  create_res = requests.post(create_url, headers=HEADERS, json=payload)
  if create_res.status_code != 201:
    raise RuntimeError(f"Ошибка создания релиза: {create_res.text}")
  return create_res.json()["upload_url"].split("{")[0]


def upload_to_release(upload_url, file_path, asset_name):
  """Заливает аудиофайл в GitHub Release и возвращает прямую ссылку."""
  print(f"[3/4] Загрузка файла {asset_name} в GitHub CDN...")
  with open(file_path, "rb") as f:
    upload_res = requests.post(
        f"{upload_url}?name={asset_name}",
        headers={
            "Authorization": f"token {GITHUB_TOKEN}",
            "Content-Type": "audio/mp4",
        },
        data=f,
    )

  if upload_res.status_code == 201:
    return upload_res.json()["browser_download_url"]
  elif upload_res.status_code == 422:
    # Файл уже существует
    return f"https://github.com/{REPO_OWNER}/{REPO_NAME}/releases/download/{RELEASE_TAG}/{asset_name}"
  else:
    raise RuntimeError(f"Ошибка загрузки ассета: {upload_res.text}")


def update_repo_code(new_tracks_dict):
  """Скачивает api/index.py с GitHub, заменяет TRACKS и пушит коммит."""
  print("[4/4] Автоматическое обновление api/index.py на GitHub...")
  url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/api/index.py"
  res = requests.get(url, headers=HEADERS)
  if res.status_code != 200:
    raise RuntimeError(f"Не удалось получить index.py: {res.text}")

  file_data = res.json()
  sha = file_data["sha"]
  current_code = base64.b64decode(file_data["content"]).decode("utf-8")

  # Форматируем новый словарь
  formatted_tracks = "TRACKS = " + json.dumps(
      new_tracks_dict, ensure_ascii=False, indent=4
  )

  # Заменяем блок TRACKS в коде
  updated_code = re.sub(
      r"TRACKS\s*=\s*\{.*?\n\}", formatted_tracks, current_code, flags=re.DOTALL
  )

  # Отправляем коммит прямо в ветку main
  commit_payload = {
      "message": "Авто-обновление аудиокаталога (real audio links)",
      "content": base64.b64encode(updated_code.encode("utf-8")).decode("utf-8"),
      "sha": sha,
  }
  put_res = requests.put(url, headers=HEADERS, json=commit_payload)
  if put_res.status_code in [200, 201]:
    print("\n ГОТОВО! Репозиторий обновлен.")
    print("Vercel подхватит изменения через 20 секунд.")
  else:
    print(f"\n Ошибка коммита: {put_res.text}")


def main():
  os.makedirs("temp_music", exist_ok=True)
  upload_url = get_or_create_release()
  new_tracks = {}

  for i, item in enumerate(TRACKS_TO_GET):
    safe_name = f"track_{i+1}.m4a"
    local_path = os.path.join("temp_music", safe_name)

    # 1. Скачиваем трек
    download_audio(item["query"], local_path)

    # 2. Заливаем в релиз
    direct_url = upload_to_release(upload_url, local_path, safe_name)

    # 3. Добавляем в каталог
    new_tracks[item["keyword"]] = {"url": direct_url, "title": item["title"]}

    # Удаляем временный файл с диска
    if os.path.exists(local_path):
      os.remove(local_path)

  # 4. Обновляем код в репозитории
  update_repo_code(new_tracks)


if __name__ == "__main__":
  main()
