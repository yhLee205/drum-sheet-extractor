import os
import cv2
import yt_dlp
from flask import Flask, render_template_string, request, send_file, jsonify
from PIL import Image

app = Flask(__name__)
UPLOAD_FOLDER = 'static/sheets'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# 아이패드 최적화: 유튜브 플레이어와 범위 슬라이더 연동 화면
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>드럼 악보 원클릭 캡처기</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <style>
        body { font-family: 'Malgun Gothic', sans-serif; padding: 15px; background: #f5f5f5; margin: 0; }
        .container { max-width: 700px; margin: 0 auto; background: white; padding: 20px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
        .input-group { display: flex; gap: 10px; margin-bottom: 15px; }
        input[type="text"] { flex: 1; padding: 12px; font-size: 16px; border: 1px solid #ddd; border-radius: 8px; box-sizing: border-box; }
        .btn { padding: 12px 20px; color: white; border: none; border-radius: 8px; font-size: 15px; font-weight: bold; cursor: pointer; }
        .btn-green { background: #4CAF50; }
        .btn-blue { width: 100%; padding: 15px; background: #2196F3; font-size: 16px; margin: 15px 0; }
        .btn-orange { width: 100%; padding: 15px; background: #FF5722; font-size: 16px; display: none; }
        
        /* 비디오뷰 및 가이드선 배치 */
        .video-box { width: 100%; position: relative; background: black; border-radius: 8px; overflow: hidden; display: none; margin-bottom: 15px; }
        video { width: 100%; display: block; }
        .guide-box { position: absolute; left: 2%; right: 2%; border: 2px solid red; pointer-events: none; box-sizing: border-box; }
        
        .range-group { background: #f9f9f9; padding: 15px; border-radius: 8px; margin-bottom: 15px; border: 1px solid #e0e0e0; display: none; }
        .range-group label { display: block; font-weight: bold; margin-bottom: 5px; font-size: 14px; }
        .range-group input[type="range"] { width: 100%; margin-bottom: 10px; }
        
        .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: 10px; margin-top: 20px; }
        .sheet-card { border: 2px solid #2196F3; border-radius: 6px; overflow: hidden; background: #fff; position: relative; }
        .sheet-card img { width: 100%; display: block; }
        .btn-delete { position: absolute; top: 5px; right: 5px; background: rgba(255,0,0,0.8); color: white; border: none; border-radius: 4px; padding: 3px 6px; font-size: 11px; cursor: pointer; }
        .loading { display: none; text-align: center; font-weight: bold; color: #666; margin: 10px 0; }
    </style>
</head>
<body>
    <div class="container">
        <h2>🥁 유튜브 드럼 악보 캡처기 (iPad 지원)</h2>
        
        <div class="input-group">
            <input type="text" id="ytUrl" placeholder="유튜브 영상 주소를 붙여넣으세요">
            <button class="btn btn-green" onclick="loadYoutubeVideo()">영상 불러오기</button>
        </div>
        <div class="loading" id="loading">🎬 유튜브 스트림 분석 중... (약 5~10초 소요)</div>

        <div class="video-box" id="videoBox">
            <video id="mainVideo" controls playsinline crossorigin="anonymous"></video>
            <div class="guide-box" id="guideBox"></div>
        </div>

        <div class="range-group" id="rangePanel">
            <label>📐 캡처 높이 조절 (% 지점)</label>
            <label id="lblYStart" style="font-weight:normal; color:#666; font-size:13px;">시작 높이: 55%</label>
            <input type="range" id="yStart" min="0" max="100" value="55" oninput="updateGuideLine()">
            
            <label id="lblYEnd" style="font-weight:normal; color:#666; font-size:13px;">끝 높이: 97%</label>
            <input type="range" id="yEnd" min="0" max="100" value="97" oninput="updateGuideLine()">
        </div>

        <button class="btn btn-blue" id="capBtn" style="display:none;" onclick="captureCurrentFrame()">📸 현재 재생 장면 악보로 저장</button>
        
        <div class="grid" id="resultGrid"></div>
        
        <button class="btn btn-orange" id="pdfBtn" onclick="generatePDF()">📄 저장한 악보 A4 PDF로 다운로드</button>
    </div>

    <script>
        let capturedCount = 0;
        let savedImages = [];
        let currentStreamUrl = "";

        // 유튜브 링크로부터 안전한 재생 주소를 파싱해 옴
        async function loadYoutubeVideo() {
            const url = document.getElementById('ytUrl').value;
            if(!url) return alert('유튜브 주소를 입력해 주세요.');

            document.getElementById('loading').style.display = 'block';
            document.getElementById('videoBox').style.display = 'none';
            document.getElementById('rangePanel').style.display = 'none';
            document.getElementById('capBtn').style.display = 'none';

            const response = await fetch('/stream-url', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url: url })
            });
            const data = await response.json();
            document.getElementById('loading').style.display = 'none';

            if(data.success) {
                currentStreamUrl = data.stream_url;
                const video = document.getElementById('mainVideo');
                video.src = data.stream_url;
                
                document.getElementById('videoBox').style.display = 'block';
                document.getElementById('rangePanel').style.display = 'block';
                document.getElementById('capBtn').style.display = 'block';
                
                video.load();
                updateGuideLine();
            } else {
                alert('영상 주소 추출 실패: ' + data.error);
            }
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

        // 아이패드에서 보던 시간대의 화면을 서버가 즉각 스냅샷 크롭 가공
        async function captureCurrentFrame() {
            const video = document.getElementById('mainVideo');
            const currentTime = video.currentTime;
            const yStart = document.getElementById('yStart').value;
            const yEnd = document.getElementById('yEnd').value;

            const response = await fetch('/capture-frame', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    stream_url: currentStreamUrl,
                    sec: currentTime,
                    y_start: yStart,
                    y_end: yEnd,
                    count: capturedCount
                })
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
            } else {
                alert('캡처에 실패했습니다.');
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
                a.download = "drum_sheets.pdf";
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
    return render_template_string(HTML_TEMPLATE)

@app.route('/stream-url', methods=['POST'])
def get_stream_url():
    data = request.json
    url = data.get('url')
    
    # yt-dlp를 이용해 영상은 안 받되 브라우저 로딩용 스트림 재생 주소만 신속 가공
    ydl_opts = {
        'format': 'bestvideo[ext=mp4][height<=720]/best[ext=mp4]',
        'quiet': True,
        'noplaylist': True
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return jsonify({'success': True, 'stream_url': info['url']})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/capture-frame', methods=['POST'])
def capture_frame():
    data = request.json
    stream_url = data.get('stream_url')
    sec = float(data.get('sec'))
    y_start = float(data.get('y_start')) / 100.0
    y_end = float(data.get('y_end')) / 100.0
    count = data.get('count')
    
    cap = cv2.VideoCapture(stream_url)
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
