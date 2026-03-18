import os
import json
import re
import gspread
from flask import Flask, render_template, abort
from google.oauth2.service_account import Credentials

app = Flask(__name__, template_folder="../templates")

SHEET_ID = "1zg86q--S8FOHE_bSQi69TfGaMzOFI09d8p-K827L3d8"
ABA_PLANILHA = "Tags NFC"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]


def _conectar_sheet():
    service_account_info = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if service_account_info:
        info = json.loads(service_account_info)
        creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    else:
        # Fallback para desenvolvimento local
        local_file = os.path.join(os.path.dirname(__file__), "..", "..", "service_account.json")
        creds = Credentials.from_service_account_file(local_file, scopes=SCOPES)
    client = gspread.authorize(creds)
    planilha = client.open_by_key(SHEET_ID)
    return planilha.worksheet(ABA_PLANILHA)


def _buscar_tag(uid_formatado):
    """Busca um UID na planilha e retorna dict com os dados ou None."""
    sheet = _conectar_sheet()
    todos = sheet.get_all_records()
    for linha in todos:
        uid_linha = str(linha.get("UID da Tag", "")).strip().upper()
        if uid_linha == uid_formatado.upper():
            return {
                "uid": uid_linha,
                "produto": linha.get("Produto", ""),
                "data_fab": linha.get("Data Fabricacao", ""),
                "hora_fab": linha.get("Hora Fabricacao", ""),
                "timestamp": linha.get("Timestamp Gravacao", ""),
                "operador": linha.get("Operador", ""),
            }
    return None


def _formatar_uid(uid_raw):
    """Converte '04A1B2C3' em '04:A1:B2:C3'."""
    uid_clean = uid_raw.upper().replace(":", "")
    if not re.fullmatch(r"[0-9A-F]+", uid_clean):
        return None
    return ":".join(uid_clean[i:i+2] for i in range(0, len(uid_clean), 2))


@app.route("/v/<uid_raw>")
def verify(uid_raw):
    uid_formatado = _formatar_uid(uid_raw)
    if not uid_formatado:
        abort(400)
    dados = _buscar_tag(uid_formatado)
    if not dados:
        return render_template("not_found.html", uid=uid_formatado), 404
    return render_template("verify.html", **dados)


@app.route("/")
def index():
    return render_template("not_found.html", uid=""), 404


if __name__ == "__main__":
    app.run(debug=True)
