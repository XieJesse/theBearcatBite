import requests
from bs4 import BeautifulSoup
import fitz
from PIL import Image
import io
import datetime
from google.cloud import vision
import pymongo
import urllib.parse
import os
import firebase_admin
from firebase_admin import db

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "./keys/bearcatbite.json"

cred_obj = firebase_admin.credentials.Certificate('./keys/firebase.json')
default_app = firebase_admin.initialize_app(cred_obj, {
    'databaseURL': 'https://bearcatbite-42a16-default-rtdb.firebaseio.com/'
    })

days = ["Sunday","Monday","Tuesday","Wednesday","Thursday","Friday","Saturday"]

headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.97 Safari/537.36",
}
client = vision.ImageAnnotatorClient()

ref = db.reference("//")


def download_pdf(url, file_name, headers):
    # Send GET request
    response = requests.get(url, headers=headers)
    # Save the image
    if response.status_code == 200:
        with open(file_name, "wb") as f:
            f.write(response.content)
    else:
        print(response.status_code)

def get_menu(dining_hall_url):
    # Load url information
    reqs = requests.get(dining_hall_url)
    # Parse html
    text = reqs.text
    soup = BeautifulSoup(text, 'html.parser')

    menus = {}
    # loop through days of the week to get links
    for day in days:
        menus[day] = {}
        try:
            menus[day]["url"] = soup.find('a',string=day).get('href')
        except:
            menus[day]["url"] = ""
        if (menus[day]["url"] != ""):
            url = menus[day]["url"]
            download_pdf("https:"+url, "menus.pdf", headers)
            pdf_file = fitz.open("menus.pdf")


            for page_index in range(len(pdf_file)):
            # get the page itself
                page = pdf_file[page_index]
                # get image list
                image_list = page.get_images()
                # printing number of images found in this page
                if image_list:
                    print(f"Image on page {page_index}")
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
                                if ("Hash Bowl" in p):
                                    menu_type = "Hash Bowl"
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

                    if (menu_type == ""):
                        continue
                    menus[day][menu_type] = {}
                    menus[day][menu_type]["menu"] = menu
                    menus[day][menu_type]["prices"] = prices
                    menus[day][menu_type]["extra_data"] = extra_data
    return menus


def update_db():

    data = get_menu('https://binghamton.sodexomyway.com/dining-near-me/c4-dining-hall')

    database = db_without_keys()

    temp_date = datetime.date.today()
    curWeekday = (temp_date.weekday()+1)%7
    one_day = datetime.timedelta(days=1)
    dayInfo = {}
    done = False
    menuOrder = 0
    for index in range(curWeekday,7): # begin at current date
        if (data[days[index]]["url"] == ""):
            done = True
            break

        month_date_year = temp_date.isoformat() # get formatted date of corresponding day
        temp_date = temp_date + one_day # increment
        if month_date_year in database: # if date already exists in database
            print("exists")
            continue

        dayInfo[month_date_year] = {} # initialize object for date
        for menu in data[days[index]].keys():
            if (menu != 'url'):
                id = 0
                collectedInfo = {}
                collectedInfo["order"] = menuOrder
                menuOrder = menuOrder + 1
                for item_index in range(0,len(data[days[index]][menu]["menu"])):
                    # create object for each item
                    info = {
                                "price" : data[days[index]][menu]["prices"][item_index],
                                "extra_data" : data[days[index]][menu]["extra_data"][item_index],
                                "id" : id
                            }
                    id = id + 1
                    collectedInfo[data[days[index]][menu]["menu"][item_index]] = info # add menu item objects to larger menu object

                dayInfo[month_date_year][menu] = collectedInfo # add menu objects to date object
    if not done:
        for index in range(0,curWeekday): # loop to start
            if (data[days[index]]["url"] == ""):
                break

            month_date_year = temp_date.isoformat() # get formatted date of corresponding day
            temp_date = temp_date + one_day # increment

            if month_date_year in database:
                continue

            dayInfo[month_date_year] = {} # initialize object for date

            for menu in data[days[index]].keys():
                if (menu != 'url'):
                    id = 0
                    collectedInfo = {}
                    collectedInfo["order"] = menuOrder
                    menuOrder = menuOrder + 1
                    for item_index in range(0,len(data[days[index]][menu]["menu"])):
                        # create object for each item
                        info = {
                                    "price" : data[days[index]][menu]["prices"][item_index],
                                    "extra_data" : data[days[index]][menu]["extra_data"][item_index],
                                    "id" : id
                                }
                        id = id + 1
                        collectedInfo[data[days[index]][menu]["menu"][item_index]] = info # add menu item objects to larger menu object

                    dayInfo[month_date_year][menu] = collectedInfo # add menu objects to date object
    ref.push(dayInfo) # update database

def db_without_keys():
    database = ref.get()
    if (database is None):
        return ""
    dictionary = {}
    for key,value in database.items():
        for date, info in value.items():
            dictionary[date] = info
    return dictionary

def get_db():
    database = db_without_keys()
    if (database == ""):
        return ""
    else:
        orderedDatabase = {}
        for key,value in database.items():
            orderedDatabase[key] = {}
            sort = dict(sorted(value.items(), key=lambda menu:menu[1]["order"]))
            for menu,data in sort.items():
                orderedMenu = {}
                del data["order"]
                sortedItems = dict(sorted(data.items(),key=lambda x:x[1]["id"]))
                orderedDatabase[key][menu] = sortedItems

        #print(database.items())
        return orderedDatabase.items()
