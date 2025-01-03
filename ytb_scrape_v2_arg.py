from dotenv import load_dotenv
load_dotenv()
from os import getpid
from sys import argv
from time import sleep
from utils import logger
from utils.lark import alarm_lark_text
from utils.utime import get_now_time_string, format_second_to_time_string
from handler.yt_dlp import ytb_dlp_format_video
from ytb_scrape_ytb_search import scrape_pipeline
from ytb_scrape_yeb_dlp_pip import import_data_to_db_pip
from ytb_scrape_yt_dlp import scrape_ytb_channel_data, import_data_to_db
from handler.yt_dlp_save_url_to_file import yt_dlp_read_url_from_file_v3
from utils.utime import get_now_time_string, format_second_to_time_string
from utils.lark import alarm_lark_text
from database import ytb_api, ytb_api_v2, ytb_init_video
from utils.ip import get_local_ip, get_public_ip

import sys
import os
import time
import multiprocessing 
import uuid

# 初始化
logger = logger.init_logger("ytb_scrape_arg")
local_ip = get_local_ip()
public_ip = get_public_ip()

# youtube_search_python
def main():
    if len(argv) <= 2:
        print("[ERROR] Too less arguments of urls to scrape.")
        print("[INFO] Example: python ytb_scrape.py yue https://www.youtube.com/@video-df1md https://www.youtube.com/@MjrmGames")
        exit()
    pid = getpid()
    language = argv[1]
    opt = input(f"[DEBUG] Check your input, language:{language}, url:{argv[2:]}. Continue?(Y/N)")
    if opt in ["Y", "y", "YES", "yes"]:
        for url in argv[2:]:
            print(f"[INFO] Now scrape url:{url}")
            sleep(1)
            scrape_pipeline(pid, channel_url=url, language=language)
    else:
        print(f"You input {opt}. Bye!")
        exit()

# yt-dlp
def main_v2():
    """
    通过命令行获取博主链接并写入txt文本,读取文本入库
    """
    if len(argv) <= 2:
        print("[ERROR] Too less arguments of urls to scrape.")
        print("[INFO] Example: python ytb_scrape_arg.py yue https://www.youtube.com/@video-df1md")
        exit()
    pid = getpid()
    language = argv[1]
    opt = input(f"[DEBUG] Check your input, language:{language}, url:{argv[2:]}. Continue?(Y/N)")
    if opt in ["Y", "y", "YES", "yes"]:
        for url in argv[2:]:
            print(f"[INFO] Now scrape url:{url}")
            sleep(1)
            for channel_url in argv[2:]:
                count = 0
                target_youtuber_blogger_urls = scrape_ytb_channel_data(pid=pid,channel_url=channel_url, language=language)
                if len(target_youtuber_blogger_urls) <= 0:
                    continue
                for watch_url in target_youtuber_blogger_urls:
                    import_data_to_db(pid, watch_url, language=language)
                    print(f"{count} | {watch_url} 处理完毕")
                    count += 1
                    time.sleep(0.5)
    else:
        print(f"You input {opt}. Bye!")
        exit()

# yt-dlp
def main_v3(): 
    """
    通过命令行从给定的 YouTube 频道链接抓取视频数据并将其存储到数据库中。
    """
    if len(argv) <= 2:
        print("[ERROR] Too less arguments of urls to scrape.")
        print("[INFO] Example: python ytb_scrape_arg.py yue https://www.youtube.com/@video-df1md")
        exit()
    pid = os.getpid()  # 捕获进程
    task_id = str(uuid.uuid4())  # 获取任务ID
    language = argv[1]
    opt = input(f"[DEBUG] Check your input, language:{language}, url:{argv[2:]}. Continue?(Y/N)")
    if opt in ["Y", "y", "YES", "yes"]:
        for channel_url in argv[2:]:
            time_st = time.time()  # 获取采集数据的起始时间
            target_youtuber_channel_urls = yt_dlp_read_url_from_file_v3(url=channel_url, language=language)
            if len(target_youtuber_channel_urls) <= 0:
                logger.error("Scraper Pipeline > no watch urls to import.")
                # exit()
                continue
            # 统计总时长
            total_duration = sum(
                [float(duration_url[1]) 
                for duration_url in target_youtuber_channel_urls 
                if 'NA' not in duration_url])
            # 统计总视频数量
            total_count = len(target_youtuber_channel_urls)
            try:
                # 使用多进程处理video_url_list入库 # 创建进程池
                with multiprocessing.Pool(5) as pool:
                    # 将列表分成5个子集，分配给每个进程
                    # chunks = np.array_split(target_youtuber_blogger_urls, 5)
                    chunk_size = len(target_youtuber_channel_urls) // 5
                    chunks = [target_youtuber_channel_urls[i:i + chunk_size] for i in range(0, total_count, chunk_size)]
                    # print(chunks)
                    # 列表的长度可能会有剩余的元素，我们将它们分配到最后一个子集中
                    if len(chunks) < 5:
                        chunks.append(target_youtuber_channel_urls[len(chunks)*chunk_size:])
                    time_ed = time.time()
                    spend_scrape_time =  time_ed - time_st  # 采集总时间
                    # 启动进程池中的进程，传递各自的子集和进程ID
                    for pool_num, chunk in enumerate(chunks):
                        # 将各项参数封装为Video对象
                        video_chunk = ytb_dlp_format_video(channel_url, chunk, language)
                        pool.apply_async(import_data_to_db_pip, (video_chunk, pool_num, pid, task_id))
                        time.sleep(0.5)
                    pool.close()
                    pool.join()  # 等待所有进程结束
                    # 频道通知开始
                    now_str = get_now_time_string()
                    notice_text = f"[Youtube Scraper | DEBUG] 采集结束. \
                        \n\t频道URL: {channel_url} \
                        \n\t语言: {language} \
                        \n\t入库视频数量: {total_count} \
                        \n\t入库时长(小时):{round((total_duration / 3600),3)} \
                        \n\t任务ID: {task_id} \
                        \n\t任务处理时间: {format_second_to_time_string(spend_scrape_time)} \
                        \n\t通知时间: {now_str}"
                    alarm_lark_text(webhook=os.getenv("NOTICE_WEBHOOK"), text=notice_text)
            except KeyboardInterrupt:
                # 捕获到 Ctrl+C 时，确保终止所有子进程
                logger.warning("KeyboardInterrupt detected, terminating pool...")
                pool.terminate()
                sys.exit()  # 退出主程序


if __name__ == "__main__":
    main_v3()