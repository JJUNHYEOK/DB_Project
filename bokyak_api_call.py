import requests
import xml.etree.ElementTree as ET # XML 파싱용 (사용)
import json # JSON 파싱용 (비활성)
import mysql.connector
import math
import time
from datetime import datetime # 날짜 형식 변환 필요시 사용
import sys # 오류 출력을 위해 추가

# --- 설정 정보 ---
# TODO: 실제 정보로 변경하세요
API_KEY = "mw5FAlSoYntyhdiIHixZmVvItA1iKLbgjUH6E4xLyuiwaqgFPg8t1/00EyDB9eWg7u6vttwBAgG3M0Yjz8NzPg=="
API_BASE_URL = "http://apis.data.go.kr/1471000/DrbEasyDrugInfoService" # 서비스 URL
API_SERVICE_NAME = "getDrbEasyDrugList" # 요청 주소의 서비스 이름

DB_CONFIG = {
    'user': 'root',
    'password': '231014',
    'host': 'localhost',
    'database': 'bokYak_helper' # CREATE DATABASE로 만든 데이터베이스 이름
}

# 한번에 가져올 데이터 수 (API 제한 100에 맞춤)
NUM_OF_ROWS = 100 # API 제한에 맞춰 100으로 변경했습니다.
# 배치 삽입 단위 (DB 성능에 따라 조절)
BATCH_SIZE = 500

# API 응답 데이터 형식 선택 (XML로 설정)
RESPONSE_TYPE = 'xml' # API 호출 시 실제 사용할 타입 설정 (API 응답이 XML로 확인됨)

# --- 데이터베이스 연결 함수 ---
def get_db_connection():
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        print("Database connection successful.")
        return conn
    except mysql.connector.Error as err:
        print(f"Database connection error: {err}", file=sys.stderr) # 오류는 stderr로 출력
        # 오류 코드별 상세 메시지 출력
        if err.errno == 1045:
             print("Access denied: Check your DB_CONFIG username and password.", file=sys.stderr)
        elif err.errno == 2003:
             print("Can't connect to MySQL server: Check host, port, and if server is running.", file=sys.stderr)
        return None

