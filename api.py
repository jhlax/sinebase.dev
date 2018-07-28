import json
import uuid

import arrow
import bson.json_util
import flask
import flask_restful as rest
import pymongo as mongo
from pymongo.database import Database

import config
import functools

from tbg_intake.logic.mvc import mongo as mvc

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


def encode_id(document):
    if isinstance(document, list):
        for idx, doc in enumerate(document):
            document[idx] = encode_id(doc)

    else:
        if '_id' in document:
            document['_id'] = str(document['_id'])

    return document


def decode_id(document):
    if isinstance(document, list):
        for idx, doc in enumerate(document):
            document[idx] = decode_id(document)

    elif isinstance(document, str):
        return bson.ObjectId(document)

    else:
        if '_id' in document:
            if isinstance(document['_id'], str):
                document['_id'] = bson.json_util.ObjectId(document['_id'])

    return document


def respond(document=None, message=None, error=None):
    return {
        'data': encode_id(document),
        'message': message,
        'error': error,
    }


def success(doc=None, message=None, error=None):
    response = respond(doc, message, error)
    response.update({
        'result': 'success',
        'message': message or 'Operation successful.',
    })
    return response


def failure(doc=None, message=None, error=None):
    response = respond(doc, message, error)
    response.update({
        'result': 'failure',
        'error': error or 'An error occurred.'
    })
    return response


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
        'result': 'success',
        'message': message
    }

    if data is not None:
        response.update({'data': data})

    return as_flask_data(response)


def make_failure(data=None, message='Operation unsuccessful.'):
    response = {
        'result': 'failure',
        'message': message
    }

    if data is not None:
        response.update({'data': data})

    return as_flask_data(response)


class Secure(object):
    LEVELS = {
        'super': 3,
        'admin': 2,
        'regular': 1,
        'viewer': 0,
    }

    def check_level(self, level):
        return self.LEVELS[level] < self.LEVELS[self.level]

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
            'id': str(user['_id']),
            'name': user['name'],
            'email': user['email'],
            'level': user['level'],
        }

        return data

    @staticmethod
    def auth_dict(user):
        data = {
            'token': user['token'],
            'user': Users.user_dict(user)
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
            'name': name,
            'email': email,
            'password': password,
            'level': level,
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
            'email': email.lower(),
            'password': password.lower(),
        })

        if cursor.count():
            user = cursor[0]

            token = str(uuid.uuid1()).lower().strip()
            timeout = arrow.utcnow().shift(weeks=2).timestamp

            user_new = USERS.find_one_and_update({
                '_id': user['_id']
            },
                {
                    '$set': {
                        'token': token.lower(),
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
                USERS.update({'token': token}, {
                    '$unset': {
                        'token': '', 'timeout': ''
                    }
                })

                return make_success(message='Logout successful.')

            else:
                return make_failure(message='No user with token exists.')

        return make_failure(message='No token given.')


class Cases(rest.Resource, mvc.MongoController):
    def __init__(self):
        rest.Resource.__init__(self)
        mvc.MongoController.__init__(self, mongo.MongoClient()['tbg_dev'],
                                     'SLA1')

    @Secure(level='viewer')
    def get(self):
        return success(self.read({}))

    @Secure(level='admin')
    def post(self):
        data = get_request_data()
        self.add_update(data)
        return success()


class Case(rest.Resource, mvc.MongoController):
    def __init__(self):
        rest.Resource.__init__(self)
        mvc.MongoController.__init__(self, mongo.MongoClient()['tbg_dev'], 'SLA1')

    @Secure()
    def get(self, case_id):
        return success(self.read({'_id': decode_id(case_id)}))

    @Secure()
    def post(self, case_id):
        data = get_request_data()
        result = self.add_update(data)
        return success(result)

    @Secure()
    def delete(self, case_id):
        case_id = decode_id(case_id)
        result = self.provider.delete_one({'_id': case_id})
        return success(result)
