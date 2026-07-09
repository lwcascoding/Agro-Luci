import os
import json
import time
import sqlite3
from decimal import Decimal, InvalidOperation
from urllib import error as urlerror
from urllib import parse, request as urlrequest
from uuid import uuid4

from flask import (
    Blueprint,
    current_app,
    flash,
    g,
    redirect,
    render_template,
    request,
    url_for,
)
from werkzeug.utils import secure_filename


admin_produtos_bp = Blueprint("admin_produtos", __name__)

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
BLOB_API_BASE_URL = "https://blob.vercel-storage.com"
BLOB_API_VERSION = "10"
BLOB_EVENTS_PREFIX = "catalog/events/"
BLOB_IMAGES_PREFIX = "produtos/"


def get_database_path():
    database = current_app.config["DATABASE"]
    if os.path.isabs(database):
        return database
    return os.path.join(current_app.root_path, database)


def get_upload_folder():
    upload_folder = current_app.config["UPLOAD_FOLDER"]
    if os.path.isabs(upload_folder):
        return upload_folder
    return os.path.join(current_app.root_path, upload_folder)


def init_app(app):
    upload_folder = app.config["UPLOAD_FOLDER"]
    if not os.path.isabs(upload_folder):
        upload_folder = os.path.join(app.root_path, upload_folder)
    os.makedirs(upload_folder, exist_ok=True)

    database = app.config["DATABASE"]
    if not os.path.isabs(database):
        database = os.path.join(app.root_path, database)
    database_folder = os.path.dirname(database)
    if database_folder:
        os.makedirs(database_folder, exist_ok=True)

    with app.app_context():
        init_db()

    app.teardown_appcontext(close_db)


def is_blob_store_enabled():
    return bool(os.environ.get("BLOB_READ_WRITE_TOKEN"))


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(get_database_path())
        g.db.row_factory = sqlite3.Row

    return g.db


def close_db(error=None):
    db = g.pop("db", None)

    if db is not None:
        db.close()


