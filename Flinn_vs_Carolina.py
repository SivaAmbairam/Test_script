import csv
import re
import os
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import ElementClickInterceptedException
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import random
from module_package import *
from transformers import BertTokenizer, BertModel
import torch
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
import nltk
from selenium.common.exceptions import ElementClickInterceptedException, TimeoutException
import logging

log_dir = r'Scrapping Scripts/Output/temp'
log_file = 'web_scraping_carolina.log'

# Ensure the directory exists
os.makedirs(log_dir, exist_ok=True)
log_path = os.path.join(log_dir, log_file)

logging.basicConfig(filename=log_path, level=logging.INFO, format='%(asctime)s %(message)s')


nltk.data.path.append(r'C:\Users\G6\AppData\Roaming\nltk_data')

model_name = 'bert-base-uncased'
tokenizer = BertTokenizer.from_pretrained(model_name)
model = BertModel.from_pretrained(model_name)
stop_words = set(stopwords.words('english'))


def remove_stop_words(sentence):
    if isinstance(sentence, float):
        return ''
    words = word_tokenize(sentence.lower())
    filtered_words = [word for word in words if word not in stop_words]
    filtered_sentence = ' '.join(filtered_words)
    return filtered_sentence


def get_sentence_embedding(sentence, pooling_strategy='mean'):
    filtered_sentence = remove_stop_words(sentence)
    inputs = tokenizer(filtered_sentence, return_tensors='pt', truncation=True, padding=True, max_length=128)
    input_ids = inputs['input_ids']
    attention_mask = inputs['attention_mask']

    with torch.no_grad():
        outputs = model(input_ids, attention_mask=attention_mask)

    last_hidden_state = outputs.last_hidden_state

    if pooling_strategy == 'mean':
        sentence_embedding = torch.mean(last_hidden_state, dim=1)
    elif pooling_strategy == 'cls':
        sentence_embedding = last_hidden_state[:, 0, :]
    elif pooling_strategy == 'max':
        sentence_embedding = torch.max(last_hidden_state, dim=1)[0]
    else:
        raise ValueError(f"Unknown pooling strategy: {pooling_strategy}")

    sentence_embedding = torch.nn.functional.normalize(sentence_embedding, p=2, dim=1)
    return sentence_embedding


def calculate_similarity(sentence1, sentence2, pooling_strategy='max'):
    embedding1 = get_sentence_embedding(sentence1, pooling_strategy)
    embedding2 = get_sentence_embedding(sentence2, pooling_strategy)
    similarity = cosine_similarity(embedding1.numpy(), embedding2.numpy())
    return similarity[0][0]

# List of common color names
color_names = ['red', 'green', 'blue', 'yellow', 'orange', 'purple', 'pink', 'brown', 'black', 'white', 'gray', 'silver']


def clean_text(text):
    # Remove colors
    for color in color_names:
        text = re.sub(rf'\b{color}\b', '', text, flags=re.IGNORECASE)
    # Remove ml and mm values
    text = re.sub(r'\b\d+(\.\d+)?\s*(mL|mm)\b', '', text, flags=re.IGNORECASE)
    # Remove standalone numbers
    text = re.sub(r'\b\d+\b', '', text)
    return text.strip()

# Function to get word sets from product names
def get_word_set(text):
    # Split the text into words, remove any empty words
    return set(word for word in re.split(r'\W+', text) if word)

# Function to get the word similarity ratio between two sets of words
def word_similarity(set1, set2):
    return len(set1 & set2) / len(set1 | set2)


