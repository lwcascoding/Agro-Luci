import os

from flask import Flask, jsonify, render_template_string, request, send_from_directory, url_for

from admin_produtos import (
    admin_produtos_bp,
    get_db,
    get_upload_folder,
    init_app as init_produtos_app,
)


WHATSAPP_PHONE = "5524999380461"


def create_app(config=None):
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-admin-secret")
    app.config["DATABASE"] = os.environ.get("DATABASE_PATH", "agro_luci.db")
    app.config["UPLOAD_FOLDER"] = os.environ.get("UPLOAD_FOLDER", "static/uploads/produtos")
    app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024

    if config:
        app.config.update(config)

    init_produtos_app(app)
    app.register_blueprint(admin_produtos_bp)

    @app.after_request
    def allow_local_product_api(response):
        if request.path == "/api/produtos":
            response.headers["Access-Control-Allow-Origin"] = "*"
        return response

    @app.template_filter("brl")
    def format_brl(value):
        return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    @app.template_global()
    def product_photo_url(photo):
        if not photo:
            return url_for("assets", filename="logo-agro-luci.jpeg")

        normalized = photo.replace("\\", "/")
        if normalized.startswith("static/"):
            return url_for("static", filename=normalized.replace("static/", "", 1))

        return url_for("uploaded_product_photo", filename=os.path.basename(normalized))

    @app.get("/")
    def index():
        produtos = get_db().execute(
            "SELECT id, nome, preco, foto FROM produtos ORDER BY id DESC"
        ).fetchall()

        with open(os.path.join(app.root_path, "index.html"), encoding="utf-8") as file:
            template = file.read()

        return render_template_string(
            template,
            produtos=produtos,
            whatsapp_phone=WHATSAPP_PHONE,
        )

    @app.get("/api/produtos")
    def api_produtos():
        produtos = get_db().execute(
            "SELECT id, nome, preco, foto FROM produtos ORDER BY id DESC"
        ).fetchall()

        return jsonify(
            [
                {
                    "id": produto["id"],
                    "nome": produto["nome"],
                    "preco": produto["preco"],
                    "preco_formatado": format_brl(produto["preco"]),
                    "foto_url": product_photo_url(produto["foto"]),
                }
                for produto in produtos
            ]
        )

    @app.get("/uploads/produtos/<path:filename>")
    def uploaded_product_photo(filename):
        return send_from_directory(get_upload_folder(), filename)

    @app.get("/assets/<path:filename>")
    def assets(filename):
        return send_from_directory(os.path.join(app.root_path, "assets"), filename)

    @app.get("/fonts/<path:filename>")
    def fonts(filename):
        return send_from_directory(os.path.join(app.root_path, "fonts"), filename)

    @app.get("/<path:filename>")
    def root_files(filename):
        if filename in {"styles.css", "script.js"}:
            return send_from_directory(app.root_path, filename)
        return ("Not found", 404)

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
