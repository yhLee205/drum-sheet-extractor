import os
import cv2
import yt_dlp
from flask import Flask, render_template_string, request, send_file, jsonify
from PIL import Image

app = Flask(__name__)
UPLOAD_FOLDER = 'static/sheets'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# [버전 관리 변수] v1.0.4로 명시하여 Render 빌드 완료 시 식별되도록 설정
APP_VERSION = "v1.0.4"
BUILD_DATE = "2026-06-07 20:50"

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>드럼 악보 우회형 원스톱 캡처기</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <style>
        body { font-family: 'Malgun Gothic', sans-serif; padding: 15px; background: #f5f5f5; margin: 0; }
        .container { max-width: 700px; margin: 0 auto; background: white; padding: 20px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); position: relative; }
        .version-badge { position: absolute; top: 15px; right: 20px; background: #e0e0e0; color: #555; padding: 4px 8px; border-radius: 6px; font-size: 11px; font-weight: bold; }
        .input-group { display: flex; gap: 10px; margin-bottom: 10px; margin-top: 15px; }
        input[type="text"] { flex: 1; padding: 12px; font-size: 16px; border: 1px solid #ddd; border-radius: 8px; box-sizing: border-box; }
        .btn { padding: 12px 20px; color: white; border: none; border-radius: 8px; font-size: 15px; font-weight: bold; cursor: pointer; }
        .btn-green { background: #4CAF50; }
        .btn-blue { width: 100%; padding: 15px; background: #2196F3; font-size: 16px; margin-bottom: 10px; }
        .btn-orange { width: 100%; padding: 15px; background: #FF5722; font-size: 16px; margin-top: 10px; }
        .status-msg { font-weight: bold; color: #555; margin-bottom: 15px; font-size: 14px; }
        .loading { display: none; text-align: center; font-weight: bold; color: #e91e63; margin: 15px 0; }
        .preview-container { width: 100%; position: relative; margin: 15px 0; background: black; overflow: hidden; border-radius: 8px; display: none; }
        #previewImg { width: 100%; display: block; }
        .guide-box { position: absolute; left: 2%; right: 2%; border: 2px solid red; pointer-events: none; box-sizing: border-box; }
        .range-group { background: #f9f9f9; padding: 15px; border-radius: 8px; margin-bottom: 15px; border: 1px solid #e0e0e0; display: none; }
        .range-group label { display: block; font-weight: bold; margin-bottom: 5px; font-size: 14px; color: #333; }
        .range-group input[type="range"] { width: 100%; margin-bottom: 15px; }
        .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: 10px; margin-top: 20px; }
        .sheet-card { border: 2px solid #2196F3; border-radius: 6px; overflow: hidden; background: #fff; position: relative; }
        .sheet-card img { width: 100%; display: block; }
        .btn-delete { position: absolute; top: 5px; right: 5px; background: rgba(255,0,0,0.8); color: white; border: none; border-radius: 4px; padding: 3px 6px; font-size: 11px; cursor: pointer; }
    </style>
</head>
<body>
    <div class="container">
        <div class="version-badge" title="빌드 시간: {{ build_date }}">{{ app_version }}</div>
        <h2>🥁 유튜브 악보 원스톱 추출 파이프라인</h2>
        
        <div class="input-group">
            <input type="text" id="ytUrl" placeholder="유튜브 악보 영상 주소를 입력하세요">
            <button class="btn btn-green" onclick="processPipeline()">1. 영상 파이프라인 가동</button>
        </div>
        <div class="loading" id="loading">🎬 우회 다운로드 파이프라인 가동 중... (약 20~40초 소요)</div>
        <div id="status" class="status-msg">유튜브 링크를 입력해 주세요.</div>

        <div class="range-group" id="controlPanel">
            <label id="lblTime">🎬 현재 영상 위치 (초): 0초</label>
            <input type="range" id="timeSlider" min="0" max="100" value="0" oninput="seekVideo()">

            <label>📐 캡처 높이 조절 (% 지점)</label>
            <label id="lblYStart" style="font-weight:normal; color:#666;">시작 높이: 55%</label>
            <input type="range" id="yStart" min="0" max="100" value="55" oninput="updateGuideLine()">
            
            <label id="lblYEnd" style="font-weight:normal; color:#666;">끝 높이: 97%</label>
            <input type="range" id="yEnd" min="0" max="100" value="97" oninput="updateGuideLine()">
        </div>

        <div class="preview-container" id="previewContainer">
            <img id="previewImg" src="">
            <div class="guide-box" id="guideBox"></div>
        </div>

        <button class="btn btn-blue" id="capBtn" style="display:none;" onclick="captureCurrentFrame()">📸 이 장면 악보로 저장</button>
        <div class="grid" id="resultGrid"></div>
        <button class="btn btn-orange" id="pdfBtn" style="display:none;" onclick="generatePDF()">📄 저장한 악보 A4 PDF로 다운로드</button>
    </div>

    <script>
        let duration = 0;
        let capturedCount = 0;
        let savedImages = [];

        async function processPipeline() {
            const url = document.getElementById('ytUrl').value;
            if(!url) return alert('유튜브 주소를 입력해 주세요.');

            document.getElementById('loading').style.display = 'block';
            document.getElementById('status').innerText = "유튜브 보안망 우회 다운로드 중...";
            
            const response = await fetch('/pipeline-download', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url: url })
            });
            const data = await response.json();
            document.getElementById('loading').style.display = 'none';

            if(data.success) {
                duration = data.duration;
                document.getElementById('timeSlider').max = Math.floor(duration);
                document.getElementById('status').innerText = `파이프라인 연동 성공! 총 길이: ${Math.floor(duration)}초`;
                
                document.getElementById('controlPanel').style.display = 'block';
                document.getElementById('previewContainer').style.display = 'block';
                document.getElementById('capBtn').style.display = 'block';
                
                seekVideo();
            } else {
                document.getElementById('status').innerText = "파이프라인 에러";
                alert('추출 실패: ' + data.error);
            }
        }

        async function seekVideo() {
            const sec = document.getElementById('timeSlider').value;
            document.getElementById('lblTime').innerText = `🎬 현재 영상 위치 (초): ${sec}초`;

            const response = await fetch(`/get-frame?sec=${sec}`);
            const blob = await response.blob();
            const imgUrl = window.URL.createObjectURL(blob);
            document.getElementById('previewImg').src = imgUrl;
            updateGuideLine();
        }

        function updateGuideLine() {
            const yStart = document.getElementById('yStart').value;
            const yEnd = document.getElementById('yEnd').value;
            document.getElementById('lblYStart').innerText = `시작 높이: ${yStart}%`;
            document.getElementById('lblYEnd').innerText = `끝 높이: ${yEnd}%`;

            const guideBox = document.getElementById('guideBox');
            guideBox.style.top = yStart + '%';
            guideBox.style.height = (yEnd - yStart) + '%';
        }

        async function captureCurrentFrame() {
            const sec = document.getElementById('timeSlider').value;
            const yStart = document.getElementById('yStart').value;
            const yEnd = document.getElementById('yEnd').value;

            const response = await fetch('/capture', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ sec: sec, y_start: yStart, y_end: yEnd, count: capturedCount })
            });
            const data = await response.json();

            if(data.success) {
                savedImages.push(data.path);
                const grid = document.getElementById('resultGrid');
                const card = document.createElement('div');
                card.className = 'sheet-card';
                card.id = `sheet_${capturedCount}`;
                card.innerHTML = `
                    <button class="btn-delete" onclick="deleteCard(${capturedCount}, '${data.path}')">삭제</button>
                    <img src="/${data.path}?t=${new Date().getTime()}">
                `;
                grid.appendChild(card);
                capturedCount++;
                document.getElementById('pdfBtn').style.display = 'block';
            }
        }

        function deleteCard(id, path) {
            document.getElementById(`sheet_${id}`).remove();
            savedImages = savedImages.filter(item => item !== path);
            if(savedImages.length === 0) document.getElementById('pdfBtn').style.display = 'none';
        }

        function generatePDF() {
            if(savedImages.length === 0) return;
            fetch('/make-pdf', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ images: savedImages })
            })
            .then(response => response.blob())
            .then(blob => {
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = "drum_sheets_pipeline.pdf";
                document.body.appendChild(a);
                a.click();
                a.remove();
            });
        }
    </script>
