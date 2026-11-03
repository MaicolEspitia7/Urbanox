import os
import secrets
from pathlib import Path

from flask import Flask

from .db import init_db
from .routes import bp


def _resolve_secret_key(root: Path) -> str:
    env_key = (os.environ.get("SECRET_KEY") or "").strip()
    if env_key:
        return env_key

    secret_file = root / ".secret_key"
    if secret_file.exists():
        stored = secret_file.read_text(encoding="utf-8").strip()
        if stored:
            return stored

    generated = secrets.token_hex(32)
    secret_file.write_text(generated, encoding="utf-8")
    return generated


def create_app() -> Flask:
    root = Path(__file__).resolve().parent.parent
    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static",
    )
    app.config["SECRET_KEY"] = _resolve_secret_key(root)
    app.config["DATABASE"] = str(root / "urbanox.db")
    app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024  # 5 MB imágenes
    # Solo dígitos con código de país. Preferí Admin → Ajustes o env WHATSAPP_NUMBER.
    app.config["WHATSAPP_NUMBER"] = (os.environ.get("WHATSAPP_NUMBER") or "").strip()
    uploads = Path(app.static_folder) / "uploads" / "products"
    uploads.mkdir(parents=True, exist_ok=True)
    app.config["PRODUCT_UPLOAD_DIR"] = str(uploads)

    init_db(app)
    app.register_blueprint(bp)
    return app
