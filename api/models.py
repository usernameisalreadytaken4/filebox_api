import os
import datetime
import base64
import uuid
from api import app, db
from werkzeug.security import generate_password_hash


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, index=True)
    password = db.Column(db.String(50))
    admin = db.Column(db.Boolean)

    @staticmethod
    def create_user(name, password):
        check_user = User.query.filter_by(name=name)
        if check_user:
            return {"message": "username is already exists. please choose another username"}
        hashed_password = generate_password_hash(password, method='sha256')
        new_user = User(name=name, password=hashed_password, admin=False)
        db.session.add(new_user)
        new_user = User.query.filter_by(name=name).first()
        default_folder = Folder(name=new_user.name, parent=None, path=new_user.name, owner_id=new_user.id)
        db.session.add(default_folder)
        db.session.commit()
        return {'message': 'user has been created with default folder'}


class Folder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(32), index=True)
    parent = db.Column(db.String(1024))
    path = db.Column(db.String(1024))
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'))

    @staticmethod
    def user_folders(path, owner_id):
        folder = Folder.query.filter_by(path=path, owner_id=owner_id).first()
        if folder is None:
            return {"message": "folder is not exists"}
        files_in = File.query.filter_by(folder_id=folder.id).all()
        folders_in = Folder.query.filter_by(parent=folder.id)
        folder_data = {}
        folder_data['current_folder'] = folder.name
        folder_data['parent_folder'] = folder.parent
        folder_data['path'] = folder.path
        folder_data['folders_in'] = [folder.name for folder in folders_in] or 'folders is not created'
        folder_data['files_in'] = [file.public_name for file in files_in] or 'files is not uploaded'
        return folder_data

    @staticmethod
    def create_folder(name, path, owner_id):
        current_folder = Folder.query.filter_by(path=path, owner_id=owner_id).first()
        if current_folder is None:
            return {"message": "folder is not exists"}
        check_folder = Folder.query.filter_by(name=name, path=f'{path}/{name}').first()
        if check_folder is not None:
            return {"message": "folder is exists"}
        new_folder = Folder(parent=current_folder.id, owner_id=owner_id,
                            name=name, path=f'{path}/{name}')
        db.session.add(new_folder)
        db.session.commit()
        return {'message': "folder is created"}


class File(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime)
    public_name = db.Column(db.String(64))
    inner_name = db.Column(db.String(128), index=True)
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    folder_id = db.Column(db.Integer, db.ForeignKey('folder.id'))
    personal_link = db.Column(db.String(512))
    download_count = db.Column(db.Integer, default=0)

    def upload_file(self, encoded_file, filename, owner_id, folder):
        self.timestamp = datetime.datetime.utcnow()
        self.public_name = filename
        self.folder_id = folder.id
        self.owner_id = owner_id
        self.inner_name = f'{self.owner_id}_{self.folder_id}_{self.public_name}'
        self.personal_link = f'{folder.path}/{self.inner_name}'
        print('пизда ' * 10)
        check_file = File.query.filter_by(folder_id=self.folder_id, owner_id=self.owner_id,
                                          public_name=self.public_name, inner_name=self.inner_name).first()
        if check_file:
            return {"message": "file already exists"}
        db.session.add(self)
        with open(f'{app.config["UPLOAD_FOLDER"]}/{self.inner_name}', "wb") as file:
            file.write(base64.decodebytes(bytes(encoded_file.encode())))
        db.session.commit()
        return {"file": file.public_name, "message": "file has been uploaded"}

    @staticmethod
    def delete_file(path, filename, owner_id):
        folder = Folder.query.filter_by(path=path, owner_id=owner_id).first()
        if folder is None:
            return {"message": "folder has not found"}
        file = File.query.filter_by(folder_id=folder.id, owner_id=owner_id, public_name=filename).first()
        if file is None:
            return {"message": "file has not found"}
        check_public_links = PublicLinks.query.filter_by(file_id=file.id).first()
        if check_public_links:
            db.session.delete(check_public_links)
        db.session.delete(file)
        db.session.commit()
        real_file = os.path.join(app.config['UPLOAD_FOLDER'], file.inner_name)
        os.remove(real_file)
        return {"file": file.public_name, "message": "has been deleted"}

    @staticmethod
    def move_file(oldpath, newpath, filename, owner_id):
        current_folder = Folder.query.filter_by(path=oldpath, owner_id=owner_id).first()
        if current_folder is None:
            return {"message": "folder is not available"}
        new_folder = Folder.query.filter_by(path=newpath, owner_id=owner_id).first()
        if new_folder is None:
            return {"message": "destination folder is not available"}
        file = File.query.filter_by(folder_id=current_folder.id, owner_id=owner_id, public_name=filename).first()
        if file is None:
            return {"message": "file is not available"}
        file.folder_id = new_folder.id
        new_inner_name = f'{file.owner_id}_{file.folder_id}_{file.public_name}'
        os.rename(os.path.join(app.config['UPLOAD_FOLDER'], file.inner_name),
                  os.path.join(app.config['UPLOAD_FOLDER'], new_inner_name))
        file.inner_name = new_inner_name
        db.session.commit()
        return {"message": "file has been moved"}

    @staticmethod
    def download_file(path, filename, owner_id):
        folder = Folder.query.filter_by(path=path, owner_id=owner_id).first()
        file = File.query.filter_by(public_name=filename, folder_id=folder.id, owner_id=owner_id).first()
        if file is None or folder is None:
            return False
        file.download_count += 1
        count = file.download_count
        db.session.commit()
        with open(f'{app.config["UPLOAD_FOLDER"]}/{file.inner_name}', "rb") as file:
            encoded_file = base64.b64encode(file.read())
        return {"download_count": count, "file": encoded_file.decode()}


class PublicLinks(db.Model):
    upload_time = db.Column(db.DateTime)
    expire = db.Column(db.DateTime)
    file_id = db.Column(db.Integer, db.ForeignKey('file.id'), primary_key=True)
    link = db.Column(db.String(512), unique=True)

    def share_file(self, path, filename, time, owner_id):
        folder = Folder.query.filter_by(path=path, owner_id=owner_id).first()
        file = File.query.filter_by(public_name=filename, folder_id=folder.id, owner_id=owner_id).first()
        if file is None:
            return {"message": "file is not found"}
        check_file = PublicLinks.query.filter_by(file_id=file.id).first()
        if check_file:
            db.session.delete(check_file)
            db.session.commit()
        self.upload_time = datetime.datetime.utcnow()
        self.expire = self.upload_time + datetime.timedelta(minutes=int(time))
        self.file_id = file.id
        self.link = f'{str(uuid.uuid4())}/{file.public_name}'
        db.session.add(self)
        db.session.commit()
        link_data = {}
        link_data['upload_time'] = self.upload_time
        link_data['expiration_time'] = self.expire
        link_data['public_link'] = self.link
        return link_data


if __name__ == '__main__':
    db.drop_all()
    db.session.commit()
    db.create_all()
    db.session.commit()
