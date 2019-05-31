#!app/bin/python
import os
import subprocess
import logging

from application import app

def init_db():
    # Create data folder before starting MongoDB
    os.makedirs('{}/data'.format(os.getcwd()), exist_ok=True)

    # Starts up a MongoDB child process.
    # Runs a subprocess. If you can tee it, great. but
    # having the open function will output the log nicely.
    # mongod --dbpath data/ --port 5051 | tee mongo.log
    with open('{}/mongo.log'.format(os.getcwd()),"wb") as out:
        process = subprocess.Popen(['mongod',
                                    '--dbpath',
                                    'data/',
                                    '--port',
                                    '5051'],
                                    shell=False,
                                    stdout=out,
                                    stderr=out)

def init_logging():
    # Enables logging in DEBUG mode.
    log_path = '{}/doby.log'.format(os.getcwd())
    logging.basicConfig(filename=log_path,
                        level=logging.DEBUG)

if __name__ == '__main__':
    
    # Starts the MongoDB process.
    init_db()

    # Enables logging in DEBUG mode.
    init_logging()
    
    # Runs Doby bot.
    app.run(debug=True,
            host='0.0.0.0',
            port=443,
            threaded=True,
            ssl_context=('/etc/ssl/certs/doby.crt',
                         '/etc/ssl/private/doby.key')
