import os
import csv
import datetime
import requests
from flask import Flask, render_template, request, jsonify
from bs4 import BeautifulSoup
import pandas as pd # Pandas 추가

app = Flask(__name__)

CRAWLED_DATA_DIR = 'crawled_data'
if not os.path.exists(CRAWLED_DATA_DIR):
    os.makedirs(CRAWLED_DATA_DIR)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/crawl', methods=['POST'])
def crawl():
    data = request.get_json()
    url = data.get('url')
    element_tag = data.get('element_tag')

    if not url or not element_tag:
        return jsonify({'error': 'URL과 추출할 HTML 태그(또는 CSS 선택자)를 모두 입력해주세요.'}), 400

    try:
        if not url.startswith(('http://', 'https://')):
            url = 'http://' + url
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        response.encoding = response.apparent_encoding
        soup = BeautifulSoup(response.text, 'html.parser')
        elements = soup.select(element_tag)

        if not elements:
            return jsonify({'message': '해당 태그/선택자에 맞는 요소를 찾을 수 없습니다.', 'data': [], 'filepath': None}), 200

        results = []
        for element in elements:
            text = element.get_text(strip=True)
            link = element.get('href') if element.name == 'a' else None
            if text:
                 results.append({'text': text, 'link': link if link else ''})

        if not results:
            return jsonify({'message': '추출할 내용이 있는 요소를 찾을 수 없습니다.', 'data': [], 'filepath': None}), 200

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_url_part = "".join(c if c.isalnum() else "_" for c in url.split('//')[-1].split('/')[0])[:50]
        filename = f'crawled_data_{safe_url_part}_{timestamp}.csv'
        filepath = os.path.join(CRAWLED_DATA_DIR, filename)

        with open(filepath, 'w', newline='', encoding='utf-8-sig') as csvfile:
            if results and isinstance(results[0], dict):
                fieldnames = results[0].keys()
            else:
                fieldnames = ['text']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for row_data in results:
                if isinstance(row_data, dict):
                    writer.writerow(row_data)
                else:
                    writer.writerow({'text': row_data})

        return jsonify({
            'message': f'크롤링 성공! {len(results)}개의 항목을 찾았습니다. 파일이 저장되었습니다.',
            'data': results[:10],
            'filepath': filepath
        }), 200

    except requests.exceptions.RequestException as e:
        return jsonify({'error': f'URL에 연결할 수 없습니다: {str(e)}'}), 500
    except Exception as e:
        return jsonify({'error': f'크롤링 중 오류 발생: {str(e)}'}), 500

# --- 시각화 관련 API 추가 ---
@app.route('/api/csv_files', methods=['GET'])
def get_csv_files():
    """crawled_data 폴더 내의 CSV 파일 목록을 반환합니다."""
    try:
        files = [f for f in os.listdir(CRAWLED_DATA_DIR) if f.endswith('.csv')]
        return jsonify({'csv_files': files})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/visualize', methods=['POST'])
def visualize_data():
    """요청에 따라 CSV 데이터를 분석하고 시각화용 데이터를 반환합니다."""
    try:
        payload = request.get_json()
        filename = payload.get('filename')
        analysis_type = payload.get('analysis_type')
        # chart_type = payload.get('chart_type') # 프론트에서 Plotly로 직접 핸들링

        if not filename:
            return jsonify({'error': 'CSV 파일명이 필요합니다.'}), 400
        
        filepath = os.path.join(CRAWLED_DATA_DIR, filename)
        if not os.path.exists(filepath):
            return jsonify({'error': f'{filename} 파일을 찾을 수 없습니다.'}), 404

        df = pd.read_csv(filepath)

        # 현재는 'text' 컬럼이 있다고 가정합니다. 실제 CSV 구조에 맞게 수정 필요.
        if 'text' not in df.columns:
            return jsonify({'error': "'text' 컬럼이 CSV 파일에 존재하지 않습니다."}), 400
        
        # NaN 값을 빈 문자열로 대체 (text 컬럼에 대해)
        df['text'] = df['text'].fillna('')


        if analysis_type == 'keyword_frequency':
            keywords_str = payload.get('keywords', '')
            if not keywords_str:
                return jsonify({'error': '키워드를 입력해주세요.'}), 400
            
            keywords = [kw.strip() for kw in keywords_str.lower().split(',') if kw.strip()]
            
            frequencies = {}
            for kw in keywords:
                # 각 키워드에 대해 전체 텍스트에서 등장 횟수 계산 (대소문자 구분 없이)
                # 여기서는 간단히 각 행의 'text' 필드에 키워드가 포함되어 있는지 여부로 빈도를 계산하거나,
                # 혹은 전체 텍스트를 합쳐서 계산할 수 있습니다.
                # 예제: 각 키워드가 포함된 행의 수 (더 정확한 빈도 계산은 NLP 기술 필요)
                # frequencies[kw] = df['text'].str.lower().str.contains(kw, case=False).sum()
                
                # 좀 더 직접적인 키워드 카운트 (하나의 큰 텍스트로 합쳐서)
                all_text_lower = " ".join(df['text'].astype(str)).lower()
                frequencies[kw] = all_text_lower.count(kw)


            x_values = list(frequencies.keys())
            y_values = list(frequencies.values())
            
            return jsonify({
                'x_values': x_values,
                'y_values': y_values,
                'title': f"'{filename}' 파일 키워드 빈도"
            })

        # --- 다른 분석 유형들 추후 추가 ---
        # elif analysis_type == 'time_series':
        #     # 시간 관련 컬럼이 필요. 예: 'timestamp' 컬럼
        #     if 'timestamp' not in df.columns:
        #         return jsonify({'error': "'timestamp' 컬럼이 CSV 파일에 존재하지 않습니다."}), 400
        #     # 시간 데이터 처리 로직 ...
        #     # 예: df['timestamp'] = pd.to_datetime(df['timestamp'])
        #     # grouped_data = df.groupby(df['timestamp'].dt.date)['some_value_column'].sum()
        #     # x_values = grouped_data.index.strftime('%Y-%m-%d').tolist()
        #     # y_values = grouped_data.values.tolist()
        #     pass # 실제 구현 필요

        else:
            return jsonify({'error': '지원하지 않는 분석 유형입니다.'}), 400

    except pd.errors.EmptyDataError:
        return jsonify({'error': f'{filename} 파일이 비어있거나 유효한 CSV 파일이 아닙니다.'}), 400
    except Exception as e:
        return jsonify({'error': f'데이터 처리 중 오류 발생: {str(e)}'}), 500


if __name__ == '__main__':
    app.run(debug=True, port=5100)