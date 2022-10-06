from bs4 import BeautifulSoup
import requests
import fitz
from PIL import Image
import io
from google.cloud import vision
import os

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "./keys/bearcatbite.json"

def download_pdf(url, file_name, headers):
    # Send GET request
    response = requests.get(url, headers=headers)
    # Save the image
    if response.status_code == 200:
        with open(file_name, "wb") as f:
            f.write(response.content)
    else:
        print(response.status_code)

if __name__ == "__main__":
    # Define HTTP Headers
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.97 Safari/537.36",
    }

    # Define pdf file name
    file_name = "menus.pdf"
    # Get url of c4 menu site
    c4 = 'https://binghamton.sodexomyway.com/dining-near-me/c4-dining-hall'
    reqs = requests.get(c4)
    # Extract url information from page
    soup = BeautifulSoup(reqs.text, 'html.parser')
    # Initialize google cloud vision api
    client = vision.ImageAnnotatorClient()

    menus = {}
    days = ["Sunday","Monday","Tuesday","Wednesday","Thursday","Friday","Saturday"]
    # loop through days of the week to get links
    for day in days:
        menus[day] = {}
        try:
            menus[day]["url"] = soup.find('a',string=day).get('href')
        except:
            menus[day]["url"] = ""
        if (menus[day]["url"] != ""):
            url = menus[day]["url"]
            download_pdf("https:"+url, file_name, headers)
            pdf_file = fitz.open(file_name)


            for page_index in range(len(pdf_file)):
            # get the page itself
                page = pdf_file[page_index]
                # get image list
                image_list = page.get_images()
                # printing number of images found in this page
                if image_list:
                    print(f"Image {len(image_list)} on page {page_index}")
                else:
                    print("[!] No images found on page", page_index)
                for image_index, img in enumerate(image_list, start=1):
                    # get the XREF of the image
                    xref = img[0]
                    # extract the image bytes
                    base_image = pdf_file.extract_image(xref)
                    image_bytes = base_image["image"]
                    # get the image extension
                    image_ext = base_image["ext"]
                    # load it to PIL
                    image = Image.open(io.BytesIO(image_bytes))
                    # save it to local disk
                    image.save(open(f"images/c4{day}{page_index+1}.{image_ext}", "wb"))
                    image_path = "images/c4"+day+str(page_index+1)+".jpeg"

                    # google cloud vision api

                    with io.open(image_path, 'rb') as image_file:
                            content = image_file.read()

                    image = vision.Image(content=content)
                    # find text in image
                    response = client.document_text_detection(image=image)


                    menu_type = ""
                    menu = []
                    prices = []
                    extra_data = []

                    for page in response.full_text_annotation.pages:
                        for block in page.blocks:
                            for paragraph in block.paragraphs:
                                p = ''
                                for word in paragraph.words:
                                    word_text = ''.join([
                                        symbol.text for symbol in word.symbols
                                    ])
                                    p += word_text+" "
                                if ((p == "* ") or ("If you have a food allergy" in p) or ("buns available" in p) or (p == "Today's Special : ") or ("cooked to order " in p) or ("We may experience " in p) or ("= Vegan " in p) or ("= Vegetarian " in p) or (p == "Vegetarian ") or (p == "X ") or (p == "V ")):
                                    continue
                                if ("SIMPLE" in p):
                                    menu_type = "Simple Servings"
                                    continue
                                if ("BREAKFAST" in p):
                                    menu_type = "Breakfast"
                                    continue
                                if ("LUNCH" in p):
                                    menu_type = "Lunch"
                                    continue
                                if ("BRUNCH" in p):
                                    menu_type = "Brunch"
                                    continue
                                if ("DINNER" in p):
                                    menu_type = "Dinner"
                                    continue
                                if ("PIZZA" in p):
                                    menu_type = "Pizza"
                                    continue
                                if ("FROM THE GRILL" in p):
                                    menu_type = "Grill"
                                    continue
                                if ("PASTA" in p):
                                    menu_type = "Pasta"
                                    continue
                                if ("TODAY'S SOUP" in p):
                                    menu_type = "Soup"
                                    continue
                                if ("Contains" in p):
                                    extra_data[-1] = p
                                    continue
                                if ("$" in p):
                                    temp_index = 0
                                    index = 1
                                    while (index < len(p)):
                                        if (p[index] == '$'):
                                            prices.append(p[temp_index:index])
                                            temp_index = index
                                        index += 1
                                    prices.append(p[temp_index:index])
                                else:
                                    menu.append(p)
                                    extra_data.append("")

                    menus[day][menu_type] = {}
                    menus[day][menu_type]["menu"] = menu
                    menus[day][menu_type]["prices"] = prices
                    menus[day][menu_type]["extra_data"] = extra_data

    print(menus)
