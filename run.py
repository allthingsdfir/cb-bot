#!app/bin/python
from application import app

if __name__ == '__main__':
    app.run(debug=True,
            host='0.0.0.0',
            port=8080,
            # ssl_context='adhoc',
            threaded=True
            # ssl_context=('/etc/ssl/certs/doby.crt',
            #              '/etc/ssl/private/doby.key')
            )
