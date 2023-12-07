import logging
import sys
import uvicorn


default_port = 8000

if __name__ == "__main__":
    port = default_port
    if sys.argv[len(sys.argv) - 1] != 'fastmain.py':
        port = int(sys.argv[len(sys.argv) - 1])

    logging.getLogger('testservice').info('Listening on port %d', port)
    uvicorn.run('fastservice:app', host='0.0.0.0', port=8000, reload=True)
