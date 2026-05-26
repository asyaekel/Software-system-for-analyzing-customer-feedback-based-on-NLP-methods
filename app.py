import streamlit as st
import pandas as pd
import plotly.express as px
from nlp_engine import PureNLPFeedbackAnalyzer
from database import init_db, register_user, verify_user, save_analysis_result, get_user_data_as_dataframe, delete_file_data

# Ініціалізуємо БД при запуску
init_db()

# Налаштування сторінки
st.set_page_config(page_title="NLP SaaS: Аналітика Відгуків", layout="wide")

# Завантажуємо модель у кеш Streamlit, щоб вона не завантажувалася заново при кожному кліку
@st.cache_resource
def load_analyzer():
    return PureNLPFeedbackAnalyzer()

# --- БЛОК АВТОРИЗАЦІЇ ---
if 'user_id' not in st.session_state:
    st.title("🔐 Вхід у систему NLP Аналітики")
    tab_login, tab_register = st.tabs(["Вхід", "Реєстрація нового магазину"])
    
    with tab_login:
        login_user = st.text_input("Логін", key="login_user")
        login_pass = st.text_input("Пароль", type="password", key="login_pass")
        if st.button("Увійти"):
            u_id = verify_user(login_user, login_pass)
            if u_id:
                st.session_state['user_id'] = u_id
                st.session_state['username'] = login_user
                st.rerun()
            else:
                st.error("Невірний логін або пароль!")
    
    with tab_register:
        reg_user = st.text_input("Придумайте логін", key="reg_user")
        reg_pass = st.text_input("Придумайте пароль", type="password", key="reg_pass")
        if st.button("Зареєструватися"):
            if reg_user and reg_pass:
                if register_user(reg_user, reg_pass):
                    st.success("Успішна реєстрація! Тепер ви можете увійти на сусідній вкладці.")
                else:
                    st.error("Такий користувач вже існує.")
            else:
                st.warning("Заповніть всі поля.")
    st.stop() # Зупиняємо виконання коду, поки користувач не увійде

# --- ОСНОВНИЙ ДОДАТОК (Для авторизованих) ---

st.sidebar.title(f"👤 Ваш акаунт: {st.session_state['username']}")
if st.sidebar.button("🚪 Вийти з акаунту"):
    del st.session_state['user_id']
    del st.session_state['username']
    st.rerun()

analyzer = load_analyzer()
st.title("🚀 Динамічний Дашборд NLP Аналітики")

tab_single, tab_bulk, tab_dashboard = st.tabs(["📝 Одиничний аналіз", "📁 Завантажити CSV", "📊 Аналітика та Дашборд"])

# ВКЛАДКА 1: Одиничний відгук
with tab_single:
    st.subheader("Тестування моделі на одному відгуку")
    user_input = st.text_area("Введіть текст відгуку:", height=150)
    if st.button("Проаналізувати відгук"):
        if user_input:
            with st.spinner("Аналізую..."):
                result = analyzer.analyze_whole_text(user_input)
                st.success("Аналіз успішно завершено! (Результат не збережено у БД)")
                st.json(result)
        else:
            st.warning("Введіть текст відгуку.")

# ВКЛАДКА 2: Масове завантаження CSV
with tab_bulk:
    st.subheader("Масовий аналіз тисяч відгуків")
    st.info("Ваш CSV файл повинен містити хоча б одну колонку з текстом відгуків.")
    uploaded_file = st.file_uploader("Завантажте CSV файл", type=['csv'])
    
    if uploaded_file is not None:
        df_upload = pd.read_csv(uploaded_file)
        st.write("Попередній перегляд вашого файлу:", df_upload.head(3))
        
        # Користувач сам обирає, в якій колонці знаходиться текст
        text_col = st.selectbox("Оберіть колонку з текстом відгуку:", df_upload.columns)
            
        if st.button("▶ Почати масовий аналіз"):
            file_name = uploaded_file.name
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            total = len(df_upload)
            for i, row in df_upload.iterrows():
                text = str(row[text_col])
                if text.strip() and text.lower() != 'nan':
                    res = analyzer.analyze_whole_text(text)
                    save_analysis_result(st.session_state['user_id'], file_name, res)
                
                # Оновлюємо прогрес-бар
                progress_bar.progress((i + 1) / total)
                status_text.text(f"Обробка: {i+1} з {total}")
                
            st.success("Масовий аналіз завершено! Всі дані збережено. Перейдіть на вкладку 'Аналітика та Дашборд'.")

