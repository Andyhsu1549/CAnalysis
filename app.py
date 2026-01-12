import streamlit as st
import pandas as pd
from datetime import datetime, date, time
from pathlib import Path

# ========================
# 基礎設定與共用函式
# ========================

DATA_DIR = Path("data")
UPLOAD_DIR = Path("uploads")
ASSETS_DIR = Path("assets")

for d in [DATA_DIR, UPLOAD_DIR, ASSETS_DIR]:
    d.mkdir(parents=True, exist_ok=True)


def load_csv(name: str, columns: list) -> pd.DataFrame:
    """讀取 CSV，如不存在則建立空 DataFrame。"""
    path = DATA_DIR / name
    if path.exists():
        df = pd.read_csv(path)
    else:
        df = pd.DataFrame(columns=columns)
    return df


def save_csv(name: str, df: pd.DataFrame):
    """儲存 DataFrame 到 CSV。"""
    path = DATA_DIR / name
    df.to_csv(path, index=False)


# ========================
# 附件管理通用區塊
# ========================

def _simple_type_from_mime(mime: str) -> str:
    if not mime:
        return "other"
    if mime.startswith("image"):
        return "image"
    if mime.startswith("video"):
        return "video"
    if mime == "application/pdf":
        return "pdf"
    return "other"


def _preview_file(path: str, file_type: str):
    """依檔案類型，在畫面中預覽或提供下載。"""
    try:
        p = Path(path)
        if not p.exists():
            st.warning(f"檔案不存在：{path}")
            return

        if file_type == "image":
            st.image(str(p))
        elif file_type == "video":
            st.video(str(p))
        elif file_type == "pdf":
            with open(p, "rb") as f:
                st.download_button(
                    "下載 PDF",
                    data=f,
                    file_name=p.name,
                    mime="application/pdf",
                )
        else:
            with open(p, "rb") as f:
                st.download_button(
                    "下載檔案",
                    data=f,
                    file_name=p.name,
                )
    except Exception as e:
        st.error(f"預覽檔案時發生錯誤：{e}")


def attachment_section(module: str, ref_df: pd.DataFrame,
                       ref_label_col: str, ref_id_col: str = "id"):
    """
    通用附件區塊：
    - module: 字串，標示是哪個模組（site/script/department/schedule/editing...）
    - ref_df: 主資料 DataFrame
    - ref_label_col: 在下拉選單顯示的欄位
    - ref_id_col: 主鍵欄位名稱，預設 "id"
    """
    st.markdown("### 相關附件")

    attachments = load_csv(
        "attachments.csv",
        [
            "id",
            "module",
            "ref_id",
            "title",
            "file_name",
            "file_path",
            "file_type",
            "uploaded_at",
            "note",
        ],
    )

    if ref_df.empty:
        st.info("目前沒有可關聯的資料，請先新增一筆主資料。")
        return

    # 選擇要管理哪一筆主資料
    options = {
        f"{row[ref_label_col]} (ID: {int(row[ref_id_col])})": int(row[ref_id_col])
        for _, row in ref_df.iterrows()
    }
    selected_label = st.selectbox(
        "選擇一筆資料來管理附件",
        list(options.keys()),
        key=f"attach_select_{module}",
    )
    selected_id = options[selected_label]

    # 上傳附件
    st.subheader("上傳新附件")
    with st.form(f"upload_form_{module}", clear_on_submit=True):
        title = st.text_input("附件名稱/說明", key=f"title_{module}")
        files = st.file_uploader(
            "選擇檔案（可多選）",
            accept_multiple_files=True,
            type=None,
            key=f"files_{module}",
        )
        note = st.text_area("備註（選填）", height=60, key=f"note_{module}")
        submitted = st.form_submit_button("上傳附件")

        if submitted and files:
            module_dir = UPLOAD_DIR / module
            module_dir.mkdir(parents=True, exist_ok=True)

            for f in files:
                file_path = module_dir / f.name
                with open(file_path, "wb") as out:
                    out.write(f.getbuffer())

                new_id = attachments["id"].max() + 1 if len(attachments) > 0 else 1
                file_type = _simple_type_from_mime(f.type)

                new_row = {
                    "id": new_id,
                    "module": module,
                    "ref_id": selected_id,
                    "title": title or f.name,
                    "file_name": f.name,
                    "file_path": str(file_path),
                    "file_type": file_type,
                    "uploaded_at": datetime.now().isoformat(),
                    "note": note,
                }
                attachments = pd.concat(
                    [attachments, pd.DataFrame([new_row])],
                    ignore_index=True,
                )

            save_csv("attachments.csv", attachments)
            st.success("附件已上傳")

    # 附件列表與預覽
    st.subheader("附件列表與預覽")
    attach_view = attachments[
        (attachments["module"] == module)
        & (attachments["ref_id"] == selected_id)
    ]

    if attach_view.empty:
        st.info("目前沒有附件。")
        return

    for _, row in attach_view.iterrows():
        st.markdown(f"**{row['title']}**  （{row['file_name']}）")
        _preview_file(row["file_path"], row["file_type"])
        if row["note"]:
            st.caption(row["note"])

        if st.button(
            f"刪除此附件（ID {int(row['id'])}）",
            key=f"del_attach_{module}_{int(row['id'])}",
        ):
            attachments = attachments[attachments["id"] != row["id"]]
            save_csv("attachments.csv", attachments)
            st.warning("附件已刪除")
            st.experimental_rerun()

        st.divider()


