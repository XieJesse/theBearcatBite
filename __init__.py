import requests
from flask import Flask, render_template, request, redirect
import db
import os
from google.cloud import vision

app = Flask(__name__)


@app.route("/")
def home():
    db.update_db()
    database = (db.get_db())
    return render_template("index.html",database = database)

if __name__ == "__main__":
    # Define HTTP Headers
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.97 Safari/537.36",
    }
    client = vision.ImageAnnotatorClient()

    dining_hall_url = 'https://binghamton.sodexomyway.com/dining-near-me/c4-dining-hall'

    app.debug = True
    app.run()
