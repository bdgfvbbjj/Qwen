--- telegram_userbot_agent/userbot_agent.py (原始)


+++ telegram_userbot_agent/userbot_agent.py (修改后)
#!/usr/bin/env python3
"""
Telegram Userbot AI Agent with Gemini
Полноценный AI-агент для управления аккаунтом Telegram

ВОЗМОЖНОСТИ:
✅ Отвечает на ЛЮБЫЕ вопросы используя Gemini AI
✅ Выполняет ЛЮБЫЕ задачи в рабочей директории
✅ Анализирует голосовые сообщения, фото, видео через Gemini
✅ Создает, читает, удаляет файлы по команде
✅ Выполняет shell и Python команды
✅ Отправляет файлы по запросу
✅ Действует как человек от вашего имени

НАСТРОЙКА:
1. Получите Telegram credentials на my.telegram.org
2. Получите Gemini API ключ на aistudio.google.com/app/apikey
3. Установите переменные окружения:
   export TG_API_ID=ваш_api_id
   export TG_API_HASH=ваш_api_hash
   export TG_PHONE=+79991234567
   export GEMINI_API_KEY=ваш_key
   export GEMINI_MODELS=gemini-1.5-pro,gemini-2.0-flash-exp,gemini-1.5-flash  # порядок: от лучших к худшим
4. Запустите: python userbot_agent.py

АВТОМАТИЧЕСКОЕ ПЕРЕКЛЮЧЕНИЕ МОДЕЛЕЙ:
- При исчерпании лимита одной модели агент автоматически переключается на другую
- Используется один API ключ, но разные модели
- Порядок моделей: ОТ ЛУЧШИХ К ХУДШИМ (сначала gemini-1.5-pro → потом gemini-2.0-flash-exp → затем gemini-1.5-flash)
- Порядок задается в переменной GEMINI_MODELS
"""

import os
import sys
import asyncio
import logging
import json
import re
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any, Union

# Telegram
from telethon import TelegramClient, events
from telethon.tl.types import Message, User, Chat, DocumentAttributeAudio, DocumentAttributeVideo
from telethon.utils import pack_bot_file_id

# Gemini
import google.generativeai as genai
from google.generativeai import GenerativeModel
from google.generativeai.types import ContentDict, PartDict

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Рабочая директория (где расположен скрипт)
WORK_DIR = Path(__file__).parent.resolve()
os.chdir(WORK_DIR)
logger.info(f"📂 Рабочая директория: {WORK_DIR}")

# Конфигурация
class Config:
    # Telegram credentials (получить на my.telegram.org)
    API_ID = int(os.getenv("TG_API_ID", "0"))
    API_HASH = os.getenv("TG_API_HASH", "")
    PHONE = os.getenv("TG_PHONE", "")
    SESSION_NAME = os.getenv("TG_SESSION_NAME", "userbot_ai_agent")

    # Один Gemini API key
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

    # Модели Gemini для переключения (при лимите одной переключаемся на другую)
    # Порядок: от лучших к худшим (сначала мощные, потом быстрые/дешевые)
    GEMINI_MODELS = [model.strip() for model in os.getenv("GEMINI_MODELS", "gemini-1.5-pro,gemini-2.0-flash-exp,gemini-1.5-flash").split(",") if model.strip()]

    # Разрешенные пользователи (кто может управлять ботом)
    ALLOWED_USERS = os.getenv("ALLOWED_USERS", "").split(",")

    # Язык ответов
    LANGUAGE = os.getenv("LANGUAGE", "ru")

    @classmethod
    def validate(cls) -> bool:
        """Проверка наличия всех необходимых переменных"""
        required = {
            "TG_API_ID": "API ID из my.telegram.org",
            "TG_API_HASH": "API Hash из my.telegram.org",
            "TG_PHONE": "Номер телефона Telegram",
            "GEMINI_API_KEY": "API ключ из aistudio.google.com"
        }
        missing = [var for var in required if not os.getenv(var)]
        if missing:
            logger.error("❌ Отсутствуют переменные окружения:")
            for var in missing:
                logger.error(f"  - {var}")
            logger.info("\n📋 Инструкция по настройке:")
            logger.info("=" * 50)
            logger.info("1. Получите Telegram credentials:")
            logger.info("   → Зайдите на https://my.telegram.org")
            logger.info("   → Авторизуйтесь по номеру телефона")
            logger.info("   → Создайте приложение и получите API ID и API Hash")
            logger.info("\n2. Получите Gemini API ключ:")
            logger.info("   → Зайдите на https://aistudio.google.com/app/apikey")
            logger.info("   → Нажмите 'Create API Key'")
            logger.info("\n3. Установите переменные окружения:")
            logger.info(f"   export TG_API_ID=ваш_api_id")
            logger.info(f"   export TG_API_HASH=ваш_api_hash")
            logger.info(f"   export TG_PHONE=+79991234567")
            logger.info(f"   export GEMINI_API_KEY=ваш_key")
            logger.info(f"   export GEMINI_MODELS=gemini-1.5-pro,gemini-2.0-flash-exp,gemini-1.5-flash  # опционально, порядок: от лучших к худшим")
            logger.info(f"   export ALLOWED_USERS=username1,username2  # опционально")
            logger.info("=" * 50)
            return False

        # Проверка что есть хотя бы один API ключ
        if not cls.GEMINI_API_KEY:
            logger.error("❌ Не указан Gemini API ключ")
            return False

        logger.info(f"✅ Настроено {len(cls.GEMINI_MODELS)} моделей Gemini для переключения")
        return True


