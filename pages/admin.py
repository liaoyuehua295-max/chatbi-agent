import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import streamlit as st
import pandas as pd
import sqlite3
from logger import get_all_logs, update_feedback
import rag
from rag import reset_vectorstore

st.set_page_config(page_title="运营后台", page_icon="🛠️", layout="wide")

# ── 密码验证 ──────────────────────────────────────────
ADMIN_PASSWORD = "chatbi2024"

if "admin_authed" not in st.session_state:
    st.session_state["admin_authed"] = False

if not st.session_state["admin_authed"]:
    st.title("🔐 后台登录")
    pwd = st.text_input("请输入管理员密码", type="password")
    if st.button("登录"):
        if pwd == ADMIN_PASSWORD:
            st.session_state["admin_authed"] = True
            st.rerun()
        else:
            st.error("密码错误")
    st.stop()

# ── 已登录 ────────────────────────────────────────────
st.title("🛠️ 运营后台")
col_title, col_logout = st.columns([8, 1])
with col_logout:
    if st.button("退出登录"):
        st.session_state["admin_authed"] = False
        st.rerun()

tab_logs, tab_data, tab_clean, tab_kb = st.tabs(["📋 查询日志", "🗃️ 数据集预览", "🧹 数据清洗", "📝 知识库编辑"])

# ════════════════════════════════════════════════════════
# TAB 1: 查询日志
# ════════════════════════════════════════════════════════
with tab_logs:
    df_logs = get_all_logs(500)

    if df_logs.empty:
        st.info("暂无数据，先去前端问几个问题吧")
    else:
        total = len(df_logs)
        error_count = int(df_logs["has_error"].sum())
        thumbs_up = int((df_logs["feedback"] == 1).sum())
        thumbs_down = int((df_logs["feedback"] == -1).sum())
        empty_count = int((df_logs["row_count"] == 0).sum())

        unique_users = df_logs["user_name"].nunique()
        c1, c2, c3, c4, c5, c6 = st.columns(6)
        c1.metric("总查询", total)
        c2.metric("👥 用户数", unique_users)
        c3.metric("👍 点赞", thumbs_up)
        c4.metric("👎 点踩", thumbs_down)
        c5.metric("❌ SQL报错", error_count)
        c6.metric("⚠️ 空数据", empty_count)

        st.divider()

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            filter_type = st.selectbox("筛选类型", ["全部", "👎 差评", "❌ 报错", "⚠️ 空数据", "👍 好评"])
        with col2:
            all_users = ["全部用户"] + sorted(df_logs["user_name"].dropna().unique().tolist())
            filter_user = st.selectbox("筛选用户", all_users)
        with col3:
            keyword = st.text_input("关键词（问题/SQL）")
        with col4:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("🔄 刷新"):
                st.rerun()

        filtered = df_logs.copy()
        if filter_type == "👎 差评":
            filtered = filtered[filtered["feedback"] == -1]
        elif filter_type == "❌ 报错":
            filtered = filtered[filtered["has_error"] == 1]
        elif filter_type == "⚠️ 空数据":
            filtered = filtered[filtered["row_count"] == 0]
        elif filter_type == "👍 好评":
            filtered = filtered[filtered["feedback"] == 1]
        if filter_user != "全部用户":
            filtered = filtered[filtered["user_name"] == filter_user]
        if keyword:
            mask = (
                filtered["question"].str.contains(keyword, case=False, na=False) |
                filtered["sql"].str.contains(keyword, case=False, na=False)
            )
            filtered = filtered[mask]

        st.markdown(f"**共 {len(filtered)} 条**")

        for _, row in filtered.iterrows():
            fb_icon = {1: "👍", -1: "👎", 0: "－"}.get(int(row["feedback"]), "－")
            tags = " ".join(filter(None, [
                "🔴 报错" if row["has_error"] else "",
                "⚠️ 空数据" if row["row_count"] == 0 else "",
            ]))
            user_tag = f"👤 {row.get('user_name', '匿名')}"
            with st.expander(f"{fb_icon} {user_tag}　**{row['question']}** {tags}　`{row['created_at']}`"):
                t1, t2, t3, t4 = st.tabs(["基本信息", "SQL", "答案", "洞察"])
                with t1:
                    st.write(f"**返回行数：** {row['row_count']}　**有图表：** {'是' if row['has_chart'] else '否'}")
                    if row["error_msg"]:
                        st.error(row["error_msg"])
                    if row["feedback_note"]:
                        st.info(f"用户反馈备注：{row['feedback_note']}")
                    new_fb = st.radio("修改标记", ["无", "👍", "👎"],
                        index={"0":0,"1":1,"-1":2}.get(str(int(row["feedback"])),0),
                        horizontal=True, key=f"fb_{row['id']}")
                    if st.button("保存标记", key=f"save_{row['id']}"):
                        update_feedback(int(row["id"]), {"无":0,"👍":1,"👎":-1}[new_fb])
                        st.rerun()
                with t2:
                    st.code(row["sql"] or "无", language="sql")
                with t3:
                    st.markdown(row["answer"])
                with t4:
                    st.markdown(row["insight"] or "无")

        st.divider()
        st.subheader("📊 高频问题词频 Top10")
        from collections import Counter
        words = []
        for q in df_logs["question"]:
            words.extend(str(q).split())
        freq_df = pd.DataFrame(Counter(words).most_common(10), columns=["关键词", "次数"])
        st.dataframe(freq_df, use_container_width=True)

        st.subheader("📈 每日查询量 & 活跃用户")
        df_logs["date"] = pd.to_datetime(df_logs["created_at"]).dt.date
        daily_queries = df_logs.groupby("date").size().reset_index(name="查询次数")
        daily_users = df_logs.groupby("date")["user_name"].nunique().reset_index(name="活跃用户数")
        daily = daily_queries.merge(daily_users, on="date")
        st.line_chart(daily.set_index("date"))

        st.subheader("👥 用户提问排行")
        user_stats = df_logs.groupby("user_name").agg(
            提问次数=("id", "count"),
            点赞数=("feedback", lambda x: (x == 1).sum()),
            点踩数=("feedback", lambda x: (x == -1).sum()),
            最近提问=("created_at", "max"),
        ).sort_values("提问次数", ascending=False).reset_index()
        user_stats.columns = ["用户", "提问次数", "👍 点赞", "👎 点踩", "最近提问"]
        st.dataframe(user_stats, use_container_width=True, hide_index=True)