# ========================
# 頁面 1：案場素材拍攝管理
# ========================

def page_shooting_materials():
    st.header("1. 案場素材拍攝管理")

    sites = load_csv(
        "shooting_sites.csv",
        ["id", "site_name", "address", "status", "visit_datetime", "note"],
    )
    assets = load_csv(
        "assets.csv",
        ["id", "site_id", "file_name", "file_path", "file_type", "uploaded_at", "note"],
    )

    # 新增案場
    st.subheader("新增案場")
    with st.form("site_form", clear_on_submit=True):
        site_name = st.text_input("案場名稱")
        address = st.text_input("地址")
        status = st.selectbox(
            "狀態",
            ["尚未勘景", "已勘景", "已拍攝", "待補拍"],
        )
        visit_date = st.date_input("預計 / 實際到場日期", value=date.today())
        visit_time = st.time_input("時間", value=time(9, 0))
        note = st.text_area("備註", height=80)
        submitted = st.form_submit_button("新增案場")

        if submitted:
            if not site_name:
                st.error("請輸入案場名稱")
            else:
                new_id = int(sites["id"].max()) + 1 if len(sites) > 0 else 1
                visit_dt = datetime.combine(visit_date, visit_time)
                new_row = {
                    "id": new_id,
                    "site_name": site_name,
                    "address": address,
                    "status": status,
                    "visit_datetime": visit_dt.isoformat(),
                    "note": note,
                }
                sites = pd.concat([sites, pd.DataFrame([new_row])], ignore_index=True)
                save_csv("shooting_sites.csv", sites)
                st.success("案場已新增")

    # 案場列表與單筆編輯
    st.subheader("案場列表")
    if sites.empty:
        st.info("目前沒有案場資料")
    else:
        st.dataframe(sites)

        st.markdown("#### 編輯 / 刪除案場")
        site_map = {f"{row['site_name']} (ID: {int(row['id'])})": int(row["id"])
                    for _, row in sites.iterrows()}
        selected_label = st.selectbox(
            "選擇要編輯的案場",
            list(site_map.keys()),
            key="edit_site_select",
        )
        selected_id = site_map[selected_label]
        row = sites[sites["id"] == selected_id].iloc[0]

        with st.form("edit_site_form"):
            site_name_ed = st.text_input("案場名稱", value=row["site_name"])
            address_ed = st.text_input("地址", value=row["address"])
            status_ed = st.selectbox(
                "狀態",
                ["尚未勘景", "已勘景", "已拍攝", "待補拍"],
                index=["尚未勘景", "已勘景", "已拍攝", "待補拍"].index(row["status"])
                if row["status"] in ["尚未勘景", "已勘景", "已拍攝", "待補拍"]
                else 0,
            )
            try:
                visit_dt = datetime.fromisoformat(str(row["visit_datetime"]))
                visit_date_ed = st.date_input("日期", value=visit_dt.date())
                visit_time_ed = st.time_input("時間", value=visit_dt.time())
            except Exception:
                visit_date_ed = st.date_input("日期", value=date.today())
                visit_time_ed = st.time_input("時間", value=time(9, 0))
            note_ed = st.text_area("備註", value=row["note"], height=80)

            col1, col2 = st.columns(2)
            with col1:
                update_btn = st.form_submit_button("儲存修改")
            with col2:
                delete_btn = st.form_submit_button("刪除此案場")

            if update_btn:
                idx = sites.index[sites["id"] == selected_id][0]
                sites.at[idx, "site_name"] = site_name_ed
                sites.at[idx, "address"] = address_ed
                sites.at[idx, "status"] = status_ed
                sites.at[idx, "visit_datetime"] = datetime.combine(
                    visit_date_ed, visit_time_ed
                ).isoformat()
                sites.at[idx, "note"] = note_ed
                save_csv("shooting_sites.csv", sites)
                st.success("案場已更新")

            if delete_btn:
                # 同時刪除該案場的素材紀錄
                sites = sites[sites["id"] != selected_id]
                assets = assets[assets["site_id"] != selected_id]
                save_csv("shooting_sites.csv", sites)
                save_csv("assets.csv", assets)
                st.warning("案場與其素材已刪除")
                st.experimental_rerun()

    # 素材上傳與預覽
    st.markdown("---")
    st.subheader("素材上傳與預覽（影像檔）")
    if sites.empty:
        st.info("請先新增案場")
    else:
        site_map2 = {f"{row['site_name']} (ID: {int(row['id'])})": int(row["id"])
                     for _, row in sites.iterrows()}
        selected_label2 = st.selectbox(
            "選擇案場上傳素材",
            list(site_map2.keys()),
            key="asset_site_select",
        )
        selected_site_id = site_map2[selected_label2]

        uploaded_files = st.file_uploader(
            "上傳素材（圖片/影片，可多選）",
            accept_multiple_files=True,
            type=None,
            key="asset_uploader",
        )
        note_assets = st.text_input("共用備註（選填）", key="asset_note")

        if st.button("上傳素材"):
            if not uploaded_files:
                st.info("尚未選擇檔案")
            else:
                for f in uploaded_files:
                    ASSETS_DIR.mkdir(exist_ok=True)
                    file_path = ASSETS_DIR / f.name
                    with open(file_path, "wb") as out:
                        out.write(f.getbuffer())

                    new_id = int(assets["id"].max()) + 1 if len(assets) > 0 else 1
                    file_type = _simple_type_from_mime(f.type)
                    new_row = {
                        "id": new_id,
                        "site_id": selected_site_id,
                        "file_name": f.name,
                        "file_path": str(file_path),
                        "file_type": file_type,
                        "uploaded_at": datetime.now().isoformat(),
                        "note": note_assets,
                    }
                    assets = pd.concat(
                        [assets, pd.DataFrame([new_row])],
                        ignore_index=True,
                    )
                save_csv("assets.csv", assets)
                st.success("素材已上傳")

        st.markdown("#### 該案場素材預覽")
        site_assets = assets[assets["site_id"] == selected_site_id]
        if site_assets.empty:
            st.info("尚無素材")
        else:
            for _, row in site_assets.iterrows():
                st.write(f"檔名：{row['file_name']}")
                _preview_file(row["file_path"], row["file_type"])
                if row["note"]:
                    st.caption(row["note"])
                if st.button(
                    f"刪除此素材（ID {int(row['id'])}）",
                    key=f"del_asset_{int(row['id'])}",
                ):
                    assets = assets[assets["id"] != row["id"]]
                    save_csv("assets.csv", assets)
                    st.warning("素材已刪除")
                    st.experimental_rerun()
                st.divider()

    # 通用附件（例如場地合約、平面圖…）
    st.markdown("---")
    attachment_section(
        module="site",
        ref_df=sites,
        ref_label_col="site_name",
        ref_id_col="id",
    )


