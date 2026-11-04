import json
from datetime import datetime, timezone

from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash

from .db import execute, get_setting, query_all, query_one, set_setting
from .helpers import (
    KERO_REASON_OPTIONS,
    KERO_RETURN_REASONS,
    REASON_OPTIONS,
    admin_required,
    clamp_focus,
    employee_required,
    format_cop,
    format_when,
    home_for_role,
    image_focus_style,
    is_kero_return,
    kero_required,
    login_required,
    reason_label,
    role_label,
    row_get,
    save_product_image,
    source_label,
    whatsapp_buy_url,
    whatsapp_number,
)

bp = Blueprint("main", __name__)


@bp.app_context_processor
def inject_helpers():
    return {
        "format_cop": format_cop,
        "format_when": format_when,
        "source_label": source_label,
        "reason_label": reason_label,
        "role_label": role_label,
        "reason_options": REASON_OPTIONS,
        "kero_reason_options": KERO_REASON_OPTIONS,
        "kero_return_reasons": KERO_RETURN_REASONS,
        "is_kero_return": is_kero_return,
        "image_focus_style": image_focus_style,
        "row_get": row_get,
        "whatsapp_buy_url": whatsapp_buy_url,
        "user_name": session.get("user_name"),
        "user_role": session.get("user_role"),
        "is_admin": session.get("user_role") == "admin",
        "is_employee": session.get("user_role") == "employee",
        "is_kero": session.get("user_role") == "kero",
    }


@bp.get("/")
def home():
    products = query_all(
        """
        SELECT * FROM products
        WHERE published = 1
        ORDER BY created_at DESC
        LIMIT 8
        """
    )
    total = query_one(
        "SELECT COUNT(*) AS c FROM products WHERE published = 1"
    )["c"]
    return render_template("home.html", products=products, total_published=total)


@bp.get("/catalogo")
def catalog():
    q = (request.args.get("q") or "").strip()
    categoria = (request.args.get("categoria") or "").strip()
    sql = "SELECT * FROM products WHERE published = 1"
    args: list = []

    if categoria:
        sql += " AND category = ?"
        args.append(categoria)
    if q:
        sql += " AND (name LIKE ? OR category LIKE ? OR color LIKE ? OR size LIKE ?)"
        like = f"%{q}%"
        args.extend([like, like, like, like])

    sql += " ORDER BY updated_at DESC"
    products = query_all(sql, args)
    categories = [
        row["category"]
        for row in query_all(
            """
            SELECT DISTINCT category FROM products
            WHERE published = 1 AND category <> ''
            ORDER BY category
            """
        )
    ]
    return render_template(
        "catalog.html",
        products=products,
        q=q,
        categoria=categoria,
        categories=categories,
    )


@bp.get("/catalogo/<int:product_id>")
def product_detail(product_id: int):
    product = query_one(
        "SELECT * FROM products WHERE id = ? AND published = 1",
        (product_id,),
    )
    if product is None:
        flash("Prenda no encontrada.", "error")
        return redirect(url_for("main.catalog"))

    related = query_all(
        """
        SELECT * FROM products
        WHERE published = 1 AND id != ? AND category = ?
        ORDER BY updated_at DESC
        LIMIT 4
        """,
        (product_id, product["category"]),
    )
    return render_template("product_detail.html", product=product, related=related)


