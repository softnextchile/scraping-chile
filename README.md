# Web Scraping Tools - Chile

Colección de herramientas de scraping para extraer datos de negocios desde Google Maps e Instagram. Diseñado para ejecutarse **localmente** (en tu computador) para evitar bloqueos por geolocalización.

## Tabla de Contenidos

- [Requisitos](#requisitos)
- [Instalación](#instalación)
- [Google Maps Scraper](#google-maps-scraper)
- [Instagram Scraper](#instagram-scraper)
- [Ejecutar desde Docker (Opcional)](#ejecutar-desde-docker-opcional)
- [Notas Importantes](#notas-importantes)
- [Solución de Problemas](#solución-de-problemas)

---

## Requisitos

- **Python 3.9+** instalado
- **Sistema operativo**: Windows, macOS, o Linux (el que uses localmente)
- **Conexión a internet** desde Chile (IP chilena recomendada)
- Para Instagram: cuenta de Instagram (opcional, mejora los resultados)

---

## Instalación

### 1. Clonar o descargar el repositorio

```bash
git clone https://github.com/softnextchile/scraping-chile.git
cd scraping-chile
```

### 2. Crear entorno virtual (recomendado)

```bash
python -m venv venv

# En Windows
venv\Scripts\activate

# En macOS/Linux
source venv/bin/activate
```

### 3. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 4. Instalar navegadores de Playwright

```bash
playwright install chromium
```

---

## Google Maps Scraper

Extrae datos de negocios desde Google Maps: nombre, dirección, teléfono, rating, coordenadas, y más.

### Uso básico

```bash
# Buscar restaurantes en Maipú
python google_maps_scraper.py --query "restaurantes" --location "Maipú, Santiago"

# Buscar cafeterías en Providencia
python google_maps_scraper.py --query "cafes" --location "Providencia, Santiago" --limit 100

# Exportar a JSON
python google_maps_scraper.py --query "talleres" --location "Santiago" --format json
```

### Opciones disponibles

| Opción | Descripción | Ejemplo |
|--------|-------------|---------|
| `--query, -q` | Tipo de negocio | `"restaurantes"`, `"cafes"`, `"tiendas"` |
| `--location, -l` | Ubicación | `"Maipú, Santiago"`, `"Las Condes, Santiago"` |
| `--limit` | Máximo de resultados | `50` (default), `100`, `200` |
| `--format, -f` | Formato de salida | `csv` (default), `json`, `both` |
| `--output, -o` | Nombre del archivo | `"mis_negocios"` |
| `--visible` | Mostrar navegador | Sin flag = headless (oculto) |

### Categorías predefinidas

Puedes usar el nombre de la categoría directamente:

```bash
python google_maps_scraper.py --query "restaurantes" --location "Santiago"
python google_maps_scraper.py --query "cafes" --location "Santiago"
python google_maps_scraper.py --query "peluquerias" --location "Santiago"
python google_maps_scraper.py --query "talleres" --location "Santiago"
python google_maps_scraper.py --query "farmacias" --location "Santiago"
python google_maps_scraper.py --query "gimnasios" --location "Santiago"
```

### Salida

El script genera archivos CSV con las siguientes columnas:

| Campo | Descripción |
|-------|-------------|
| `name` | Nombre del negocio |
| `category` | Categoría/rubro |
| `address` | Dirección |
| `phone` | Teléfono |
| `website` | Sitio web (si está disponible) |
| `rating` | Puntuación (1-5) |
| `reviews_count` | Cantidad de reseñas |
| `latitude` | Latitud GPS |
| `longitude` | Longitud GPS |
| `place_id` | ID de Google Maps |
| `extracted_at` | Fecha/hora de extracción |

### Ejemplo de salida CSV

```csv
name,category,address,phone,rating,latitude,longitude
"La Casa de la Sopa","Restaurante","Av. Maipú 123, Maipú","+56 2 2345 6789",4.5,-33.4890,-70.6543
"Café del Barrio","Cafetería","Padre Hurtado 456, Maipú","+56 2 2345 6790",4.2,-33.4870,-70.6520
```

---

## Instagram Scraper

Extrae datos de posts y cuentas de negocio desde Instagram usando hashtags o ubicaciones.

### Uso básico

```bash
# Buscar por hashtag
python instagram_scraper.py --hashtag "comidachilena" --limit 50

# Buscar por ubicación
python instagram_scraper.py --location "maipu-chile" --limit 100

# Login para mejores resultados
python instagram_scraper.py --login --username TU_USUARIO --password TU_PASSWORD
```

### Opciones disponibles

| Opción | Descripción |
|--------|-------------|
| `--hashtag` | Hashtag a buscar (sin #) |
| `--location` | Slug de ubicación de Instagram |
| `--limit` | Máximo de resultados (default: 50) |
| `--format` | `csv`, `json`, o `both` |
| `--login` | Iniciar sesión antes de buscar |
| `--username` | Usuario de Instagram |
| `--password` | Contraseña de Instagram |
| `--session` | Archivo de sesión guardada |
| `--visible` | Mostrar navegador |
| `--slow-mo` | Delay entre acciones en ms |

### Login (Recomendado)

Para mejores resultados, primero inicia sesión:

```bash
python instagram_scraper.py --login --username tu_usuario --password tu_password
```

Esto guarda las cookies en `instagram_state.json` y las reutiliza en futuras ejecuciones.

### Salida

| Campo | Descripción |
|-------|-------------|
| `username` | Usuario de Instagram |
| `full_name` | Nombre completo |
| `post_url` | URL del post |
| `likes` | Cantidad de likes |
| `caption` | Texto del post |
| `location` | Ubicación mencionada |
| `extracted_at` | Fecha/hora de extracción |

---

## Ejecutar desde Docker (Opcional)

Si prefieres no instalar dependencias localmente:

```bash
# Construir la imagen
docker build -t scraping-chile .

# Ejecutar Google Maps scraper
docker run --rm -v $(pwd)/output:/app/output scraping-chile \
  python google_maps_scraper.py --query "restaurantes" --location "Santiago"

# Ejecutar Instagram scraper
docker run --rm -v $(pwd)/output:/app/output scraping-chile \
  python instagram_scraper.py --hashtag "comidachilena"
```

**Nota**: Docker aún tendrá el problema de geolocalización. Es mejor ejecutar localmente.

---

## Notas Importantes

### ⚠️ Sobre geolocalización

Estos scripts están diseñados para ejecutarse **localmente** (en tu computador en Chile). Si los ejecutas en un servidor remoto en otro país, Google Maps e Instagram bloquararán las solicitudes.

### ⚠️ Rate limits

- **Google Maps**: Puede mostrar CAPTCHAs después de ~100 búsquedas seguidas
- **Instagram**: Puede bloquear tu cuenta si haces demasiado scraping

Recomendación: usa `--limit` moderado y espera entre ejecuciones.

### ⚠️ Términos de servicio

El scraping puede violar los términos de servicio de Google Maps e Instagram. Usar para fines personales y de investigación. No usar para spam o venta de datos.

---

## Solución de Problemas

### Error: "Playwright browsers not installed"

```bash
playwright install chromium
```

### Error: "Timeout" o "Navigation failed"

- Verifica tu conexión a internet
- Intenta con `--visible` para ver qué pasa
- Puede que Google Maps esté mostrando un CAPTCHA (espera unos minutos)

### Instagram muestra pantalla de login

```bash
# Primero inicia sesión
python instagram_scraper.py --login --username TU_USUARIO --password TU_PASSWORD

# Luego usa la sesión guardada
python instagram_scraper.py --hashtag "comida" --session instagram_state.json
```

### El scraper se ejecuta muy lento

- Reduce `--slow-mo` para ir más rápido (puede aumentar detección)
- Usa `--limit` menor para pruebas

### No encuentra resultados

- Verifica que la IP sea de Chile
- Intenta con términos más genéricos
- Para Instagram, usa hashtags populares en español

---

## Estructura del Proyecto

```
scraping-chile/
├── google_maps_scraper.py   # Scraper de Google Maps
├── instagram_scraper.py      # Scraper de Instagram
├── requirements.txt          # Dependencias de Python
├── README.md                # Este archivo
└── output/                  # Carpeta para resultados (crear manualmente)
    ├── google_maps_results_20240611.csv
    └── instagram_results_20240611.csv
```

---

## Próximos Pasos

1. Ejecuta los scrapers desde tu computador local
2. Los resultados se guardan en archivos CSV/JSON
3. Puedes importar los CSV a Excel o Google Sheets
4. Para enviar por email, usa el script `enviar_resultados.py` (próximamente)

---

## Licencia

Para uso personal y educativo. No usar comercialmente sin consentimiento de las plataformas.
