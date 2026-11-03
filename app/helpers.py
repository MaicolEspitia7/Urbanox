import uuid
from datetime import datetime
from functools import wraps
from pathlib import Path

from urllib.parse import quote

from flask import current_app, flash, redirect, session, url_for
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

ALLOWED_IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


def format_cop(value) -> str:
    try:
        amount = int(round(float(value)))
    except (TypeError, ValueError):
        amount = 0
    return f"$ {amount:,}".replace(",", ".")


def whatsapp_number() -> str:
    """Número de WhatsApp activo (admin puede cambiarlo)."""
    from .db import get_setting

    raw = get_setting("whatsapp_number", current_app.config.get("WHATSAPP_NUMBER", ""))
    return "".join(ch for ch in str(raw) if ch.isdigit())


def whatsapp_buy_url(product) -> str:
    """Link wa.me: vi esto en la tienda → refiere la prenda del catálogo."""
    phone = whatsapp_number()
    if not phone:
        return "#"

    name = product["name"] if product else "prenda"
    price = format_cop(product["price"] if product else 0)
    size = (product["size"] or "").strip() if product else ""
    color = (product["color"] or "").strip() if product else ""
    sku = (product["sku"] or "").strip() if product else ""
    product_id = product["id"] if product else None

    lines = [
        "Hola URBANOX,",
        "Vi esto en la tienda y me interesa esta prenda del catálogo:",
        f"- {name}",
        f"- Precio: {price}",
    ]
    if size:
        lines.append(f"- Talla: {size}")
    if color:
        lines.append(f"- Color: {color}")
    if sku:
        lines.append(f"- SKU: {sku}")
    if product_id:
        try:
            link = url_for("main.product_detail", product_id=product_id, _external=True)
            lines.append(f"- Link: {link}")
        except RuntimeError:
            pass
    lines.append("¿Sigue disponible? Quiero comprarla.")

    return f"https://wa.me/{phone}?text={quote(chr(10).join(lines))}"



def clamp_focus(value, default: int = 50) -> int:
    try:
        return max(0, min(100, int(round(float(value)))))
    except (TypeError, ValueError):
        return default


def _focus_from(product, key: str, default: int = 50) -> int:
    try:
        if hasattr(product, "get"):
            value = product.get(key)
        else:
            value = product[key]
        if value is None or value == "":
            return default
        return clamp_focus(value, default)
    except (KeyError, TypeError, IndexError):
        return default


def image_focus_style(product) -> str:
    """CSS object-position from product focus fields."""
    if product is None:
        return "object-position: 50% 50%;"
    x = _focus_from(product, "image_focus_x")
    y = _focus_from(product, "image_focus_y")
    return f"object-position: {x}% {y}%;"


# Compat: sqlite3.Row no siempre trae .get
def row_get(row, key, default=None):
    try:
        if hasattr(row, "get"):
            value = row.get(key, default)
            return default if value is None else value
        return row[key]
    except (KeyError, TypeError, IndexError):
        return default


def source_label(source: str) -> str:
    if source == "KERO":
        return "Proveedor Kero"
    if source == "PROVIDER":
        return "Proveedor"
    return "Urbanox"


def role_label(role: str) -> str:
    if role == "employee":
        return "Empleado"
    if role == "kero":
        return "Proveedor Kero"
    return "Administrador"


def format_when(value: str) -> str:
    if not value:
        return "—"
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt.strftime("%d/%m/%Y %H:%M")
    except ValueError:
        return value[:16].replace("T", " ")


REASON_OPTIONS = (
    ("venta", "Venta"),
    ("entrega", "Entrega a cliente"),
    ("cambio", "Cambio / devolución"),
    ("dano", "Daño / merma"),
    ("otro", "Otro"),
)

KERO_REASON_OPTIONS = (
    ("venta_kero", "Se vendió"),
    ("retiro_kero", "Se retiró"),
    ("devolucion", "Se devolvió"),
)

KERO_RETURN_REASONS = frozenset({"devolucion", "no_vendido"})

# Etiquetas viejas que puedan existir en historial
_KERO_LEGACY_LABELS = {
    "exhibicion": "Retiro para exhibir",
    "retiro_kero": "Se retiró",
    "cambio_kero": "Cambio / devolución",
    "no_vendido": "No se vendió",
    "otro": "Otra salida",
}


def is_kero_return(reason: str) -> bool:
    return reason in KERO_RETURN_REASONS


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            flash("Inicia sesión para continuar.", "error")
            return redirect(url_for("main.login"))
        return view(*args, **kwargs)

    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            flash("Inicia sesión para continuar.", "error")
            return redirect(url_for("main.login"))
        if session.get("user_role") != "admin":
            flash("No tienes acceso a esa sección.", "error")
            return redirect(home_for_role(session.get("user_role") or "employee"))
        return view(*args, **kwargs)

    return wrapped


def employee_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            flash("Inicia sesión para continuar.", "error")
            return redirect(url_for("main.login"))
        if session.get("user_role") not in ("admin", "employee"):
            flash("No tienes acceso a esa sección.", "error")
            return redirect(home_for_role(session.get("user_role") or "kero"))
        return view(*args, **kwargs)

    return wrapped


def kero_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            flash("Inicia sesión para continuar.", "error")
            return redirect(url_for("main.login"))
        if session.get("user_role") not in ("admin", "kero"):
            flash("No tienes acceso al módulo Kero.", "error")
            return redirect(home_for_role(session.get("user_role") or "employee"))
        return view(*args, **kwargs)

    return wrapped


def home_for_role(role: str) -> str:
    if role == "employee":
        return url_for("main.employee_desk")
    if role == "kero":
        return url_for("main.kero_desk")
    return url_for("main.admin_inventory")


def reason_label(code: str) -> str:
    for key, label in REASON_OPTIONS + KERO_REASON_OPTIONS:
        if key == code:
            return label
    if code in _KERO_LEGACY_LABELS:
        return _KERO_LEGACY_LABELS[code]
    return code or "—"


def save_product_image(file: FileStorage | None) -> tuple[str | None, str | None]:
    """Guarda una imagen subida. Devuelve (url_relativa, error)."""
    if file is None or not getattr(file, "filename", None):
        return None, None

    original = secure_filename(file.filename)
    ext = Path(original).suffix.lower()
    if ext not in ALLOWED_IMAGE_EXT:
        return None, "La imagen debe ser JPG, PNG, WEBP o GIF."

    upload_dir = Path(current_app.config["PRODUCT_UPLOAD_DIR"])
    upload_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4().hex}{ext}"
    path = upload_dir / filename
    file.save(path)
    return f"/static/uploads/products/{filename}", None