@bp.route("/admin/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(home_for_role(session.get("user_role", "admin")))

    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        user = query_one("SELECT * FROM admins WHERE email = ?", (email,))
        if user and check_password_hash(user["password_hash"], password):
            role = user["role"] if user["role"] in ("admin", "employee", "kero") else "admin"
            session.clear()
            session["user_id"] = user["id"]
            session["user_name"] = user["name"]
            session["user_role"] = role
            flash(f"Hola, {user['name']}.", "ok")
            return redirect(home_for_role(role))
        flash("Credenciales inválidas.", "error")

    return render_template("login.html")


@bp.post("/admin/logout")
@login_required
def logout():
    session.clear()
    flash("Sesión cerrada.", "ok")
    return redirect(url_for("main.login"))


@bp.get("/admin")
@admin_required
def admin_inventory():
    products = query_all("SELECT * FROM products ORDER BY updated_at DESC")
    total_units = sum(p["stock"] for p in products)
    inventory_value = sum(p["stock"] * p["price"] for p in products)
    published = sum(1 for p in products if p["published"])
    return render_template(
        "admin_inventory.html",
        products=products,
        total_units=total_units,
        inventory_value=inventory_value,
        published=published,
    )


@bp.get("/admin/kero")
@admin_required
def admin_kero_moves():
    q = (request.args.get("q") or "").strip()
    sql = """
        SELECT
            m.id, m.quantity, m.note, m.reason, m.unit_price, m.sale_total,
            m.stock_after, m.created_at, m.source,
            p.name AS product_name, p.sku AS product_sku, p.image_url,
            a.name AS user_name
        FROM stock_moves m
        JOIN products p ON p.id = m.product_id
        JOIN admins a ON a.id = m.user_id
        WHERE m.source = 'KERO'
    """
    args: list = []
    if q:
        sql += " AND (p.name LIKE ? OR p.sku LIKE ? OR m.note LIKE ? OR a.name LIKE ?)"
        like = f"%{q}%"
        args.extend([like, like, like, like])
    sql += " ORDER BY m.created_at DESC LIMIT 100"
    moves = query_all(sql, args)
    totals = query_one(
        """
        SELECT
            COUNT(*) AS moves,
            COALESCE(SUM(CASE WHEN reason IN ('devolucion', 'no_vendido') THEN 0 ELSE quantity END), 0) AS out_units,
            COALESCE(SUM(CASE WHEN reason IN ('devolucion', 'no_vendido') THEN quantity ELSE 0 END), 0) AS in_units,
            COALESCE(SUM(CASE WHEN reason IN ('devolucion', 'no_vendido') THEN 0 ELSE sale_total END), 0) AS amount
        FROM stock_moves
        WHERE source = 'KERO'
        """
    )
    today = query_one(
        """
        SELECT
            COUNT(*) AS moves,
            COALESCE(SUM(CASE WHEN reason IN ('devolucion', 'no_vendido') THEN 0 ELSE quantity END), 0) AS out_units,
            COALESCE(SUM(CASE WHEN reason IN ('devolucion', 'no_vendido') THEN quantity ELSE 0 END), 0) AS in_units
        FROM stock_moves
        WHERE source = 'KERO'
          AND substr(created_at, 1, 10) = date('now')
        """
    )
    return render_template(
        "admin_kero.html",
        moves=moves,
        q=q,
        totals=totals,
        today=today,
    )


@bp.get("/kero")
@kero_required
def kero_desk():
    q = (request.args.get("q") or "").strip()
    sql = "SELECT * FROM products WHERE 1=1"
    args: list = []
    if q:
        sql += " AND (name LIKE ? OR sku LIKE ? OR category LIKE ? OR size LIKE ? OR color LIKE ?)"
        like = f"%{q}%"
        args.extend([like, like, like, like, like])
    sql += " ORDER BY name ASC"
    products = query_all(sql, args)
    units = sum(p["stock"] for p in products)

    recent = query_all(
        """
        SELECT
            m.quantity, m.note, m.reason, m.unit_price, m.sale_total, m.stock_after, m.created_at,
            p.name AS product_name, p.sku AS product_sku,
            a.name AS user_name
        FROM stock_moves m
        JOIN products p ON p.id = m.product_id
        JOIN admins a ON a.id = m.user_id
        WHERE m.source = 'KERO'
        ORDER BY m.created_at DESC
        LIMIT 20
        """
    )
    return render_template(
        "kero_desk.html",
        products=products,
        recent=recent,
        q=q,
        units=units,
    )


@bp.post("/kero/productos/<int:product_id>/salida")
@kero_required
def kero_deduct(product_id: int):
    product = query_one("SELECT * FROM products WHERE id = ?", (product_id,))
    if product is None:
        flash("Prenda no encontrada.", "error")
        return redirect(url_for("main.kero_desk"))

    try:
        qty = int(request.form.get("quantity") or 0)
    except ValueError:
        qty = 0
    note = (request.form.get("note") or "").strip()
    reason = (request.form.get("reason") or "venta_kero").strip()
    valid_reasons = {key for key, _ in KERO_REASON_OPTIONS}
    if reason not in valid_reasons:
        reason = "venta_kero"
    returning = is_kero_return(reason)

    try:
        unit_price = float(request.form.get("unit_price") or product["price"] or 0)
    except ValueError:
        unit_price = float(product["price"] or 0)

    next_q = (request.form.get("next_q") or "").strip()

    def back():
        return redirect(url_for("main.kero_desk", q=next_q))

    if qty < 1:
        flash("Indica cuántas prendas anotar.", "error")
        return back()
    if not returning and qty > product["stock"]:
        flash(f"Solo hay {product['stock']} en stock de «{product['name']}».", "error")
        return back()
    if qty > 99:
        flash("Máximo 99 unidades por anotación.", "error")
        return back()
    if len(note) < 3:
        flash("La anotación necesita una nota (mínimo 3 caracteres).", "error")
        return back()
    if unit_price < 0:
        unit_price = float(product["price"] or 0)

    now = datetime.now(timezone.utc).isoformat()
    if returning:
        next_stock = product["stock"] + qty
        sale_total = 0.0
        flash_msg = (
            f"Devolución Kero: +{qty} «{product['name']}». Quedan {next_stock}. "
            "El admin ya puede verlo."
        )
    else:
        next_stock = product["stock"] - qty
        sale_total = unit_price * qty
        flash_msg = (
            f"Anotación Kero: −{qty} «{product['name']}». Quedan {next_stock}. "
            "El admin ya puede verlo."
        )

    execute(
        "UPDATE products SET stock = ?, updated_at = ? WHERE id = ?",
        (next_stock, now, product_id),
    )
    execute(
        """
        INSERT INTO stock_moves (
            product_id, user_id, quantity, note, reason, source,
            unit_price, sale_total, stock_after, created_at
        ) VALUES (?, ?, ?, ?, ?, 'KERO', ?, ?, ?, ?)
        """,
        (
            product_id,
            session["user_id"],
            qty,
            note,
            reason,
            unit_price,
            sale_total,
            next_stock,
            now,
        ),
    )
    flash(flash_msg, "ok")
    return back()


@bp.get("/empleado")
@employee_required
def employee_desk():
    q = (request.args.get("q") or "").strip()
    sql = "SELECT * FROM products WHERE 1=1"
    args: list = []
    if q:
        sql += " AND (name LIKE ? OR sku LIKE ? OR category LIKE ? OR size LIKE ? OR color LIKE ?)"
        like = f"%{q}%"
        args.extend([like, like, like, like, like])
    sql += " ORDER BY name ASC"
    products = query_all(sql, args)
    units = sum(p["stock"] for p in products)

    recent = query_all(
        """
        SELECT
            m.quantity, m.note, m.reason, m.unit_price, m.sale_total, m.stock_after, m.created_at,
            p.name AS product_name, p.sku AS product_sku,
            a.name AS user_name
        FROM stock_moves m
        JOIN products p ON p.id = m.product_id
        JOIN admins a ON a.id = m.user_id
        ORDER BY m.created_at DESC
        LIMIT 20
        """
    )
    return render_template(
        "employee_desk.html",
        products=products,
        recent=recent,
        q=q,
        units=units,
    )


def _parse_employee_reason_note():
    note = (request.form.get("note") or "").strip()
    reason = (request.form.get("reason") or "venta").strip()
    valid_reasons = {key for key, _ in REASON_OPTIONS}
    if reason not in valid_reasons:
        reason = "venta"
    return reason, note


def _employee_apply_deduct(product, qty: int, unit_price: float, reason: str, note: str):
    """Aplica una salida. Devuelve (ok, message, sale_total)."""
    if qty < 1:
        return False, "Indica cuántas unidades vas a descontar.", 0
    if qty > product["stock"]:
        return (
            False,
            f"Solo hay {product['stock']} en stock de «{product['name']}».",
            0,
        )
    if unit_price < 0:
        return False, "El precio de venta no puede ser negativo.", 0

    now = datetime.now(timezone.utc).isoformat()
    next_stock = product["stock"] - qty
    sale_total = unit_price * qty
    execute(
        "UPDATE products SET stock = ?, updated_at = ? WHERE id = ?",
        (next_stock, now, product["id"]),
    )
    execute(
        """
        INSERT INTO stock_moves (
            product_id, user_id, quantity, note, reason, source,
            unit_price, sale_total, stock_after, created_at
        ) VALUES (?, ?, ?, ?, ?, 'OWN', ?, ?, ?, ?)
        """,
        (
            product["id"],
            session["user_id"],
            qty,
            note,
            reason,
            unit_price,
            sale_total,
            next_stock,
            now,
        ),
    )
    return (
        True,
        f"−{qty} «{product['name']}» por {format_cop(sale_total)}. Quedan {next_stock}.",
        sale_total,
    )


@bp.post("/empleado/productos/<int:product_id>/descontar")
@employee_required
def employee_deduct(product_id: int):
    product = query_one("SELECT * FROM products WHERE id = ?", (product_id,))
    if product is None:
        flash("Prenda no encontrada.", "error")
        return redirect(url_for("main.employee_desk"))

    try:
        qty = int(request.form.get("quantity") or 0)
    except ValueError:
        qty = 0

    reason, note = _parse_employee_reason_note()
    try:
        unit_price = float(request.form.get("unit_price") or product["price"] or 0)
    except ValueError:
        unit_price = float(product["price"] or 0)

    next_q = (request.form.get("next_q") or "").strip()

    def back():
        return redirect(url_for("main.employee_desk", q=next_q))

    ok, message, _sale_total = _employee_apply_deduct(
        product, qty, unit_price, reason, note
    )
    flash(f"Salida: {message}" if ok else message, "ok" if ok else "error")
    return back()


@bp.post("/empleado/descontar-lote")
@employee_required
def employee_deduct_batch():
    next_q = (request.form.get("next_q") or "").strip()

    def back():
        return redirect(url_for("main.employee_desk", q=next_q))

    raw = (request.form.get("items") or "").strip()
    try:
        items = json.loads(raw) if raw else []
    except json.JSONDecodeError:
        flash("No pude leer el lote. Volvé a armarlo.", "error")
        return back()

    if not isinstance(items, list) or not items:
        flash("Seleccioná al menos una prenda para el lote.", "error")
        return back()

    reason, note = _parse_employee_reason_note()
    if note:
        note = f"[lote] {note}"
    else:
        note = "salida en lote"

    lines_ok = []
    lines_err = []
    grand_total = 0.0
    units_out = 0

    for raw_item in items[:40]:
        if not isinstance(raw_item, dict):
            continue
        try:
            product_id = int(raw_item.get("id"))
            qty = int(raw_item.get("qty") or 0)
        except (TypeError, ValueError):
            lines_err.append("Ítem inválido en el lote.")
            continue

        product = query_one("SELECT * FROM products WHERE id = ?", (product_id,))
        if product is None:
            lines_err.append(f"Prenda #{product_id} no encontrada.")
            continue

        try:
            unit_price = float(raw_item.get("unit_price") if raw_item.get("unit_price") is not None else product["price"] or 0)
        except (TypeError, ValueError):
            unit_price = float(product["price"] or 0)

        ok, message, sale_total = _employee_apply_deduct(
            product, qty, unit_price, reason, note
        )
        if ok:
            lines_ok.append(message)
            grand_total += sale_total
            units_out += qty
        else:
            lines_err.append(message)

    if lines_ok:
        flash(
            f"Lote OK: {len(lines_ok)} prenda(s), −{units_out} und. Total {format_cop(grand_total)}.",
            "ok",
        )
    if lines_err:
        flash("Algunas no salieron: " + " · ".join(lines_err[:4]), "error")
    if not lines_ok and not lines_err:
        flash("El lote estaba vacío.", "error")
    return back()


def _product_from_form():
    name = (request.form.get("name") or "").strip()
    description = (request.form.get("description") or "").strip()
    category = (request.form.get("category") or "General").strip() or "General"
    color = (request.form.get("color") or "").strip()
    size = (request.form.get("size") or "").strip()
    sku = (request.form.get("sku") or "").strip() or None
    image_url = (request.form.get("image_url") or "").strip()
    published = 1 if request.form.get("published") == "on" else 0

    try:
        price = float(request.form.get("price") or 0)
        stock = int(request.form.get("stock") or 0)
    except ValueError:
        return None, "Precio o stock inválido."

    if len(name) < 2:
        return None, "El nombre es obligatorio."
    if price <= 0:
        return None, "El precio de venta debe ser mayor a 0."
    if stock < 0:
        return None, "El stock no puede ser negativo."

    uploaded_url, upload_error = save_product_image(request.files.get("image_file"))
    if upload_error:
        return None, upload_error
    if uploaded_url:
        image_url = uploaded_url

    focus_x = clamp_focus(request.form.get("image_focus_x"), 50)
    focus_y = clamp_focus(request.form.get("image_focus_y"), 50)

    return {
        "name": name,
        "description": description,
        "category": category,
        "color": color,
        "size": size,
        "price": price,
        "stock": stock,
        "sku": sku,
        "image_url": image_url,
        "image_focus_x": focus_x,
        "image_focus_y": focus_y,
        "source": "OWN",
        "provider_name": None,
        "published": published,
    }, None


@bp.route("/admin/productos/nuevo", methods=["GET", "POST"])
@admin_required
def product_new():
    if request.method == "POST":
        data, error = _product_from_form()
        if error:
            flash(error, "error")
            return render_template("product_form.html", product=request.form, mode="new")

        now = datetime.now(timezone.utc).isoformat()
        try:
            execute(
                """
                INSERT INTO products (
                    name, description, category, color, size, price, stock, sku,
                    image_url, image_focus_x, image_focus_y, source, provider_name,
                    published, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    data["name"],
                    data["description"],
                    data["category"],
                    data["color"],
                    data["size"],
                    data["price"],
                    data["stock"],
                    data["sku"],
                    data["image_url"],
                    data["image_focus_x"],
                    data["image_focus_y"],
                    data["source"],
                    data["provider_name"],
                    data["published"],
                    now,
                    now,
                ),
            )
        except Exception:
            flash("No se pudo crear. ¿SKU duplicado?", "error")
            return render_template("product_form.html", product=request.form, mode="new")

        flash("Prenda creada.", "ok")
        return redirect(url_for("main.admin_inventory"))

    return render_template("product_form.html", product=None, mode="new")


@bp.route("/admin/productos/<int:product_id>", methods=["GET", "POST"])
@admin_required
def product_edit(product_id: int):
    product = query_one("SELECT * FROM products WHERE id = ?", (product_id,))
    if product is None:
        flash("Prenda no encontrada.", "error")
        return redirect(url_for("main.admin_inventory"))

    if request.method == "POST":
        data, error = _product_from_form()
        if error:
            flash(error, "error")
            return render_template(
                "product_form.html",
                product=request.form,
                mode="edit",
                product_id=product_id,
            )

        now = datetime.now(timezone.utc).isoformat()
        try:
            execute(
                """
                UPDATE products SET
                    name = ?, description = ?, category = ?, color = ?, size = ?,
                    price = ?, stock = ?, sku = ?, image_url = ?,
                    image_focus_x = ?, image_focus_y = ?, source = ?,
                    provider_name = ?, published = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    data["name"],
                    data["description"],
                    data["category"],
                    data["color"],
                    data["size"],
                    data["price"],
                    data["stock"],
                    data["sku"],
                    data["image_url"],
                    data["image_focus_x"],
                    data["image_focus_y"],
                    data["source"],
                    data["provider_name"],
                    data["published"],
                    now,
                    product_id,
                ),
            )
        except Exception:
            flash("No se pudo actualizar. ¿SKU duplicado?", "error")
            return render_template(
                "product_form.html",
                product=request.form,
                mode="edit",
                product_id=product_id,
            )

        flash("Prenda actualizada.", "ok")
        return redirect(url_for("main.admin_inventory"))

    return render_template(
        "product_form.html",
        product=product,
        mode="edit",
        product_id=product_id,
    )


