# save as scrape_wingo.py

# install all these libraries
# pip install selenium pandas

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import pandas as pd

# ---------- CONFIG ----------
URL = "https://damansuperstar1.com/#/saasLottery/WinGo?gameCode=WinGo_30S&lottery=WinGo"
PHONE = "6392449432"     # your phone
PASSWORD = "Adarsh6392"  # your password
MAX_WAIT = 15             # seconds to wait for elements to appear
SCRAPE_INTERVAL_SECONDS = 270  # 5 minutes between scrapes
CSV_FILENAME = "wingo_outcomes.csv"
# -----------------------------

def try_find(driver, selectors):
    """Try a list of (By, selector) until one is found. Returns WebElement or raises."""
    for by, sel in selectors:
        try:
            el = driver.find_element(by, sel)
            return el
        except Exception:
            continue
    raise Exception(f"None of selectors found: {selectors}")

def is_login_form_present(driver):
    """Heuristically determine if we're still on the login page (visible phone/password inputs)."""
    try:
        inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='password'], input[type='tel'], input[placeholder*='Phone' i], input[placeholder*='Mobile' i]")
        for el in inputs:
            try:
                if el.is_displayed():
                    return True
            except Exception:
                continue
        return False
    except Exception:
        return False

def ensure_logged_in(driver, wait, phone, password, max_attempts=3):
    """Ensure the session is logged in. If on login page, submit credentials and wait until login form disappears
    or main containers appear. Retries up to max_attempts.
    Returns True on success, False on failure.
    """
    for attempt in range(1, max_attempts + 1):
        if not is_login_form_present(driver):
            # Additional sanity check: look for app containers
            try:
                wait.until(lambda d: len(d.find_elements(By.CSS_SELECTOR, ".nav-box, .record-body")) > 0)
            except Exception:
                pass
            return True

        print(f"🟡 Login required (attempt {attempt}/{max_attempts})...")

        phone_selectors = [
            (By.CSS_SELECTOR, "input[type='tel']"),
            (By.CSS_SELECTOR, "input[type='text']"),
            (By.CSS_SELECTOR, "input[placeholder*='Phone' i]"),
            (By.CSS_SELECTOR, "input[placeholder*='Mobile' i]")
        ]
        password_selectors = [
            (By.CSS_SELECTOR, "input[type='password']"),
            (By.CSS_SELECTOR, "input[placeholder*='Password' i]")
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
            except Exception:
                # fallback: press Enter in password field
                try:
                    from selenium.webdriver.common.keys import Keys
                    pwd_input.send_keys(Keys.ENTER)
                except Exception:
                    pass

            # Wait for login form to disappear or app containers to appear
            try:
                wait.until(lambda d: not is_login_form_present(d))
            except Exception:
                pass

            # Final confirmation: look for app main containers
            try:
                wait.until(lambda d: len(d.find_elements(By.CSS_SELECTOR, ".nav-box, .record-body, [class*='homepage']")) > 0)
                print("✅ Login confirmed (main containers visible)")
                return True
            except Exception:
                print("⚠️ Main containers not visible yet after login click")
        except Exception as e:
            print(f"⚠️ Login interaction failed: {e}")

        time.sleep(2)

    print("❌ Unable to confirm login after retries")
    return False

def dismiss_popups(driver):
    """Aggressively dismiss all popups/overlays multiple times."""
    print("🔍 Scanning for popups...")
    closed_count = 0
    
    # Try to find and click close buttons - multiple passes
    close_selectors = [
        "img[src*='close']",
        ".van-popup__close",
        ".van-icon-cross",
        "button[class*='close']",
        "[class*='close-icon']",
        "[class*='popup-close']",
        ".van-overlay",
        "[class*='modal'] [class*='close']",
        "[class*='dialog'] [class*='close']",
        "button[aria-label*='close' i]",
        "button[aria-label*='Close' i]",
    ]
    
    # Multiple passes to catch popups that appear after closing others
    for pass_num in range(3):
        time.sleep(0.5)  # Small delay between passes
        
        for selector in close_selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                for elem in elements:
                    try:
                        if elem.is_displayed() and elem.is_enabled():
                            # Try regular click first
                            try:
                                elem.click()
                                closed_count += 1
                                print(f"✅ Closed popup (selector: {selector})")
                                time.sleep(0.3)
                            except:
                                # Try JS click if regular click fails
                                try:
                                    driver.execute_script("arguments[0].click();", elem)
                                    closed_count += 1
                                    print(f"✅ Closed popup via JS (selector: {selector})")
                                    time.sleep(0.3)
                                except:
                                    pass
                    except:
                        continue
            except:
                continue
        
        # Also try ESC key to close popups
        try:
            from selenium.webdriver.common.keys import Keys
            driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.ESCAPE)
            time.sleep(0.3)
        except:
            pass
    
    if closed_count > 0:
        print(f"✅ Dismissed {closed_count} popup(s)")
    else:
        print("ℹ️  No popups found")
    
    time.sleep(0.5)

