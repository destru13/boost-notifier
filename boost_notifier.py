import json, os, hashlib, requests, traceback
from datetime import datetime, timedelta
from bs4 import BeautifulSoup

TELEGRAM_TOKEN   = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
CACHE_FILE       = "boosts_vus.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Accept-Language": "fr-FR,fr;q=0.9",
    "Accept": "application/json, text/html, */*",
    "Referer": "https://www.google.fr/",
}

def send_telegram(message):
    url = "https://api.telegram.org/bot" + TELEGRAM_TOKEN + "/sendMessage"
    resp = requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": message,
        "parse_mode": "HTML", "disable_web_page_preview": True}, timeout=10)
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

# ---- UNIBET via API Kambi (non geobloquee) ----
def scrape_unibet():
    boosts = []
    bk = "Unibet"
    try:
        url = "https://eu-offering-api.kambicdn.com/offering/v2018/ubfr/listView/all/all/all/all/boosted.json"
        params = {"lang": "fr_FR", "market": "FR", "client_id": "2",
                  "channel_id": "1", "useCombined": "true", "numrows": "50"}
        print("[" + bk + "] Appel API Kambi...")
        resp = requests.get(url, params=params, headers=HEADERS, timeout=15)
        print("[" + bk + "] Status: " + str(resp.status_code))
        if resp.status_code == 200:
            data = resp.json()
            events = data.get("events", [])
            print("[" + bk + "] Events: " + str(len(events)))
            for event in events:
                name = event.get("event", {}).get("name", "")
                for offer in event.get("betOffers", []):
                    tags = offer.get("tags", [])
                    is_boosted = offer.get("boosted", False) or "PRICE_BOOST" in tags
                    if is_boosted:
                        for outcome in offer.get("outcomes", []):
                            label = outcome.get("label", "")
                            odds = outcome.get("odds", 0) / 1000
                            prev = outcome.get("previousOdds", 0) / 1000
                            titre = name + " -- " + label
                            if prev > 0:
                                titre += " (" + str(prev) + " -> " + str(odds) + ")"
                            boosts.append({"bookmaker": bk, "titre": titre[:300],
                                "url": "https://www.unibet.fr/sport",
                                "heure": datetime.now().strftime("%H:%M")})
        else:
            print("[" + bk + "] Reponse: " + resp.text[:200])
    except Exception as e:
        print("[" + bk + "] ERREUR: " + str(e))
        print(traceback.format_exc()[:300])
    print("[scrape_unibet] " + str(len(boosts)) + " boost(s)")
    return boosts

