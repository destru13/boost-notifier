import asyncio, json, os, hashlib, requests, traceback
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

async def accept_cookies(page, bk):
    print("[" + bk + "] Tentative acceptation cookies...")
    selectors = [
        "button:has-text('Tout accepter')",
        "button:has-text('Accepter tout')",
        "button:has-text('Accepter les cookies')",
        "button:has-text('Accepter')",
        "#onetrust-accept-btn-handler",
        ".btn-accept",
    ]
    for sel in selectors:
        try:
            btn = page.locator(sel).first
            if await btn.is_visible(timeout=2000):
                await btn.click()
                await page.wait_for_timeout(2000)
                print("[" + bk + "] Cookies acceptes via: " + sel)
                return True
        except Exception:
            continue
    print("[" + bk + "] Aucun bouton cookies trouve")
    return False

async def scrape_betclic(page):
    boosts = []
    bk = "Betclic"
    try:
        print("[" + bk + "] Navigation...")
        await page.goto("https://www.betclic.fr/", timeout=30000)
        print("[" + bk + "] Titre: " + await page.title())
        await page.wait_for_timeout(3000)
        await accept_cookies(page, bk)
        await page.wait_for_timeout(4000)
        await page.evaluate("window.scrollTo(0, 400)")
        await page.wait_for_timeout(2000)
        print("[" + bk + "] URL: " + page.url)
        count = await page.evaluate("document.querySelectorAll('.boostedCard').length")
        print("[" + bk + "] .boostedCard count: " + str(count))
        body = await page.evaluate("document.body.innerText.substring(0,200)")
        print("[" + bk + "] body: " + body.replace("\n"," ")[:150])
        if count > 0:
            data = await page.evaluate(
                "Array.from(document.querySelectorAll('.boostedCard')).map(c => ({" +
                "  title: (c.querySelector('.boostedCard_title')?.innerText || '')," +
                "  sub:   (c.querySelector('.boostedCard_subtitle')?.innerText || '')," +
                "  desc:  (c.querySelector('.boostedCard_description')?.innerText || '')," +
                "  href:  c.href || ''" +
                "}))"
            )
            print("[" + bk + "] data: " + str(data)[:200])
            for item in data:
                titre = (item.get("title","") + " " + item.get("sub","") + " -- " + item.get("desc","")).strip()
                if titre and len(titre) > 5:
                    boosts.append({"bookmaker": bk, "titre": titre[:300],
                        "url": item.get("href") or "https://www.betclic.fr/",
                        "heure": datetime.now().strftime("%H:%M")})
    except Exception as e:
        print("[" + bk + "] ERREUR: " + str(e))
        print(traceback.format_exc()[:400])
    print("[scrape_betclic] " + str(len(boosts)) + " boost(s)")
    return boosts

async def scrape_unibet(page):
    boosts = []
    bk = "Unibet"
    try:
        print("[" + bk + "] Navigation...")
        await page.goto("https://www.unibet.fr/sport", timeout=30000)
        print("[" + bk + "] Titre: " + await page.title())
        await page.wait_for_timeout(3000)
        await accept_cookies(page, bk)
        await page.wait_for_timeout(4000)
        await page.evaluate("window.scrollTo(0, 400)")
        await page.wait_for_timeout(2000)
        print("[" + bk + "] URL: " + page.url)
        count = await page.evaluate("document.querySelectorAll('.scb-card').length")
        print("[" + bk + "] .scb-card count: " + str(count))
        scb = await page.evaluate("document.querySelectorAll('.scb').length")
        print("[" + bk + "] .scb section count: " + str(scb))
        body = await page.evaluate("document.body.innerText.substring(0,200)")
        print("[" + bk + "] body: " + body.replace("\n"," ")[:150])
        if count > 0:
            data = await page.evaluate(
                "Array.from(document.querySelectorAll('.scb-card')).map(c => ({" +
                "  match: (c.querySelector('.scb-card-title')?.innerText || '').trim()," +
                "  sel:   (c.querySelector('.scb-card-selection-title')?.innerText || '').trim()," +
                "  comp:  (c.querySelector('.scb-card-info')?.innerText || '').trim()" +
                "}))"
            )
            for item in data:
                match_t = item.get("match","")
                sel_t   = item.get("sel","")
                comp_t  = item.get("comp","").replace("\n"," | ")
                if match_t:
                    titre = (comp_t + " -- " + match_t + " -- " + sel_t) if comp_t else (match_t + " -- " + sel_t)
                    boosts.append({"bookmaker": bk, "titre": titre[:300],
                        "url": "https://www.unibet.fr/sport",
                        "heure": datetime.now().strftime("%H:%M")})
    except Exception as e:
        print("[" + bk + "] ERREUR: " + str(e))
        print(traceback.format_exc()[:400])
    print("[scrape_unibet] " + str(len(boosts)) + " boost(s)")
    return boosts

