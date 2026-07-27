# PLANTOR UI

The UI is provided via browser. The front-end is written in React, while the backend relies on 
Python3 with Flask in order to server the APIs. 

## Docker installation

A docker-compose is provided in order to simplify the execution of the code. After installing 
Docker, one just has to run from within this directory:

```shell
cd llm_ui
docker-compose up --build
```

## Local installation

### Install the due dependencies

First enter `backend` and run `pip install`, possibly creating or sourcing a virtual environment 
before.

```shell
# Consider using virtualenv
# virtualenv plantor_venv
# source plantor_venv/bin/activate
cd llm_ui/backend 
python3 -m pip install -r requirements.txt
```

Then enter the `frontend` directory and install the modules for NodeJS.

```shell
cd llm_ui/frontend
npm install
```

### Run the server

On one shell, run the following command from within the `backend` directory:

```shell
python3 run.py
```

### Start the UI

On another shell, run the following command from within the `frontend` directory:

```shell
npm start
```