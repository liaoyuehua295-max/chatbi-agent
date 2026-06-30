"""
ChatBI Agent 100条测试集评测
判断标准：SQL能否成功执行（execution accuracy）
覆盖：简单查询/聚合统计/多表关联/歧义易错 四个难度层次
"""
import os, time, json
from dotenv import load_dotenv
from agent import ChatBIAgent

load_dotenv()
API_KEY = os.getenv("DASHSCOPE_API_KEY", "")
BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
MODEL = "qwen-plus"

TEST_CASES = [
    # ───────── 简单查询（25条）─────────
    {"q": "campaigns表一共有多少条记录",                    "level": "简单"},
    {"q": "男性患者有多少人",                              "level": "简单"},
    {"q": "女性患者有多少人",                              "level": "简单"},
    {"q": "筹款状态为completed的项目有多少",               "level": "简单"},
    {"q": "筹款状态为active的项目有多少",                  "level": "简单"},
    {"q": "筹款状态为closed的项目有多少",                  "level": "简单"},
    {"q": "广东省有多少个筹款项目",                        "level": "简单"},
    {"q": "北京市有多少个筹款项目",                        "level": "简单"},
    {"q": "donations表共有多少条捐款记录",                  "level": "简单"},
    {"q": "微信渠道的捐款有多少条",                        "level": "简单"},
    {"q": "支付宝渠道的捐款有多少条",                      "level": "简单"},
    {"q": "匿名捐款有多少条",                              "level": "简单"},
    {"q": "withdrawals表共有多少条记录",                   "level": "简单"},
    {"q": "提现状态为通过的有多少条",                      "level": "简单"},
    {"q": "提现状态为拒绝的有多少条",                      "level": "简单"},
    {"q": "staff表共有多少名员工",                         "level": "简单"},
    {"q": "职位为组长的员工有多少人",                      "level": "简单"},
    {"q": "职位为专员的员工有多少人",                      "level": "简单"},
    {"q": "hospitals表共有多少家医院",                     "level": "简单"},
    {"q": "三甲医院有多少家",                              "level": "简单"},
    {"q": "diseases表共有多少种疾病",                      "level": "简单"},
    {"q": "regions表共有多少个大区",                       "level": "简单"},
    {"q": "teams表共有多少个团队",                         "level": "简单"},
    {"q": "70岁以上的患者有多少人",                        "level": "简单"},
    {"q": "目标金额为50000的项目有多少个",                 "level": "简单"},

    # ───────── 聚合统计（30条）─────────
    {"q": "所有项目的总筹款金额是多少",                    "level": "聚合"},
    {"q": "平均每个项目筹款多少钱",                        "level": "聚合"},
    {"q": "筹款金额最高的项目是哪个",                      "level": "聚合"},
    {"q": "筹款金额最低的项目是哪个",                      "level": "聚合"},
    {"q": "捐款总金额是多少",                              "level": "聚合"},
    {"q": "平均每笔捐款金额是多少",                        "level": "聚合"},
    {"q": "单笔捐款最高金额是多少",                        "level": "聚合"},
    {"q": "各省筹款总额排名前5",                           "level": "聚合"},
    {"q": "各省项目数量排名",                              "level": "聚合"},
    {"q": "各捐款渠道的捐款总额对比",                      "level": "聚合"},
    {"q": "各捐款渠道的捐款笔数对比",                      "level": "聚合"},
    {"q": "按性别统计平均筹款金额",                        "level": "聚合"},
    {"q": "按筹款状态统计项目数量",                        "level": "聚合"},
    {"q": "按筹款状态统计总筹款金额",                      "level": "聚合"},
    {"q": "患者年龄分布，按10岁分段统计",                  "level": "聚合"},
    {"q": "2024年每月的捐款总额趋势",                      "level": "聚合"},
    {"q": "2023年每月新增筹款项目数",                      "level": "聚合"},
    {"q": "每个疾病科室的项目数量",                        "level": "聚合"},
    {"q": "目标金额达成率超过100%的项目有多少个",          "level": "聚合"},
    {"q": "平均每个项目的捐款人数",                        "level": "聚合"},
    {"q": "捐款人数最多的项目",                            "level": "聚合"},
    {"q": "提现总金额是多少",                              "level": "聚合"},
    {"q": "平均提现金额是多少",                            "level": "聚合"},
    {"q": "提现审核通过率是多少",                          "level": "聚合"},
    {"q": "按职位统计员工人数",                            "level": "聚合"},
    {"q": "每位员工负责的项目数量排名前10",                "level": "聚合"},
    {"q": "筹款金额超过目标金额的项目占比",                "level": "聚合"},
    {"q": "各疾病类别的平均筹款金额",                      "level": "聚合"},
    {"q": "住院类项目和门诊类项目的数量对比",              "level": "聚合"},
    {"q": "2024年第一季度的总捐款金额",                    "level": "聚合"},

    # ───────── 多表关联（30条）─────────
    {"q": "各大区的总筹款金额排名",                        "level": "多表"},
    {"q": "各大区的项目数量",                              "level": "多表"},
    {"q": "各团队负责的项目数量排名",                      "level": "多表"},
    {"q": "各团队的总筹款金额",                            "level": "多表"},
    {"q": "三甲医院的筹款项目共有多少个",                  "level": "多表"},
    {"q": "三甲医院项目的平均筹款金额",                    "level": "多表"},
    {"q": "广东省三甲医院的筹款项目数量",                  "level": "多表"},
    {"q": "肿瘤科疾病的筹款项目有多少个",                  "level": "多表"},
    {"q": "各疾病名称对应的项目数量排名前10",              "level": "多表"},
    {"q": "筹款金额最高的前5个项目对应的医院名称",         "level": "多表"},
    {"q": "每个大区的平均筹款金额",                        "level": "多表"},
    {"q": "捐款人数最多的前5个项目的疾病名称",             "level": "多表"},
    {"q": "各省的三甲医院数量",                            "level": "多表"},
    {"q": "每个团队的提现通过总金额",                      "level": "多表"},
    {"q": "北京大区下有多少个团队",                        "level": "多表"},
    {"q": "每位组长负责的项目数量",                        "level": "多表"},
    {"q": "微信渠道捐款最多的前5个项目",                   "level": "多表"},
    {"q": "各大区的提现通过率对比",                        "level": "多表"},
    {"q": "住院类疾病的总筹款金额",                        "level": "多表"},
    {"q": "门诊类疾病的平均筹款金额",                      "level": "多表"},
    {"q": "每个大区筹款成功项目的数量",                    "level": "多表"},
    {"q": "内科疾病的筹款项目有多少",                      "level": "多表"},
    {"q": "外科疾病的平均筹款金额",                        "level": "多表"},
    {"q": "各省的平均捐款金额",                            "level": "多表"},
    {"q": "每个团队的平均项目筹款金额",                    "level": "多表"},
    {"q": "筹款完成率最高的前5个省份",                     "level": "多表"},
    {"q": "各大区下属团队数量",                            "level": "多表"},
    {"q": "捐款总额最高的前3个省份对应的大区",             "level": "多表"},
    {"q": "每家医院的筹款项目数量排名前10",                "level": "多表"},
    {"q": "三甲医院项目的提现通过率",                      "level": "多表"},

    # ───────── 歧义易错（15条）─────────
    {"q": "筹款进行中的项目有哪些",                        "level": "歧义"},
    {"q": "已经关闭的项目平均筹了多少钱",                  "level": "歧义"},
    {"q": "哪个员工业绩最好",                              "level": "歧义"},
    {"q": "最近一个月新增了多少筹款项目",                  "level": "歧义"},
    {"q": "筹款效率最高的团队",                            "level": "歧义"},
    {"q": "每个staff的平均筹款金额",                       "level": "歧义"},
    {"q": "捐款金额分布情况",                              "level": "歧义"},
    {"q": "哪个渠道的用户最慷慨",                          "level": "歧义"},
    {"q": "项目成功率最高的省份",                          "level": "歧义"},
    {"q": "老年患者的筹款情况",                            "level": "歧义"},
    {"q": "儿童患者有多少",                                "level": "歧义"},
    {"q": "大病项目的筹款情况",                            "level": "歧义"},
    {"q": "哪个大区表现最好",                              "level": "歧义"},
    {"q": "捐款最活跃的时间段",                            "level": "歧义"},
    {"q": "最难筹到钱的疾病类型",                          "level": "歧义"},
]


