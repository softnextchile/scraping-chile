"""
Instagram Scraper para Chile
============================
Extrae datos de cuentas de negocios desde Instagram usando Playwright.
Ejecutar LOCALMENTE (no funciona en servidores remotos por geolocalización).

Uso:
    python instagram_scraper.py --hashtag "comida" --location "Maipú"
    python instagram_scraper.py --hashtag "cafe" --location "Santiago" --limit 100
"""

import argparse
import csv
import json
import time
import random
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright


class InstagramScraper:
    """Scraper de Instagram usando Playwright."""

    BASE_URL = "https://www.instagram.com"

    def __init__(self, headless: bool = True, slow_mo: int = 100):
        """Inicializa el scraper.

        Args:
            headless: Si True, el navegador no muestra ventana (recomendado).
            slow_mo: Milisegundos de delay entre acciones (ayuda a evitar detección).
        """
        self.playwright = None
        self.browser = None
        self.context = None
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
        self.context = self.browser.new_context(
            viewport={"width": 1280, "height": 720},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            locale="es-ES",
            timezone_id="Europe/Madrid",
            permissions=["geolocation"],
        )
        self.page = self.context.new_page()
        # Bloquear recursos pesados
        self.page.route(
            "**/*.{png,jpg,jpeg,gif,svg,ico,woff,woff2}",
            lambda route: route.abort(),
        )

    def stop(self):
        """Cierra el navegador."""
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()

    def login(self, username: str, password: str) -> bool:
        """Inicia sesión en Instagram.

        Args:
            username: Nombre de usuario de Instagram
            password: Contraseña

        Returns:
            True si el login fue exitoso
        """
        print(f"[+] Iniciando sesión como @{username}")
        self.page.goto(f"{self.BASE_URL}/accounts/login/")

        # Esperar a que cargue el formulario
        time.sleep(random.uniform(2, 4))

        # Ingresar username
        try:
            self.page.fill('input[name="username"]', username, timeout=10000)
            time.sleep(random.uniform(0.5, 1))
            self.page.fill('input[name="password"]', password)
            time.sleep(random.uniform(0.5, 1))
            self.page.click('button[type="submit"]')
            time.sleep(random.uniform(3, 5))

            # Guardar cookies para futuras sesiones
            self.context.storage_state(path="instagram_state.json")
            print("[+] Login exitoso")
            return True
        except Exception as e:
            print(f"[!] Error en login: {e}")
            return False

    def load_session(self, state_file: str = "instagram_state.json"):
        """Carga una sesión guardada previamente.

        Args:
            state_file: Ruta al archivo de estado de cookies
        """
        try:
            self.context = self.browser.new_context(
                viewport={"width": 1280, "height": 720},
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                locale="es-ES",
                storage_state=state_file,
            )
            self.page = self.context.new_page()
            print(f"[+] Sesión cargada desde {state_file}")
            return True
        except Exception as e:
            print(f"[!] Error cargando sesión: {e}")
            return False

    def search_by_hashtag(self, hashtag: str, limit: int = 50) -> list:
        """Busca posts por hashtag.

        Args:
            hashtag: Hashtag a buscar (sin #)
            limit: Máximo de resultados a extraer

        Returns:
            Lista de diccionarios con datos de cada post/cuenta
        """
        self.results = []
        url = f"{self.BASE_URL}/explore/tags/{hashtag}/"

        print(f"[+] Abriendo hashtag: #{hashtag}")
        self.page.goto(url)
        time.sleep(random.uniform(3, 5))

        # Scroll para cargar más posts
        print(f"[+] Extrayendo posts...")
        self._scroll_and_extract(limit)

        print(f"[+] Extraídos {len(self.results)} resultados")
        return self.results

    def search_by_location(self, location_slug: str, limit: int = 50) -> list:
        """Busca posts por ubicación.

        Args:
            location_slug: Slug de ubicación de Instagram (ej: "maipu-chile")
            limit: Máximo de resultados a extraer

        Returns:
            Lista de diccionarios con datos
        """
        self.results = []
        url = f"{self.BASE_URL}/explore/locations/{location_slug}/"

        print(f"[+] Abriendo ubicación: {location_slug}")
        self.page.goto(url)
        time.sleep(random.uniform(3, 5))

        self._scroll_and_extract(limit)

        print(f"[+] Extraídos {len(self.results)} resultados")
        return self.results

    def _scroll_and_extract(self, limit: int):
        """Scroll y extracción de posts."""
        scroll_count = 0
        max_scrolls = (limit // 12) + 10  # Aproximadamente 12 posts por scroll

        while scroll_count < max_scrolls and len(self.results) < limit:
            # Extraer posts visibles
            self._extract_visible_posts(limit)

            # Scroll hacia abajo
            self.page.evaluate('window.scrollBy(0, 800)')
            time.sleep(random.uniform(1, 2))

            scroll_count += 1

    def _extract_visible_posts(self, limit: int):
        """Extrae los posts visibles en pantalla."""
        # Los posts en explore son artículos con enlaces
        posts = self.page.query_selector_all("article a")

        for post in posts:
            if len(self.results) >= limit:
                break

            try:
                href = post.get_attribute("href")
                if not href or "/p/" not in href:
                    continue

                # Obtener datos del post
                data = self._extract_post_data(href)
                if data:
                    self.results.append(data)
                    print(f"    [{len(self.results)}] @{data.get('username', 'unknown')}")

            except Exception as e:
                continue

    def _extract_post_data(self, post_url: str) -> dict:
        """Extrae datos de un post individual."""
        data = {
            "username": None,
            "full_name": None,
            "post_url": None,
            "likes": None,
            "comments_count": None,
            "caption": None,
            "timestamp": None,
            "location": None,
            "extracted_at": datetime.now().isoformat(),
        }

        try:
            full_url = post_url if post_url.startswith("http") else f"{self.BASE_URL}{post_url}"
            data["post_url"] = full_url

            # Abrir el post en una nueva página
            self.page.goto(full_url)
            time.sleep(random.uniform(2, 3))

            # Username
            try:
                username_elem = self.page.query_selector("header a.x1i10hfl")
                if username_elem:
                    href = username_elem.get_attribute("href")
                    if href:
                        data["username"] = href.strip("/")
            except Exception:
                pass

            # Full name
            try:
                name_elem = self.page.query_selector("header span.x1lliihq")
                if name_elem:
                    data["full_name"] = name_elem.inner_text().strip()
            except Exception:
                pass

            # Likes
            try:
                likes_elem = self.page.query_selector(
                    "section span a span, section span"
                )
                if likes_elem:
                    likes_text = likes_elem.inner_text()
                    if "me gusta" in likes_text.lower() or "like" in likes_text.lower():
                        data["likes"] = likes_text
            except Exception:
                pass

            # Caption
            try:
                caption_elem = self.page.query_selector("div._a9zs span")
                if caption_elem:
                    data["caption"] = caption_elem.inner_text()[:500]  # Limitar longitud
            except Exception:
                pass

            # Location
            try:
                location_elem = self.page.query_selector(
                    "a.oajrlxb2[href*='/explore/locations/']"
                )
                if location_elem:
                    data["location"] = location_elem.inner_text().strip()
            except Exception:
                pass

        except Exception as e:
            pass

        return data

    def search_businesses_by_location(self, location_query: str, limit: int = 50) -> list:
        """Busca cuentas de negocios en una ubicación específica.

        Args:
            location_query: Query de ubicación (ej: "Maipú, Santiago, Chile")
            limit: Máximo de cuentas a extraer

        Returns:
            Lista de cuentas de negocios encontradas
        """
        self.results = []

        # Primero buscar la ubicación
        print(f"[+] Buscando ubicación: {location_query}")
        self.page.goto(f"{self.BASE_URL}/explore/search/")
        time.sleep(random.uniform(2, 3))

        # Buscar por lugar
        try:
            search_box = self.page.query_selector('input[placeholder*="Buscar"]')
            if search_box:
                search_box.fill(location_query)
                time.sleep(random.uniform(2, 3))

                # Click en resultado de Lugar
                place_option = self.page.query_selector(
                    'a[href*="/explore/locations/"]'
                )
                if place_option:
                    place_option.click()
                    time.sleep(random.uniform(2, 3))

                    # Extraer posts de la ubicación
                    self._scroll_and_extract(limit)

                    # De los posts, extraer usernames únicos
                    businesses = self._extract_businesses_from_posts()
                    self.results = businesses
        except Exception as e:
            print(f"[!] Error buscando ubicación: {e}")

        print(f"[+] Encontrados {len(self.results)} negocios")
        return self.results

    def _extract_businesses_from_posts(self) -> list:
        """Extrae cuentas de negocio únicas de los posts."""
        seen_usernames = set()
        businesses = []

        for result in self.results:
            username = result.get("username")
            if username and username not in seen_usernames:
                seen_usernames.add(username)
                businesses.append({
                    "username": username,
                    "full_name": result.get("full_name"),
                    "location": result.get("location"),
                    "extracted_at": datetime.now().isoformat(),
                })

        return businesses

    def save_to_csv(self, filename: str = None) -> str:
        """Guarda los resultados en un archivo CSV."""
        if not self.results:
            print("[!] No hay resultados para guardar")
            return None

        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"instagram_results_{timestamp}.csv"

        filepath = Path(filename)
        fieldnames = list(self.results[0].keys())

        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(self.results)

        print(f"[+] Guardado en: {filepath}")
        return str(filepath)

    def save_to_json(self, filename: str = None) -> str:
        """Guarda los resultados en un archivo JSON."""
        if not self.results:
            print("[!] No hay resultados para guardar")
            return None

        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"instagram_results_{timestamp}.json"

        filepath = Path(filename)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.results, f, ensure_ascii=False, indent=2)

        print(f"[+] Guardado en: {filepath}")
        return str(filepath)


