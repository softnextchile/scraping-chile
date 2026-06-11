"""
Google Maps Scraper para Chile
==============================
Extrae datos de negocios desde Google Maps usando Playwright.
Ejecutar LOCALMENTE (no funciona en servidores remotos por geolocalización).

Uso:
    python google_maps_scraper.py --query "restaurantes" --location "Maipú, Santiago"
    python google_maps_scraper.py --query "cafes" --location "Providencia, Santiago" --limit 50
"""

import argparse
import csv
import json
import time
import random
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright


class GoogleMapsScraper:
    """Scraper de Google Maps usando Playwright."""

    BASE_URL = "https://www.google.com/maps"

    # Categorías predefinidas para facilitar búsqueda
    CATEGORIES = {
        "restaurantes": "restaurantes",
        "cafes": "cafeterías",
        "tiendas": "tiendas",
        "peluquerias": "peluquerías",
        "talleres": "talleres mecánicos",
        "farmacias": "farmacias",
        "supermercados": "supermercados",
        "gimnasios": "gimnasios",
        "dentistas": "dentistas",
        "bancos": "bancos",
    }

    def __init__(self, headless: bool = True, slow_mo: int = 100):
        """Inicializa el scraper.

        Args:
            headless: Si True, el navegador no muestra ventana (recomendado).
            slow_mo: Milisegundos de delay entre acciones (ayuda a evitar detección).
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
            ],
        )
        # Crear contexto con usuario realista
        context = self.browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            locale="es-CL",
            timezone_id="America/Santiago",
            geolocation={"latitude": -33.4489, "longitude": -70.6693},
            permissions=["geolocation"],
        )
        self.page = context.new_page()
        # Bloquear recursos pesados innecesarios
        self.page.route(
            "**/*.{png,jpg,jpeg,gif,svg,ico,woff,woff2}",
            lambda route: route.abort(),
        )
        self.page.route(
            "**/ads*/**",
            lambda route: route.abort(),
        )

    def stop(self):
        """Cierra el navegador."""
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()

    def search(self, query: str, location: str, limit: int = 50) -> list:
        """Busca negocios en Google Maps.

        Args:
            query: Tipo de negocio (ej: "restaurantes", "cafes")
            location: Ubicación (ej: "Maipú, Santiago")
            limit: Máximo de resultados a extraer

        Returns:
            Lista de diccionarios con datos de cada negocio
        """
        self.results = []
        search_url = f"{self.BASE_URL}/search/{query}@{location}"

        print(f"[+] Abriendo Google Maps: {search_url}")
        self.page.goto(search_url)

        # Aceptar cookies si aparece el popup
        self._accept_cookies()

        # Scroll para cargar más resultados
        print(f"[+] Buscando: {query} en {location}")
        self._scroll_results(limit)

        # Extraer datos de cada tarjeta
        self._extract_cards(limit)

        print(f"[+] Extraídos {len(self.results)} resultados")
        return self.results

    def _accept_cookies(self):
        """Acepta el popup de cookies si aparece."""
        try:
            # Intentar múltiples selectores
            selectors = [
                'button[aria-label*="Aceitar"]',
                'button[aria-label*="Aceptar"]',
                'button[aria-label*="Accept"]',
                "#LGAyq",
                'button[action*="accept"]',
            ]
            for selector in selectors:
                try:
                    self.page.wait_for_selector(selector, timeout=3000)
                    self.page.click(selector)
                    time.sleep(random.uniform(0.5, 1))
                    break
                except Exception:
                    continue
        except Exception:
            pass

    def _scroll_results(self, limit: int):
        """Hace scroll en los resultados para cargar más."""
        scroll_count = 0
        max_scrolls = (limit // 10) + 5  # Aproximadamente 10 resultados por scroll

        while scroll_count < max_scrolls and len(self.results) < limit:
            # Scroll hacia abajo
            self.page.evaluate(
                'document.querySelector(".result-files").scrollBy(0, 800)'
            )
            time.sleep(random.uniform(1, 2))

            # Intentar cargar más resultados (botón "Más resultados")
            try:
                more_btn = self.page.query_selector(
                    'button[aria-label*="Más resultados"]'
                )
                if more_btn:
                    more_btn.click()
                    time.sleep(random.uniform(1, 2))
            except Exception:
                pass

            scroll_count += 1

    def _extract_cards(self, limit: int):
        """Extrae datos de las tarjetas de resultados."""
        # Seleccionar todas las tarjetas de resultados
        cards = self.page.query_selector_all('[data-result-focused="true"]')

        for i, card in enumerate(cards):
            if len(self.results) >= limit:
                break

            try:
                # Click en la tarjeta para abrir detalles
                card.click()
                time.sleep(random.uniform(1.5, 2.5))

                # Extraer datos del panel lateral
                data = self._extract_business_details()
                if data and data.get("name"):
                    self.results.append(data)
                    print(f"    [{len(self.results)}] {data.get('name', 'Sin nombre')}")

            except Exception as e:
                print(f"    [!] Error extrayendo tarjeta {i}: {e}")
                continue

    def _extract_business_details(self) -> dict:
        """Extrae los detalles de un negocio del panel lateral."""
        data = {
            "name": None,
            "category": None,
            "address": None,
            "phone": None,
            "website": None,
            "rating": None,
            "reviews_count": None,
            "latitude": None,
            "longitude": None,
            "place_id": None,
            "extracted_at": datetime.now().isoformat(),
        }

        try:
            # Nombre
            try:
                name_elem = self.page.query_selector("h1.DUwDvf")
                if name_elem:
                    data["name"] = name_elem.inner_text().strip()
            except Exception:
                pass

            # Categoría
            try:
                category_elem = self.page.query_selector(
                    "[class*='widget-pane-info'] [class*='title']"
                )
                if category_elem:
                    data["category"] = category_elem.inner_text().strip()
            except Exception:
                pass

            # Buscar en la sección de información
            info_elements = self.page.query_selector_all(
                "[class*='widget-pane-info'] [class*='container']"
            )
            for elem in info_elements:
                try:
                    text = elem.inner_text()
                    if "Dirección" in text or "Address" in text:
                        addr = text.split("Dirección")[-1].split("Teléfono")[0].strip()
                        data["address"] = addr if addr != text else None
                    elif "Teléfono" in text or "Phone" in text:
                        phone = text.split("Teléfono")[-1].split("Sitio")[0].strip()
                        data["phone"] = phone if phone != text else None
                    elif "Sitio web" in text or "Website" in text:
                        web = text.split("Sitio web")[-1].strip()
                        data["website"] = web if web != text else None
                except Exception:
                    continue

            # Rating
            try:
                rating_elem = self.page.query_selector(
                    "[class*='rating'] [class*='score']"
                )
                if rating_elem:
                    rating_text = rating_elem.inner_text()
                    data["rating"] = float(rating_text.replace(",", "."))
            except Exception:
                pass

            # URL actual para extraer coordenadas y place_id
            current_url = self.page.url
            if "@" in current_url:
                try:
                    # Extraer coordenadas de la URL
                    coords_part = current_url.split("@")[1].split("!")[0]
                    lat, lng = coords_part.split(",")
                    data["latitude"] = float(lat)
                    data["longitude"] = float(lng)
                except Exception:
                    pass

            if "place/" in current_url:
                try:
                    data["place_id"] = current_url.split("place/")[1].split("/")[0]
                except Exception:
                    pass

        except Exception as e:
            print(f"    [!] Error extrayendo detalles: {e}")

        return data

    def save_to_csv(self, filename: str = None) -> str:
        """Guarda los resultados en un archivo CSV.

        Args:
            filename: Nombre del archivo. Si es None, genera uno con timestamp.

        Returns:
            Ruta del archivo guardado.
        """
        if not self.results:
            print("[!] No hay resultados para guardar")
            return None

        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"google_maps_results_{timestamp}.csv"

        filepath = Path(filename)
        fieldnames = [
            "name",
            "category",
            "address",
            "phone",
            "website",
            "rating",
            "reviews_count",
            "latitude",
            "longitude",
            "place_id",
            "extracted_at",
        ]

        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(self.results)

        print(f"[+] Guardado en: {filepath}")
        return str(filepath)

    def save_to_json(self, filename: str = None) -> str:
        """Guarda los resultados en un archivo JSON.

        Args:
            filename: Nombre del archivo. Si es None, genera uno con timestamp.

        Returns:
            Ruta del archivo guardado.
        """
        if not self.results:
            print("[!] No hay resultados para guardar")
            return None

        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"google_maps_results_{timestamp}.json"

        filepath = Path(filename)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.results, f, ensure_ascii=False, indent=2)

        print(f"[+] Guardado en: {filepath}")
        return str(filepath)


def main():
    parser = argparse.ArgumentParser(
        description="Google Maps Scraper para Chile",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python google_maps_scraper.py --query "restaurantes" --location "Maipú, Santiago"
  python google_maps_scraper.py --query "cafes" --location "Providencia, Santiago" --limit 100
  python google_maps_scraper.py --query "talleres" --location "Santiago" --format json

Categorías disponibles: restaurantes, cafes, tiendas, peluquerias,
                         talleres, farmacias, supermercados, gimnasios,
                         dentistas, bancos
        """,
    )
    parser.add_argument(
        "--query",
        "-q",
        type=str,
        default="restaurantes",
        help="Tipo de negocio a buscar (default: restaurantes)",
    )
    parser.add_argument(
        "--location",
        "-l",
        type=str,
        default="Santiago, Chile",
        help="Ubicación para la búsqueda (default: Santiago, Chile)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Máximo de resultados a extraer (default: 50)",
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
        help="Nombre del archivo de salida (sin extensión)",
    )
    parser.add_argument(
        "--visible",
        action="store_true",
        help="Muestra el navegador (por defecto es oculto)",
    )

    args = parser.parse_args()

    # Validar categoría
    query = args.query
    if query.lower() in GoogleMapsScraper.CATEGORIES:
        query = GoogleMapsScraper.CATEGORIES[query.lower()]

    print("=" * 60)
    print("  Google Maps Scraper - Chile")
    print("=" * 60)
    print(f"  Búsqueda: {query}")
    print(f"  Ubicación: {args.location}")
    print(f"  Límite: {args.limit}")
    print("=" * 60)

    scraper = GoogleMapsScraper(headless=not args.visible)

    try:
        scraper.start()
        results = scraper.search(
            query=query,
            location=args.location,
            limit=args.limit,
        )

        if results:
            if args.output:
                base_name = args.output
            else:
                base_name = None

            if args.format in ["csv", "both"]:
                ext = ".csv" if base_name and not base_name.endswith(".csv") else ""
                filename = f"{base_name or 'results'}{ext}" if base_name else None
                scraper.save_to_csv(filename)

            if args.format in ["json", "both"]:
                ext = ".json" if base_name and not base_name.endswith(".json") else ""
                filename = f"{base_name or 'results'}{ext}" if base_name else None
                scraper.save_to_json(filename)
        else:
            print("[!] No se encontraron resultados")

    except KeyboardInterrupt:
        print("\n[!] Interrupted by user")
        if results := scraper.results:
            print(f"[+] Guardando {len(results)} resultados antes de salir...")
            scraper.save_to_csv()
    finally:
        scraper.stop()


if __name__ == "__main__":
    main()