def navigate_to_wingo(driver, wait, retries=3):
    """Navigate to the Win Go page that contains record-body with van-row rows.
    Returns True if navigation succeeded, False otherwise.
    """
    def has_data_container(d):
        try:
            return len(d.find_elements(By.CSS_SELECTOR, "div.record-body div.van-row")) > 0
        except Exception:
            return False

    # Utility: try multiple locators and click with Selenium first, JS fallback second
    def try_click_any(locators, scroll=True, wait_time=3):
        for by, sel in locators:
            try:
                el = WebDriverWait(driver, wait_time).until(EC.element_to_be_clickable((by, sel)))
                if scroll:
                    try:
                        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
                        time.sleep(0.3)
                    except Exception:
                        pass
                try:
                    el.click()
                    time.sleep(0.5)
                    return True
                except Exception:
                    # JS click fallback
                    try:
                        driver.execute_script("arguments[0].click();", el)
                        time.sleep(0.5)
                        return True
                    except Exception:
                        continue
            except Exception:
                continue
        return False

    # Step 0: If already on data page, return
    if has_data_container(driver):
        print("✅ Already on data page (record-body present)")
        return True

    for attempt in range(1, retries + 1):
        print(f"\n🔄 Navigating to Win Go (attempt {attempt}/{retries})...")

        # Step 1: Aggressively dismiss any popups FIRST
        dismiss_popups(driver)

        # Step 2: Try clicking Win Go card/button
        wingo_locators = [
            (By.XPATH, "//h3[normalize-space()='Win Go']/ancestor::div[contains(@class,'daman_img')][1]"),
            (By.XPATH, "//*[contains(text(), 'Win Go') and not(self::script)]"),
            (By.XPATH, "//*[contains(text(), 'WinGo') and not(self::script)]"),
            (By.XPATH, "//div[contains(@class,'lottery')]//h3[contains(text(),'Win Go')]"),
            (By.CSS_SELECTOR, "div[class*='lottery'] h3"),
        ]
        clicked = try_click_any(wingo_locators, wait_time=5)
        if clicked:
            print("✅ Clicked Win Go card/button")
            time.sleep(2)
            # Dismiss popups again after clicking
            dismiss_popups(driver)

        # Step 3: Check if we reached the game page
        time.sleep(1)
        
        # Dismiss popups before looking for tabs
        dismiss_popups(driver)
        
        # Step 4: Skip period tab click (default already 30S)
        print("⏭️ Skipping period tab selection (default is 30S)")

        # Step 5: Try clicking history/records tab
        print("🔍 Looking for History/Records tab...")
        history_locators = [
            (By.XPATH, "//*[contains(text(), 'History') and not(self::script)]"),
            (By.XPATH, "//*[contains(text(), 'Game Record') and not(self::script)]"),
            (By.XPATH, "//*[contains(text(), 'History Records') and not(self::script)]"),
            (By.XPATH, "//*[contains(text(), 'Record') and not(self::script)]"),
            (By.XPATH, "//button[contains(text(), 'History')]"),
            (By.CSS_SELECTOR, "div[class*='history']"),
        ]
        if try_click_any(history_locators, wait_time=3):
            print("✅ Clicked History/Records tab")
            time.sleep(1)
            # Dismiss popups after opening history
            dismiss_popups(driver)
        else:
            print("⚠️ Could not find History tab, trying to scroll...")

        # Step 6: Scroll to trigger lazy loading
        try:
            driver.execute_script("window.scrollTo(0, 400);")
            time.sleep(0.5)
            dismiss_popups(driver)
            driver.execute_script("window.scrollTo(0, 800);")
            time.sleep(0.5)
            dismiss_popups(driver)
        except:
            pass

        # Step 7: Wait for data container
        try:
            print("⏳ Waiting for data rows to appear...")
            WebDriverWait(driver, 8).until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.record-body div.van-row")))
            time.sleep(1)
            
            # Verify we have data
            rows = driver.find_elements(By.CSS_SELECTOR, "div.record-body div.van-row")
            if len(rows) > 0:
                print(f"✅ Reached data page ({len(rows)} rows found)")
                return True
            else:
                print("⚠️ Found record-body but no rows, retrying...")
        except Exception as e:
            print(f"⚠️ Data rows not found yet: {str(e)[:100]}")
            # Additional scroll
            try:
                driver.execute_script("window.scrollBy(0, 600);")
            except:
                pass
            time.sleep(1)

    print("❌ Could not reach data page after all retries")
    return False

