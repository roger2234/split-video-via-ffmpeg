import os
import subprocess
import datetime
import re
from pathlib import Path

from typing import List, Tuple, Dict

VIDEO_EXTENSIONS = ['.ts', '.mp4', '.mkv']


def parse_duration_string(duration_str: str) -> int:
    """將像 1h20m30s 這樣的格式轉換成秒數"""
    pattern = r'(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?'
    match = re.fullmatch(pattern, duration_str.strip())
    if not match:
        raise ValueError("時間格式錯誤，請使用例如 '1h20m30s' 的格式")

    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)
    return hours * 3600 + minutes * 60 + seconds


def get_video_files_from_dirs(directories: List[str]) -> List[Path]:
    video_files = []
    for dir_path in directories:
        p = Path(dir_path)
        if not p.is_dir():
            print(f"找不到資料夾：{dir_path}")
            continue
        for file in p.iterdir():
            if file.suffix.lower() in VIDEO_EXTENSIONS and '_cut_' not in file.stem:
                video_files.append(file)
    return video_files


def get_video_info(file_path: Path) -> Tuple[float, float]:
    """取得影片長度(秒)與檔案大小(MB)"""
    try:
        cmd = [
            'ffprobe',
            '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            str(file_path)
        ]
        duration = float(subprocess.check_output(cmd).strip())
        size = file_path.stat().st_size / (1024 * 1024)
        return duration, size
    except Exception as e:
        print(f"無法取得影片資訊：{file_path}，錯誤：{e}")
        return 0.0, 0.0


def format_duration(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def main():
    print("請輸入影片所在的【資料夾】路徑(可貼多個，用 ; 分隔)：")
    input_paths = input(">> ").strip()
    directories = [p.strip() for p in input_paths.split(';') if p.strip()]

    all_files = get_video_files_from_dirs(directories)

    if not all_files:
        print("找不到任何影片檔案。")
        return

    file_infos = []
    print("\n=== 找到以下影片檔案 ===")
    for idx, f in enumerate(all_files, 1):
        duration, size = get_video_info(f)
        print(f"[{idx}] {f.name} | 時長: {format_duration(duration)} | 大小: {size:.2f} MB")
        file_infos.append((f, duration, size))

    print("\n請輸入欲分割的影片編號(用逗號分隔，輸入 a 表示全部)：")
    selected = input(">> ").strip()
    if selected.lower() == 'a':
        selected_files = file_infos
    else:
        indexes = [int(x) for x in selected.split(',') if x.strip().isdigit()]
        selected_files = [file_infos[i-1] for i in indexes if 0 < i <= len(file_infos)]

    print("\n請選擇分割時長的方式：1. 固定時長 2. 多個分割點")
    mode = input(">> ").strip()

    segment_settings: Dict[Path, List[int]] = {}

    if mode == '2':
        for idx, (file, duration, size) in enumerate(selected_files, 1):
            print(f"\n[{idx}] {file.name} | 時長: {format_duration(duration)} | 大小: {size:.2f} MB")
            print("請輸入多個分割點(格式如 30m10s,1h31m52s,...)，輸入 end 結束：")
            points = []
            while True:
                raw = input("-->> ").strip()
                if raw.lower() == 'end':
                    break
                try:
                    seconds = parse_duration_string(raw)
                    if seconds >= duration:
                        print("  ⚠️ 分割點超出影片長度，請重新輸入")
                        continue
                    points.append(seconds)
                except Exception as e:
                    print(f"  ⚠️ 格式錯誤：{e}")
            segment_settings[file] = sorted(points)

    else:
        print("請輸入分割的時間長度(例如：1h30m / 3600s)：")
        raw = input(">> ").strip()
        try:
            fixed_duration = parse_duration_string(raw)
            for file, duration, size in selected_files:
                segment_settings[file] = [fixed_duration]  # 用固定長度表示
        except Exception as e:
            print(f"格式錯誤：{e}")
            return

    # 紀錄 log
    now_str = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    log_path = Path(f"split_video_{now_str}.log")
    start_time = datetime.datetime.now()

    with open(log_path, 'w', encoding='utf-8') as log:
        log.write(f"開始時間：{start_time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")

        for file, settings in segment_settings.items():
            output_pattern = file.with_name(file.stem + '_cut_%03d' + file.suffix)
            log.write(f"=== {file.name} ===\n")

            if len(settings) == 1:
                seg_time = settings[0]
                cmd = [
                    "ffmpeg",
                    "-i", str(file),
                    "-c", "copy",
                    "-f", "segment",
                    "-segment_time", str(seg_time),
                    "-reset_timestamps", "1",
                    "-individual_header_trailer", "1",
                    "-segment_start_number", "1",
                    str(output_pattern)
                ]
                log.write("# " + " ".join(cmd) + " #\n\n")
                subprocess.run(cmd, shell=True)
            else:
                prev = 0
                for idx, point in enumerate(settings + [get_video_info(file)[0]]):
                    output_file = file.with_name(f"{file.stem}_cut_{idx+1:03d}{file.suffix}")
                    cmd = [
                        "ffmpeg",
                        "-i", str(file),
                        "-ss", str(datetime.timedelta(seconds=prev)),
                        "-to", str(datetime.timedelta(seconds=point)),
                        "-c", "copy",
                        str(output_file)
                    ]
                    log.write("# " + " ".join(cmd) + " #\n")
                    subprocess.run(cmd, shell=True)
                    prev = point
            log.write("\n\n")

        end_time = datetime.datetime.now()
        duration = end_time - start_time
        log.write(f"結束時間：{end_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        log.write(f"總執行時間：{duration.total_seconds():.2f} 秒\n")

    print("\n✅ 全部處理完成。紀錄檔：", log_path)


if __name__ == '__main__':
    main()
