import sqlite3
import random
import os
from datetime import datetime, timedelta

random.seed(42)

DB_PATH = os.path.join(os.path.dirname(__file__), "shuidi.db")
conn = sqlite3.connect(DB_PATH)

# ── 建表 ─────────────────────────────────────────────
conn.executescript("""
DROP TABLE IF EXISTS hospitals;
DROP TABLE IF EXISTS diseases;
DROP TABLE IF EXISTS campaigns;
DROP TABLE IF EXISTS donations;
DROP TABLE IF EXISTS withdrawals;

CREATE TABLE hospitals (
    hospital_id   INTEGER PRIMARY KEY,
    name          TEXT,
    level         TEXT,  -- 三甲/二甲/一甲
    province      TEXT,
    city          TEXT
);

CREATE TABLE diseases (
    disease_id    INTEGER PRIMARY KEY,
    name          TEXT,
    department    TEXT,  -- 科室
    category      TEXT,  -- 大类
    visit_type    TEXT   -- 门诊/住院
);

CREATE TABLE campaigns (
    campaign_id      INTEGER PRIMARY KEY,
    patient_name     TEXT,
    age              INTEGER,
    gender           TEXT,
    province         TEXT,
    city             TEXT,
    hospital_id      INTEGER,
    disease_id       INTEGER,
    target_amount    REAL,
    raised_amount    REAL,
    donor_count      INTEGER,
    created_at       TEXT,
    deadline         TEXT,
    status           TEXT,  -- 筹款中/已完成/已关闭
    FOREIGN KEY (hospital_id) REFERENCES hospitals(hospital_id),
    FOREIGN KEY (disease_id)  REFERENCES diseases(disease_id)
);

CREATE TABLE donations (
    donation_id    INTEGER PRIMARY KEY,
    campaign_id    INTEGER,
    amount         REAL,
    donated_at     TEXT,
    channel        TEXT,  -- 微信/APP/H5
    is_anonymous   INTEGER,
    FOREIGN KEY (campaign_id) REFERENCES campaigns(campaign_id)
);

CREATE TABLE withdrawals (
    withdrawal_id  INTEGER PRIMARY KEY,
    campaign_id    INTEGER,
    amount         REAL,
    applied_at     TEXT,
    reviewed_at    TEXT,
    status         TEXT,  -- 通过/拒绝/处理中
    FOREIGN KEY (campaign_id) REFERENCES campaigns(campaign_id)
);
""")

# ── 医院数据 ─────────────────────────────────────────
province_cities = {
    "广东": ["广州", "深圳", "佛山", "东莞", "珠海"],
    "北京": ["北京"],
    "上海": ["上海"],
    "浙江": ["杭州", "宁波", "温州", "绍兴"],
    "江苏": ["南京", "苏州", "无锡", "南通"],
    "四川": ["成都", "绵阳", "德阳"],
    "湖北": ["武汉", "宜昌", "荆州"],
    "湖南": ["长沙", "株洲", "衡阳"],
    "河南": ["郑州", "洛阳", "开封"],
    "山东": ["济南", "青岛", "烟台"],
    "陕西": ["西安", "咸阳"],
    "重庆": ["重庆"],
    "福建": ["福州", "厦门"],
    "安徽": ["合肥", "芜湖"],
    "河北": ["石家庄", "保定", "唐山"],
}

hospital_prefixes = ["省人民医院", "市第一人民医院", "市第二人民医院", "大学附属医院",
                     "中医院", "儿童医院", "肿瘤医院", "协和医院", "华西医院分院"]
levels = ["三甲", "三甲", "三甲", "二甲", "二甲", "一甲"]

hospitals = []
hid = 1
for province, cities in province_cities.items():
    for city in cities:
        for prefix in random.sample(hospital_prefixes, k=random.randint(2, 4)):
            hospitals.append((hid, f"{city}{prefix}", random.choice(levels), province, city))
            hid += 1

conn.executemany("INSERT INTO hospitals VALUES (?,?,?,?,?)", hospitals)
print(f"医院: {len(hospitals)} 家")