# ========================
# 頁面 2：訪談腳本 & 分鏡
# ========================

def page_scripts_storyboard():
    st.header("2. 訪談腳本 & 分鏡設計")

    scripts = load_csv(
        "scripts.csv",
        ["id", "category", "title", "content", "version", "is_approved", "updated_at"],
    )
    storyboards = load_csv(
        "storyboards.csv",
        ["id", "script_id", "shot_no", "description", "image_path", "note"],
    )

    tab1, tab2, tab3 = st.tabs(["訪談腳本管理", "分鏡設計", "分鏡列表與編輯"])

    # --- 訪談腳本管理 ---
    with tab1:
        st.subheader("新增腳本")
        with st.form("script_form", clear_on_submit=True):
            category = st.text_input("腳本分類（例：老闆訪談 / 工廠導覽）")
            title = st.text_input("腳本標題")
            content = st.text_area("腳本內容（可條列/訪綱/完整稿）", height=200)
            version = st.text_input("版本號", value="v1.0")
            is_approved = st.checkbox("是否為確認版（凍結）", value=False)
            submitted = st.form_submit_button("新增腳本")

            if submitted:
                if not title:
                    st.error("請輸入腳本標題")
                else:
                    new_id = int(scripts["id"].max()) + 1 if len(scripts) > 0 else 1
                    new_row = {
                        "id": new_id,
                        "category": category,
                        "title": title,
                        "content": content,
                        "version": version,
                        "is_approved": is_approved,
                        "updated_at": datetime.now().isoformat(),
                    }
                    scripts = pd.concat(
                        [scripts, pd.DataFrame([new_row])],
                        ignore_index=True,
                    )
                    save_csv("scripts.csv", scripts)
                    st.success("腳本已新增")

        st.subheader("腳本列表")
        if scripts.empty:
            st.info("尚無腳本")
        else:
            st.dataframe(scripts)

            st.markdown("#### 編輯 / 刪除腳本")
            script_map = {
                f"{row['title']} (ID: {int(row['id'])})": int(row["id"])
                for _, row in scripts.iterrows()
            }
            selected_label = st.selectbox(
                "選擇要編輯的腳本",
                list(script_map.keys()),
                key="edit_script_select",
            )
            selected_id = script_map[selected_label]
            row = scripts[scripts["id"] == selected_id].iloc[0]

            with st.form("edit_script_form"):
                category_ed = st.text_input(
                    "分類",
                    value=row["category"],
                )
                title_ed = st.text_input("標題", value=row["title"])
                content_ed = st.text_area(
                    "內容",
                    value=row["content"],
                    height=200,
                )
                version_ed = st.text_input("版本", value=row["version"])
                is_approved_ed = st.checkbox(
                    "確認版",
                    value=bool(row["is_approved"]),
                )

                col1, col2 = st.columns(2)
                with col1:
                    update_btn = st.form_submit_button("儲存修改")
                with col2:
                    delete_btn = st.form_submit_button("刪除此腳本")

                if update_btn:
                    idx = scripts.index[scripts["id"] == selected_id][0]
                    scripts.at[idx, "category"] = category_ed
                    scripts.at[idx, "title"] = title_ed
                    scripts.at[idx, "content"] = content_ed
                    scripts.at[idx, "version"] = version_ed
                    scripts.at[idx, "is_approved"] = is_approved_ed
                    scripts.at[idx, "updated_at"] = datetime.now().isoformat()
                    save_csv("scripts.csv", scripts)
                    st.success("腳本已更新")

                if delete_btn:
                    # 連同刪除相關分鏡
                    scripts = scripts[scripts["id"] != selected_id]
                    storyboards = storyboards[storyboards["script_id"] != selected_id]
                    save_csv("scripts.csv", scripts)
                    save_csv("storyboards.csv", storyboards)
                    st.warning("腳本與相關分鏡已刪除")
                    st.experimental_rerun()

        # 腳本附件（Word/PDF 等）
        st.markdown("---")
        if not scripts.empty:
            attachment_section(
                module="script",
                ref_df=scripts,
                ref_label_col="title",
                ref_id_col="id",
            )

    # --- 分鏡新增 ---
    with tab2:
        st.subheader("新增分鏡")
        if scripts.empty:
            st.info("請先新增至少一個腳本")
        else:
            script_map2 = {
                f"{row['title']} (ID: {int(row['id'])})": int(row["id"])
                for _, row in scripts.iterrows()
            }
            selected_label2 = st.selectbox(
                "選擇腳本",
                list(script_map2.keys()),
                key="sb_script_select",
            )
            selected_script_id = script_map2[selected_label2]

            with st.form("storyboard_form", clear_on_submit=True):
                shot_no = st.text_input("鏡號", value="1A")
                description = st.text_area("分鏡描述（景別 / 運鏡 / 內容）")
                image_file = st.file_uploader(
                    "上傳分鏡圖片（選填）",
                    type=["png", "jpg", "jpeg"],
                )
                note = st.text_input("備註", value="")
                submitted = st.form_submit_button("新增分鏡")

                if submitted:
                    image_path = ""
                    if image_file:
                        sb_dir = ASSETS_DIR / "storyboards"
                        sb_dir.mkdir(parents=True, exist_ok=True)
                        file_path = sb_dir / image_file.name
                        with open(file_path, "wb") as out:
                            out.write(image_file.getbuffer())
                        image_path = str(file_path)

                    new_id = (
                        int(storyboards["id"].max()) + 1
                        if len(storyboards) > 0
                        else 1
                    )
                    new_row = {
                        "id": new_id,
                        "script_id": selected_script_id,
                        "shot_no": shot_no,
                        "description": description,
                        "image_path": image_path,
                        "note": note,
                    }
                    storyboards = pd.concat(
                        [storyboards, pd.DataFrame([new_row])],
                        ignore_index=True,
                    )
                    save_csv("storyboards.csv", storyboards)
                    st.success("分鏡已新增")

    # --- 分鏡列表與編輯 ---
    with tab3:
        st.subheader("分鏡列表")
        if storyboards.empty:
            st.info("尚無分鏡")
        else:
            st.dataframe(storyboards)

            st.markdown("#### 編輯 / 刪除分鏡")
            label_map = {}
            for _, row in storyboards.iterrows():
                label = f"腳本ID {int(row['script_id'])} - 鏡號 {row['shot_no']} (ID: {int(row['id'])})"
                label_map[label] = int(row["id"])

            selected_label3 = st.selectbox(
                "選擇要編輯的分鏡",
                list(label_map.keys()),
                key="edit_sb_select",
            )
            selected_sb_id = label_map[selected_label3]
            row = storyboards[storyboards["id"] == selected_sb_id].iloc[0]

            with st.form("edit_sb_form"):
                shot_no_ed = st.text_input("鏡號", value=row["shot_no"])
                description_ed = st.text_area(
                    "分鏡描述",
                    value=row["description"],
                    height=120,
                )
                note_ed = st.text_input("備註", value=row["note"])
                col1, col2 = st.columns(2)
                with col1:
                    update_btn = st.form_submit_button("儲存修改")
                with col2:
                    delete_btn = st.form_submit_button("刪除此分鏡")

                if update_btn:
                    idx = storyboards.index[storyboards["id"] == selected_sb_id][0]
                    storyboards.at[idx, "shot_no"] = shot_no_ed
                    storyboards.at[idx, "description"] = description_ed
                    storyboards.at[idx, "note"] = note_ed
                    save_csv("storyboards.csv", storyboards)
                    st.success("分鏡已更新")

                if delete_btn:
                    storyboards = storyboards[storyboards["id"] != selected_sb_id]
                    save_csv("storyboards.csv", storyboards)
                    st.warning("分鏡已刪除")
                    st.experimental_rerun()

            # 分鏡附件（例如 PSD/參考影片等）
            st.markdown("---")
            attachment_section(
                module="storyboard",
                ref_df=storyboards,
                ref_label_col="shot_no",
                ref_id_col="id",
            )


