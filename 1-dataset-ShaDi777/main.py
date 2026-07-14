import csv
import os
import time

from bs4 import BeautifulSoup as bsoup, BeautifulSoup
from bs4.element import PageElement
from bs4.element import Tag
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait


class DriverFactory:
    def __init__(self):
        self.driver: webdriver = None

    def __init_driver(self):
        # Workaround from StackOverflow to pass BotDetection
        # https://stackoverflow.com/questions/70753662/selenium-chrome-opens-a-white-page
        chrome_options = ChromeOptions()
        chrome_options.add_experimental_option("excludeSwitches", ['enable-automation'])
        chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        # chrome_options.add_argument("start-maximized")
        # chrome_options.add_argument("--headless=new") # disable UI

        self.driver = webdriver.Chrome(options=chrome_options)

    def get_driver(self):
        if self.driver is None:
            self.__init_driver()

        return self.driver


driver_factory = DriverFactory()


def scroll_page():
    driver = driver_factory.get_driver()
    SCROLL_PAUSE_TIME = 1

    last_height = driver.execute_script("return document.body.scrollHeight")

    while True:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(SCROLL_PAUSE_TIME)

        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height


# The element with this tag is located at the bottom of the page.
# Therefore, this element is loaded after the entire page becomes available to us.
def load_page(url: str, needScroll: bool = True) -> str:
    driver = driver_factory.get_driver()
    driver.get(url)

    try:
        print("Start waiting for ozonTagManagerApp")
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.ID, "ozonTagManagerApp"))
        )
        print("End waiting for ozonTagManagerApp")

        driver.execute_script("window.stop();")

        if needScroll:
            scroll_page()
    finally:
        return driver.page_source


def parse_characteristics(soup: BeautifulSoup) -> dict:
    characteristics = {}
    characteristics_tag = soup.find('div', id='section-characteristics')
    for dl in characteristics_tag.find_all('dl'):
        key = dl.find('dt').get_text(strip=True)
        key = key.strip(':')

        value = dl.find('dd').get_text(strip=True)
        characteristics[key] = value

    print("Successfully parsed characteristics:")
    for key, value in characteristics.items():
        print(f'{key}: {value}')

    return characteristics


def parse_score(soup: BeautifulSoup) -> dict:
    try:
        score_tag = soup.select('div[data-widget="webSingleProductScore"]', limit=1).pop()
        score = score_tag.a.div.text
        rating, reviews_count = score.split('•')
        rating = float(rating)
        reviews_count = int(reviews_count[:reviews_count.rindex(' ')].replace(' ', ''))

        return {
            'Оценка': rating,
            'Количество отзывов': reviews_count,
        }

    except Exception:
        return {
            'Оценка': None,
            'Количество отзывов': None,
        }


def parse_question(soup: BeautifulSoup) -> dict:
    try:
        question_tag = soup.select('div[data-widget="webQuestionCount"]', limit=1).pop()
        question_count = question_tag.div.text
        question_count = int(question_count[:question_count.rindex(' ')].replace(' ', ''))
        return {
            'Количество вопросов': question_count,
        }
    except Exception:
        return {
            'Количество вопросов': 0,
        }


def parse_price(soup: BeautifulSoup) -> dict:
    price = None
    try:
        price_tag = soup.select('div[data-widget="webPrice"]', limit=1).pop()
        price = price_tag.div.div.find_next_sibling().div.div.span.text
        price = int(price.encode('ascii', 'ignore'))
    except Exception:
        try:
            price_tag = soup.select('div[data-widget="webPrice"]', limit=1).pop()
            price = price_tag.div.div.div.div.span.text
            price = int(price.encode('ascii', 'ignore'))
        except Exception:
            pass
    return {
        'Цена': price,
    }


def parse_description(soup: BeautifulSoup) -> dict:
    try:
        description_tag = soup.find('div', id='section-description')
        description = description_tag.div.find_next_sibling().div.div.div.text
    except Exception:
        description = None

    return {
        "Описание": description
    }


def parse_seller(soup: BeautifulSoup) -> dict:
    try:
        seller_tag = soup.select('div[data-widget="webCurrentSeller"]', limit=1).pop()
        seller = seller_tag.div.div.div.a['href']
        seller = seller.split('/')[-2]
    except Exception:
        seller = None

    return {
        "Продавец": seller
    }


def process_single_item(item: Tag):
    item_page_href = item.div.a['href']

    url = f"https://ozon.ru{item_page_href}"
    result = load_page(url, needScroll=False)
    soup = bsoup(result, 'html.parser')

    print(f"\nURL: {url}")

    characteristics = parse_characteristics(soup)
    score = parse_score(soup)
    question = parse_question(soup)
    price = parse_price(soup)
    description = parse_description(soup)
    seller = parse_seller(soup)

    data = {
        **characteristics,
        **score,
        **question,
        **price,
        **description,
        **seller,
        'url': url,
    }
    append_data_to_tsv(data)


def parse_single_block(block):
    for item in block:
        if isinstance(item, Tag):
            try:
                process_single_item(item)
            except Exception:
                pass


def parse_paginator(paginator):
    for block in paginator:
        if isinstance(block, Tag):
            parse_single_block(block.div)


# Function to press "Next page" at the bottom of the website
# Not used because Ozon detects this as a bot and stops giving new pages.
def get_next_url(paginator: Tag) -> str:
    try:
        page_selector: PageElement = paginator.fetchNextSiblings()[0].div.div
        for obj in page_selector:
            try:
                if isinstance(obj, Tag) and "page=" in obj['href']:
                    return obj["href"]
            except:
                pass
    except Exception:
        return ""
    return ""

# Путь к TSV файлу
file_name = 'parsed_data.tsv'


def read_existing_tsv():
    global file_name

    if os.path.exists(file_name):
        with open(file_name, mode='r', newline='', encoding='utf-8') as file:
            reader = csv.DictReader(file, delimiter='\t')
            data = list(reader)
            existing_keys = reader.fieldnames
            return data, existing_keys
    else:
        return [], []


def append_data_to_tsv(new_data):
    global file_name

    existing_data, existing_keys = read_existing_tsv()
    new_keys = new_data.keys()

    new_columns = [key for key in new_keys if key not in existing_keys]

    if new_columns:
        existing_keys.extend(new_columns)

        for row in existing_data:
            for key in new_columns:
                row[key] = None

    with open(file_name, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=existing_keys, delimiter='\t')

        writer.writeheader()
        writer.writerows(existing_data)

        new_row = {key: new_data.get(key, None) for key in existing_keys}
        writer.writerow(new_row)


BASE_URL = "https://www.ozon.ru/category/monitory-15738"
score_query = "/?sorting=score"
# score_query = "/?sorting=new"
# score_query = "/?sorting=price"
# score_query = "/?sorting=price_desc"
# score_query = "/?sorting=rating"
# score_query = "/?sorting=discount"
page_num = 1
while True:
    print("Now on page " + str(page_num))
    page_query = f"&page={page_num}"
    url = f'{BASE_URL}{score_query}{page_query}'
    result = load_page(url)

    soup = bsoup(result, 'html.parser')
    paginator = soup.find('div', id='paginatorContent')
    if paginator is None or len(paginator) == 0:
        break

    parse_paginator(paginator)

    page_num += 3
