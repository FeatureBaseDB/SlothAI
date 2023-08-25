import datetime

from flask import Flask

from flask import Flask, session, request, render_template, make_response, redirect, url_for
from flask_talisman import Talisman
import flask_login

from web.site import site
from web.auth import auth

import config

# create app
app = Flask(__name__)
app.secret_key = config.secret_key

# logins
login_manager = flask_login.LoginManager()
login_manager.init_app(app)
login_manager.session_protection = "strong"
login_manager.login_message = u""

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
    # timestamps are everything
    now = datetime.datetime.utcnow()
    timestring = "%Y-%m-%dT%H:%M:%SZ"
    timestamp = now.strftime(timestring)

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
app.register_blueprint(site)
app.register_blueprint(auth)


login_manager.blueprint_login_views = {
    'site': "/login",
}

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
    dev = True