# ========================
# 頁面 3：部門 / 工班資訊
# ========================

def page_departments():
    st.header("3. 部門 / 工班資訊管理")

    df = load_csv(
        "departments.csv",
        ["id", "dept_type", "name", "role", "contact", "note"],
    )

    st.subheader("新增部門 / 工班")
    with st.form("dept_form", clear_on_submit=True):
        dept_type = st.text_input("部門類型（美術 / 燈光 / 攝影 / 收音 / 後製 / 客戶窗口 等）")
        name = st.text_input("名稱（人名或公司）")
        role = st.text_input("角色描述（例：主攝影 / 燈光師 / 副導）")
        contact = st.text_input("聯絡方式（電話 / Line / Email）")
        note = st.text_area("備註", height=80)
        submitted = st.form_submit_button("新增")

        if submitted:
            if not name:
                st.error("請輸入名稱")
            else:
                new_id = int(df["id"].max()) + 1 if len(df) > 0 else 1
                new_row = {
                    "id": new_id,
                    "dept_type": dept_type,
                    "name": name,
                    "role": role,
                    "contact": contact,
                    "note": note,
                }
                df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                save_csv("departments.csv", df)
                st.success("已新增部門 / 工班")

    st.subheader("部門 / 工班列表")
    if df.empty:
        st.info("尚無工班資料")
    else:
        st.dataframe(df)

        st.markdown("#### 編輯 / 刪除部門 / 工班")
        dept_map = {
            f"{row['name']} (ID: {int(row['id'])})": int(row["id"])
            for _, row in df.iterrows()
        }
        selected_label = st.selectbox(
            "選擇要編輯的項目",
            list(dept_map.keys()),
            key="edit_dept_select",
        )
        selected_id = dept_map[selected_label]
        row = df[df["id"] == selected_id].iloc[0]

        with st.form("edit_dept_form"):
            dept_type_ed = st.text_input("部門類型", value=row["dept_type"])
            name_ed = st.text_input("名稱", value=row["name"])
            role_ed = st.text_input("角色描述", value=row["role"])
            contact_ed = st.text_input("聯絡方式", value=row["contact"])
            note_ed = st.text_area("備註", value=row["note"], height=80)

            col1, col2 = st.columns(2)
            with col1:
                update_btn = st.form_submit_button("儲存修改")
            with col2:
                delete_btn = st.form_submit_button("刪除此項目")

            if update_btn:
                idx = df.index[df["id"] == selected_id][0]
                df.at[idx, "dept_type"] = dept_type_ed
                df.at[idx, "name"] = name_ed
                df.at[idx, "role"] = role_ed
                df.at[idx, "contact"] = contact_ed
                df.at[idx, "note"] = note_ed
                save_csv("departments.csv", df)
                st.success("資料已更新")

            if delete_btn:
                df = df[df["id"] != selected_id]
                save_csv("departments.csv", df)
                st.warning("資料已刪除")
                st.experimental_rerun()

    # 工班附件（作品集、合約、spec 等）
    st.markdown("---")
    attachment_section(
        module="department",
        ref_df=df,
        ref_label_col="name",
        ref_id_col="id",
    )


