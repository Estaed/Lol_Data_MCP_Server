import asyncio
from bs4 import BeautifulSoup
from wiki_sscraper import WikiScraper, WikiScraperError

async def main():
    scraper = WikiScraper()

    try:
        with open("C:/Users/tarik/OneDrive/Masaüstü/Lol Wiki/wiki.leagueoflegends.com/en-us/Taric.html", "r", encoding="utf-8") as f:
            html_content = f.read()
        
        soup = BeautifulSoup(html_content, 'html.parser')

        print("--- Parsing Champion Abilities (using new scraper) ---")
        try:
            abilities = scraper.parse_champion_abilities(soup)
            print(abilities)
        except WikiScraperError as e:
            print(f"Error parsing abilities: {e}")

    except FileNotFoundError:
        print("Error: Taric.html not found. Make sure the file path is correct.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    asyncio.run(main())