# def read_threshold_log():
#     file_path = os.path.join('Output', 'temp', 'carolina_threshold_log.txt')
#     completed_thresholds = set()
#     if os.path.exists(file_path):
#         with open(file_path, 'r') as file:
#             for line in file:
#                 completed_thresholds.add(line.strip())
#     return completed_thresholds
#
#
# def write_threshold_log(threshold):
#     output_dir = os.path.join('Output', 'temp')
#     if not os.path.exists(output_dir):
#         os.makedirs(output_dir)
#     file_path = os.path.join(output_dir, 'carolina_threshold_log.txt')
#     with open(file_path, 'a', encoding='utf-8') as file:
#         file.write(f"{threshold}\n")
#
# def read_global_matched_products():
#     try:
#         with open('Output/temp/global_matched_carolina_products.txt', 'r') as file:
#             global_matched_products = set(file.read().splitlines())
#         return global_matched_products
#     except FileNotFoundError:
#         return set()
#
# def write_global_matched_products(matched_products):
#     output_dir = os.path.join('Output', 'temp')
#     if not os.path.exists(output_dir):
#         os.makedirs(output_dir)
#     file_path = os.path.join(output_dir, 'global_matched_carolina_products.txt')
#     with open(file_path, 'w') as file:
#         for product_id in matched_products:
#             file.write(f"{product_id}\n")


def fetch_carolina_product_ids(driver, key_name, retry_attempts=3):
    for attempt in range(retry_attempts):
        try:
            driver.get('https://www.carolina.com/')
            search_element = WebDriverWait(driver, 20).until(
                EC.element_to_be_clickable((By.NAME, 'Ntt'))
            )
            search_element.send_keys(key_name)

            search_button = WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.XPATH, "//button[@type='submit']"))
            )

            try:
                driver.execute_script("arguments[0].scrollIntoView(true);", search_button)
                WebDriverWait(driver, 20).until(EC.element_to_be_clickable((By.XPATH, "//button[@type='submit']")))
                search_button.click()
            except ElementClickInterceptedException:
                driver.execute_script("arguments[0].click();", search_button)

            time.sleep(random.randint(1, 20))
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            results_number = soup.find_all('p', class_='c-product-total')
            product_ids =[]
            for single_number in results_number:
                if 'Item' in str(single_number):
                    id_tag = strip_it(single_number.text.split('#', 1)[-1].replace('(', '').replace(')', '').strip())
                    product_ids.append(id_tag)
            return product_ids
        except TimeoutException as e:
            logging.error(f"TimeoutException: {e}")
            driver.save_screenshot('timeout_exception_screenshot.png')
        except Exception as e:
            logging.error(f"An error occurred: {e}")
        time.sleep(5)
    return []

