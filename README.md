# Shuvit

Worldwide skatepark index with photos and reviews from the community.

- `backend/`: FastAPI, PostgreSQL/PostGIS and Redis
- `ios/Shuvit/`: SwiftUI app. The Xcode project is generated from `project.yml` with `xcodegen generate`
- `pipeline/`: scrapes parks from OpenStreetMap
- `site/`: static pages served at shuvit.app
- `deploy/`: server configuration and scripts

## Local setup

Needs PostgreSQL with PostGIS, Redis and ffmpeg (`brew install postgresql postgis redis ffmpeg`).

```sh
make test-db
make backend-setup pipeline-setup
cp backend/.env.example backend/.env
make migrate
make test
make backend
```

Run the pipeline from the repo root, so that `pipeline` is importable:

```sh
pipeline/.venv/bin/python -m pipeline.scraper.main scrape --source osm --dry-run
```

## Deploying

```sh
bash deploy/deploy.sh
```

Run it from the repo root. It backs up production, syncs the code, runs migrations and restarts the API, then checks an endpoint that queries the database. It connects through this entry in `~/.ssh/config`:

```
Host shuvit-vps
  HostName 209.74.85.177
  Port 22022
  User root
  IdentityFile ~/.ssh/shuvit_vps
  IdentitiesOnly yes
```

## Backups

`shuvit-backup.timer` writes the database, media and env file to `/var/backups/shuvit` on the server every night and keeps 14 days. On the Mac, launchd runs `deploy/pull-backup.sh` daily, copied to `~/Library/Application Support/shuvit/`, which pulls them to `~/Backups/shuvit` and keeps 60 days.

Restore a database dump with:

```sh
pg_restore -d shuvit --no-owner db-<timestamp>.dump
```

## Things that are easy to break

- `shuvit-api.service` must use `ProtectHome=tmpfs`, not `true`. asyncpg checks `~/.postgresql` when connecting and crashes every database request if `/home` is unreadable. `/health` keeps passing when this happens.
- nginx `client_max_body_size` must stay above `MAX_VIDEO_SIZE` in `backend/app/config.py`.
- OpenStreetMap requires the attribution shown in the app and on the site. GeoNames requires the attribution in `site/terms.html`.
- Use the default offline geocoder for large scrapes. Nominatim's usage policy doesn't allow bulk geocoding.