# ========================
# 頁面 4：拍攝流程 & 餐食管理
# ========================

def page_shooting_schedule():
    st.header("4. 拍攝時間流程 & 人員餐食管理")

    schedules = load_csv(
        "schedules.csv",
        [
            "id",
            "date",
            "start_time",
            "end_time",
            "location",
            "scene_desc",
            "responsible",
            "note",
        ],
    )
    meals = load_csv(
        "meals.csv",
        ["id", "date", "meal_type", "time", "people", "vendor", "note"],
    )

    tab1, tab2 = st.tabs(["拍攝流程", "餐食管理"])

    # --- 拍攝流程 ---
    with tab1:
        st.subheader("新增拍攝時段")
        with st.form("schedule_form", clear_on_submit=True):
            date_val = st.date_input("日期", value=date.today())
            start_time = st.time_input("開始時間", value=time(9, 0))
            end_time = st.time_input("結束時間", value=time(10, 0))
            location = st.text_input("地點 / 場景")
            scene_desc = st.text_area("內容描述（要拍什麼）", height=80)
            responsible = st.text_input("負責人（導演 / 製片 / 客戶窗口等）")
            note = st.text_input("備註", value="")
            submitted = st.form_submit_button("新增拍攝時段")

            if submitted:
                new_id = int(schedules["id"].max()) + 1 if len(schedules) > 0 else 1
                new_row = {
                    "id": new_id,
                    "date": date_val.isoformat(),
                    "start_time": start_time.isoformat(),
                    "end_time": end_time.isoformat(),
                    "location": location,
                    "scene_desc": scene_desc,
                    "responsible": responsible,
                    "note": note,
                }
                schedules = pd.concat(
                    [schedules, pd.DataFrame([new_row])],
                    ignore_index=True,
                )
                save_csv("schedules.csv", schedules)
                st.success("拍攝時段已新增")

        st.subheader("拍攝流程列表")
        if schedules.empty:
            st.info("尚無拍攝流程資料")
        else:
            df_view = schedules.copy()
            # 轉換排序用
            try:
                df_view["date_dt"] = pd.to_datetime(df_view["date"])
                df_view["start_dt"] = pd.to_datetime(df_view["start_time"])
                df_view = df_view.sort_values(by=["date_dt", "start_dt"])
            except Exception:
                pass
            st.dataframe(df_view.drop(columns=[c for c in df_view.columns if c.endswith("_dt")]))

            st.markdown("#### 編輯 / 刪除拍攝時段")
            sch_map = {
                f"{row['date']} {row['location']} (ID: {int(row['id'])})": int(row["id"])
                for _, row in schedules.iterrows()
            }
            selected_label = st.selectbox(
                "選擇要編輯的時段",
                list(sch_map.keys()),
                key="edit_schedule_select",
            )
            selected_id = sch_map[selected_label]
            row = schedules[schedules["id"] == selected_id].iloc[0]

            # 從字串轉回 date/time
            try:
                date_ed = datetime.fromisoformat(str(row["date"])).date()
            except Exception:
                date_ed = date.today()
            try:
                start_time_ed = datetime.fromisoformat(str(row["start_time"])).time()
            except Exception:
                start_time_ed = time(9, 0)
            try:
                end_time_ed = datetime.fromisoformat(str(row["end_time"])).time()
            except Exception:
                end_time_ed = time(10, 0)

            with st.form("edit_schedule_form"):
                date_form = st.date_input("日期", value=date_ed)
                start_time_form = st.time_input("開始時間", value=start_time_ed)
                end_time_form = st.time_input("結束時間", value=end_time_ed)
                location_ed = st.text_input("地點 / 場景", value=row["location"])
                scene_desc_ed = st.text_area(
                    "內容描述",
                    value=row["scene_desc"],
                    height=80,
                )
                responsible_ed = st.text_input("負責人", value=row["responsible"])
                note_ed = st.text_input("備註", value=row["note"])

                col1, col2 = st.columns(2)
                with col1:
                    update_btn = st.form_submit_button("儲存修改")
                with col2:
                    delete_btn = st.form_submit_button("刪除此時段")

                if update_btn:
                    idx = schedules.index[schedules["id"] == selected_id][0]
                    schedules.at[idx, "date"] = date_form.isoformat()
                    schedules.at[idx, "start_time"] = start_time_form.isoformat()
                    schedules.at[idx, "end_time"] = end_time_form.isoformat()
                    schedules.at[idx, "location"] = location_ed
                    schedules.at[idx, "scene_desc"] = scene_desc_ed
                    schedules.at[idx, "responsible"] = responsible_ed
                    schedules.at[idx, "note"] = note_ed
                    save_csv("schedules.csv", schedules)
                    st.success("拍攝時段已更新")

                if delete_btn:
                    schedules = schedules[schedules["id"] != selected_id]
                    save_csv("schedules.csv", schedules)
                    st.warning("時段已刪除")
                    st.experimental_rerun()

        # 拍攝流程附件（Call Sheet PDF 等）
        st.markdown("---")
        attachment_section(
            module="schedule",
            ref_df=schedules,
            ref_label_col="scene_desc",
            ref_id_col="id",
        )

    # --- 餐食管理 ---
    with tab2:
        st.subheader("新增餐食安排")
        with st.form("meal_form", clear_on_submit=True):
            date_val = st.date_input("日期", value=date.today(), key="meal_date")
            meal_type = st.selectbox(
                "餐別",
                ["早餐", "午餐", "晚餐", "消夜"],
            )
            time_val = st.time_input("用餐時間", value=time(12, 0))
            people = st.text_input("用餐人員（文字或人數說明）")
            vendor = st.text_input("餐廠 / 外送來源")
            note = st.text_input("備註", value="")
            submitted = st.form_submit_button("新增餐食安排")

            if submitted:
                new_id = int(meals["id"].max()) + 1 if len(meals) > 0 else 1
                new_row = {
                    "id": new_id,
                    "date": date_val.isoformat(),
                    "meal_type": meal_type,
                    "time": time_val.isoformat(),
                    "people": people,
                    "vendor": vendor,
                    "note": note,
                }
                meals = pd.concat(
                    [meals, pd.DataFrame([new_row])],
                    ignore_index=True,
                )
                save_csv("meals.csv", meals)
                st.success("餐食安排已新增")

        st.subheader("餐食安排列表")
        if meals.empty:
            st.info("尚無餐食資料")
        else:
            df_view = meals.copy()
            try:
                df_view["date_dt"] = pd.to_datetime(df_view["date"])
                df_view["time_dt"] = pd.to_datetime(df_view["time"])
                df_view = df_view.sort_values(by=["date_dt", "time_dt"])
            except Exception:
                pass
            st.dataframe(df_view.drop(columns=[c for c in df_view.columns if c.endswith("_dt")]))

            st.markdown("#### 編輯 / 刪除餐食安排")
            meal_map = {
                f"{row['date']} {row['meal_type']} (ID: {int(row['id'])})": int(row["id"])
                for _, row in meals.iterrows()
            }
            selected_label = st.selectbox(
                "選擇要編輯的餐食安排",
                list(meal_map.keys()),
                key="edit_meal_select",
            )
            selected_id = meal_map[selected_label]
            row = meals[meals["id"] == selected_id].iloc[0]

            try:
                date_ed = datetime.fromisoformat(str(row["date"])).date()
            except Exception:
                date_ed = date.today()
            try:
                time_ed = datetime.fromisoformat(str(row["time"])).time()
            except Exception:
                time_ed = time(12, 0)

            with st.form("edit_meal_form"):
                date_form = st.date_input("日期", value=date_ed)
                meal_type_ed = st.selectbox(
                    "餐別",
                    ["早餐", "午餐", "晚餐", "消夜"],
                    index=["早餐", "午餐", "晚餐", "消夜"].index(row["meal_type"])
                    if row["meal_type"] in ["早餐", "午餐", "晚餐", "消夜"]
                    else 1,
                )
                time_form = st.time_input("用餐時間", value=time_ed)
                people_ed = st.text_input("用餐人員", value=row["people"])
                vendor_ed = st.text_input("餐廠 / 外送來源", value=row["vendor"])
                note_ed = st.text_input("備註", value=row["note"])

                col1, col2 = st.columns(2)
                with col1:
                    update_btn = st.form_submit_button("儲存修改")
                with col2:
                    delete_btn = st.form_submit_button("刪除此安排")

                if update_btn:
                    idx = meals.index[meals["id"] == selected_id][0]
                    meals.at[idx, "date"] = date_form.isoformat()
                    meals.at[idx, "meal_type"] = meal_type_ed
                    meals.at[idx, "time"] = time_form.isoformat()
                    meals.at[idx, "people"] = people_ed
                    meals.at[idx, "vendor"] = vendor_ed
                    meals.at[idx, "note"] = note_ed
                    save_csv("meals.csv", meals)
                    st.success("餐食安排已更新")

                if delete_btn:
                    meals = meals[meals["id"] != selected_id]
                    save_csv("meals.csv", meals)
                    st.warning("餐食安排已刪除")
                    st.experimental_rerun()

        # 餐食附件（菜單、對帳單等，如需要）
        st.markdown("---")
        attachment_section(
            module="meal",
            ref_df=meals,
            ref_label_col="meal_type",
            ref_id_col="id",
        )


