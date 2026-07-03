import os
import sqlite3
from decimal import Decimal, InvalidOperation

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


def init_app(app):
    os.makedirs(os.path.join(app.root_path, app.config["UPLOAD_FOLDER"]), exist_ok=True)

    with app.app_context():
        init_db()

    app.teardown_appcontext(close_db)


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(
            os.path.join(current_app.root_path, current_app.config["DATABASE"])
        )
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

    upload_folder = os.path.join(current_app.root_path, current_app.config["UPLOAD_FOLDER"])
    os.makedirs(upload_folder, exist_ok=True)
    file_storage.save(os.path.join(upload_folder, filename))

    return f"{current_app.config['UPLOAD_FOLDER']}/{filename}"


def delete_photo(photo_path):
    if not photo_path:
        return

    full_path = os.path.abspath(os.path.join(current_app.root_path, photo_path))
    upload_folder = os.path.abspath(
        os.path.join(current_app.root_path, current_app.config["UPLOAD_FOLDER"])
    )

    if os.path.commonpath([full_path, upload_folder]) == upload_folder and os.path.exists(
        full_path
    ):
        os.remove(full_path)


def get_produto_or_404(produto_id):
    produto = get_db().execute(
        "SELECT id, nome, preco, foto FROM produtos WHERE id = ?",
        (produto_id,),
    ).fetchone()

    if produto is None:
        from flask import abort

        abort(404)

    return produto


@admin_produtos_bp.get("/admin-agronossosbichos")
def listar_produtos():
    produtos = get_db().execute(
        "SELECT id, nome, preco, foto FROM produtos ORDER BY id DESC"
    ).fetchall()
    return render_template("admin_produtos/lista.html", produtos=produtos)


@admin_produtos_bp.post("/admin-agronossosbichos/produtos")
def cadastrar_produto():
    nome = request.form.get("nome", "").strip()

    if not nome:
        flash("Nome é obrigatório.")
        return redirect(url_for("admin_produtos.listar_produtos"))

    try:
        preco = parse_preco(request.form.get("preco"))
        foto = save_uploaded_photo(request.files.get("foto"))
    except ValueError as exc:
        flash(str(exc))
        return redirect(url_for("admin_produtos.listar_produtos"))

    db = get_db()
    db.execute(
        "INSERT INTO produtos (nome, preco, foto) VALUES (?, ?, ?)",
        (nome, preco, foto),
    )
    db.commit()

    flash("Produto cadastrado.")
    return redirect(url_for("admin_produtos.listar_produtos"))


@admin_produtos_bp.get("/admin-agronossosbichos/produtos/<int:produto_id>/editar")
def editar_produto_form(produto_id):
    produto = get_produto_or_404(produto_id)
    return render_template("admin_produtos/editar.html", produto=produto)


@admin_produtos_bp.post("/admin-agronossosbichos/produtos/<int:produto_id>/editar")
def editar_produto(produto_id):
    produto = get_produto_or_404(produto_id)
    nome = request.form.get("nome", "").strip()

    if not nome:
        flash("Nome é obrigatório.")
        return redirect(url_for("admin_produtos.editar_produto_form", produto_id=produto_id))

    try:
        preco = parse_preco(request.form.get("preco"))
        nova_foto = save_uploaded_photo(request.files.get("foto"))
    except ValueError as exc:
        flash(str(exc))
        return redirect(url_for("admin_produtos.editar_produto_form", produto_id=produto_id))

    foto = nova_foto or produto["foto"]

    db = get_db()
    db.execute(
        "UPDATE produtos SET nome = ?, preco = ?, foto = ? WHERE id = ?",
        (nome, preco, foto, produto_id),
    )
    db.commit()

    if nova_foto and produto["foto"]:
        delete_photo(produto["foto"])

    flash("Produto atualizado.")
    return redirect(url_for("admin_produtos.listar_produtos"))


@admin_produtos_bp.post("/admin-agronossosbichos/produtos/<int:produto_id>/excluir")
def excluir_produto(produto_id):
    produto = get_produto_or_404(produto_id)

    db = get_db()
    db.execute("DELETE FROM produtos WHERE id = ?", (produto_id,))
    db.commit()

    delete_photo(produto["foto"])

    flash("Produto excluído.")
    return redirect(url_for("admin_produtos.listar_produtos"))
