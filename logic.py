from textwrap import dedent


class Provider:
    def create(self, item):
        raise NotImplementedError

    def read(self, item):
        raise NotImplementedError

    def update(self, item):
        raise NotImplementedError

    def delete(self, item):
        raise NotImplementedError

    def add_update(self, item):
        raise NotImplementedError

    def unset(self, item):
        raise NotImplementedError

    def __iter__(self):
        raise NotImplementedError

    def __getitem__(self, item):
        raise NotImplementedError


class Model(dict):
    def save(self):
        raise NotImplementedError

    def delete(self):
        raise NotImplementedError

    def duplicate(self):
        raise NotImplementedError


class Representation:
    def __str__(self):
        return super(Representation, self).__str__()

    def __repr__(self):
        return super(Representation, self).__repr__()

    def render(self):
        raise NotImplementedError


class Controller:
    pass


import json

import bson
import bson.json_util
import pymongo as mongo

mongo_client = mongo.MongoClient()


class MongoProvider(Provider):
    class Requires_ID:
        def __init__(self):
            pass

        def __call__(self, func):
            def deco(self, document):
                document = MongoProvider.sanitize_id(document)

                if '_id' not in document:
                    raise ValueError(
                        'Document must have an `_id` value to update.')

                else:
                    return func(self, document)

            return deco

    @staticmethod
    def sanitize_id(document):
        if 'id' in document:
            _id = bson.ObjectId(document['id'])
            document['_id'] = _id
            del document['id']
        return document

    @staticmethod
    def remove_id(document):
        if 'id' in document:
            del document['id']
        if '_id' in document:
            del document['_id']
        return document

    @staticmethod
    def objectid_to_string(document):
        if '_id' in document:
            if '$oid' in document['_id']:
                _id = document['_id']['$oid']
                document['id'] = _id
                del document['_id']
        return document

    @staticmethod
    def mongo_items_to_dict(cursor):
        n = cursor.count()

        if n:
            _json = []

            for item in cursor:
                _item = json.loads(bson.json_util.dumps(item))
                _item = MongoProvider.objectid_to_string(_item)
                _json.append(_item)

            return _json
        else:
            return None

    def __init__(self, database, table):
        self._table = mongo_client[database][table]

    def __iter__(self):
        yield from self.read()

    def __getitem__(self, item):
        if isinstance(item, str):
            return self.read({'_id': item})[0]
        elif isinstance(item, int):
            return self.read()[item]
        elif isinstance(item, dict):
            return self.read(item)

    def __setitem__(self, key, value):
        if isinstance(key, str):
            document = {**value, 'id': key}
            return self.update(document)
        elif isinstance(key, int):
            document = dict(self.read()[key])
            document.update(value)
            return self.update(document)
        elif key is None:
            return self.add_update(value)
        else:
            raise NotImplementedError

    def create(self, document):
        document = MongoProvider.remove_id(document)

        return self._table.insert(document)

    def read(self, parameters=None):
        if parameters is None:
            parameters = {}

        cursor = self._table.find(parameters)
        items = MongoProvider.mongo_items_to_dict(cursor)

        return items

    @Requires_ID()
    def update(self, document):
        _id = document['_id']
        del document['_id']

        return self._table.find_one_and_update({'_id': _id},
                                               {'$set': document})

    @Requires_ID()
    def delete(self, document):
        _id = document['_id']

        return self._table.delete_one({'_id': _id})

    def add_update(self, document):
        if 'id' in document:
            return self.update(document)
        else:
            return self.create(document)

    @Requires_ID()
    def unset(self, document):
        _id = document['_id']
        del document['_id']

        return self._table.update({'_id': _id}, {'$unset': document})


x = MongoProvider('test_db', 'users')
print(x.read())
