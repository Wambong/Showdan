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

```commandline
curl -X 'POST' \
  'http://127.0.0.1:8000/en/api/accounts/auth/login/' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -H 'X-CSRFTOKEN: shDNW46qAjEvBb3GHKLjCjTxGxf0dNxoQ76nhU2NxXZnehJu9oI1ZBMQtt1fakZb' \
  -d '{
  "email": "showdan@gmail.com",
  "password": "Shwdowdawdnwd.32wd"
}'
```

```commandline
{
  "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoicmVmcmVzaCIsImV4cCI6MTc2OTUzOTM5MSwiaWF0IjoxNzY5NDUyOTkxLCJqdGkiOiI5YjFiYWZiODliZGE0MGZkOGQwYjRhODNkMjMyYzQ5MSIsInVzZXJfaWQiOiIxMSJ9._YoSFjgxSRjeklXA_FySPcGL1N605K8FpAET0kDa1Y0",
  "access": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoiYWNjZXNzIiwiZXhwIjoxNzY5NDUzMjkxLCJpYXQiOjE3Njk0NTI5OTEsImp0aSI6IjVkZTViYzU0NzM2YzQxYzViOGU0NjE3MjUwMmU0YWVjIiwidXNlcl9pZCI6IjExIn0.2OWSyHw0-pq9Tb1ADllUnNt7zAbakoU0TvZ-VZmVpTA"
}
```