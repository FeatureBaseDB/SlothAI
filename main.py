from flask import Flask

from flask import Flask, session, request, render_template, make_response, redirect, url_for

from web.site import site

import config

# create app
app = Flask(__name__)
app.secret_key = config.secret_key

app.register_blueprint(site)

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

