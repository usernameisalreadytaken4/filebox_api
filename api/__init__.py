from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_jsonrpc import JSONRPC

app = Flask(__name__)
app.config.from_object('config')
db = SQLAlchemy(app)



from api import views, models
