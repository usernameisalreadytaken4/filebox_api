from flask_sqlalchemy import SQLAlchemy
import os
from flask import Flask, jsonify, request, make_response, send_from_directory, abort
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
import datetime
import uuid
from functools import wraps


app = Flask(__name__)
db = SQLAlchemy(app)

basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SECRET_KEY'] = 'thisissecret'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'app.db')
app.config['MAX_CONTENT_LENGTH'] = 64*1024*1024
app.config['UPLOAD_FOLDER'] = os.path.join(basedir, 'storage')


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, index=True)
    password = db.Column(db.String(50))
    admin = db.Column(db.Boolean)


class Folder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(32), index=True)
    parent = db.Column(db.String(1024))
    path = db.Column(db.String(1024))
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'))


class File(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime)
    public_name = db.Column(db.String(64))
    inner_name = db.Column(db.String(128), index=True)
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    folder_id = db.Column(db.Integer, db.ForeignKey('folder.id'))
    personal_link = db.Column(db.String(512))
    download_count = db.Column(db.Integer, default=0)

    def upload_file(self, request, owner_id, folder):
        file = request.files['multipart/form-data']
        self.timestamp = datetime.datetime.utcnow()
        self.public_name = file.filename
        self.folder_id = folder.id
        self.owner_id = owner_id
        self.inner_name = f'{self.owner_id}_{self.folder_id}_{self.public_name}'
        self.personal_link = f'{folder.path}/{self.inner_name}'
        check_file = File.query.filter_by(folder_id=self.id, owner_id=self.owner_id,
                                          public_name=self.public_name, inner_name=self.inner_name).first()
        if check_file is not None:
            return False
        db.session.add(self)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], self.inner_name))
        db.session.commit()
        return self

    @staticmethod
    def delete_file(request, owner_id):
        data = request.get_json()
        folder = Folder.query.filter_by(path=data['path'], owner_id=owner_id).first()
        if folder is None:
            return None
        file = File.query.filter_by(folder_id=folder.id, owner_id=owner_id, public_name=data['filename']).first()
        if file is None:
            return None
        check_public_links = PublicLinks.query.filter_by(file_id=file.id).first()
        if check_public_links.file_id:
            db.session.delete(check_public_links)
        db.session.delete(file)
        db.session.commit()
        real_file = os.path.join(app.config['UPLOAD_FOLDER'], file.inner_name)
        os.remove(real_file)
        return file

    @staticmethod
    def move_file(request, owner_id):
        data = request.get_json()
        current_folder = Folder.query.filter_by(path=data['oldpath'], owner_id=owner_id).first()
        new_folder = Folder.query.filter_by(path=data['newpath'], owner_id=owner_id).first()
        if current_folder.id is None or new_folder.id is None:
            return False
        file = File.query.filter_by(folder_id=current_folder.id, owner_id=owner_id, public_name=data['filename']).first()
        file.folder_id = new_folder.id
        new_inner_name = f'{file.owner_id}_{file.folder_id}_{file.public_name}'
        os.rename(os.path.join(app.config['UPLOAD_FOLDER'], file.inner_name),
                  os.path.join(app.config['UPLOAD_FOLDER'], file.inner_name))
        file.inner_name = new_inner_name
        db.session.commit()
        return True

    @staticmethod
    def download_file(request, owner_id):
        data = request.get_json()
        folder = Folder.query.filter_by(path=data['path'], owner_id=owner_id).first()
        file = File.query.filter_by(public_name=data['filename'], folder_id=folder.id, owner_id=owner_id).first()
        if file is None or folder is None:
            return False
        file.download_count += 1
        db.session.commit()
        return file


class PublicLinks(db.Model):
    upload_time = db.Column(db.DateTime)
    expire = db.Column(db.DateTime)
    file_id = db.Column(db.Integer, db.ForeignKey('file.id'), primary_key=True)
    link = db.Column(db.String(512), unique=True)

    def share_file(self, request, owner_id):
        data = request.get_json()
        folder = Folder.query.filter_by(path=data['path'], owner_id=owner_id).first()
        file = File.query.filter_by(public_name=data['filename'], folder_id=folder.id, owner_id=owner_id).first()
        if file is None:
            return False
        check_file = PublicLinks.query.filter_by(file_id=file.id).first()
        if check_file:
            db.session.delete(check_file)
            db.session.commit()
        self.upload_time = datetime.datetime.utcnow()
        self.expire = self.upload_time + datetime.timedelta(minutes=int(data['time']))
        self.file_id = file.id
        self.link = f'{str(uuid.uuid4())}/{file.public_name}'
        db.session.add(self)
        db.session.commit()
        return self


def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if 'x-access-token' in request.headers:
            token = request.headers['x-access-token']
        if not token:
            return jsonify({'message': 'Token is missing!'}), 401

        try:
            data = jwt.decode(token, app.config['SECRET_KEY'])
            current_user = User.query.filter_by(name=data['name']).first()
        except:
            return jsonify({'message': 'token is invalid!'}), 401
        return f(current_user, *args, **kwargs)
    return decorated


