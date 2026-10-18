import csv
import json
from pathlib import Path

import pytest
import responses
from responses import matchers

from conftest import API, PRICE, PRODUCT
from mcmaster_fetch import cli
from mcmaster_fetch.client import McMasterClient, McMasterError, _filename
from mcmaster_fetch.config import ConfigError, load_credentials

STEP_BYTES = b"ISO-10303-21;\nHEADER;\nENDSEC;\n"


def add_product(api, product=PRODUCT):
    api.put(
        f"{API}/v1/products",
        json=product,
        match=[
            matchers.json_params_matcher({"URL": f"https://mcmaster.com/{product['PartNumber']}"}),
            matchers.header_matcher({"Authorization": "Bearer tok-123"}),
        ],
    )


def test_fetch_writes_specs_and_step(creds_env, api, tmp_path):
    add_product(api)
    api.get(
        f"{API}/v1/cad/91251A540_Socket_Head_Screw.STEP",
        body=STEP_BYTES,
        headers={"Content-Disposition": 'attachment; filename="91251A540.STEP"'},
    )

    out = tmp_path / "out"
    assert cli.main(["fetch", "91251a540", "-o", str(out)]) == 0

    assert (out / "cad" / "91251A540" / "91251A540.STEP").read_bytes() == STEP_BYTES
    records = json.loads((out / "parts.json").read_text())
    assert records[0]["product"]["PartNumber"] == "91251A540"
    assert records[0]["files"] == ["cad/91251A540/91251A540.STEP"]

    with (out / "parts.csv").open() as f:
        rows = list(csv.DictReader(f))
    assert rows[0]["Thread Size"] == '1/4"-20'
    assert rows[0]["Material"] == "Black-Oxide Alloy Steel"
    assert rows[0]["CadFiles"] == "cad/91251A540/91251A540.STEP"

    login = api.calls[0].request
    assert json.loads(login.body) == {"UserName": "yazeed@example.com", "Password": "secret"}
    assert api.calls[-1].request.url == f"{API}/v1/logout"


def test_multiple_cad_types_images_and_price(creds_env, api, tmp_path):
    add_product(api)
    api.get(f"{API}/v1/products/91251A540/price", json=PRICE)
    api.get(f"{API}/v1/cad/91251A540_Socket_Head_Screw.STEP", body=STEP_BYTES)
    api.get(f"{API}/v1/cad/91251A540_Socket_Head_Screw.dwg", body=b"dwg")
    api.get(f"{API}/v1/images/91251A540.png", body=b"png")

    out = tmp_path / "out"
    rc = cli.main(
        ["fetch", "91251A540", "-o", str(out), "--cad", "3-D STEP", "--cad", "2-D DWG", "--images", "--price"]
    )
    assert rc == 0
    files = sorted(p.name for p in (out / "cad" / "91251A540").iterdir())
    assert files == ["91251A540.png", "91251A540_Socket_Head_Screw.STEP", "91251A540_Socket_Head_Screw.dwg"]
    with (out / "parts.csv").open() as f:
        assert next(csv.DictReader(f))["Price"] == "13.04/Pack"


def test_missing_cad_type_is_skipped(creds_env, api, tmp_path, capsys):
    product = {**PRODUCT, "PartNumber": "1234A5", "Links": []}
    add_product(api, product)

    out = tmp_path / "out"
    assert cli.main(["fetch", "1234A5", "-o", str(out)]) == 0
    assert "no '3-D STEP' file available" in capsys.readouterr().err
    assert json.loads((out / "parts.json").read_text())[0]["files"] == []


def test_part_list_file_and_bad_part(creds_env, api, tmp_path):
    add_product(api)
    api.put(
        f"{API}/v1/products",
        status=400,
        json={"ErrorMessage": "Invalid part number"},
        match=[matchers.json_params_matcher({"URL": "https://mcmaster.com/NOPE"})],
    )
    parts = tmp_path / "parts.txt"
    parts.write_text("# screws\n91251A540\nnope  # typo\n91251A540\n")

    out = tmp_path / "out"
    assert cli.main(["fetch", "-f", str(parts), "-o", str(out), "--no-cad"]) == 1
    records = json.loads((out / "parts.json").read_text())
    assert [r["product"]["PartNumber"] for r in records] == ["91251A540"]


