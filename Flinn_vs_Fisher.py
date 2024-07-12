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
import glob



log_dir = r'Output/temp'
log_file = 'web_scraping_Fisher.log'

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
#     file_path = os.path.join('Output', 'temp', 'fisher_threshold_log.txt')
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
#     file_path = os.path.join(output_dir, 'fisher_threshold_log.txt')
#     with open(file_path, 'a', encoding='utf-8') as file:
#         file.write(f"{threshold}\n")
#
#
# def read_global_matched_products():
#     try:
#         with open('Output/temp/global_matched_fisher_products.txt', 'r') as file:
#             global_matched_products = set(file.read().splitlines())
#         return global_matched_products
#     except FileNotFoundError:
#         return set()
#
# def write_global_matched_products(matched_products):
#     output_dir = os.path.join('Output', 'temp')
#     if not os.path.exists(output_dir):
#         os.makedirs(output_dir)
#     file_path = os.path.join(output_dir, 'global_matched_fisher_products.txt')
#     with open(file_path, 'w') as file:
#         for product_id in matched_products:
#             file.write(f"{product_id}\n")


def fetch_fisher_product_ids(driver, key_name, retry_attempts=3):
    for attempt in range(retry_attempts):
        try:
            driver.get('https://www.fishersci.com/us/en/home.html')
            search_element = WebDriverWait(driver, 20).until(
                EC.element_to_be_clickable((By.NAME, 'keyword'))
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
            results_number = soup.find_all('h3', class_='result_title')
            base_url = 'https://www.fishersci.com'
            headers = {
                'authority': 'www.fishersci.com',
                'method': 'GET',
                'path': '/us/en/home.html',
                'scheme': 'https',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                # 'Accept-Encoding': 'gzip, deflate, br, zstd',
                'Accept-Language': 'en-US,en;q=0.9',
                'Cache-Control': 'max-age=0',
                # 'Cookie': 'new_hf=true; new_cart=true; new_overlay=true; f_num=gmr; estore=estore-scientific; mdLogger=false; kampyle_userid=3cc8-fbfb-d62f-9006-dc00-3c93-3bdc-21c7; notice_preferences=2:; notice_gdpr_prefs=0,1,2:; cmapi_cookie_privacy=permit 1,2,3; s_vi=[CS]v1|330F088F363E0F9D-40001AC782A03632[CE]; s_ecid=MCMID%7C37161450081914606704547458763525740027; _gcl_au=1.1.1721032353.1713246496; QuantumMetricUserID=833703007cfee3fe1bd5ef1002d272d4; _hjSessionUser_341846=eyJpZCI6IjZlMzQ0MDQ1LWNkZTMtNWE1NS05YzczLTNhNTc2NDc1NzkxNSIsImNyZWF0ZWQiOjE3MTMyNDY0OTU2NjAsImV4aXN0aW5nIjp0cnVlfQ==; aam_uuid=40520749103498727913797215346890034770; WCXUID=35760512971517138714287; preventSingleResultRedirect=true; _gid=GA1.2.273275572.1714052867; locale=en_US; usertype=G; formSecurity=sv2cer9z3ul; akacd_FS_US_ProdA_Search_LucidWorks=3891575502~rv=10~id=1ff70e092d28aa94c023c341544a4939; AMCVS_8FED67C25245B39C0A490D4C%40AdobeOrg=1; AMCV_8FED67C25245B39C0A490D4C%40AdobeOrg=359503849%7CMCIDTS%7C19839%7CMCMID%7C37161450081914606704547458763525740027%7CMCAAMLH-1714727504%7C12%7CMCAAMB-1714727504%7CRKhpRz8krg2tLO6pguXWp5olkAcUniQYPHaMWWgdJ3xzPWQmdj0y%7CMCOPTOUT-1714129904s%7CNONE%7CMCAID%7C330F088F363E0F9D-40001AC782A03632%7CvVersion%7C5.0.1%7CMCCIDH%7C-1997303517; akacd_FS_Prod_AWS_EKS=3891575503~rv=70~id=78d608c4b1e6e7d51523efc10909b204; BIGipServerwww.fishersci.com_magellan_pool=1288357898.37919.0000; vcCookie=1; testTLD=test; WCXSID=00007737851171412270517166666666; userTypeDescription=guest; akacd_FS_Prod_AWS_EKS_Users=3891575503~rv=48~id=dc1fd6e52d24b3f40fdfb308193fcccc; memberId_AAM=; at_check=true; PFM=unsorted; accountId_AAM=Guest%20or%20No%20Account%20Chosen; com.ibm.commerce.ubx.idsync.DSPID_ADOBE%2CaaUserId%2CmcId%2Cx1VisitorId=com.ibm.commerce.ubx.idsync.DSPID_ADOBE%2CaaUserId%2CmcId%2Cx1VisitorId; bm_mi=A1B64201425E6D725F37E26F190F73BC~YAAQdDkgFzxaqBWPAQAAnwmtGRf3pU/gt8nqSvSytoynTAstbxQLcdnkVfrk/0OKxnml3vjgEntEWpB+M2XlBxZsM13g1AEyg9nuqwvUGjhDYuZMkc6z8L++DodS2lEV4/37mFfAVuY9b84NUVbJkVACBWH3RPqEICroDl0/k6EmjfIwIYc11l/tM7FM7bzwMx1V/DwdG8WB9YyKHIqIkX2sXTGSc1sLQRgYSqRTpKDiu+tCS3zuuoROAZQZUXR/30SG2C0raPkXlHfmic8ZPqauVPl2qvA5v6uK67s1LCpKHnd67qIzzzW1wGBBIbKB0VM4yyv31mecUGaNuEM=~1; WCXSID_expiry=1714123073316; TAsessionID=6bfaa024-0300-4019-8b07-e8294456460c|EXISTING; _hjSession_341846=eyJpZCI6Ijk2MGRmZTRjLWU4ZTUtNDRkZC1iYmJhLTZlYzUwMWYwYzc3NyIsImMiOjE3MTQxMjYyNjMwMzAsInMiOjAsInIiOjAsInNiIjowLCJzciI6MCwic2UiOjAsImZzIjowLCJzcCI6MH0=; s_days_since_new_s=Less than 1 day; dmdbase_cdc=DBSET; QuantumMetricSessionID=69d1356ac01e048f5f2e8fe90226cf63; adcloud={%22_les_v%22:%22c%2Cy%2Cfishersci.com%2C1714128068%22}; notice_behavior=implied,eu; new_quote=true; new_checkout=gmr; cmapi_gtm_bl=; s_days_since_new=1714126681820; s_pers=%20s_fid%3D14A195C2B6AD3030-11BBF514B556C1B0%7C1871012895376%3B%20gpv_pn%3Dhome%7C1714128482190%3B; _ga_TX98RX25ZK=GS1.1.1714126263.5.1.1714126682.58.0.0; _ga=GA1.1.573004469.1713246496; kampyleUserSession=1714126682365; kampyleUserSessionsCount=10; kampyleSessionPageCounter=1; mbox=PC#a38a87586d78400a8f67559b29c65b00.41_0#1777371483|session#5dc60f80a46b42d390f715ea7176ed40#1714128124; ak_bmsc=D8688914345F53570EFBDCDD4A60A8BB~000000000000000000000000000000~YAAQdDkgF8McqxWPAQAAwIXpGReAE0uBCMsGdjRMkKYoLDb7Bpm/MGhth0UXa5X0rpiduwas4Om5wZcOH9ZoUsbbmto+a2KxIV1n6Z/ivcaTFzAqpFxZ83PqvbuFoiedM76WvdCjZ6RplHHBLAeEgSrxSMposV19B48xF4XVC3Ot075eZTolInyS46J7mdk9Vkry9zKM21ECZwzU9x/0I25NUlHsolsbxk0m24YyemvQQIfRlfSjxkZ48FNO6k/UkcdM9hsel3dAcrAP3M7xlfSDixy7kYlMDEUsHl0FVkNALiaWswNPNKuusEECCjS9DdH/R2MpwaklmzCtkF6crZAeU2N97rMnyo0zU8GGi7RKeyc6nDG6n29jSrBnnESZBOTDZPqyxVi/X8aROFdJDhy7WU6LiVGwRisdh0LTQ8+sSnhG6JqKC2fjIkGe5fWJCcsmdpLfHs+zdcgO14SzVyfYs5GqpE0Ae3mTBYAo8Ys7mdSmnxO54R+cLataBsJQlLBk6O39kJC5ApG3/GaP3VI=; bm_sv=89AECBB20820FF8B2CA64B2B79139709~YAAQdDkgF8QcqxWPAQAAwIXpGReyb4SruJ82mMiMatFUEaN0LKBtB/wAZ3bw3nDA5Blf/H39K6tLCG/y99qHj8Y7ucAjrkx9h2bQ6KtZxEEEhXKZZ+EUQCXkalj1WGqcjL9UJ4X6Hah5z1i7LJubD/cxpft3t48o9Yex/uMBY0o4c049YXQ7btPGWAo5m0lgS+iR3HYeVQ7KNeYqdAxfIawmr7Q+7JeYvGYlbIu6RUJdNUcKGts4RRkJps3X5DD95FtmEg==~1; cto_bundle=OOIu2V9SeEo2c0E0U3owbW01NmJYUlNpQ0pMZHo2UHhSVnRsd0p2UHJveGJNRyUyRiUyRlZPWklJJTJGTVVNdHBaSnh4QVRTVDBxaUpLdCUyQlhIU3ZLeThnNHVOU0tveE41MWVaJTJCdmJ2cHQ5OWt4VEY2RDNIUk43bTkwcWlWcUd1RUtKMUdLZEVJSmgxUzhGRlVBam1XYUVKWlhTNGl4eFJZaVdMckdCakU1elFETVVSVWFTVmFCN3NkZ0VxSXoxWEljcko2RWV4Und6Zkg4R3JNTGx6TThBaXJMMFFsZEpFQSUzRCUzRA; s_sess=%20s_cc%3Dtrue%3B%20s_sq%3Dthermofisherfishersciprod%253D%252526pid%25253Dhome%252526pidt%25253D1%252526oid%25253D%2525250A%25252520%25252520%25252520%25252520%25252520%25252520%25252520%25252520%25252520%25252520%25252520%25252520%25252520%25252520%25252520%25252520%25252520%25252520%25252520%25252520%25252520%25252520%25252520%25252520%25252520%25252520%25252520%25252520%25252520%25252520%25252520%25252520%25252520%25252520%25252520%25252520%25252520%25252520%25252520%25252520%25252520%25252520%25252520%25252520%2525250A%25252520%25252520%25252520%25252520%25252520%25252520%25252520%25252520%25252520%25252520%25252520%25252520%25252520%25252520%25252520%25252520%25252520%25252520%25252520%25252520%25252520%25252520%25252520%25252520%25252520%25252520%25252520%25252520%25252520%25252520%25252520%25252520%25252520%25252520%25252520%25252520%25252520%25252520%25252520%25252520%252526oidt%25253D3%252526ot%25253DSUBMIT%3B',
                'Priority': 'u=0, i',
                'Sec-Ch-Ua': '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
                'Sec-Ch-Ua-Mobile': '?0',
                'Sec-Ch-Ua-Platform': '"Windows"',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
                'Upgrade-Insecure-Requests': '1',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            }
            product_ids = []
            for single_data in results_number:
                url = f'{base_url}{single_data.a["href"]}'
                soup_req = get_soup(url, headers)
                code = soup_req.find('p', class_='rightProductCode').find('span', attrs={'itemprop': 'sku'}).text.strip()
                product_ids.append(code)
            return product_ids
        except TimeoutException as e:
            logging.error(f"TimeoutException: {e}")
            driver.save_screenshot('timeout_exception_screenshot.png')
        except Exception as e:
            logging.error(f"An error occurred: {e}")
        time.sleep(5)
    return []


def match_products(flinn_products, fisher_products, initial_threshold, threshold_decrement, output_folder):
    matched_products = []
    threshold = initial_threshold
    prev_threshold = None  # Initialize prev_threshold to None

    # Get the absolute path of the output folder
    output_folder_path = os.path.join('Output', 'temp', output_folder)

    # Create the output folder if it doesn't exist
    os.makedirs(output_folder_path, exist_ok=True)
    # completed_thresholds = read_threshold_log()
    # global_matched_products = read_global_matched_products()

    flinn_file_path = os.path.join('Output', 'Flinn_Products.csv')
    fisher_file_path = os.path.join('Output', 'Fisher_Products.csv')

    flinn_csv = pd.read_csv(flinn_file_path)
    fisher_csv = pd.read_csv(fisher_file_path)
    options = Options()
    options.add_argument("--headless")
    driver = webdriver.Chrome(options=options)

    while threshold >= 0:
        # if str(threshold) in completed_thresholds:
        #     print(f"Threshold {threshold} already processed. Skipping...")
        #     threshold = round(threshold - threshold_decrement, 2)
        #     continue
        print(f"Matching products with threshold: {threshold:.2f}")
        output_file = os.path.join(output_folder_path, f"FlinnVsFisher_{threshold:.2f}.csv")  # Round the threshold to 2 decimal places for the file name

        if prev_threshold is None or threshold != prev_threshold:  # Check if the threshold has changed
            unmatched_flinn_products = []

            with open(output_file, 'w', newline='', encoding='utf-8') as master_file:
                writer = csv.writer(master_file)

                writer.writerow(['Flinn_product_category', 'Flinn_product_sub_category', 'Flinn_product_id', 'Flinn_product_name', 'Flinn_product_quantity', 'Flinn_product_price', 'Flinn_product_url', 'Flinn_image_url', 'Fisher_product_category', 'Fisher_product_sub_category', 'Fisher_product_id', 'Fisher_product_name', 'Fisher_product_quantity', 'Fisher_product_price', 'Fisher_product_url', 'Fisher_image_url', 'Fisher_Match_Score'])

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

                    for original_fisher_row, fisher_word_set in fisher_products:
                        combined_similarity = word_similarity(flinn_word_set, fisher_word_set)
                        if 0.3 <= threshold <= 0.4:
                            combined_similarity = float(re.search(r'\d*\.\d*', str(combined_similarity)).group())
                            if combined_similarity == threshold:
                                product_ids = fetch_fisher_product_ids(driver, key_name)
                                if not product_ids:
                                    if combined_similarity >= best_match_score:
                                        best_match_score = combined_similarity
                                        best_match = original_fisher_row
                                    continue
                                for product_id in product_ids:
                                    fisher_row = fisher_csv[fisher_csv['Fisher_product_id'] == product_id]
                                    if not fisher_row.empty:
                                        fisher_title = fisher_row.iloc[0]['Fisher_product_name']
                                        fisher_description = fisher_row.iloc[0]['Fisher_product_desc']
                                        title_similarity_score = calculate_similarity(key_name, fisher_title,
                                                                                      pooling_strategy='mean')
                                        description_similarity_score = calculate_similarity(desc_name,
                                                                                            fisher_description,
                                                                                            pooling_strategy='mean')
                                        combined_similarity_score = (title_similarity_score + description_similarity_score) / 2

                                        if combined_similarity_score >= best_match_score:
                                            best_match_score = combined_similarity_score
                                            best_match = original_fisher_row
                                break
                        else:
                            if combined_similarity >= best_match_score:
                                best_match_score = combined_similarity
                                best_match = original_fisher_row

                    flinn_colors = [color for color in color_names if
                                    re.search(rf'\b{color}\b', original_flinn_product, re.IGNORECASE)]
                    fisher_colors = [color for color in color_names if
                                      best_match and re.search(rf'\b{color}\b', best_match['Fisher_product_name'],
                                                               re.IGNORECASE)]

                    flinn_ml_mm = re.findall(r'\b\d+(\.\d+)?\s*(mL|mm)\b', original_flinn_product, re.IGNORECASE)
                    fisher_ml_mm = re.findall(r'\b\d+(\.\d+)?\s*(mL|mm)\b', best_match['Fisher_product_name'],
                                               re.IGNORECASE) if best_match else []

                    if best_match_score >= threshold:
                        if set(flinn_colors) == set(fisher_colors) and set(flinn_ml_mm) == set(fisher_ml_mm):
                            writer.writerow([original_flinn_row['Flinn_product_category'], original_flinn_row['Flinn_product_sub_category'], original_flinn_row['Flinn_product_id'], original_flinn_product, original_flinn_row['Flinn_product_quantity'], original_flinn_row['Flinn_product_price'], original_flinn_row['Flinn_product_url'], original_flinn_row['Flinn_image_url'], best_match['Fisher_product_category'], best_match['Fisher_product_sub_category'], best_match['Fisher_product_id'], best_match['Fisher_product_name'], best_match['Fisher_product_quantity'], best_match['Fisher_product_price'], best_match['Fisher_product_url'], best_match['Fisher_image_url'], best_match_score])
                            print(f"{original_flinn_product} -> {best_match} (Match Score: {best_match_score}, Colors and mL/mm Match)")
                            matched_products.append((original_flinn_row, original_fisher_row, best_match_score))
                            # global_matched_products.add(flinn_product_id)
                        elif set(flinn_colors) == set(fisher_colors):
                            writer.writerow([original_flinn_row['Flinn_product_category'], original_flinn_row['Flinn_product_sub_category'], original_flinn_row['Flinn_product_id'], original_flinn_product, original_flinn_row['Flinn_product_quantity'], original_flinn_row['Flinn_product_price'], original_flinn_row['Flinn_product_url'], original_flinn_row['Flinn_image_url'], best_match['Fisher_product_category'], best_match['Fisher_product_sub_category'], best_match['Fisher_product_id'], best_match['Fisher_product_name'], best_match['Fisher_product_quantity'], best_match['Fisher_product_price'], best_match['Fisher_product_url'], best_match['Fisher_image_url'], best_match_score])
                            print(f"{original_flinn_product} -> {best_match} (Match Score: {best_match_score}, Colors Match, mL/mm Mismatch)")
                            matched_products.append((original_flinn_row, original_fisher_row, best_match_score))
                            # global_matched_products.add(flinn_product_id)
                        else:
                            writer.writerow([original_flinn_row['Flinn_product_category'], original_flinn_row['Flinn_product_sub_category'], original_flinn_row['Flinn_product_id'], original_flinn_product, original_flinn_row['Flinn_product_quantity'], original_flinn_row['Flinn_product_price'], original_flinn_row['Flinn_product_url'], original_flinn_row['Flinn_image_url'], best_match['Fisher_product_category'], best_match['Fisher_product_sub_category'], best_match['Fisher_product_id'], best_match['Fisher_product_name'], best_match['Fisher_product_quantity'], best_match['Fisher_product_price'], best_match['Fisher_product_url'], best_match['Fisher_image_url'], best_match_score])
                            print(f"{original_flinn_product} -> {best_match} (Match Score: {best_match_score}, Colors Mismatch)")
                            matched_products.append((original_flinn_row, original_fisher_row, best_match_score))
                            # global_matched_products.add(flinn_product_id)
                    else:
                        writer.writerow([original_flinn_row['Flinn_product_category'], original_flinn_row['Flinn_product_sub_category'], original_flinn_row['Flinn_product_id'], original_flinn_product, original_flinn_row['Flinn_product_quantity'], original_flinn_row['Flinn_product_price'], original_flinn_row['Flinn_product_url'], original_flinn_row['Flinn_image_url'], '', '', '', 'No good match found (Low match score)', '', '', '', '', 0])
                        print(f"{original_flinn_product} -> No good match found (Low match score)")
                        unmatched_flinn_products.append((original_flinn_row, flinn_word_set))
                # write_global_matched_products(global_matched_products)


            with open(output_file, 'r', encoding='utf-8') as master_file:
                reader = csv.DictReader(master_file)
                flinn_products = [(row, get_word_set(clean_text(row['Flinn_product_name']))) for row in reader if row['Fisher_product_name'] == 'No good match found (Low match score)']

            fisher_file_paths = os.path.join('Output', 'Fisher_Products.csv')

            with open(fisher_file_paths, 'r', encoding='utf-8') as fisher_file:
                fisher_reader = csv.DictReader(fisher_file)
                unmatched_fisher_products = []
                for fisher_row in fisher_reader:
                    fisher_product_name = fisher_row['Fisher_product_name']
                    if fisher_row not in [match[1] for match in matched_products]:
                        unmatched_fisher_products.append((fisher_row, get_word_set(clean_text(fisher_product_name))))

            fisher_products = unmatched_fisher_products
            prev_threshold = threshold
            threshold = round(threshold - threshold_decrement, 2)
            # write_threshold_log(prev_threshold)
    driver.quit()
    return matched_products


flinn_file_path = os.path.join('Output', 'Flinn_Products.csv')
fisher_file_path = os.path.join('Output', 'Fisher_Products.csv')


with open(flinn_file_path, 'r', encoding='utf-8') as flinn_file, open(fisher_file_path, 'r', encoding='utf-8') as fisher_file:
    flinn_reader = csv.DictReader(flinn_file)
    fisher_reader = csv.DictReader(fisher_file)

    flinn_products = [(row, get_word_set(clean_text(row['Flinn_product_name']))) for row in flinn_reader]
    fisher_products = [(row, get_word_set(clean_text(row['Fisher_product_name']))) for row in fisher_reader]


initial_threshold = 0.8
threshold_decrement = 0.01
output_folder = 'FlinnVsFisher'


# matched_products = match_products(flinn_products, fisher_products, initial_threshold, threshold_decrement, output_folder)
output_files = match_products(flinn_products, fisher_products, initial_threshold, threshold_decrement, output_folder)


output_csv_dir = r'Output/temp/FlinnVsFisher/*.csv'
csv_files = glob.glob(output_csv_dir)
dfs = []
for csv_file in csv_files:
    df = pd.read_csv(csv_file)
    dfs.append(df)
merged_df = pd.concat(dfs, ignore_index=True)
merged_df.drop_duplicates(subset=['Flinn_product_name', 'Flinn_product_id'], keep='first', inplace=True)
merged_output_file = 'Output/Matched_Products.csv'
merged_df.to_csv(merged_output_file, index=False)
print(f"Merged {len(csv_files)} CSV files into '{merged_output_file}'.")


# final_output_file = os.path.join('Scrapping Scripts', 'Output', 'temp', output_folder, 'Matched_Products.csv')
# with open(final_output_file, 'w', newline='', encoding='utf-8') as final_file:
#     writer = csv.writer(final_file)
#     writer.writerow(['Flinn_product_category', 'Flinn_product_sub_category', 'Flinn_product_id', 'Flinn_product_name',
#                      'Flinn_product_quantity', 'Flinn_product_price', 'Flinn_product_url', 'Flinn_image_url', 'Fisher_product_category',
#                      'Fisher_product_sub_category', 'Fisher_product_id', 'Fisher_product_name',
#                      'Fisher_product_quantity',
#                      'Fisher_product_price', 'Fisher_product_url', 'Fisher_image_url', 'Fisher_Match_Score'])
#     for match in matched_products:
#         flinn_product, fisher_product, match_score = match
#         writer.writerow([flinn_product['Flinn_product_category'], flinn_product['Flinn_product_sub_category'],
#                          flinn_product['Flinn_product_id'], flinn_product['Flinn_product_name'],
#                          flinn_product['Flinn_product_quantity'], flinn_product['Flinn_product_price'],
#                          flinn_product['Flinn_product_url'], flinn_product['Flinn_image_url'], fisher_product['Fisher_product_category'],
#                          fisher_product['Fisher_product_sub_category'], fisher_product['Fisher_product_id'],
#                          fisher_product['Fisher_product_name'], fisher_product['Fisher_product_quantity'],
#                          fisher_product['Fisher_product_price'], fisher_product['Fisher_product_url'],
#                          fisher_product['Fisher_image_url'], match_score])
#
# print(f"Final matched products have been saved to {final_output_file}")