@app.route('/user', methods=['POST'])
def create_user():
    data = request.get_json()
    hashed_password = generate_password_hash(data['password'], method='sha256')
    new_user = User(name=data['name'], password=hashed_password, admin=False)
    db.session.add(new_user)
    new_user = User.query.filter_by(name=data['name']).first()
    default_folder = Folder(name=new_user.name, parent=None, path=new_user.name, owner_id=new_user.id)
    db.session.add(default_folder)
    db.session.commit()
    return jsonify({'message': 'user has been created with default folder'})


@app.route('/folders', methods=['VIEW'])
@token_required
def user_folders(current_user):
    data = request.get_json()
    folder = Folder.query.filter_by(path=data["path"], owner_id=current_user.id).first()
    if folder is None:
        return jsonify({"message": "такой папки не существует"})
    files_in = File.query.filter_by(folder_id=folder.id).all()
    folders_in = Folder.query.filter_by(parent=folder.id)
    folder_data = {}
    folder_data['current_folder'] = folder.name
    folder_data['parent_folder'] = folder.parent
    folder_data['path'] = folder.path
    folder_data['folders_in'] = [folder.name for folder in folders_in] or 'folders is not created'
    folder_data['files_in'] = [file.public_name for file in files_in] or 'files is not uploaded'
    return jsonify(folder_data)


@app.route('/folders', methods=['POST'])
@token_required
def create_folder(current_user):
    data = request.get_json()
    current_folder = Folder.query.filter_by(path=data['path'], owner_id=current_user.id).first()
    if current_folder is None:
        return jsonify({"message": "такой папки не существует"})
    check_folder = Folder.query.filter_by(name=data['name'], path=f'{data["path"]}/{data["name"]}').first()
    if check_folder is not None:
        return jsonify({"message": "такая папка уже есть"})
    new_folder = Folder(parent=current_folder.id, owner_id=current_user.id,
                        name=data['name'], path=f'{data["path"]}/{data["name"]}')
    db.session.add(new_folder)
    db.session.commit()
    return jsonify({'message': "папка создана"})


# теоретически наверно можно сделать через закодирования файла в Base64 и послать уже комплексно
# например {"folder": "<folder_name>", "file_name": "<file_name>", "file": "<огромная Base64 строка>"}
@app.route('/upload_file/<path:folders>', methods=['POST'])
@token_required
def upload_file(current_user, folders):
    folder = Folder.query.filter_by(path=folders, owner_id=current_user.id).first()
    if folder is None:
        return jsonify({"message": "folder has not found"})
    file = File()
    file = file.upload_file(request, current_user.id, folder)
    if file is False:
        return jsonify({"message": "file already exists"})
    return jsonify({"file": file.public_name, "message": "file has been uploaded"})


@app.route('/files', methods=['DELETE'])
@token_required
def delete_file(current_user):
    file = File.delete_file(request, current_user.id)
    if file is None:
        return jsonify({"message": "file or folder has not found"})
    return jsonify({"file": file.public_name, "message": "has been deleted"})


@app.route('/files', methods=['PUT'])  # можно и COPY, один хрен
@token_required
def move_file(current_user):
    file = File.move_file(request, current_user.id)
    if file is False:
        return jsonify({"message": "current folder or new folder is not available"})
    else:
        return jsonify({"message": "file has been moved"})


@app.route('/files', methods=['LINK'])
@token_required
def download_file(current_user):
    file = File.download_file(request, current_user.id)
    return jsonify({"your_link": file.personal_link, "download count": file.download_count})


@app.route('/<path:personal_link>', methods=['GET'])
@token_required
def get_file(current_user, personal_link):
    filename = personal_link.split('/')[-1]
    file = File.query.filter_by(personal_link=personal_link, owner_id=current_user.id).first()
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename,
                               as_attachment=True, attachment_filename=file.public_name)


@app.route('/share', methods=['LINK'])
@token_required
def share_file(current_user):
    file = PublicLinks()
    file = file.share_file(request, current_user.id)
    if file is False:
        return jsonify({"message": "file is not found"})
    link_data = {}
    link_data['upload_time'] = file.upload_time
    link_data['expiration_time'] = file.expire
    link_data['public_link'] = file.link
    return jsonify(link_data)


@app.route('/s/<path:public_link>', methods=['GET'])
def get_shared_file(public_link):
    print(public_link)
    link_meta_data = PublicLinks.query.filter_by(link=public_link).first()
    current_time = datetime.datetime.utcnow()
    if current_time > link_meta_data.expire:
        abort(404)
    file = File.query.filter_by(id=link_meta_data.file_id).first()
    filename = file.inner_name
    file.download_count += 1
    db.session.delete(link_meta_data)
    db.session.commit()
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename,
                               as_attachment=True, attachment_filename=file.public_name)


@app.route('/login')
def login():
    auth = request.authorization
    if not auth or not auth.username or not auth.password:
        return make_response('Could not verify', 401, {'WWW-Authenticate': 'Basic realm="Login required"'})
    user = User.query.filter_by(name=auth.username).first()
    if not user:
        return make_response('Could not verify', 401, {'WWW-Authenticate': 'Basic realm="Login required"'})

    if check_password_hash(user.password, auth.password):
        token = jwt.encode({'name': user.name, 'exp': datetime.datetime.utcnow() + datetime.timedelta(minutes=120)}, app.config['SECRET_KEY'])
        return jsonify({'token': token.decode('UTF-8')})


if __name__ == '__main__':
    db.drop_all()
    db.session.commit()
    db.create_all()
    db.session.commit()
