from flask import Flask, render_template, request, abort
import mysql.connector
import sys
from datetime import datetime # 필요시 날짜 변환용
import json 
# 기존 DB 연결 함수를 가져옵니다.
# 만약 기존 스크립트(load_drugs.py 등)에 있다면 해당 함수를 복사해오거나 import 하세요.

# --- 기존 DB 연결 함수 (load_drugs.py 등에서 복사해왔다고 가정) ---
DB_CONFIG = {
    'user': 'root',
    'password': '231014',
    'host': 'localhost',
    'database': 'bokYak_helper',
    'port': 3306,
    'charset': 'utf8mb4'
}

def get_db_connection():
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        # print("Database connection successful.") # 웹 서비스에서는 콘솔 출력 대신 로깅 사용
        return conn
    except mysql.connector.Error as err:
        print(f"Database connection error: {err}", file=sys.stderr)
        if err.errno == 1045:
             print("Access denied: Check your DB_CONFIG username and password.", file=sys.stderr)
        elif err.errno == 2003:
             print("Can't connect to MySQL server: Check host, port, and if server is running.", file=sys.stderr)
        return None
# --- DB 연결 함수 끝 ---


app = Flask(__name__)

# 메인 페이지: 검색 폼을 보여줍니다.
@app.route('/')
def index():
    # 아주 간단한 HTML 템플릿을 문자열로 바로 정의합니다.
    # 실제 서비스에서는 별도의 .html 파일로 분리하는 것이 일반적입니다.
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>💊 복약했수다 💊</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; }
            form { margin-bottom: 20px; }
            table { border-collapse: collapse; width: 100%; }
            th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
            th { background-color: #f2f2f2; }
        </style>
    </head>
    <body>
        <h1>💊 복약했수다 💊</h1>
        <form action="/search" method="get">
            <label for="query">약 이름 또는 품목코드 검색:</label>
            <input type="text" id="query" name="query" required>
            <button type="submit">검색</button>
        </form>

        <h2>검색 결과</h2>
        {% if drugs %}
            <table>
                <thead>
                    <tr>
                        <th>품목코드</th>
                        <th>제품명</th>
                        <th>업체명</th>
                        <th>효능/효과</th>
                        <th>용법/용량</th>
                        </tr>
                </thead>
                <tbody>
                    {% for drug in drugs %}
                    <tr>
                        <td>{{ drug.item_code }}</td>
                        <td><a href="/drug/{{ drug.item_code }}">{{ drug.product_name }}</a></td>
                        <td>{{ drug.company_name }}</td>
                        <td>{{ drug.efficacy }}</td>
                        <td>{{ drug.howtouse }}</td>
                        </tr>
                    {% endfor %}
                </tbody>
            </table>
        {% elif query %} {# query 변수는 검색이 시도되었으나 결과가 없을 때만 존재 #}
            <p>'{{ query }}'에 대한 검색 결과가 없습니다.</p>
        {% endif %}
    </body>
    </html>
    """
    # 처음 로드될 때는 drugs 목록이나 query가 없으므로 검색 폼만 보입니다.
    return render_template('index.html', drugs=None, query=None)

# 검색 요청을 처리하는 라우트
@app.route('/search', methods=['GET'])
def search():
    query = request.args.get('query', '') # GET 요청에서 'query' 파라미터 값을 가져옵니다.

    if not query:
         # 검색어가 없으면 검색 폼이 있는 메인 페이지로 리다이렉트하거나 메시지 표시
        return render_template('index.html', drugs=None, query="")
    conn = get_db_connection()
    drugs = []
    if conn:
        cursor = conn.cursor(dictionary=True) # 결과를 딕셔너리 형태로 받도록 설정
        try:
            # TODO: SQL Injection 방지를 위해 사용자 입력 값을 직접 쿼리 문자열에 넣지 마세요!
            # %s 플레이스홀더와 두 번째 인자로 튜플/리스트를 사용해야 합니다.

            # 예시: 품목코드 또는 제품명으로 검색 (대소문자 구분 없이 검색되도록 LIKE와 LOWER/UPPER 사용 권장)
            # MySQL은 기본적으로 대소문자 구분을 안하지만, 설정에 따라 달라질 수 있습니다.
            # %s 플레이스홀더 사용 예시
            search_term = f"%{query}%" # '포함' 검색을 위해 % 와일드카드 사용

            sql = """
            SELECT item_code, product_name, company_name, efficacy, howtouse
            FROM drugs
            WHERE item_code = %s OR product_name LIKE %s OR efficacy LIKE %s
            """
            search_params = (query, search_term, search_term)
            cursor.execute(sql, (query, search_term, search_term)) # 사용자 입력 값을 튜플로 전달

              # --- 디버깅 출력 코드 추가 ---
            print(f"Executing SQL: {sql}", file=sys.stderr)
            print(f"With parameters: {search_params}", file=sys.stderr)
            # --- 디버깅 출력 코드 끝 ---

            drugs = cursor.fetchall() # 모든 결과 가져오기

        except mysql.connector.Error as err:
            print(f"Database query error: {err}", file=sys.stderr)
        except Exception as e:
            print(f"An unexpected error occurred during search: {e}", file=sys.stderr)
        finally:
            cursor.close()
            conn.close()

    # 검색 결과를 포함하여 메인 페이지 템플릿을 다시 렌더링합니다.
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>💊 복약했수다 💊</title>
         <style>
            body { font-family: Arial, sans-serif; margin: 20px; }
            form { margin-bottom: 20px; }
            table { border-collapse: collapse; width: 100%; }
            th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
            th { background-color: #f2f2f2; }
        </style>
    </head>
    <body>
        <h1>💊 복약했수다 💊</h1>
        <form action="/search" method="get">
            <label for="query">약 이름 또는 품목코드 검색:</label>
            <input type="text" id="query" name="query" value="{{ query | default('') }}" required> {# 이전에 검색했던 값 표시 #}
            <button type="submit">검색</button>
        </form>

        <h2>검색 결과</h2>
        {% if drugs %}
            <p>총 {{ drugs | length }} 건의 결과가 있습니다.</p> {# 결과 개수 표시 #}
            <table>
                <thead>
                    <tr>
                        <th>품목코드</th>
                        <th>제품명</th>
                        <th>업체명</th>
                        <th>효능/효과</th>
                        <th>용법/용량</th>
                        </tr>
                </thead>
                <tbody>
                    {% for drug in drugs %}
                    <tr>
                        <td>{{ drug.item_code }}</td>
                        <td><a href="/drug/{{ drug.item_code }}">{{ drug.product_name }}</a></td>
                        <td>{{ drug.company_name }}</td>
                        <td>{{ drug.efficacy }}</td>
                        <td>{{ drug.howtouse }}</td>
                        </tr>
                    {% endfor %}
                </tbody>
            </table>
        {% elif query %} {# drugs가 비어있고 query가 존재하는 경우 (검색 결과 없음) #}
            <p>'{{ query }}'에 대한 검색 결과가 없습니다.</p>
        {% endif %}
    </body>
    </html>
    """
    return render_template('index.html', drugs=drugs, query=query)

# 특정 약품의 상세 정보를 보여주는 라우트
@app.route('/drug/<item_code>')
def drug_detail(item_code): # URL에서 <item_code> 부분이 이 함수의 item_code 매개변수로 전달됩니다.
    print(f"Attempting to fetch details for item_code: {item_code}", file=sys.stderr) # 디버깅 출력

    conn = get_db_connection()
    drug = None # 약 정보를 저장할 변수

    if conn:
        cursor = conn.cursor(dictionary=True) # 결과를 딕셔너리 형태로 받도록 설정
        try:
            # item_code로 해당 약품의 모든 컬럼 정보를 조회
            # TODO: 필요한 모든 컬럼 이름을 SELECT 절에 명시적으로 나열하는 것이 좋습니다.
            # 예시: SELECT item_code, product_name, company_name, efficacy, howtouse, warning_warning, ... FROM drugs WHERE item_code = %s
            # 여기서는 예시로 일부 컬럼만 가져옵니다. 실제 필요한 모든 컬럼을 추가하세요.
            sql = """
            SELECT
                item_code, product_name, company_name, efficacy, howtouse,
                warning_warning, precautions, interactions, side_effects, storage,
                public_date, update_date, tablet_image_info
            FROM drugs
            WHERE item_code = %s
            """
            cursor.execute(sql, (item_code,)) # URL에서 받은 item_code 값을 튜플 형태로 전달

            drug = cursor.fetchone() # 결과는 하나이므로 fetchone() 사용

        except mysql.connector.Error as err:
            print(f"Database query error in drug_detail: {err}", file=sys.stderr)
        except Exception as e:
            print(f"An unexpected error occurred in drug_detail: {e}", file=sys.stderr)
        finally:
            if cursor: cursor.close()
            if conn: conn.close()

    # TODO: 다음 단계에서 이 부분에 상세 정보를 보여줄 HTML 템플릿 렌더링 코드를 작성합니다.
    # 지금은 데이터가 제대로 가져와지는지 확인하기 위해 간단하게 출력해보거나 딕셔너리를 문자열로 반환해봅니다.

    if drug:
        # 약 정보를 찾았을 경우
        print(f"Found drug details for {item_code}", file=sys.stderr) # 디버깅 출력
        # 임시로 찾은 약 정보를 문자열로 반환하여 브라우저에 표시 (JSON 형태로)
        return render_template('drug_detail.html', drug=drug) # 한글 깨짐 방지, 보기 좋게 들여쓰기

    else:
        # 해당 item_code의 약 정보를 찾지 못했을 경우
        print(f"No drug found for item_code: {item_code}", file=sys.stderr) # 디버깅 출력
        # 약을 찾지 못했다는 메시지 또는 404 페이지를 반환
        # Flask의 abort 함수를 사용하면 404 페이지를 쉽게 반환할 수 있습니다.
        # from flask import abort <- 위에 import 필요
        # abort(404, description="Drug not found")
        abort(404, description=f"Item Code {item_code} 에 해당하는 약품 정보를 찾을 수 없습니다.")

@app.route('/check_interactions', methods=['POST']) # POST 방식으로 요청을 받도록 설정
def check_interactions():
    # 웹 브라우저로부터 POST 요청으로 전달된 'item_codes' 이름의 체크박스 값 목록을 가져옵니다.
    # request.form.getlist('item_codes')는 선택된 모든 체크박스의 value(품목코드)를 리스트 형태로 반환합니다.
    selected_item_codes = request.form.getlist('item_codes')

    print(f"Received item codes for interaction check: {selected_item_codes}", file=sys.stderr) # 디버깅 출력

    if not selected_item_codes:
        # 만약 선택된 항목이 하나도 없다면
        print("No items selected for interaction check.", file=sys.stderr)
        # TODO: 사용자에게 선택하라는 메시지를 보여주는 페이지를 렌더링하거나, 검색 페이지로 리다이렉트
        # 지금은 간단한 메시지와 함께 400 상태 코드를 반환합니다.
        return "상호작용 확인할 약품을 하나 이상 선택해주세요.", 400 # Bad Request

    conn = get_db_connection()
    selected_drugs_data = [] # 선택된 약들의 정보를 저장할 리스트

    if conn:
        cursor = conn.cursor(dictionary=True) # 결과를 딕셔너리 형태로 받도록 설정
        try:
            # SQL 쿼리를 구성합니다. IN 절을 사용하여 여러 품목코드에 해당하는 약들을 한 번에 가져옵니다.
            # 선택된 품목코드 개수만큼 %s 플레이스홀더를 동적으로 만듭니다.
            placeholders = ', '.join(['%s'] * len(selected_item_codes)) # 예: 선택이 3개면 "%s, %s, %s" 문자열 생성

            # 상호작용 확인에 필요한 컬럼들만 선택합니다.
            sql = f"""
            SELECT item_code, product_name, warning_warning, precautions, interactions
            FROM drugs
            WHERE item_code IN ({placeholders})
            """ # IN 절에 동적으로 생성된 플레이스홀더 문자열 사용

            print(f"Executing interaction SQL: {sql}", file=sys.stderr) # 디버깅 출력: 실행될 SQL
            print(f"With parameters: {selected_item_codes}", file=sys.stderr) # 디버깅 출력: 전달될 파라미터 목록

            # SQL 실행. execute 메소드는 IN 절의 플레이스홀더 개수와 두 번째 인자(리스트/튜플)의 항목 개수가 일치할 때 자동으로 안전하게 처리합니다.
            cursor.execute(sql, selected_item_codes) # 선택된 품목코드 리스트를 그대로 전달

            selected_drugs_data = cursor.fetchall() # 해당 약들의 정보 모두 가져오기

            # TODO: 가져온 selected_drugs_data를 조합하여 상호작용 결과를 분석/가공합니다.
            # 가장 간단하게는 모든 약의 warning_warning, precautions, interactions 내용을 모아서 보여줄 수 있습니다.

        except mysql.connector.Error as err:
            print(f"Database query error in check_interactions: {err}", file=sys.stderr)
            # TODO: 사용자에게 데이터베이스 오류 발생을 알리는 페이지를 렌더링
            return "상호작용 정보를 가져오는 중 데이터베이스 오류가 발생했습니다.", 500 # Internal Server Error
        except Exception as e:
            print(f"An unexpected error occurred in check_interactions: {e}", file=sys.stderr)
            # TODO: 사용자에게 알 수 없는 오류 발생을 알리는 페이지를 렌더링
            return f"처리 중 예상치 못한 오류가 발생했습니다: {e}", 500 # Internal Server Error
        finally:
            if cursor: cursor.close()
            if conn: conn.close()

    # TODO: 다음 단계는 가져온 selected_drugs_data를 바탕으로
    # 상호작용 결과를 보여줄 HTML 템플릿을 렌더링하는 것입니다.
    # 지금은 데이터가 제대로 가져와지는지 확인하기 위해 임시로 JSON 형태로 반환합니다.

    print(f"Fetched data for {len(selected_drugs_data)} selected drugs.", file=sys.stderr) # 디버깅 출력
    # 가져온 약 정보 리스트를 JSON 형태로 브라우저에 반환 (보기 좋게 들여쓰기 적용)
    # import json 필요 (파일 상단에 추가)
    return render_template('interactions_result.html', selected_drugs=selected_drugs_data)

if __name__ == '__main__':
    # Flask 애플리케이션 실행 (디버그 모드 활성화 - 개발 시 유용)
    # host='0.0.0.0'으로 설정하면 외부 접속 허용 (주의!)
    app.run(debug=True, host='127.0.0.1', port=5000) # 기본 로컬호스트 5000번 포트 사용