def match_products(flinn_products, carolina_products, initial_threshold, threshold_decrement, output_folder):
    matched_products = []
    threshold = initial_threshold
    prev_threshold = None  # Initialize prev_threshold to None

    # Get the absolute path of the output folder
    output_folder_path = os.path.join('Scrapping Scripts', 'Output', 'temp', output_folder)

    # Create the output folder if it doesn't exist
    os.makedirs(output_folder_path, exist_ok=True)
    # completed_thresholds = read_threshold_log()
    # global_matched_products = read_global_matched_products()

    flinn_file_path = os.path.join('Scrapping Scripts', 'Output', 'Flinn_Products.csv')
    carolina_file_path = os.path.join('Scrapping Scripts', 'Output', 'Carolina_Products.csv')

    flinn_csv = pd.read_csv(flinn_file_path)
    carolina_csv = pd.read_csv(carolina_file_path)
    # options = Options()
    # options.add_argument("--headless")
    # driver = webdriver.Chrome()

    while threshold >= 0:
        # if str(threshold) in completed_thresholds:
        #     print(f"Threshold {threshold} already processed. Skipping...")
        #     threshold = round(threshold - threshold_decrement, 2)
        #     continue
        print(f"Matching products with threshold: {threshold:.2f}")
        output_file = os.path.join(output_folder_path, f"FlinnVsCarolina_{threshold:.2f}.csv")  # Round the threshold to 2 decimal places for the file name

        if prev_threshold is None or threshold != prev_threshold:  # Check if the threshold has changed
            unmatched_flinn_products = []

            with open(output_file, 'w', newline='', encoding='utf-8') as master_file:
                writer = csv.writer(master_file)

                writer.writerow(['Flinn_product_category', 'Flinn_product_sub_category', 'Flinn_product_id', 'Flinn_product_name', 'Flinn_product_quantity', 'Flinn_product_price', 'Flinn_product_url', 'Flinn_image_url', 'Carolina_product_category', 'Carolina_product_sub_category', 'Carolina_product_id', 'Carolina_product_name', 'Carolina_product_quantity', 'Carolina_product_price', 'Carolina_product_url', 'Carolina_image_url', 'Carolina_Match_Score'])

                for original_flinn_row, flinn_word_set in flinn_products:
                    original_flinn_product = original_flinn_row['Flinn_product_name']
                    flinn_product_id = original_flinn_row['Flinn_product_id']
                    # if flinn_product_id in global_matched_products:
                    #     continue

                    flinn_row = flinn_csv[flinn_csv['Flinn_product_id'] == flinn_product_id]
                    desc_name = flinn_row.iloc[0]['Flinn_product_desc']
                    key_name = original_flinn_product
                    best_match = None
                    best_match_score = 0

                    for original_carolina_row, carolina_word_set in carolina_products:
                        title = original_carolina_row['Carolina_product_name']
                        carolina_desc = original_carolina_row['Carolina_product_desc']
                        combined_similarity = word_similarity(flinn_word_set, carolina_word_set)
                        if 0.3 <= threshold <= 0.4:
                            combined_similarity = float(re.search(r'\d*\.\d*', str(combined_similarity)).group())
                            if combined_similarity == threshold:
                                title_similarity_score = calculate_similarity(key_name, title, pooling_strategy='mean')
                                description_similarity_score = calculate_similarity(desc_name, carolina_desc, pooling_strategy='mean')
                                combined_similarity_score = (title_similarity_score + description_similarity_score) / 2

                                if combined_similarity_score >= best_match_score:
                                    best_match_score = combined_similarity_score
                                    best_match = original_carolina_row
                                break
                        else:
                            if combined_similarity >= best_match_score:
                                best_match_score = combined_similarity
                                best_match = original_carolina_row

                    flinn_colors = [color for color in color_names if
                                    re.search(rf'\b{color}\b', original_flinn_product, re.IGNORECASE)]
                    carolina_colors = [color for color in color_names if
                                      best_match and re.search(rf'\b{color}\b', best_match['Carolina_product_name'],
                                                               re.IGNORECASE)]

                    flinn_ml_mm = re.findall(r'\b\d+(\.\d+)?\s*(mL|mm)\b', original_flinn_product, re.IGNORECASE)
                    carolina_ml_mm = re.findall(r'\b\d+(\.\d+)?\s*(mL|mm)\b', best_match['Carolina_product_name'],
                                               re.IGNORECASE) if best_match else []

                    if best_match_score >= threshold:
                        if set(flinn_colors) == set(carolina_colors) and set(flinn_ml_mm) == set(carolina_ml_mm):
                            writer.writerow([original_flinn_row['Flinn_product_category'], original_flinn_row['Flinn_product_sub_category'], original_flinn_row['Flinn_product_id'], original_flinn_product, original_flinn_row['Flinn_product_quantity'], original_flinn_row['Flinn_product_price'], original_flinn_row['Flinn_product_url'], original_flinn_row['Flinn_image_url'], best_match['Carolina_product_category'], best_match['Carolina_product_sub_category'], best_match['Carolina_product_id'], best_match['Carolina_product_name'], best_match['Carolina_product_quantity'], best_match['Carolina_product_price'], best_match['Carolina_product_url'], best_match['Carolina_image_url'], best_match_score])
                            print(f"{original_flinn_product} -> {best_match} (Match Score: {best_match_score}, Colors and mL/mm Match)")
                            matched_products.append((original_flinn_row, original_carolina_row, best_match_score))
                            # global_matched_products.add(flinn_product_id)
                        elif set(flinn_colors) == set(carolina_colors):
                            writer.writerow([original_flinn_row['Flinn_product_category'], original_flinn_row['Flinn_product_sub_category'], original_flinn_row['Flinn_product_id'], original_flinn_product, original_flinn_row['Flinn_product_quantity'], original_flinn_row['Flinn_product_price'], original_flinn_row['Flinn_product_url'], original_flinn_row['Flinn_image_url'], best_match['Carolina_product_category'], best_match['Carolina_product_sub_category'], best_match['Carolina_product_id'], best_match['Carolina_product_name'], best_match['Carolina_product_quantity'], best_match['Carolina_product_price'], best_match['Carolina_product_url'], best_match['Carolina_image_url'], best_match_score])
                            print(f"{original_flinn_product} -> {best_match} (Match Score: {best_match_score}, Colors Match, mL/mm Mismatch)")
                            matched_products.append((original_flinn_row, original_carolina_row, best_match_score))
                            # global_matched_products.add(flinn_product_id)
                        else:
                            writer.writerow([original_flinn_row['Flinn_product_category'], original_flinn_row['Flinn_product_sub_category'], original_flinn_row['Flinn_product_id'], original_flinn_product, original_flinn_row['Flinn_product_quantity'], original_flinn_row['Flinn_product_price'], original_flinn_row['Flinn_product_url'], original_flinn_row['Flinn_image_url'], best_match['Carolina_product_category'], best_match['Carolina_product_sub_category'], best_match['Carolina_product_id'], best_match['Carolina_product_name'], best_match['Carolina_product_quantity'], best_match['Carolina_product_price'], best_match['Carolina_product_url'], best_match['Carolina_image_url'], best_match_score])
                            print(f"{original_flinn_product} -> {best_match} (Match Score: {best_match_score}, Colors Mismatch)")
                            matched_products.append((original_flinn_row, original_carolina_row, best_match_score))
                            # global_matched_products.add(flinn_product_id)
                    else:
                        writer.writerow([original_flinn_row['Flinn_product_category'], original_flinn_row['Flinn_product_sub_category'], original_flinn_row['Flinn_product_id'], original_flinn_product, original_flinn_row['Flinn_product_quantity'], original_flinn_row['Flinn_product_price'], original_flinn_row['Flinn_product_url'], original_flinn_row['Flinn_image_url'], '', '', '', 'No good match found (Low match score)', '', '', '', '', 0])
                        print(f"{original_flinn_product} -> No good match found (Low match score)")
                        unmatched_flinn_products.append((original_flinn_row, flinn_word_set))
                # write_global_matched_products(global_matched_products)


            with open(output_file, 'r', encoding='utf-8') as master_file:
                reader = csv.DictReader(master_file)
                flinn_products = [(row, get_word_set(clean_text(row['Flinn_product_name']))) for row in reader if row['Carolina_product_name'] == 'No good match found (Low match score)']

            carolina_file_paths = os.path.join('Scrapping Scripts', 'Output', 'Carolina_Products.csv')

            with open(carolina_file_paths, 'r', encoding='utf-8') as carolina_file:
                carolina_reader = csv.DictReader(carolina_file)
                unmatched_carolina_products = []
                for carolina_row in carolina_reader:
                    carolina_product_name = carolina_row['Carolina_product_name']
                    if carolina_row not in [match[1] for match in matched_products]:
                        unmatched_carolina_products.append((carolina_row, get_word_set(clean_text(carolina_product_name))))

            carolina_products = unmatched_carolina_products
            prev_threshold = threshold
            threshold = round(threshold - threshold_decrement, 2)
            # write_threshold_log(prev_threshold)
    # driver.quit()
    return matched_products


