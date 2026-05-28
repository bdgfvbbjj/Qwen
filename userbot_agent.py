#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Telegram Userbot Agent
Полнофункциональный юзербот для управления аккаунтом Telegram
с возможностью выполнения задач в файловой системе.

Авторизация: при первом запуске будет запрошен номер телефона и код подтверждения.
"""

import os
import asyncio
import subprocess
import shutil
from pathlib import Path
from pyrogram import Client, filters
from pyrogram.types import Message, Document
from pyrogram.errors import FloodWait, SessionPasswordNeeded

# Конфигурация
API_ID = int(os.getenv("API_ID", "0"))  # Замените на ваш API ID
API_HASH = os.getenv("API_HASH", "")     # Замените на ваш API Hash
BOT_WORKDIR = Path(__file__).parent.resolve()  # Рабочая директория бота

# Создание клиента
app = Client(
    "userbot_agent",
    api_id=API_ID,
    api_hash=API_HASH,
    workdir=BOT_WORKDIR
)

# Список администраторов, которые могут управлять ботом (по user_id)
# Оставьте пустым [], чтобы разрешить только себе
ALLOWED_USERS = []


def is_allowed(user_id: int) -> bool:
    """Проверка, имеет ли пользователь доступ к боту"""
    if not ALLOWED_USERS:
        return True  # Если список пуст, разрешаем только владельцу сессии
    return user_id in ALLOWED_USERS


@app.on_message(filters.command("start") & filters.me)
async def start_command(client: Client, message: Message):
    """Команда /start - информация о боте"""
    response = """
🤖 **Telegram Userbot Agent**

Я могу управлять вашим аккаунтом Telegram и выполнять задачи в файловой системе.

**Доступные команды:**

📁 **Файловые операции:**
• `/create_file <name> [content]` - создать файл
• `/read_file <path>` - прочитать файл
• `/delete_file <path>` - удалить файл
• `/list_files [path]` - список файлов в директории
• `/send_file <path>` - отправить файл в чат

💻 **Выполнение команд:**
• `/exec <command>` - выполнить команду в shell
• `/python <code>` - выполнить Python код

👤 **Управление аккаунтом:**
• `/me` - информация о вашем аккаунте
• `/chats` - список чатов
• `/send_msg <chat_id> <text>` - отправить сообщение
• `/forward <from_chat> <msg_id> <to_chat>` - переслать сообщение

🔧 **Прочее:**
• `/help` - подробная справка
• `/status` - статус бота

**Примеры:**
`/create_file test.txt "Hello World"`
`/exec ls -la`
`/send_file /path/to/file.pdf`
`/send_msg @username Привет!`
"""
    await message.edit(response)


@app.on_message(filters.command("help") & filters.me)
async def help_command(client: Client, message: Message):
    """Команда /help - подробная справка"""
    response = """
📚 **Подробная справка по командам**

**ФАЙЛОВЫЕ ОПЕРАЦИИ:**

`/create_file <имя> [содержимое]`
  Создает файл в рабочей директории бота.
  Пример: `/create_file notes.txt "Важные заметки"`

`/read_file <путь>`
  Читает содержимое файла и отправляет в чат.
  Пример: `/read_file config.json`

`/delete_file <путь>`
  Удаляет файл. Будьте осторожны!
  Пример: `/delete_file temp.txt`

`/list_files [путь]`
  Показывает список файлов в директории.
  Пример: `/list_files` или `/list_files /home/user`

`/send_file <путь>`
  Отправляет файл в текущий чат.
  Пример: `/send_file document.pdf`

**ВЫПОЛНЕНИЕ КОМАНД:**

`/exec <команда>`
  Выполняет shell команду и возвращает результат.
  Пример: `/exec pwd` или `/exec git status`

`/python <код>`
  Выполняет Python код и возвращает результат.
  Пример: `/python print(2+2)`

**УПРАВЛЕНИЕ АККАУНТОМ:**

`/me`
  Показывает информацию о вашем аккаунте.

`/chats [limit]`
  Показывает список последних чатов.
  Пример: `/chats 10`

`/send_msg <чат_id> <текст>`
  Отправляет сообщение в указанный чат.
  Пример: `/send_msg @username Привет!`
  Пример: `/send_msg 123456789 Текст сообщения`

`/forward <из_чата> <id_сообщения> <в_чат>`
  Пересылает сообщение из одного чата в другой.

