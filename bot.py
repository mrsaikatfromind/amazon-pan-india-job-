
import requests, os, json, re, time
from bs4 import BeautifulSoup

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
SEEN_JOBS_FILE = "seen_jobs.json"

HEADERS = {"User-Agent": "Mozilla/5.0 (JobBot; +github-actions)"}

# Remote + India (sorted recent). Adjust if Amazon changes filters.
SEARCH_URL = "https://www.amazon.jobs/en/search?category=remote&country=IND&sort=recent"

# Cities that usually mean "remote but only from this city/area"
EXCLUDED_CITIES = [
    "Bengaluru","Bangalore","Hyderabad","Pune","Chennai","Mumbai","Navi Mumbai",
    "Gurgaon","Gurugram","Noida","Delhi","New Delhi","Kolkata","Jaipur","Ahmedabad",
    "Surat","Indore","Nagpur","Lucknow","Coimbatore","Kochi","Trivandrum","Thiruvananthapuram",
    "Chandigarh","Mohali","Mysore","Mysuru","Bhubaneswar","Vizag","Visakhapatnam","Vadodara",
    "Thane","Kharadi","Hinjewadi"
]

# Phrases that indicate truly Pan-India eligibility
PAN_INDIA_KEYWORDS = [
    "PAN India","Pan-India","Anywhere in India","across India","India - Remote",
    "Work from home - India","WFH - India","Remote within India"
]

def load_seen():
    if os.path.exists(SEEN_JOBS_FILE):
        with open(SEEN_JOBS_FILE, "r") as f: return set(json.load(f))
    return set()

def save_seen(seen):
    with open(SEEN_JOBS_FILE, "w") as f: json.dump(sorted(list(seen)), f)

def tg_send(text):
    if not (TELEGRAM_TOKEN and TELEGRAM_CHAT_ID): return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode":"HTML"}, timeout=20)

def contains_city(text):
    t = text.lower()
    return any(c.lower() in t for c in EXCLUDED_CITIES)

def is_pan_india(loc_text, description):
    blob = f"{loc_text}\n{description}"
    if any(re.search(k, blob, re.IGNORECASE) for k in PAN_INDIA_KEYWORDS): return True
    # Accept plain "India" (no city)
    if loc_text.strip().lower() in {"india","remote - india","work from home - india"}: return True
    return False

def get_soup(url):
    r = requests.get(url, headers=HEADERS, timeout=25)
    r.raise_for_status()
    return BeautifulSoup(r.text, "html.parser")

def fetch_jobs():
    soup = get_soup(SEARCH_URL)
    jobs = []
    # NOTE: Selectors may change; adjust if needed.
    for card in soup.select(".job-tile, .job-card"):  # be flexible
        a = card.select_one("a[href*='/job/']")
        if not a: continue
        link = "https://www.amazon.jobs" + a["href"]
        title_el = card.select_one(".job-title, h3, .title")
        loc_el = card.select_one(".location-and-id, .location, .job-location")
        title = title_el.get_text(strip=True) if title_el else "Untitled"
        location = loc_el.get_text(strip=True) if loc_el else ""
        jobs.append({"title": title, "link": link, "location": location})
    return jobs

def fetch_description(job_url):
    try:
        s = get_soup(job_url)
        # Grab visible text
        return s.get_text(" ", strip=True)
    except Exception:
        return ""

def main():
    try:
        seen = load_seen()
        cards = fetch_jobs()

        # First-run safety: record current jobs but don’t spam you
        if not seen and cards:
            for j in cards: seen.add(j["link"])
            save_seen(seen)
            tg_send("✅ Amazon PAN-India Job Bot is live. I’ll ping you for NEW matches.")
            return

        new_links = []
        for j in cards:
            if j["link"] in seen: continue
            desc = fetch_description(j["link"])
            # Skip if city-restricted remote
            if contains_city(j["location"]) or contains_city(desc): 
                seen.add(j["link"]); continue
            # Keep only truly PAN-India
            if not is_pan_india(j["location"], desc):
                seen.add(j["link"]); continue

            # Send alert
            msg = f"🆕 <b>{j['title']}</b>\n📍 {j['location']}\n🔗 {j['link']}"
            tg_send(msg)
            new_links.append(j["link"])
            seen.add(j["link"])
            time.sleep(1)  # polite

        if new_links:
            save_seen(seen)
        else:
            # Still persist so we don't re-check same items
            save_seen(seen)
    except Exception as e:
        # Don’t fail the workflow on transient errors
        tg_send(f"⚠️ Bot error: {e}")

if __name__ == "__main__":
    main()