class GeminiAI:
    """
    Интеграция с Gemini API для:
    - Ответов на любые вопросы
    - Анализа текста, фото, видео, аудио
    - Определения действий для выполнения задач

    АВТОМАТИЧЕСКОЕ ПЕРЕКЛЮЧЕНИЕ МОДЕЛЕЙ:
    - При исчерпании лимита одной модели агент автоматически переключается на другую
    - Порядок моделей задается в GEMINI_MODELS
    - Используется один API ключ, но разные модели
    """

    def __init__(self, api_key: str, models: List[str]):
        self.api_key = api_key
        self.models = models
        self.current_model_index = 0
        self.failed_models = set()  # Модели которые вернули ошибки лимита

        # Инициализация с первой рабочей моделью
        self._initialize_with_next_model()

        # История чата для контекста
        self.chat_sessions: Dict[int, list] = {}

        # Системный промпт для определения действий
        self.action_prompt = """
Ты - AI-ассистент Telegram Userbot с возможностью выполнения действий.

ТВОИ ВОЗМОЖНОСТИ:
1. ОТВЕЧАТЬ на любые вопросы (используй свои знания)
2. ВЫПОЛНЯТЬ действия в файловой системе:
   - write_file: создать файл (filename, content)
   - read_file: прочитать файл (filename)
   - delete_file: удалить файл (filename)
   - list_files: список файлов (pattern, например "*.py")
   - execute_shell: выполнить команду (command)
   - execute_python: выполнить Python код (code)
   - send_file: отправить файл пользователю (filename)

ВАЖНЫЕ ПРАВИЛА:
- ВСЕГДА отвечай на вопросы пользователя, даже если не нужно действие
- Если просят что-то сделать - определяй нужное действие
- Если действие не нужно - используй action: "respond"
- Файловые операции ТОЛЬКО в текущей директории
- НЕ выполняй опасные команды (rm -rf/, форматирование и т.д.)
- Отвечай на языке пользователя

ФОРМАТ ОТВЕТА (JSON):
{
    "action": "название_действия или respond",
    "parameters": {...},
    "response": "Твой ответ пользователю (ОБЯЗАТЕЛЬНО)"
}

ПРИМЕРЫ:

Вопрос: "Привет! Как дела?"
Ответ: {"action": "respond", "parameters": {}, "response": "Привет! Я AI-агент, готов помогать вам с задачами в Telegram. Что нужно сделать?"}

Вопрос: "Создай файл hello.txt с текстом Hello World"
Ответ: {"action": "write_file", "parameters": {"filename": "hello.txt", "content": "Hello World"}, "response": "Создаю файл hello.txt с текстом 'Hello World'"}

Вопрос: "Что в файле config.json?"
Ответ: {"action": "read_file", "parameters": {"filename": "config.json"}, "response": "Сейчас прочитаю файл config.json"}

Вопрос: "Покажи все Python файлы"
Ответ: {"action": "list_files", "parameters": {"pattern": "*.py"}, "response": "Показываю все Python файлы в директории"}

Вопрос: "Выполни команду ls -la"
Ответ: {"action": "execute_shell", "parameters": {"command": "ls -la"}, "response": "Выполняю команду ls -la"}

Вопрос: "Отправь мне файл report.txt"
Ответ: {"action": "send_file", "parameters": {"filename": "report.txt"}, "response": "Отправляю файл report.txt"}
"""

    def _initialize_with_next_model(self) -> bool:
        """
        Инициализация модели со следующей доступной моделью
        Возвращает True если успешно, False если все модели исчерпаны
        """
        max_attempts = len(self.models)

        for attempt in range(max_attempts):
            # Получаем следующую модель (циклически)
            model_index = (self.current_model_index + attempt) % len(self.models)
            model_name = self.models[model_index]

            # Пропускаем модели которые уже в failed
            if model_name in self.failed_models:
                continue

            try:
                genai.configure(api_key=self.api_key)
                self.model = GenerativeModel(model_name)
                self.current_model_index = model_index
                self.current_model_name = model_name
                logger.info(f"✅ Gemini инициализирован с моделью: {model_name}")
                return True
            except Exception as e:
                logger.warning(f"Модель {model_name} не работает: {e}")
                self.failed_models.add(model_name)

        # Все модели не работают
        logger.error("❌ Все модели исчерпаны или нерабочие")
        return False

    def _switch_to_next_model(self) -> bool:
        """
        Переключение на следующую модель при ошибке лимита
        Возвращает True если удалось переключиться
        """
        # Помечаем текущую модель как failed
        current_model = self.models[self.current_model_index]
        self.failed_models.add(current_model)
        logger.warning(f"⚠️ Модель {current_model} исчерпала лимит, переключаемся...")

        # Сбрасываем failed_models если все модели помечены (попытка повторного использования)
        if len(self.failed_models) >= len(self.models):
            logger.info("🔄 Все модели были использованы, сбрасываем счетчики через 60 секунд...")
            # Не сбрасываем сразу, даем время на восстановление лимитов
            # Сброс произойдет при следующей попытке если все модели failed

        # Пробуем следующую модель
        return self._initialize_with_next_model()

    def _is_rate_limit_error(self, error: Exception) -> bool:
        """
        Проверка является ли ошибка ошибкой лимита (rate limit / quota exceeded)
        """
        error_str = str(error).lower()
        rate_limit_indicators = [
            "quota exceeded",
            "rate limit",
            "too many requests",
            "resource exhausted",
            "429",
            "daily limit",
            "limit reached"
        ]
        return any(indicator in error_str for indicator in rate_limit_indicators)

    async def _generate_with_retry(self, prompt: Union[str, list], retry_count: int = 0) -> Any:
        """
        Генерация ответа с автоматическим переключением моделей при лимитах
        """
        try:
            response = await self.model.generate_content_async(prompt)
            return response
        except Exception as e:
            if self._is_rate_limit_error(e):
                logger.warning(f"Обнаружен лимит модели {self.current_model_name}: {e}")

                # Пробуем переключиться на следующую модель
                if self._switch_to_next_model():
                    logger.info(f"Переключаемся на модель {self.current_model_name} и повторяем запрос...")
                    # Повторяем запрос с новой моделью
                    return await self._generate_with_retry(prompt, retry_count + 1)
                else:
                    logger.error("Нет доступных моделей для переключения")
                    raise Exception("Все модели исчерпали лимиты. Попробуйте позже.")
            else:
                # Другая ошибка - просто пробрасываем
                raise e

    def get_chat_history(self, user_id: int) -> list:
        """Получить историю чата для пользователя"""
        if user_id not in self.chat_sessions:
            self.chat_sessions[user_id] = []
        return self.chat_sessions[user_id]

    def add_to_history(self, user_id: int, role: str, content: Union[str, dict]):
        """Добавить сообщение в историю"""
        if user_id not in self.chat_sessions:
            self.chat_sessions[user_id] = []

        # Ограничиваем историю последними 20 сообщениями
        if len(self.chat_sessions[user_id]) >= 40:
            self.chat_sessions[user_id] = self.chat_sessions[user_id][-20:]

        self.chat_sessions[user_id].append({"role": role, "parts": [content] if isinstance(content, str) else content})

    async def chat_with_media(self, user_id: int, text: str = "", media_path: str = None) -> str:
        """
        Общение с Gemini с возможностью отправки медиа (фото, видео, аудио)
        С автоматическим переключением ключей при лимитах
        """
        try:
            parts = []

            # Добавляем текст
            if text:
                parts.append(text)

            # Добавляем медиафайл если есть
            if media_path and os.path.exists(media_path):
                try:
                    # Загружаем файл для анализа через Gemini API
                    file_data = genai.upload_file(media_path)
                    parts.append(file_data)
                    logger.info(f"📎 Медиафайл загружен: {media_path}")
                except Exception as e:
                    logger.warning(f"Не удалось загрузить медиа через API: {e}")
                    # Fallback - просто текст
                    pass

            # Формируем сообщение
            self.add_to_history(user_id, "user", parts if media_path else text)

            # Получаем ответ от модели с retry logic
            history = self.get_chat_history(user_id)
            response = await self._generate_with_retry(history)

            # Сохраняем ответ в историю
            response_text = response.text
            self.add_to_history(user_id, "model", response_text)

            return response_text

        except Exception as e:
            logger.error(f"Ошибка Gemini API: {e}")
            # Fallback к простому запросу
            return await self.simple_query(text)

    async def simple_query(self, query: str) -> str:
        """Простой запрос без медиа с retry logic"""
        try:
            response = await self._generate_with_retry(query)
            return response.text
        except Exception as e:
            logger.error(f"Ошибка запроса: {e}")
            return f"Извините, произошла ошибка: {e}"

    async def analyze_for_action(self, user_message: str, context: str = "") -> Dict[str, Any]:
        """
        Анализ запроса для определения необходимого действия
        Возвращает структуру с action, parameters и response
        С автоматическим переключением ключей при лимитах
        """
        prompt = f"""{self.action_prompt}

КОНТЕКСТ:
{context}

ЗАПРОС ПОЛЬЗОВАТЕЛЯ:
{user_message}

ТВОЙ ОТВЕТ (JSON):"""

        try:
            response = await self._generate_with_retry(prompt)
            response_text = response.text.strip()

            # Извлекаем JSON из ответа
            json_match = re.search(r'\{[^{}]*"action"[^{}]*\}', response_text, re.DOTALL)
            if not json_match:
                # Пробуем найти любой JSON
                json_match = re.search(r'\{.*\}', response_text, re.DOTALL)

            if json_match:
                result = json.loads(json_match.group())
                # Убеждаемся что есть response
                if "response" not in result:
                    result["response"] = result.get("explanation", "Выполняю запрос...")
                return result
            else:
                return {
                    "action": "respond",
                    "parameters": {},
                    "response": response_text
                }

        except Exception as e:
            logger.error(f"Ошибка анализа: {e}")
            return {
                "action": "respond",
                "parameters": {},
                "response": f"Произошла ошибка при анализе запроса: {e}. Но я всё равно отвечу: {await self.simple_query(user_message)}"
            }