**БЕЗОПАСНОСТЬ:**
⚠️ Бот может выполнять любые команды от вашего имени!
⚠️ Используйте только с доверенными источниками.
⚠️ Не передавайте session файл третьим лицам.
"""
    await message.edit(response)


@app.on_message(filters.command("me") & filters.me)
async def me_command(client: Client, message: Message):
    """Команда /me - информация об аккаунте"""
    user = await client.get_me()
    response = f"""
👤 **Информация об аккаунте:**

ID: `{user.id}`
Имя: {user.first_name}
Фамилия: {user.last_name or 'Не указана'}
Username: @{user.username or 'Не установлен'}
Телефон: `{user.phone_number or 'Скрыт'}`
Bio: {user.bio or 'Не указано'}
Статус: {'Premium' if user.is_premium else 'Обычный'}
Бот: {'Да' if user.is_bot else 'Нет'}
"""
    await message.edit(response)


@app.on_message(filters.command("create_file") & filters.me)
async def create_file_command(client: Client, message: Message):
    """Команда /create_file - создание файла"""
    try:
        parts = message.text.split(maxsplit=2)
        if len(parts) < 2:
            await message.edit("❌ Использование: `/create_file <имя> [содержимое]`")
            return
        
        filename = parts[1]
        content = parts[2] if len(parts) > 2 else ""
        
        filepath = BOT_WORKDIR / filename
        
        # Защита от выхода за пределы рабочей директории
        try:
            filepath.resolve().relative_to(BOT_WORKDIR.resolve())
        except ValueError:
            await message.edit("❌ Ошибка: нельзя создавать файлы вне рабочей директории!")
            return
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        
        await message.edit(f"✅ Файл создан: `{filepath}`\nРазмер: {len(content)} символов")
    except Exception as e:
        await message.edit(f"❌ Ошибка: {e}")


@app.on_message(filters.command("read_file") & filters.me)
async def read_file_command(client: Client, message: Message):
    """Команда /read_file - чтение файла"""
    try:
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            await message.edit("❌ Использование: `/read_file <путь>`")
            return
        
        filepath = Path(parts[1])
        
        # Защита от чтения файлов вне рабочей директории
        try:
            filepath.resolve().relative_to(BOT_WORKDIR.resolve())
        except ValueError:
            await message.edit("❌ Ошибка: нельзя читать файлы вне рабочей директории!")
            return
        
        if not filepath.exists():
            await message.edit("❌ Файл не найден!")
            return
        
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Если файл слишком большой, отправляем как документ
        if len(content) > 4000:
            await message.edit(f"📄 Файл слишком большой ({len(content)} символов). Отправляю как документ...")
            await client.send_document(message.chat.id, str(filepath))
        else:
            response = f"📄 **{filepath.name}**:\n\n```\n{content}\n```"
            await message.edit(response)
    except Exception as e:
        await message.edit(f"❌ Ошибка: {e}")


@app.on_message(filters.command("delete_file") & filters.me)
async def delete_file_command(client: Client, message: Message):
    """Команда /delete_file - удаление файла"""
    try:
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            await message.edit("❌ Использование: `/delete_file <путь>`")
            return
        
        filepath = Path(parts[1])
        
        # Защита от удаления файлов вне рабочей директории
        try:
            filepath.resolve().relative_to(BOT_WORKDIR.resolve())
        except ValueError:
            await message.edit("❌ Ошибка: нельзя удалять файлы вне рабочей директории!")
            return
        
        if not filepath.exists():
            await message.edit("❌ Файл не найден!")
            return
        
        filepath.unlink()
        await message.edit(f"✅ Файл удален: `{filepath}`")
    except Exception as e:
        await message.edit(f"❌ Ошибка: {e}")


@app.on_message(filters.command("list_files") & filters.me)
async def list_files_command(client: Client, message: Message):
    """Команда /list_files - список файлов"""
    try:
        parts = message.text.split(maxsplit=1)
        target_path = BOT_WORKDIR
        if len(parts) > 1:
            target_path = Path(parts[1])
            # Защита от просмотра директорий вне рабочей
            try:
                target_path.resolve().relative_to(BOT_WORKDIR.resolve())
            except ValueError:
                await message.edit("❌ Ошибка: нельзя просматривать директории вне рабочей!")
                return
        
        if not target_path.exists():
            await message.edit("❌ Директория не найдена!")
            return
        
        if not target_path.is_dir():
            await message.edit("❌ Это не директория!")
            return
        
        items = []
        for item in target_path.iterdir():
            icon = "📁" if item.is_dir() else "📄"
            size = ""
            if item.is_file():
                size = f" ({item.stat().st_size} B)"
            items.append(f"{icon} `{item.name}`{size}")
        
        if not items:
            response = f"📂 **{target_path}**:\n\nПусто"
        else:
            response = f"📂 **{target_path}**:\n\n" + "\n".join(items)
        
        await message.edit(response)
    except Exception as e:
        await message.edit(f"❌ Ошибка: {e}")


@app.on_message(filters.command("send_file") & filters.me)
async def send_file_command(client: Client, message: Message):
    """Команда /send_file - отправка файла"""
    try:
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            await message.edit("❌ Использование: `/send_file <путь>`")
            return
        
        filepath = Path(parts[1])
        
        # Защита от отправки файлов вне рабочей директории
        try:
            filepath.resolve().relative_to(BOT_WORKDIR.resolve())
        except ValueError:
            await message.edit("❌ Ошибка: нельзя отправлять файлы вне рабочей директории!")
            return
        
        if not filepath.exists():
            await message.edit("❌ Файл не найден!")
            return
        
        if not filepath.is_file():
            await message.edit("❌ Это не файл!")
            return
        
        await message.edit(f"📤 Отправляю файл: `{filepath.name}`...")
        await client.send_document(message.chat.id, str(filepath))
        await message.delete()
    except Exception as e:
        await message.edit(f"❌ Ошибка: {e}")


@app.on_message(filters.command("exec") & filters.me)
async def exec_command(client: Client, message: Message):
    """Команда /exec - выполнение shell команды"""
    try:
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            await message.edit("❌ Использование: `/exec <команда>`")
            return
        
        command = parts[1]
        
        # Блокировка опасных команд
        dangerous_patterns = ['rm -rf /', 'mkfs', 'dd if=', ':(){:|:&};:', '> /dev/sda']
        for pattern in dangerous_patterns:
            if pattern in command:
                await message.edit("❌ Опасная команда заблокирована!")
                return
        
        await message.edit(f"⏳ Выполняю: `{command}`...")
        
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            cwd=BOT_WORKDIR,
            timeout=60
        )
        
        output = ""
        if result.stdout:
            output += f"**STDOUT:**\n```\n{result.stdout}\n```\n"
        if result.stderr:
            output += f"**STDERR:**\n```\n{result.stderr}\n```\n"
        if not output:
            output = "✅ Команда выполнена (нет вывода)"
        
        output += f"\n**Код возврата:** `{result.returncode}`"
        
        if len(output) > 4000:
            # Сохраняем вывод в файл и отправляем
            output_file = BOT_WORKDIR / "exec_output.txt"
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(output)
            await message.edit("📄 Вывод слишком большой. Отправляю как файл...")
            await client.send_document(message.chat.id, str(output_file))
            output_file.unlink()
        else:
            await message.edit(output)
    except subprocess.TimeoutExpired:
        await message.edit("❌ Таймаут выполнения команды (60 сек)")
    except Exception as e:
        await message.edit(f"❌ Ошибка: {e}")


@app.on_message(filters.command("python") & filters.me)
async def python_command(client: Client, message: Message):
    """Команда /python - выполнение Python кода"""
    try:
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            await message.edit("❌ Использование: `/python <код>`")
            return
        
        code = parts[1]
        
        await message.edit("⏳ Выполняю Python код...")
        
        # Создаем временный файл с кодом
        temp_file = BOT_WORKDIR / "temp_exec.py"
        with open(temp_file, 'w', encoding='utf-8') as f:
            f.write(code)
        
        result = subprocess.run(
            ['python', str(temp_file)],
            capture_output=True,
            text=True,
            cwd=BOT_WORKDIR,
            timeout=60
        )
        
        temp_file.unlink()  # Удаляем временный файл
        
        output = ""
        if result.stdout:
            output += f"**Вывод:**\n```\n{result.stdout}\n```\n"
        if result.stderr:
            output += f"**Ошибки:**\n```\n{result.stderr}\n```\n"
        if not output:
            output = "✅ Код выполнен (нет вывода)"
        
        output += f"\n**Код возврата:** `{result.returncode}`"
        
        if len(output) > 4000:
            output_file = BOT_WORKDIR / "python_output.txt"
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(output)
            await message.edit("📄 Вывод слишком большой. Отправляю как файл...")
            await client.send_document(message.chat.id, str(output_file))
            output_file.unlink()
        else:
            await message.edit(output)
    except subprocess.TimeoutExpired:
        await message.edit("❌ Таймаут выполнения кода (60 сек)")
    except Exception as e:
        await message.edit(f"❌ Ошибка: {e}")


@app.on_message(filters.command("chats") & filters.me)
async def chats_command(client: Client, message: Message):
    """Команда /chats - список чатов"""
    try:
        parts = message.text.split()
        limit = int(parts[1]) if len(parts) > 1 else 20
        
        await message.edit(f"⏳ Загружаю список чатов (лимит: {limit})...")
        
        chats_list = []
        async for dialog in client.get_dialogs(limit=limit):
            chat_type = "👥" if dialog.chat.type in ["group", "supergroup"] else "💬"
            if dialog.chat.type == "private":
                chat_type = "👤"
            elif dialog.chat.type == "channel":
                chat_type = "📢"
            
            name = dialog.chat.title or dialog.chat.first_name or "Unknown"
            chat_id = dialog.chat.id
            username = f"@{dialog.chat.username}" if dialog.chat.username else ""
            
            chats_list.append(f"{chat_type} `{name}` ({chat_id}) {username}")
        
        if not chats_list:
            await message.edit("❌ Чаты не найдены!")
            return
        
        response = "📋 **Ваши чаты:**\n\n" + "\n".join(chats_list)
        
        if len(response) > 4000:
            output_file = BOT_WORKDIR / "chats_list.txt"
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(response)
            await message.edit("📄 Список слишком большой. Отправляю как файл...")
            await client.send_document(message.chat.id, str(output_file))
            output_file.unlink()
        else:
            await message.edit(response)
    except Exception as e:
        await message.edit(f"❌ Ошибка: {e}")


@app.on_message(filters.command("send_msg") & filters.me)
async def send_msg_command(client: Client, message: Message):
    """Команда /send_msg - отправка сообщения"""
    try:
        parts = message.text.split(maxsplit=2)
        if len(parts) < 3:
            await message.edit("❌ Использование: `/send_msg <chat_id> <текст>`")
            return
        
        chat_identifier = parts[1]
        text = parts[2]
        
        # Пытаемся определить тип идентификатора
        if chat_identifier.startswith('@'):
            chat_id = chat_identifier
        else:
            try:
                chat_id = int(chat_identifier)
            except ValueError:
                chat_id = chat_identifier
        
        await client.send_message(chat_id, text)
        await message.edit(f"✅ Сообщение отправлено в `{chat_identifier}`")
    except Exception as e:
        await message.edit(f"❌ Ошибка: {e}")


@app.on_message(filters.command("status") & filters.me)
async def status_command(client: Client, message: Message):
    """Команда /status - статус бота"""
    import sys
    
    response = f"""
🤖 **Статус Userbot Agent**

✅ Бот активен и работает
📂 Рабочая директория: `{BOT_WORKDIR}`
🐍 Python версия: {sys.version.split()[0]}
📱 Pyrogram версия: 2.0.106

**Использование памяти:**
- Доступно для выполнения команд
- Может создавать/читать/удалять файлы
- Может отправлять сообщения от вашего имени
"""
    await message.edit(response)


async def main():
    """Основная функция запуска"""
    print("=" * 50)
    print("🤖 Telegram Userbot Agent")
    print("=" * 50)
    print(f"📂 Рабочая директория: {BOT_WORKDIR}")
    print()
    print("⚠️  ВАЖНО:")
    print("1. При первом запуске потребуется авторизация")
    print("2. Введите номер телефона в международном формате")
    print("3. Введите код подтверждения из Telegram")
    print("4. Если включена 2FA, введите пароль")
    print()
    print("📝 Для остановки нажмите Ctrl+C")
    print("=" * 50)
    
    await app.start()
    print("\n✅ Бот успешно запущен!")
    print("📩 Используйте команду /start в любом чате для получения справки")
    
    # Ожидание событий
    await asyncio.Event().wait()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n🛑 Бот остановлен пользователем")
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
