import asyncio
import aiohttp
import aiofiles
import logging
from pathlib import Path
from typing import AsyncGenerator

# Настройка простого логгера (позже сделаем круче)
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class WikiAPI:
    def __init__(self, session: aiohttp.ClientSession):
        self.session = session
        self.url = 'https://ru.wikipedia.org/w/api.php'

    async def titles_generator(self, total_count: int) -> AsyncGenerator[str, None]:
        generated = 0
        batch_size = 50  # Не жадничаем, берем пачками

        while generated < total_count:
            # Параметры лучше определять внутри цикла или обновлять, если нужно
            params = {
                "action": "query",
                "format": "json",
                "list": "random",
                "rnlimit": batch_size,
                "rnnamespace": 0
            }
            try:
                async with self.session.get(self.url, params=params) as response:
                    response.raise_for_status()  # Проверка на 404/500 ошибки
                    data = await response.json()

                    titles_list = data.get('query', {}).get('random', [])
                    if not titles_list:
                        logger.warning("Пустой ответ от API")
                        break

                    for item in titles_list:
                        if generated >= total_count:
                            return  # Полный выход из генератора
                        yield item['title']
                        generated += 1

            except aiohttp.ClientError as e:
                logger.error(f"Ошибка сети: {e}")
                await asyncio.sleep(2)  # Backoff (ждем перед повтором)

    async def get_article_text(self, title: str) -> str | None:
        params = {
            "action": "query",
            "format": "json",
            "titles": title,
            "prop": "extracts",
            "explaintext": "1"
        }
        try:
            async with self.session.get(self.url, params=params) as response:
                response.raise_for_status()
                data = await response.json()
                pages = data.get('query', {}).get('pages', {})

                # Логика извлечения первой страницы
                if not pages:
                    return None

                page_value = next(iter(pages.values()))
                return page_value.get('extract')  # Может вернуть None
        except Exception as e:
            logger.error(f"Не удалось скачать статью '{title}': {e}")
            return None


class ArticleDiskSave:
    def __init__(self, output_path: Path):
        self.path = output_path
        self.path.mkdir(parents=True, exist_ok=True)

    # Убрали async - это CPU операция, она быстрая
    def _clean_filename(self, title: str) -> str:
        clean = title
        for char in r'\/:*?"<>|':
            clean = clean.replace(char, '_')
        return clean

    async def save(self, title: str, text: str) -> None:
        if not text:
            return

        filename = self._clean_filename(title)
        file_path = self.path / f"{filename}.txt"

        try:
            async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
                # Добавим метаданные для красоты
                content = f"URL: https://ru.wikipedia.org/wiki/{title}\n\n{text}"
                await f.write(content)
            logger.info(f"Сохранено: {filename}")
        except Exception as e:
            logger.error(f"Ошибка записи файла {filename}: {e}")


class WikiScraper:
    def __init__(self, client: WikiAPI, saver: ArticleDiskSave, concurrency: int = 10):
        self.client = client
        self.saver = saver
        self.sem = asyncio.Semaphore(concurrency)  # Ограничиваем кол-во одновременных загрузок

    async def _process_one(self, title: str):
        async with self.sem:
            text = await self.client.get_article_text(title)
            if text:
                await self.saver.save(title, text)

    async def run(self, total_articles: int):
        logger.info(f"Начинаем скачивание {total_articles} статей...")
        async with asyncio.TaskGroup() as tg:
            async for title in self.client.titles_generator(total_articles):
                tg.create_task(self._process_one(title))


# --- ENTRY POINT ---
# Это должно быть в отдельном файле main.py, но пока оставим тут для теста
async def main():
    headers = {"User-Agent": "NeuralSearchBot/1.0 (me@example.com)"}

    # ПРАВИЛЬНЫЙ ПУТЬ: используем data/raw внутри проекта
    # Предполагаем, что запускаем из корня проекта
    output_dir = Path("data/raw/wikipedia")

    async with aiohttp.ClientSession(headers=headers) as session:
        api = WikiAPI(session)
        saver = ArticleDiskSave(output_dir)
        scraper = WikiScraper(api, saver, concurrency=20)  # 20 потоков

        # Запускаем ВНУТРИ контекста сессии
        await scraper.run(total_articles=50)  # Скачаем 50 для теста


if __name__ == '__main__':
    # Проверка версии Python для TaskGroup
    import sys

    if sys.version_info < (3, 11):
        raise RuntimeError("Нужен Python 3.11+ для asyncio.TaskGroup")

    asyncio.run(main())