# ВКЛАДКА 3: Дашборд
with tab_dashboard:
    df = get_user_data_as_dataframe(st.session_state['user_id'])
    
    if df.empty:
        st.info("У вас ще немає проаналізованих даних. Використайте сусідні вкладки, щоб додати відгуки.")
    else:
        aspect_columns = [
            'quality', 'delivery', 'support', 'price', 'ui_ux', 'packaging', 
            'assortment', 'returns', 'loyalty', 'recommendation', 'overall_satisfaction'
        ]
        
        available_files = df['file_name'].unique().tolist()
        selected_files = st.multiselect("📁 Оберіть файли/періоди для аналізу (для порівняння оберіть кілька):", available_files, default=available_files)
        
        if not selected_files:
            st.warning("Оберіть хоча б один файл для відображення аналітики.")
        else:
            # Фільтруємо дані за обраними файлами
            filtered_df = df[df['file_name'].isin(selected_files)]
            means_global = filtered_df[aspect_columns].mean().round(1)
            
            # Відкидаємо "overall_satisfaction" для пошуку сильних/слабких сторін та інсайтів
            specific_aspects = [col for col in aspect_columns if col != 'overall_satisfaction']
            means_specific = means_global.drop('overall_satisfaction', errors='ignore')
            
            # --- 1. ВІДЖЕТИ KPI ---
            st.subheader("💡 Глобальні показники (KPI)")
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Відгуків у вибраних файлах", len(filtered_df))
            with col2:
                global_sat = filtered_df['overall_satisfaction'].mean().round(1) if 'overall_satisfaction' in filtered_df.columns and pd.notna(filtered_df['overall_satisfaction'].mean()) else "-"
                st.metric("Загальне задоволення", global_sat)
            with col3:
                if not means_specific.dropna().empty:
                    best_aspect = means_specific.idxmax()
                    st.metric("Сильна сторона", best_aspect, f"{means_specific[best_aspect]} / 10", delta_color="normal")
                else:
                    st.metric("Сильна сторона", "-", "-")
            with col4:
                if not means_specific.dropna().empty:
                    worst_aspect = means_specific.idxmin()
                    st.metric("Вузьке місце (Проблема)", worst_aspect, f"{means_specific[worst_aspect]} / 10", delta_color="inverse")
                else:
                    st.metric("Вузьке місце", "-", "-")
                
            st.markdown("---")
            
            # --- 2. АВТОМАТИЧНІ ІНСАЙТИ ---
            st.subheader("🧠 Автоматичні інсайти")
            ins1, ins2, ins3, ins4 = st.columns(4)
            
            counts = filtered_df[specific_aspects].count()
            stds = filtered_df[specific_aspects].std().round(2)
            
            with ins1:
                if not means_specific.dropna().empty:
                    st.success(f"**👍 Що працює найкраще:**\n\n**{means_specific.idxmax()}** отримує стабільно високі оцінки. Продовжуйте в тому ж дусі!")
                else:
                    st.success("Бракує даних")
            with ins2:
                if not means_specific.dropna().empty:
                    st.error(f"**⚠️ Критична зона:**\n\n**{means_specific.idxmin()}** псує загальне враження. Це головна причина невдоволення клієнтів.")
                else:
                    st.error("Бракує даних")
            with ins3:
                if not counts.dropna().empty and counts.max() > 0:
                    st.info(f"**💬 Найбільш обговорюване:**\n\nКлієнти найчастіше пишуть про **{counts.idxmax()}** ({counts.max()} згадок). Це їх найбільше хвилює.")
                else:
                    st.info("Бракує даних")
            with ins4:
                if not stds.dropna().empty and pd.notna(stds.max()):
                    st.warning(f"**⚡ Найбільш суперечливе:**\n\n**{stds.idxmax()}** має найбільший розкид оцінок (відхилення {stds.max()}). Думки клієнтів дуже різняться.")
                else:
                    st.warning("Бракує даних")

            st.markdown("---")

            # --- 3. ІНТЕРАКТИВНІ ФІЛЬТРИ ДЛЯ ГРАФІКІВ ТА ТАБЛИЦЬ ---
            st.markdown("### 🎛 Налаштування детального відображення")
            col_filter1, col_filter2, col_filter3 = st.columns(3)
            with col_filter1:
                selected_aspects = st.multiselect(
                    "Оберіть критерії для графіків/таблиць:", 
                    aspect_columns, 
                    default=aspect_columns
                )
            with col_filter2:
                metrics_mapping = {
                    'mean': 'Середнє (Avg)', 'median': 'Медіана (Median)', 'min': 'Мінімум (Min)', 
                    'max': 'Максимум (Max)', 'std': 'Відхилення (Std)', 'count': 'Кількість згадок'
                }
                selected_metrics = st.multiselect(
                    "Оберіть метрики для детальної таблиці:", 
                    list(metrics_mapping.keys()), 
                    default=['mean', 'median', 'min', 'max'],
                    format_func=lambda x: metrics_mapping[x]
                )
            with col_filter3:
                chart_metric = st.selectbox(
                    "Оберіть метрику для графіків (Bar, Radar):",
                    ['mean', 'median', 'min', 'max'],
                    format_func=lambda x: metrics_mapping[x]
                )
                
            if not selected_aspects:
                st.warning("Оберіть хоча б один критерій у фільтрі.")
            else:
                # --- 4. ГРАФІКИ ---
                st.subheader("📈 Порівняльна візуалізація даних")
                tab_charts1, tab_charts2, tab_charts3 = st.tabs(["📊 Порівняння рейтингів (Bar Chart)", "🕸 Профіль (Radar Chart)", "📦 Розкид (Box Plot)"])
                
                metric_label = metrics_mapping.get(chart_metric, chart_metric)
                # Групуємо дані по файлах для порівняння
                df_grouped = filtered_df.groupby('file_name')[selected_aspects].agg(chart_metric).round(1).reset_index()
                df_melted_grouped = df_grouped.melt(id_vars=['file_name'], value_vars=selected_aspects, var_name='Критерій', value_name=metric_label)
                
                with tab_charts1:
                    fig_bar = px.bar(df_melted_grouped, x='Критерій', y=metric_label, color='file_name', barmode='group', range_y=[0, 10], title=f"Порівняння файлів за критеріями ({metric_label})")
                    st.plotly_chart(fig_bar, use_container_width=True)
                    
                with tab_charts2:
                    fig_radar = px.line_polar(df_melted_grouped, r=metric_label, theta='Критерій', color='file_name', line_close=True, range_r=[0, 10], markers=True, title=f"Радар порівняння ({metric_label})")
                    st.plotly_chart(fig_radar, use_container_width=True)
                    
                with tab_charts3:
                    df_melted_raw = filtered_df.melt(id_vars=['id', 'file_name'], value_vars=selected_aspects, var_name='Критерій', value_name='Оцінка').dropna()
                    fig_box = px.box(df_melted_raw, x='Критерій', y='Оцінка', color='file_name', title="Розкид оцінок по кожному критерію (в розрізі файлів)")
                    st.plotly_chart(fig_box, use_container_width=True)
                
                st.markdown("---")
                
                # --- 5. ДЕТАЛЬНА АГРЕГОВАНА СТАТИСТИКА ---
                st.subheader("📋 Порівняльна агрегована статистика")
                if selected_metrics:
                    # Розбиваємо метрики по вкладках для зручності
                    metric_tabs = st.tabs([metrics_mapping[m] for m in selected_metrics])
                    
                    for i, metric in enumerate(selected_metrics):
                        with metric_tabs[i]:
                            # Створюємо таблицю тільки для поточної метрики
                            metric_df = filtered_df.groupby('file_name')[selected_aspects].agg(metric).round(2).T
                            metric_df.index.name = "Критерій"
                            
                            # Робимо кольорову Heatmap-таблицю (від червоного до зеленого) для оцінок
                            if metric in ['mean', 'median', 'min', 'max']:
                                styled_df = metric_df.style.background_gradient(cmap='RdYlGn', axis=None, vmin=1, vmax=10)
                                st.dataframe(styled_df, use_container_width=True)
                            else:
                                st.dataframe(metric_df, use_container_width=True)
                    
                    # Підготовка загального файлу для скачування (всі метрики разом, як раніше)
                    full_stats_df = filtered_df.groupby('file_name')[selected_aspects].agg(selected_metrics).round(2).T
                    if isinstance(full_stats_df.index, pd.MultiIndex):
                        full_stats_df.index = [f"{aspect} ({metrics_mapping.get(metric, metric)})" for aspect, metric in full_stats_df.index]
                    
                    csv_data = full_stats_df.to_csv(index_label="Критерій").encode('utf-8')
                    st.download_button(
                        label="📥 Завантажити повний звіт (усі обрані метрики в одному CSV)",
                        data=csv_data,
                        file_name='aggregated_comparison_report.csv',
                        mime='text/csv',
                    )
                else:
                    st.info("Оберіть хоча б одну метрику для детальної таблиці.")
                    
                st.markdown("---")
            
            # --- БЛОК ВИДАЛЕННЯ ФАЙЛІВ (В САМОМУ НИЗУ) ---
            st.subheader("⚙️ Управління даними")
            with st.expander("🗑️ Керування файлами (Видалити дані)"):
                st.warning("Увага! Ця дія незворотна. Усі аналітичні дані обраного файлу будуть видалені з бази.")
                del_col1, del_col2 = st.columns([3, 1])
                with del_col1:
                    file_to_delete = st.selectbox("Оберіть файл для видалення:", available_files, key="del_file")
                with del_col2:
                    st.write("") 
                    st.write("") 
                    if st.button("❌ Видалити файл", type="primary", use_container_width=True):
                        delete_file_data(st.session_state['user_id'], file_to_delete)
                        st.success(f"Дані файлу '{file_to_delete}' успішно видалено!")
                        st.rerun()