def test_failed_cad_download_keeps_specs(creds_env, api, tmp_path):
    add_product(api)
    api.get(f"{API}/v1/cad/91251A540_Socket_Head_Screw.STEP", status=400)

    out = tmp_path / "out"
    assert cli.main(["fetch", "91251A540", "-o", str(out)]) == 0
    record = json.loads((out / "parts.json").read_text())[0]
    assert record["files"] == []
    assert "HTTP 400" in record["errors"][0]


def test_login_failure(creds_env, tmp_path, capsys):
    with responses.RequestsMock() as rsps:
        rsps.post(f"{API}/v1/login", status=401, json={"ErrorDescription": "Login failed"})
        assert cli.main(["fetch", "91251A540", "-o", str(tmp_path / "out")]) == 1
    assert "Login failed" in capsys.readouterr().err


def test_retries_rate_limit(creds_env, api):
    api.get(f"{API}/v1/products/91251A540", status=429, headers={"Retry-After": "5"})
    api.get(f"{API}/v1/products/91251A540", json=PRODUCT)
    sleeps = []
    with McMasterClient(load_credentials(), sleep=sleeps.append) as client:
        assert client.get_product("91251A540")["PartNumber"] == "91251A540"
    assert sleeps == [5.0]


def test_gives_up_after_retries(creds_env, api):
    for _ in range(3):
        api.get(f"{API}/v1/products/91251A540", status=429)
    with McMasterClient(load_credentials(), max_retries=2, sleep=lambda s: None) as client:
        with pytest.raises(McMasterError) as e:
            client.get_product("91251A540")
    assert e.value.status == 429


def test_unsubscribe(creds_env, api):
    api.delete(
        f"{API}/v1/products",
        status=204,
        match=[matchers.json_params_matcher({"URL": "https://mcmaster.com/91251A540"})],
    )
    assert cli.main(["unsubscribe", "91251A540"]) == 0


def test_filename_cannot_escape_folder():
    class Resp:
        headers = {"Content-Disposition": 'attachment; filename="../../etc/passwd"'}

    assert _filename(Resp(), "/v1/cad/x.STEP") == "passwd"
    Resp.headers = {}
    assert _filename(Resp(), "/v1/cad/..") == "download"
    assert _filename(Resp(), "/v1/cad/My%20Part.STEP") == "My Part.STEP"


def test_config_file_and_env_override(tmp_path, monkeypatch):
    for var in ("MCMASTER_USERNAME", "MCMASTER_PASSWORD", "MCMASTER_CERT", "MCMASTER_KEY"):
        monkeypatch.delenv(var, raising=False)
    cert, key = tmp_path / "c.pem", tmp_path / "k.pem"
    cert.write_text("c")
    key.write_text("k")
    cfg = tmp_path / "mcmaster.toml"
    cfg.write_text(f'[mcmaster]\nusername = "a"\npassword = "b"\ncert = "{cert}"\nkey = "{key}"\n')

    creds = load_credentials(cfg)
    assert creds.requests_cert == (str(cert), str(key))

    monkeypatch.setenv("MCMASTER_PASSWORD", "from-env")
    assert load_credentials(cfg).password == "from-env"


def test_missing_credentials(tmp_path, monkeypatch):
    for var in ("MCMASTER_USERNAME", "MCMASTER_PASSWORD", "MCMASTER_CERT", "MCMASTER_KEY"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ConfigError, match="MCMASTER_USERNAME"):
        load_credentials()


def test_pfx_cert_rejected_with_hint(creds_env, tmp_path, monkeypatch):
    pfx = tmp_path / "client.pfx"
    pfx.write_bytes(b"\x30")
    monkeypatch.setenv("MCMASTER_CERT", str(pfx))
    with pytest.raises(ConfigError, match="Convert it to PEM"):
        load_credentials()
