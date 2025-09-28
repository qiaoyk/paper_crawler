# 安装需要依赖
pip3 install -r requirements.txt

# 1. 查看所有可用数据源
python3 crawler.py --list

# 2. 按索引选择数据源 (从1开始计数)
python3 crawler.py -s 1          # 选择第一个数据源
python3 crawler.py -s 5          # 选择第五个数据源

# 3. 按名称模糊匹配选择数据源  
python3 crawler.py -s "海南"      # 匹配包含"海南"的所有数据源
python3 crawler.py -s "日报"      # 匹配所有包含"日报"的数据源

# 4. 处理全部数据源
python3 crawler.py -s all        # 或者
python3 crawler.py               # 不指定source默认处理全部

# 5. 向后兼容：直接传URL (保持原有功能)
python3 crawler.py http://example.com/newspaper/