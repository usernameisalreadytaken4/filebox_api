import datetime
from functools import wraps
import jwt
from flask import request, make_response
from flask_jsonrpc import jsonify, JSONRPC
from werkzeug.security import check_password_hash
from api import app
from .models import File, Folder, User, PublicLinks


def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if 'x-access-token' in request.headers:
            token = request.headers['x-access-token']
        if not token:
            return {'message': 'Token is missing!'}
        try:
            data = jwt.decode(token, app.config['SECRET_KEY'])
            current_user = User.query.filter_by(name=data['name']).first()
        except:
            return {'message': 'token is invalid!'}
        return f(current_user, *args, **kwargs)
    return decorated


jsonrpc = JSONRPC(app)


@jsonrpc.method('View.user')
@token_required
def user_folders(current_user, path):
    return Folder.user_folders(path=path, owner_id=current_user.id)


@jsonrpc.method('Create.folder')
@token_required
def create_folder(current_user, name, path):
    return Folder.create_folder(name=name, path=path, owner_id = current_user.id)


@jsonrpc.method('Upload.file')
@token_required
def upload_file(current_user, path, encoded_file, filename):
    folder = Folder.query.filter_by(path=path, owner_id=current_user.id).first()
    if folder is None:
        return {"message": "folder has not found"}
    file = File()
    return file.upload_file(encoded_file=encoded_file, filename=filename,
                            owner_id=current_user.id, folder=folder)


@jsonrpc.method('Move.file')
@token_required
def move_file(current_user, oldpath, newpath, filename):
    return File.move_file(oldpath=oldpath, newpath=newpath,
                          filename=filename, owner_id=current_user.id)


@jsonrpc.method('Get.file')
@token_required
def download_file(current_user, path, filename):
    return File.download_file(path=path, filename=filename, owner_id=current_user.id)


@jsonrpc.method('Delete.file')
@token_required
def delete_file(current_user, path, filename):
    return File.delete_file(path=path, filename=filename, owner_id=current_user.id)


@jsonrpc.method('Share.file')
@token_required
def share_file(current_user, path, filename, time):
    file = PublicLinks()
    return file.share_file(path=path, filename=filename, time=time, owner_id=current_user.id)


@jsonrpc.method('Create.user')
def create_user(username, password):
    return User.create_user(username, password)


@jsonrpc.method('Login.user')
def login(username, password):
    user = User.query.filter_by(name=username).first()
    if not user:
        return make_response('Could not verify', 401, {'WWW-Authenticate': 'Basic realm="Login required"'})

    if check_password_hash(user.password, password):
        token = jwt.encode({'name': user.name, 'exp': datetime.datetime.utcnow() + datetime.timedelta(minutes=120)}, app.config['SECRET_KEY'])
        return jsonify({'token': token.decode('UTF-8')})