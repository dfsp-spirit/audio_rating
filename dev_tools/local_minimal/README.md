## dev_tools/local_minimal -- Configuration and helpers to run in python web server

The files in this directory allwo you to run this app locally in Python's built-in webserver (frontend) with direct access to the uvicorn WSGI server. This setup uses:

* direct backend access (no reverse proxy), so not very secure and not suitable for production (no SSL!)
* runs the frontend at http://localhost:3000/
* runs the backend at http://localhost:8000/, which is accessed directly by the frontend
* this means FastAPI has an empty root path in this setup.


This setup is further away from what you will get in production compared to the local nginx dev setup, so it is harder to find path issues early.
It is a less complex to setup though, as it does not require a locally running nginx, only python.