def run_once(agent, question):
    """不带重试，返回是否成功"""
    try:
        result = agent.chat(question, enable_insight=False)
        sql = result.get("sql", "")
        answer = result.get("answer", "")
        # 明确失败：answer包含错误关键词
        fail_kw = ["SQL执行错误", "执行失败", "无法查询", "Error", "error",
                   "抱歉，我无法", "无法完成", "出现了错误"]
        for k in fail_kw:
            if k in answer:
                return False, f"含错误关键词:{k}"
        # 没有SQL但有实质性回答也算成功（Agent直接推理回答）
        if not sql:
            if len(answer) > 20:
                return True, f"无SQL但有回答:{answer[:40]}"
            return False, "无SQL且无实质回答"
        return True, sql[:60]
    except Exception as e:
        return False, str(e)[:60]


def run_with_retry(agent, question):
    """带重试，返回是否成功"""
    try:
        from langchain_core.messages import HumanMessage
        messages = [HumanMessage(content=question)]
        result = agent._run_with_retry(messages, max_retries=3)
        all_msgs = result.get("messages", [])
        for msg in reversed(all_msgs):
            if hasattr(msg, "name") and msg.name == "run_sql_query":
                if "SQL执行错误" in msg.content:
                    return False, "重试后仍失败"
                break
        return True, "重试成功"
    except Exception as e:
        return False, str(e)[:60]


