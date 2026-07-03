import os

from flask import Flask

from admin_produtos import admin_produtos_bp, init_app as init_produtos_app


def create_app(config=None):
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-admin-secret")
    app.config["DATABASE"] = "agro_nossos_bichos.db"
    app.config["UPLOAD_FOLDER"] = "static/uploads/produtos"
    app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024

    if config:
        app.config.update(config)

    init_produtos_app(app)
    app.register_blueprint(admin_produtos_bp)

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