# ========================
# 頁面 5：剪輯進度管理
# ========================

def page_editing_progress():
    st.header("5. 剪輯進度管理")

    df = load_csv(
        "editing_tasks.csv",
        [
            "id",
            "clip_name",
            "type",
            "editor",
            "status",
            "version",
            "last_update",
            "note",
        ],
    )

    st.subheader("新增剪輯任務")
    with st.form("edit_task_form", clear_on_submit=True):
        clip_name = st.text_input("剪輯項目名稱（例：主片 90s / Reels_01）")
        clip_type = st.selectbox(
            "類型",
            ["正片", "短版剪輯", "直式剪輯", "預告片", "其他"],
        )
        editor = st.text_input("剪輯師")
        status = st.selectbox(
            "狀態",
            ["未開始", "粗剪中", "粗剪完成", "精剪中", "客戶審稿", "已定稿"],
        )
        version = st.text_input("版本", value="v0.1")
        note = st.text_area("備註 / 回饋重點", height=80)
        submitted = st.form_submit_button("新增剪輯任務")

        if submitted:
            if not clip_name:
                st.error("請輸入剪輯項目名稱")
            else:
                new_id = int(df["id"].max()) + 1 if len(df) > 0 else 1
                new_row = {
                    "id": new_id,
                    "clip_name": clip_name,
                    "type": clip_type,
                    "editor": editor,
                    "status": status,
                    "version": version,
                    "last_update": datetime.now().isoformat(),
                    "note": note,
                }
                df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                save_csv("editing_tasks.csv", df)
                st.success("剪輯任務已新增")

    st.subheader("剪輯任務列表")
    if df.empty:
        st.info("尚無剪輯任務")
    else:
        st.dataframe(df)

        st.markdown("#### 編輯 / 刪除剪輯任務")
        task_map = {
            f"{row['clip_name']} (ID: {int(row['id'])})": int(row["id"])
            for _, row in df.iterrows()
        }
        selected_label = st.selectbox(
            "選擇要編輯的剪輯任務",
            list(task_map.keys()),
            key="edit_task_select",
        )
        selected_id = task_map[selected_label]
        row = df[df["id"] == selected_id].iloc[0]

        with st.form("edit_task_form2"):
            clip_name_ed = st.text_input("剪輯項目名稱", value=row["clip_name"])
            clip_type_ed = st.selectbox(
                "類型",
                ["正片", "短版剪輯", "直式剪輯", "預告片", "其他"],
                index=["正片", "短版剪輯", "直式剪輯", "預告片", "其他"].index(
                    row["type"]
                )
                if row["type"] in ["正片", "短版剪輯", "直式剪輯", "預告片", "其他"]
                else 0,
            )
            editor_ed = st.text_input("剪輯師", value=row["editor"])
            status_ed = st.selectbox(
                "狀態",
                ["未開始", "粗剪中", "粗剪完成", "精剪中", "客戶審稿", "已定稿"],
                index=["未開始", "粗剪中", "粗剪完成", "精剪中", "客戶審稿", "已定稿"].index(
                    row["status"]
                )
                if row["status"]
                in ["未開始", "粗剪中", "粗剪完成", "精剪中", "客戶審稿", "已定稿"]
                else 0,
            )
            version_ed = st.text_input("版本", value=row["version"])
            note_ed = st.text_area("備註 / 回饋重點", value=row["note"], height=80)

            col1, col2 = st.columns(2)
            with col1:
                update_btn = st.form_submit_button("儲存修改")
            with col2:
                delete_btn = st.form_submit_button("刪除此任務")

            if update_btn:
                idx = df.index[df["id"] == selected_id][0]
                df.at[idx, "clip_name"] = clip_name_ed
                df.at[idx, "type"] = clip_type_ed
                df.at[idx, "editor"] = editor_ed
                df.at[idx, "status"] = status_ed
                df.at[idx, "version"] = version_ed
                df.at[idx, "note"] = note_ed
                df.at[idx, "last_update"] = datetime.now().isoformat()
                save_csv("editing_tasks.csv", df)
                st.success("剪輯任務已更新")

            if delete_btn:
                df = df[df["id"] != selected_id]
                save_csv("editing_tasks.csv", df)
                st.warning("剪輯任務已刪除")
                st.experimental_rerun()

    # 剪輯任務附件（回饋截圖、特殊素材說明等）
    st.markdown("---")
    attachment_section(
        module="editing",
        ref_df=df,
        ref_label_col="clip_name",
        ref_id_col="id",
    )


