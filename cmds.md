```commandline
django-admin makemessages -l ru
```
```commandline
django-admin makemessages -l es
```
```commandline
django-admin makemessages -l uk
```
```commandline
django-admin makemessages -l uz
```
```commandline
django-admin compilemessages
```

```commandline
curl -X POST http://http://127.0.0.1:8000/api/v1/auth/register/ \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "first_name": "John",
    "last_name": "Doe",
    "phone": "+1234567890",
    "country": "USA",
    "city": "New York",
    "date_of_birth": "1990-01-01",
    "account_type": "personal",
    "password": "securepassword123",
    "password2": "securepassword123"
  }'
```