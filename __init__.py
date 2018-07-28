import flask
from flask_restful import Api

import api
import config

app = flask.Flask(config.APP_NAME)
app.config['DEBUG'] = True


@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def webapp(path):
    return app.send_static_file('partials/app.html')


# noinspection PyTypeChecker
rest = Api(app)

# noinspection PyTypeChecker
rest.add_resource(api.Auth, '/api/auth')
# noinspection PyTypeChecker
rest.add_resource(api.Users, '/api/users')
# noinspection PyTypeChecker
rest.add_resource(api.User, '/api/users/<string:user_id>')
# noinspection PyTypeChecker
rest.add_resource(api.Cases, '/api/cases')
# noinspection PyTypeChecker
rest.add_resource(api.Case, '/api/cases/<string:case_id>')

if __name__ == '__main__':
    app.run('0.0.0.0')
