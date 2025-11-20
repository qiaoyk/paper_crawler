import os
import sys
from PyPDF2 import PdfReader

def count_them_all(directory="downloaded_pdfs"):
    """
    统计指定目录下所有PDF的页数。
    """
    if not os.path.exists(directory):
        print(f"目录 '{directory}' 不存在！")
        return

    files = [f for f in os.listdir(directory) if f.lower().endswith('.pdf')]
    if not files:
        print(f"'{directory}' 没有PDF文件")
        return

    print(f"正在扫描 '{directory}' 下的 {len(files)} 个文件...")
    print("-" * 60)
    print(f"{'文件名':<40} | {'页数':<10}")
    print("-" * 60)

    total_pages = 0
    valid_files = 0
    
    files.sort()

    for f in files:
        path = os.path.join(directory, f)
        try:
            reader = PdfReader(path)
            pages = len(reader.pages)
            
            display_name = (f[:37] + '..') if len(f) > 37 else f
            
            print(f"{display_name:<40} | {pages:<10}")
            total_pages += pages
            valid_files += 1
        except Exception as e:
            print(f"{f:<40} | (读不了: {str(e)[:20]}...)")

    print("-" * 60)
    if valid_files > 0:
        print(f"统计完成。")
        print(f"总文件数: {valid_files}")
        print(f"总页数  : {total_pages}")
        print(f"平均页数: {total_pages / valid_files:.2f}")
    else:
        print("没有可读的PDF文件。")

if __name__ == "__main__":
    target_dir = "downloaded_pdfs"
    if len(sys.argv) > 1:
        target_dir = sys.argv[1]
    
    count_them_all(target_dir)