flinn_file_path = os.path.join('Scrapping Scripts/Output', 'Flinn_Products.csv')
carolina_file_path = os.path.join('Scrapping Scripts/Output', 'Carolina_Products.csv')


with open(flinn_file_path, 'r', encoding='utf-8') as flinn_file, open(carolina_file_path, 'r', encoding='utf-8') as carolina_file:
    flinn_reader = csv.DictReader(flinn_file)
    carolina_reader = csv.DictReader(carolina_file)

    flinn_products = [(row, get_word_set(clean_text(row['Flinn_product_name']))) for row in flinn_reader]
    carolina_products = [(row, get_word_set(clean_text(row['Carolina_product_name']))) for row in carolina_reader]


initial_threshold = 0.8
threshold_decrement = 0.01
output_folder = 'FlinnVsCarolina'


matched_products = match_products(flinn_products, carolina_products, initial_threshold, threshold_decrement, output_folder)


def write_matched_products_to_csv(matched_products, output_folder):
    # Create the output directory if it doesn't exist
    os.makedirs(os.path.join('Output', 'temp', output_folder), exist_ok=True)

    final_output_file = os.path.join('Output', 'temp', output_folder, 'Matched_Products.csv')

    # Convert matched products to DataFrame for easier manipulation
    data = []
    for match in matched_products:
        flinn_product, carolina_product, match_score = match
        data.append({
            'Flinn_product_category': flinn_product['Flinn_product_category'],
            'Flinn_product_sub_category': flinn_product['Flinn_product_sub_category'],
            'Flinn_product_id': flinn_product['Flinn_product_id'],
            'Flinn_product_name': flinn_product['Flinn_product_name'],
            'Flinn_product_quantity': flinn_product['Flinn_product_quantity'],
            'Flinn_product_price': flinn_product['Flinn_product_price'],
            'Flinn_product_url': flinn_product['Flinn_product_url'],
            'Flinn_image_url': flinn_product['Flinn_image_url'],
            'Carolina_product_category': carolina_product['Carolina_product_category'],
            'Carolina_product_sub_category': carolina_product['Carolina_product_sub_category'],
            'Carolina_product_id': carolina_product['Carolina_product_id'],
            'Carolina_product_name': carolina_product['Carolina_product_name'],
            'Carolina_product_quantity': carolina_product['Carolina_product_quantity'],
            'Carolina_product_price': carolina_product['Carolina_product_price'],
            'Carolina_product_url': carolina_product['Carolina_product_url'],
            'Carolina_image_url': carolina_product['Carolina_image_url'],
            'Carolina_Match_Score': match_score
        })

    df = pd.DataFrame(data)
    df.drop_duplicates(subset=['Flinn_product_id', 'Carolina_product_id'], keep='first', inplace=True)
    df.to_csv(final_output_file, index=False)

    print(f"Final matched products have been saved to {final_output_file}")

