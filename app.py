import os
import cv2
import yt_dlp
from flask import Flask, render_template_string, request, send_file, jsonify
from PIL import Image
from skimage.metrics import structural_similarity as ssim

app = Flask(__name__)
UPLOAD_FOLDER = 'static/sheets'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>드럼 악보 자동 추출기</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <style>
        body { font-family: 'Malgun Gothic', sans-serif; padding: 20px; background: #f5f5f5; margin: 0; }
        .container { max-width: 800px; margin: 0 auto; background: white; padding: 20px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
        input[type="text"] { width: 100%; padding: 12px; font-size: 16px; border: 1px solid #ddd; border-radius: 8px; box-sizing: border-box; margin-bottom: 15px; }
        .range-group { background: #eee; padding: 15px; border-radius: 8px; margin-bottom: 15px; }
        .range-group label { display: block; font-weight: bold; margin-bottom: 5px; font-size: 14px; }
        .range-group input { width: 100%; margin-bottom: 10px; }
        button { width: 100%; padding: 15px; background: #4CAF50; color: white; border: none; border-radius: 8px; font-size: 16px; font-weight: bold; cursor: pointer; }
        .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 15px; margin-top: 20px; }
        .sheet-card { border: 2px solid #eee; border-radius: 8px; overflow: hidden; position: relative; background: #fff; cursor: pointer; }
        .sheet-card.selected { border-color: #2196F3; box-shadow: 0 0 10px rgba(33,150,243,0.5); }
        .sheet-card img { width: 100%; display: block; }
        .checkbox { position: absolute; top: 10px; left: 10px; transform: scale(1.5); }
        #pdfBtn { background: #FF5722; margin-top: 20px; display: none; }
        .loading { display: none; text-align: center; font-weight: bold; color: #666; margin: 20px 0; }
    </style>
</head>
<body>
    <div class="container">
        <h2>🥁 유튜브 악보 자동 변환기 (누구나 사용 가능)</h2>
        <input type="text" id="url" placeholder="유튜브 악보 영상 링크를 붙여넣으세요">
        
        <div class="range-group">
            <label>📐 캡처 범위 조절 (영상 상단 기준 비율 %)</label>
            <label id="lblYStart">악보 시작 높이: 55% 지점</label>
            <input type="range" id="yStart" min="0" max="100" value="55" oninput="updateLabel()">
            <label id="lblYEnd">악보 끝 높이: 97% 지점</label>
            <input type="range" id="yEnd" min="0" max="100" value="97" oninput="updateLabel()">
        </div>

        <button onclick="analyzeVideo()">1. 악보 자동 추출 시작</button>
        <div class="loading" id="loading">🎬 유튜브 영상을 분석하고 있습니다... (약 1분 소요)</div>
        <div class="grid" id="resultGrid"></div>
        <button id="pdfBtn" onclick="generatePDF()">2. 선택한 악보 A4 PDF로 저장</button>
    </div>

    <script>
        let fetchedImages = [];
        function updateLabel() {
            document.getElementById('lblYStart').innerText = `악보 시작 높이: ${document.getElementById('yStart').value}% 지점`;
            document.getElementById('lblYEnd').innerText = `악보 끝 높이: ${document.getElementById('yEnd').value}% 지점`;
        }

        async function analyzeVideo() {
            const url = document.getElementById('url').value;
            const yStart = document.getElementById('yStart').value;
            const yEnd = document.getElementById('yEnd').value;
            if(!url) return alert('유튜브 링크를 입력해주세요.');
            if(parseInt(yStart) >= parseInt(yEnd)) return alert('시작 높이가 끝 높이보다 낮아야 합니다.');
            
            document.getElementById('loading').style.display = 'block';
            document.getElementById('resultGrid').innerHTML = '';
            document.getElementById('pdfBtn').style.display = 'none';

            const response = await fetch('/analyze', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url: url, y_start: yStart, y_end: yEnd })
            });
            
            const data = await response.json();
            document.getElementById('loading').style.display = 'none';

            if(data.success) {
                fetchedImages = data.images;
                const grid = document.getElementById('resultGrid');
                data.images.forEach((imgSrc, index) => {
                    const card = document.createElement('div');
                    card.className = 'sheet-card selected';
                    card.id = 'card_' + index;
                    card.onclick = () => toggleSelect(index);
                    card.innerHTML = `
                        <input type="checkbox" class="checkbox" id="check_${index}" checked onclick="event.stopPropagation(); toggleSelect(${index});">
                        <img src="/${imgSrc}">
                    `;
                    grid.appendChild(card);
                });
                document.getElementById('pdfBtn').style.display = 'block';
            } else {
                alert('분석 실패: ' + data.error);
            }
        }

        function toggleSelect(index) {
            const card = document.getElementById('card_' + index);
            const checkbox = document.getElementById('check_' + index);
            checkbox.checked = !checkbox.checked;
            if(checkbox.checked) card.classList.add('selected');
            else card.classList.remove('selected');
        }

        function generatePDF() {
            const selectedImages = [];
            fetchedImages.forEach((img, idx) => {
                if(document.getElementById('check_' + idx).checked) selectedImages.push(img);
            });
            if(selectedImages.length === 0) return alert('선택된 악보가 없습니다.');

            fetch('/make-pdf', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ images: selectedImages })
            })
            .then(response => response.blob())
            .then(blob => {
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = "drum_sheet.pdf";
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

@app.route('/analyze', methods=['POST'])
def analyze():
    data = request.json
    url = data.get('url')
    y_start = float(data.get('y_start', 55)) / 100.0
    y_end = float(data.get('y_end', 97)) / 100.0
    
    for f in os.listdir(UPLOAD_FOLDER):
        try: os.remove(os.path.join(UPLOAD_FOLDER, f))
        except: pass

    ydl_opts = {
        'format': 'bestvideo[ext=mp4][height<=480]+bestaudio[ext=m4a]/best[ext=mp4][height<=480]',
        'outtmpl': 'temp_download.mp4',
        'quiet': True,
        'noplaylist': True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl: ydl.download([url])
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

    cap = cv2.VideoCapture('temp_download.mp4')
    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_interval = int(fps * 0.8)

    prev_roi = None
    saved_paths = []
    count = 0
    frame_idx = 0

    while True:
        ret, frame = cap.read()
        if not ret: break

        if frame_idx % frame_interval == 0:
            h, w, _ = frame.shape
            roi = frame[int(h*y_start):int(h*y_end), int(w*0.02):int(w*0.98)]
            gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

            if prev_roi is not None:
                score, _ = ssim(prev_roi, gray, full=True)
                if score < 0.88:
                    path = f"{UPLOAD_FOLDER}/sheet_{count:03d}.png"
                    cv2.imwrite(path, roi)
                    saved_paths.append(path)
                    count += 1
                    prev_roi = gray
            else:
                path = f"{UPLOAD_FOLDER}/sheet_{count:03d}.png"
                cv2.imwrite(path, roi)
                saved_paths.append(path)
                count += 1
                prev_roi = gray
        frame_idx += 1

    cap.release()
    if os.path.exists('temp_download.mp4'): os.remove('temp_download.mp4')
    return jsonify({'success': True, 'images': saved_paths})

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