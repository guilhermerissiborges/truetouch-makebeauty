import os
import json
import re
import gspread
from datetime import datetime
from flask import Flask, render_template, abort, request
from google.oauth2.service_account import Credentials

app = Flask(__name__, template_folder="../templates")

SHEET_ID = "1zg86q--S8FOHE_bSQi69TfGaMzOFI09d8p-K827L3d8"
ABA_PLANILHA = "Tags NFC"
ABA_ACESSOS  = "Acessos"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def _conectar_planilha():
    service_account_info = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if service_account_info:
        info = json.loads(service_account_info)
        creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    else:
        local_file = os.path.join(os.path.dirname(__file__), "..", "service_account.json")
        creds = Credentials.from_service_account_file(local_file, scopes=SCOPES)
    client = gspread.authorize(creds)
    return client.open_by_key(SHEET_ID)


def _conectar_sheet():
    return _conectar_planilha().worksheet(ABA_PLANILHA)


def _conectar_sheet_acessos():
    planilha = _conectar_planilha()
    try:
        return planilha.worksheet(ABA_ACESSOS)
    except gspread.WorksheetNotFound:
        sheet = planilha.add_worksheet(title=ABA_ACESSOS, rows=1000, cols=6)
        sheet.append_row(["Email", "UID", "Produto", "Timestamp", "IP"])
        return sheet


def _registrar_acesso(email, uid, produto, ip):
    try:
        sheet = _conectar_sheet_acessos()
        timestamp = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        sheet.append_row([email, uid, produto, timestamp, ip or ""])
    except Exception:
        pass


def _validar_email(email):
    """Valida formato básico de email."""
    padrao = r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$'
    return re.match(padrao, email.strip()) is not None


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
                "data_fab": linha.get("Data Fabricacao", "") or linha.get("Data Fabricação", ""),
                "hora_fab": linha.get("Hora Fabricacao", "") or linha.get("Hora Fabricação", ""),
                "timestamp": linha.get("Timestamp Gravacao", "") or linha.get("Timestamp Gravação", ""),
                "operador": linha.get("Operador", ""),
            }
    return None


def _formatar_uid(uid_raw):
    """Converte '04A1B2C3' em '04:A1:B2:C3'."""
    uid_clean = uid_raw.upper().replace(":", "")
    if not re.fullmatch(r"[0-9A-F]+", uid_clean):
        return None
    return ":".join(uid_clean[i:i+2] for i in range(0, len(uid_clean), 2))


@app.route("/v/<uid_raw>", methods=["GET", "POST"])
def verify(uid_raw):
    uid_formatado = _formatar_uid(uid_raw)
    if not uid_formatado:
        abort(400)

    # GET — exibe formulário de email
    if request.method == "GET":
        return render_template("email_gate.html", uid=uid_raw, erro=None, email_digitado="")

    # POST — valida email e exibe resultado
    email = request.form.get("email", "").strip().lower()

    if not email or not _validar_email(email):
        return render_template(
            "email_gate.html",
            uid=uid_raw,
            erro="Please enter a valid email address.",
            email_digitado=email
        )

    dados = _buscar_tag(uid_formatado)

    ip = request.headers.get("X-Real-IP") or request.remote_addr
    _registrar_acesso(email, uid_formatado, dados.get("produto", "") if dados else "", ip)

    if not dados:
        return render_template("not_found.html", uid=uid_formatado), 404

    return render_template("verify.html", **dados)


@app.route("/")
def index():
    return render_template("not_found.html", uid=""), 404


if __name__ == "__main__":
    app.run(debug=True)
