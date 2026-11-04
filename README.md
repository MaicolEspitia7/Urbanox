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
# Windows PowerShell
.\venv\Scripts\Activate.ps1
# Windows CMD
# venv\Scripts\activate.bat
# Git Bash / macOS / Linux
# source venv/bin/activate   # o: source venv/Scripts/activate

pip install -r requirements.txt
python run.py
```

Abrí [http://127.0.0.1:5055](http://127.0.0.1:5055).

Sin `DATABASE_URL` la app usa **SQLite** (`urbanox.db`).

### Usuarios (primera vez)

Las claves **no** van en el código. Opciones:

1. Definí variables de entorno antes del primer arranque:
   - `URBANOX_ADMIN_PASSWORD`
   - `URBANOX_EMPLOYEE_PASSWORD`
   - `URBANOX_KERO_PASSWORD`
2. Si no las definís, al crear cada usuario la clave temporal se imprime en la consola.

Correos por defecto: `admin@urbanox.com`, `empleado@urbanox.com`, `kero@urbanox.com`.

Ejemplo (Git Bash):

```bash
export URBANOX_ADMIN_PASSWORD="admin123"
export URBANOX_EMPLOYEE_PASSWORD="empleado123"
export URBANOX_KERO_PASSWORD="kero123"
export WHATSAPP_NUMBER="573212055222"
rm -f urbanox.db
python run.py
```

## Deploy online (Render + Supabase)

GitHub guarda el código. **Render** corre la app. **Supabase** guarda Postgres (el inventario no se pierde al redeploy).

### 1) Supabase

1. Creá un proyecto en [supabase.com](https://supabase.com).
2. **Project Settings → Database → Connection string → URI**.
3. Preferí el **pooler** (puerto `6543`) e insertá la password del proyecto.
4. Ejemplo: `postgresql://postgres.xxxx:TU_PASSWORD@aws-0-....pooler.supabase.com:6543/postgres`

La app crea las tablas sola al arrancar con `DATABASE_URL`.

### 2) Render

1. [render.com](https://render.com) → Login with GitHub → **New → Web Service**.
2. Conectá el repo `Urbanox`.
3. Ajustes:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn -b 0.0.0.0:$PORT "run:app"`
4. **Environment** (Environment Variables):

| Key | Valor |
|-----|--------|
| `DATABASE_URL` | URI de Supabase |
| `SECRET_KEY` | clave larga aleatoria |
| `WHATSAPP_NUMBER` | `573212055222` |
| `URBANOX_ADMIN_PASSWORD` | tu clave admin |
| `URBANOX_EMPLOYEE_PASSWORD` | tu clave empleado |
| `URBANOX_KERO_PASSWORD` | tu clave kero |

5. Deploy → URL tipo `https://urbanox-xxxx.onrender.com`.

Cada `git push` a la rama conectada vuelve a desplegar. El plan free de Render se duerme ~15 min sin tráfico; el primer hit puede tardar 30–60s.

## Notas de seguridad

- `urbanox.db`, `.env` y `.secret_key` **no** se suben al repo.
- `SECRET_KEY`, `DATABASE_URL` y `WHATSAPP_NUMBER` van por entorno (Render / local).
- Subidas: `app/static/uploads/products/` (en Render el disco es efímero; las fotos demo del repo en `/static/img` sí persisten).
