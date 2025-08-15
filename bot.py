# bot.py
import os, json, re, time, requests
from bs4 import BeautifulSoup

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
SEEN_FILE = "seen_jobs.json"
HEADERS = {"User-Agent": "Mozilla/5.0 (JobBot)"}

SEARCH_URL = "https://www.amazon.jobs/en/search?category=remote&country=IND&sort=recent"

EXCLUDED_CITIES = [
    "bengaluru","bangalore","hyderabad","pune","chennai","mumbai","navi mumbai",
    "gurgaon","gurugram","noida","delhi","new delhi","kolkata","jaipur","ahmedabad",
    "surat","indore","nagpur","lucknow","coimbatore","kochi","trivandrum","thiruvananthapuram",
    "chandigarh","mohali","mysore","mysuru","bhubaneswar","visakhapatnam","vadodara","thane"
]

PAN_KEYWORDS = [
    "pan india","pan-india","anywhere in india","across india","remote within india",
    "work from home - india","india - remote"
]

def load_seen():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r") as f:
            try:
                return set(json.load(f))
            except:
                return set()
    return set()

def save_seen(seen):
    with open(SEEN_FILE, "w") as f:
        json.dump(sorted(list(seen)), f)

def send_telegram(text):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Missing TELEGRAM_TOKEN or TELEGRAM_CHAT_ID")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode":"HTML"}, timeout=20)

def contains_excluded(text):
    t = (text or "").lower()
    return any(city in t for city in EXCLUDED_CITIES)

def has_pan_keyword(text):
    t = (text or "").lower()
    return any(k in t for k in PAN_KEYWORDS)

def get_soup(url):
    r = requests.get(url, headers=HEADERS, timeout=25)
    r.raise_for_status()
    return BeautifulSoup(r.text, "html.parser")

def fetch_listings():
    soup = get_soup(SEARCH_URL)
    results = []
    # find links that look like job links
    for a in soup.select("a[href*='/job/'], a[href*='/jobs/']"):
        href = a.get("href")
        if not href: continue
        if not href.startswith("http"):
            link = "https://www.amazon.jobs" + href
        else:
            link = href
        title = a.get_text(strip=True) or "Amazon Job"
        # find location text in nearest container
        parent = a.parent
        loc_text = ""
        if parent:
            loc = parent.select_one(".location, .job-location, .location-and-id")
            if loc: loc_text = loc.get_text(strip=True)
        results.append({"title": title, "link": link, "location": loc_text})
    # deduplicate by link
    seen = set()
    unique = []
    for r in results:
        if r["link"] not in seen:
            unique.append(r); seen.add(r["link"])
    return unique

def fetch_description(url):
    try:
        soup = get_soup(url)
        return soup.get_text(" ", strip=True)
    except Exception:
        return ""

def main():
    seen = load_seen()
    cards = fetch_listings()

    # on first run, register existing so you don't get spam
    if not seen and cards:
        for c in cards: seen.add(c["link"])
        save_seen(seen)
        send_telegram("✅ Amazon PAN-India Job Bot is live. I will notify you of NEW PAN-India remote jobs.")
        return

    new_found = False
    for c in cards:
        link = c["link"]
        if link in seen: continue
        desc = fetch_description(link)
        loc = c.get("location","")
        # exclude if location or description contains restricted city
        if contains_excluded(loc) or contains_excluded(desc):
            seen.add(link); continue
        # accept only if it mentions pan-india or generic India
        if not (has_pan_keyword(loc) or has_pan_keyword(desc) or loc.strip().lower() in {"india", "remote - india", "work from home - india"}):
            seen.add(link); continue
        # send alert
        msg = f"🆕 <b>{c['title']}</b>\n📍 {loc or 'PAN India / Remote'}\n🔗 {link}"
        send_telegram(msg)
        seen.add(link)
        new_found = True
        time.sleep(1)

    save_seen(seen)
    if not new_found:
        print("No new PAN-India jobs found.")

if __name__ == "__main__":
    main()
