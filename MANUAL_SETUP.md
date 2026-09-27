# Manual Setup Checklist

Everything in this file **requires an account, a payment card, or a decision
that is yours to make.** I cannot do any of it for you. The code is already
wired to consume these values — you supply them in `.env`.

Work top to bottom. Each item says exactly where to get the value, what it is
for, and how to verify it landed.

---

## The 5-minute version

If you just want it running locally, you need **one** value:

```bash
cp .env.example .env
python -c "from django.core.management.utils import get_random_secret_key as g; print(g())"
# paste the output into SECRET_KEY= in .env
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Everything below is for **production**.

---

## 1. `SECRET_KEY` — do this first

**What it is:** the key that signs sessions, password-reset tokens, CSRF, and
signed URLs. Anyone holding it can forge logins.

**Get one:**
```bash
python -c "from django.core.management.utils import get_random_secret_key as g; print(g())"
```

**Rules:**
- Generate a fresh one. **Do not reuse the dev one.**
- Never commit it. Never paste it in Slack, email, or a GitHub issue.
- Rotating it logs everyone out. That is correct behaviour.
- If it has ever been committed, rotate it and assume it is compromised.

**Verify:**
```bash
python manage.py check --deploy
# W009 means the key is too weak or still looks auto-generated
```

---

## 2. Google Maps API key

**Why:** the listing detail page renders a map. Without a key the map is
*omitted*, not broken — the page still works, you just see a "map location is
not available" line.

**Get one:**
1. Go to <https://console.cloud.google.com/apis/credentials>
2. Create a project (or pick an existing one)
3. **Enable API** → *Maps JavaScript API*
4. **Create credentials** → *API key*
5. Click the key → *Edit* → **API restrictions**:
   - Restrict to **Maps JavaScript API**
6. **Application restrictions** → **HTTP referrers (web sites)**:
   - `https://your-domain.com/*`
   - `https://www.your-domain.com/*`
   - `http://localhost:8113/*` (so it works in development)

> **The referrer restriction is the single most important step.** Without it
> your key is public and billable by anyone, and Google will email you when
> someone runs up a bill.

**Set:** `GOOGLE_MAPS_API_KEY=AIza...`

**Set a budget alert:** Google Cloud Console → *Billing* → *Budgets & alerts* →
create a $5/mo budget. This is your backstop against a runaway bill.

**Verify:** load a listing page, confirm the map renders, and check the
browser network tab for a `google.com/maps/api/js` 200.

---

## 3. Transactional email (SMTP)

**Why:** password resets and realtor inquiry notifications. In development
mail prints to the console. In production, **without this, password reset is
silently broken** — the user clicks a link that was never sent.

**Recommended: Postmark** (simplest for transactional mail)
1. Sign up at <https://postmarkapp.com>
2. *Sender Domains* → *Add Sender Domain* → add `your-domain.com`
3. Follow the DNS records they give you (SPF + DKIM) in your DNS provider
4. *Sending Domains* → confirm
5. *API Tokens* → create a server token

**Alternatives:** AWS SES (cheapest at volume, but you must leave the AWS
sandbox first), Mailgun, Resend, SendGrid.

**Set:**
```
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.postmarkapp.com
EMAIL_PORT=587
EMAIL_HOST_USER=your-postmark-server-token
EMAIL_HOST_PASSWORD=your-postmark-server-token
EMAIL_USE_TLS=True
DEFAULT_FROM_EMAIL=noreply@your-domain.com
SERVER_EMAIL=noreply@your-domain.com
```

> The original code hardcoded `schonefeld.dev@gmail.com` as the sender **and
> blind-CC'd it on every inquiry**, meaning every lead's phone number and
> message was emailed to a personal Gmail account. That is fixed — it is now
> `settings.DEFAULT_FROM_EMAIL`. **Do not put a personal address back.**

**Verify — do this on staging, not production:**
```bash
python manage.py shell -c "
from django.core.mail import send_mail
import os
send_mail('test', 'body', os.environ['DEFAULT_FROM_EMAIL'], ['you@your-own-inbox.com'], fail_silently=False)
"
```
Check SPAM. Postmark's sandbox mode only sends to your own address until you
confirm the domain.

---

## 4. Google OAuth (optional — read this before doing it)

**Current state:** the code is now *correct* (the `OCIALACCOUNT_PROVIDERS`
typo is fixed, the custom-user adapter is fixed, and `/accounts/signup/` no
longer 500s). But **no credentials are configured**, so clicking "Sign in with
Google" will not work.

**My recommendation: skip it.** Email + password already works, has email
verification, and has password reset. Google OAuth adds a third-party
dependency, a callback URL to keep in sync across environments, and a whole
class of account-linking bugs — for a feature most buyers of a property site
will not use.

