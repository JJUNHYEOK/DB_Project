from flask import Flask, render_template, request, abort
import mysql.connector
import sys
from datetime import datetime 
import json 

NUM_OF_ROWS = 10 

#DB 연결
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
        return conn
    except mysql.connector.Error as err:
        print(f"Database connection error: {err}", file=sys.stderr)
        if err.errno == 1045:
             print("Access denied: Check your DB_CONFIG username and password.", file=sys.stderr)
        elif err.errno == 2003:
             print("Can't connect to MySQL server: Check host, port, and if server is running.", file=sys.stderr)
        return None



app = Flask(__name__)

# 메인 페이지
@app.route('/')
def home():
    return render_template('home.html')

@app.route('/interactions_info')
def interactions_info():
    return render_template('interactions_info.html')



# 검색 요청을 처리하는 라우트
@app.route('/search', methods=['GET'])
def search():
    query = request.args.get('query', '') 
    try:
        page = int(request.args.get('page', 1)) 
        per_page = int(request.args.get('per_page', NUM_OF_ROWS)) 

        if page < 1:
            page = 1
   
        if per_page < 1 or per_page > 1000:
             per_page = NUM_OF_ROWS

    except (ValueError, TypeError):
     
        page = 1
        per_page = NUM_OF_ROWS

 
    offset = (page - 1) * per_page

 
    if not query:
      
         return render_template('index.html', drugs=[], query=None, total_count=0, page=1, per_page=NUM_OF_ROWS)


    conn = get_db_connection()
    drugs = [] 
    total_count = 0 

    if conn:
        cursor = conn.cursor(dictionary=True) 
        try:
            search_term = f"%{query}%"
            
            search_params = (query, search_term, search_term) 

            
            count_sql = """
            SELECT COUNT(*) as total
            FROM drugs
            WHERE item_code = %s OR product_name LIKE %s OR efficacy LIKE %s
            """
            print(f"Executing count SQL: {count_sql}", file=sys.stderr) 
            print(f"With parameters: {search_params}", file=sys.stderr) 
            cursor.execute(count_sql, search_params)
            count_result = cursor.fetchone() 
            if count_result:
                total_count = count_result['total'] 

            #  현재 페이지에 보여줄 결과를 가져오는 쿼리 (LIMIT/OFFSET 사용)
            if total_count > 0:
                sql = f"""
                SELECT item_code, product_name, company_name, efficacy, howtouse 
                FROM drugs
                WHERE item_code = %s OR product_name LIKE %s OR efficacy LIKE %s
                LIMIT %s OFFSET %s 
                """
               
                execute_params = search_params + (per_page, offset)

                print(f"Executing data SQL: {sql}", file=sys.stderr) 
                print(f"With parameters: {execute_params}", file=sys.stderr) 
                cursor.execute(sql, execute_params)

                drugs = cursor.fetchall() 

        except mysql.connector.Error as err:
            print(f"Database query error in search: {err}", file=sys.stderr)
            return "검색 중 데이터베이스 오류가 발생했습니다.", 500
        except Exception as e:
            print(f"An unexpected error occurred in search: {e}", file=sys.stderr)
            return f"검색 처리 중 오류가 발생했습니다: {e}", 500
        finally:
            if cursor: cursor.close()
            if conn: conn.close()

    # 검색 결과 (현재 페이지), 전체 결과 수, 현재 페이지 번호, 페이지당 항목 수를 템플릿에 전달
    return render_template('index.html', drugs=drugs, query=query,
                           total_count=total_count, page=page, per_page=per_page)

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
def drug_detail(item_code): 
    print(f"Attempting to fetch details for item_code: {item_code}", file=sys.stderr) 

    conn = get_db_connection()
    drug = None 

    if conn:
        cursor = conn.cursor(dictionary=True) 
        try:
            sql = """
            SELECT
                item_code, product_name, company_name, efficacy, howtouse,
                warning_warning, precautions, interactions, side_effects, storage,
                public_date, update_date, tablet_image_info
            FROM drugs
            WHERE item_code = %s
            """
            cursor.execute(sql, (item_code,)) 

            drug = cursor.fetchone() 

        except mysql.connector.Error as err:
            print(f"Database query error in drug_detail: {err}", file=sys.stderr)
        except Exception as e:
            print(f"An unexpected error occurred in drug_detail: {e}", file=sys.stderr)
        finally:
            if cursor: cursor.close()
            if conn: conn.close()


    if drug:
        # 약 정보를 찾았을 경우
        print(f"Found drug details for {item_code}", file=sys.stderr)
        return render_template('drug_detail.html', drug=drug)

    else:
        # 해당 item_code의 약 정보를 찾지 못했을 경우
        print(f"No drug found for item_code: {item_code}", file=sys.stderr)
        abort(404, description=f"Item Code {item_code} 에 해당하는 약품 정보를 찾을 수 없습니다.")

@app.route('/check_interactions', methods=['POST']) 
def check_interactions():
    selected_item_codes = request.form.getlist('item_codes')

    print(f"Received item codes for interaction check: {selected_item_codes}", file=sys.stderr) 

    if not selected_item_codes:
        print("No items selected for interaction check.", file=sys.stderr)
        return "상호작용 확인할 약품을 하나 이상 선택해주세요.", 400 

    conn = get_db_connection()
    selected_drugs_data = []

    if conn:
        cursor = conn.cursor(dictionary=True)
        try:
    
            placeholders = ', '.join(['%s'] * len(selected_item_codes)) 

            sql = f"""
            SELECT item_code, product_name, warning_warning, precautions, interactions
            FROM drugs
            WHERE item_code IN ({placeholders})
            """ 

            print(f"Executing interaction SQL: {sql}", file=sys.stderr)
            print(f"With parameters: {selected_item_codes}", file=sys.stderr) 

            cursor.execute(sql, selected_item_codes)

            selected_drugs_data = cursor.fetchall() 

        except mysql.connector.Error as err:
            print(f"Database query error in check_interactions: {err}", file=sys.stderr)
            return "상호작용 정보를 가져오는 중 데이터베이스 오류가 발생했습니다.", 500
        except Exception as e:
            print(f"An unexpected error occurred in check_interactions: {e}", file=sys.stderr)
            return f"처리 중 예상치 못한 오류가 발생했습니다: {e}", 500 
        finally:
            if cursor: cursor.close()
            if conn: conn.close()

    print(f"Fetched data for {len(selected_drugs_data)} selected drugs.", file=sys.stderr)
    return render_template('interactions_result.html', selected_drugs=selected_drugs_data)

if __name__ == '__main__':
    # Flask 애플리케이션 실행 (디버그 모드 활성화 - 개발 시 유용)
    # host='0.0.0.0'으로 설정하면 외부 접속 허용 (주의!)
    app.run(debug=True, host='127.0.0.1', port=5000)