# --- 데이터 삽입 함수 (배치 처리) ---
def insert_drugs_batch(conn, data):
    if not data:
        return

    cursor = conn.cursor()
    # INSERT 쿼리: 최종 테이블 구조에 맞춰 컬럼명과 %s 개수, 순서가 정확해야 합니다.
    # howtouse로 이름 변경된 것을 반영했습니다.
    # 추가된 public_date, update_date, tablet_image_info 컬럼을 포함했습니다.
    sql = """
    INSERT INTO drugs (
        item_code, product_name, company_name, efficacy, howtouse, warning_warning,
        precautions, interactions, side_effects, storage, public_date, update_date,
        tablet_image_info
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    try:
        cursor.executemany(sql, data)
        conn.commit()
        print(f"Inserted {len(data)} records.")
    except mysql.connector.Error as err:
        print(f"Error inserting data: {err}", file=sys.stderr) # 오류는 stderr로 출력
        print(f"MySQL Error Code: {err.errno}", file=sys.stderr)
        # TODO: 어떤 데이터 때문에 오류가 났는지 디버깅을 위해 data 변수의 내용 일부를 로깅하거나 출력할 수 있습니다.
        # print("Problematic batch data sample:", data[:5], file=sys.stderr) # 오류난 데이터의 앞부분 5개만 출력
        conn.rollback() # 오류 발생 시 롤백하여 중복 삽입 방지
    except Exception as e:
         print(f"An unexpected error occurred during batch insertion: {e}", file=sys.stderr)
         conn.rollback()
    finally:
        cursor.close()

# --- API 호출 및 파싱 함수 ---
def fetch_data_from_api(page_no, num_of_rows):
    url = f"{API_BASE_URL}/{API_SERVICE_NAME}"
    params = {
        'serviceKey': API_KEY,
        'pageNo': page_no,
        'numOfRows': num_of_rows, # NUM_OF_ROWS 설정값 사용 (100으로 변경됨)
        '_type': 'xml', # API 응답이 XML로 오는 것이 확인되었으므로 'xml'로 설정
        # TODO: 필수 검색 파라미터 추가. API 명세서에서 getDrbEasyDrugList 서비스의 필수 파라미터 이름 확인.
        # 전체 목록 조회를 위해 가장 넓은 범위의 검색 조건 사용 (예: '제품명'에 한글 자음/모음)
        'item_name': '가' # 예시: 제품명에 '가'가 포함된 모든 약 검색. API 명세서에서 실제 파라미터 이름 확인 필수!
        # 만약 필수 파라미터 이름이 'item_name'이 아니거나, '가'로 검색해도 전체가 안 나온다면 수정해야 합니다.
        # API 명세서에 '목록 조회'를 위한 특정 파라미터 가이드가 있을 수 있습니다.
    }

    try:
        # 요청 URL 확인 (디버깅 용도)
        # print(f"Requesting URL: {url} with params: {params}") # 디버깅 시 활성화

        response = requests.get(url, params=params)
        response.raise_for_status() # HTTP 오류 발생 시 예외 발생 (4xx, 5xx 등)

        # --- API 응답 상태 코드와 내용 확인을 위한 코드 (디버깅 완료 후 삭제 또는 주석 처리) ---
        print(f"API Response Status Code for page {page_no}: {response.status_code}", file=sys.stderr)
        print(f"API Response Text for page {page_no} (first 500 chars):\n{response.text[:500]}", file=sys.stderr)
        # --- 코드 추가 끝 ---


        items = []
        total_count = 0 # total_count 초기화 (첫 페이지에서만 제대로 옴)

        # API 응답 형식에 맞춰 XML 파싱 로직 활성화 및 수정
        if params['_type'] == 'xml': # 'xml'로 설정했으므로 이 블록 실행
            try:
                root = ET.fromstring(response.text)

                # TODO: API 응답 구조에 맞춰 item 목록이 있는 경로와 totalCount 경로를 수정해야 합니다.
                # API 명세서의 응답 예시를 보고 정확한 경로를 확인하세요.
                # 예시: <response><body><items><item>...</item>...</items></body><header>...<totalCount>...</totalCount>...</header></response>
                item_list_path = './/body/items/item' # 실제 아이템 태그 경로 확인 (이전 응답 구조 기반 수정)
                total_count_path = './/body/totalCount' # 실제 totalCount 태그 경로 확인 (이전 응답 구조 기반 수정)

                # totalCount 추출
                total_count_elem = root.find(total_count_path)
                # totalCount가 존재하고 숫자인 경우에만 추출
                if total_count_elem is not None and total_count_elem.text and total_count_elem.text.isdigit():
                     total_count = int(total_count_elem.text)
                else:
                     # resultCode 확인 (오류 응답일 가능성)
                     result_code_elem = root.find('.//header/resultCode') # 실제 resultCode 태그 경로 확인
                     result_code = result_code_elem.text if result_code_elem is not None else 'N/A'
                     result_msg_elem = root.find('.//header/resultMsg') # 실제 resultMsg 태그 경로 확인
                     result_msg = result_msg_elem.text if result_msg_elem is not None else 'N/A'
                     print(f"Warning: Could not extract totalCount from XML response on page {page_no}. resultCode: {result_code}, resultMsg: {result_msg}", file=sys.stderr)
                     # totalCount 추출 실패 시 데이터가 없다고 간주하고 반환
                     return [], 0


                # 아이템 데이터 파싱
                # totalCount가 0보다 큰 경우에만 items를 찾도록 조건 추가 가능
                if total_count > 0:
                     for item_elem in root.findall(item_list_path):
                          try:
                            # --- 실제 API 응답의 태그 이름으로 수정했습니다 (대소문자 일치). API 명세서 확인 필수! ---
                            item_code_raw = item_elem.findtext('itemSeq', default=None) # <itemSeq> 사용

                            # --- item_code가 None인지 확인하고 건너뛰는 로직 ---
                            if item_code_raw is None or str(item_code_raw).strip() == '':
                                # 제품명 태그 이름도 실제 API 응답에 맞게 수정 (itemName)
                                item_name_for_log = item_elem.findtext('itemName', default='N/A') # <itemName> 사용
                                print(f"Warning: Skipping record due to missing item_code on page {page_no}. Item Name: {item_name_for_log}", file=sys.stderr)
                                continue # 현재 레코드를 건너뛰고 다음 레코드로 이동
                            item_code = item_code_raw.strip() # 양쪽 공백 제거
                            # --- 로직 끝 ---

                            # --- 나머지 필드들도 실제 API 응답의 태그 이름으로 수정했습니다 (대소문자 일치). API 명세서 확인 필수! ---
                            product_name = item_elem.findtext('itemName', default=None) # <itemName> 사용
                            company_name = item_elem.findtext('entpName', default=None) # <entpName> 사용
                            efficacy = item_elem.findtext('efcyQesitm', default=None) # <efcyQesitm> 사용 (문항1)
                            howtouse_val = item_elem.findtext('useMethodQesitm', default=None) # <useMethodQesitm> 사용 (문항2)
                            warning_warning = item_elem.findtext('precautionWarnQesitm', default=None) # 예상 태그 이름. API 명세서 확인 필수!
                            precautions = item_elem.findtext('atpnQesitm', default=None) # 예상 태그 이름. API 명세서 확인 필수!
                            interactions = item_elem.findtext('intrcQesitm', default=None) # 예상 태그 이름. API 명세서 확인 필수!
                            side_effects = item_elem.findtext('seQesitm', default=None) # 예상 태그 이름. API 명세서 확인 필수!
                            storage = item_elem.findtext('depositMethodQesitm', default=None) # 예상 태그 이름. API 명세서 확인 필수!
                            # 공개일자, 수정일자, 낱알이미지 태그 이름도 예상되는 이름으로 수정 (API 명세서 확인 필수!)
                            public_date_str = item_elem.findtext('openDate', default=None) # 예상 태그 이름
                            update_date_str = item_elem.findtext('updateDate', default=None) # 예상 태그 이름
                            tablet_image_info = item_elem.findtext('drugImage', default=None) # 예상 태그 이름

                            # TODO: 날짜 문자열이 'YYYYMMDD' 형태라면 DATE 타입 변환 필요
                            # API 응답이 'YYYYMMDD' 형식으로 온다고 가정하고 변환 로직 추가
                            public_date = None
                            if public_date_str and str(public_date_str).isdigit() and len(str(public_date_str)) == 8:
                                try:
                                    public_date = datetime.strptime(str(public_date_str), "%Y%m%d").strftime("%Y-%m-%d")
                                except ValueError:
                                    print(f"Warning: Invalid public_date format: {public_date_str} on page {page_no}.", file=sys.stderr)
                                except Exception as ve:
                                     print(f"Warning: Unexpected error converting public_date {public_date_str}: {ve} on page {page_no}.", file=sys.stderr)


                            update_date = None
                            if update_date_str and str(update_date_str).isdigit() and len(str(update_date_str)) == 8:
                                 try:
                                     update_date = datetime.strptime(str(update_date_str), "%Y%m%d").strftime("%Y-%m-%d")
                                 except ValueError:
                                     print(f"Warning: Invalid update_date format: {update_date_str} on page {page_no}.", file=sys.stderr)
                                 except Exception as ve:
                                      print(f"Warning: Unexpected error converting update_date {update_date_str}: {ve} on page {page_no}.", file=sys.stderr)


                            # DB에 삽입할 데이터 형태로 가공 (튜플). 순서는 INSERT 쿼리와 일치해야 합니다.
                            # item_code, product_name, company_name, efficacy, howtouse, warning_warning, precautions, interactions, side_effects, storage, public_date, update_date, tablet_image_info
                            items.append((
                                item_code, product_name, company_name, efficacy, howtouse_val, # howtouse_val 변수 사용
                                warning_warning, precautions, interactions, side_effects, storage,
                                public_date, update_date, tablet_image_info
                            ))
                          except Exception as parse_err:
                            print(f"Error parsing individual item data on page {page_no}: {parse_err}", file=sys.stderr)
                            # 특정 아이템 파싱 오류는 건너뛰고 계속 진행

            except ET.ParseError as e:
                 print(f"XML parsing error on page {page_no}: {e}", file=sys.stderr)
                 # 디버깅을 위해 응답 내용 전체 또는 일부 출력 가능
                 # print(f"Response text start: {response.text[:500]}...", file=sys.stderr)
                 return [], 0 # 파싱 오류 시 빈 리스트 반환
            except Exception as e:
                 print(f"An unexpected error occurred during XML parsing setup on page {page_no}: {e}", file=sys.stderr)
                 return [], 0


        elif params['_type'] == 'json':
            # TODO: JSON 파싱을 사용하려면 params['_type']을 'json'으로 바꾸고 이 부분을 활성화/수정하세요.
            # 현재는 XML 응답 확인 후 XML 파싱을 사용하도록 설정되어 있습니다.
            # 필요 없으면 이 elif 블록 전체를 삭제해도 됩니다.
            print(f"Warning: JSON parsing block active but _type is 'xml' on page {page_no}. Check RESPONSE_TYPE setting.", file=sys.stderr)
            return [], 0 # JSON 선택했는데 XML 받으면 파싱하지 않고 종료
            # try:
            #      data = response.json()
            #      # ... (JSON 파싱 로직, totalCount 추출, items_data 확인, item 파싱, howtouse 변수 사용 등) ...
            #      # ... item_code None 체크 로직도 JSON 파싱 안에 추가했었음 ...
            #      return items, total_count
            # except json.JSONDecodeError as e:
            #      print(f"JSON parsing error on page {page_no}: {e}", file=sys.stderr)
            #      print(f"Response text start: {response.text[:500]}...", file=sys.stderr)
            #      return [], 0
            # except Exception as e:
            #      print(f"An unexpected error occurred during JSON parsing setup on page {page_no}: {e}", file=sys.stderr)
            #      return [], 0

        else: # _type이 'xml' 또는 'json'이 아닌 경우
             print(f"Error: Invalid _type parameter '{params['_type']}'. Must be 'xml' or 'json'.", file=sys.stderr)
             return [], 0


        # API 호출 성공, 파싱 결과 반환
        return items, total_count

    except requests.exceptions.RequestException as e:
        print(f"API request failed for page {page_no}: {e}", file=sys.stderr)
        # print(f"Response status code: {e.response.status_code if e.response else 'N/A'}", file=sys.stderr) # 상태 코드 출력
        # print(f"Response text: {e.response.text[:500] if e.response else 'N/A'}", file=sys.stderr) # 응답 내용 일부 출력
        # API 호출 오류 시 해당 페이지만 실패로 처리하고 빈 리스트 반환. 전역 total_count는 변경 안 함.
        return [], 0 # 오류 발생 시 빈 리스트와 0 반환 (total_count는 첫 페이지 외에는 무의미)
    except Exception as e:
        print(f"An unexpected error occurred during API call setup for page {page_no}: {e}", file=sys.stderr)
        return [], 0


# --- 메인 로딩 로직 ---
def main():
    conn = get_db_connection()
    if not conn:
        print("Database connection failed. Exiting.", file=sys.stderr)
        return

    total_count = 0
    current_page = 1
    all_data_collected = [] # 배치 삽입을 위한 데이터 임시 저장 리스트

    print("Starting data fetching and loading...")

    # 첫 페이지 호출로 totalCount 확인
    print(f"Fetching initial page {current_page} to get total count...")
    # fetch_data_from_api 내부에서 API_KEY, NUM_OF_ROWS, RESPONSE_TYPE 등을 사용
    items, initial_total_count = fetch_data_from_api(current_page, NUM_OF_ROWS)

    # 첫 페이지 호출 실패 또는 데이터 없음
    # totalCount가 0이거나, items가 비어있거나, fetch_data_from_api에서 오류로 []를 반환한 경우
    # items가 None일 경우는 fetch_data_from_api에서 처리하지 않도록 수정했으므로 items가 빈 리스트인지 확인
    if not items and initial_total_count == 0: # 데이터가 없거나 첫 페이지 가져오기 실패 (items가 빈 리스트, total_count=0)
        print("No data found from API or failed to get data/total count from the first page.", file=sys.stderr)
        conn.close()
        return
    
    # total_count가 0이 아니지만 items가 비어있는 경우 (totalCount는 있는데 첫 페이지 데이터 파싱 실패 등)도 고려
    if initial_total_count > 0 and not items:
         print(f"Failed to parse data from the first page despite totalCount = {initial_total_count} > 0.", file=sys.stderr)
         # 디버깅 프린트 (상태 코드/본문)를 통해 원인 파악 필요
         conn.close()
         return


    total_count = initial_total_count # 첫 페이지에서 얻은 전체 결과 수 사용

    total_pages = math.ceil(total_count / NUM_OF_ROWS)
    print(f"Total items found: {total_count}, Total pages: {total_pages}")

    # 첫 페이지 데이터 처리 (fetch_data_from_api에서 이미 items 리스트로 반환됨)
    all_data_collected.extend(items)
    print(f"Collected {len(items)} items from page {current_page}.")

    # 나머지 페이지 순회
    # total_pages가 0보다 크고, 이미 첫 페이지 처리를 했으므로 두 번째 페이지부터 시작
    for page_num in range(current_page + 1, total_pages + 1):
        print(f"Fetching page {page_num} / {total_pages}...")

        # API 호출 제한 방지를 위해 필요시 잠시 대기
        # time.sleep(0.5) # 예: 0.5초 대기 (API 정책 확인 후 조절)

        # fetch_data_from_api 내부에서 파라미터 설정 (RESPONSE_TYPE 사용)
        items, _ = fetch_data_from_api(page_num, NUM_OF_ROWS) # total_count는 첫 페이지 외에는 사용 안 함

        if items: # 해당 페이지에서 데이터가 정상적으로 파싱된 경우 (빈 리스트가 아닐 경우)
            all_data_collected.extend(items)
            # print(f"Collected {len(items)} items from page {page_num}. Total collected in buffer: {len(all_data_collected)}") # 버퍼 현황 로그

            # 배치 삽입 시점 체크
            if len(all_data_collected) >= BATCH_SIZE:
                print(f"Inserting batch of {len(all_data_collected)} records...")
                insert_drugs_batch(conn, all_data_collected)
                all_data_collected = [] # 배치 삽입 후 리스트 비우기
        else:
             # 해당 페이지에서 API 호출 오류나 파싱 오류가 발생한 경우 (fetch_data_from_api에서 이미 워닝 출력)
             # 해당 페이지의 데이터는 수집되지 않음
             pass # 오류 메시지는 fetch_data_from_api에서 이미 출력

    # 마지막 남은 데이터 배치 삽입
    if all_data_collected:
        print(f"Inserting final batch of {len(all_data_collected)} records...")
        insert_drugs_batch(conn, all_data_collected)

    conn.close()
    print("Data loading finished. Database connection closed.")

if __name__ == "__main__":
    main()