write_matched_products_to_csv(matched_products, output_folder)


# final_output_file = os.path.join('Scrapping Scripts', 'Output', 'temp', output_folder, 'Matched_Products.csv')
# with open(final_output_file, 'w', newline='', encoding='utf-8') as final_file:
#     writer = csv.writer(final_file)
#     writer.writerow(['Flinn_product_category', 'Flinn_product_sub_category', 'Flinn_product_id', 'Flinn_product_name',
#                      'Flinn_product_quantity', 'Flinn_product_price', 'Flinn_product_url', 'Flinn_image_url', 'Carolina_product_category',
#                      'Carolina_product_sub_category', 'Carolina_product_id', 'Carolina_product_name',
#                      'Carolina_product_quantity',
#                      'Carolina_product_price', 'Carolina_product_url', 'Carolina_image_url', 'Carolina_Match_Score'])
#     for match in matched_products:
#         flinn_product, carolinar_product, match_score = match
#         writer.writerow([flinn_product['Flinn_product_category'], flinn_product['Flinn_product_sub_category'],
#                          flinn_product['Flinn_product_id'], flinn_product['Flinn_product_name'],
#                          flinn_product['Flinn_product_quantity'], flinn_product['Flinn_product_price'],
#                          flinn_product['Flinn_product_url'], flinn_product['Flinn_image_url'], carolinar_product['Carolina_product_category'],
#                          carolinar_product['Carolina_product_sub_category'], carolinar_product['Carolina_product_id'],
#                          carolinar_product['Carolina_product_name'], carolinar_product['Carolina_product_quantity'],
#                          carolinar_product['Carolina_product_price'], carolinar_product['Carolina_product_url'],
#                          carolinar_product['Carolina_image_url'], match_score])
#
# print(f"Final matched products have been saved to {final_output_file}")
