from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import csv
import os
import re

# 디렉토리 설정
csv_dir = "./Crawling_data/"
os.makedirs(csv_dir, exist_ok=True)
csv_path = os.path.join(csv_dir, "steam_game.csv")

# CSV 파일 초기화 (헤더 작성)
try:
    with open(csv_path, mode='w', newline='', encoding='utf-8-sig') as file:
        writer = csv.writer(file)
        writer.writerow(["Title", "Description"])
    print(f"📁 CSV 파일 초기화: {csv_path}")
except Exception as e:
    print(f"❌ CSV 파일 초기화 실패: {e}")
    exit(1)

# 크롤링 설정
GAMES_PER_PAGE = 12  # 한 페이지당 게임 수
TOTAL_GAMES = 6397  # 총 크롤링할 게임 수
PAGES_NEEDED = (TOTAL_GAMES + GAMES_PER_PAGE - 1) // GAMES_PER_PAGE

# 속도 최적화 설정
WAIT_TIMEOUT = 10  # 기본 대기시간
SCROLL_DELAY = 0.3  # 스크롤 후 대기
CLICK_DELAY = 1.5  # 클릭 후 대기
PAGE_LOAD_DELAY = 2  # 페이지 로딩 대기
WINDOW_SWITCH_DELAY = 1  # 창 전환 후 대기

