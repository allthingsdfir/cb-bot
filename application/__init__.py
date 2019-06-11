import datetime
import os

import pymongo
from flask import Flask

app = Flask(__name__)

# Application configuration
app.config['SECRET_KEY'] = '1w86x19c2tfaxmf3rdyiv65x5q1raa43p9psycqyaei56249m19fww614871'
app.config['DEFAULT_PASSWORD'] = "Doby4n62019!!!"
app.config['SESSION_TIMEOUT'] = datetime.timedelta(minutes=60)
app.config['TOKEN_TIMEOUT'] = datetime.timedelta(minutes=10)

# Database configuration
app.config['MONGO_CLIENT'] = pymongo.MongoClient('127.0.0.1', 5051)
app.config['DOBY_DB'] = app.config['MONGO_CLIENT'].doby

# Temporary directory folders
app.config['WEB_DIRECTORY'] = os.getcwd()
app.config['APPLICATION_DIRECTORY'] =  "{}/application".format(app.config['WEB_DIRECTORY'])
app.config['LIBRARIES_DIRECTORY'] =  "{}/libraries".format(app.config['APPLICATION_DIRECTORY'])
app.config['TEMP_DIRECTORY'] =  "{}/temp".format(app.config['WEB_DIRECTORY'])
app.config['UPLOAD_DIRECTORY'] =  "{}/upload".format(app.config['TEMP_DIRECTORY'])
app.config['LOG_DIRECTORY'] =  "{}/logs".format(app.config['TEMP_DIRECTORY'])
app.config['OUTPUT_DIRECTORY'] =  "/data/sweep_output".format(app.config['WEB_DIRECTORY'])

# Accepted extensions for Doby to upload
# This is not implemented yet, but can be implemented.
app.config['ALLOWED_EXTENSIONS'] = set(['exe', 'bat', 'cmd'])

from application.routes import main