def init_db():
    db = get_db()
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS produtos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            preco REAL NOT NULL,
            foto TEXT
        )
        """
    )
    db.commit()


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def parse_preco(value):
    if value is None:
        raise ValueError("Preço é obrigatório.")

    normalized = value.strip().replace(",", ".")
    if not normalized:
        raise ValueError("Preço é obrigatório.")

    try:
        preco = Decimal(normalized)
    except InvalidOperation as exc:
        raise ValueError("Preço deve ser numérico.") from exc

    if preco < 0:
        raise ValueError("Preço deve ser maior ou igual a zero.")

    return float(preco)


def save_uploaded_photo(file_storage):
    if not file_storage or not file_storage.filename:
        return None

    if not allowed_file(file_storage.filename):
        raise ValueError("Foto deve ser uma imagem png, jpg, jpeg ou webp.")

    filename = secure_filename(file_storage.filename)
    name, extension = os.path.splitext(filename)
    filename = f"{name}_{os.urandom(8).hex()}{extension.lower()}"

    upload_folder = get_upload_folder()
    os.makedirs(upload_folder, exist_ok=True)
    file_storage.save(os.path.join(upload_folder, filename))

    return f"uploads/produtos/{filename}"


def _blob_token():
    token = os.environ.get("BLOB_READ_WRITE_TOKEN")
    if not token:
        raise RuntimeError("BLOB_READ_WRITE_TOKEN nao configurado.")
    return token


def _blob_headers(extra=None):
    headers = {
        "authorization": f"Bearer {_blob_token()}",
        "x-api-version": BLOB_API_VERSION,
    }
    if extra:
        headers.update(extra)
    return headers


def _blob_json_request(url, method="GET", payload=None, headers=None, timeout=12):
    data = None
    request_headers = _blob_headers(headers)

    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        request_headers["content-type"] = "application/json"

    req = urlrequest.Request(url, data=data, headers=request_headers, method=method)
    try:
        with urlrequest.urlopen(req, timeout=timeout) as response:
            body = response.read()
    except urlerror.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Erro no Vercel Blob ({exc.code}): {detail}") from exc

    if not body:
        return {}
    return json.loads(body.decode("utf-8"))


def _blob_list(prefix):
    blobs = []
    cursor = None

    while True:
        params = {"prefix": prefix, "limit": "1000"}
        if cursor:
            params["cursor"] = cursor

        data = _blob_json_request(f"{BLOB_API_BASE_URL}?{parse.urlencode(params)}")
        blobs.extend(data.get("blobs", []))

        if not data.get("hasMore"):
            return blobs

        cursor = data.get("cursor")
        if not cursor:
            return blobs


def _blob_put(pathname, data, content_type, cache_control_max_age="31536000"):
    encoded_path = parse.quote(pathname, safe="/")
    headers = {
        "access": "public",
        "x-content-type": content_type,
        "x-cache-control-max-age": cache_control_max_age,
    }
    req = urlrequest.Request(
        f"{BLOB_API_BASE_URL}/?pathname={encoded_path}",
        data=data,
        headers=_blob_headers(headers),
        method="PUT",
    )

    try:
        with urlrequest.urlopen(req, timeout=20) as response:
            body = response.read()
    except urlerror.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Erro ao salvar no Vercel Blob ({exc.code}): {detail}") from exc

    return json.loads(body.decode("utf-8"))


def _blob_delete(url_or_path):
    if not url_or_path:
        return

    try:
        _blob_json_request(
            f"{BLOB_API_BASE_URL}/delete",
            method="POST",
            payload={"urls": [url_or_path]},
        )
    except RuntimeError:
        current_app.logger.warning("Nao foi possivel remover blob antigo.", exc_info=True)


def _download_json(url):
    with urlrequest.urlopen(url, timeout=12) as response:
        return json.loads(response.read().decode("utf-8"))


def _new_event_path(event_type, product_id):
    timestamp = int(time.time() * 1000)
    return f"{BLOB_EVENTS_PREFIX}{timestamp}_{product_id}_{event_type}_{uuid4().hex}.json"


def _write_product_event(event_type, product_id, product=None):
    event = {
        "type": event_type,
        "id": int(product_id),
        "product": product,
        "created_at": int(time.time() * 1000),
    }
    _blob_put(
        _new_event_path(event_type, product_id),
        json.dumps(event, ensure_ascii=False).encode("utf-8"),
        "application/json",
    )


def _save_blob_photo(file_storage):
    if not file_storage or not file_storage.filename:
        return None

    if not allowed_file(file_storage.filename):
        raise ValueError("Foto deve ser uma imagem png, jpg, jpeg ou webp.")

    filename = secure_filename(file_storage.filename)
    name, extension = os.path.splitext(filename)
    filename = f"{name}_{uuid4().hex}{extension.lower()}"
    content_type = file_storage.mimetype or "application/octet-stream"
    blob = _blob_put(
        f"{BLOB_IMAGES_PREFIX}{filename}",
        file_storage.read(),
        content_type,
    )
    return blob["url"]


def _apply_product_events(events):
    products = {}

    for event in events:
        event_type = event.get("type")
        product_id = event.get("id")
        if product_id is None:
            continue

        product_id = int(product_id)
        if event_type == "delete":
            products.pop(product_id, None)
            continue

        product = event.get("product") or {}
        if event_type == "create":
            products[product_id] = {
                "id": product_id,
                "nome": product.get("nome", ""),
                "preco": float(product.get("preco", 0)),
                "foto": product.get("foto"),
            }
        elif event_type == "update" and product_id in products:
            products[product_id].update(
                {
                    "nome": product.get("nome", products[product_id]["nome"]),
                    "preco": float(product.get("preco", products[product_id]["preco"])),
                    "foto": product.get("foto", products[product_id].get("foto")),
                }
            )

    return sorted(products.values(), key=lambda produto: produto["id"], reverse=True)


def _blob_products():
    events = []

    for blob in sorted(_blob_list(BLOB_EVENTS_PREFIX), key=lambda item: item.get("pathname", "")):
        try:
            events.append(_download_json(blob["url"]))
        except (OSError, ValueError, KeyError):
            current_app.logger.warning("Evento de produto invalido no Blob.", exc_info=True)

    return _apply_product_events(events)


def delete_photo(photo_path):
    if not photo_path:
        return

    normalized = photo_path.replace("\\", "/")
    if os.path.isabs(photo_path):
        full_path = os.path.abspath(photo_path)
    elif normalized.startswith("static/"):
        full_path = os.path.abspath(os.path.join(current_app.root_path, normalized))
    else:
        full_path = os.path.abspath(os.path.join(get_upload_folder(), os.path.basename(normalized)))

    upload_folder = os.path.abspath(get_upload_folder())
    legacy_upload_folder = os.path.abspath(
        os.path.join(current_app.root_path, "static/uploads/produtos")
    )

    allowed_folders = (upload_folder, legacy_upload_folder)
    if (
        any(os.path.commonpath([full_path, folder]) == folder for folder in allowed_folders)
        and os.path.exists(full_path)
    ):
        os.remove(full_path)


def list_products():
    if is_blob_store_enabled():
        return _blob_products()

    return get_db().execute(
        "SELECT id, nome, preco, foto FROM produtos ORDER BY id DESC"
    ).fetchall()


def create_product(nome, preco, file_storage=None):
    if is_blob_store_enabled():
        produto_id = int(time.time() * 1000)
        produto = {
            "id": produto_id,
            "nome": nome,
            "preco": preco,
            "foto": _save_blob_photo(file_storage),
        }
        _write_product_event("create", produto_id, produto)
        return produto

    foto = save_uploaded_photo(file_storage)
    db = get_db()
    cursor = db.execute(
        "INSERT INTO produtos (nome, preco, foto) VALUES (?, ?, ?)",
        (nome, preco, foto),
    )
    db.commit()

    return {
        "id": cursor.lastrowid,
        "nome": nome,
        "preco": preco,
        "foto": foto,
    }


def update_product(produto_id, nome, preco, file_storage=None):
    produto = get_produto_or_404(produto_id)

    if is_blob_store_enabled():
        nova_foto = _save_blob_photo(file_storage)
        foto = nova_foto or produto["foto"]
        atualizado = {
            "id": produto_id,
            "nome": nome,
            "preco": preco,
            "foto": foto,
        }
        _write_product_event("update", produto_id, atualizado)
        if nova_foto and produto["foto"]:
            _blob_delete(produto["foto"])
        return atualizado

    nova_foto = save_uploaded_photo(file_storage)
    foto = nova_foto or produto["foto"]
    db = get_db()
    db.execute(
        "UPDATE produtos SET nome = ?, preco = ?, foto = ? WHERE id = ?",
        (nome, preco, foto, produto_id),
    )
    db.commit()

    if nova_foto and produto["foto"]:
        delete_photo(produto["foto"])

    return {
        "id": produto_id,
        "nome": nome,
        "preco": preco,
        "foto": foto,
    }


def delete_product(produto_id):
    produto = get_produto_or_404(produto_id)

    if is_blob_store_enabled():
        _write_product_event("delete", produto_id)
        _blob_delete(produto["foto"])
        return

    db = get_db()
    db.execute("DELETE FROM produtos WHERE id = ?", (produto_id,))
    db.commit()
    delete_photo(produto["foto"])


def get_produto_or_404(produto_id):
    if is_blob_store_enabled():
        for produto in list_products():
            if int(produto["id"]) == int(produto_id):
                return produto

        from flask import abort

        abort(404)

    produto = get_db().execute(
        "SELECT id, nome, preco, foto FROM produtos WHERE id = ?",
        (produto_id,),
    ).fetchone()

    if produto is None:
        from flask import abort

        abort(404)

    return produto


@admin_produtos_bp.get("/admin-agroluci")
def listar_produtos():
    produtos = list_products()
    return render_template("admin_produtos/lista.html", produtos=produtos)


@admin_produtos_bp.post("/admin-agroluci/produtos")
def cadastrar_produto():
    nome = request.form.get("nome", "").strip()

    if not nome:
        flash("Nome é obrigatório.")
        return redirect(url_for("admin_produtos.listar_produtos"))

    try:
        preco = parse_preco(request.form.get("preco"))
        create_product(nome, preco, request.files.get("foto"))
    except (ValueError, RuntimeError) as exc:
        flash(str(exc))
        return redirect(url_for("admin_produtos.listar_produtos"))

    flash("Produto cadastrado.")
    return redirect(url_for("admin_produtos.listar_produtos"))


@admin_produtos_bp.get("/admin-agroluci/produtos/<int:produto_id>/editar")
def editar_produto_form(produto_id):
    produto = get_produto_or_404(produto_id)
    return render_template("admin_produtos/editar.html", produto=produto)


@admin_produtos_bp.post("/admin-agroluci/produtos/<int:produto_id>/editar")
def editar_produto(produto_id):
    nome = request.form.get("nome", "").strip()

    if not nome:
        flash("Nome é obrigatório.")
        return redirect(url_for("admin_produtos.editar_produto_form", produto_id=produto_id))

    try:
        preco = parse_preco(request.form.get("preco"))
        update_product(produto_id, nome, preco, request.files.get("foto"))
    except (ValueError, RuntimeError) as exc:
        flash(str(exc))
        return redirect(url_for("admin_produtos.editar_produto_form", produto_id=produto_id))

    flash("Produto atualizado.")
    return redirect(url_for("admin_produtos.listar_produtos"))


@admin_produtos_bp.post("/admin-agroluci/produtos/<int:produto_id>/excluir")
def excluir_produto(produto_id):
    delete_product(produto_id)

    flash("Produto excluído.")
    return redirect(url_for("admin_produtos.listar_produtos"))
