# Video Translator - Chinese to Vietnamese

Ứng dụng desktop dịch video từ tiếng Trung sang tiếng Việt hoàn toàn miễn phí, không sử dụng API trả phí.

## Tính năng

- 🎬 **Phát video**: Hỗ trợ các định dạng MP4, MKV, AVI, MOV, WMV, FLV, WebM, M4V
- 🎯 **Chọn vùng phụ đề (ROI)**: Chỉ OCR trong vùng được chọn để tăng tốc và độ chính xác
- 📝 **OCR**: Sử dụng PaddleOCR với hỗ trợ tiếng Trung
- 🌐 **Dịch**: Dịch offline sử dụng MarianMT (Helsinki-NLP)
- 📋 **Xuất phụ đề**: Hỗ trợ SRT, ASS, VTT
- 🎥 **Render video**: Burn phụ đề vào video bằng FFmpeg

## Yêu cầu hệ thống

- Python 3.8+
- FFmpeg (để render video)
- Qt6 runtime libraries (libEGL, libxcb)
- RAM: 8GB+ (khuyến nghị 16GB)
- GPU: Hỗ trợ CUDA (tùy chọn, tăng tốc OCR)
- Display: X11 hoặc Wayland (hoặc sử dụng headless mode)

## Cài đặt

### 1. Cài đặt FFmpeg

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install ffmpeg
```

**macOS:**
```bash
brew install ffmpeg
```

**Windows:**
Tải từ https://ffmpeg.org/download.html và thêm vào PATH

### 2. Cài đặt Python packages

```bash
pip install -r requirements.txt
```

### 3. Cài đặt Qt runtime libraries

**Ubuntu/Debian:**
```bash
sudo apt install libegl1 libgl1 libxkbcommon0 libxcb-cursor0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-randr0 libxcb-render-util0 libxcb-shape0
```

### 4. Cài đặt PaddlePaddle (GPU)

```bash
# GPU (NVIDIA)
pip install paddlepaddle-gpu

# CPU
pip install paddlepaddle
```

## Sử dụng

```bash
# Chạy với display
python main.py

# Chạy headless (không có display)
QT_QPA_PLATFORM=offscreen python main.py
```

### Hướng dẫn

1. **Chọn video**: Nhấn "Chọn Video" và chọn file video
2. **Chọn vùng phụ đề**: Kéo chuột trên video để bôi vùng chứa phụ đề
3. **OCR**: Nhấn "Bắt đầu OCR" để nhận diện text
4. **Dịch**: Nhấn "Dịch Phụ Đề" để dịch sang tiếng Việt
5. **Render**: Nhấn "Render Video" để tạo video có phụ đề

## Cấu trúc project

```
video-translator/
├── main.py                 # Entry point
├── config.py               # Configuration
├── requirements.txt        # Dependencies
├── README.md               # Documentation
│
├── ui/                     # UI Module (PyQt6)
│   ├── main_window.py      # Main window
│   ├── video_player.py     # Video player with ROI
│   ├── sidebar.py          # Left sidebar controls
│   ├── subtitle_panel.py   # Right panel (subtitles + logs)
│   └── styles.py           # Dark theme stylesheet
│
├── ocr/                    # OCR Module (PaddleOCR)
│   ├── paddle_ocr.py       # PaddleOCR wrapper
│   └── frame_processor.py  # Frame processing & SSIM
│
├── translator/             # Translator Module (MarianMT)
│   ├── translator.py       # Base translator interface
│   └── offline_translator.py # MarianMT implementation
│
├── subtitle/               # Subtitle Module
│   ├── subtitle.py         # Subtitle data models
│   ├── processor.py        # Subtitle processing
│   └── exporter.py         # SRT/ASS/VTT export
│
├── renderer/               # Renderer Module (FFmpeg)
│   └── ffmpeg_renderer.py  # FFmpeg video rendering
│
├── video/                  # Video Module (OpenCV)
│   ├── video_reader.py     # OpenCV video reader
│   └── frame_cache.py      # Frame caching
│
└── utils/                  # Utils Module
    ├── logger.py           # Logging setup
    ├── roi_manager.py       # ROI persistence
    └── helpers.py           # Helper functions
```

## Tối ưu hiệu suất

- **Multi-thread OCR**: Xử lý nhiều frame song song
- **SSIM deduplication**: Bỏ qua các frame giống nhau
- **ROI cropping**: Chỉ OCR trong vùng phụ đề
- **Translation caching**: Cache kết quả dịch
- **GPU acceleration**: Tự động sử dụng GPU nếu có

## Phím tắt

| Phím | Chức năng |
|------|-----------|
| Space | Play/Pause |
| ESC | Dừng |
| ← | Tua lùi 5 giây |
| → | Tua tới 5 giây |

## Giấy phép

MIT License

## Đóng góp

Pull requests are welcome!