# 크롬 드라이버 설정 (속도 최적화)
options = Options()
options.add_argument("--start-maximized")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--disable-blink-features=AutomationControlled")
options.add_argument("--disable-images")  # 이미지 로딩 비활성화
options.add_argument("--disable-javascript")  # 불필요한 JS 비활성화
options.add_argument("--disable-plugins")
options.add_argument("--disable-extensions")
options.add_argument("--no-first-run")
options.add_argument("--disable-default-apps")
options.add_argument("--disable-gpu")
options.add_argument("--disable-logging")
options.add_argument("--log-level=3")
options.add_argument(
    "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
options.add_experimental_option('useAutomationExtension', False)
options.add_argument("--page-load-strategy=eager")  # DOM 로딩 완료되면 바로 진행

# ChromeDriver 설정
try:
    driver = webdriver.Chrome(options=options)
except Exception as e:
    print(f"❌ ChromeDriver 초기화 실패: {e}")
    exit(1)

# 페이지 로드 타임아웃 설정
driver.set_page_load_timeout(15)
driver.implicitly_wait(5)

driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
driver.execute_script("Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]})")
driver.execute_script("Object.defineProperty(navigator, 'languages', {get: () => ['ko-KR', 'ko']})")

wait = WebDriverWait(driver, WAIT_TIMEOUT)

# 스팀 언어 설정
def setup_korean_language():
    print("🔧 한국어 설정 중...")
    cookies_to_add = [
        {'name': 'Steam_Language', 'value': 'koreana', 'domain': '.steampowered.com'},
        {'name': 'language', 'value': 'koreana', 'domain': '.steampowered.com'},
        {'name': 'steamCountry', 'value': 'KR%7C37d90c1b1f756ad3bb4e20b0c8739de4', 'domain': '.steampowered.com'},
        {'name': 'steamCurrencyId', 'value': '23', 'domain': '.steampowered.com'},
    ]
    for cookie in cookies_to_add:
        try:
            driver.add_cookie(cookie)
        except Exception as e:
            print(f"쿠키 설정 실패: {cookie['name']} - {e}")
    try:
        driver.execute_script("""
            localStorage.setItem('Steam_Language', 'koreana');
            localStorage.setItem('language', 'koreana');
            localStorage.setItem('steamCountry', 'KR');
        """)
    except Exception as e:
        print(f"로컬스토리지 설정 실패: {e}")
    print("✅ 한국어 설정 완료")

# 나이 확인 처리
def handle_age_check():
    try:
        age_elements = driver.find_elements(By.XPATH, '//select[@id="ageYear"] | //input[@id="ageYear"]')
        if not age_elements:
            print("나이 확인 창이 없습니다.")
            return True
        age_check = age_elements[0]
        if not age_check.is_displayed() or not age_check.is_enabled():
            print("나이 확인 요소가 비활성화되어 있습니다.")
            return True
        if age_check.tag_name == "select":
            from selenium.webdriver.support.ui import Select
            select = Select(age_check)
            select.select_by_value("1990")
        elif age_check.tag_name == "input":
            age_check.clear()
            age_check.send_keys("1990")
        view_btn_elements = driver.find_elements(By.XPATH, '//*[@id="view_product_page_btn"]')
        if not view_btn_elements:
            print("view_product_page_btn을 찾을 수 없습니다.")
            return False
        view_btn = view_btn_elements[0]
        if view_btn.is_displayed() and view_btn.is_enabled():
            try:
                view_btn.click()
            except:
                driver.execute_script("arguments[0].click();", view_btn)
        else:
            print("view_product_page_btn이 클릭할 수 없는 상태입니다.")
            return False
        try:
            WebDriverWait(driver, 5).until(
                EC.any_of(
                    EC.presence_of_element_located((By.ID, "game_area_description")),
                    EC.presence_of_element_located((By.CLASS_NAME, "apphub_AppName"))
                )
            )
            return True
        except:
            print("페이지 로딩 대기 시간 초과")
            return True
    except Exception as e:
        print(f"나이 확인 처리 오류: {e}")
        return False

# 게임 정보 추출 함수
def extract_game_info(game_number):
    title = None
    title_selectors = [
        ".apphub_AppName",
        "h1.apphub_AppName",
        "#appHubAppName",
        ".page_title_area .apphub_AppName",
        '//*[@id="tabletGrid"]/div[1]/div[2]/div[1]/div[1]/a[3]/span',
        '//*[@id="tabletGrid"]/div[1]/div[2]/div[1]/div[1]/a[4]/span'
    ]
    for selector in title_selectors:
        try:
            if selector.startswith('/'):
                title_elem = WebDriverWait(driver, 2).until(
                    EC.presence_of_element_located((By.XPATH, selector))
                )
            else:
                title_elem = WebDriverWait(driver, 2).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                )
            title = title_elem.text.strip()
            if title:
                break
        except:
            continue
    if not title:
        title = f"제목_없음_{game_number}"
    description = "설명 없음"
    try:
        driver.execute_script("""
            var moreButtons = document.querySelectorAll('div, span, a');
            for(var i = 0; i < moreButtons.length; i++) {
                var text = moreButtons[i].innerText || moreButtons[i].textContent;
                if(text && (text.includes('더 보기') || text.includes('더보기') || text.includes('Read More'))) {
                    moreButtons[i].click();
                    break;
                }
            }
        """)
        time.sleep(0.5)
    except Exception as e:
        print(f"더보기 버튼 처리 오류: {e}")
    desc_selectors = [
        "#game_area_description",
        ".game_description_snippet",
        ".game_area_description",
        ".game_page_autocollapse_ctn",
        ".game_description"
    ]
    for selector in desc_selectors:
        try:
            desc_elem = WebDriverWait(driver, 2).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, selector))
            )
            desc_text = desc_elem.text.strip()
            if desc_text and len(desc_text) > 20:
                description = re.sub(r'\s+', ' ', desc_text).strip()
                break
        except:
            continue
    return title, description

# 메인 크롤링 로직
print(f"🚀 Steam 게임 크롤링 시작 (총 {TOTAL_GAMES}개 게임, {PAGES_NEEDED}페이지)")
print("📝 제목과 설명만 수집합니다 (이미지 제외)")

game_counter = 1

