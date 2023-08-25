# [START gae_python37_app]
from flask import Flask

app = Flask(__name__)


@app.route('/')
def hello():
    """Return a friendly HTTP greeting."""
    return 'Hi Nico! Hi PyData Manchester.'


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=8080, debug=True)

# [END gae_python37_app]
