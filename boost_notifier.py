import asyncio, json, os, hashlib, requests
from datetime import datetime, timedelta
from playwright.async_api import async_playwright

TELEGRAM_TOKEN   = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
CACHE_FILE       = "boosts_vus.json"

def send_telegram(message):
    url = "https://api.telegram.org/bot" + TELEGRAM_TOKEN + "/sendMessage"
    resp = requests.post(url, json={
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }, timeout=10)
    if not resp.ok:
        print("Telegram error: " + resp.text)

def load_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_cache(cache):
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)

def boost_uid(bookmaker, titre):
    return hashlib.md5((bookmaker + "|" + titre).encode()).hexdigest()

async def scrape_winamax(page):
    boosts = []
    try:
        await page.goto("https://www.winamax.fr/paris-sportifs/sports", timeout=30000)
        await page.wait_for_load_state("networkidle", timeout=15000)
        await page.wait_for_timeout(4000)
        elements = await page.query_selector_all(
            "[class*='boosted'],[class*='boost'],[class*='cbflash'],[class*='cb-flash']"
        )
        for el in elements:
            t = (await el.inner_text()).strip()
            if t and len(t) > 5:
                boosts.append({
                    "bookmaker": "Winamax",
                    "titre": t[:300],
                    "url": "https://www.winamax.fr/paris-sportifs/sports",
                    "heure": datetime.now().strftime("%H:%M")
                })
    except Exception as e:
        print("[Winamax] Erreur : " + str(e))
    print("[scrape_winamax] " + str(len(boosts)) + " boost(s) trouve(s)")
    return boosts

async def scrape_betclic(page):
    boosts = []
    try:
        await page.goto("https://www.betclic.fr/", timeout=30000)
        await page.wait_for_load_state("networkidle", timeout=15000)
        await page.wait_for_timeout(4000)
        cards = await page.query_selector_all(".boostedCard")
        for card in cards:
            title_el = await card.query_selector(".boostedCard_title")
            sub_el   = await card.query_selector(".boostedCard_subtitle")
            desc_el  = await card.query_selector(".boostedCard_description")
            title_t  = (await title_el.inner_text()).strip() if title_el else ""
            sub_t    = (await sub_el.inner_text()).strip()   if sub_el   else ""
            desc_t   = (await desc_el.inner_text()).strip()  if desc_el  else ""
            if desc_t or title_t:
                titre = title_t + " " + sub_t + " -- " + desc_t
                href  = await card.get_attribute("href") or "https://www.betclic.fr/"
                boosts.append({
                    "bookmaker": "Betclic",
                    "titre": titre.strip()[:300],
                    "url": href,
                    "heure": datetime.now().strftime("%H:%M")
                })
    except Exception as e:
        print("[Betclic] Erreur : " + str(e))
    print("[scrape_betclic] " + str(len(boosts)) + " boost(s) trouve(s)")
    return boosts

async def scrape_unibet(page):
    boosts = []
    try:
        await page.goto("https://www.unibet.fr/sport", timeout=30000)
        await page.wait_for_load_state("networkidle", timeout=15000)
        await page.wait_for_timeout(5000)
        cards = await page.query_selector_all(".scb-card")
        for card in cards:
            match_el = await card.query_selector(".scb-card-title")
            sel_el   = await card.query_selector(".scb-card-selection-title")
            comp_el  = await card.query_selector(".scb-card-info")
            match_t  = (await match_el.inner_text()).strip() if match_el else ""
            sel_t    = (await sel_el.inner_text()).strip()   if sel_el   else ""
            comp_t   = (await comp_el.inner_text()).strip().replace("\n", " | ") if comp_el else ""
            if match_t:
                titre = (comp_t + " -- " + match_t + " -- " + sel_t) if comp_t else (match_t + " -- " + sel_t)
                boosts.append({
                    "bookmaker": "Unibet",
                    "titre": titre[:300],
                    "url": "https://www.unibet.fr/sport",
                    "heure": datetime.now().strftime("%H:%M")
                })
    except Exception as e:
        print("[Unibet] Erreur : " + str(e))
    print("[scrape_unibet] " + str(len(boosts)) + " boost(s) trouve(s)")
    return boosts

async def scrape_parionssport(page):
    boosts = []
    try:
        await page.goto("https://www.enligne.parionssport.fdj.fr/", timeout=30000)
        await page.wait_for_load_state("networkidle", timeout=15000)
        await page.wait_for_timeout(5000)
        elements = await page.query_selector_all(".psel-boosted-bet")
        for el in elements:
            t = (await el.inner_text()).strip()
            if t and len(t) > 5:
                boosts.append({
                    "bookmaker": "ParionsSport",
                    "titre": t[:300],
                    "url": "https://www.enligne.parionssport.fdj.fr/",
                    "heure": datetime.now().strftime("%H:%M")
                })
    except Exception as e:
        print("[ParionsSport] Erreur : " + str(e))
    print("[scrape_parionssport] " + str(len(boosts)) + " boost(s) trouve(s)")
    return boosts

def format_message(boost):
    emojis = {"Winamax": "O", "Betclic": "B", "Unibet": "U", "ParionsSport": "P"}
    emoji = emojis.get(boost["bookmaker"], "X")
    lines = [
        emoji + " <b>NOUVEAU BOOST -- " + boost["bookmaker"] + "</b>",
        "Heure : " + boost["heure"],
        "",
        boost["titre"],
        "",
        '<a href="' + boost["url"] + '">Voir offre</a>'
    ]
    return "\n".join(lines)

async def main():
    cache = load_cache()
    nouveaux = []
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage",
                  "--disable-blink-features=AutomationControlled"]
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            locale="fr-FR",
            viewport={"width": 1280, "height": 800}
        )
        await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        page = await context.new_page()
        for scraper in [scrape_winamax, scrape_betclic, scrape_unibet, scrape_parionssport]:
            boosts = await scraper(page)
            for boost in boosts:
                uid = boost_uid(boost["bookmaker"], boost["titre"])
                if uid not in cache:
                    nouveaux.append(boost)
                    cache[uid] = {
                        "vu_le": datetime.now().isoformat(),
                        "bookmaker": boost["bookmaker"],
                        "titre": boost["titre"][:100]
                    }
        await browser.close()
    if nouveaux:
        print("NOUVEAUX BOOSTS : " + str(len(nouveaux)))
        for boost in nouveaux:
            send_telegram(format_message(boost))
            print("  -> " + boost["bookmaker"] + " | " + boost["titre"][:60])
    else:
        print("Aucun nouveau boost detecte.")
    cutoff = (datetime.now() - timedelta(days=7)).isoformat()
    cache = {k: v for k, v in cache.items() if v.get("vu_le", "") > cutoff}
    save_cache(cache)

if __name__ == "__main__":
    asyncio.run(main())
