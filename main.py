import datetime

from flask import Flask

from flask import Flask, session, request, render_template, make_response, redirect, url_for
from flask_talisman import Talisman
import flask_login

from google.cloud import ndb

from web.site import site
from web.auth import auth
from web.cron import cron
from web.table import table
from web.tasks import tasks

from web.models import User

import config

# create app
app = Flask(__name__)
app.secret_key = config.secret_key

# logins
login_manager = flask_login.LoginManager()
login_manager.init_app(app)
login_manager.session_protection = "strong"
login_manager.login_message = u""

# client connection
client = ndb.Client()


def get_uid():
    try:
        return flask_login.current_user.uid
    except Exception as ex:
        return "anonymous"

@login_manager.request_loader
def load_request(request):
    # get a token, if there is one
    token = request.args.get('token')
    if not token:
        token = request.form.get('token')

    if token:
        with client.context():
            user = User.query().filter(User.api_token==token).get()
        return user
    else:
        return None

@login_manager.user_loader 
def load_user(uid):
    try:
        # get the user
        with client.context():
            if uid != "anonymous":
                user = User.query().filter(User.uid==uid).get()

        if user.authenticated == False and uid !="anonymous":
            return None

    except Exception as ex:
        print("In load user error was %s" % ex)
        return None

    return user

# blueprints
with app.app_context():
    app.register_blueprint(site)
    app.register_blueprint(auth)
    app.register_blueprint(cron)
    app.register_blueprint(tasks)
    app.register_blueprint(table)

login_manager.blueprint_login_views = {
    'site': "/login",
}

@app.before_request
def before_request():
    if request.url.startswith('http://') and config.dev == "False" and "cron" not in request.url and "tasks" not in request.url:
        url = request.url.replace('http://', 'https://', 1)
        code = 301
        return redirect(url, code=code)


@app.errorhandler(404)
def f404_notfound(e):
    response = make_response(
        render_template(
            'pages/404_notfound.html'
        )
    )
    return response, 404


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=8080, debug=True)

