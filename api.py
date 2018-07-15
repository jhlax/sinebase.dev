import json
import uuid

import arrow
import bson.json_util
import flask
import flask_restful as rest
import pymongo as mongo

import config
import functools

client = mongo.MongoClient()
db = client[config.APP_NAME]

USERS = db['users']


def as_flask_data(o):
    """
    Returns a Flask-serializable structure from a MongoDB entity.

    :param o: the object to be converted
    :return: Flask-serializable structure
    """
    return json.loads(bson.json_util.dumps(o))


def as_objectid(id):
    return bson.ObjectId(id)


def get_request_data():
    """
    :return: Request JSON as object
    """
    return flask.request.get_json()


def get_request_headers() -> dict:
    return flask.request.headers


def get_request():
    return get_request_data(), get_request_headers()


def make_success(data=None, message='Operation successful.'):
    response = {
        'result':  'success',
        'message': message
    }

    if data is not None:
        response.update({'data': data})

    return as_flask_data(response)


def make_failure(data=None, message='Operation unsuccessful.'):
    response = {
        'result':  'failure',
        'message': message
    }

    if data is not None:
        response.update({'data': data})

    return as_flask_data(response)


class Secure(object):
    LEVELS = {
        'super':   3,
        'admin':   2,
        'regular': 1,
        'viewer':  0,
    }

    def check_level(self, level):
        return Secure.LEVELS[level] < Secure.LEVELS[self.level]

    def __init__(self, level='viewer'):
        self.level = level

    def __call__(self, func):
        @functools.wraps(func)
        def deco(*args, **kwargs):
            headers = get_request_headers()

            if 'Token' in headers:
                token = headers['Token']
                cursor = USERS.find({'token': token})

                if cursor.count():
                    user = cursor[0]

                    timeout, now = arrow.get(user['timeout']).timestamp, \
                                   arrow.utcnow().timestamp

                    if timeout <= now:
                        return make_failure(message='Token expired.')

                    elif self.check_level(user['level']):
                        return make_failure(message='You are not authorized.')

                    return func(*args, **kwargs)

            return make_failure(message='No token found.')

        return deco


class Users(rest.Resource):
    @staticmethod
    def user_dict(user):
        data = {
            'id':    str(user['_id']),
            'name':  user['name'],
            'email': user['email'],
            'level': user['level'],
        }

        return data

    @staticmethod
    def auth_dict(user):
        data = {
            'token': user['token'],
            'user':  Users.user_dict(user)
        }

        return data

    @Secure(level='admin')
    def post(self):
        data = get_request_data()

        email = data['email'].lower()
        password = data['password'].lower()  # SHA-256 is done on client-side
        name = data['name'].capitalize()
        level = data['level'].lower()

        if USERS.find({'email': email}).count():
            return make_failure('An account with that email already exists.')

        USERS.insert({
            'name':     name,
            'email':    email,
            'password': password,
            'level':    level,
        })

        return make_success()

    @Secure(level='admin')
    def get(self):
        users = []
        cursor = USERS.find({})

        if cursor.count():
            for user in cursor:
                users.append(Users.user_dict(user))

            return make_success(users)

        return make_failure(message='No users found.')


class User(rest.Resource):
    @Secure(level='admin')
    def post(self, user_id):
        data = get_request_data()
        _id = as_objectid(user_id)

        del data['id']

        USERS.update({
            '_id': _id,
        }, {
            '$set': data
        })

        return make_success()

    @Secure(level='admin')
    def get(self, user_id):
        cursor = USERS.find({'_id': as_objectid(user_id)})

        if cursor.count():
            return make_success(Users.user_dict(cursor[0]))

        else:
            return make_failure(message='User not found')

    @Secure(level='admin')
    def delete(self, user_id):
        id = as_objectid(user_id)
        USERS.delete_one({'_id': id})
        return make_success()


class Auth(rest.Resource):
    # noinspection PyMethodMayBeStatic
    def post(self):
        """
        Login
        :return: response to the login
        """
        data = get_request_data()
        email, password = data['email'], data['password']

        cursor = USERS.find({
            'email':    email.lower(),
            'password': password.lower(),
        })

        if cursor.count():
            user = cursor[0]

            token = str(uuid.uuid1()).lower().strip()
            timeout = arrow.utcnow().shift(weeks=2).timestamp

            user_new = USERS.find_one_and_update({
                '_id': user['_id']},
                {
                    '$set': {
                        'token':   token.lower(),
                        'timeout': timeout
                    }
                }, return_document=mongo.ReturnDocument.AFTER
            )

            return make_success(Users.auth_dict(user_new), 'Login successful')

        else:
            return make_failure(message='User not found.')

    @Secure(level='viewer')
    def get(self):
        """
        Validate token
        :return: response to validation
        """
        headers = get_request_headers()
        token = headers['Token']

        cursor = USERS.find({'token': token})

        if cursor.count():
            user = cursor[0]

            return make_success(Users.auth_dict(user),
                                'Validation successful.')

        else:
            return make_failure(message='Validation unsuccessful.')

    @Secure(level='viewer')
    def delete(self):
        """
        Logout
        :return: response for logout
        """
        headers = get_request_headers()
        if 'Token' in headers:
            token = headers['Token']

            cursor = USERS.find({'token': token})

            if cursor.count():
                USERS.update({'token': token}, {'$unset': {
                    'token': '', 'timeout': ''
                }})

                return make_success(message='Logout successful.')

            else:
                return make_failure(message='No user with token exists.')

        return make_failure(message='No token given.')