</body>
</html>
"""

@app.route('/')
def home():
    return render_template_string(HTML_TEMPLATE, app_version=APP_VERSION, build_date=BUILD_DATE)

@app.route('/pipeline-download', methods=['POST'])
def pipeline_download():
    data = request.json
    url = data.get('url')
    video_path = 'uploaded_video.mp4'
    
    if os.path.exists(video_path):
        try: os.remove(video_path)
        except: pass

    # [핵심] 클라우드 봇 차단 필터를 무력화하는 전용 클라이언트 우회 옵션 세팅
    ydl_opts = {
        'format': 'bestvideo[ext=mp4][height<=480]+bestaudio[ext=m4a]/best[ext=mp4][height<=480]',
        'outtmpl': video_path,
        'quiet': True,
        'noplaylist': True,
        # 유튜브 검문소를 우회하기 위한 모바일 클라이언트 위장 헤더 파이프라인
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Mobile Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
        }
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    duration = total_frames / fps if fps > 0 else 0
    cap.release()
    
    for f in os.listdir(UPLOAD_FOLDER):
        try: os.remove(os.path.join(UPLOAD_FOLDER, f))
        except: pass
        
    return jsonify({'success': True, 'duration': duration})

@app.route('/get-frame', methods=['GET'])
def get_frame():
    sec = float(request.args.get('sec', 0))
    cap = cv2.VideoCapture('uploaded_video.mp4')
    fps = cap.get(cv2.CAP_PROP_FPS)
    cap.set(cv2.CAP_PROP_POS_FRAMES, int(fps * sec))
    ret, frame = cap.read()
    cap.release()
    if ret:
        frame_resized = cv2.resize(frame, (854, 480))
        _, img_encoded = cv2.imencode('.jpg', frame_resized)
        return img_encoded.tobytes(), 200, {'Content-Type': 'image/jpeg'}
    return '실패', 400

@app.route('/capture', methods=['POST'])
def capture():
    data = request.json
    sec = float(data.get('sec'))
    y_start = float(data.get('y_start')) / 100.0
    y_end = float(data.get('y_end')) / 100.0
    count = data.get('count')
    
    cap = cv2.VideoCapture('uploaded_video.mp4')
    fps = cap.get(cv2.CAP_PROP_FPS)
    cap.set(cv2.CAP_PROP_POS_FRAMES, int(fps * sec))
    ret, frame = cap.read()
    cap.release()
    if ret:
        h, w, _ = frame.shape
        roi = frame[int(h*y_start):int(h*y_end), int(w*0.02):int(w*0.98)]
        path = f"{UPLOAD_FOLDER}/sheet_{count}.png"
        cv2.imwrite(path, roi)
        return jsonify({'success': True, 'path': path})
    return jsonify({'success': False})

@app.route('/make-pdf', methods=['POST'])
def make_pdf():
    data = request.json
    images_paths = data.get('images', [])
    a4_w, a4_h = 2480, 3508
    margin = 100
    pdf_pages = []
    current_page = Image.new("RGB", (a4_w, a4_h), "white")
    current_y = margin

    for path in sorted(images_paths):
        if not os.path.exists(path): continue
        img = Image.open(path)
        img_w, img_h = img.size
        target_w = a4_w - (margin * 2)
        target_h = int(img_h * (target_w / img_w))
        img_resized = img.resize((target_w, target_h), Image.Resampling.LANCZOS)
        
        if current_y + target_h + 50 > a4_h - margin:
            pdf_pages.append(current_page)
            current_page = Image.new("RGB", (a4_w, a4_h), "white")
            current_y = margin
            
        current_page.paste(img_resized, (margin, current_y))
        current_y += target_h + 50

    pdf_pages.append(current_page)
    pdf_output = "static/final_sheets.pdf"
    pdf_pages[0].save(pdf_output, "PDF", save_all=True, append_images=pdf_pages[1:])
    return send_file(pdf_output, as_attachment=True)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