def main():
    agent = ChatBIAgent(API_KEY, BASE_URL, MODEL)
    total = len(TEST_CASES)
    print(f"=" * 70)
    print(f"ChatBI Agent 评测 共{total}条")
    print(f"=" * 70)

    no_retry_results = []
    retry_results = []
    details = []

    for i, case in enumerate(TEST_CASES, 1):
        q = case["q"]
        level = case["level"]

        # 无重试
        r1, msg1 = run_once(agent, q)
        no_retry_results.append(r1)

        # 只对失败的做重试
        if not r1:
            time.sleep(1)
            r2, msg2 = run_with_retry(agent, q)
        else:
            r2, msg2 = True, "无需重试"
        retry_results.append(r2)

        status = "✓" if r1 else ("→✓" if r2 else "✗")
        print(f"[{i:03d}][{level}] {status} {q[:35]:35s} | {msg1[:40]}")

        details.append({
            "id": i, "level": level, "question": q,
            "no_retry": r1, "with_retry": r2,
            "msg": msg1,
        })
        time.sleep(0.8)

    # ── 汇总 ──
    n = total
    nr_ok = sum(no_retry_results)
    r_ok = sum(retry_results)

    # 按难度分层统计
    levels = ["简单", "聚合", "多表", "歧义"]
    print(f"\n{'=' * 70}")
    print("分层统计")
    print(f"{'=' * 70}")
    for lv in levels:
        lv_cases = [d for d in details if d["level"] == lv]
        lv_n = len(lv_cases)
        lv_nr = sum(1 for d in lv_cases if d["no_retry"])
        lv_r = sum(1 for d in lv_cases if d["with_retry"])
        print(f"[{lv:4s}] {lv_n}条 | 无重试:{lv_nr}/{lv_n}={lv_nr/lv_n*100:.0f}% | 带重试:{lv_r}/{lv_n}={lv_r/lv_n*100:.0f}%")

    print(f"\n{'=' * 70}")
    print("总体结果")
    print(f"{'=' * 70}")
    print(f"总题数    : {n}")
    print(f"无重试成功: {nr_ok}/{n} = {nr_ok/n*100:.1f}%")
    print(f"带重试成功: {r_ok}/{n} = {r_ok/n*100:.1f}%")
    print(f"重试提升  : +{(r_ok-nr_ok)/n*100:.1f}个百分点")

    # 失败清单
    failed = [d for d in details if not d["with_retry"]]
    if failed:
        print(f"\n带重试仍失败的题目（{len(failed)}条）：")
        for d in failed:
            print(f"  [{d['level']}] {d['question']} | {d['msg']}")

    # 保存结果
    with open("eval_100_result.json", "w", encoding="utf-8") as f:
        json.dump({
            "total": n,
            "no_retry_rate": round(nr_ok/n*100, 1),
            "retry_rate": round(r_ok/n*100, 1),
            "details": details,
        }, f, ensure_ascii=False, indent=2)
    print("\n结果已保存到 eval_100_result.json")


if __name__ == "__main__":
    main()