**If you do want it:**
1. <https://console.cloud.google.com/apis/credentials> → *OAuth client ID*
2. Application type: **Web application**
3. **Authorised redirect URIs** — add one per environment:
   - `http://localhost:8113/accounts/google/login/callback/`
   - `https://your-domain.com/accounts/google/login/callback/`
   - `https://staging.your-domain.com/accounts/google/login/callback/`

   > Get the exact path from `python manage.py shell -c "from django.urls import reverse; print(reverse('google_login'))"`
4. Add your domain to **Authorised domains**
5. Publish the app, or add yourself as a test user

**Set:** `GOOGLE_CLIENT_ID=...apps.googleusercontent.com` and
`GOOGLE_CLIENT_SECRET=...`

**To remove it entirely** if you decide against it:
- Delete the 3 `allauth` lines from `INSTALLED_APPS` in `project/settings/base.py`
- Delete `path("accounts/", include("allauth.urls"))` from `project/urls.py`
- Delete the `SOCIALACCOUNT_*` and `ACCOUNT_ADAPTER` settings
- Delete `accounts/adapter.py`

---

## 5. Object storage (S3) for media

**Why:** property photos and buyer-facing exposé PDFs. **The container
filesystem is wiped on every deploy** — anything not in S3 is lost. This is not
optional in production; it is the difference between losing your media and
keeping it.

**Get one:**
1. Sign in at <https://console.aws.amazon.com/s3/home>
2. **Create bucket**
   - Name: globally unique, e.g. `my-realestate-media`
   - Region: pick the one closest to your users
   - **Block all public access: ON** ← important
3. **IAM** → *Users* → create a user with programmatic access
4. Attach a policy scoped to just that bucket:
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [{
       "Effect": "Allow",
       "Action": ["s3:GetObject","s3:PutObject","s3:DeleteObject"],
       "Resource": "arn:aws:s3:::my-realestate-media/*"
     }]
   }
   ```
   > Scope it to the bucket. A policy with `"Resource": "*"` gives the app
   > permission to delete every file in your entire AWS account.
5. Create an **access key** for that user, and store the secret in a password
   manager

**Set:**
```
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
AWS_STORAGE_BUCKET_NAME=my-realestate-media
AWS_S3_REGION_NAME=eu-central-1
```

> The S3 backend activates automatically when `AWS_STORAGE_BUCKET_NAME` is
> set, so local development keeps using the filesystem.

**Also set up:**
- **Lifecycle rule** on the bucket: expire or transition objects older than
  your retention policy
- **Versioning** ON, so a deleted photo is recoverable
- **CORS** if you later serve media directly from a CDN

**Verify:** upload a listing photo in the admin, confirm it appears in the
bucket, and confirm it renders on the public page.

---

## 6. PostgreSQL

**Why:** SQLite is a single file with a single writer. It does not survive a
multi-instance deploy and cannot handle concurrent inquiries.

**Options:**
- **Managed:** Supabase, Neon, Railway, RDS, PlanetScale-style offerings
- **Self-managed:** the included `docker-compose.yml` runs Postgres 16

**Set:** `DATABASE_URL=postgres://user:password@host:5432/dbname`

> Use a **strong random password**, and a **non-superuser** role. The app
> needs `CREATE`/`ALTER` only during migrations; it does not need superuser.

**Verify:**
```bash
DJANGO_ENV=prod python manage.py migrate
DJANGO_ENV=prod python manage.py check --database default
```

---

## 7. Nominatim User-Agent (easy to overlook, and it bites)

