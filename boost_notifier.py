"""
Système de notification des boosts sportifs → Telegram
Bookmakers : Winamax, Betclic, Unibet, ParionsSport
Exécution  : GitHub Actions (cron toutes les 15 min)
"""

import asyncio
import json
import os
import hashlib
import requests
from datetime import datetime
from playwright.async_api import async_playwright

# ─── Configuration ───────────────────────────────────────────────────────────
TELEGRAM_TOKEN   = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
CACHE_FILE       = "boosts_vus.json"

# ─── Emojis par bookmaker ────────────────────────────────────────────────────
BOOKMAKER_EMOJI = {
    "Winamax":     "🟠",
    "Betclic":     "🔵",
    "Unibet":      "🟢",
    "ParionsSport": "🔴",
}

# ─── Telegram ────────────────────────────────────────────────────────────────
def send_telegram(message: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    resp = requests.post(url, json={
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }, timeout=10)
    if not resp.ok:
        print(f"Telegram error: {resp.text}")

# ─── Cache (boosts déjà vus) ──────────────────────────────────────────────────
def load_cache() -> dict:
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_cache(cache: dict):
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)

def boost_uid(bookmaker: str, titre: str) -> str:
    return hashlib.md5(f"{bookmaker}|{titre}".encode()).hexdigest()

# ─── Scrapers ─────────────────────────────────────────────────────────────────
async def scrape_winamax(page) -> list[dict]:
    boosts = []
    try:
        await page.goto("https://www.winamax.fr/paris-sportifs/sports", timeout=30000)
        await page.wait_for_timeout(3000)

        # Winamax affiche les boosts CB FLASH via leur API interne
        # On cherche les éléments avec "boost" ou "CB FLASH" dans le DOM
        elements = await page.query_selector_all(
            "[class*='boost'], [class*='Boost'], [data-testid*='boost']"
        )
        for el in elements:
            texte = (await el.inner_text()).strip()
            if texte and len(texte) > 5:
                boosts.append({
                    "bookmaker": "Winamax",
                    "titre": texte[:300],
                    "url": "https://www.winamax.fr/paris-sportifs/sports",
                    "heure": datetime.now().strftime("%H:%M"),
                })

        # Fallback : chercher le texte "CB FLASH" directement
        if not boosts:
            content = await page.content()
            if "CB FLASH" in content or "cote boostée" in content.lower():
                items = await page.query_selector_all("text=CB FLASH")
                for item in items[:10]:
                    parent = await item.evaluate_handle("el => el.closest('[class*=\"market\"], [class*=\"bet\"], article, li')")
                    if parent:
                        texte = (await parent.inner_text()).strip()
                        if texte:
                            boosts.append({
                                "bookmaker": "Winamax",
                                "titre": texte[:300],
                                "url": "https://www.winamax.fr/paris-sportifs/sports",
                                "heure": datetime.now().strftime("%H:%M"),
                            })
    except Exception as e:
        print(f"[Winamax] Erreur : {e}")
    return boosts


async def scrape_betclic(page) -> list[dict]:
    boosts = []
    try:
        await page.goto("https://www.betclic.fr/paris-sportifs", timeout=30000)
        await page.wait_for_timeout(3000)

        elements = await page.query_selector_all(
            "[class*='boost'], [class*='Boost'], [class*='surboost'], "
            "[class*='cote-boostee'], [data-type*='boost']"
        )
        for el in elements:
            texte = (await el.inner_text()).strip()
            if texte and len(texte) > 5:
                boosts.append({
                    "bookmaker": "Betclic",
                    "titre": texte[:300],
                    "url": "https://www.betclic.fr/paris-sportifs",
                    "heure": datetime.now().strftime("%H:%M"),
                })
    except Exception as e:
        print(f"[Betclic] Erreur : {e}")
    return boosts


async def scrape_unibet(page) -> list[dict]:
    boosts = []
    try:
        await page.goto("https://www.unibet.fr/sport", timeout=30000)
        await page.wait_for_timeout(3000)

        elements = await page.query_selector_all(
            "[class*='boost'], [class*='Boost'], [class*='enhanced'], "
            "[class*='super-price'], [data-role*='boost']"
        )
        for el in elements:
            texte = (await el.inner_text()).strip()
            if texte and len(texte) > 5:
                boosts.append({
                    "bookmaker": "Unibet",
                    "titre": texte[:300],
                    "url": "https://www.unibet.fr/sport",
                    "heure": datetime.now().strftime("%H:%M"),
                })
    except Exception as e:
        print(f"[Unibet] Erreur : {e}")
    return boosts


async def scrape_parionssport(page) -> list[dict]:
    boosts = []
    try:
        await page.goto("https://www.parionssport.fdj.fr/paris-sportifs", timeout=30000)
        await page.wait_for_timeout(3000)

        elements = await page.query_selector_all(
            "[class*='boost'], [class*='Boost'], [class*='cb-live'], "
            "[class*='cb-flash'], [class*='cote-boostee']"
        )
        for el in elements:
            texte = (await el.inner_text()).strip()
            if texte and len(texte) > 5:
                boosts.append({
                    "bookmaker": "ParionsSport",
                    "titre": texte[:300],
                    "url": "https://www.parionssport.fdj.fr/paris-sportifs",
                    "heure": datetime.now().strftime("%H:%M"),
                })
    except Exception as e:
        print(f"[ParionsSport] Erreur : {e}")
    return boosts


# ─── Formatage du message Telegram ───────────────────────────────────────────
def format_message(boost: dict) -> str:
    emoji = BOOKMAKER_EMOJI.get(boost["bookmaker"], "⚡")
    return (
        f"{emoji} <b>NOUVEAU BOOST — {boost['bookmaker']}</b>\n"
        f"🕐 {boost['heure']}\n\n"
        f"📋 {boost['titre']}\n\n"
        f"🔗 <a href=\"{boost['url']}\">Voir l'offre</a>"
    )


# ─── Orchestrateur principal ─────────────────────────────────────────────────
async def main():
    cache = load_cache()
    nouveaux_boosts = []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
        )
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/121.0.0.0 Safari/537.36"
            ),
            locale="fr-FR",
        )
        page = await context.new_page()

        scrapers = [
            scrape_winamax,
            scrape_betclic,
            scrape_unibet,
            scrape_parionssport,
        ]

        for scraper in scrapers:
            boosts = await scraper(page)
            print(f"[{scraper.__name__}] {len(boosts)} boost(s) trouvé(s)")

            for boost in boosts:
                uid = boost_uid(boost["bookmaker"], boost["titre"])
                if uid not in cache:
                    nouveaux_boosts.append(boost)
                    cache[uid] = {
                        "vu_le": datetime.now().isoformat(),
                        "bookmaker": boost["bookmaker"],
                        "titre": boost["titre"][:100],
                    }

        await browser.close()

    # Envoi des notifications
    if nouveaux_boosts:
        print(f"\n🔔 {len(nouveaux_boosts)} nouveau(x) boost(s) détecté(s) !")
        for boost in nouveaux_boosts:
            msg = format_message(boost)
            send_telegram(msg)
            print(f"  → Notifié : {boost['bookmaker']} | {boost['titre'][:60]}...")
        save_cache(cache)
    else:
        print("✅ Aucun nouveau boost détecté.")

    # Nettoyage du cache (garder seulement les 7 derniers jours)
    from datetime import timedelta
    cutoff = (datetime.now() - timedelta(days=7)).isoformat()
    cache = {k: v for k, v in cache.items() if v.get("vu_le", "") > cutoff}
    save_cache(cache)


if __name__ == "__main__":
    asyncio.run(main())
