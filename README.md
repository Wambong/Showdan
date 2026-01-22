# Showdan — Frontend Developer Guide (Templates, CSS, JS)

This README focuses on the **frontend layer** of the project: **Django templates**, **static CSS/JS**, and how the UI is assembled (including dashboard + HTMX partial loads).

---

## 1) Clone the project

```bash
git clone https://github.com/Wambong/Showdan.git
cd Showdan
```
## copy the file .env to the 
``Showdan/`` directory and same as manage.py

# 2) Create a virtual environment + install requirements
## Windows (PowerShell)

```commandline
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

```
## macOS / Linux
```commandline
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

```
# 3) Run migrations + start the dev server
```commandline
python manage.py migrate
python manage.py runserver

```
### Home page:
`` 
Home page: http://127.0.0.1:8000/
``
### Dashboard:
```
http://127.0.0.1:8000/accounts/dashboard/
```

## Use account credentials as admin account
### email
```commandline
showdan@gmail.com
```
### passwor
```commandline
Shwdowdawdnwd.32wd
```


# Static assets are under:
`` static/css/app.css``
`` static/js/main.js``