# ════════════════════════════════════════════════════════
# TAB 2: 数据集预览
# ════════════════════════════════════════════════════════
with tab_data:
    DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "shuidi.db")
    conn = sqlite3.connect(DB_PATH)
    tables = pd.read_sql_query("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name", conn)["name"].tolist()
    tables = [t for t in tables if not t.startswith("sqlite_")]
    conn.close()

    col_a, col_b, col_c = st.columns([2, 2, 4])
    with col_a:
        selected_table = st.selectbox("选择数据表", tables)
    with col_b:
        limit = st.number_input("显示行数", min_value=10, max_value=1000, value=50, step=10)
    with col_c:
        search_col_val = st.text_input("关键词过滤（模糊匹配所有列）")

    conn = sqlite3.connect(DB_PATH)
    df_table = pd.read_sql_query(f'SELECT * FROM [{selected_table}] LIMIT {limit}', conn)
    conn.close()

    # 统计信息
    conn = sqlite3.connect(DB_PATH)
    total_rows = pd.read_sql_query(f'SELECT COUNT(*) as cnt FROM [{selected_table}]', conn).iloc[0]["cnt"]
    conn.close()
    st.caption(f"表 **{selected_table}** 共 {total_rows} 行，当前显示前 {limit} 行")

    if search_col_val:
        mask = df_table.apply(lambda col: col.astype(str).str.contains(search_col_val, case=False, na=False)).any(axis=1)
        df_table = df_table[mask]
        st.caption(f"过滤后显示 {len(df_table)} 行")

    st.dataframe(df_table, use_container_width=True)

    st.subheader("字段说明")
    st.dataframe(
        pd.DataFrame({"字段名": df_table.columns, "类型": [str(df_table[c].dtype) for c in df_table.columns]}),
        use_container_width=True,
        hide_index=True
    )

