# Chithi Backend Deployment Notes

## Render backend commands

Build command:

```bash
cd backend && pip install -r requirements.txt && python manage.py collectstatic --noinput
```

Start command:

```bash
daphne backend.asgi:application --bind 0.0.0.0 --port $PORT
```

## Required Render environment variables

```env
DJANGO_SECRET_KEY=replace-with-a-real-secret
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=your-render-service.onrender.com
DJANGO_CORS_ALLOWED_ORIGINS=https://your-frontend-domain.com
DJANGO_CSRF_TRUSTED_ORIGINS=https://your-render-service.onrender.com,https://your-frontend-domain.com
DATABASE_URL=postgres://USER:PASSWORD@HOST:5432/DBNAME
DATABASE_SSL_REQUIRE=True
REDIS_URL=rediss://default:password@host:port
CLOUDINARY_CLOUD_NAME=your-cloud-name
CLOUDINARY_API_KEY=your-api-key
CLOUDINARY_API_SECRET=your-api-secret
```

## One-time production commands

Run migrations only after confirming the production `DATABASE_URL` points to the intended database:

```bash
cd backend && python manage.py migrate
```

Create an admin user if needed:

```bash
cd backend && python manage.py createsuperuser
```

## Local fallback behavior

When production variables are not set:

- database falls back to `backend/db.sqlite3`
- media falls back to local `MEDIA_ROOT` / `MEDIA_URL`
- Channels falls back to the in-memory channel layer