@bp.route("/admin/ajustes", methods=["GET", "POST"])
@admin_required
def admin_settings():
    if request.method == "POST":
        raw = (request.form.get("whatsapp_number") or "").strip()
        phone = "".join(ch for ch in raw if ch.isdigit())
        if len(phone) < 10:
            flash("Ingresá un número válido con código de país (ej. 573001112233).", "error")
            return redirect(url_for("main.admin_settings"))
        set_setting("whatsapp_number", phone)
        flash("Número de WhatsApp actualizado. Las compras del catálogo van a ese chat.", "ok")
        return redirect(url_for("main.admin_settings"))

    return render_template(
        "admin_settings.html",
        whatsapp_number=whatsapp_number() or get_setting("whatsapp_number", ""),
    )


@bp.post("/admin/productos/<int:product_id>/eliminar")
@admin_required
def product_delete(product_id: int):
    product = query_one("SELECT id, name, image_url FROM products WHERE id = ?", (product_id,))
    if product is None:
        flash("Prenda no encontrada.", "error")
        return redirect(url_for("main.admin_inventory"))

    image_url = product["image_url"] or ""
    execute("DELETE FROM products WHERE id = ?", (product_id,))

    # Borra archivo local subido (si aplica)
    if image_url.startswith("/static/uploads/products/"):
        from flask import current_app
        from pathlib import Path

        filename = Path(image_url).name
        path = Path(current_app.config["PRODUCT_UPLOAD_DIR"]) / filename
        if path.is_file():
            try:
                path.unlink()
            except OSError:
                pass

    flash(f"«{product['name']}» eliminada del inventario y del catálogo.", "ok")
    return redirect(url_for("main.admin_inventory"))