# ── 疾病数据 ─────────────────────────────────────────
disease_data = [
    # (名称, 科室, 大类, 就诊类型)
    ("肺癌", "肿瘤科", "癌症", "住院"),
    ("乳腺癌", "肿瘤科", "癌症", "住院"),
    ("肝癌", "肿瘤科", "癌症", "住院"),
    ("胃癌", "肿瘤科", "癌症", "住院"),
    ("白血病", "血液科", "癌症", "住院"),
    ("结肠癌", "肿瘤科", "癌症", "住院"),
    ("宫颈癌", "妇科", "癌症", "住院"),
    ("脑瘤", "神经外科", "癌症", "住院"),
    ("冠心病", "心内科", "心脑血管", "住院"),
    ("心肌梗死", "心内科", "心脑血管", "住院"),
    ("脑梗塞", "神经内科", "心脑血管", "住院"),
    ("脑出血", "神经外科", "心脑血管", "住院"),
    ("先天性心脏病", "心外科", "心脑血管", "住院"),
    ("尿毒症", "肾内科", "肾病", "住院"),
    ("肾衰竭", "肾内科", "肾病", "住院"),
    ("肾移植", "泌尿外科", "肾病", "住院"),
    ("车祸骨折", "骨科", "外伤", "住院"),
    ("脊柱损伤", "骨科", "外伤", "住院"),
    ("烧烫伤", "烧伤科", "外伤", "住院"),
    ("重症肌无力", "神经内科", "罕见病", "住院"),
    ("渐冻症", "神经内科", "罕见病", "住院"),
    ("血友病", "血液科", "罕见病", "住院"),
    ("糖尿病并发症", "内分泌科", "慢性病", "门诊"),
    ("慢性肾炎", "肾内科", "慢性病", "门诊"),
    ("慢性肝炎", "肝病科", "慢性病", "门诊"),
    ("儿童脑瘫", "儿科", "儿童疾病", "住院"),
    ("儿童白血病", "儿科", "儿童疾病", "住院"),
    ("早产儿救治", "新生儿科", "儿童疾病", "住院"),
    ("肺炎重症", "呼吸科", "呼吸系统", "住院"),
    ("矽肺病", "呼吸科", "职业病", "住院"),
]

conn.executemany("INSERT INTO diseases VALUES (?,?,?,?,?)",
    [(i+1,) + d for i, d in enumerate(disease_data)])
print(f"疾病: {len(disease_data)} 种")

# ── 筹款项目数据 ─────────────────────────────────────
surnames = "李王张刘陈杨赵黄周吴徐孙朱马胡郭林何高梁郑罗宋谢唐韩曹许邓萧冯曾程蔡彭潘袁于董余苏叶吕魏蒋田杜丁沈姜范江傅钟卢汪戴崔任陆廖姚方金谷邹熊白孟秦邱侯江尹薛"
first_names = "伟芳娜秀英敏静丽强磊军洋勇艳杰涛明超霞平和丰辉燕鹏飞华美宝丹利玉梅波宁昊鑫旭峰"

def rand_name():
    return random.choice(surnames) + "".join(random.choices(first_names, k=random.randint(1,2)))

def rand_date(start="2022-01-01", end="2024-06-30"):
    s = datetime.strptime(start, "%Y-%m-%d")
    e = datetime.strptime(end, "%Y-%m-%d")
    return (s + timedelta(days=random.randint(0, (e-s).days))).strftime("%Y-%m-%d")

