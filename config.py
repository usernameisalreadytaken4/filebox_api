import os

basedir = os.path.abspath(os.path.dirname(__file__))
SECRET_KEY = 'thisissecret'
SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(basedir, 'app.db')
MAX_CONTENT_LENGTH = 64*1024*1024
UPLOAD_FOLDER = os.path.join(basedir, 'storage')