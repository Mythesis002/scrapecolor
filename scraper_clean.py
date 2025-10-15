# save as scrape_wingo_cloud.py
# Optimized for Render.com with keep-alive server

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import time
import pandas as pd
import os
from datetime import datetime
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

# ---------- CONFIG ----------
URL = "https://damansuperstar1.com/#/saasLottery/WinGo?gameCode=WinGo_30S&lottery=WinGo"
PHONE = os.getenv("WINGO_PHONE", "6392449432")
PASSWORD = os.getenv("WINGO_PASSWORD", "Adarsh6392")
MAX_WAIT = 15
SCRAPE_INTERVAL_SECONDS = int(os.getenv("SCRAPE_INTERVAL", "270"))
CSV_FILENAME = "wingo_outcomes.csv"
HEADLESS = os.getenv("HEADLESS", "true").lower() == "true"
PORT = int(os.getenv("PORT", "10000"))  # Render uses PORT env variable
# -----------------------------

# Global status for health check
scraper_status = {
    "running": True,
    "last_scrape": "Not started",
    "total_cycles": 0,
    "errors": 0
}

# Simple HTTP server for health checks (prevents Render sleep)
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        
        status_html = f"""
        <html>
        <head><title>WinGo Scraper Status</title></head>
        <body style="font-family: Arial; padding: 20px;">
            <h1>🎰 WinGo Scraper Status</h1>
            <p><strong>Status:</strong> {'🟢 Running' if scraper_status['running'] else '🔴 Stopped'}</p>
            <p><strong>Last Scrape:</strong> {scraper_status['last_scrape']}</p>
            <p><strong>Total Cycles:</strong> {scraper_status['total_cycles']}</p>
            <p><strong>Errors:</strong> {scraper_status['errors']}</p>
            <p><strong>Uptime:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        </body>
        </html>
        """
        self.wfile.write(status_html.encode())
    
    def log_message(self, format, *args):
        pass  # Suppress HTTP logs

def start_health_server():
    """Start HTTP server in background thread"""
    server = HTTPServer(('0.0.0.0', PORT), HealthCheckHandler)
    print(f"🌐 Health check server started on port {PORT}")
    server.serve_forever()

def get_chrome_options():
    """Configure Chrome for cloud/headless environment"""
    options = Options()
    
    if HEADLESS:
        options.add_argument("--headless=new")
        print("🔇 Running in HEADLESS mode")
    
    # Essential for cloud environments
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-software-rasterizer")
    options.add_argument("--disable-extensions")
    options.add_argument("--start-maximized")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-notifications")
    options.add_experimental_option('excludeSwitches', ['enable-logging'])
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    # User agent to avoid detection
    options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    
    return options

def try_find(driver, selectors):
    for by, sel in selectors:
        try:
            el = driver.find_element(by, sel)
            return el
        except Exception:
            continue
    raise Exception(f"None of selectors found")

def is_login_form_present(driver):
    try:
        inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='password'], input[type='tel'], input[placeholder*='Phone' i]")
        for el in inputs:
            try:
                if el.is_displayed():
                    return True
            except:
                continue
        return False
    except:
        return False

def ensure_logged_in(driver, wait, phone, password, max_attempts=3):
    for attempt in range(1, max_attempts + 1):
        if not is_login_form_present(driver):
            try:
                wait.until(lambda d: len(d.find_elements(By.CSS_SELECTOR, ".nav-box, .record-body")) > 0)
            except:
                pass
            return True

        print(f"🟡 Login required (attempt {attempt}/{max_attempts})...")

        phone_selectors = [
            (By.CSS_SELECTOR, "input[type='tel']"),
            (By.CSS_SELECTOR, "input[type='text']"),
            (By.CSS_SELECTOR, "input[placeholder*='Phone' i]"),
        ]
        password_selectors = [
            (By.CSS_SELECTOR, "input[type='password']"),
        ]
        login_button_selectors = [
            (By.CSS_SELECTOR, "button[type='submit']"),
            (By.XPATH, "//button[contains(translate(., 'LOGIN', 'login'),'login')]")
        ]

        try:
            phone_input = try_find(driver, phone_selectors)
            pwd_input = try_find(driver, password_selectors)
            phone_input.clear(); phone_input.send_keys(phone); time.sleep(0.2)
            pwd_input.clear(); pwd_input.send_keys(password); time.sleep(0.2)
            
            try:
                login_btn = try_find(driver, login_button_selectors)
                login_btn.click()
            except:
                from selenium.webdriver.common.keys import Keys
                pwd_input.send_keys(Keys.ENTER)

            try:
                wait.until(lambda d: not is_login_form_present(d))
            except:
                pass

            try:
                wait.until(lambda d: len(d.find_elements(By.CSS_SELECTOR, ".nav-box, .record-body")) > 0)
                print("✅ Login confirmed")
                return True
            except:
                print("⚠️ Main containers not visible yet")
        except Exception as e:
            print(f"⚠️ Login interaction failed: {e}")

        time.sleep(2)

    print("❌ Unable to confirm login")
    return False