**Why:** listing coordinates are geocoded via OpenStreetMap's public Nominatim
service. Their [usage policy](https://operations.osmfoundation.org/policies/nominatim/)
**requires a real, contactable User-Agent** and caps you at 1 request/second.
An unidentifiable agent gets blocked.

**Set** — and make the contact address one you actually read:
```
NOMINATIM_USER_AGENT=RealEstate/1.0 (https://your-domain.com; hello@your-domain.com)
```

The code **refuses to geocode** unless the User-Agent contains an `@` or an
`http`, and logs a warning rather than getting your IP blocked.

**Policy requirements you must also meet:**
- Max **1 request/second** → `tools/manage_messages.py` is unrelated, but
  `manage.py backfill_geocoding` sleeps 1.1s by default. Keep it.
- **No autocomplete / prefetch on typing** (we do not have this)
- **Cache results** → we cache for 7 days in production
- Identify yourself, and **honour a reasonable request volume**

> **For a site with thousands of listings, consider a hosted geocoder** —
> Mapbox, Google Geocoding, Geoapify, or Photon/Komoot. Nominatim's public
> instance is a demo service and is not a production SLA.

**Backfill existing listings:**
```bash
python manage.py backfill_geocoding          # missing only
python manage.py backfill_geocoding --force  # re-resolve everything
```

---

## 8. Domain, DNS, and TLS

**DNS records to create:**

| Type | Name | Value |
|---|---|---|
| `A` / `AAAA` | `@` | your server IP |
| `CNAME` | `www` | your server or hosting target |
| `MX` | `@` | your mail provider |
| `TXT` | `@` | `v=spf1 include:...` (from your mail provider) |
| `TXT` | `selector._domainkey` | DKIM record from your mail provider |
| `TXT` | `_dmarc` | `v=DMARC1; p=quarantine; rua=mailto:dmarc@your-domain.com` |

**TLS:** if deploying with the included Docker setup, run **Caddy** or
**nginx** in front and terminate TLS there. The Django side already sends
`X-Forwarded-Proto` (via `SECURE_PROXY_SSL_HEADER`); make sure your proxy sets
it, or `SECURE_SSL_REDIRECT` will loop forever.

**Verify:** <https://www.ssllabs.com/ssltest/>

**Set:**
```
ALLOWED_HOSTS=your-domain.com,www.your-domain.com
CSRF_TRUSTED_ORIGINS=https://your-domain.com,https://www.your-domain.com
SITE_URL=https://your-domain.com
SITE_NAME=Your Company Name
```

> `CSRF_TRUSTED_ORIGINS` is required the moment you serve over HTTPS with a
> non-localhost host, or you will get *"Origin checking failed"* on every form
> submission. This is a very common first-deploy surprise.

---

## 9. Legal pages — do not skip, get a lawyer

`templates/core/impressum.html` and `templates/core/privacy.html` exist but
currently contain **two different people's names and two different domains**,
copied from the original tutorial project.

**If you operate in the EU/Germany, this is legally required before launch:**
- **Impressum** (§ 5 DDG / TMG): legal entity name, address, commercial
  register, VAT ID, responsible party for content, dispute resolution,
  professional-insurance details where applicable
- **Privacy policy** (GDPR Art. 13/14): who the data controller is, what data
  is collected, the **legal basis** for each, retention periods, **every third
  party that processes data** (your host, your mail provider, your object
  storage, Google Analytics if you add it), and the rights users have
- **Cookie/consent banner** if you use any non-essential cookies

**I am not a lawyer and this is not legal advice.** Budget for a review —
typically a few hundred euros — and do it *before* you take a real lead.

---

## 10. Remaining production decisions

These are engineering calls, not key-fetching, but you need to make them:

- [ ] **Monitoring.** Sentry (free tier) or equivalent. Wire
      `SENTRY_DSN` into `project/settings/prod.py` — the code is not wired yet.
- [ ] **Uptime monitoring** on `GET /healthz` (liveness) and
      `GET /readyz` (checks the database — returns 503 when it is down).
- [ ] **Backups.** Automated Postgres dumps *and* an S3 versioning/backup
      rule. **Test a restore.** A backup you have never restored is a theory.
- [ ] **Secret storage.** Platform secret manager (Render/Railway/Fly) or
      Vault. Do not use a `.env` file in a shared server for production.
- [ ] **Dependency updates.** Dependabot or Renovate, weekly.
- [ ] **Analytics + cookie consent** if you want traffic data.
- [ ] **Content.** `Country` and `State` rows are required before creating
      listings — `Address.state` is a non-null FK.

---

## Launch-day checklist

```bash
# 1. Configuration is complete
DJANGO_ENV=prod python manage.py check --deploy
#    must print: System check identified no issues

# 2. Migrations are committed
python manage.py makemigrations --check --dry-run
#    must print: No changes detected

# 3. Tests pass
pytest

# 4. Static files collect
DJANGO_ENV=prod python manage.py collectstatic --noinput

# 5. Database migrated
DJANGO_ENV=prod python manage.py migrate

# 6. Superuser exists
DJANGO_ENV=prod python manage.py createsuperuser

# 7. Health endpoints respond
curl -fsS https://your-domain.com/healthz
curl -fsS https://your-domain.com/readyz

# 8. The real flow works, as a logged-in human
#    - register an account
#    - confirm you receive the verification email
#    - request a password reset and confirm the email arrives
#    - log in, submit an inquiry, confirm the realtor receives it
#    - grant can_access_documents, confirm the buyer sees the exposé
#    - confirm a map renders on a listing page
```

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `ValueError: Environment variable 'X' is required` | Working as designed | Set it in `.env`. This is better than the old silent fallback that ran production in DEBUG mode |
| `DisallowedHost` | `ALLOWED_HOSTS` missing your domain | Add it, comma-separated |
| *"Origin checking failed" on every form | HTTPS + missing `CSRF_TRUSTED_ORIGINS` | Add `https://your-domain.com` |
| Redirect loop | Proxy isn't setting `X-Forwarded-Proto` | Configure the proxy |
| Password reset does nothing | Email backend not configured | Check `EMAIL_BACKEND`; verify with `send_mail` |
| Uploaded images 404 | S3 not configured, or `STATIC_ROOT`/`MEDIA_ROOT` wrong | Check `STORAGES` and bucket policy |
| Map is blank | No API key, or referrer restriction doesn't match | Verify key, restrictions, and billing |
| `Nominatim is not contactable` warning | `NOMINATIM_USER_AGENT` lacks `@` or `http` | Set a real contact address |
| Listings have no map pin | Geocoding never ran | `python manage.py backfill_geocoding` |
