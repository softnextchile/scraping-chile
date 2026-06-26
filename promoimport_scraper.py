"""
Promoimport Scraper para Chile
==============================
Extrae productos desde promoimport.cl usando Playwright.

Uso:
    python promoimport_scraper.py --category "lapices" --limit 50
    python promoimport_scraper.py --search "promociones" --format json
"""

import argparse
import csv
import json
import time
import random
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright


class PromoimportScraper:
    """Scraper de promoimport.cl usando Playwright."""

    BASE_URL = "https://www.promoimport.cl"

    def __init__(self, headless: bool = True, slow_mo: int = 150):
        """Inicializa el scraper.

        Args:
            headless: Si True, el navegador no muestra ventana (recomendado).
            slow_mo: Milisegundos de delay entre acciones.
        """
        self.playwright = None
        self.browser = None
        self.page = None
        self.headless = headless
        self.slow_mo = slow_mo
        self.results = []

    def start(self):
        """Inicia el navegador."""
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(
            headless=self.headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-web-security",
                "--disable-features=IsolateOrigins,site-per-process",
            ],
        )
        context = self.browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            locale="es-CL",
            timezone_id="America/Santiago",
            extra_http_headers={
                "Accept-Language": "es-CL,es;q=0.9,en;q=0.8",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
        )
        self.page = context.new_page()
        # Bloquear recursos pesados
        self.page.route(
            "**/*.{png,jpg,jpeg,gif,svg,ico,woff,woff2}",
            lambda route: route.abort(),
        )
        self.page.route(
            "**/ads/**",
            lambda route: route.abort(),
        )
        # Detectar y reportar bloqueos de Cloudflare
        self.page.on("response", self._check_blocked)

    def _check_blocked(self, response):
        """Detecta si Cloudflare está bloqueando."""
        if response.status in [403, 503]:
            body = response.text() if hasattr(response, 'text') else ""
            if "cloudflare" in body.lower() or "cf-" in body.lower():
                print(f"[!] ALERTA: Cloudflare bloqueando ({response.status})")

    def stop(self):
        """Cierra el navegador."""
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()

    def wait_for_cloudflare(self, timeout: int = 15):
        """Espera a que Cloudflare pase o verifique si está bloqueado."""
        time.sleep(2)
        title = self.page.title()
        if "cloudflare" in title.lower() or "blocked" in title.lower():
            print(f"[!] Cloudflare bloquendo la solicitud")
            return False
        return True

    def get_categories(self) -> list:
        """Extrae todas las categorías disponibles."""
        print(f"[+] Obteniendo categorías desde {self.BASE_URL}")
        self.page.goto(self.BASE_URL, wait_until="networkidle", timeout=30000)

        if not self.wait_for_cloudflare():
            return []

        categories = []

        # Selector común para menús de categorías en ecommerce chileno
        selectors = [
            "nav.categories a",
            ".category-menu a",
            "[class*='category'] a",
            ".menu-item a",
            ".nav-links a",
            "header a[href*='category']",
            ".sidebar a",
        ]

        for selector in selectors:
            try:
                links = self.page.query_selector_all(selector)
                if links:
                    for link in links:
                        href = link.get_attribute("href") or ""
                        text = link.inner_text().strip()
                        if href and text and "/category/" in href:
                            categories.append({
                                "name": text,
                                "url": href if href.startswith("http") else self.BASE_URL + href,
                            })
                    if categories:
                        break
            except Exception:
                continue

        print(f"[+] {len(categories)} categorías encontradas")
        return categories

    def get_products_from_page(self) -> list:
        """Extrae productos de la página actual."""
        products = []

        # Selectores comunes para productos en ecommerce chileno
        selectors = [
            ".product-item",
            ".product-card",
            ".item-product",
            "[class*='product']",
            ".catalog-item",
            ".products li",
        ]

        cards = []
        for selector in selectors:
            try:
                cards = self.page.query_selector_all(selector)
                if cards:
                    break
            except Exception:
                continue

        for card in cards:
            try:
                product = self._extract_product_data(card)
                if product and product.get("name"):
                    products.append(product)
            except Exception as e:
                print(f"    [!] Error extrayendo producto: {e}")
                continue

        return products

    def _extract_product_data(self, card) -> dict:
        """Extrae datos de una tarjeta de producto."""
        data = {
            "name": None,
            "sku": None,
            "price": None,
            "original_price": None,
            "category": None,
            "url": None,
            "image_url": None,
            "description": None,
            "stock": None,
            "extracted_at": datetime.now().isoformat(),
        }

        try:
            # Nombre
            name_selectors = ["h2", "h3", ".title", ".name", "[class*='title']"]
            for sel in name_selectors:
                try:
                    elem = card.query_selector(sel)
                    if elem:
                        data["name"] = elem.inner_text().strip()
                        break
                except Exception:
                    continue

            # Precio
            price_selectors = [".price", ".current-price", "[class*='price']", ".offer-price"]
            for sel in price_selectors:
                try:
                    elem = card.query_selector(sel)
                    if elem:
                        text = elem.inner_text().strip()
                        # Limpiar formato chileno: $1.234 -> 1234
                        import re
                        numbers = re.findall(r"[\d.]+", text.replace("$", ""))
                        if numbers:
                            # Tomar el último número (precio actual)
                            data["price"] = numbers[-1]
                        break
                except Exception:
                    continue

            # Precio original (tachado)
            try:
                orig = card.query_selector(".original-price, .old-price, [class*='was']")
                if orig:
                    text = orig.inner_text()
                    numbers = re.findall(r"[\d.]+", text)
                    if numbers:
                        data["original_price"] = numbers[0]
            except Exception:
                pass

            # SKU
            try:
                sku = card.query_selector("[class*='sku'], [class*='code']")
                if sku:
                    data["sku"] = sku.inner_text().strip()
            except Exception:
                pass

            # URL del producto
            try:
                link = card.query_selector("a")
                if link:
                    href = link.get_attribute("href") or ""
                    data["url"] = href if href.startswith("http") else self.BASE_URL + href
            except Exception:
                pass

            # Imagen
            try:
                img = card.query_selector("img")
                if img:
                    data["image_url"] = img.get_attribute("src") or img.get_attribute("data-src") or ""
            except Exception:
                pass

            # Stock
            try:
                stock = card.query_selector("[class*='stock'], [class*='availability']")
                if stock:
                    data["stock"] = stock.inner_text().strip()
            except Exception:
                pass

        except Exception as e:
            print(f"    [!] Error extrayendo datos de producto: {e}")

        return data

    def scroll_page(self, max_scrolls: int = 5):
        """Hace scroll para cargar más productos (paginación infinita)."""
        last_height = 0

        for i in range(max_scrolls):
            # Scroll hacia abajo
            self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(random.uniform(1.5, 2.5))

            # Verificar si hay más contenido
            new_height = self.page.evaluate("document.body.scrollHeight")
            if new_height == last_height:
                print(f"    [i] Scroll detenido (altura no cambió)")
                break

            last_height = new_height
            print(f"    [i] Scroll {i+1}/{max_scrolls} completado")

            # Intentar cargar más resultados si hay botón
            try:
                more_btn = self.page.query_selector(
                    "button[class*='more'], .load-more, [class*='load']"
                )
                if more_btn:
                    more_btn.click()
                    time.sleep(random.uniform(1, 2))
            except Exception:
                pass

    def scrape_category(self, category: str = None, limit: int = 100) -> list:
        """Extrae productos de una categoría.

        Args:
            category: Nombre o URL de la categoría. Si es None, scrapea todo el sitio.
            limit: Máximo de productos a extraer.

        Returns:
            Lista de diccionarios con datos de cada producto.
        """
        self.results = []

        if category:
            if category.startswith("http"):
                url = category
            else:
                # Buscar categoría en el sitio
                slug = category.lower().replace(" ", "-")
                url = f"{self.BASE_URL}/category/{slug}"
        else:
            url = self.BASE_URL

        print(f"[+] Navegando a: {url}")
        self.page.goto(url, wait_until="networkidle", timeout=45000)

        if not self.wait_for_cloudflare():
            print("[!] Sitio bloqueado por Cloudflare")
            return self.results

        print(f"[+] Extrayendo productos...")
        self.scroll_page(max_scrolls=5)

        # Extraer productos
        products = self.get_products_from_page()
        self.results.extend(products[:limit])

        print(f"[+] Extraídos {len(self.results)} productos")
        return self.results

    def search(self, query: str, limit: int = 100) -> list:
        """Busca productos por término.

        Args:
            query: Término de búsqueda.
            limit: Máximo de productos.

        Returns:
            Lista de productos encontrados.
        """
        self.results = []
        search_url = f"{self.BASE_URL}/?s={query.replace(' ', '+')}"

        print(f"[+] Buscando: '{query}' en {search_url}")
        self.page.goto(search_url, wait_until="networkidle", timeout=45000)

        if not self.wait_for_cloudflare():
            return self.results

        self.scroll_page(max_scrolls=5)
        self.results = self.get_products_from_page()[:limit]

        print(f"[+] {len(self.results)} productos encontrados")
        return self.results

    def save_to_csv(self, filename: str = None) -> str:
        """Guarda los resultados en CSV."""
        if not self.results:
            print("[!] No hay resultados para guardar")
            return None

        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"promoimport_products_{timestamp}.csv"

        filepath = Path(filename)
        fieldnames = [
            "name", "sku", "price", "original_price", "category",
            "url", "image_url", "description", "stock", "extracted_at",
        ]

        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(self.results)

        print(f"[+] Guardado en: {filepath}")
        return str(filepath)

    def save_to_json(self, filename: str = None) -> str:
        """Guarda los resultados en JSON."""
        if not self.results:
            print("[!] No hay resultados para guardar")
            return None

        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"promoimport_products_{timestamp}.json"

        filepath = Path(filename)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.results, f, ensure_ascii=False, indent=2)

        print(f"[+] Guardado en: {filepath}")
        return str(filepath)


