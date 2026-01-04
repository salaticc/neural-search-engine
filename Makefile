run-scraper:
	python src/crawler/async_scraper.py

clean-data:
	rm -rf data/raw/*