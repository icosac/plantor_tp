# run.py

from flask import Flask
from flask_cors import CORS
from app.routes import app_routes

import sys, getopt

app = Flask(__name__)
CORS(app)

# Register blueprints
app.register_blueprint(app_routes)


def usage():
    print("Options are: d{,ebug}, h{,elp}, p{ort}=<port>")


if __name__ == "__main__":
    port = 5000
    debug = False
    try:
        opt, args = getopt.getopt(sys.argv[1:], "dp:h", ["help", "debug", "port="])
    except getopt.GetoptError as err:
        print(err)
        usage()
        sys.exit(2)

    for o, a in opt:
        if o in ["-h", "--help"]:
            usage()
            sys.exit(0)
        elif o in ["-p", "--port"]:
            port = int(a)
        elif o in ["-d", "--debug"]:
            debug = True
        else:
            print("Option not recognized")

    app.run(debug=debug, host="0.0.0.0", port=port, threaded=True)