def main():
    parser = argparse.ArgumentParser(
        description="Promoimport Scraper para Chile",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python promoimport_scraper.py --category "lapices" --limit 50
  python promoimport_scraper.py --category "cuadernos" --format json
  python promoimport_scraper.py --search "promocion" --limit 100
  python promoimport_scraper.py --list-categories
        """,
    )
    parser.add_argument(
        "--category",
        "-c",
        type=str,
        default=None,
        help="Categoría a scrapear (nombre o URL)",
    )
    parser.add_argument(
        "--search",
        "-s",
        type=str,
        default=None,
        help="Término de búsqueda",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Máximo de productos (default: 100)",
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["csv", "json", "both"],
        default="csv",
        help="Formato de salida (default: csv)",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=None,
        help="Nombre base del archivo de salida (sin extensión)",
    )
    parser.add_argument(
        "--visible",
        action="store_true",
        help="Muestra el navegador (útil para debug)",
    )
    parser.add_argument(
        "--list-categories",
        action="store_true",
        help="Lista las categorías disponibles",
    )

    args = parser.parse_args()

    print("=" * 60)
    print("  Promoimport Scraper - Chile")
    print("=" * 60)

    scraper = PromoimportScraper(headless=not args.visible)

    try:
        scraper.start()

        if args.list_categories:
            categories = scraper.get_categories()
            if categories:
                print("\nCategorías disponibles:")
                for cat in categories:
                    print(f"  - {cat['name']}: {cat['url']}")
                scraper.save_to_json("promoimport_categories.json")
            return

        results = []

        if args.search:
            results = scraper.search(query=args.search, limit=args.limit)
        elif args.category:
            results = scraper.scrape_category(category=args.category, limit=args.limit)
        else:
            results = scraper.scrape_category(limit=args.limit)

        if results:
            base = args.output or "promoimport_products"

            if args.format in ["csv", "both"]:
                scraper.save_to_csv(f"{base}.csv")

            if args.format in ["json", "both"]:
                scraper.save_to_json(f"{base}.json")
        else:
            print("[!] No se encontraron productos")
            print("[i] Posibles razones:")
            print("    - Cloudflare está bloqueando las solicitudes")
            print("    - La estructura del sitio cambió")
            print("    - La categoría no existe")
            print("\nPrueba con --visible para ver qué pasa en el navegador")

    except KeyboardInterrupt:
        print("\n[!] Interrupted by user")
        if scraper.results:
            print(f"[+] Guardando {len(scraper.results)} resultados antes de salir...")
            scraper.save_to_csv()
    finally:
        scraper.stop()


if __name__ == "__main__":
    main()