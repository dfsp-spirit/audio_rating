## dev_tools/local_nginx -- Configuration and helpers to run in nginx

The files in this directory allwo you to run this app locally in nginx. This setup uses:

* a reverse proxy to access the backend
* runs the frontend at http://localhost:3000/rate/
* runs the backend at http://localhost:3000/ar_backend/ (via nginx proxy)
* runs the internal uvicorn server at http://localhost:8000, but you should not use this and access the backend via the proxy


This setup is a lot closer to what you will get in production than the minimal dev setup, so it is easier to find path issues early.
It is a bit more complex to setup though, as it requires a locally running nginx.


### Usage

```sh
# from repo root
cp dev_tools/local_nginx/frontend_settings/ar_settings.dev-nginx.js frontend/settings/ar_settings.js
cp dev_tools/local_nginx/backend_settings/.env.dev-nginx backend/.env

# start script that runs nginx and uvicorn
./run_dev_nginx.bash
```


