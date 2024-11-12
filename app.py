from flask import Flask, jsonify, request
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import time

app = Flask(__name__)

# Function for scraping individual property data from a specific URL
def scrape_data(url):
    driver_path = r"binary\chromedriver.exe"
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--start-maximized")

    driver = webdriver.Chrome(service=ChromeService(executable_path=driver_path), options=chrome_options)
    driver.get(url)
    time.sleep(1)

    # Example: Click to open calendar and extract dates
    try:
        calendar = driver.find_element(By.CLASS_NAME, "caleran_container")
        calendar.click()
        time.sleep(1)
    except Exception as e:
        driver.quit()
        return {"error": f"Failed to open calendar: {e}"}

    def unix_to_datetime(unix_timestamp):
        return datetime.fromtimestamp(int(unix_timestamp)).strftime('%Y-%m-%d %H:%M:%S')

    def extract_dates():
        dates = []
        active_dates = driver.find_elements(By.CSS_SELECTOR, ".caleran-day")
        disabled_dates = driver.find_elements(By.CSS_SELECTOR, ".caleran-day.caleran-disabled-range.caleran-disabled-range-end")

        for date in active_dates + disabled_dates:
            date_text = date.text.strip()
            date_value = date.get_attribute("data-value")

            if date_value:
                human_date = unix_to_datetime(date_value)
                dates.append((date_text, human_date))
        return dates

    collected_dates = []
    for _ in range(3):
        try:
            collected_dates.extend(extract_dates())
            driver.find_element(By.CSS_SELECTOR, ".fa.fa-arrow-right").click()
            time.sleep(1.5)
        except Exception as e:
            print(f"Error navigating calendar: {e}")
            break

    driver.quit()
    df = pd.DataFrame(collected_dates, columns=["Date", "DateTime"])
    df['DateTime'] = pd.to_datetime(df['DateTime'])
    df.drop_duplicates(subset='DateTime', inplace=True)
    return df.sort_values(by='DateTime').to_dict(orient="records")

# Function for scraping property listings from multiple pages
def scrape_properties():
    url_base = 'https://www.brassbell.net/properties/?page='
    driver_path = r"D:\LikeCard\LCPricing\binary\chromedriver.exe"
    options = Options()
    options.add_argument("--headless")
    driver = webdriver.Chrome(service=ChromeService(executable_path=driver_path), options=options)
    driver.set_window_size(1920, 1080)

    properties_data = []
    base_url = 'https://www.brassbell.net/'

    for page_number in range(1, 32):
        url = f"{url_base}{page_number}"
        driver.get(url)
        try:
            parent_container = WebDriverWait(driver, 20).until(
                EC.visibility_of_element_located((By.CLASS_NAME, 'row.grid-container-15'))
            )
        except Exception as e:
            print(f"Failed to load page {page_number}: {e}")
            continue

        property_blocks = parent_container.find_elements(By.CLASS_NAME, 'grid-item')

        for block in property_blocks:
            html_content = block.get_attribute('outerHTML')
            soup = BeautifulSoup(html_content, 'html.parser')

            property_data = {}
            property_link = soup.find('a', class_='block_property')
            if property_link:
                property_data['url'] = base_url + property_link['href']
                property_data['title'] = property_link['title']

            image_container = soup.find('div', class_='image')
            if image_container:
                property_data['image_url'] = base_url + image_container['style'].split("url(")[-1].strip(")")

            price_container = soup.find('div', class_='price')
            if price_container:
                property_data['price_per_night'] = price_container.find('b').text.strip()
                discount = price_container.find('div', class_='discount')
                property_data['discounted_price_per_night'] = discount.text.strip() if discount else None

            block_content = soup.find('div', class_='block_content')
            if block_content:
                details = block_content.find('small')
                if details:
                    property_data['details'] = details.text.strip()

            location = soup.find('div', class_='block_content').find('h3') if block_content else None
            if location:
                property_data['location'] = location.text.strip()

            properties_data.append(property_data)

    driver.quit()
    df = pd.DataFrame(properties_data)
    return df.to_dict(orient="records")

# Endpoint to scrape individual property data
@app.route('/scrape', methods=['GET'])
def scrape_endpoint():
    url = request.args.get('url')
    if not url:
        return jsonify({"error": "URL is required"}), 400
    try:
        data = scrape_data(url)
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Endpoint to scrape properties listing data
@app.route('/scrape-properties', methods=['GET'])
def scrape_properties_endpoint():
    try:
        data = scrape_properties()
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