def dismiss_popups(driver):
    closed_count = 0
    close_selectors = [
        "img[src*='close']", ".van-popup__close", ".van-icon-cross",
        "button[class*='close']", "[class*='close-icon']", ".van-overlay"
    ]
    
    for pass_num in range(2):
        time.sleep(0.3)
        for selector in close_selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                for elem in elements:
                    try:
                        if elem.is_displayed() and elem.is_enabled():
                            try:
                                elem.click()
                                closed_count += 1
                                time.sleep(0.2)
                            except:
                                driver.execute_script("arguments[0].click();", elem)
                                closed_count += 1
                                time.sleep(0.2)
                    except:
                        continue
            except:
                continue
    
    if closed_count > 0:
        print(f"✅ Dismissed {closed_count} popup(s)")
    time.sleep(0.3)

def navigate_to_wingo(driver, wait, retries=3):
    def has_data_container(d):
        try:
            return len(d.find_elements(By.CSS_SELECTOR, "div.record-body div.van-row")) > 0
        except:
            return False

    def try_click_any(locators, wait_time=3):
        for by, sel in locators:
            try:
                el = WebDriverWait(driver, wait_time).until(EC.element_to_be_clickable((by, sel)))
                try:
                    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
                    time.sleep(0.2)
                except:
                    pass
                try:
                    el.click()
                    time.sleep(0.4)
                    return True
                except:
                    driver.execute_script("arguments[0].click();", el)
                    time.sleep(0.4)
                    return True
            except:
                continue
        return False

    if has_data_container(driver):
        print("✅ Already on data page")
        return True

    for attempt in range(1, retries + 1):
        print(f"🔄 Navigating to Win Go (attempt {attempt}/{retries})...")
        dismiss_popups(driver)

        wingo_locators = [
            (By.XPATH, "//h3[normalize-space()='Win Go']/ancestor::div[contains(@class,'daman_img')][1]"),
            (By.XPATH, "//*[contains(text(), 'Win Go') and not(self::script)]"),
        ]
        if try_click_any(wingo_locators, wait_time=5):
            print("✅ Clicked Win Go")
            time.sleep(1)
            dismiss_popups(driver)

        time.sleep(0.5)
        dismiss_popups(driver)

        history_locators = [
            (By.XPATH, "//*[contains(text(), 'History') and not(self::script)]"),
            (By.XPATH, "//*[contains(text(), 'Record') and not(self::script)]"),
        ]
        if try_click_any(history_locators, wait_time=3):
            print("✅ Clicked History")
            time.sleep(1)
            dismiss_popups(driver)

        try:
            driver.execute_script("window.scrollTo(0, 600);")
            time.sleep(0.3)
            dismiss_popups(driver)
        except:
            pass

        try:
            WebDriverWait(driver, 8).until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.record-body div.van-row")))
            rows = driver.find_elements(By.CSS_SELECTOR, "div.record-body div.van-row")
            if len(rows) > 0:
                print(f"✅ Reached data page ({len(rows)} rows)")
                return True
        except Exception as e:
            print(f"⚠️ Data rows not found: {str(e)[:50]}")
            time.sleep(1)

    print("❌ Could not reach data page")
    return False

def scrape_once(driver):
    rows = driver.find_elements(By.CSS_SELECTOR, "div.record-body div.van-row")
    print(f"📊 Found {len(rows)} rows")

    data = []
    for idx, row in enumerate(rows, 1):
        try:
            cols = row.find_elements(By.CSS_SELECTOR, "div.van-col")
            if len(cols) < 4:
                continue

            period = cols[0].text.strip()

            number = ""
            number_color = ""
            try:
                num_elem = cols[1].find_element(By.CSS_SELECTOR, "div.record-body-num")
                number = num_elem.text.strip()
                num_classes = num_elem.get_attribute("class").split()
                for cls in num_classes:
                    if "Color" in cls:
                        number_color = cls.replace("Color", "").lower()
                        break
            except:
                number = cols[1].text.strip()

            big_small = ""
            try:
                span_elem = cols[2].find_element(By.TAG_NAME, "span")
                big_small = span_elem.text.strip()
            except:
                big_small = cols[2].text.strip()

            color = ""
            try:
                color_elems = cols[3].find_elements(By.CSS_SELECTOR, "div.record-origin-I")
                if color_elems:
                    colors = []
                    for ce in color_elems:
                        classes = ce.get_attribute("class").split()
                        for cls in classes:
                            if cls in ["green", "red", "violet", "greenColor", "redColor", "violetColor"]:
                                colors.append(cls.replace("Color", "").lower())
                    color = ", ".join(colors) if colors else ""
            except:
                pass
            if not color and number_color:
                color = number_color

            data.append({
                "Period": period,
                "Number": number,
                "Big/Small": big_small,
                "Color": color
            })
        except Exception as e:
            print(f"❌ Error scraping row {idx}: {e}")
    return data

