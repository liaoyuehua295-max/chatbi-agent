"""
结果准确性评测 (Answer Accuracy)
从Agent回答中提取关键数值，与标准SQL查询结果对比
重点评测30条有确定性数值答案的题目（简单查询+部分聚合）
"""
import os, re, time, json, sqlite3
from dotenv import load_dotenv
from agent import ChatBIAgent

load_dotenv()
API_KEY = os.getenv("DASHSCOPE_API_KEY", "")
BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
MODEL = "qwen-plus"

conn = sqlite3.connect("shuidi.db")

# 只选有明确单一数值答案的30条题目，适合做准确性校验
EVAL_CASES = [
    # 简单计数（标准答案是单个数字）
    ("campaigns表一共有多少条记录",         "SELECT COUNT(*) FROM campaigns"),
    ("男性患者有多少人",                    "SELECT COUNT(*) FROM campaigns WHERE gender='男'"),
    ("女性患者有多少人",                    "SELECT COUNT(*) FROM campaigns WHERE gender='女'"),
    ("筹款状态为completed的项目有多少",     "SELECT COUNT(*) FROM campaigns WHERE status='completed'"),
    ("筹款状态为active的项目有多少",        "SELECT COUNT(*) FROM campaigns WHERE status='active'"),
    ("筹款状态为closed的项目有多少",        "SELECT COUNT(*) FROM campaigns WHERE status='closed'"),
    ("广东省有多少个筹款项目",              "SELECT COUNT(*) FROM campaigns WHERE province='广东'"),
    ("donations表共有多少条捐款记录",       "SELECT COUNT(*) FROM donations"),
    ("微信渠道的捐款有多少条",              "SELECT COUNT(*) FROM donations WHERE channel='微信'"),
    ("支付宝渠道的捐款有多少条",            "SELECT COUNT(*) FROM donations WHERE channel='支付宝'"),
    ("匿名捐款有多少条",                    "SELECT COUNT(*) FROM donations WHERE is_anonymous=1"),
    ("withdrawals表共有多少条记录",         "SELECT COUNT(*) FROM withdrawals"),
    ("提现状态为通过的有多少条",            "SELECT COUNT(*) FROM withdrawals WHERE status='通过'"),
    ("提现状态为拒绝的有多少条",            "SELECT COUNT(*) FROM withdrawals WHERE status='拒绝'"),
    ("staff表共有多少名员工",               "SELECT COUNT(*) FROM staff"),
    ("hospitals表共有多少家医院",           "SELECT COUNT(*) FROM hospitals"),
    ("三甲医院有多少家",                    "SELECT COUNT(*) FROM hospitals WHERE level='三甲'"),
    ("diseases表共有多少种疾病",            "SELECT COUNT(*) FROM diseases"),
    ("70岁以上的患者有多少人",              "SELECT COUNT(*) FROM campaigns WHERE age>70"),
    ("目标金额达成率超过100%的项目有多少个","SELECT COUNT(*) FROM campaigns WHERE raised_amount >= target_amount"),

    # 聚合（单一数值）
    ("所有项目的总筹款金额是多少",          "SELECT ROUND(SUM(raised_amount),2) FROM campaigns"),
    ("平均每个项目筹款多少钱",              "SELECT ROUND(AVG(raised_amount),2) FROM campaigns"),
    ("捐款总金额是多少",                    "SELECT ROUND(SUM(amount),2) FROM donations"),
    ("平均每笔捐款金额是多少",              "SELECT ROUND(AVG(amount),2) FROM donations"),
    ("单笔捐款最高金额是多少",              "SELECT MAX(amount) FROM donations"),
    ("提现总金额是多少",                    "SELECT ROUND(SUM(amount),2) FROM withdrawals"),
    ("平均提现金额是多少",                  "SELECT ROUND(AVG(amount),2) FROM withdrawals"),
    ("三甲医院的筹款项目共有多少个",        "SELECT COUNT(*) FROM campaigns c JOIN hospitals h ON c.hospital_id=h.hospital_id WHERE h.level='三甲'"),
    ("肿瘤科疾病的筹款项目有多少个",        "SELECT COUNT(*) FROM campaigns c JOIN diseases d ON c.disease_id=d.disease_id WHERE d.department='肿瘤科'"),
    ("内科疾病的筹款项目有多少",            "SELECT COUNT(*) FROM campaigns c JOIN diseases d ON c.disease_id=d.disease_id WHERE d.department='内科'"),
]


