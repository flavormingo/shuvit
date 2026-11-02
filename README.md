# Shuvit

Worldwide skatepark index with photos from the community.

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
pipeline/.venv/bin/python -m pipeline.scraper.main scrape --world --dry-run
```

`--world` fetches every park on the planet from [QLever](https://qlever.dev) in two queries, loads them, then removes OSM parks that are no longer in the data. It runs monthly from `shuvit-pipeline.timer`. For a small area, `--bbox south,west,north,east` uses Overpass instead.

Run iOS UI tests against production with `xcodebuild test -project ios/Shuvit/Shuvit.xcodeproj -scheme Shuvit -destination 'platform=iOS Simulator,name=<device>'`.

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

`shuvit-backup.timer` writes the database and env file to `/var/backups/shuvit` on the server every night and keeps 14 days.

On the Mac, launchd runs `deploy/pull-backup.sh` daily, copied to `~/Library/Application Support/shuvit/`. It pulls those files to `~/Backups/shuvit` and keeps 60 days. It also mirrors uploaded media to `~/Backups/shuvit/media`, copying only new files. Files deleted from the server move to `~/Backups/shuvit/media-deleted/<date>` and are removed after 60 days, which is the limit the privacy policy promises.

The Mac holds the only backup of uploaded media, and it only updates when the Mac is on.

Restore a database dump with:

```sh
pg_restore -d shuvit --no-owner db-<timestamp>.dump
```

Restore media with:

```sh
rsync -a ~/Backups/shuvit/media/ shuvit-vps:/opt/shuvit/media/
ssh shuvit-vps chown -R shuvit:shuvit /opt/shuvit/media
```

## Things that are easy to break

- `shuvit-api.service` must use `ProtectHome=tmpfs`, not `true`. asyncpg checks `~/.postgresql` when connecting and crashes every database request if `/home` is unreadable. `/health` keeps passing when this happens.
- nginx `client_max_body_size` must stay above the upload limits in `backend/app/config.py`.
- Video uploads are off. To bring them back, set `ALLOW_VIDEO_UPLOADS`, raise the nginx limit and restore the iOS picker and player from git history.
- OpenStreetMap requires the attribution shown in the app and on the site. GeoNames requires the attribution in `site/terms.html`.
- Use the default offline geocoder for large scrapes. Nominatim's usage policy doesn't allow bulk geocoding.