# ========================
# 主程式入口（卡片式側邊欄）
# ========================

def main():
    st.set_page_config(
        page_title="寶鴻 - 形象影片拍攝專案管理系統",
        layout="wide",
    )

    # 全域 CSS（藍色卡片式側邊欄，使用 radio 不會 re-layout）
    st.markdown(
        """
        <style>
        [data-testid="stSidebar"] > div:first-child {
            padding-top: 1rem;
        }
        .sidebar-title {
            font-size: 1.1rem;
            font-weight: 700;
            margin-bottom: 0.25rem;
        }
        .sidebar-subtitle {
            font-size: 0.8rem;
            color: #5f6c80;
            margin-bottom: 1rem;
        }

        /* 把 radio 改成卡片樣式 */
        .stRadio > div[role="radiogroup"] {
            gap: 0.4rem !important;
        }

        .stRadio > div[role="radiogroup"] > label {
            border-radius: 0.9rem;
            padding: 0.55rem 0.9rem;
            border: 1px solid #1e88e5;
            background-color: #e3f2fd;
            color: #1565c0;
            font-size: 0.9rem;
            font-weight: 500;
            width: 100%;
            display: flex;
            align-items: center;
            box-sizing: border-box;
            cursor: pointer;
            box-shadow: 0 0 0 rgba(0,0,0,0);
        }

        /* 隱藏原本的 radio 圓點 */
        .stRadio > div[role="radiogroup"] > label > div:first-child {
            display: none;
        }

        /* 文字容器靠左 */
        .stRadio > div[role="radiogroup"] > label > div:nth-child(2) {
            width: 100%;
        }

        /* hover 效果 */
        .stRadio > div[role="radiogroup"] > label:hover {
            background-color: #d0e7ff;
            border-color: #1565c0;
        }

        /* 已選取（active）狀態：深藍漸層卡片，白字，陰影 */
        .stRadio > div[role="radiogroup"] > label[data-checked="true"] {
            border: 1px solid #1565c0;
            background: linear-gradient(135deg, #1e88e5, #1565c0);
            color: #ffffff;
            font-weight: 600;
            box-shadow: 0 2px 6px rgba(21, 101, 192, 0.3);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    with st.sidebar:
        st.markdown(
            '<div class="sidebar-title">寶鴻 - 形象影片拍攝專案管理系統</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="sidebar-subtitle">選擇管理模組</div>',
            unsafe_allow_html=True,
        )

        # radio 選單（用 emoji + 文案組成 label）
        page_label = st.radio(
            "選擇管理模組",
            [
                "📍 案場素材拍攝管理",
                "📖 訪談腳本 & 分鏡設計",
                "👥 部門 / 工班資訊管理",
                "🗓️ 拍攝流程 & 餐食管理",
                "🎬 剪輯進度管理",
            ],
            label_visibility="collapsed",
        )

    # 主畫面標題
    st.title("寶鴻 - 形象影片拍攝專案管理系統")

    # 根據 label 決定要顯示哪一頁
    if page_label.startswith("📍"):
        page_shooting_materials()
    elif page_label.startswith("📖"):
        page_scripts_storyboard()
    elif page_label.startswith("👥"):
        page_departments()
    elif page_label.startswith("🗓️"):
        page_shooting_schedule()
    elif page_label.startswith("🎬"):
        page_editing_progress()


if __name__ == "__main__":
    main()