def main():
    parser = argparse.ArgumentParser(
        description="Instagram Scraper para Chile",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  # Buscar por hashtag
  python instagram_scraper.py --hashtag "comidachilena"

  # Buscar por ubicación
  python instagram_scraper.py --location "maipu-chile"

  # Con sesión guardada (primero hacer login)
  python instagram_scraper.py --hashtag "cafe" --session instagram_state.json

  # Login y guardar sesión
  python instagram_scraper.py --login --username tu_usuario --password tu_password

Notas:
  - Instagram puede bloquear cuentas si se hace demasiado scraping
  - Se recomienda usar --slow-modo para evitar detección
  - Guardar la sesión permite reutilizar cookies
        """,
    )
    parser.add_argument(
        "--hashtag",
        type=str,
        help="Hashtag a buscar (sin #)",
    )
    parser.add_argument(
        "--location",
        type=str,
        help="Slug de ubicación (ej: maipu-chile)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Máximo de resultados (default: 50)",
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
        help="Nombre del archivo de salida",
    )
    parser.add_argument(
        "--login",
        action="store_true",
        help="Iniciar sesión antes de hacer scraping",
    )
    parser.add_argument(
        "--username",
        type=str,
        help="Usuario de Instagram para login",
    )
    parser.add_argument(
        "--password",
        type=str,
        help="Contraseña de Instagram para login",
    )
    parser.add_argument(
        "--session",
        type=str,
        default="instagram_state.json",
        help="Archivo de sesión guardada (default: instagram_state.json)",
    )
    parser.add_argument(
        "--visible",
        action="store_true",
        help="Muestra el navegador",
    )
    parser.add_argument(
        "--slow-mo",
        type=int,
        default=100,
        help="Delay entre acciones en ms (default: 100)",
    )

    args = parser.parse_args()

    if not any([args.hashtag, args.location, args.login]):
        parser.print_help()
        print("\n[!] Debe especificar --hashtag, --location, o --login")
        return

    print("=" * 60)
    print("  Instagram Scraper - Chile")
    print("=" * 60)

    scraper = InstagramScraper(
        headless=not args.visible,
        slow_mo=args.slow_mo,
    )

    try:
        scraper.start()

        # Login si se requiere
        if args.login:
            if not args.username or not args.password:
                print("[!] Se requiere --username y --password para login")
                return
            scraper.login(args.username, args.password)
        elif Path(args.session).exists():
            scraper.load_session(args.session)

        results = []

        # Buscar según el modo
        if args.hashtag:
            results = scraper.search_by_hashtag(args.hashtag, limit=args.limit)
        elif args.location:
            results = scraper.search_by_location(args.location, limit=args.limit)

        # Guardar resultados
        if results:
            if args.output:
                base = args.output
            else:
                base = None

            if args.format in ["csv", "both"]:
                ext = ".csv" if base and not base.endswith(".csv") else ""
                filename = f"{base or 'results'}{ext}" if base else None
                scraper.save_to_csv(filename)

            if args.format in ["json", "both"]:
                ext = ".json" if base and not base.endswith(".json") else ""
                filename = f"{base or 'results'}{ext}" if base else None
                scraper.save_to_json(filename)
        else:
            print("[!] No se encontraron resultados")

    except KeyboardInterrupt:
        print("\n[!] Interrupted by user")
        if results := scraper.results:
            print(f"[+] Guardando {len(results)} resultados...")
            scraper.save_to_csv()
    finally:
        scraper.stop()


if __name__ == "__main__":
    main()