class UserBotAgent:
    """Основной класс агента"""

    def __init__(self):
        self.config = Config()
        self.client: Optional[TelegramClient] = None
        self.ai: Optional[GeminiAI] = None
        self.allowed_user_ids: List[int] = []
        self.current_chat_id: Optional[int] = None

    async def initialize(self):
        """Инициализация клиента и AI"""
        if not self.config.validate():
            sys.exit(1)

        # Создаем директорию для временных медиафайлов
        media_dir = WORK_DIR / "temp_media"
        media_dir.mkdir(exist_ok=True)

        # Инициализация Gemini с переключением моделей
        self.ai = GeminiAI(self.config.GEMINI_API_KEY, self.config.GEMINI_MODELS)
        logger.info(f"Gemini AI инициализирован (модели: {', '.join(self.config.GEMINI_MODELS)})")

        # Инициализация Telegram клиента
        self.client = TelegramClient(
            self.config.SESSION_NAME,
            self.config.API_ID,
            self.config.API_HASH
        )

        await self.client.start(phone=self.config.PHONE)
        logger.info(f"Telegram клиент запущен: @{(await self.client.get_me()).username}")

        # Загрузка разрешенных пользователей
        await self._load_allowed_users()

    async def _load_allowed_users(self):
        """Загрузка ID разрешенных пользователей"""
        if self.config.ALLOWED_USERS and self.config.ALLOWED_USERS[0]:
            for username in self.config.ALLOWED_USERS:
                try:
                    user = await self.client.get_entity(username.strip())
                    self.allowed_user_ids.append(user.id)
                    logger.info(f"Добавлен разрешенный пользователь: {username}")
                except Exception as e:
                    logger.warning(f"Не удалось добавить пользователя {username}: {e}")

        # Если список пуст, разрешаем владельцу аккаунта
        if not self.allowed_user_ids:
            me = await self.client.get_me()
            self.allowed_user_ids.append(me.id)
            logger.info("Разрешен владелец аккаунта")

    def _is_allowed(self, user_id: int) -> bool:
        """Проверка доступа пользователя"""
        return user_id in self.allowed_user_ids or not self.allowed_user_ids

    async def execute_action(self, action: str, parameters: Dict[str, Any], chat_id: int) -> str:
        """Выполнение действия"""
        try:
            if action == "write_file":
                return await self._write_file(parameters)
            elif action == "read_file":
                return await self._read_file(parameters)
            elif action == "delete_file":
                return await self._delete_file(parameters)
            elif action == "list_files":
                return await self._list_files(parameters)
            elif action == "execute_shell":
                return await self._execute_shell(parameters)
            elif action == "execute_python":
                return await self._execute_python(parameters)
            elif action == "send_file":
                return await self._send_file(parameters, chat_id)
            elif action == "send_message":
                return await self._send_message(parameters, chat_id)
            elif action == "respond":
                # Просто ответ от AI, без дополнительных действий
                return ""
            else:
                return f"Неизвестное действие: {action}"
        except Exception as e:
            logger.error(f"Ошибка выполнения {action}: {e}")
            return f"Ошибка при выполнении {action}: {str(e)}"

    async def _write_file(self, params: Dict[str, Any]) -> str:
        """Создание файла"""
        filename = params.get("filename", "untitled.txt")
        content = params.get("content", "")

        # Безопасность: только в рабочей директории
        file_path = (WORK_DIR / filename).resolve()
        if not str(file_path).startswith(str(WORK_DIR)):
            return "Ошибка: выход за пределы рабочей директории запрещен"

        file_path.write_text(content, encoding="utf-8")
        return f"✅ Файл создан: {file_path.relative_to(WORK_DIR)}"

    async def _read_file(self, params: Dict[str, Any]) -> str:
        """Чтение файла"""
        filename = params.get("filename", "")
        file_path = (WORK_DIR / filename).resolve()

        if not str(file_path).startswith(str(WORK_DIR)):
            return "Ошибка: выход за пределы рабочей директории запрещен"

        if not file_path.exists():
            return f"❌ Файл не найден: {filename}"

        content = file_path.read_text(encoding="utf-8")
        # Ограничение размера
        if len(content) > 4000:
            content = content[:4000] + "\n... (файл обрезан)"

        return f"📄 Содержимое {filename}:\n```\n{content}\n```"

    async def _delete_file(self, params: Dict[str, Any]) -> str:
        """Удаление файла"""
        filename = params.get("filename", "")
        file_path = (WORK_DIR / filename).resolve()

        if not str(file_path).startswith(str(WORK_DIR)):
            return "Ошибка: выход за пределы рабочей директории запрещен"

        if not file_path.exists():
            return f"❌ Файл не найден: {filename}"

        file_path.unlink()
        return f"✅ Файл удален: {filename}"

    async def _list_files(self, params: Dict[str, Any]) -> str:
        """Список файлов"""
        pattern = params.get("pattern", "*")
        files = list(WORK_DIR.glob(pattern))

        if not files:
            return "📂 Файлы не найдены"

        result = "📁 Файлы в рабочей директории:\n"
        for f in files[:50]:  # Ограничение 50 файлов
            if f.is_file():
                result += f"📄 {f.name} ({f.stat().st_size} байт)\n"
            else:
                result += f"📁 {f.name}/\n"

        if len(files) > 50:
            result += f"... и еще {len(files) - 50} файлов"

        return result

    async def _execute_shell(self, params: Dict[str, Any]) -> str:
        """Выполнение shell команды"""
        command = params.get("command", "")

        # Блокировка опасных команд
        dangerous = ["rm -rf /", "mkfs", "dd if=", ":(){:|:&}", "chmod 777 /"]
        if any(d in command for d in dangerous):
            return "❌ Ошибка: выполнение опасной команды запрещено"

        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=WORK_DIR
            )
            stdout, stderr = await process.communicate()

            result = ""
            if stdout:
                result = stdout.decode()[:4000]
            if stderr:
                result += f"\n⚠️ Ошибки:\n{stderr.decode()[:2000]}"

            return f"⚙️ Результат выполнения `{command}`:\n```\n{result}\n```"
        except Exception as e:
            return f"❌ Ошибка выполнения команды: {str(e)}"

    async def _execute_python(self, params: Dict[str, Any]) -> str:
        """Выполнение Python кода"""
        code = params.get("code", "")

        try:
            # Создаем временный файл
            temp_file = WORK_DIR / "temp_script.py"
            temp_file.write_text(code, encoding="utf-8")

            process = await asyncio.create_subprocess_exec(
                sys.executable, str(temp_file),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=WORK_DIR
            )
            stdout, stderr = await process.communicate()

            temp_file.unlink()  # Удаляем временный файл

            result = ""
            if stdout:
                result = stdout.decode()[:4000]
            if stderr:
                result += f"\n⚠️ Ошибки:\n{stderr.decode()[:2000]}"

            return f"🐍 Результат:\n```\n{result}\n```"
        except Exception as e:
            return f"❌ Ошибка выполнения Python кода: {str(e)}"

    async def _send_file(self, params: Dict[str, Any], chat_id: int) -> str:
        """Отправка файла в чат"""
        filename = params.get("filename", "")
        file_path = (WORK_DIR / filename).resolve()

        if not str(file_path).startswith(str(WORK_DIR)):
            return "❌ Ошибка: выход за пределы рабочей директории запрещен"

        if not file_path.exists():
            return f"❌ Файл не найден: {filename}"

        await self.client.send_file(chat_id, str(file_path))
        return f"✅ Файл отправлен: {filename}"

    async def _send_message(self, params: Dict[str, Any], chat_id: int) -> str:
        """Отправка сообщения"""
        message = params.get("message", "")
        await self.client.send_message(chat_id, message)
        return "✅ Сообщение отправлено"

    async def run(self):
        """Запуск агента"""
        await self.initialize()

        @self.client.on(events.NewMessage(incoming=True))
        async def handler(event: events.NewMessage.Event):
            """Обработка входящих сообщений (текст, фото, видео, голосовые)"""
            if not self._is_allowed(event.sender_id):
                logger.warning(f"Запрос от неразрешенного пользователя {event.sender_id}")
                return

            # Сохраняем chat_id для отправки файлов
            self.current_chat_id = event.chat_id

            # Получаем текст сообщения
            user_message = event.message.text or ""

            # Проверяем наличие медиа (фото, видео, голосовые, документы)
            media_path = None
            media_type = None

            if event.message.photo:
                # Фото - скачиваем для анализа
                media_path = await event.message.download_media(file=f"{WORK_DIR}/temp_media/")
                media_type = "photo"
                logger.info(f"📷 Получено фото: {media_path}")

            elif event.message.video:
                # Видео - скачиваем для анализа
                media_path = await event.message.download_media(file=f"{WORK_DIR}/temp_media/")
                media_type = "video"
                logger.info(f"🎬 Получено видео: {media_path}")

            elif event.message.voice:
                # Голосовое сообщение - скачиваем для анализа
                media_path = await event.message.download_media(file=f"{WORK_DIR}/temp_media/")
                media_type = "audio"
                logger.info(f"🎤 Получено голосовое: {media_path}")

            elif event.message.document:
                # Документ - проверяем тип
                doc = event.message.document
                if doc.mime_type and (doc.mime_type.startswith('audio') or doc.mime_type.startswith('video')):
                    media_path = await event.message.download_media(file=f"{WORK_DIR}/temp_media/")
                    media_type = doc.mime_type.split('/')[0]
                    logger.info(f"📎 Получен документ ({doc.mime_type}): {media_path}")

            # Создаем директорию для медиа если нет
            if media_path and not os.path.exists(os.path.dirname(media_path)):
                os.makedirs(os.path.dirname(media_path), exist_ok=True)

            # Если есть медиа или текст - обрабатываем через Gemini
            context = f"Текущая директория: {WORK_DIR}"

            if media_path:
                # Медиа + возможно текст
                logger.info(f"Анализ медиа ({media_type}) через Gemini...")

                # Сначала получаем описание медиа от Gemini
                media_description = await self.ai.chat_with_media(
                    event.sender_id,
                    text=user_message if user_message else f"Опиши что на этом {media_type}",
                    media_path=media_path
                )

                logger.info(f"Описание медиа: {media_description[:200]}...")

                # Теперь анализируем запрос с учетом описания медиа
                full_context = f"{context}\n\nМедиа ({media_type}): {media_description}"
                analysis = await self.ai.analyze_for_action(user_message or f"Что делать с этим {media_type}?", full_context)

                # Очищаем временный файл медиа
                try:
                    if os.path.exists(media_path):
                        os.remove(media_path)
                        logger.info(f"Временный файл удален: {media_path}")
                except Exception as e:
                    logger.warning(f"Не удалось удалить временный файл: {e}")
            else:
                # Только текст
                if not user_message:
                    return

                logger.info(f"Сообщение от {event.sender_id}: {user_message[:100]}")
                analysis = await self.ai.analyze_for_action(user_message, context)

            logger.info(f"Анализ: action={analysis.get('action')}, response={analysis.get('response', '')[:100]}...")

            # AI всегда дает response - это основной ответ пользователю
            ai_response = analysis.get("response", "")

            # Выполняем действие если нужно
            action_result = ""
            if analysis.get("action") and analysis["action"] != "respond":
                action_result = await self.execute_action(
                    analysis["action"],
                    analysis["parameters"],
                    event.chat_id
                )

            # Формируем итоговый ответ
            if ai_response and action_result:
                final_response = f"🤖 {ai_response}\n\n{action_result}"
            elif ai_response:
                final_response = f"🤖 {ai_response}"
            elif action_result:
                final_response = action_result
            else:
                final_response = "✅ Выполнено"

            # Отправляем ответ
            if len(final_response) > 4000:
                # Слишком длинный - отправляем файлом
                result_file = WORK_DIR / "response.txt"
                result_file.write_text(final_response, encoding="utf-8")
                await self.client.send_file(event.chat_id, str(result_file))
                result_file.unlink()
            else:
                await event.respond(final_response)

        logger.info("=" * 50)
        logger.info("🤖 Telegram Userbot AI Agent запущен!")
        logger.info(f"📂 Рабочая директория: {WORK_DIR}")
        logger.info("📬 Ожидание команд (текст, фото, видео, голосовые)...")
        logger.info("=" * 50)
        await self.client.run_until_disconnected()

async def main():
    """Точка входа"""
    agent = UserBotAgent()
    await agent.run()

if __name__ == "__main__":
    asyncio.run(main())