import asyncio
import aiohttp
from pathlib import Path
from aiohttp import ClientSession
import json
import aiofiles

output_dir = Path('C:/Users/ThinkPad/PycharmProjects/neural-search-engine/data_saved')
url = 'https://ru.wikipedia.org/w/api.php' # точка входа запросов к серверу через API
headers = {
    "User-Agent": "EducationalBot/1.0 (gadamokov@gmail.com)"
}


async def titles_generator(total_count, session):
    generated = 0 # считаем сколько сгенерировали заголовков
    my_params = {
        "action": "query",
        "format": "json",
        "rnlimit": 500,
        "list": "random",
        "rnnamespace": 0
    }
    while generated < total_count:
        async with session.get(url, params = my_params) as response:
            data = await response.json()
            titles_list = data['query']['random']
            for item in titles_list:
                if generated >= total_count: # останавливаем цикл если статей больше нужного
                  break
                yield item['title'] # возвращаем название статьи
                generated +=1


async def get_article_text(session, title):
        params = {
            "action": "query", #
            "format": "json",
            "titles": title,
            "prop": "extracts", #
            "explaintext": "1" # ставим парметр что хотим получать чистый текст
        }
        async with session.get(url=url, params= params) as response:
            data = await response.json()
            pages = data['query']['pages']
            page_data = next(iter(pages.values()))
            text = page_data.get('extract', 'Текст не найден')
            return text


async def save_articles(title, text):
    bad_chars = r'\/:*?"<>|'
    save_name = title
    for char in bad_chars:
        save_name = save_name.replace(char, '_')
    path_txt = output_dir / f'article_{save_name}.txt'
    async with aiofiles.open(path_txt, 'w', encoding='utf-8') as f:
        await f.write(f'НАЗВАНИЕ: {save_name}' + '\n\n')
        await f.write('='* 30 + "\n\n")
        await f.write(f'СОДЕРЖАНИЕ:{text}' + "\n\n")


async def handle_article(session, title, sem):
    async with sem:
        text = await get_article_text(session, title)
        await save_articles(title, text)

async def main():
    sem = asyncio.Semaphore(100)
    async with aiohttp.ClientSession(headers=headers) as session:
        async with asyncio.TaskGroup() as tg:
            async for title in titles_generator(1000, session):
                tg.create_task(handle_article(session, title, sem))
if __name__ == '__main__':
    asyncio.run(main())





