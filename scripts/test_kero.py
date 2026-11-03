"""Prueba rápida del flujo Kero. Requiere URBANOX_KERO_PASSWORD en el entorno."""
import os
import sys

from app import create_app
from app.db import query_all, query_one

password = (os.environ.get("URBANOX_KERO_PASSWORD") or "").strip()
if not password:
    print("Definí URBANOX_KERO_PASSWORD para correr este script.")
    sys.exit(1)

app = create_app()
client = app.test_client()

login = client.post(
    "/admin/login",
    data={"email": "kero@urbanox.com", "password": password},
    follow_redirects=False,
)
print("login", login.status_code, login.headers.get("Location"))

with app.app_context():
    product = query_one("SELECT id, stock, name, price FROM products ORDER BY id LIMIT 1")
    print("product", dict(product))
    product_id = product["id"]
    unit_price = str(product["price"])

deduct = client.post(
    f"/kero/productos/{product_id}/salida",
    data={
        "quantity": "1",
        "reason": "venta_kero",
        "note": "demo kero",
        "unit_price": unit_price,
    },
    follow_redirects=True,
)
print("deduct", deduct.status_code)

with app.app_context():
    mid = query_one("SELECT id, stock FROM products WHERE id = ?", (product_id,))
    print("stock_after_out", dict(mid))

ret = client.post(
    f"/kero/productos/{product_id}/salida",
    data={
        "quantity": "1",
        "reason": "devolucion",
        "note": "devolucion demo",
        "unit_price": unit_price,
    },
    follow_redirects=True,
)
print("return", ret.status_code)

with app.app_context():
    after = query_one("SELECT id, stock FROM products WHERE id = ?", (product_id,))
    moves = query_all(
        """
        SELECT source, reason, quantity, note, stock_after
        FROM stock_moves
        WHERE source = 'KERO'
        ORDER BY id DESC
        LIMIT 3
        """
    )
    print("stock_after_in", dict(after))
    print("moves", [dict(m) for m in moves])