def main():
    options = Options()
    options.add_experimental_option('excludeSwitches', ['enable-logging'])
    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-notifications")

    # Use local chromedriver
    driver = webdriver.Chrome(options=options)

    try:
        print("="*60)
        print("🚀 AUTOMATED WINGO SCRAPER")
        print("="*60)
        print("\n📱 Opening website...")
        driver.get(URL)
        wait = WebDriverWait(driver, MAX_WAIT)
        time.sleep(3)

        # ---------- LOGIN (robust with retry) ----------
        print("\n🔐 Logging in...")
        if not ensure_logged_in(driver, wait, PHONE, PASSWORD, max_attempts=3):
            raise Exception("Login failed after retries")
        print("⏳ Waiting for dashboard to load...")
        time.sleep(3)

        # ---------- AGGRESSIVE POPUP DISMISSAL ----------
        print("\n🚫 Dismissing all popups...")
        for i in range(3):
            print(f"   Pass {i+1}/3...")
            dismiss_popups(driver)
            time.sleep(1)

        # ---------- NAVIGATE TO DATA PAGE ----------
        print("\n🎯 Navigating to Win Go data page...")
        reached = navigate_to_wingo(driver, wait, retries=5)
        if not reached:
            print("\n⚠️ Could not automatically navigate to data page.")
            print("📸 Taking screenshot for debugging...")
            driver.save_screenshot("navigation_failed.png")
            raise Exception("Navigation failed: record-body rows not found")
        
        # Final verification
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.record-body div.van-row")))
        time.sleep(1)
        print("\n✅ Successfully navigated to data page!")

        # ---------- PERIODIC SCRAPING LOOP ----------
        def scrape_once():
            rows = driver.find_elements(By.CSS_SELECTOR, "div.record-body div.van-row")
            print(f"📊 Found {len(rows)} rows to scrape")

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

        print("\n" + "="*60)
        print("🔄 ENTERING CONTINUOUS SCRAPING MODE")
        print(f"⏱️  Scraping every {SCRAPE_INTERVAL_SECONDS} seconds (5 minutes)")
        print("⛔ Press Ctrl+C to stop")
        print("="*60 + "\n")
        
        while True:
            try:
                # Dismiss popups at start of each cycle
                dismiss_popups(driver)
                
                # If we got logged out, re-login first
                if is_login_form_present(driver):
                    print("🟡 Login form detected during loop. Re-logging in...")
                    if not ensure_logged_in(driver, wait, PHONE, PASSWORD, max_attempts=2):
                        print("❌ Re-login failed, will retry soon")
                        time.sleep(30)
                        continue

                # Ensure we are still on the data page; re-navigate if DOM missing
                if len(driver.find_elements(By.CSS_SELECTOR, "div.record-body div.van-row")) == 0:
                    print("⚠️ Data rows missing. Re-navigating to data page...")
                    dismiss_popups(driver)
                    if not navigate_to_wingo(driver, wait, retries=3):
                        print("❌ Re-navigation failed. Will retry after interval.")
                        time.sleep(30)
                        continue

                print("\n" + "="*60)
                print(f"🕐 SCRAPING CYCLE - {time.strftime('%Y-%m-%d %H:%M:%S')}")
                print("="*60 + "\n")

                data = scrape_once()
                if data:
                    df = pd.DataFrame(data)
                    
                    # Display first 10 results
                    print("\n📋 Latest 10 outcomes:")
                    print(df.head(10).to_string(index=False))
                    
                    # Append to the same file, then sort by Period ascending
                    try:
                        # If file exists, append without header
                        with open(CSV_FILENAME, 'r'):
                            pass
                        df.to_csv(CSV_FILENAME, mode='a', header=False, index=False)
                    except FileNotFoundError:
                        # If file does not exist, write with header
                        df.to_csv(CSV_FILENAME, index=False)

                    # Enforce ascending order by Period (oldest to newest), robust to missing header
                    try:
                        try:
                            all_df = pd.read_csv(CSV_FILENAME)
                            if 'Period' not in all_df.columns:
                                raise KeyError('Missing Period header')
                        except Exception:
                            # Re-read without header and assign expected columns
                            all_df = pd.read_csv(CSV_FILENAME, header=None, names=['Period','Number','Big/Small','Color'])

                        # Ensure Period is sortable numerically
                        all_df['Period'] = pd.to_numeric(all_df['Period'], errors='coerce').astype('Int64')
                        all_df = all_df.dropna(subset=['Period']).astype({'Period':'int64'})
                        # Sort ascending, then drop duplicate Periods (keep the latest appended)
                        all_df.sort_values(by='Period', ascending=True, inplace=True)
                        before = len(all_df)
                        all_df.drop_duplicates(subset=['Period'], keep='last', inplace=True)
                        after = len(all_df)
                        all_df.to_csv(CSV_FILENAME, index=False)
                        deduped = before - after
                        msg = f" and removed {deduped} duplicate(s)" if deduped > 0 else ""
                        print(f"\n✅ Appended {len(df)} rows, sorted by Period (ascending){msg} in '{CSV_FILENAME}'")
                    except Exception as sort_err:
                        print(f"⚠️ Could not sort CSV this cycle: {sort_err}")
                else:
                    print("⚠️ No data scraped this cycle")

                print(f"\n💤 Sleeping for {SCRAPE_INTERVAL_SECONDS} seconds...")
                
                # Dismiss popups before sleeping too
                dismiss_popups(driver)
                time.sleep(SCRAPE_INTERVAL_SECONDS)
                
            except KeyboardInterrupt:
                print("\n⛔ Stopping continuous scraping (Ctrl+C pressed)")
                break
            except Exception as e:
                print(f"❌ Loop error: {e}")
                import traceback
                traceback.print_exc()
                print("\n⏳ Waiting 30 seconds before retry...")
                time.sleep(30)

    except Exception as e:
        print(f"\n❌ An error occurred: {e}")
        import traceback
        traceback.print_exc()
        
        # Save screenshot for debugging
        try:
            driver.save_screenshot("error_screenshot.png")
            print("📸 Screenshot saved as 'error_screenshot.png'")
        except:
            pass
            
    finally:
        try:
            driver.quit()
        except Exception:
            pass
        print("\n✅ Browser closed")
        print("="*60)
        print("🏁 SCRAPER STOPPED")
        print("="*60)

if __name__ == "__main__":
    main()