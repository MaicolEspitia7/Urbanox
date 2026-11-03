import os
import secrets
import sqlite3
from datetime import datetime, timezone

from flask import current_app, g
from werkzeug.security import generate_password_hash


def _seed_password(env_key: str, email: str) -> str:
    """Clave desde entorno, o una temporal (solo se imprime al crear el usuario)."""
    password = (os.environ.get(env_key) or "").strip()
    if password:
        return password
    password = secrets.token_urlsafe(10)
    print(f"[URBANOX] Usuario creado {email} — guardá esta clave: {password}")
    return password



def get_db() -> sqlite3.Connection:
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_error=None) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


def _ensure_column(db: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    cols = {row["name"] for row in db.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in cols:
        db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def init_db(app) -> None:
    app.teardown_appcontext(close_db)
    with app.app_context():
        db = get_db()
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS admins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'admin' CHECK(role IN ('admin', 'employee', 'kero')),
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                category TEXT NOT NULL DEFAULT 'General',
                color TEXT NOT NULL DEFAULT '',
                size TEXT NOT NULL DEFAULT '',
                price REAL NOT NULL,
                stock INTEGER NOT NULL DEFAULT 0,
                sku TEXT UNIQUE,
                image_url TEXT NOT NULL DEFAULT '',
                source TEXT NOT NULL CHECK(source IN ('OWN', 'PROVIDER')),
                provider_name TEXT,
                published INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS stock_moves (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                quantity INTEGER NOT NULL,
                note TEXT NOT NULL DEFAULT '',
                reason TEXT NOT NULL DEFAULT 'venta',
                source TEXT,
                unit_price REAL,
                sale_total REAL,
                stock_after INTEGER,
                created_at TEXT NOT NULL,
                FOREIGN KEY(product_id) REFERENCES products(id) ON DELETE CASCADE,
                FOREIGN KEY(user_id) REFERENCES admins(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL DEFAULT ''
            );
            """
        )
        _seed_settings(db)
        _ensure_column(db, "admins", "role", "TEXT NOT NULL DEFAULT 'admin'")
        _ensure_column(db, "stock_moves", "reason", "TEXT NOT NULL DEFAULT 'venta'")
        _ensure_column(db, "stock_moves", "source", "TEXT")
        _ensure_column(db, "stock_moves", "unit_price", "REAL")
        _ensure_column(db, "stock_moves", "sale_total", "REAL")
        _ensure_column(db, "stock_moves", "stock_after", "INTEGER")
        _ensure_column(db, "products", "image_focus_x", "INTEGER NOT NULL DEFAULT 50")
        _ensure_column(db, "products", "image_focus_y", "INTEGER NOT NULL DEFAULT 50")
        _migrate_admin_roles(db)
        # Todo el inventario se maneja como propio
        db.execute("UPDATE products SET source = 'OWN', provider_name = NULL")
        db.commit()
        seed_if_empty(db)


def _seed_settings(db: sqlite3.Connection) -> None:
    """Valores por defecto editables desde el admin."""
    from flask import current_app

    default_phone = (current_app.config.get("WHATSAPP_NUMBER") or "").strip()
    existing = db.execute(
        "SELECT value FROM settings WHERE key = 'whatsapp_number'"
    ).fetchone()
    if existing is None:
        db.execute(
            "INSERT INTO settings (key, value) VALUES ('whatsapp_number', ?)",
            (default_phone,),
        )


def get_setting(key: str, default: str = "") -> str:
    row = query_one("SELECT value FROM settings WHERE key = ?", (key,))
    if row is None:
        return default
    return row["value"] if row["value"] is not None else default


def set_setting(key: str, value: str) -> None:
    execute(
        """
        INSERT INTO settings (key, value) VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
        (key, value),
    )


def _migrate_admin_roles(db: sqlite3.Connection) -> None:
    """Recrea admins si el CHECK viejo no admite el rol kero."""
    row = db.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'admins'"
    ).fetchone()
    sql = (row["sql"] or "") if row else ""
    if "kero" in sql.lower():
        return

    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS admins_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'admin' CHECK(role IN ('admin', 'employee', 'kero')),
            created_at TEXT NOT NULL
        );
        INSERT INTO admins_new (id, email, name, password_hash, role, created_at)
        SELECT id, email, name, password_hash,
               CASE WHEN role IN ('admin', 'employee', 'kero') THEN role ELSE 'admin' END,
               created_at
        FROM admins;
        DROP TABLE admins;
        ALTER TABLE admins_new RENAME TO admins;
        """
    )


def seed_if_empty(db: sqlite3.Connection) -> None:
    now = datetime.now(timezone.utc).isoformat()

    admin = db.execute(
        "SELECT id FROM admins WHERE email = ?",
        ("admin@urbanox.com",),
    ).fetchone()
    if admin is None:
        db.execute(
            """
            INSERT INTO admins (email, name, password_hash, role, created_at)
            VALUES (?, ?, ?, 'admin', ?)
            """,
            (
                "admin@urbanox.com",
                "Administrador",
                generate_password_hash(_seed_password("URBANOX_ADMIN_PASSWORD", "admin@urbanox.com")),
                now,
            ),
        )
    else:
        db.execute(
            "UPDATE admins SET role = COALESCE(NULLIF(role, ''), 'admin') WHERE id = ?",
            (admin["id"],),
        )

    employee = db.execute(
        "SELECT id FROM admins WHERE email = ?",
        ("empleado@urbanox.com",),
    ).fetchone()
    if employee is None:
        db.execute(
            """
            INSERT INTO admins (email, name, password_hash, role, created_at)
            VALUES (?, ?, ?, 'employee', ?)
            """,
            (
                "empleado@urbanox.com",
                "Empleado",
                generate_password_hash(
                    _seed_password("URBANOX_EMPLOYEE_PASSWORD", "empleado@urbanox.com")
                ),
                now,
            ),
        )

    kero = db.execute(
        "SELECT id FROM admins WHERE email = ?",
        ("kero@urbanox.com",),
    ).fetchone()
    if kero is None:
        db.execute(
            """
            INSERT INTO admins (email, name, password_hash, role, created_at)
            VALUES (?, ?, ?, 'kero', ?)
            """,
            (
                "kero@urbanox.com",
                "Proveedor Kero",
                generate_password_hash(_seed_password("URBANOX_KERO_PASSWORD", "kero@urbanox.com")),
                now,
            ),
        )
    else:
        db.execute("UPDATE admins SET role = 'kero', name = ? WHERE id = ?", ("Proveedor Kero", kero["id"]))

    demo_images = {
        "URB-CAM-001": "/static/img/products/camisa-oversize.jpg",
        "URB-JEA-002": "/static/img/products/jean-indigo.jpg",
        "URB-HOO-003": "/static/img/products/hoodie-stone.jpg",
        "URB-CAP-004": "/static/img/products/gorra-snapback.jpg",
        "URB-BOM-005": "/static/img/products/bomber-night.jpg",
        "URB-TEE-006": "/static/img/products/tee-crown.jpg",
    }
    for sku, url in demo_images.items():
        db.execute(
            """
            UPDATE products
            SET image_url = ?
            WHERE sku = ?
            """,
            (url, sku),
        )

    count = db.execute("SELECT COUNT(*) AS c FROM products").fetchone()["c"]
    if count == 0:
        samples = [
            (
                "Camisa Oversize Negro",
                "Algodón premium, corte relajado. Pieza base del drop urbano.",
                "Camisas",
                "Negro",
                "M",
                89000,
                12,
                "URB-CAM-001",
                demo_images["URB-CAM-001"],
                "OWN",
                None,
                1,
                now,
                now,
            ),
            (
                "Jean Recto Índigo",
                "Denim rígido con lavado índigo. Silueta clean para la calle.",
                "Pantalones",
                "Índigo",
                "32",
                145000,
                8,
                "URB-JEA-002",
                demo_images["URB-JEA-002"],
                "OWN",
                None,
                1,
                now,
                now,
            ),
            (
                "Hoodie Urbanox Stone",
                "Felpa pesada con capucha y bolsillo canguro. Comfort con actitud.",
                "Abrigos",
                "Stone",
                "L",
                169000,
                5,
                "URB-HOO-003",
                demo_images["URB-HOO-003"],
                "OWN",
                None,
                1,
                now,
                now,
            ),
            (
                "Gorra Snapback Gold",
                "Estructura firme, visera plana. Detalle dorado Urbanox.",
                "Accesorios",
                "Negro/Oro",
                "Única",
                65000,
                15,
                "URB-CAP-004",
                demo_images["URB-CAP-004"],
                "OWN",
                None,
                1,
                now,
                now,
            ),
            (
                "Chaqueta Bomber Night",
                "Bomber ligera para salidas nocturnas. Cierre metal y ribetes.",
                "Abrigos",
                "Negro",
                "L",
                210000,
                4,
                "URB-BOM-005",
                demo_images["URB-BOM-005"],
                "OWN",
                None,
                1,
                now,
                now,
            ),
            (
                "Tee Graphic Crown",
                "Jersey 220gsm con graphic crown. El fit esencial del catálogo.",
                "Camisas",
                "Blanco",
                "M",
                72000,
                20,
                "URB-TEE-006",
                demo_images["URB-TEE-006"],
                "OWN",
                None,
                1,
                now,
                now,
            ),
        ]
        db.executemany(
            """
            INSERT INTO products (
                name, description, category, color, size, price, stock, sku,
                image_url, source, provider_name, published, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            samples,
        )
    db.commit()


def query_all(sql: str, args=()):
    return get_db().execute(sql, args).fetchall()


def query_one(sql: str, args=()):
    return get_db().execute(sql, args).fetchone()


def execute(sql: str, args=()):
    db = get_db()
    cur = db.execute(sql, args)
    db.commit()
    return cur
