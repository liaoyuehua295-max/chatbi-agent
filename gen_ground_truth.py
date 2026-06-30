"""
生成100条测试题的标准答案（Ground Truth）
直接用SQL查询数据库，作为正确答案基准
"""
import sqlite3, json

conn = sqlite3.connect("shuidi.db")

# 每条问题对应的标准SQL
GROUND_TRUTH_SQL = [
    # 简单查询
    ("campaigns表一共有多少条记录",               "SELECT COUNT(*) FROM campaigns"),
    ("男性患者有多少人",                          "SELECT COUNT(*) FROM campaigns WHERE gender='男'"),
    ("女性患者有多少人",                          "SELECT COUNT(*) FROM campaigns WHERE gender='女'"),
    ("筹款状态为completed的项目有多少",           "SELECT COUNT(*) FROM campaigns WHERE status='completed'"),
    ("筹款状态为active的项目有多少",              "SELECT COUNT(*) FROM campaigns WHERE status='active'"),
    ("筹款状态为closed的项目有多少",              "SELECT COUNT(*) FROM campaigns WHERE status='closed'"),
    ("广东省有多少个筹款项目",                    "SELECT COUNT(*) FROM campaigns WHERE province='广东'"),
    ("北京市有多少个筹款项目",                    "SELECT COUNT(*) FROM campaigns WHERE city='北京'"),
    ("donations表共有多少条捐款记录",             "SELECT COUNT(*) FROM donations"),
    ("微信渠道的捐款有多少条",                    "SELECT COUNT(*) FROM donations WHERE channel='微信'"),
    ("支付宝渠道的捐款有多少条",                  "SELECT COUNT(*) FROM donations WHERE channel='支付宝'"),
    ("匿名捐款有多少条",                          "SELECT COUNT(*) FROM donations WHERE is_anonymous=1"),
    ("withdrawals表共有多少条记录",               "SELECT COUNT(*) FROM withdrawals"),
    ("提现状态为通过的有多少条",                  "SELECT COUNT(*) FROM withdrawals WHERE status='通过'"),
    ("提现状态为拒绝的有多少条",                  "SELECT COUNT(*) FROM withdrawals WHERE status='拒绝'"),
    ("staff表共有多少名员工",                     "SELECT COUNT(*) FROM staff"),
    ("职位为组长的员工有多少人",                  "SELECT COUNT(*) FROM staff WHERE title='组长'"),
    ("职位为专员的员工有多少人",                  "SELECT COUNT(*) FROM staff WHERE title='专员'"),
    ("hospitals表共有多少家医院",                 "SELECT COUNT(*) FROM hospitals"),
    ("三甲医院有多少家",                          "SELECT COUNT(*) FROM hospitals WHERE level='三甲'"),
    ("diseases表共有多少种疾病",                  "SELECT COUNT(*) FROM diseases"),
    ("regions表共有多少个大区",                   "SELECT COUNT(*) FROM regions"),
    ("teams表共有多少个团队",                     "SELECT COUNT(*) FROM teams"),
    ("70岁以上的患者有多少人",                    "SELECT COUNT(*) FROM campaigns WHERE age>70"),
    ("目标金额为50000的项目有多少个",             "SELECT COUNT(*) FROM campaigns WHERE target_amount=50000"),

    # 聚合统计
    ("所有项目的总筹款金额是多少",                "SELECT ROUND(SUM(raised_amount),2) FROM campaigns"),
    ("平均每个项目筹款多少钱",                    "SELECT ROUND(AVG(raised_amount),2) FROM campaigns"),
    ("筹款金额最高的项目是哪个",                  "SELECT campaign_id, patient_name, raised_amount FROM campaigns ORDER BY raised_amount DESC LIMIT 1"),
    ("筹款金额最低的项目是哪个",                  "SELECT campaign_id, patient_name, raised_amount FROM campaigns ORDER BY raised_amount ASC LIMIT 1"),
    ("捐款总金额是多少",                          "SELECT ROUND(SUM(amount),2) FROM donations"),
    ("平均每笔捐款金额是多少",                    "SELECT ROUND(AVG(amount),2) FROM donations"),
    ("单笔捐款最高金额是多少",                    "SELECT MAX(amount) FROM donations"),
    ("各省筹款总额排名前5",                       "SELECT province, ROUND(SUM(raised_amount),2) AS total FROM campaigns GROUP BY province ORDER BY total DESC LIMIT 5"),
    ("各省项目数量排名",                          "SELECT province, COUNT(*) AS cnt FROM campaigns GROUP BY province ORDER BY cnt DESC"),
    ("各捐款渠道的捐款总额对比",                  "SELECT channel, ROUND(SUM(amount),2) AS total FROM donations GROUP BY channel ORDER BY total DESC"),
    ("各捐款渠道的捐款笔数对比",                  "SELECT channel, COUNT(*) AS cnt FROM donations GROUP BY channel ORDER BY cnt DESC"),
    ("按性别统计平均筹款金额",                    "SELECT gender, ROUND(AVG(raised_amount),2) FROM campaigns GROUP BY gender"),
    ("按筹款状态统计项目数量",                    "SELECT status, COUNT(*) FROM campaigns GROUP BY status"),
    ("按筹款状态统计总筹款金额",                  "SELECT status, ROUND(SUM(raised_amount),2) FROM campaigns GROUP BY status"),
    ("患者年龄分布，按10岁分段统计",              "SELECT (age/10)*10 AS age_group, COUNT(*) FROM campaigns GROUP BY age_group ORDER BY age_group"),
    ("2024年每月的捐款总额趋势",                  "SELECT strftime('%Y-%m', donated_at) AS month, ROUND(SUM(amount),2) FROM donations WHERE donated_at LIKE '2024%' GROUP BY month ORDER BY month"),
    ("2023年每月新增筹款项目数",                  "SELECT strftime('%Y-%m', created_at) AS month, COUNT(*) FROM campaigns WHERE created_at LIKE '2023%' GROUP BY month ORDER BY month"),
    ("每个疾病科室的项目数量",                    "SELECT d.department, COUNT(c.campaign_id) FROM campaigns c JOIN diseases d ON c.disease_id=d.disease_id GROUP BY d.department ORDER BY COUNT(c.campaign_id) DESC"),
    ("目标金额达成率超过100%的项目有多少个",      "SELECT COUNT(*) FROM campaigns WHERE raised_amount >= target_amount"),
    ("平均每个项目的捐款人数",                    "SELECT ROUND(AVG(donor_count),2) FROM campaigns"),
    ("捐款人数最多的项目",                        "SELECT campaign_id, patient_name, donor_count FROM campaigns ORDER BY donor_count DESC LIMIT 1"),
    ("提现总金额是多少",                          "SELECT ROUND(SUM(amount),2) FROM withdrawals"),
    ("平均提现金额是多少",                        "SELECT ROUND(AVG(amount),2) FROM withdrawals"),
    ("提现审核通过率是多少",                      "SELECT ROUND(SUM(CASE WHEN status='通过' THEN 1 ELSE 0 END)*100.0/COUNT(*),2) FROM withdrawals"),
    ("按职位统计员工人数",                        "SELECT title, COUNT(*) FROM staff GROUP BY title ORDER BY COUNT(*) DESC"),
    ("每位员工负责的项目数量排名前10",            "SELECT staff_id, COUNT(*) AS cnt FROM campaigns GROUP BY staff_id ORDER BY cnt DESC LIMIT 10"),
    ("筹款金额超过目标金额的项目占比",            "SELECT ROUND(SUM(CASE WHEN raised_amount>=target_amount THEN 1 ELSE 0 END)*100.0/COUNT(*),2) FROM campaigns"),
    ("各疾病类别的平均筹款金额",                  "SELECT d.category, ROUND(AVG(c.raised_amount),2) FROM campaigns c JOIN diseases d ON c.disease_id=d.disease_id GROUP BY d.category"),
    ("住院类项目和门诊类项目的数量对比",          "SELECT d.visit_type, COUNT(*) FROM campaigns c JOIN diseases d ON c.disease_id=d.disease_id GROUP BY d.visit_type"),
    ("2024年第一季度的总捐款金额",               "SELECT ROUND(SUM(amount),2) FROM donations WHERE donated_at>='2024-01-01' AND donated_at<'2024-04-01'"),

    # 多表关联
    ("各大区的总筹款金额排名",                    "SELECT r.name, ROUND(SUM(c.raised_amount),2) AS total FROM campaigns c JOIN staff s ON c.staff_id=s.staff_id JOIN teams t ON s.team_id=t.team_id JOIN regions r ON t.region_id=r.region_id GROUP BY r.name ORDER BY total DESC"),
    ("各大区的项目数量",                          "SELECT r.name, COUNT(c.campaign_id) FROM campaigns c JOIN staff s ON c.staff_id=s.staff_id JOIN teams t ON s.team_id=t.team_id JOIN regions r ON t.region_id=r.region_id GROUP BY r.name"),
    ("各团队负责的项目数量排名",                  "SELECT t.name, COUNT(c.campaign_id) AS cnt FROM campaigns c JOIN staff s ON c.staff_id=s.staff_id JOIN teams t ON s.team_id=t.team_id GROUP BY t.name ORDER BY cnt DESC"),
    ("各团队的总筹款金额",                        "SELECT t.name, ROUND(SUM(c.raised_amount),2) FROM campaigns c JOIN staff s ON c.staff_id=s.staff_id JOIN teams t ON s.team_id=t.team_id GROUP BY t.name ORDER BY SUM(c.raised_amount) DESC"),
    ("三甲医院的筹款项目共有多少个",              "SELECT COUNT(*) FROM campaigns c JOIN hospitals h ON c.hospital_id=h.hospital_id WHERE h.level='三甲'"),
    ("三甲医院项目的平均筹款金额",               "SELECT ROUND(AVG(c.raised_amount),2) FROM campaigns c JOIN hospitals h ON c.hospital_id=h.hospital_id WHERE h.level='三甲'"),
    ("广东省三甲医院的筹款项目数量",              "SELECT COUNT(*) FROM campaigns c JOIN hospitals h ON c.hospital_id=h.hospital_id WHERE h.level='三甲' AND h.province='广东'"),
    ("肿瘤科疾病的筹款项目有多少个",              "SELECT COUNT(*) FROM campaigns c JOIN diseases d ON c.disease_id=d.disease_id WHERE d.department='肿瘤科'"),
    ("各疾病名称对应的项目数量排名前10",          "SELECT d.name, COUNT(c.campaign_id) AS cnt FROM campaigns c JOIN diseases d ON c.disease_id=d.disease_id GROUP BY d.name ORDER BY cnt DESC LIMIT 10"),
    ("筹款金额最高的前5个项目对应的医院名称",     "SELECT c.patient_name, c.raised_amount, h.name FROM campaigns c JOIN hospitals h ON c.hospital_id=h.hospital_id ORDER BY c.raised_amount DESC LIMIT 5"),
    ("每个大区的平均筹款金额",                    "SELECT r.name, ROUND(AVG(c.raised_amount),2) FROM campaigns c JOIN staff s ON c.staff_id=s.staff_id JOIN teams t ON s.team_id=t.team_id JOIN regions r ON t.region_id=r.region_id GROUP BY r.name"),
    ("捐款人数最多的前5个项目的疾病名称",         "SELECT c.patient_name, c.donor_count, d.name FROM campaigns c JOIN diseases d ON c.disease_id=d.disease_id ORDER BY c.donor_count DESC LIMIT 5"),
    ("各省的三甲医院数量",                        "SELECT province, COUNT(*) FROM hospitals WHERE level='三甲' GROUP BY province ORDER BY COUNT(*) DESC"),
    ("每个团队的提现通过总金额",                  "SELECT t.name, ROUND(SUM(w.amount),2) FROM withdrawals w JOIN campaigns c ON w.campaign_id=c.campaign_id JOIN staff s ON c.staff_id=s.staff_id JOIN teams t ON s.team_id=t.team_id WHERE w.status='通过' GROUP BY t.name ORDER BY SUM(w.amount) DESC"),
    ("北京大区下有多少个团队",                    "SELECT COUNT(*) FROM teams t JOIN regions r ON t.region_id=r.region_id WHERE r.name LIKE '%北京%'"),
    ("每位组长负责的项目数量",                    "SELECT s.name, COUNT(c.campaign_id) AS cnt FROM campaigns c JOIN staff s ON c.staff_id=s.staff_id WHERE s.title='组长' GROUP BY s.name ORDER BY cnt DESC"),
    ("微信渠道捐款最多的前5个项目",               "SELECT c.campaign_id, c.patient_name, ROUND(SUM(d.amount),2) AS total FROM donations d JOIN campaigns c ON d.campaign_id=c.campaign_id WHERE d.channel='微信' GROUP BY c.campaign_id ORDER BY total DESC LIMIT 5"),
    ("各大区的提现通过率对比",                    "SELECT r.name, ROUND(SUM(CASE WHEN w.status='通过' THEN 1 ELSE 0 END)*100.0/COUNT(*),2) FROM withdrawals w JOIN campaigns c ON w.campaign_id=c.campaign_id JOIN staff s ON c.staff_id=s.staff_id JOIN teams t ON s.team_id=t.team_id JOIN regions r ON t.region_id=r.region_id GROUP BY r.name"),
    ("住院类疾病的总筹款金额",                    "SELECT ROUND(SUM(c.raised_amount),2) FROM campaigns c JOIN diseases d ON c.disease_id=d.disease_id WHERE d.visit_type='住院'"),
    ("门诊类疾病的平均筹款金额",                  "SELECT ROUND(AVG(c.raised_amount),2) FROM campaigns c JOIN diseases d ON c.disease_id=d.disease_id WHERE d.visit_type='门诊'"),
    ("每个大区筹款成功项目的数量",                "SELECT r.name, COUNT(c.campaign_id) FROM campaigns c JOIN staff s ON c.staff_id=s.staff_id JOIN teams t ON s.team_id=t.team_id JOIN regions r ON t.region_id=r.region_id WHERE c.status='completed' GROUP BY r.name"),
    ("内科疾病的筹款项目有多少",                  "SELECT COUNT(*) FROM campaigns c JOIN diseases d ON c.disease_id=d.disease_id WHERE d.department='内科'"),
    ("外科疾病的平均筹款金额",                    "SELECT ROUND(AVG(c.raised_amount),2) FROM campaigns c JOIN diseases d ON c.disease_id=d.disease_id WHERE d.department='外科'"),
    ("各省的平均捐款金额",                        "SELECT c.province, ROUND(AVG(d.amount),2) FROM donations d JOIN campaigns c ON d.campaign_id=c.campaign_id GROUP BY c.province ORDER BY AVG(d.amount) DESC"),
    ("每个团队的平均项目筹款金额",                "SELECT t.name, ROUND(AVG(c.raised_amount),2) FROM campaigns c JOIN staff s ON c.staff_id=s.staff_id JOIN teams t ON s.team_id=t.team_id GROUP BY t.name ORDER BY AVG(c.raised_amount) DESC"),
    ("筹款完成率最高的前5个省份",                 "SELECT province, ROUND(AVG(raised_amount*100.0/target_amount),2) AS rate FROM campaigns GROUP BY province ORDER BY rate DESC LIMIT 5"),
    ("各大区下属团队数量",                        "SELECT r.name, COUNT(t.team_id) FROM teams t JOIN regions r ON t.region_id=r.region_id GROUP BY r.name"),
    ("捐款总额最高的前3个省份对应的大区",         "SELECT c.province, ROUND(SUM(d.amount),2) AS total, r.name FROM donations d JOIN campaigns c ON d.campaign_id=c.campaign_id JOIN staff s ON c.staff_id=s.staff_id JOIN teams t ON s.team_id=t.team_id JOIN regions r ON t.region_id=r.region_id GROUP BY c.province ORDER BY total DESC LIMIT 3"),
    ("每家医院的筹款项目数量排名前10",            "SELECT h.name, COUNT(c.campaign_id) AS cnt FROM campaigns c JOIN hospitals h ON c.hospital_id=h.hospital_id GROUP BY h.name ORDER BY cnt DESC LIMIT 10"),
    ("三甲医院项目的提现通过率",                  "SELECT ROUND(SUM(CASE WHEN w.status='通过' THEN 1 ELSE 0 END)*100.0/COUNT(*),2) FROM withdrawals w JOIN campaigns c ON w.campaign_id=c.campaign_id JOIN hospitals h ON c.hospital_id=h.hospital_id WHERE h.level='三甲'"),

    # 歧义易错（用合理的SQL解释）
    ("筹款进行中的项目有哪些",                    "SELECT campaign_id, patient_name, raised_amount FROM campaigns WHERE status='active' LIMIT 10"),
    ("已经关闭的项目平均筹了多少钱",              "SELECT ROUND(AVG(raised_amount),2) FROM campaigns WHERE status='closed'"),
    ("哪个员工业绩最好",                          "SELECT s.name, ROUND(SUM(c.raised_amount),2) AS total FROM campaigns c JOIN staff s ON c.staff_id=s.staff_id GROUP BY s.name ORDER BY total DESC LIMIT 1"),
    ("最近一个月新增了多少筹款项目",              "SELECT COUNT(*) FROM campaigns WHERE created_at >= date('now','-1 month')"),
    ("筹款效率最高的团队",                        "SELECT t.name, ROUND(AVG(c.raised_amount*100.0/c.target_amount),2) AS rate FROM campaigns c JOIN staff s ON c.staff_id=s.staff_id JOIN teams t ON s.team_id=t.team_id GROUP BY t.name ORDER BY rate DESC LIMIT 1"),
    ("每个staff的平均筹款金额",                   "SELECT s.name, ROUND(AVG(c.raised_amount),2) FROM campaigns c JOIN staff s ON c.staff_id=s.staff_id GROUP BY s.name ORDER BY AVG(c.raised_amount) DESC LIMIT 10"),
    ("捐款金额分布情况",                          "SELECT CASE WHEN amount<100 THEN '<100' WHEN amount<500 THEN '100-500' WHEN amount<1000 THEN '500-1000' ELSE '>=1000' END AS range, COUNT(*) FROM donations GROUP BY range"),
    ("哪个渠道的用户最慷慨",                      "SELECT channel, ROUND(AVG(amount),2) AS avg_amount FROM donations GROUP BY channel ORDER BY avg_amount DESC LIMIT 1"),
    ("项目成功率最高的省份",                      "SELECT province, ROUND(SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END)*100.0/COUNT(*),2) AS rate FROM campaigns GROUP BY province ORDER BY rate DESC LIMIT 5"),
    ("老年患者的筹款情况",                        "SELECT COUNT(*), ROUND(AVG(raised_amount),2), ROUND(SUM(raised_amount),2) FROM campaigns WHERE age>=60"),
    ("儿童患者有多少",                            "SELECT COUNT(*) FROM campaigns WHERE age<=14"),
    ("大病项目的筹款情况",                        "SELECT d.category, COUNT(*), ROUND(AVG(c.raised_amount),2) FROM campaigns c JOIN diseases d ON c.disease_id=d.disease_id WHERE d.category='重症' GROUP BY d.category"),
    ("哪个大区表现最好",                          "SELECT r.name, ROUND(SUM(c.raised_amount),2) AS total FROM campaigns c JOIN staff s ON c.staff_id=s.staff_id JOIN teams t ON s.team_id=t.team_id JOIN regions r ON t.region_id=r.region_id GROUP BY r.name ORDER BY total DESC LIMIT 1"),
    ("捐款最活跃的时间段",                        "SELECT strftime('%H', donated_at) AS hour, COUNT(*) AS cnt FROM donations GROUP BY hour ORDER BY cnt DESC LIMIT 5"),
    ("最难筹到钱的疾病类型",                      "SELECT d.category, ROUND(AVG(c.raised_amount*100.0/c.target_amount),2) AS rate FROM campaigns c JOIN diseases d ON c.disease_id=d.disease_id GROUP BY d.category ORDER BY rate ASC LIMIT 3"),
]

# 执行所有SQL获取标准答案
results = []
for q, sql in GROUND_TRUTH_SQL:
    try:
        rows = conn.execute(sql).fetchall()
        answer = str(rows[:5])  # 只取前5行
        results.append({"question": q, "sql": sql, "answer": answer, "status": "ok"})
    except Exception as e:
        results.append({"question": q, "sql": sql, "answer": "", "status": f"error:{e}"})

conn.close()

# 保存
with open("ground_truth.json", "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

ok = sum(1 for r in results if r["status"] == "ok")
print(f"标准答案生成完成：{ok}/{len(results)} 条成功")
errors = [r for r in results if r["status"] != "ok"]
if errors:
    print("失败的SQL：")
    for r in errors:
        print(f"  {r['question']} → {r['status']}")