def get_ground_truth(sql: str) -> str:
    """执行标准SQL，返回第一个值的字符串"""
    rows = conn.execute(sql).fetchone()
    if rows:
        val = rows[0]
        # 格式化浮点数
        if isinstance(val, float):
            return f"{val:.2f}"
        return str(val)
    return "NULL"


def extract_number_from_text(text: str) -> list[str]:
    """从Agent回答里提取所有数字"""
    # 匹配整数和小数，包括带逗号千分位格式
    nums = re.findall(r"\b\d{1,3}(?:,\d{3})*(?:\.\d+)?\b|\b\d+(?:\.\d+)?\b", text)
    # 去掉千分位逗号，标准化
    result = []
    for n in nums:
        cleaned = n.replace(",", "")
        try:
            f = float(cleaned)
            # 格式化对齐：如果是整数就不加小数点
            if f == int(f):
                result.append(str(int(f)))
            else:
                result.append(f"{f:.2f}")
        except:
            pass
    return result


def numbers_match(agent_nums: list[str], truth: str) -> bool:
    """判断标准答案是否出现在Agent提取的数字列表中"""
    truth_clean = truth.replace(",", "")
    try:
        truth_f = float(truth_clean)
        if truth_f == int(truth_f):
            truth_norm = str(int(truth_f))
        else:
            truth_norm = f"{truth_f:.2f}"
    except:
        truth_norm = truth

    return truth_norm in agent_nums


def main():
    agent = ChatBIAgent(API_KEY, BASE_URL, MODEL)
    total = len(EVAL_CASES)
    print(f"{'='*70}")
    print(f"结果准确性评测  共{total}条（单值答案题目）")
    print(f"{'='*70}")

    results = []
    correct = 0
    wrong = 0
    nonum = 0

    for i, (q, sql) in enumerate(EVAL_CASES, 1):
        truth = get_ground_truth(sql)

        # 用带重试的方式调用Agent
        try:
            result = agent.chat(q, enable_insight=False)
            answer = result.get("answer", "")
        except Exception as e:
            answer = f"ERROR:{e}"

        agent_nums = extract_number_from_text(answer)
        matched = numbers_match(agent_nums, truth)

        if not agent_nums:
            status = "??"  # 无数字提取
            nonum += 1
        elif matched:
            status = "✓"
            correct += 1
        else:
            status = "✗"
            wrong += 1

        flag = "OK" if status == "✓" else ("??" if status == "??" else "XX")
        print(f"[{i:02d}] {flag} | 标准:{truth:>12s} | 提取:{str(agent_nums[:3]):30s} | {q[:30]}")
        results.append({
            "id": i, "question": q, "truth": truth,
            "agent_nums": agent_nums[:5], "answer_snippet": answer[:100],
            "matched": matched, "has_nums": bool(agent_nums),
        })
        time.sleep(1)

    print(f"\n{'='*70}")
    print(f"准确性评测结果")
    print(f"{'='*70}")
    print(f"总题数     : {total}")
    print(f"答案正确   : {correct}/{total} = {correct/total*100:.1f}%")
    print(f"答案错误   : {wrong}/{total} = {wrong/total*100:.1f}%")
    print(f"无数字提取 : {nonum}/{total} = {nonum/total*100:.1f}%")

    wrong_cases = [r for r in results if not r["matched"]]
    if wrong_cases:
        print(f"\n错误/无法判断的题目（{len(wrong_cases)}条）：")
        for r in wrong_cases:
            flag = "??" if not r["has_nums"] else "XX"
            print(f"  [{flag}] {r['question']}")
            print(f"       标准:{r['truth']}  提取:{r['agent_nums']}")

    conn.close()
    with open("eval_accuracy_result.json", "w", encoding="utf-8") as f:
        json.dump({
            "total": total, "correct": correct, "wrong": wrong, "nonum": nonum,
            "accuracy": round(correct/total*100, 1),
            "details": results,
        }, f, ensure_ascii=False, indent=2)
    print("\n结果已保存到 eval_accuracy_result.json")


if __name__ == "__main__":
    main()
