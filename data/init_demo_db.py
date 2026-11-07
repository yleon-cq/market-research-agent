"""初始化演示数据库（SQLite）：竞品调研场景。

虚构公司设定（避免真实品牌）：
- 本公司：启声科技，产品线 EchoMind 系列
- 竞品：声浪科技（X5 系列）/ 聆悦电子（聆风系列）/ 极目智能（视界系列）

运行：python data/init_demo_db.py
"""
import random
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "demo_market.db"

PRODUCTS = [
    # (product_id, product_name, brand, category, price, launch_date)
    (101, "EchoMind Mini", "启声科技", "智能音箱", 349, "2025-11-20"),
    (102, "EchoMind Pro", "启声科技", "智能音箱", 699, "2026-03-15"),
    (103, "EchoMind Screen", "启声科技", "带屏音箱", 999, "2026-06-01"),
    (201, "声浪 X5", "声浪科技", "智能音箱", 499, "2026-01-10"),
    (202, "声浪 X5 Pro", "声浪科技", "智能音箱", 899, "2026-10-15"),
    (301, "聆风 Air", "聆悦电子", "智能音箱", 299, "2025-08-01"),
    (302, "聆风 Studio", "聆悦电子", "AI 音箱", 1299, "2026-04-20"),
    (401, "视界 S1", "极目智能", "带屏音箱", 899, "2026-02-10"),
]

CHANNELS = ["线上自营", "电商平台", "线下门店"]


def init_db():
    random.seed(42)
    if DB_PATH.exists():
        DB_PATH.unlink()
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.executescript(
        """
        CREATE TABLE products (
            product_id INTEGER PRIMARY KEY,
            product_name TEXT NOT NULL,
            brand TEXT NOT NULL,
            category TEXT,
            price REAL,
            launch_date TEXT
        );
        CREATE TABLE sales_records (
            sale_id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER,
            month TEXT,
            quantity INTEGER,
            unit_price REAL,
            rating REAL,
            channel TEXT
        );
        CREATE TABLE inventory (
            record_id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER,
            warehouse TEXT,
            stock_qty INTEGER,
            update_date TEXT
        );
        """
    )
    cur.executemany("INSERT INTO products VALUES (?,?,?,?,?,?)", PRODUCTS)

    # 销量设定：头部型号走量，新上市型号爬坡；声浪 X5 借 X5 Pro 发布带动增长
    base_qty = {
        101: 5200, 102: 3100, 103: 900,
        201: 4500, 202: 1600,   # X5 Pro 10月刚发布
        301: 6800, 302: 600,
        401: 1500,
    }
    months = [f"2026-{m:02d}" for m in range(1, 11)]
    for pid, base in base_qty.items():
        price = next(p[4] for p in PRODUCTS if p[0] == pid)
        for i, month in enumerate(months):
            qty = int(base * (0.85 + 0.3 * random.random()) * (1 + 0.04 * i))
            if pid == 202 and month < "2026-10":
                qty = 0  # 上市前无销量
            rating = round(random.uniform(4.1, 4.8), 1)
            channel = random.choice(CHANNELS)
            cur.execute(
                "INSERT INTO sales_records (product_id, month, quantity, unit_price, rating, channel)"
                " VALUES (?,?,?,?,?,?)",
                (pid, month, qty, price, rating, channel),
            )

    for pid, _ in base_qty.items():
        for wh in ["华东仓", "华南仓"]:
            cur.execute(
                "INSERT INTO inventory (product_id, warehouse, stock_qty, update_date) VALUES (?,?,?,?)",
                (pid, wh, random.randint(200, 5000), "2026-10-31"),
            )

    conn.commit()
    cur.execute("SELECT COUNT(*) FROM sales_records")
    n_sales = cur.fetchone()[0]
    conn.close()
    print(f"演示数据库已生成: {DB_PATH}")
    print(f"  products={len(PRODUCTS)}, sales_records={n_sales}, inventory={len(base_qty) * 2}")


if __name__ == "__main__":
    init_db()
