import os
import re
import json
import sys
import requests
import concurrent.futures
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from PyPDF2 import PdfMerger, PdfReader
from PyPDF2.errors import PdfReadError

def natural_sort_key(s):
    """
    进行自然排序，以便于对包含数字的文件名进行排序。
    """
    return [int(text) if text.isdigit() else text.lower() for text in re.split('([0-9]+)', str(s))]

def crawl_pages(start_url):
    """
    从指定的起始URL开始，爬取所有相关的页面。
    """
    visited = set()
    to_visit = [start_url]
    crawled_urls = []
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    while to_visit:
        current_url = to_visit.pop(0)
        is_start_url = (current_url == start_url)
        if current_url in visited:
            continue
        
        try:
            print(f"正在爬取页面: {current_url}")
            response = requests.get(current_url, headers=headers, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            
            visited.add(current_url)
            crawled_urls.append(current_url)

            for link in soup.find_all("a", href=True):
                href = link["href"].strip()
                if "node_" in href and ".html" in href:
                    full_url = urljoin(current_url, href)
                    if full_url not in visited and full_url not in to_visit:
                        to_visit.append(full_url)
        except requests.RequestException as e:
            if is_start_url and not crawled_urls:
                print(f"起始页面 {start_url} 无法访问: {e}。跳过此日期。")
                return None
            print(f"爬取 {current_url} 失败: {e}")
            
    return crawled_urls

def download_and_validate_pdf(url_info, output_dir, headers):
    """
    下载并验证单个PDF文件。此函数由线程池调用。
    url_info 是一个元组 (index, url)，用于保证排序。
    """
    index, pdf_url = url_info
    try:
        print(f"线程启动: 开始下载 {pdf_url}")
        response = requests.get(pdf_url, headers=headers, timeout=60) # 加长超时
        response.raise_for_status()
        
        if not response.content:
            print(f"警告: 下载的文件是空的 {pdf_url}")
            return None

        file_name = os.path.basename(urlparse(pdf_url).path)
        safe_filename = re.sub(r'[\\/*?:"<>|]', "_", file_name)
        if not safe_filename.lower().endswith('.pdf'):
            safe_filename += ".pdf"
        
        file_path = os.path.join(output_dir, safe_filename)
        
        with open(file_path, "wb") as f:
            f.write(response.content)

        try:
            with open(file_path, 'rb') as pdf_file:
                reader = PdfReader(pdf_file, strict=False)
                num_pages = len(reader.pages)
                if num_pages == 0:
                    print(f"警告: PDF文件 '{file_path}' 没有页面，跳过。")
                    os.remove(file_path)
                    return None
            print(f"线程完成: 下载并验证成功 {file_path} (共 {num_pages} 页)")
            return (index, file_path, num_pages)
        except PdfReadError as e:
            print(f"错误: 文件 '{file_path}' 不是有效的PDF。错误: {e}")
            os.remove(file_path)
            return None

    except requests.RequestException as e:
        print(f"下载 {pdf_url} 失败: {e}")
        return None
    except Exception as e:
        print(f"处理 {pdf_url} 时发生了未知错误: {e}")
        return None

def download_and_merge_pdfs(seed_url, output_dir="downloaded_pdfs", merged_filename="merged.pdf"):
    """
    下载所有找到的PDF，然后将它们合并。
    """
    if not seed_url:
        print("错误: 未提供起始URL。")
        return 0

    pages = crawl_pages(seed_url)
    if pages is None:
        return 0
    if not pages:
        print("未能爬取到任何页面。")
        return 0

    pdf_urls = [] # 使用列表以保证顺序
    print("\n开始在爬到的页面里找PDF链接...")
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    for page_url in pages:
        try:
            response = requests.get(page_url, headers=headers, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")

            for link in soup.find_all("a", href=True):
                href = link["href"].strip()
                if ".pdf" in href.lower():
                    full_pdf_url = urljoin(page_url, href)
                    if full_pdf_url not in pdf_urls: # 检查重复并保持顺序
                        pdf_urls.append(full_pdf_url)
        except requests.RequestException as e:
            print(f"获取页面 {page_url} 出错了: {e}")
            continue
    
    if not pdf_urls:
        print("在页面中未找到PDF链接。")
        return 0

    print(f"\n找到了 {len(pdf_urls)} 个PDF，准备开干...")

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    temp_pdf_files_with_index = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        url_with_indices = list(enumerate(pdf_urls))
        
        future_results = executor.map(download_and_validate_pdf, url_with_indices, [output_dir]*len(url_with_indices), [headers]*len(url_with_indices))
        
        for result in future_results:
            if result:
                temp_pdf_files_with_index.append(result)

    if not temp_pdf_files_with_index:
        print("未能成功下载任何有效的PDF文件。")
        return 0

    temp_pdf_files_with_index.sort(key=lambda x: x[0])
    temp_pdf_files = [path for index, path, pages in temp_pdf_files_with_index]
    pages_this_run = sum(pages for index, path, pages in temp_pdf_files_with_index)

    if not temp_pdf_files:
        print("未能成功下载任何有效的PDF文件。")
        return 0
        
    merged_file_path = os.path.join(output_dir, merged_filename)
    print(f"\n开始合并 {len(temp_pdf_files)} 个PDF文件 (共 {pages_this_run} 页) 到: {merged_file_path}")
    merger = PdfMerger()
    success = False
    try:
        for pdf_path in temp_pdf_files:
            merger.append(pdf_path)
        
        merger.write(merged_file_path)
        merger.close()

        # 检查合并后的文件是不是个废物
        if os.path.exists(merged_file_path) and os.path.getsize(merged_file_path) > 0:
            print(f"\n合并成功！最终文件: {merged_file_path}")
            success = True
        else:
            print(f"\n操，合并失败了，生成的文件是空的或者不存在。")

    except Exception as e:
        print(f"合并PDF时出错了: {e}")
    finally:
        if success:
            print("\n开始清理下载的临时文件...")
            for pdf_path in temp_pdf_files:
                try:
                    os.remove(pdf_path)
                except OSError as e:
                    print(f"删除文件 {pdf_path} 失败: {e}")
            print("清理完毕。")
        else:
            print("\n合并失败，临时PDF文件已保留在下载目录中以便检查。")
    
    return pages_this_run if success else 0

def main():
    """
    主函数，程序入口。
    """
    websites_file = "websites.json"
    
    if len(sys.argv) > 1:
        seed_url = sys.argv[1]
        site_name = re.sub(r'https?://', '', seed_url).split('/')[0].replace(".", "_")
        merged_filename = f"{site_name}_merged.pdf"
        print(f"\n从命令行接收到任务: {seed_url}")
        download_and_merge_pdfs(seed_url, merged_filename=merged_filename)
        return

    if not os.path.exists(websites_file):
        print(f"错误: 未找到 '{websites_file}'。")
        return

    try:
        with open(websites_file, "r", encoding="utf-8") as f:
            websites = json.load(f)
    except Exception as e:
        print(f"读取 '{websites_file}' 文件时出错: {e}")
        return

    if not websites:
        print(f"'{websites_file}' 文件为空。")
        return

    page_limit = 50

    try:
        start_date_str = input("输入开始日期 (YYYY-MM-DD): ").strip()
        end_date_str = input("输入结束日期 (YYYY-MM-DD): ").strip()
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
    except ValueError:
        print("日期格式不正确，请使用 YYYY-MM-DD 格式。")
        return

    for site in websites:
        pages_for_this_site = 0 # 每个网站单独计算页数
        url_template = site['url']
        site_name_template = site['name'].replace(" ", "_").replace(".", "_")

        date_format_code = None
        date_pattern = None
        # 格式: YYYY-MM/DD
        if re.search(r'\d{4}-\d{2}/\d{2}', url_template):
            date_pattern = re.search(r'(\d{4}-\d{2}/\d{2})', url_template)
            date_format_code = "%Y-%m/%d"
        # 格式: YYYYMM/DD
        elif re.search(r'\d{6}/\d{2}', url_template):
            date_pattern = re.search(r'(\d{6}/\d{2})', url_template)
            date_format_code = "%Y%m/%d"
        # 格式: YYYY/MM/DD
        elif re.search(r'\d{4}/\d{2}/\d{2}', url_template):
            date_pattern = re.search(r'(\d{4}/\d{2}/\d{2})', url_template)
            date_format_code = "%Y/%m/%d"
        # 格式: YYYYMMDD
        elif re.search(r'\d{8}', url_template):
            date_pattern = re.search(r'(\d{8})', url_template)
            date_format_code = "%Y%m%d"

        if not date_pattern:
            print(f"警告: 在URL '{url_template}' 中没找到可识别的日期格式，跳过该网站。")
            continue

        print(f"\n{'='*20} 开始处理网站: {site['name']} {'='*20}")
        current_date = start_date
        while current_date <= end_date:
            date_str_url = current_date.strftime(date_format_code)

            seed_url = url_template.replace(date_pattern.group(0), date_str_url)
            date_str_file = current_date.strftime("%Y-%m-%d")
            merged_filename = f"{site_name_template}_{date_str_file}.pdf"
            
            print(f"\n--- [{date_str_file}] 开始处理: '{seed_url}' ---")
            
            pages_this_run = download_and_merge_pdfs(seed_url, merged_filename=merged_filename)
            
            if pages_this_run > 0:
                pages_for_this_site += pages_this_run
                print(f"本轮收集 {pages_this_run} 页，'{site['name']}' 已累计: {pages_for_this_site}/{page_limit} 页")
            
            if pages_for_this_site >= page_limit:
                print(f"\n网站 '{site['name']}' 已达到或超过 {page_limit} 页的上限，停止处理该网站。")
                break
            
            current_date += timedelta(days=1)

    print(f"\n{'='*20} 所有网站处理完毕 {'='*20}")


if __name__ == "__main__":
    main()