# ---- BETCLIC via requests + BeautifulSoup ----
def scrape_betclic():
    boosts = []
    bk = "Betclic"
    try:
        # Essai API CDN BegMedia
        api_url = "https://offer.cdn.begmedia.com/api/pub/v4/homesports?application=2&countrycode=FR&language=0&limit=20"
        print("[" + bk + "] Essai API CDN...")
        r = requests.get(api_url, headers=HEADERS, timeout=10)
        print("[" + bk + "] CDN status: " + str(r.status_code))
        if r.status_code == 200 and "json" in r.headers.get("content-type",""):
            data = r.json()
            print("[" + bk + "] CDN data type: " + str(type(data)) + " keys: " + str(list(data.keys()) if isinstance(data,dict) else "list:" + str(len(data)))[:80])
        # Essai page principale avec session
        print("[" + bk + "] Essai page HTML...")
        sess = requests.Session()
        sess.headers.update(HEADERS)
        r2 = sess.get("https://www.betclic.fr/", timeout=15)
        print("[" + bk + "] Page status: " + str(r2.status_code))
        print("[" + bk + "] Body debut: " + r2.text[:150].replace("
"," "))
        if r2.status_code == 200:
            soup = BeautifulSoup(r2.text, "html.parser")
            cards = soup.find_all(class_="boostedCard")
            print("[" + bk + "] boostedCard count: " + str(len(cards)))
            for card in cards:
                t_el = card.find(class_="boostedCard_title")
                s_el = card.find(class_="boostedCard_subtitle")
                d_el = card.find(class_="boostedCard_description")
                t = ((t_el.text if t_el else "") + " " + (s_el.text if s_el else "") + " -- " + (d_el.text if d_el else "")).strip()
                href = card.get("href","https://www.betclic.fr/")
                if t and len(t) > 5:
                    boosts.append({"bookmaker": bk, "titre": t[:300], "url": href,
                        "heure": datetime.now().strftime("%H:%M")})
    except Exception as e:
        print("[" + bk + "] ERREUR: " + str(e))
        print(traceback.format_exc()[:300])
    print("[scrape_betclic] " + str(len(boosts)) + " boost(s)")
    return boosts

# ---- PARIONSSPORT via requests ----
def scrape_parionssport():
    boosts = []
    bk = "ParionsSport"
    try:
        # Essai API JSON publique FDJ
        apis = [
            "https://www.enligne.parionssport.fdj.fr/api/psel/market/boosted-bet",
            "https://api.parionssport.fdj.fr/psel/market/boosted",
        ]
        for api_url in apis:
            print("[" + bk + "] Essai API: " + api_url)
            try:
                r = requests.get(api_url, headers=HEADERS, timeout=10)
                print("[" + bk + "] Status: " + str(r.status_code) + " CT: " + r.headers.get("content-type","")[:40])
                if r.status_code == 200:
                    if "json" in r.headers.get("content-type",""):
                        data = r.json()
                        print("[" + bk + "] JSON: " + str(data)[:200])
                    else:
                        print("[" + bk + "] HTML: " + r.text[:150].replace("
"," "))
            except Exception as e2:
                print("[" + bk + "] erreur: " + str(e2)[:80])
        # Essai page HTML
        print("[" + bk + "] Essai page HTML...")
        r3 = requests.get("https://www.enligne.parionssport.fdj.fr/paris-sportifs/cotes-boostees",
                          headers=HEADERS, timeout=15)
        print("[" + bk + "] Page status: " + str(r3.status_code))
        if r3.status_code == 200:
            soup = BeautifulSoup(r3.text, "html.parser")
            els = soup.find_all(attrs={"class": lambda c: c and "boosted" in " ".join(c).lower()})
            print("[" + bk + "] boosted elements: " + str(len(els)))
            for el in els[:3]:
                print("[" + bk + "] el: " + el.get_text()[:100])
    except Exception as e:
        print("[" + bk + "] ERREUR: " + str(e))
        print(traceback.format_exc()[:300])
    print("[scrape_parionssport] " + str(len(boosts)) + " boost(s)")
    return boosts

# ---- WINAMAX via API interne ----
def scrape_winamax():
    boosts = []
    bk = "Winamax"
    try:
        # Chercher les CB Flash via API Winamax
        apis = [
            "https://www.winamax.fr/apiv1/sports/1",
            "https://www.winamax.fr/paris-sportifs/sports/1/7",
        ]
        for api_url in apis:
            print("[" + bk + "] Essai: " + api_url)
            try:
                r = requests.get(api_url, headers=HEADERS, timeout=10)
                print("[" + bk + "] Status: " + str(r.status_code) + " CT: " + r.headers.get("content-type","")[:40])
                if r.status_code == 200:
                    ct = r.headers.get("content-type","")
                    if "json" in ct:
                        data = r.json()
                        print("[" + bk + "] JSON keys: " + str(list(data.keys()) if isinstance(data,dict) else "list")[:80])
                    else:
                        soup = BeautifulSoup(r.text, "html.parser")
                        print("[" + bk + "] Title: " + (soup.title.text if soup.title else "none"))
                        boost_els = soup.find_all(attrs={"class": lambda c: c and any(k in " ".join(c).lower() for k in ["boost","cbflash","cb-flash"])})
                        print("[" + bk + "] boost elements: " + str(len(boost_els)))
                        for el in boost_els[:3]:
                            print("[" + bk + "] el: " + el.get_text()[:100])
                    break
            except Exception as e2:
                print("[" + bk + "] erreur: " + str(e2)[:80])
    except Exception as e:
        print("[" + bk + "] ERREUR: " + str(e))
        print(traceback.format_exc()[:300])
    print("[scrape_winamax] " + str(len(boosts)) + " boost(s)")
    return boosts

def format_message(boost):
    emojis = {"Winamax": "O", "Betclic": "B", "Unibet": "U", "ParionsSport": "P"}
    emoji = emojis.get(boost["bookmaker"], "X")
    return (emoji + " <b>NOUVEAU BOOST -- " + boost["bookmaker"] + "</b>\n" +
            "Heure : " + boost["heure"] + "\n\n" +
            boost["titre"] + "\n\n" +
            '<a href="' + boost["url"] + '">Voir offre</a>')

def main():
    print("=== DEMARRAGE API MODE ===")
    cache = load_cache()
    print("Cache: " + str(len(cache)) + " entrees")
    nouveaux = []
    for scraper in [scrape_betclic, scrape_unibet, scrape_parionssport, scrape_winamax]:
        print("--- " + scraper.__name__ + " ---")
        try:
            boosts = scraper()
        except Exception as e:
            print("ERREUR " + scraper.__name__ + ": " + str(e))
            boosts = []
        for boost in boosts:
            uid = boost_uid(boost["bookmaker"], boost["titre"])
            if uid not in cache:
                nouveaux.append(boost)
                cache[uid] = {"vu_le": datetime.now().isoformat(),
                    "bookmaker": boost["bookmaker"], "titre": boost["titre"][:100]}
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
    main()