# ════════════════════════════════════════════════════════
# TAB 3: 数据清洗
# ════════════════════════════════════════════════════════
with tab_clean:
    DB_PATH_CLEAN = os.path.join(os.path.dirname(os.path.dirname(__file__)), "shuidi.db")

    def query(sql):
        c = sqlite3.connect(DB_PATH_CLEAN)
        df = pd.read_sql_query(sql, c)
        c.close()
        return df

    def fix_sql(sql):
        c = sqlite3.connect(DB_PATH_CLEAN)
        c.execute(sql)
        c.commit()
        c.close()

    st.markdown("对数据库进行质量检测，发现问题后可一键修复或查看明细。")

    # ── 一键全量检测 ──────────────────────────────────
    if st.button("🔍 一键全量检测", type="primary"):
        st.session_state["clean_run"] = True

    if st.session_state.get("clean_run"):

        # ─ 1. 空值/缺失值检测 ─────────────────────────
        st.subheader("1️⃣ 字段空值检测")
        null_checks = {
            "campaigns.patient_name 为空": "SELECT COUNT(*) as cnt FROM campaigns WHERE patient_name IS NULL OR patient_name=''",
            "campaigns.hospital_id 为空": "SELECT COUNT(*) as cnt FROM campaigns WHERE hospital_id IS NULL",
            "campaigns.disease_id 为空":  "SELECT COUNT(*) as cnt FROM campaigns WHERE disease_id IS NULL",
            "campaigns.staff_id 为空":    "SELECT COUNT(*) as cnt FROM campaigns WHERE staff_id IS NULL",
            "donations.amount 为空":      "SELECT COUNT(*) as cnt FROM donations WHERE amount IS NULL",
            "withdrawals.amount 为空":    "SELECT COUNT(*) as cnt FROM withdrawals WHERE amount IS NULL",
        }
        null_results = []
        for desc, sql in null_checks.items():
            cnt = query(sql).iloc[0]["cnt"]
            null_results.append({"检测项": desc, "问题数量": cnt, "状态": "✅ 正常" if cnt == 0 else "⚠️ 有问题"})
        st.dataframe(pd.DataFrame(null_results), use_container_width=True, hide_index=True)

        # ─ 2. 异常值检测 ──────────────────────────────
        st.subheader("2️⃣ 异常值检测")

        age_df = query("SELECT campaign_id, patient_name, age FROM campaigns WHERE age < 0 OR age > 120")
        neg_raised = query("SELECT campaign_id, patient_name, raised_amount FROM campaigns WHERE raised_amount < 0")
        neg_target = query("SELECT campaign_id, patient_name, target_amount FROM campaigns WHERE target_amount <= 0")
        neg_donation = query("SELECT donation_id, campaign_id, amount FROM donations WHERE amount <= 0")

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("年龄异常", len(age_df), help="age<0 或 age>120")
        col2.metric("已筹金额为负", len(neg_raised))
        col3.metric("目标金额异常", len(neg_target))
        col4.metric("捐款金额异常", len(neg_donation))

        if len(age_df):
            with st.expander(f"查看年龄异常明细（{len(age_df)}条）"):
                st.dataframe(age_df, use_container_width=True)

        # ─ 3. 数据一致性检测 ──────────────────────────
        st.subheader("3️⃣ 数据一致性检测")

        over_raised = query("""
            SELECT campaign_id, patient_name, target_amount, raised_amount,
                   ROUND(raised_amount-target_amount,2) as 超出金额
            FROM campaigns WHERE raised_amount > target_amount * 1.05
        """)

        deadline_err = query("""
            SELECT campaign_id, patient_name, created_at, deadline
            FROM campaigns WHERE deadline < created_at
        """)

        withdraw_err = query("""
            SELECT w.withdrawal_id, w.campaign_id, w.amount as 提现金额,
                   c.raised_amount as 已筹金额,
                   ROUND(w.amount - c.raised_amount, 2) as 超出金额
            FROM withdrawals w JOIN campaigns c ON w.campaign_id=c.campaign_id
            WHERE w.amount > c.raised_amount * 1.01
        """)

        c1, c2, c3 = st.columns(3)
        c1.metric("已筹>目标105%", len(over_raised), help="raised_amount > target_amount×1.05")
        c2.metric("截止日期早于发起", len(deadline_err))
        c3.metric("提现>已筹金额", len(withdraw_err))

        if len(over_raised):
            with st.expander(f"已筹超出目标明细（{len(over_raised)}条）"):
                st.dataframe(over_raised, use_container_width=True)
        if len(deadline_err):
            with st.expander(f"截止日期异常明细（{len(deadline_err)}条）"):
                st.dataframe(deadline_err, use_container_width=True)
                if st.button("🔧 一键修复：将截止日期设为发起日+90天"):
                    fix_sql("UPDATE campaigns SET deadline=date(created_at,'+90 days') WHERE deadline < created_at")
                    st.success("已修复")
                    st.session_state["clean_run"] = False
                    st.rerun()
        if len(withdraw_err):
            with st.expander(f"提现金额异常明细（{len(withdraw_err)}条）"):
                st.dataframe(withdraw_err, use_container_width=True)

        # ─ 4. 重复数据检测 ────────────────────────────
        st.subheader("4️⃣ 重复数据检测")
        dup_df = query("""
            SELECT patient_name, hospital_id, disease_id,
                   COUNT(*) as 重复次数,
                   GROUP_CONCAT(campaign_id) as 项目ID列表
            FROM campaigns
            GROUP BY patient_name, hospital_id, disease_id
            HAVING COUNT(*) > 1
            ORDER BY 重复次数 DESC
            LIMIT 50
        """)
        if len(dup_df):
            st.warning(f"发现 {len(dup_df)} 组疑似重复项目（同患者+同医院+同疾病）")
            st.dataframe(dup_df, use_container_width=True, hide_index=True)
        else:
            st.success("✅ 未发现重复项目")

        # ─ 汇总 ───────────────────────────────────────
        st.divider()
        total_issues = (
            sum(r["问题数量"] for r in null_results) +
            len(age_df) + len(neg_raised) + len(neg_target) + len(neg_donation) +
            len(over_raised) + len(deadline_err) + len(withdraw_err) + len(dup_df)
        )
        if total_issues == 0:
            st.success("🎉 数据质量良好，未发现问题！")
        else:
            st.warning(f"共发现 **{total_issues}** 个数据质量问题，请查看上方明细处理。")

