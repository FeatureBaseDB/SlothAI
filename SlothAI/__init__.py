import flask_login

from flask import Flask, render_template, make_response

from google.cloud import ndb

from SlothAI.web.site import site
from SlothAI.web.auth import auth
from SlothAI.web.cron import cron
from SlothAI.web.tasks import tasks

from SlothAI.web.pipelines import pipeline
from SlothAI.web.nodes import node
from SlothAI.web.templates import template

from SlothAI.web.models import User

import config as config 

def create_app(conf='dev'):

    app = Flask(__name__)

    if conf == 'testing':
        app.config.from_object(config.TestingConfig)
    elif conf == 'dev':
        app.config.from_object(config.DevConfig)
    elif conf == 'prod':
        app.config.from_object(config.ProdConfig)
    else:
        raise Exception("invalid conf argument: must be 'testing', 'dev', or 'prod'.") 

    # logins
    login_manager = flask_login.LoginManager()
    login_manager.init_app(app)
    login_manager.session_protection = "strong"
    login_manager.login_message = u""

    # client connection
    client = ndb.Client()

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
        app.register_blueprint(pipeline)
        app.register_blueprint(node)
        app.register_blueprint(template)

    login_manager.blueprint_login_views = {
        'site': "/login",
    }

    @app.before_request
    def before_request():
        pass
    @app.errorhandler(404)
    def f404_notfound(e):
        response = make_response(
            render_template(
                'pages/404_notfound.html'
            )
        )
        return response, 404

    return app
    # flask --app SlothAI run --port 8080 --debug