import asyncio
import aiohttp
from pathlib import Path
import aiofiles

class WikiAPI:
    def __init__(self, session: aiohttp.ClientSession):
        self.session = session
        self.url = 'https://ru.wikipedia.org/w/api.php'# точка входа запросов к серверу через API


    async def titles_generator(self, total_count: int):
        generated = 0 # считаем сколько сгенерировали заголовков
        my_params = {
            "action": "query",
            "format": "json",
            "rnlimit": 500,       #
            "list": "random",
            "rnnamespace": 0
    }
        while generated < total_count:
            async with self.session.get(self.url, params = my_params) as response:
                data = await response.json()
                titles_list = data['query']['random']
                for item in titles_list:
                    if generated >= total_count: # останавливаем цикл если статей больше нужного
                           break
                yield item['title'] # возвращаем название статьи
                generated +=1


    async def get_article_text(self, title: str):
        params = {
            "action": "query", #
            "format": "json", # получаем данные в форме JSON вытаскиваем данные по ключу
            "titles": title,
            "prop": "extracts", #
            "explaintext": "1" # ставим парметр что хотим получать чистый текст
        }
        async with self.session.get(self.url, params= params) as response:
            data = await response.json()
            pages = data['query']['pages']
            page_data = next(iter(pages.values()))
            text = page_data.get('extract', 'Текст не найден')
            return text


class ArticleDiskSave:
    def __init__(self, output_path: Path):
        self.path = output_path
        self.path.mkdir(parents=True, exist_ok= True)

    async def correct_title(self, title:str) -> str:
        for char in r'\/:*?"<>|':
            correct_title = title.replace(char, '_')
        return correct_title

    async def save_articles(self, title: str, text: str):
        correct_filename = self.correct_title(title)
        file_path = self.path /  f'article_{correct_filename}.txt'
        async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
            await f.write(f'НАЗВАНИЕ: {correct_filename}\n\n{"="*30}\n\n{text}')

class WikiParcer:
    def __init__(self, client: WikiAPI, saver: ArticleDiskSave, max_it_once: int):
        self.client = client
        self.saver = saver
        self.sem = asyncio.Semaphore(max_it_once)

    async def __process_one(self, title:str):
        async with self.sem:
            text = await self.client.get_article_text(title)
            await self.saver.save_articles(title, text)

    async def run(self, total_article: int):
        async with asyncio.TaskGroup() as tg:
            async for title in self.client.titles_generator(total_article):
                tg.create_task(self.__process_one(title))

async def main():
    headers = {"User-Agent": "EducationalBot/1.0 (gadamokov@gmail.com)"}
    output = Path('../../data_saved')
    async with aiohttp.ClientSession(headers=headers) as session:
        client = WikiAPI(session)
        saver = ArticleDiskSave(output)
        app = WikiParcer(client, saver, 100)

    await app.run(1000)

if __name__ == '__main__':
    asyncio.run(main())





