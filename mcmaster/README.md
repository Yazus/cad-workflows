# mcmaster-fetch

Pull part specs and CAD models from McMaster-Carr by part number.

```bash
mcmaster fetch 91251A540 92196A194 -o hardware/
```

gives you:

```
hardware/
├── parts.csv          # one row per part, one column per spec (Thread Size, Length, Material, ...)
├── parts.json         # the full API response for each part (plus price, if requested)
└── cad/
    ├── 91251A540/91251A540_Socket_Head_Screw.STEP
    └── 92196A194/...
```

It uses McMaster-Carr's official [Product Information API](https://www.mcmaster.com/help/api)
rather than scraping the website, so you need an approved API account first.

## 1. Get API access

The API is free but not self-serve. McMaster-Carr approves customers individually.

1. Have a regular McMaster-Carr account at [mcmaster.com](https://www.mcmaster.com) (the
   API login is your account's email and password).
2. Email **eCommerce@mcmaster.com** asking for access to the Product Information API.
   Say what company you're with, your account email, and what you'll use it for
   (for example: "pulling specs and STEP models for parts we design in, roughly N parts a month").
3. If approved, they send you a **client certificate** (usually a `.pfx` file) and the
   certificate's password. Every API request has to present this certificate.

Read their terms when you get them. The API also caps how many parts you can subscribe to,
how many you can add per day, and how fast you can download CAD, and the limits are set
per account.

## 2. Install

Requires Python 3.11+.

```bash
cd mcmaster
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
```

## 3. Convert the certificate

Python's `requests` needs PEM files, not `.pfx`. Convert once with OpenSSL
(it will ask for the certificate password McMaster-Carr gave you):

```bash
mkdir -p ~/.mcmaster && chmod 700 ~/.mcmaster
openssl pkcs12 -in mcmaster.pfx -clcerts -nokeys -out ~/.mcmaster/client-cert.pem
openssl pkcs12 -in mcmaster.pfx -nocerts -nodes  -out ~/.mcmaster/client-key.pem
chmod 600 ~/.mcmaster/*.pem
```

On OpenSSL 3 you may need to add `-legacy` to both commands if you get an
"unsupported algorithm" error.

The key file is unencrypted, so treat it like a password: keep it out of the repo,
synced folders, and chat.

## 4. Configure credentials

Either set environment variables:

```bash
export MCMASTER_USERNAME="you@company.com"
export MCMASTER_PASSWORD="your mcmaster.com password"
export MCMASTER_CERT=~/.mcmaster/client-cert.pem
export MCMASTER_KEY=~/.mcmaster/client-key.pem
```

or copy [`mcmaster.example.toml`](mcmaster.example.toml) to `mcmaster.toml` and fill it in.
`mcmaster.toml`, `*.pem`, `*.pfx`, `.env`, and the default output folder are all gitignored.
Environment variables win over the file. Use `--config path/to/file.toml` to point somewhere else.

## Usage

```bash
# Specs + STEP model (default)
mcmaster fetch 91251A540

# A list of parts from a file (one per line, # comments allowed)
mcmaster fetch -f bom.txt -o hardware/

# Choose CAD formats; names match the API's link names
mcmaster fetch 91251A540 --cad "3-D STEP" --cad "2-D DWG"

# Specs only, with pricing
mcmaster fetch -f bom.txt --no-cad --price

# Product photos too
mcmaster fetch 91251A540 --images

# Free up subscription slots when you're done with parts
mcmaster unsubscribe -f bom.txt
```

Common CAD link names are `3-D STEP`, `2-D DWG`, `3-D SolidWorks`, `3-D IGES`, and `2-D DXF`.
Which ones exist varies by part. If a part doesn't have the one you asked for, the tool
says so and moves on. The full list for a part is in `Links` in `parts.json`.

### How it works

1. Logs in (`POST /v1/login`) with your username, password, and certificate to get a token.
2. Subscribes to each part (`PUT /v1/products`). The API only serves data for parts you're
   subscribed to, and this call returns the product info at the same time.
3. Downloads the requested files from the part's `Links` (`/v1/cad/...`, `/v1/images/...`).
4. Writes `parts.json` and `parts.csv`, then logs out.

If McMaster-Carr rate-limits a request (HTTP 429/503), the tool waits and retries a few
times. A failed CAD download doesn't lose that part's specs; the error is recorded under
`errors` in `parts.json`.

## Development

```bash
pip install -e ".[dev]"
pytest
```

The tests mock every API call with [`responses`](https://github.com/getsentry/responses),
so they run without credentials. The mocked responses follow the shapes in McMaster-Carr's
API docs. The tool hasn't yet been run against the live API, so the first real run is
worth watching.
