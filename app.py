import os
import cv2
from flask import Flask, render_template_string, request, send_file, jsonify
from PIL import Image

app = Flask(__name__)
UPLOAD_FOLDER = 'static/sheets'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# [버전 관리 변수] v1.0.7로 명시하여 자라기 단계 탑재 확인
APP_VERSION = "v1.0.7"
BUILD_DATE = "2026-06-07 21:30"

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>드럼 악보 마스터 캡처기</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <style>
        body { font-family: 'Malgun Gothic', sans-serif; padding: 15px; background: #f5f5f5; margin: 0; }
        .container { max-width: 700px; margin: 0 auto; background: white; padding: 20px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); position: relative; }
        .version-badge { position: absolute; top: 15px; right: 20px; background: #e0e0e0; color: #555; padding: 4px 8px; border-radius: 6px; font-size: 11px; font-weight: bold; }
        
        .option-box { background: #f9f9f9; padding: 20px; border-radius: 10px; margin-top: 15px; margin-bottom: 20px; border: 1px solid #e2e8f0; }
        .option-title { font-size: 16px; font-weight: bold; margin-bottom: 10px; color: #2d3748; }
        
        .btn { width: 100%; padding: 14px; color: white; border: none; border-radius: 8px; font-size: 16px; font-weight: bold; cursor: pointer; display: block; text-align: center; box-sizing: border-box; }
        .btn-green { background: #4CAF50; }
        .btn-blue { background: #2196F3; }
        .btn-purple { background: #9c27b0; }
        .btn-orange { background: #FF5722; margin-top: 15px; }
        
        .status-msg { font-weight: bold; color: #4a5568; margin: 10px 0; font-size: 14px; }
        
        /* 공통 프리뷰 및 가이드선 레이아웃 */
        .preview-container { width: 100%; position: relative; margin: 15px 0; background: black; overflow: hidden; border-radius: 8px; display: none; }
        #previewImg { width: 100%; display: block; }
        .guide-box { position: absolute; left: 2%; right: 2%; border: 2px solid red; pointer-events: none; box-sizing: border-box; }
        
        .range-group { background: #f7fafc; padding: 15px; border-radius: 8px; margin-bottom: 15px; border: 1px solid #edf2f7; display: none; }
        .range-group label { display: block; font-weight: bold; margin-bottom: 5px; font-size: 14px; color: #4a5568; }
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
        <h2>🥁 드럼 악보 정밀 가공기 (v1.0.7)</h2>
        
        <div class="option-box">
            <div class="option-title">📸 옵션 1 : 화면 캡처 이미지들 한방에 크롭 변환</div>
            <input type="file" id="imageFiles" accept="image/*" multiple style="display:none;" onchange="uploadDirectImages()">
            <button class="btn btn-purple" onclick="document.getElementById('imageFiles').click()">캡처 이미지 파일들 일괄 선택 (다중 선택)</button>
        </div>

        <div class="option-box">
            <div class="option-title">🎬 옵션 2 : 영상 업로드 후 원하는 장면 지정 추출</div>
            <input type="file" id="videoFile" accept="video/*" style="display:none;" onchange="processVideoUpload()">
            <button class="btn btn-green" onclick="document.getElementById('videoFile').click()">드럼 연주 영상 파일 선택 (.mp4)</button>
        </div>

        <div id="status" class="status-msg">원하시는 옵션을 선택해 주세요.</div>

        <div class="range-group" id="controlPanel">
            <div id="videoTimeContainer" style="display:none;">
                <label id="lblTime">🎬 현재 영상 위치 (초): 0초</label>
                <input type="range" id="timeSlider" min="0" max="100" value="0" oninput="seekVideo()">
            </div>

            <label style="margin-top: 10px;">📐 악보 잘라내기(Crop) 범위 설정 (% 지점)</label>
            <label id="lblYStart" style="font-weight:normal; color:#666; font-size:13px;">시작 높이: 55%</label>
            <input type="range" id="yStart" min="0" max="100" value="55" oninput="updateGuideLine()">
            
            <label id="lblYEnd" style="font-weight:normal; color:#666; font-size:13px;">끝 높이: 97%</label>
            <input type="range" id="yEnd" min="0" max="100" value="97" oninput="updateGuideLine()">
            
            <button class="btn btn-blue" id="capBtn" onclick="captureCurrentFrame()" style="display:none;">📸 이 장면 악보 조각으로 저장</button>
            <button class="btn btn-purple" id="cropAllBtn" onclick="cropAndMergeImages()" style="display:none;">✂️ 설정한 범위로 모든 이미지 일괄 크롭 가공</button>
        </div>

        <div class="preview-container" id="previewContainer">
            <img id="previewImg" src="">
            <div class="guide-box" id="guideBox"></div>
        </div>
        
        <div class="grid" id="resultGrid"></div>
        
        <button class="btn btn-orange" id="pdfBtn" style="display:none;" onclick="generatePDF()">📄 A4 규격 완성형 PDF 다운로드</button>
    </div>

    <script>
        let duration = 0;
        let capturedCount = 0;
        let savedImages = [];
        let currentMode = ""; // "image" 또는 "video" 확인용 변수

        // --- 옵션 1 : 이미지 다중 업로드 처리 ---
        async function uploadDirectImages() {
            const fileInput = document.getElementById('imageFiles');
            if(fileInput.files.length === 0) return;

            document.getElementById('status').innerText = "이미지 원본 로드 중... 범위를 지정해 주세요.";
            resetGrid();
            currentMode = "image";

            const formData = new FormData();
            for(let i=0; i<fileInput.files.length; i++) {
                formData.append('images', fileInput.files[i]);
            }

            const response = await fetch('/upload-images', { method: 'POST', body: formData });
            const data = await response.json();

            if(data.success) {
                // 첫 번째 이미지 경로를 프리뷰 창에 띄워서 범위를 잡을 수 있게 가이드 제공
                document.getElementById('previewImg').src = "/" + data.first_image + "?t=" + new Date().getTime();
                
                document.getElementById('videoTimeContainer').style.display = 'none';
                document.getElementById('controlPanel').style.display = 'block';
                document.getElementById('previewContainer').style.display = 'block';
                document.getElementById('cropAllBtn').style.display = 'block';
                document.getElementById('capBtn').style.display = 'none';
                
                updateGuideLine();
            } else {
                alert('이미지 업로드 실패: ' + data.error);
            }
        }

        // [옵션 1 핵심] 사용자가 지정한 가이드라인 비율대로 서버가 이미지 전체를 도려냄
        async function cropAndMergeImages() {
            const yStart = document.getElementById('yStart').value;
            const yEnd = document.getElementById('yEnd').value;
            document.getElementById('status').innerText = "설정하신 범위대로 전체 이미지 크롭 가공 중...";

            const response = await fetch('/crop-all-images', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ y_start: yStart, y_end: yEnd })
            });
            const data = await response.json();

            if(data.success) {
                savedImages = data.paths;
                document.getElementById('status').innerText = `가공 완료! 총 ${data.paths.length}개의 정제된 악보 띠가 추출되었습니다.`;
                
                const grid = document.getElementById('resultGrid');
                grid.innerHTML = '';
                data.paths.forEach((path) => {
                    const card = document.createElement('div');
                    card.className = 'sheet-card';
                    card.innerHTML = `<img src="/${path}?t=${new Date().getTime()}">`;
                    grid.appendChild(card);
                });
                document.getElementById('pdfBtn').style.display = 'block';
            } else {
                alert('크롭 실패');
            }
        }

        // --- 옵션 2 : 비디오 연동 처리 ---
        async function processVideoUpload() {
            const fileInput = document.getElementById('videoFile');
            if(fileInput.files.length === 0) return;

            document.getElementById('status').innerText = "영상을 로드하고 있습니다...";
            resetGrid();
            currentMode = "video";

            const formData = new FormData();
            formData.append('video', fileInput.files[0]);

            const response = await fetch('/upload-video', { method: 'POST', body: formData });
            const data = await response.json();

            if(data.success) {
                duration = data.duration;
                document.getElementById('timeSlider').max = Math.floor(duration);
                document.getElementById('status').innerText = `영상 로드 성공! 원하는 타임의 범위를 캡처하세요.`;
                
                document.getElementById('videoTimeContainer').style.display = 'block';
                document.getElementById('controlPanel').style.display = 'block';
                document.getElementById('previewContainer').style.display = 'block';
                document.getElementById('capBtn').style.display = 'block';
                document.getElementById('cropAllBtn').style.display = 'none';
                
                seekVideo();
            } else {
                alert('영상 분석 실패: ' + data.error);
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

            const response = await fetch('/capture-video-frame', {
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

        function resetGrid() {
            document.getElementById('resultGrid').innerHTML = '';
            document.getElementById('pdfBtn').style.display = 'none';
            document.getElementById('controlPanel').style.display = 'none';
            document.getElementById('previewContainer').style.display = 'none';
            savedImages = [];
            capturedCount = 0;
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
                a.download = "drum_sheet_processed.pdf";
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

# --- 옵션 1 전용 처리 파트 ---
@app.route('/upload-images', methods=['POST'])
def upload_images():
    if 'images' not in request.files:
        return jsonify({'success': False, 'error': '파일이 없습니다.'})
    
    files = request.files.getlist('images')
    
    # 임시 세션 클리어 및 업로드 이미지 정렬 처리
    for f in os.listdir(UPLOAD_FOLDER):
        try: os.remove(os.path.join(UPLOAD_FOLDER, f))
        except: pass
        
    # 원본 파일명 순서대로 정확하게 정렬하여 저장
    sorted_files = sorted(files, key=lambda x: x.filename)
    for idx, file in enumerate(sorted_files):
        path = f"{UPLOAD_FOLDER}/raw_{idx}.png"
        file.save(path)
        
    return jsonify({'success': True, 'first_image': f"{UPLOAD_FOLDER}/raw_0.png"})

@app.route('/crop-all-images', methods=['POST'])
def crop_all_images():
    data = request.json
    y_start = float(data.get('y_start')) / 100.0
    y_end = float(data.get('y_end')) / 100.0
    
    raw_files = sorted([f for f in os.listdir(UPLOAD_FOLDER) if f.startswith('raw_')])
    processed_paths = []
    
    for idx, filename in enumerate(raw_files):
        img_path = os.path.join(UPLOAD_FOLDER, filename)
        img = cv2.imread(img_path)
        if img is None: continue
        
        h, w, _ = img.shape
        # 설정한 비율대로 순식간에 이미지 전체 가공 조절
        roi = img[int(h*y_start):int(h*y_end), int(w*0.02):int(w*0.98)]
        
        out_path = f"{UPLOAD_FOLDER}/processed_{idx}.png"
        cv2.imwrite(out_path, roi)
        processed_paths.append(out_path)
        
    return jsonify({'success': True, 'paths': processed_paths})

# --- 옵션 2 전용 처리 파트 ---
@app.route('/upload-video', methods=['POST'])
def upload_video():
    if 'video' not in request.files:
        return jsonify({'success': False, 'error': '파일이 없습니다.'})
    
    file = request.files['video']
    video_path = 'uploaded_video.mp4'
    file.save(video_path)
    
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    duration = total_frames / fps if fps > 0 else 0
    cap.release()
    
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

@app.route('/capture-video-frame', methods=['POST'])
def capture_video_frame():
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
