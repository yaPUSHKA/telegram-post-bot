import requests
import os

print("🚀 Запуск скрипта...")

# Убедимся, что папка templates существует
os.makedirs("templates", exist_ok=True)

# Ссылка на картинку
url = "https://i.imgur.com/3XvbmFu.png"

# Скачиваем картинку
response = requests.get(url)

# Проверка успешности запроса
print(f"Статус ответа: {response.status_code}")

if response.status_code == 200:
    with open("templates/drake.png", "wb") as f:
        f.write(response.content)
    print("✅ Картинка успешно скачана в templates/drake.png")
else:
    print(f"❌ Ошибка при скачивании. Код ответа: {response.status_code}")