campaigns = []
for cid in range(1, 5001):
    province = random.choice(list(province_cities.keys()))
    city = random.choice(province_cities[province])
    # 优先选本省医院
    local_hospitals = [h for h in hospitals if h[3] == province]
    hosp = random.choice(local_hospitals if local_hospitals else hospitals)
    disease = random.choice(disease_data)
    disease_id = disease_data.index(disease) + 1

    age = random.randint(1, 80)
    gender = random.choice(["男", "女"])

    # 目标金额按疾病类型设定
    if disease[2] == "癌症":
        target = random.choice([50000, 80000, 100000, 150000, 200000])
    elif disease[2] in ["心脑血管", "肾病"]:
        target = random.choice([30000, 50000, 80000, 100000])
    elif disease[2] == "罕见病":
        target = random.choice([100000, 150000, 200000, 300000])
    elif disease[2] == "儿童疾病":
        target = random.choice([20000, 30000, 50000, 80000])
    else:
        target = random.choice([10000, 20000, 30000, 50000])

    created = rand_date("2022-01-01", "2024-06-30")
    deadline = (datetime.strptime(created, "%Y-%m-%d") + timedelta(days=random.choice([30,60,90]))).strftime("%Y-%m-%d")

    # 筹款结果
    completion = random.random()
    if completion > 0.7:
        status = "已完成"
        raised = target
        donor_count = random.randint(int(target/200), int(target/50))
    elif completion > 0.15:
        status = "筹款中" if datetime.strptime(deadline, "%Y-%m-%d") > datetime.now() else "已关闭"
        raised = round(target * random.uniform(0.1, 0.95), 2)
        donor_count = random.randint(int(raised/300), max(1, int(raised/80)))
    else:
        status = "已关闭"
        raised = round(target * random.uniform(0.01, 0.2), 2)
        donor_count = random.randint(1, 30)

    campaigns.append((cid, rand_name(), age, gender, province, city,
                      hosp[0], disease_id, target, raised, donor_count,
                      created, deadline, status))

conn.executemany("INSERT INTO campaigns VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", campaigns)
print(f"筹款项目: {len(campaigns)} 条")

# ── 捐款记录 ─────────────────────────────────────────
channels = ["微信", "微信", "微信", "APP", "APP", "H5"]
donations = []
did = 1
for camp in campaigns:
    cid, _, _, _, _, _, _, _, target, raised, donor_count, created, deadline, status = camp
    if donor_count == 0:
        continue
    avg_donation = raised / donor_count
    created_dt = datetime.strptime(created, "%Y-%m-%d")
    deadline_dt = datetime.strptime(deadline, "%Y-%m-%d")
    span = max(1, (deadline_dt - created_dt).days)

    for _ in range(min(donor_count, 50)):  # 每个项目最多写50条捐款
        amount = round(max(1, random.gauss(avg_donation, avg_donation * 0.5)), 2)
        amount = min(amount, 10000)
        days_offset = random.randint(0, span)
        donated_at = (created_dt + timedelta(days=days_offset)).strftime("%Y-%m-%d %H:%M:%S")
        channel = random.choice(channels)
        is_anon = 1 if random.random() < 0.3 else 0
        donations.append((did, cid, amount, donated_at, channel, is_anon))
        did += 1

conn.executemany("INSERT INTO donations VALUES (?,?,?,?,?,?)", donations)
print(f"捐款记录: {len(donations)} 条")

# ── 提现记录 ─────────────────────────────────────────
withdrawals = []
wid = 1
completed = [c for c in campaigns if c[13] in ("已完成", "已关闭") and c[9] > 1000]
for camp in completed:
    cid, _, _, _, _, _, _, _, _, raised, _, created, _, _ = camp
    if raised < 100:
        continue
    apply_date = (datetime.strptime(created, "%Y-%m-%d") + timedelta(days=random.randint(5, 30))).strftime("%Y-%m-%d")
    r = random.random()
    if r > 0.1:
        status = "通过"
        reviewed = (datetime.strptime(apply_date, "%Y-%m-%d") + timedelta(days=random.randint(1, 7))).strftime("%Y-%m-%d")
    elif r > 0.05:
        status = "拒绝"
        reviewed = (datetime.strptime(apply_date, "%Y-%m-%d") + timedelta(days=random.randint(1, 5))).strftime("%Y-%m-%d")
    else:
        status = "处理中"
        reviewed = ""
    withdrawals.append((wid, cid, round(raised * 0.99, 2), apply_date, reviewed, status))
    wid += 1

conn.executemany("INSERT INTO withdrawals VALUES (?,?,?,?,?,?)", withdrawals)
print(f"提现记录: {len(withdrawals)} 条")

conn.commit()
conn.close()
print("\n✅ shuidi.db 生成完成！")
