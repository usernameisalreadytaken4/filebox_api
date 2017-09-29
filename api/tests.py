#!/usr/bin/env python
import os
import unittest
from config import basedir
import json
import base64


from api import app, db


TEST_DB = 'test.db'


class Tests(unittest.TestCase):

    def setUp(self):
        print('---------------------- RUNNING setUp')
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, TEST_DB)
        self.app = app.test_client()
        db.drop_all()
        db.create_all()

    def tearDown(self):
        pass

    ################################
    ######### supports #############
    ################################

    def create_user(self, username='default', password='value'):
        data = {
            "method": "Create.user",
            "jsonrpc" : "2.0",
            "params" : {"username": username, "password": password},
            "id" : 0
        }
        return self.app.post('/api', data=json.dumps(data), content_type='application/json')

    def login_user(self, username, password):
        data = {
            "method": "Login.user",
            "jsonrpc": "2.0",
            "params": {"username": username, "password": password},
            "id": 0
        }
        return self.app.post('/api', data=json.dumps(data), content_type='application/json')

    def get_token(self):
        self.create_user(username='vasya', password='pupkin')
        return json.loads(self.login_user(username='vasya', password='pupkin').data).get('token')

    def upload(self, token, filename):
        with open('/home/bobrovskiy/Downloads/default.png', 'rb') as image_file:
            file = base64.b64encode(image_file.read()).decode()
        data = {
            "jsonrpc": "2.0",
            "method": "Upload.file",
            "params": {"path": "vasya", "file": file, "filename": filename},
            "id": "1"}
        return self.app.post('/api', data=json.dumps(data), headers={'content-type': 'application/json', 'x-access-token': token})

    def make_folder(self, token, folder_name='folder1'):

        data = {
            "jsonrpc": "2.0",
            "method": "Create.folder",
            "params": {"path": "vasya", "name": folder_name},
            "id": "1"}
        return self.app.post('/api', data=json.dumps(data),
                                 headers={'content-type': 'application/json', 'x-access-token': token})


    ########### TESTS ###########

    def test_on_off(self):
        response = self.app.get('/api')
        self.assertEqual(response.status_code, 405)

    def test_create_user(self):
        response = self.create_user(username='user', password='ifailmylife')
        self.assertEqual(json.loads(response.data)['result'], {"message": "user has been created with default folder"})

    def test_create_dublicate_user(self):
        response1 = self.create_user(username='user2', password='ifailmylife')
        response2 = self.create_user(username='user2', password='ifailmylifetoo')
        self.assertEqual(json.loads(response1.data)['result'],  {"message": "user has been created with default folder"})
        self.assertEqual(json.loads(response2.data)['result'], {'message': 'username is already exists. please choose another username'})

    def create_folder(self):
        token = self.get_token()
        response = self.make_folder(token=token)
        self.assertEqual(json.loads(response.data)['result'], {'message': "folder is created"})

    def create_exists_folder(self):
        token = self.get_token()
        self.make_folder(token=token)
        data = {
            "jsonrpc": "2.0",
            "method": "Create.folder",
            "params": {"path": "vasya", "name": "folder1"},
            "id": "1"}
        response = self.app.post('/api', data=json.dumps(data),
                      headers={'content-type': 'application/json', 'x-access-token': token})
        self.assertEqual(json.loads(response.data)['result'], {"message": "folder is exists"})

    def create_folder_in_fake_directory(self):
        token = self.get_token()
        data = {
            "jsonrpc": "2.0",
            "method": "Create.folder",
            "params": {"path": "ne_vasya", "name": "folder1"},
            "id": "1"}
        response = self.app.post('/api', data=json.dumps(data),
                      headers={'content-type': 'application/json', 'x-access-token': token})

        self.assertEqual(json.loads(response.data)['result'], {"message": "you choose wrong folder path"})

    def upload_file(self):
        token = self.get_token()
        filename = 'default.png'
        response = self.upload(token=token, filename=filename)
        self.assertEqual(json.loads(response.data)['result'], {"file": filename, "message": "file has been uploaded"})

    def upload_same_file(self):
        token = self.get_token()
        filename = 'default.png'
        self.upload(token=token, filename=filename)
        response = self.upload(token=token, filename=filename)
        self.assertEqual(json.loads(response.data)['result'], {"message": "file already exists"})

    def delete_file(self):
        token = self.get_token()
        filename = 'default.png'
        self.upload(token=token, filename=filename)
        data = {"jsonrpc": "2.0",
                "method": "Delete.file",
                "params": {"filename": "default.png", "path": "vasya"},
                "id": "1"}
        response = self.app.post('/api', data=json.dumps(data),
                                 headers={'content-type': 'application/json', 'x-access-token': token})
        self.assertEqual(json.loads(response.data)['result'], {"file": filename, "message": "has been deleted"})

    def delete_ghost_file(self):
        token = self.get_token()
        data = {"jsonrpc": "2.0",
                "method": "Delete.file",
                "params": {"filename": "default.png", "path": "vasya"},
                "id": "1"}
        response = self.app.post('/api', data=json.dumps(data),
                                 headers={'content-type': 'application/json', 'x-access-token': token})
        self.assertEqual(json.loads(response.data)['result'], {"message": "file has not found"})

    def delete_file_from_wrong_directory(self):
        token = self.get_token()
        filename = 'default.png'
        self.upload(token=token, filename=filename)
        data = {"jsonrpc": "2.0",
                "method": "Delete.file",
                "params": {"filename": "default.png", "path": "ne_vasya"},
                "id": "1"}
        response = self.app.post('/api', data=json.dumps(data),
                                 headers={'content-type': 'application/json', 'x-access-token': token})
        self.assertEqual(json.loads(response.data)['result'], {"message": "folder has not found"})

    def move_file(self):
        token = self.get_token()
        self.make_folder(token)
        filename = 'default.png'
        self.upload(token=token, filename=filename)
        data = {"jsonrpc": "2.0",
                "method": "Move.file",
                "params" : {"oldpath": "vasya", "newpath": "folder1", "filename": filename},
                "id": "1"}
        response = self.app.post('/api', data=json.dumps(data),
                                 headers={'content-type': 'application/json', 'x-access-token': token})
        self.assertEqual(json.loads(response.data)['result'], {"message": "file has been moved"})

    def move_file_from_wrong_directory(self):
        token = self.get_token()
        self.make_folder(token)
        filename = 'default.png'
        self.upload(token=token, filename=filename)
        data = {"jsonrpc": "2.0",
                "method": "Move.file",
                "params": {"oldpath": "vaserwya", "newpath": "folder1", "filename": filename},
                "id": "1"}
        response = self.app.post('/api', data=json.dumps(data),
                                 headers={'content-type': 'application/json', 'x-access-token': token})
        self.assertEqual(json.loads(response.data)['result'], {"message": "folder is not available"})

    def move_file_in_wrong_directory(self):
        token = self.get_token()
        self.make_folder(token)
        self.make_folder(token, folder_name='folder2')
        filename = 'default.png'
        self.upload(token=token, filename=filename)
        data = {"jsonrpc": "2.0",
                "method": "Move.file",
                "params": {"oldpath": "vasya", "newpath": "fdsfsdolder1", "filename": filename},
                "id": "1"}
        response = self.app.post('/api', data=json.dumps(data),
                                 headers={'content-type': 'application/json', 'x-access-token': token})
        self.assertEqual(json.loads(response.data)['result'], {"message": "destination folder is not available"})

    def move_ghost_file(self):
        token = self.get_token()
        self.make_folder(token)
        filename = 'default.png'
        self.upload(token=token, filename=filename)
        data = {"jsonrpc": "2.0",
                "method": "Move.file",
                "params": {"oldpath": "vasya", "newpath": "folder1", "filename": "hren.jpg"},
                "id": "1"}
        response = self.app.post('/api', data=json.dumps(data),
                                 headers={'content-type': 'application/json', 'x-access-token': token})
        self.assertEqual(json.loads(response.data)['result'], {"message": "file is not available"})

    def download_file(self):
        token = self.get_token()
        filename = 'default.png'
        self.upload(token=token, filename=filename)
        data = {"jsonrpc": "2.0",
                "method": "Get.file",
                "params": {"filename": "default.png", "path": "vasya"},
                "id": "1"}
        response = self.app.post('/api', data=json.dumps(data),
                                 headers={'content-type': 'application/json', 'x-access-token': token})
        self.assertTrue(json.loads(response.data)['result'].get('file'))

    def download_ghost_file(self):
        token = self.get_token()
        filename = 'default.png'
        self.upload(token=token, filename=filename)
        data = {"jsonrpc": "2.0",
                "method": "Get.file",
                "params": {"filename": "defdsfdsault.png", "path": "vasya"},
                "id": "1"}
        response = self.app.post('/api', data=json.dumps(data),
                                 headers={'content-type': 'application/json', 'x-access-token': token})
        self.assertEqual(json.loads(response.data)['result'], {"message": "file is not available"})

    def download_file_from_ghost_directory(self):
        token = self.get_token()
        filename = 'default.png'
        self.upload(token=token, filename=filename)
        data = {"jsonrpc": "2.0",
                "method": "Get.file",
                "params": {"filename": "default.png", "path": "no_vasya"},
                "id": "1"}
        response = self.app.post('/api', data=json.dumps(data),
                                 headers={'content-type': 'application/json', 'x-access-token': token})
        self.assertEqual(json.loads(response.data)['result'], {"message": "wrong folder"})

    def share_file(self):
        token = self.get_token()
        filename = 'default.png'
        self.upload(token=token, filename=filename)
        data = {"jsonrpc": "2.0",
                "method": "Share.file",
                "params": {"filename": "default.png", "path": "vasya", "time": "5"},
                "id": "1"}
        response = self.app.post('/api', data=json.dumps(data),
                                 headers={'content-type': 'application/json', 'x-access-token': token})
        self.assertTrue(json.loads(response.data)['result'].get('public_link'))

    def share_ghost_file(self):
        token = self.get_token()
        filename = 'default.png'
        self.upload(token=token, filename=filename)
        data = {"jsonrpc": "2.0",
                "method": "Share.file",
                "params": {"filename": "defausdslt.png", "path": "vasya", "time": "5"},
                "id": "1"}
        response = self.app.post('/api', data=json.dumps(data),
                                 headers={'content-type': 'application/json', 'x-access-token': token})
        self.assertEqual(json.loads(response.data)['result'], {"message": "file is not found"})

if __name__ == "__main__":
    unittest.main()