from flask import Flask, request, jsonify
from flask_cors import CORS # flask-CORS 임포트
import requests
from bs4 import BeautifulSoup
import logging

# 로깅 설정 (터미널에 로그를 출력합니다)
logging.basicConfig(level=logging.INFO)

app = Flask(__name__)
CORS(app) # 모든 출처에서의 요청을 허용합니다. 특정 출처만 허용하려면 CORS(app, resources={r"/crawl/*": {"origins": "http://localhost:xxxx"}}) 와 같이 설정할 수 있습니다.

# 웹 크롤링을 수행하는 함수
def perform_crawl(target_url):
    """
    지정된 URL에서 웹페이지 제목과 첫 번째 H1 태그 내용을 크롤링합니다.
    Args:
        target_url (str): 크롤링할 웹페이지의 URL입니다.
    Returns:
        dict: 크롤링 결과 또는 오류 메시지를 담은 딕셔너리입니다.
    """
    results = []
    app.logger.info(f"'{target_url}' 크롤링 시작") # 어떤 URL을 크롤링하는지 로그로 남깁니다.

    headers = { # 웹사이트에서 봇으로 인식하지 않도록 일반적인 브라우저 헤더 정보를 추가합니다.
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    try:
        # 웹페이지에 GET 요청을 보냅니다. timeout은 10초로 설정합니다.
        response = requests.get(target_url, headers=headers, timeout=10)
        # HTTP 오류 코드가 발생하면 예외를 발생시킵니다 (예: 404 Not Found, 500 Internal Server Error).
        response.raise_for_status()

        # BeautifulSoup 객체를 생성하여 HTML을 파싱합니다. 'lxml' 파서를 사용합니다.
        soup = BeautifulSoup(response.content, 'lxml') # response.text 대신 response.content를 사용하면 인코딩 문제를 줄일 수 있습니다.

        # 웹페이지 제목을 찾습니다.
        title_tag = soup.find('title')
        if title_tag and title_tag.string: # .string으로 태그 내부의 텍스트만 가져옵니다.
            results.append({"type": "페이지 제목", "content": title_tag.string.strip()})
        else:
            results.append({"type": "페이지 제목", "content": "찾을 수 없음"})

        # 첫 번째 H1 태그를 찾습니다.
        h1_tag = soup.find('h1')
        if h1_tag and h1_tag.string:
            results.append({"type": "첫 번째 H1 태그", "content": h1_tag.string.strip()})
        else:
            # H1 태그가 없으면 다른 주요 제목 태그(H2)를 찾아봅니다.
            h2_tag = soup.find('h2')
            if h2_tag and h2_tag.string:
                 results.append({"type": "첫 번째 H2 태그", "content": h2_tag.string.strip()})
            else:
                results.append({"type": "주요 제목 태그", "content": "찾을 수 없음 (H1, H2)"})


        # 예시: 모든 p 태그의 텍스트 일부 가져오기 (처음 3개만)
        paragraphs = soup.find_all('p', limit=3) # p 태그를 최대 3개까지만 찾습니다.
        for i, p_tag in enumerate(paragraphs):
            if p_tag.string:
                 # 너무 긴 텍스트는 잘라서 보여줍니다.
                content_preview = p_tag.string.strip()[:100] + "..." if len(p_tag.string.strip()) > 100 else p_tag.string.strip()
                results.append({"type": f"문단 내용 #{i+1}", "content": content_preview})


        if not results:
            app.logger.warning(f"'{target_url}'에서 추출할 정보를 찾지 못했습니다.")
            return {"error": "정보를 찾을 수 없습니다."}

        app.logger.info(f"'{target_url}' 크롤링 성공. 결과: {results}")
        return {"data": results}

    except requests.exceptions.Timeout:
        app.logger.error(f"'{target_url}' 요청 시간 초과")
        return {"error": f"'{target_url}' 요청 시간이 초과되었습니다. (10초)"}
    except requests.exceptions.HTTPError as http_err:
        app.logger.error(f"'{target_url}' HTTP 오류 발생: {http_err}")
        return {"error": f"'{target_url}'에 접속 중 HTTP 오류가 발생했습니다: {http_err}"}
    except requests.exceptions.RequestException as req_err:
        app.logger.error(f"'{target_url}' 접속 오류: {req_err}")
        return {"error": f"'{target_url}'에 접속 중 오류가 발생했습니다: {req_err}"}
    except Exception as e:
        app.logger.error(f"'{target_url}' 크롤링 중 알 수 없는 오류: {e}", exc_info=True) # 상세 오류 정보 로깅
        return {"error": f"크롤링 중 알 수 없는 오류가 발생했습니다: {e}"}

# '/crawl' 경로로 POST 요청이 오면 이 함수를 실행합니다.
@app.route('/crawl', methods=['POST'])
def crawl_website_route():
    """
    클라이언트로부터 URL을 받아 크롤링을 수행하고 결과를 JSON으로 반환하는 라우트입니다.
    """
    # 클라이언트가 보낸 JSON 데이터를 가져옵니다.
    data = request.get_json()
    if not data or 'url' not in data:
        app.logger.warning("요청에 URL이 누락되었습니다.")
        return jsonify({"error": "요청 본문에 'url'이 포함되어야 합니다."}), 400 # 400 Bad Request 응답

    target_url = data['url']
    app.logger.info(f"크롤링 요청 수신: {target_url}")

    # URL 유효성 검사 (간단하게 http 또는 https로 시작하는지만 확인)
    if not (target_url.startswith('http://') or target_url.startswith('https://')):
        app.logger.warning(f"잘못된 URL 형식: {target_url}")
        return jsonify({"error": "잘못된 URL 형식입니다. 'http://' 또는 'https://'로 시작해야 합니다."}), 400

    crawl_result = perform_crawl(target_url)
    return jsonify(crawl_result)

# 이 스크립트가 직접 실행될 때 Flask 개발 서버를 실행합니다.
if __name__ == '__main__':
    # debug=True는 개발 중에만 사용하고, 실제 서비스 시에는 False로 변경하거나 제거해야 합니다.
    # host='0.0.0.0'은 로컬 네트워크의 다른 기기에서도 접속할 수 있게 합니다.
    app.run(host='0.0.0.0', port=5100, debug=True)
