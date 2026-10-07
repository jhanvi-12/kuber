<!-- PROJECT LOGO -->
<br />
<div align="center">

<h3 align="center">Kuber cab project</h3>

  <p align="center">
      Kuber cab project 
  </p>
</div>



<!-- TABLE OF CONTENTS -->
<details  >
  <summary>Table of Contents</summary>
  <ol>
    <li>
      <a href="#about-the-project">About The Project</a>
      <ul>
        <li><a href="#built-with">Built With</a></li>
      </ul>
    </li>
    <li>
      <a href="#getting-started">Getting Started</a>
      <ul>
        <li><a href="#prerequisites">Prerequisites</a></li>
        <li><a href="#install-poetry">Install Poetry</a></li>
        <li><a href="#installation">Installation</a></li>
        <li><a href="#poetry-commands">Poetry commands</a></li>
      </ul>
    </li>
    <li><a href="#run-the-server">Run the server</a></li>
    <li><a href="#database-migrations">Database migrations</a></li>
    <li><a href="#tests">Tests</a></li>
  </ol>
</details>

<!-- ABOUT THE PROJECT -->
## About The Project

Kuber Backend project is an application to book your ride with ease.


### Built With

* [![Python][Python]][Python-url]
* [![FastAPI][FastAPI]][FastAPI-url]

<!-- GETTING STARTED -->
## Getting Started

Local setup uses Poetry for dependencies, MySQL for the database, and Redis for sockets and ride dispatch.

### Prerequisites

* Python 3.12
* [Poetry](https://python-poetry.org/)
* MySQL
* Redis

Check Python:

```bash
python --version
```

### Install Poetry

Linux or macOS:

```bash
curl -sSL https://install.python-poetry.org | python3 -
```

Windows (PowerShell):

```powershell
(Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | py -
```

If `poetry` is not recognized, add it to PATH:

* Linux/macOS: `$HOME/.local/bin`
* Windows: `%APPDATA%\Python\Scripts`

Confirm the install:

```bash
poetry --version
```

### Installation

1. Clone the repo and move into it

   ```bash
   git clone https://github.com/jhanvi-12/kuber.git
   cd kuber
   ```

2. Install dependencies from `pyproject.toml`

   ```bash
   poetry install
   ```

3. Create a `.env` file in the project root. The app reads it on startup. Required groups:

   * Database: `DATABASE_NAME`, `DATABASE_USER`, `DATABASE_PASSWORD`, `DATABASE_HOST`, `DATABASE_PORT`
   * Redis: `REDIS_HOST`, `REDIS_PORT`
   * Server: `SERVER_HOST`, `SERVER_PORT`
   * Auth: `JWT_SECRET_KEY`, `JWT_ALGORITHM`
   * Socket: `SOCKET_SERVER_HOST`, `SOCKET_SERVER_PORT`

4. Create the MySQL database named in `DATABASE_NAME`, then apply migrations (see below).

### Poetry commands

Run a command inside the project virtual environment:

```bash
poetry run <command>
```

Add a package:

```bash
poetry add <package-name>
```

Add a development-only package:

```bash
poetry add --group dev <package-name>
```

Update locked dependencies:

```bash
poetry update
```

Show installed packages:

```bash
poetry show
```

Show the virtualenv path:

```bash
poetry env info
```

Activate the virtualenv in the current shell (Poetry 2):

```bash
poetry env activate
```

On older Poetry versions:

```bash
poetry shell
```

## Run the server

From the project root, with `.env` in place and MySQL and Redis running:

```bash
poetry run python asgi.py
```

This starts the API and Socket.IO together.

* Swagger: http://localhost:8000/docs
* ReDoc: http://localhost:8000/redoc

Optional flags:

```bash
poetry run python asgi.py --env local
poetry run python asgi.py --env dev --debug
```

Run the Socket.IO server on its own (uses `SOCKET_SERVER_HOST` and `SOCKET_SERVER_PORT`):

```bash
poetry run python socket_server.py
```

## Database migrations

Migrations live in `migrations/`. Run Alembic through Poetry so it uses the project environment.

Set `sqlalchemy.url` in `alembic.ini` to the same MySQL database as `.env`, using the sync driver:

```text
sqlalchemy.url = mysql+pymysql://user:password@localhost:3306/db_name
```

Apply all migrations:

```bash
poetry run python -m alembic upgrade head
```

See the current revision:

```bash
poetry run python -m alembic current
```

Create a new migration after model changes:

```bash
poetry run python -m alembic revision --autogenerate -m "describe the change"
```

Undo the last migration:

```bash
poetry run python -m alembic downgrade -1
```

## Tests

```bash
poetry run pytest
```

## Additional resources

* [Poetry documentation](https://python-poetry.org/docs/)
* [FastAPI documentation](https://fastapi.tiangolo.com/)
* [Alembic documentation](https://alembic.sqlalchemy.org/)

## Release History

* 0.1
    * Work in progress

   
<!-- MARKDOWN LINKS & IMAGES -->
[Python]: https://img.shields.io/badge/Python-000000?style=for-the-badge&logo=python&logoColor=Blue
[Python-url]: https://docs.python.org/3.12/
[FastAPI]: https://img.shields.io/badge/FastAPI-20232A?style=for-the-badge&logo=fastapi&logoColor=009485
[FastAPI-url]: https://fastapi.tiangolo.com/