for page in range(PAGES_NEEDED):
    offset = page * GAMES_PER_PAGE
    page_url = f"https://store.steampowered.com/genre/Free%20to%20Play/?offset={offset}"
    print(f"\n📄 페이지 {page + 1}/{PAGES_NEEDED} 처리 중 (오프셋: {offset})")
    print(f"🔗 URL: {page_url}")

    driver.get(page_url)
    setup_korean_language()
    time.sleep(PAGE_LOAD_DELAY)
    driver.execute_script("window.scrollTo(0, 2000);")
    time.sleep(SCROLL_DELAY)

    main_window = driver.current_window_handle
    games_this_page = min(GAMES_PER_PAGE, TOTAL_GAMES - (page * GAMES_PER_PAGE))

    for i in range(1, games_this_page + 1):
        if game_counter > TOTAL_GAMES:
            break
        print(f"\n[{game_counter}/{TOTAL_GAMES}] 게임 #{game_counter} 처리 중... (페이지 {page + 1}, 항목 {i})")
        try:
            xpath = f'//*[@id="SaleSection_377601"]/div[2]/div[2]/div[2]/div/div[2]/div[{i}]/div/div/div/div[1]/a/div/div[2]/img'
            try:
                game_img = wait.until(EC.element_to_be_clickable((By.XPATH, xpath)))
                driver.execute_script("arguments[0].scrollIntoView(true);", game_img)
                time.sleep(SCROLL_DELAY)
                game_img = driver.find_element(By.XPATH, xpath)
                driver.execute_script("arguments[0].click();", game_img)
                print(f"  📱 게임 링크 클릭 완료")
                time.sleep(CLICK_DELAY)
            except Exception as e:
                print(f"  ❌ 게임 링크 클릭 실패: {e}")
                game_counter += 1
                continue
            all_windows = driver.window_handles
            for w in all_windows:
                if w != main_window:
                    driver.switch_to.window(w)
                    break
            handle_age_check()
            title, description = extract_game_info(game_counter)
            print(f"  📝 게임 제목: {title}")
            print(f"  📄 설명: {description}")

            # 실시간 CSV 저장
            try:
                with open(csv_path, mode='a', newline='', encoding='utf-8-sig') as file:
                    writer = csv.writer(file)
                    writer.writerow([title, description])
                print(f"  ✅ 데이터 CSV에 저장 완료")
            except Exception as e:
                print(f"  ❌ CSV 저장 실패: {e}")
                # 에러 데이터도 저장
                try:
                    with open(csv_path, mode='a', newline='', encoding='utf-8-sig') as file:
                        writer = csv.writer(file)
                        writer.writerow([f"에러_게임_{game_counter}", f"데이터 수집 실패: {str(e)}"])
                except Exception as csv_e:
                    print(f"  ❌ CSV 에러 데이터 저장 실패: {csv_e}")

        except Exception as e:
            print(f"  ❌ 게임 #{game_counter} 처리 중 에러: {e}")
            try:
                with open(csv_path, mode='a', newline='', encoding='utf-8-sig') as file:
                    writer = csv.writer(file)
                    writer.writerow([f"에러_게임_{game_counter}", f"데이터 수집 실패: {str(e)}"])
                print(f"  ✅ 에러 데이터 CSV에 저장 완료")
            except Exception as csv_e:
                print(f"  ❌ CSV 에러 데이터 저장 실패: {csv_e}")

        finally:
            try:
                if len(driver.window_handles) > 1:
                    driver.close()
                driver.switch_to.window(main_window)
            except:
                pass
            time.sleep(WINDOW_SWITCH_DELAY)
            game_counter += 1

    print(f"✅ 페이지 {page + 1} 완료 ({game_counter - 1}개 게임 수집됨)")

# 드라이버 종료
driver.quit()

print(f"\n🎉 크롤링 완료!")
print(f"📁 CSV 파일: {csv_path}")
print(f"📊 수집된 게임 수: {game_counter - 1}개")

# 수집된 게임 목록 출력 (처음 10개만)
try:
    with open(csv_path, mode='r', encoding='utf-8-sig') as file:
        reader = csv.reader(file)
        next(reader)  # 헤더 건너뛰기
        print("\n📋 수집된 게임 목록 (처음 10개):")
        for i, row in enumerate(reader, 1):
            if i > 10:
                break
            print(f"  {i}. {row[0]}")
except Exception as e:
    print(f"❌ CSV 파일 읽기 실패: {e}")

print("\n작업 완료!")