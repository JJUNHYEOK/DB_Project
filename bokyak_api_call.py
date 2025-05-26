import requests
import xml.etree.ElementTree as ET # XML 파싱용 (사용)
import json # JSON 파싱용 (비활성)
import mysql.connector
import math
import time
from datetime import datetime # 날짜 형식 변환 필요시 사용
import sys # 오류 출력을 위해 추가

API_KEY = "mw5FAlSoYntyhdiIHixZmVvItA1iKLbgjUH6E4xLyuiwaqgFPg8t1/00EyDB9eWg7u6vttwBAgG3M0Yjz8NzPg=="
API_BASE_URL = "http://apis.data.go.kr/1471000/DrbEasyDrugInfoService" # 서비스 URL
API_SERVICE_NAME = "getDrbEasyDrugList" # 요청 주소의 서비스 이름

DB_CONFIG = {
    'user': 'root',
    'password': '231014',
    'host': 'localhost',
    'database': 'bokYak_helper' # CREATE DATABASE로 만든 데이터베이스 이름
}


NUM_OF_ROWS = 100
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
        'numOfRows': num_of_rows, 
        '_type': 'xml', # API 응답이 XML로 오는 것이 확인되었으므로 'xml'로 설정
        'item_name': '가' 
    }

    try:

        response = requests.get(url, params=params)
        response.raise_for_status() 

        print(f"API Response Status Code for page {page_no}: {response.status_code}", file=sys.stderr)
        print(f"API Response Text for page {page_no} (first 500 chars):\n{response.text[:500]}", file=sys.stderr)



        items = []
        total_count = 0 

        if params['_type'] == 'xml':
            try:
                root = ET.fromstring(response.text)
                item_list_path = './/body/items/item' 
                total_count_path = './/body/totalCount' 

                # totalCount 추출
                total_count_elem = root.find(total_count_path)
                if total_count_elem is not None and total_count_elem.text and total_count_elem.text.isdigit():
                     total_count = int(total_count_elem.text)
                else:
                     result_code_elem = root.find('.//header/resultCode') # 실제 resultCode 태그 경로 확인
                     result_code = result_code_elem.text if result_code_elem is not None else 'N/A'
                     result_msg_elem = root.find('.//header/resultMsg') # 실제 resultMsg 태그 경로 확인
                     result_msg = result_msg_elem.text if result_msg_elem is not None else 'N/A'
                     print(f"Warning: Could not extract totalCount from XML response on page {page_no}. resultCode: {result_code}, resultMsg: {result_msg}", file=sys.stderr)
                     return [], 0

                if total_count > 0:
                     for item_elem in root.findall(item_list_path):
                          try:
                            item_code_raw = item_elem.findtext('itemSeq', default=None) 

                            if item_code_raw is None or str(item_code_raw).strip() == '':
                                item_name_for_log = item_elem.findtext('itemName', default='N/A') 
                                print(f"Warning: Skipping record due to missing item_code on page {page_no}. Item Name: {item_name_for_log}", file=sys.stderr)
                                continue # 현재 레코드를 건너뛰고 다음 레코드로 이동
                            item_code = item_code_raw.strip() # 양쪽 공백 제거
                            product_name = item_elem.findtext('itemName', default=None) # <itemName> 사용
                            company_name = item_elem.findtext('entpName', default=None) # <entpName> 사용
                            efficacy = item_elem.findtext('efcyQesitm', default=None) # <efcyQesitm> 사용 (문항1)
                            howtouse_val = item_elem.findtext('useMethodQesitm', default=None) # <useMethodQesitm> 사용 (문항2)
                            warning_warning = item_elem.findtext('precautionWarnQesitm', default=None) # 예상 태그 이름. API 명세서 확인 필수!
                            precautions = item_elem.findtext('atpnQesitm', default=None) # 예상 태그 이름. API 명세서 확인 필수!
                            interactions = item_elem.findtext('intrcQesitm', default=None) # 예상 태그 이름. API 명세서 확인 필수!
                            side_effects = item_elem.findtext('seQesitm', default=None) # 예상 태그 이름. API 명세서 확인 필수!
                            storage = item_elem.findtext('depositMethodQesitm', default=None) # 예상 태그 이름. API 명세서 확인 필수!
                            public_date_str = item_elem.findtext('openDate', default=None) # 예상 태그 이름
                            update_date_str = item_elem.findtext('updateDate', default=None) # 예상 태그 이름
                            tablet_image_info = item_elem.findtext('drugImage', default=None) # 예상 태그 이름

                            # TODO: 날짜 문자열이 'YYYYMMDD' 형태라면 DATE 타입 변환 필요
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

                            items.append((
                                item_code, product_name, company_name, efficacy, howtouse_val, # howtouse_val 변수 사용
                                warning_warning, precautions, interactions, side_effects, storage,
                                public_date, update_date, tablet_image_info
                            ))
                          except Exception as parse_err:
                            print(f"Error parsing individual item data on page {page_no}: {parse_err}", file=sys.stderr)

            except ET.ParseError as e:
                 print(f"XML parsing error on page {page_no}: {e}", file=sys.stderr)
                 return [], 0 
            except Exception as e:
                 print(f"An unexpected error occurred during XML parsing setup on page {page_no}: {e}", file=sys.stderr)
                 return [], 0


        elif params['_type'] == 'json':
            print(f"Warning: JSON parsing block active but _type is 'xml' on page {page_no}. Check RESPONSE_TYPE setting.", file=sys.stderr)
            return [], 0 # JSON 선택했는데 XML 받으면 파싱하지 않고 종료
        else: # _type이 'xml' 또는 'json'이 아닌 경우
             print(f"Error: Invalid _type parameter '{params['_type']}'. Must be 'xml' or 'json'.", file=sys.stderr)
             return [], 0


        # API 호출 성공, 파싱 결과 반환
        return items, total_count

    except requests.exceptions.RequestException as e:
        print(f"API request failed for page {page_no}: {e}", file=sys.stderr)
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
    if not items and initial_total_count == 0: # 데이터가 없거나 첫 페이지 가져오기 실패 (items가 빈 리스트, total_count=0)
        print("No data found from API or failed to get data/total count from the first page.", file=sys.stderr)
        conn.close()
        return
    
    if initial_total_count > 0 and not items:
         print(f"Failed to parse data from the first page despite totalCount = {initial_total_count} > 0.", file=sys.stderr)
         # 디버깅 프린트 (상태 코드/본문)를 통해 원인 파악 필요
         conn.close()
         return


    total_count = initial_total_count

    total_pages = math.ceil(total_count / NUM_OF_ROWS)
    print(f"Total items found: {total_count}, Total pages: {total_pages}")

    all_data_collected.extend(items)
    print(f"Collected {len(items)} items from page {current_page}.")

    for page_num in range(current_page + 1, total_pages + 1):
        print(f"Fetching page {page_num} / {total_pages}...")

        items, _ = fetch_data_from_api(page_num, NUM_OF_ROWS) # total_count는 첫 페이지 외에는 사용 안 함

        if items: 
            all_data_collected.extend(items)
    
            if len(all_data_collected) >= BATCH_SIZE:
                print(f"Inserting batch of {len(all_data_collected)} records...")
                insert_drugs_batch(conn, all_data_collected)
                all_data_collected = []
        else:
             pass
    # 마지막 남은 데이터 배치 삽입
    if all_data_collected:
        print(f"Inserting final batch of {len(all_data_collected)} records...")
        insert_drugs_batch(conn, all_data_collected)

    conn.close()
    print("Data loading finished. Database connection closed.")

if __name__ == "__main__":
    main()