# ════════════════════════════════════════════════════════
# TAB 4: 知识库编辑
# ════════════════════════════════════════════════════════
with tab_kb:
    ROOT = os.path.dirname(os.path.dirname(__file__))
    BASE_KB_PATH   = os.path.join(ROOT, "knowledge_base.txt")
    CUSTOM_KB_PATH = os.path.join(ROOT, "knowledge_custom.txt")

    st.markdown("知识库分为两部分，Agent查询时会同时使用。修改后点保存，下次查询自动生效。")

    kb_col1, kb_col2 = st.columns(2)

    # ── 左侧：固定知识库 ──
    with kb_col1:
        st.subheader("📚 固定知识库")
        st.caption("表结构、业务基准指标、季节规律等，建议不要随意改动")
        with open(BASE_KB_PATH, encoding="utf-8") as f:
            base_content = f.read()
        new_base = st.text_area("固定知识库内容", value=base_content, height=500, key="base_kb")
        b1, b2 = st.columns(2)
        with b1:
            if st.button("💾 保存固定知识库", type="primary", key="save_base"):
                with open(BASE_KB_PATH, "w", encoding="utf-8") as f:
                    f.write(new_base)
                reset_vectorstore()
                st.success("✅ 已保存，缓存已清空")
        with b2:
            st.caption(f"{len(base_content)} 字符")

    # ── 右侧：自定义知识库 ──
    with kb_col2:
        st.subheader("✏️ 自定义知识库")
        st.caption("AI识别不准时在这里补充：纠错说明、特殊字段、业务规则强化")
        with open(CUSTOM_KB_PATH, encoding="utf-8") as f:
            custom_content = f.read()
        new_custom = st.text_area("自定义知识库内容", value=custom_content, height=500, key="custom_kb")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("💾 保存自定义知识库", type="primary", key="save_custom"):
                with open(CUSTOM_KB_PATH, "w", encoding="utf-8") as f:
                    f.write(new_custom)
                reset_vectorstore()
                st.success("✅ 已保存，缓存已清空")
        with c2:
            st.caption(f"{len(custom_content)} 字符")

    st.divider()
    st.subheader("💡 自定义知识库写法建议")
    st.markdown("""
| 场景 | 怎么写 |
|------|--------|
| AI把某个字段理解错了 | `【纠错】用户问"XX"时，正确字段是YY表的ZZ列，不是...` |
| 某个指标计算方式特殊 | `【计算规则】净销售额 = 销售额 - 退款金额，退款在Returns表` |
| 某类问题AI总答偏 | `【强化】问员工业绩时，必须按销售额排序，不是订单量` |
| 新增业务术语 | `【术语】"大客户"指年采购额超过10万的客户` |
    """)
