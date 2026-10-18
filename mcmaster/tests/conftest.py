import pytest
import responses

API = "https://api.mcmaster.com"

# Shaped after the examples in https://www.mcmaster.com/help/api
PRODUCT = {
    "PartNumber": "91251A540",
    "ProductStatus": "Active",
    "FamilyDescription": "Socket Head Screw",
    "DetailDescription": "Black-Oxide Alloy Steel Socket Head Screw, 1/4\"-20 Thread Size, 1\" Long",
    "Specifications": [
        {"Attribute": "Thread Size", "Values": ["1/4\"-20"]},
        {"Attribute": "Length", "Values": ["1\""]},
        {"Attribute": "Material", "Values": ["Black-Oxide Alloy Steel"]},
    ],
    "Links": [
        {"Key": "Price", "Value": "/v1/products/91251A540/price"},
        {"Key": "Image", "Value": "/v1/images/91251A540.png"},
        {"Key": "2-D DWG", "Value": "/v1/cad/91251A540_Socket_Head_Screw.dwg"},
        {"Key": "3-D STEP", "Value": "/v1/cad/91251A540_Socket_Head_Screw.STEP"},
    ],
}

PRICE = [{"Amount": 13.04, "MinimumQuantity": 1, "UnitOfMeasure": "Pack"}]


@pytest.fixture
def creds_env(tmp_path, monkeypatch):
    cert = tmp_path / "client.pem"
    cert.write_text("-----BEGIN CERTIFICATE-----\nfake\n-----END CERTIFICATE-----\n")
    monkeypatch.setenv("MCMASTER_USERNAME", "yazeed@example.com")
    monkeypatch.setenv("MCMASTER_PASSWORD", "secret")
    monkeypatch.setenv("MCMASTER_CERT", str(cert))
    monkeypatch.delenv("MCMASTER_KEY", raising=False)
    monkeypatch.setenv("MCMASTER_CONFIG", str(tmp_path / "absent.toml"))
    monkeypatch.chdir(tmp_path)
    return cert


@pytest.fixture
def api():
    with responses.RequestsMock() as rsps:
        rsps.post(f"{API}/v1/login", json={"AuthToken": "tok-123", "ExpirationTS": "2026-10-19T12:00:00"})
        rsps.post(f"{API}/v1/logout", status=204)
        yield rsps
