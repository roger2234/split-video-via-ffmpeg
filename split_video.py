#!/usr/bin/env python3

import os
import subprocess
from datetime import datetime
import re

# 支援的影片格式
video_extensions = ['.ts', '.mp4', '.mkv']

# 時間字串轉換為秒數（支援 1h2m3s / 90m / 5400s 等格式）
def parse_time_string(time_str):
    pattern = r'(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?'
    match = re.match(pattern, time_str.lower())
    if not match:
        return int(time_str)
    h, m, s = match.groups()
    return int(h or 0) * 3600 + int(m or 0) * 60 + int(s or 0)

# 取得影片時長（秒）和大小（MB）
def get_video_info(filepath):
    try:
        result = subprocess.run([
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "format=duration,size", "-of",
            "default=noprint_wrappers=1:nokey=1", filepath
        ], capture_output=True, text=True)

        duration_str, size_str = result.stdout.strip().split("\n")
        duration = float(duration_str)
        size_mb = round(int(size_str) / (1024 * 1024), 2)
        return duration, size_mb
    except:
        return None, None

# 取得輸入資料夾
input_dir = input("請輸入影片所在資料夾：").strip()
if not os.path.exists(input_dir):
    print("錯誤：指定路徑不存在。")
    exit()

# 取得所有符合格式的檔案
all_files = [f for f in os.listdir(input_dir) if os.path.splitext(f)[1].lower() in video_extensions]

# 顯示檔案資訊
print("\n檔案列表：")
file_info_list = []
for i, filename in enumerate(all_files, start=1):
    path = os.path.join(input_dir, filename)
    duration, size_mb = get_video_info(path)
    file_info_list.append((filename, duration, size_mb))
    dur_str = f"{int(duration//60)}m{int(duration%60)}s" if duration else "N/A"
    print(f"[{i}] {filename} | 長度: {dur_str} | 大小: {size_mb}MB")

# 使用者選擇欲處理的檔案
selection = input("請選擇要分割的檔案編號（以逗號分隔，或輸入 a 表示全部）：").strip()
if selection.lower() == 'a':
    selected = file_info_list
else:
    indices = [int(x)-1 for x in selection.split(',') if x.strip().isdigit()]
    selected = [file_info_list[i] for i in indices if 0 <= i < len(file_info_list)]

# 是否個別設定切割時長
individual = input("是否針對每個檔案個別設定分割時間？(y/n)：").strip().lower() == 'y'
segment_times = {}

# 紀錄 log 檔
log_name = datetime.now().strftime("%Y%m%d_%H%M%S") + ".log"
log_path = os.path.join(input_dir, log_name)
log_file = open(log_path, 'w', encoding='utf-8')

for filename, duration, size in selected:
    print(f"\n處理：{filename} | 長度: {int(duration//60)}m{int(duration%60)}s | 大小: {size}MB")
    if individual:
        t_str = input("請輸入分割時長（支援 1h30m, 90m, 5400s）：").strip()
    else:
        if not segment_times:
            t_str = input("請輸入分割時長（統一套用所有檔案）：").strip()
            segment_times['default'] = parse_time_string(t_str)
        segment_time = segment_times['default']
        t_str = f"{segment_time}s"

    segment_time = parse_time_string(t_str)
    segment_times[filename] = segment_time

    input_path = os.path.join(input_dir, filename)
    basename, ext = os.path.splitext(filename)
    output_pattern = os.path.join(input_dir, f"{basename}_cut_%03d{ext}")

    # 指令依據副檔名選擇設定
    if ext.lower() in ['.ts', '.mp4', '.mkv']:
        ffmpeg_cmd = [
            "ffmpeg", "-i", input_path, "-c", "copy", "-f", "segment",
            "-segment_time", str(segment_time),
            "-reset_timestamps", "1", "-individual_header_trailer", "1",
            "-segment_start_number", "1", output_pattern
        ]
    else:
        continue

    cmd_str = ' '.join(ffmpeg_cmd)
    border = "#" * (len(cmd_str) + 4)
    print(border)
    print(f"# {cmd_str} #")
    print(border)

    log_file.write(f"\n=== {filename} ===\n")
    log_file.write(border + "\n")
    log_file.write(f"# {cmd_str} #\n")
    log_file.write(border + "\n")

    subprocess.run(ffmpeg_cmd)

log_file.write("\n全部處理完成。\n")
log_file.close()
print("\n分割作業完成。")