@bp.post("/admin/productos/<int:product_id>/publicar")
@admin_required
def product_toggle_publish(product_id: int):
    product = query_one("SELECT id, name, published FROM products WHERE id = ?", (product_id,))
    if product is None:
        flash("Prenda no encontrada.", "error")
        return redirect(url_for("main.admin_inventory"))

    next_published = 0 if product["published"] else 1
    now = datetime.now(timezone.utc).isoformat()
    execute(
        "UPDATE products SET published = ?, updated_at = ? WHERE id = ?",
        (next_published, now, product_id),
    )
    if next_published:
        flash(f"«{product['name']}» publicada en el catálogo.", "ok")
    else:
        flash(f"«{product['name']}» ocultada del catálogo.", "ok")
    return redirect(url_for("main.admin_inventory"))


@bp.post("/admin/productos/<int:product_id>/stock")
@admin_required
def product_stock(product_id: int):
    delta = int(request.form.get("delta") or 0)
    product = query_one("SELECT stock FROM products WHERE id = ?", (product_id,))
    if product is None:
        flash("Prenda no encontrada.", "error")
        return redirect(url_for("main.admin_inventory"))

    next_stock = max(0, product["stock"] + delta)
    now = datetime.now(timezone.utc).isoformat()
    execute(
        "UPDATE products SET stock = ?, updated_at = ? WHERE id = ?",
        (next_stock, now, product_id),
    )
    return redirect(url_for("main.admin_inventory"))