async def scrape_parionssport(page):
    boosts = []
    bk = "ParionsSport"
    try:
        print("[" + bk + "] Navigation...")
        await page.goto("https://www.enligne.parionssport.fdj.fr/", timeout=30000)
        print("[" + bk + "] Titre: " + await page.title())
        await page.wait_for_timeout(3000)
        await accept_cookies(page, bk)
        await page.wait_for_timeout(4000)
        await page.evaluate("window.scrollTo(0, 400)")
        await page.wait_for_timeout(2000)
        print("[" + bk + "] URL: " + page.url)
        count = await page.evaluate("document.querySelectorAll('.psel-boosted-bet').length")
        print("[" + bk + "] .psel-boosted-bet count: " + str(count))
        count2 = await page.evaluate("document.querySelectorAll('[class*=boosted]').length")
        print("[" + bk + "] [class*=boosted] count: " + str(count2))
        body = await page.evaluate("document.body.innerText.substring(0,200)")
        print("[" + bk + "] body: " + body.replace("\n"," ")[:150])
        if count > 0:
            data = await page.evaluate(
                "Array.from(document.querySelectorAll('.psel-boosted-bet')).map(e => (e.innerText||''). trim())"
            )
            for t in data:
                if t and len(t) > 5:
                    boosts.append({"bookmaker": bk, "titre": t[:300],
                        "url": "https://www.enligne.parionssport.fdj.fr/",
                        "heure": datetime.now().strftime("%H:%M")})
    except Exception as e:
        print("[" + bk + "] ERREUR: " + str(e))
        print(traceback.format_exc()[:400])
    print("[scrape_parionssport] " + str(len(boosts)) + " boost(s)")
    return boosts

async def scrape_winamax(page):
    boosts = []
    bk = "Winamax"
    try:
        print("[" + bk + "] Navigation...")
        await page.goto("https://www.winamax.fr/paris-sportifs/sports", timeout=30000)
        print("[" + bk + "] Titre: " + await page.title())
        await page.wait_for_timeout(3000)
        await accept_cookies(page, bk)
        await page.wait_for_timeout(5000)
        print("[" + bk + "] URL: " + page.url)
        body = await page.evaluate("document.body.innerText.substring(0,200)")
        print("[" + bk + "] body: " + body.replace("\n"," ")[:150])
        elements = await page.query_selector_all(
            "[class*='boosted'],[class*='boost'],[class*='cbflash'],[class*='cb-flash']"
        )
        print("[" + bk + "] elements boost: " + str(len(elements)))
        for el in elements:
            t = (await el.inner_text()).strip()
            cls = await el.get_attribute("class") or ""
            print("[" + bk + "] el class=" + cls[:50] + " text=" + t[:60])
            if t and len(t) > 5:
                boosts.append({"bookmaker": bk, "titre": t[:300],
                    "url": "https://www.winamax.fr/paris-sportifs/sports",
                    "heure": datetime.now().strftime("%H:%M")})
    except Exception as e:
        print("[" + bk + "] ERREUR: " + str(e))
        print(traceback.format_exc()[:400])
    print("[scrape_winamax] " + str(len(boosts)) + " boost(s)")
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
    print("=== DEMARRAGE ===")
    cache = load_cache()
    print("Cache: " + str(len(cache)) + " entrees")
    nouveaux = []
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=["--no-sandbox","--disable-setuid-sandbox","--disable-dev-shm-usage",
                  "--disable-blink-features=AutomationControlled"]
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            locale="fr-FR",
            viewport={"width": 1280, "height": 800}
        )
        await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        page = await context.new_page()
        for scraper in [scrape_betclic, scrape_unibet, scrape_parionssport, scrape_winamax]:
            print("--- " + scraper.__name__ + " ---")
            boosts = await scraper(page)
            for boost in boosts:
                uid = boost_uid(boost["bookmaker"], boost["titre"])
                if uid not in cache:
                    nouveaux.append(boost)
                    cache[uid] = {"vu_le": datetime.now().isoformat(),
                        "bookmaker": boost["bookmaker"], "titre": boost["titre"][:100]}
        await browser.close()
    if nouveaux:
        print("NOUVEAUX: " + str(len(nouveaux)))
        for boost in nouveaux:
            print("  -> " + boost["bookmaker"] + " | " + boost["titre"][:60])
            send_telegram(format_message(boost))
    else:
        print("Aucun nouveau boost.")
    cutoff = (datetime.now() - timedelta(days=7)).isoformat()
    cache = {k: v for k, v in cache.items() if v.get("vu_le","") > cutoff}
    save_cache(cache)
    print("=== FIN ===")

if __name__ == "__main__":
    asyncio.run(main())
