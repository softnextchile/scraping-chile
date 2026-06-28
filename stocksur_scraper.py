#!/usr/bin/env python3
"""
Scraper para chile.stocksur.com
Extrae: nombre, código, descripción, dimensiones, material, peso,
        colores, imágenes (URLs), packing (volumen, cantidad por caja)
"""

import argparse
import json
import logging
import random
import re
import time
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

# ─── Configuración ────────────────────────────────────────────────────────────

BASE_URL = "https://chile.stocksur.com"
HEADLESS = True
TIMEOUT = 30_000  # ms

# ─── Logging ──────────────────────────────────────────────────────────────────

LOG_DIR = Path("/tmp/scraper_output")
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "scraper.log"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)


# ─── Scraper ───────────────────────────────────────────────────────────────────

class StocksurScraper:
    def __init__(self, delay: float = 0.6):
        self.delay = delay
        self.browser = None
        self.context = None
        self.page = None
        self._running = False
        self.seen_codes = set()

    # ── lifecycle ─────────────────────────────────────────────────────────────

    def start(self):
        self._running = True
        log.info("Iniciando navegador...")
        self.pw = sync_playwright().start()
        self.browser = self.pw.chromium.launch(headless=HEADLESS)
        self.context = self.browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            locale="es-CL",
        )
        self.page = self.context.new_page()
        log.info("Navegador listo.")

    def stop(self):
        self._running = False
        if self.page:
            self.page.close()
        if self.browser:
            self.browser.close()
        if hasattr(self, "pw"):
            self.pw.stop()
        log.info("Navegador cerrado.")

    # ── helpers ────────────────────────────────────────────────────────────────

    def _slug_to_name(self, slug: str) -> str:
        """Convierte /producto/silla-plegable-camp → SILLA PLEGABLE CAMP"""
        return " ".join(
            w.upper() for w in slug.split("-") if w and w not in ("y", "de", "la", "el")
        )

    def _clean_text(self, text: str) -> str:
        return re.sub(r"\s+", " ", text).strip()

    # ── extracción ─────────────────────────────────────────────────────────────

    def get_categories(self) -> list[dict]:
        """Devuelve [{name, url}] de todas las categorías."""
        log.info("Obteniendo categorías...")
        self.page.goto(BASE_URL, timeout=TIMEOUT)
        self.page.wait_for_load_state("domcontentloaded")
        time.sleep(2)

        nav_links = self.page.query_selector_all("nav a, .menu a, header a")
        categories = []
        seen_urls = set()

        for link in nav_links:
            href = link.get_attribute("href") or ""
            name = self._clean_text(link.inner_text())
            if "/colecciones/" in href or "/category/" in href:
                full_url = href if href.startswith("http") else BASE_URL + href
                if full_url not in seen_urls and len(name) > 2:
                    seen_urls.add(full_url)
                    categories.append({"name": name, "url": full_url})

        # Si no encontró en nav, buscar en el homepage
        if not categories:
            all_links = self.page.query_selector_all("a")
            for link in all_links:
                href = link.get_attribute("href") or ""
                name = self._clean_text(link.inner_text())
                if "/colecciones/" in href and href not in seen_urls:
                    full_url = href if href.startswith("http") else BASE_URL + href
                    seen_urls.add(full_url)
                    categories.append({"name": name, "url": full_url})

        log.info(f"Encontradas {len(categories)} categorías")
        return categories

    def get_products_in_category(self, category_url: str, category_name: str) -> list[dict]:
        """Itera paginación y devuelve lista de {name, code, url} por categoría."""
        page_num = 1
        products = []
        seen_urls = set()

        while self._running:
            url = f"{category_url}?page={page_num}" if page_num > 1 else category_url
            log.info(f"  Categoría '{category_name}' — página {page_num}")
            self.page.goto(url, timeout=TIMEOUT)
            self.page.wait_for_load_state("domcontentloaded")
            time.sleep(2)

            items = self.page.query_selector_all(".product-item, article.product, .product-card, [data-product-id]")
            found_new = 0

            for item in items:
                link_el = item.query_selector("a[href*='/producto/']") or item.query_selector("a")
                if not link_el:
                    continue
                href = link_el.get_attribute("href") or ""
                if not href or "/producto/" not in href:
                    continue
                full_url = href if href.startswith("http") else BASE_URL + href
                if full_url in seen_urls:
                    continue
                seen_urls.add(full_url)

                # Intentar extraer código del texto del item
                item_text = self._clean_text(item.inner_text())
                code_match = re.search(r"\b([A-Z]{1,3}\d{2,5})\b", item_text)
                code = code_match.group(1) if code_match else ""
                name = self._clean_text(
                    item.query_selector("h2, h3, .title, .name").inner_text()
                    if item.query_selector("h2, h3, .title, .name")
                    else item_text.split("\n")[0]
                )

                products.append({"name": name, "code": code, "url": full_url})
                found_new += 1

            log.info(f"    {found_new} productos nuevos — total {len(products)}")
            if found_new == 0:
                break
            page_num += 1
            time.sleep(self.delay)

        return products

    def get_product_details(self, url: str) -> dict | None:
        """Extrae todos los detalles de un producto individual."""
        # Eliminar '/colores/' para evitar redirecciones
        clean_url = re.sub(r"/colores/[^/]+", "", url)
        if clean_url != url:
            url = clean_url
            self.page.goto(url, timeout=TIMEOUT)
            self.page.wait_for_load_state("domcontentloaded")
            time.sleep(1.5)

        try:
            self.page.goto(url, timeout=TIMEOUT)
            self.page.wait_for_load_state("domcontentloaded")
            time.sleep(2)
        except Exception:
            return None

        body_text = self._clean_text(self.page.inner_text("body"))

        # ─ Nombre ─
        name = ""
        # Buscar en body con patrón: código + nombre (T798 Silla plegable "CAMP")
        m = re.search(r"\b([A-Z]{1,3}\d{2,5})\s*\n?\s*([A-ZÁÉÍÓÚÑ][^\n]{3,150})", body_text)
        if m:
            name = self._clean_text(m.group(2))
        if not name:
            m = re.search(r'"([^"]{3,100})"', body_text[:500])
            if m:
                name = m.group(1)
        if not name:
            # Fallback: extraer del title o slug
            slug = url.rstrip("/").split("/")[-1]
            name = self._slug_to_name(slug)

        # ─ Código ─
        code = ""
        m = re.search(r"\b([A-Z]{1,3}\d{2,5})\b", body_text[:500])
        if m:
            code = m.group(1)

        # ─ Descripción ─
        description = ""
        m = re.search(r"\n\n([^\n]{30,500})\n\n", body_text)
        if m:
            description = m.group(1)
        if not description:
            m = re.search(r"(?:Descripción|Descripción del producto)[:\s]*([^\n]{20,500})", body_text)
            if m:
                description = m.group(1)

        # ─ Dimensiones ─
        dimensions = ""
        m = re.search(r"Medidas?[:\s]*([^\n]{5,100})", body_text)
        if m:
            dimensions = m.group(1)

        # ─ Material ─
        material = ""
        m = re.search(r"Materiales?[:\s]*([^\n]{5,150})", body_text)
        if m:
            material = m.group(1)

        # ─ Peso ─
        weight = ""
        m = re.search(r"Peso[:\s]*([^\n]{5,80})", body_text)
        if m:
            weight = m.group(1)

        # ─ Imágenes ─
        images = []
        for img in self.page.query_selector_all("img[src]"):
            src = img.get_attribute("src") or ""
            if "logo-stocksur" in src.lower():
                continue
            if src.startswith("//"):
                src = "https:" + src
            elif src.startswith("/"):
                src = BASE_URL + src
            if src and src not in images:
                # Preferir /large/ sobre /medium/
                src = src.replace("/medium/", "/large/")
                images.append(src)

        # ─ Colores ─
        colors = []
        try:
            color_options = self.page.locator(
                'select[name="variacion[color]"] option, '
                '.variant-select option, '
                '[data-variant="color"] option'
            ).all_text_contents()
            colors = [self._clean_text(c) for c in color_options if c.strip()]
        except Exception:
            pass

        # ─ Packing ─
        volume = ""
        qty_per_box = 0
        m = re.search(r"Volumen[:\s]*([^\n,]{5,80})", body_text)
        if m:
            volume = m.group(1)
        m = re.search(r"Cantidad por caja[:\s]*(\d+)", body_text)
        if m:
            qty_per_box = int(m.group(1))

        return {
            "url": url,
            "name": name,
            "code": code,
            "description": description,
            "dimensions": dimensions,
            "material": material,
            "weight": weight,
            "images": images,
            "colors": colors,
            "packing": {
                "volume": volume,
                "quantity_per_box": qty_per_box,
            },
        }

    # ── scrape completo ────────────────────────────────────────────────────────

    def scrape_all(self) -> list[dict]:
        """Orquestador principal. Devuelve lista de productos."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = LOG_DIR / f"stocksur_products_{timestamp}.json"
        all_products = []
        categories = self.get_categories()

        for cat in categories:
            if not self._running:
                break
            log.info(f"Procesando categoría: {cat['name']}")
            cat_products = self.get_products_in_category(cat["url"], cat["name"])
            log.info(f"  {len(cat_products)} productos en '{cat['name']}'")

            for prod in cat_products:
                if not self._running:
                    break
                if prod["code"] in self.seen_codes:
                    log.info(f"  Saltando duplicado: {prod['code']}")
                    continue

                log.info(f"  Extrayendo detalles: {prod['code']} — {prod['name']}")
                details = self.get_product_details(prod["url"])
                if details:
                    details["category"] = cat["name"]
                    all_products.append(details)
                    self.seen_codes.add(details["code"])
                    log.info(
                        f"  ✓ {details['code']} | {details['name'][:40]} | "
                        f"{len(details['images'])} img | {len(details['colors'])} colores"
                    )

                time.sleep(self.delay)

            # Guardar parcial cada categoría
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(all_products, f, ensure_ascii=False, indent=2)
            log.info(f"  Guardado parcial: {len(all_products)} productos")

        log.info(f"Scraping completado: {len(all_products)} productos únicos")
        return all_products


# ─── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Scraper Stocksur Chile")
    parser.add_argument("--delay", type=float, default=0.6, help="Segundos entre requests")
    parser.add_argument("--headless", action="store_true", default=True)
    parser.add_argument("--no-headless", dest="headless", action="store_false")
    args = parser.parse_args()

    global HEADLESS
    HEADLESS = args.headless

    scraper = StocksurScraper(delay=args.delay)
    try:
        scraper.start()
        products = scraper.scrape_all()

        timestamp = datetime.now().strftime("%Y%m%d")
        out_path = Path(__file__).parent / f"stocksur_products_{timestamp}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(products, f, ensure_ascii=False, indent=2)
        log.info(f"Guardado final: {out_path}")
        print(f"Productos: {len(products)}")
    finally:
        scraper.stop()


if __name__ == "__main__":
    main()
