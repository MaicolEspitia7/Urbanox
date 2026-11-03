# URBANOX

Inventario + catálogo streetwear (Flask).

## Qué incluye

- **Shop** público: catálogo, ficha de prenda y compra por WhatsApp
- **Admin**: inventario, prendas, ajustes de WhatsApp, movimientos Kero
- **Empleado**: salidas de tienda
- **Proveedor Kero**: anotaciones (se vendió / se retiró / se devolvió)

## Requisitos

- Python 3.11+

## Arranque local

```bash
python -m venv venv
# Windows
venv\Scripts\activate
# macOS/Linux
# source venv/bin/activate

pip install -r requirements.txt
python run.py
```

Abrí [http://127.0.0.1:5055](http://127.0.0.1:5055).

### Usuarios (primera vez)

Las claves **no** van en el código. Opciones:

1. Definí variables de entorno antes del primer arranque:
   - `URBANOX_ADMIN_PASSWORD`
   - `URBANOX_EMPLOYEE_PASSWORD`
   - `URBANOX_KERO_PASSWORD`
2. Si no las definís, al crear cada usuario la clave temporal se imprime en la consola.

Correos por defecto: `admin@urbanox.com`, `empleado@urbanox.com`, `kero@urbanox.com`.

## Notas de seguridad

- `urbanox.db`, `.env` y `.secret_key` **no** se suben al repo.
- `SECRET_KEY` y `WHATSAPP_NUMBER` pueden ir por entorno; el WhatsApp también se configura en Admin → **Ajustes**.
- Subidas: `app/static/uploads/products/` (ignorado en git salvo `.gitkeep`).