def main():
    global scraper_status
    
    # Start health check server in background
    health_thread = threading.Thread(target=start_health_server, daemon=True)
    health_thread.start()
    
    print("="*60)
    print("🚀 RENDER.COM WINGO SCRAPER")
    print(f"🕐 Started at: {datetime.now()}")
    print("="*60)
    
    # Setup Chrome with cloud-optimized options
    options = get_chrome_options()
    
    try:
        # Use webdriver-manager for automatic chromedriver management
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
    except Exception as e:
        print(f"⚠️ webdriver-manager failed: {e}")
        print("Trying default Chrome...")
        driver = webdriver.Chrome(options=options)

    try:
        print("\n📱 Opening website...")
        driver.get(URL)
        wait = WebDriverWait(driver, MAX_WAIT)
        time.sleep(3)

        print("\n🔐 Logging in...")
        if not ensure_logged_in(driver, wait, PHONE, PASSWORD, max_attempts=3):
            raise Exception("Login failed")
        time.sleep(3)

        print("\n🚫 Dismissing popups...")
        for i in range(2):
            dismiss_popups(driver)
            time.sleep(0.5)

        print("\n🎯 Navigating to data page...")
        if not navigate_to_wingo(driver, wait, retries=5):
            raise Exception("Navigation failed")
        
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.record-body div.van-row")))
        print("\n✅ Successfully navigated!")

        print("\n" + "="*60)
        print("🔄 CONTINUOUS SCRAPING MODE")
        print(f"⏱️  Interval: {SCRAPE_INTERVAL_SECONDS}s")
        print(f"🌐 Health endpoint: http://0.0.0.0:{PORT}/")
        print("="*60 + "\n")
        
        cycle = 0
        while True:
            try:
                cycle += 1
                scraper_status['total_cycles'] = cycle
                
                dismiss_popups(driver)
                
                if is_login_form_present(driver):
                    print("🟡 Re-logging in...")
                    if not ensure_logged_in(driver, wait, PHONE, PASSWORD, max_attempts=2):
                        time.sleep(30)
                        continue

                if len(driver.find_elements(By.CSS_SELECTOR, "div.record-body div.van-row")) == 0:
                    print("⚠️ Re-navigating...")
                    if not navigate_to_wingo(driver, wait, retries=3):
                        time.sleep(30)
                        continue

                print(f"\n{'='*60}")
                print(f"🕐 CYCLE #{cycle} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"{'='*60}\n")

                data = scrape_once(driver)
                if data:
                    df = pd.DataFrame(data)
                    
                    print("\n📋 Latest 10 outcomes:")
                    print(df.head(10).to_string(index=False))
                    
                    try:
                        with open(CSV_FILENAME, 'r'):
                            pass
                        df.to_csv(CSV_FILENAME, mode='a', header=False, index=False)
                    except FileNotFoundError:
                        df.to_csv(CSV_FILENAME, index=False)

                    try:
                        all_df = pd.read_csv(CSV_FILENAME)
                        all_df['Period'] = pd.to_numeric(all_df['Period'], errors='coerce').astype('Int64')
                        all_df = all_df.dropna(subset=['Period']).astype({'Period':'int64'})
                        all_df.sort_values(by='Period', ascending=True, inplace=True)
                        before = len(all_df)
                        all_df.drop_duplicates(subset=['Period'], keep='last', inplace=True)
                        after = len(all_df)
                        all_df.to_csv(CSV_FILENAME, index=False)
                        deduped = before - after
                        msg = f" ({deduped} dupes removed)" if deduped > 0 else ""
                        print(f"\n✅ Saved {len(df)} rows{msg} to '{CSV_FILENAME}'")
                        
                        scraper_status['last_scrape'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    except Exception as e:
                        print(f"⚠️ Sort error: {e}")
                        scraper_status['errors'] += 1
                else:
                    print("⚠️ No data scraped")

                print(f"\n💤 Sleeping {SCRAPE_INTERVAL_SECONDS}s...")
                dismiss_popups(driver)
                time.sleep(SCRAPE_INTERVAL_SECONDS)
                
            except KeyboardInterrupt:
                print("\n⛔ Ctrl+C pressed")
                scraper_status['running'] = False
                break
            except Exception as e:
                print(f"❌ Loop error: {e}")
                scraper_status['errors'] += 1
                time.sleep(30)

    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        scraper_status['running'] = False
        scraper_status['errors'] += 1
        try:
            driver.save_screenshot("error_screenshot.png")
            print("📸 Screenshot saved")
        except:
            pass
    finally:
        try:
            driver.quit()
        except:
            pass
        print("\n✅ Browser closed")
        print("🏁 SCRAPER STOPPED")
        scraper_status['running'] = False

if __name__ == "__main__":
    main()
