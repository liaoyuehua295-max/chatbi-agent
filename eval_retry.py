"""
重试机制效果测评
对比：不带重试 vs 带重试（最多3次）的SQL执行成功率
"""
import os, time
from dotenv import load_dotenv
from agent import ChatBIAgent

load_dotenv()
API_KEY = os.getenv("DASHSCOPE_API_KEY", "")
BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
MODEL = "qwen-plus"

# 10条测试问题，覆盖三种难度
TEST_CASES = [
    # 简单查询（5条）
    {"q": "各省筹款总额排名前5",          "level": "简单"},
    {"q": "男女患者各有多少人",            "level": "简单"},
    {"q": "每个疾病科室的项目数量",        "level": "简单"},
    {"q": "捐款渠道分布统计",              "level": "简单"},
    {"q": "筹款成功（status=completed）的项目有多少", "level": "简单"},

    # 歧义/易错查询（3条）
    {"q": "每个team的平均筹款金额",        "level": "歧义"},
    {"q": "提现审核通过率是多少",          "level": "歧义"},
    {"q": "每个staff负责的项目里平均捐款人数", "level": "歧义"},

    # 多表关联（2条）
    {"q": "各大区（region）的总筹款金额排名",  "level": "多表"},
    {"q": "三甲医院中筹款金额最高的前3个项目", "level": "多表"},
]


def run_once(agent: ChatBIAgent, question: str) -> bool:
    """不带重试，直接调用，返回是否SQL执行成功"""
    try:
        result = agent.chat(question, enable_insight=False)
        sql = result.get("sql", "")
        answer = result.get("answer", "")
        # 判断失败：没有SQL，或者answer里有错误关键词
        if not sql:
            return False
        fail_keywords = ["SQL执行错误", "执行失败", "无法查询", "找不到", "error", "Error"]
        if any(k in answer for k in fail_keywords):
            return False
        return True
    except Exception:
        return False


def run_with_retry(agent: ChatBIAgent, question: str) -> bool:
    """带重试，调用 _run_with_retry"""
    try:
        from langchain_core.messages import HumanMessage
        messages = [HumanMessage(content=question)]
        result = agent._run_with_retry(messages, max_retries=3)
        all_msgs = result.get("messages", [])
        # 检查最后一条tool message是否有错误
        for msg in reversed(all_msgs):
            if hasattr(msg, "name") and msg.name == "run_sql_query":
                if "SQL执行错误" in msg.content:
                    return False
                break
        return True
    except Exception:
        return False


def main():
    agent = ChatBIAgent(API_KEY, BASE_URL, MODEL)

    print("=" * 60)
    print("测评开始：不带重试 vs 带重试")
    print("=" * 60)

    no_retry_results = []
    retry_results = []

    for i, case in enumerate(TEST_CASES, 1):
        q = case["q"]
        level = case["level"]
        print(f"\n[{i:02d}] [{level}] {q}")

        # 不带重试
        t0 = time.time()
        r1 = run_once(agent, q)
        t1 = time.time()
        no_retry_results.append(r1)
        print(f"  无重试: {'✓ 成功' if r1 else '✗ 失败'}  ({t1-t0:.1f}s)")

        time.sleep(1)  # 避免限流

        # 带重试（只对上一步失败的才测，节省API费用）
        if not r1:
            t0 = time.time()
            r2 = run_with_retry(agent, q)
            t1 = time.time()
            print(f"  带重试: {'✓ 成功' if r2 else '✗ 失败'}  ({t1-t0:.1f}s)")
        else:
            r2 = True  # 无重试已成功，重试也必然成功
            print(f"  带重试: ✓ 无需重试")
        retry_results.append(r2)

        time.sleep(1)

    # 汇总
    n = len(TEST_CASES)
    no_retry_ok = sum(no_retry_results)
    retry_ok = sum(retry_results)

    print("\n" + "=" * 60)
    print("测评结果汇总")
    print("=" * 60)
    print(f"总题数：{n}")
    print(f"无重试成功率：{no_retry_ok}/{n} = {no_retry_ok/n*100:.0f}%")
    print(f"带重试成功率：{retry_ok}/{n} = {retry_ok/n*100:.0f}%")
    print(f"重试机制提升：+{(retry_ok-no_retry_ok)/n*100:.0f}个百分点")

    print("\n各题明细：")
    for i, case in enumerate(TEST_CASES):
        r1 = "✓" if no_retry_results[i] else "✗"
        r2 = "✓" if retry_results[i] else "✗"
        print(f"  [{case['level']}] {case['q'][:30]:30s}  无重试:{r1}  带重试:{r2}")


if __name__ == "__main__":
    main()
