import sqlite3
import random
from datetime import datetime, timedelta

random.seed(99)
DB_PATH = r'C:\Users\11029\Desktop\chatbi-agent\shuidi.db'
conn = sqlite3.connect(DB_PATH)

# ── 建表 ─────────────────────────────────────────────
conn.executescript("""
DROP TABLE IF EXISTS regions;
DROP TABLE IF EXISTS teams;
DROP TABLE IF EXISTS staff;

CREATE TABLE regions (
    region_id   INTEGER PRIMARY KEY,
    name        TEXT
);

CREATE TABLE teams (
    team_id     INTEGER PRIMARY KEY,
    region_id   INTEGER,
    name        TEXT,
    FOREIGN KEY (region_id) REFERENCES regions(region_id)
);

CREATE TABLE staff (
    staff_id    INTEGER PRIMARY KEY,
    name        TEXT,
    team_id     INTEGER,
    title       TEXT,  -- 专员/组长
    hired_at    TEXT,
    FOREIGN KEY (team_id) REFERENCES teams(team_id)
);
""")

# ── 大区 ─────────────────────────────────────────────
region_data = [
    (1, "华北大区"),
    (2, "华南大区"),
    (3, "华东大区"),
    (4, "华中大区"),
    (5, "西南大区"),
    (6, "西北大区"),
]
conn.executemany("INSERT INTO regions VALUES (?,?)", region_data)

# ── 小组（每个大区3-4组）────────────────────────────
region_cities = {
    1: ["北京", "天津", "石家庄"],
    2: ["广州", "深圳", "佛山"],
    3: ["上海", "杭州", "南京"],
    4: ["武汉", "长沙", "郑州"],
    5: ["成都", "重庆", "昆明"],
    6: ["西安", "兰州"],
}

teams = []
tid = 1
for region_id, cities in region_cities.items():
    for city in cities:
        for i in range(1, random.randint(2, 4)):
            teams.append((tid, region_id, f"{city}{i}组"))
            tid += 1

conn.executemany("INSERT INTO teams VALUES (?,?,?)", teams)
print(f"小组: {len(teams)} 个")

# ── 员工（每组4-8人，含1个组长）────────────────────
surnames = "李王张刘陈杨赵黄周吴徐孙朱马胡郭林何高梁郑"
first_names = "伟芳娜秀英敏静丽强磊军洋勇艳杰涛明超霞平"

def rand_name():
    return random.choice(surnames) + random.choice(first_names) + (random.choice(first_names) if random.random()>0.5 else "")

def rand_date(start="2020-01-01", end="2023-06-30"):
    s = datetime.strptime(start, "%Y-%m-%d")
    e = datetime.strptime(end, "%Y-%m-%d")
    return (s + timedelta(days=random.randint(0, (e-s).days))).strftime("%Y-%m-%d")

staff_list = []
sid = 1
for team in teams:
    team_id = team[0]
    count = random.randint(4, 8)
    for i in range(count):
        title = "组长" if i == 0 else "专员"
        staff_list.append((sid, rand_name(), team_id, title, rand_date()))
        sid += 1

conn.executemany("INSERT INTO staff VALUES (?,?,?,?,?)", staff_list)
print(f"员工: {len(staff_list)} 人")

# ── campaigns表加staff_id字段 ────────────────────────
try:
    conn.execute("ALTER TABLE campaigns ADD COLUMN staff_id INTEGER")
except:
    pass

staff_ids = [s[0] for s in staff_list]
campaigns = conn.execute("SELECT campaign_id FROM campaigns").fetchall()
for (cid,) in campaigns:
    conn.execute("UPDATE campaigns SET staff_id=? WHERE campaign_id=?",
                 (random.choice(staff_ids), cid))

conn.commit()
conn.close()
print(f"campaigns已关联staff_id")
print("done")
