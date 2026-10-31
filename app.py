import streamlit as st
import sqlite3
import json
import os
from datetime import datetime

# Importar el motor de IA previamente creado
from educational_ai_engine import (
    generate_challenges_from_text,
    evaluate_student_writing,
    ChallengePackage,
    EvaluationResult
)

# Configuración de página
st.set_page_config(
    page_title="Misión Lectura - Aventura Formativa",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =====================================================================
# INICIALIZACIÓN DE BASE DE DATOS LOCAL (SQLite)
# =====================================================================
DB_PATH = "mision_lectura.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 1. Usuarios
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        full_name TEXT NOT NULL,
        role TEXT NOT NULL CHECK (role IN ('teacher', 'student')),
        xp_points INTEGER DEFAULT 0
    )
    """)

    # 2. Períodos
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS periods (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        max_bonus_points REAL DEFAULT 2.0
    )
    """)

    # 3. Textos de Lectura
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS texts (
        id TEXT PRIMARY KEY,
        period_id TEXT,
        title TEXT NOT NULL,
        content TEXT NOT NULL,
        summary TEXT,
        order_index INTEGER NOT NULL,
        min_score_to_unlock INTEGER DEFAULT 70,
        FOREIGN KEY(period_id) REFERENCES periods(id)
    )
    """)

    # 4. Desafíos (Niveles 1, 2 y 3)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS challenges (
        id TEXT PRIMARY KEY,
        text_id TEXT,
        level_type TEXT NOT NULL,
        title TEXT NOT NULL,
        prompt TEXT NOT NULL,
        payload TEXT NOT NULL,
        FOREIGN KEY(text_id) REFERENCES texts(id)
    )
    """)

    # 5. Progreso del Estudiante por Texto
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS student_text_progress (
        id TEXT PRIMARY KEY,
        student_id TEXT,
        text_id TEXT,
        status TEXT DEFAULT 'locked',
        level_1_completed INTEGER DEFAULT 0,
        level_2_completed INTEGER DEFAULT 0,
        level_3_completed INTEGER DEFAULT 0,
        final_score REAL DEFAULT 0.0,
        bonus_points_earned REAL DEFAULT 0.0,
        UNIQUE(student_id, text_id)
    )
    """)

    # 6. Entregas / Intentos
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS submissions (
        id TEXT PRIMARY KEY,
        student_id TEXT,
        challenge_id TEXT,
        student_response TEXT,
        score REAL,
        ai_feedback TEXT,
        status TEXT,
        hints_used INTEGER DEFAULT 0,
        evaluated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Datos iniciales de demostración
    cursor.execute("SELECT COUNT(*) FROM users WHERE id = 'prof_demo'")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO users VALUES ('prof_demo', 'Profe Ana', 'teacher', 0)")
        cursor.execute("INSERT INTO users VALUES ('est_demo', 'Estudiante Alex', 'student', 150)")
        cursor.execute("INSERT INTO periods VALUES ('per_demo', 'Primer Período - Comprensión Crítica', 2.0)")

    conn.commit()
    conn.close()

init_db()

# =====================================================================
# FUNCIONES AUXILIARES DE BASE DE DATOS
# =====================================================================
def get_db():
    return sqlite3.connect(DB_PATH)

def ensure_student_progress(student_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, order_index FROM texts ORDER BY order_index ASC")
    all_texts = cursor.fetchall()
    
    for idx, (text_id, order_index) in enumerate(all_texts):
        initial_status = "unlocked" if order_index == 1 else "locked"
        cursor.execute("""
            INSERT OR IGNORE INTO student_text_progress (id, student_id, text_id, status)
            VALUES (?, ?, ?, ?)
        """, (f"{student_id}_{text_id}", student_id, text_id, initial_status))
    conn.commit()
    conn.close()

# =====================================================================
# INTERFAZ PRINCIPAL
# =====================================================================
st.sidebar.title("🎮 Misión Lectura")
st.sidebar.markdown("**Plataforma Formativa Gamificada**")

role = st.sidebar.radio("Elige tu rol:", ["👨‍🏫 Panel del Docente", "🎒 Modo Aventura (Estudiante)"])

if role == "👨‍🏫 Panel del Docente":
    st.title("📚 Panel de Gestión y Generación Curricular")
    st.markdown("Carga una lectura de clase. El motor de IA generará automáticamente la ruta de 3 niveles con pistas formativas y rúbrica.")

    col1, col2 = st.columns([2, 1])
    with col1:
        text_title = st.text_input("Título de la lectura:", placeholder="Ej. El misterio de los arrecifes de coral")
        content_input = st.text_area(
            "Contenido del texto:",
            height=260,
            placeholder="Pega aquí el artículo, cuento o fragmento histórico que tus alumnos leerán..."
        )
    with col2:
        st.subheader("Configuración de Misión")
        order_index = st.number_input("Orden en la ruta (Nº Misión):", min_value=1, value=1)
        grade_level = st.selectbox("Nivel educativo:", ["Primaria Alta (5to-6to)", "Secundaria Inicial (1ro-2do)", "Secundaria Alta (3ro-5to)", "Bachillerato / Preuniversitario"])
        min_unlock = st.slider("Puntaje mínimo para desbloquear siguiente texto (%):", 50, 100, 70)

    if st.button("✨ Generar Desafíos y Guardar en la Misión", type="primary"):
        if not content_input.strip() or not text_title.strip():
            st.error("Por favor completa el título y el contenido del texto.")
        else:
            with st.spinner("La IA pedagógica está analizando el texto y estructurando los 3 niveles formativos..."):
                try:
                    pkg = generate_challenges_from_text(content_input, grade_level)
                    conn = get_db()
                    c = conn.cursor()
                    text_id = f"txt_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                    
                    c.execute("""
                        INSERT INTO texts (id, period_id, title, content, summary, order_index, min_score_to_unlock)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (text_id, 'per_demo', text_title, content_input, pkg.summary, order_index, min_unlock))
                    
                    # Nivel 1: Preguntas de comprensión
                    c.execute("""
                        INSERT INTO challenges (id, text_id, level_type, title, prompt, payload)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (f"ch1_{text_id}", text_id, 'level_1_comprehension', 'Nivel 1: El Radar', 'Preguntas de comprensión', json.dumps([q.model_dump() for q in pkg.level_1])))

                    # Nivel 2: Redacción guiada
                    c.execute("""
                        INSERT INTO challenges (id, text_id, level_type, title, prompt, payload)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (f"ch2_{text_id}", text_id, 'level_2_creation', 'Nivel 2: Taller del Escritor', pkg.level_2.prompt, json.dumps(pkg.level_2.model_dump())))

                    # Nivel 3: Multimodal
                    c.execute("""
                        INSERT INTO challenges (id, text_id, level_type, title, prompt, payload)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (f"ch3_{text_id}", text_id, 'level_3_multimodal', 'Nivel 3: El Cartógrafo Visual', pkg.level_3.prompt, json.dumps(pkg.level_3.model_dump())))

                    conn.commit()
                    conn.close()
                    st.success("¡Misión creada exitosamente! Tus estudiantes ya tienen disponible esta aventura.")
                    st.json(pkg.model_dump())
                except Exception as e:
                    st.error(f"Error al conectar con la API de IA: {str(e)}")

    st.markdown("---")
    st.subheader("📋 Misiones Publicadas en este Período")
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT order_index, title, summary FROM texts ORDER BY order_index ASC")
    rows = c.fetchall()
    conn.close()
    if rows:
        for r in rows:
            st.markdown(f"**Misión #{r[0]}: {r[1]}**")
            st.caption(f"Resumen: {r[2]}")
    else:
        st.info("Aún no has publicado misiones. Carga tu primer texto arriba.")

elif role == "🎒 Modo Aventura (Estudiante)":
    student_id = "est_demo"
    ensure_student_progress(student_id)

    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT full_name, xp_points FROM users WHERE id = ?", (student_id,))
    u_info = c.fetchone()
    st.title(f"🚀 ¡Bienvenido a tu Aventura de Lectura, {u_info[0]}!")
    
    # Barra de Gamificación superior
    col_xp, col_bonus, col_rank = st.columns(3)
    col_xp.metric("✨ Puntos de Experiencia (XP)", f"{u_info[1]} XP")
    
    # Calcular puntos extra acumulados para nota final
    c.execute("SELECT SUM(bonus_points_earned) FROM student_text_progress WHERE student_id = ?", (student_id,))
    total_bonus = c.fetchone()[0] or 0.0
    col_bonus.metric("🎯 Puntos Extra Ganados", f"+{total_bonus:.1f} pts")
    col_rank.metric("🏅 Rango", "Explorador Crítico")

    st.markdown("---")
    st.subheader("🗺️ Tu Ruta de Misiones Desbloqueables")

    c.execute("""
        SELECT t.id, t.order_index, t.title, p.status, p.level_1_completed, p.level_2_completed, p.level_3_completed
        FROM texts t
        JOIN student_text_progress p ON t.id = p.text_id
        WHERE p.student_id = ?
        ORDER BY t.order_index ASC
    """, (student_id,))
    missions = c.fetchall()

    if not missions:
        st.warning("El docente aún no ha publicado textos en este período. ¡Vuelve pronto!")
    else:
        # Selector de misión disponible
        available_missions = {f"Misión {m[1]}: {m[2]}": m for m in missions}
        selected_label = st.selectbox("Selecciona una misión activa:", list(available_missions.keys()))
        current_mission = available_missions[selected_label]
        text_id, order_idx, m_title, m_status, l1_ok, l2_ok, l3_ok = current_mission

        if m_status == "locked":
            st.error("🔒 Esta misión está bloqueada. Debes completar y aprobar la misión anterior para desbloquearla.")
        else:
            # Obtener contenido del texto y desafíos
            c.execute("SELECT content FROM texts WHERE id = ?", (text_id,))
            text_content = c.fetchone()[0]

            with st.expander("📖 Haz clic aquí para leer el texto base de la misión", expanded=True):
                st.markdown(text_content)

            # Pestañas de niveles
            tab1, tab2, tab3 = st.tabs([
                f"Nivel 1: Comprensión {'✅' if l1_ok else '🎯'}",
                f"Nivel 2: Taller de Escritura {'✅' if l2_ok else '✍️'}",
                f"Nivel 3: Organizador Visual {'✅' if l3_ok else '🧩'}"
            ])

            # NIVEL 1
            with tab1:
                st.markdown("### 🎯 Nivel 1: Demuestra tu Comprensión")
                c.execute("SELECT payload FROM challenges WHERE text_id = ? AND level_type = 'level_1_comprehension'", (text_id,))
                row_l1 = c.fetchone()
                if row_l1:
                    questions = json.loads(row_l1[0])
                    student_answers = {}
                    
                    for i, q in enumerate(questions):
                        st.markdown(f"**Pregunta {i+1}: {q['prompt']}**")
                        user_choice = st.radio(f"Selecciona tu respuesta para la pregunta {i+1}:", q['options'], key=f"q_{text_id}_{i}")
                        student_answers[i] = user_choice
                        
                        # Sistema de Andamiaje / Pistas
                        with st.expander(f"💡 ¿Necesitas una pista para la pregunta {i+1}?"):
                            for h in q.get('hints', []):
                                st.info(f"**Pista Nivel {h['level']}:** {h['text']}")
                        st.write("")

                    if st.button("Verificar Respuestas Nivel 1", key=f"btn_l1_{text_id}"):
                        correct_count = 0
                        for i, q in enumerate(questions):
                            choice_letter = student_answers[i][0] # Toma 'A', 'B', 'C', 'D'
                            if choice_letter == q['correct_answer']:
                                correct_count += 1
                        
                        score_pct = int((correct_count / len(questions)) * 100)
                        if score_pct >= 66:
                            st.success(f"¡Excelente! Acertaste {correct_count}/{len(questions)} ({score_pct}%). Has superado el Nivel 1 y sumas +50 XP.")
                            c.execute("""
                                UPDATE student_text_progress 
                                SET level_1_completed = 1, status = 'in_progress' 
                                WHERE student_id = ? AND text_id = ?
                            """, (student_id, text_id))
                            c.execute("UPDATE users SET xp_points = xp_points + 50 WHERE id = ?", (student_id,))
                            conn.commit()
                            st.rerun()
                        else:
                            st.warning(f"Obtuviste {correct_count}/{len(questions)}. Revisa las pistas formativas y vuelve a intentarlo.")

            # NIVEL 2
            with tab2:
                st.markdown("### ✍️ Nivel 2: Taller del Escritor (Creación)")
                if not l1_ok:
                    st.info("Completa primero el Nivel 1 para habilitar tu pluma de escritor.")
                else:
                    c.execute("SELECT prompt, payload FROM challenges WHERE text_id = ? AND level_type = 'level_2_creation'", (text_id,))
                    row_l2 = c.fetchone()
                    if row_l2:
                        l2_prompt = row_l2[0]
                        l2_payload = json.loads(row_l2[1])
                        st.markdown(f"**Consigna:** {l2_prompt}")
                        st.caption(f"Extensión mínima sugerida: {l2_payload.get('min_words', 80)} palabras.")

                        # Andamiaje para la escritura
                        with st.expander("💡 Pistas de redacción y plantilla de inicio"):
                            for h in l2_payload.get('hints', []):
                                st.markdown(f"• **{h.get('type', 'Guía').capitalize()}:** {h['text']}")

                        with st.expander("📖 Ver ejemplo modelo inspirador"):
                            st.markdown(l2_payload.get('scaffolding_example', 'Escribe con tus propias palabras conectando tus argumentos.'))

                        student_draft = st.text_area("Escribe tu texto aquí:", height=180, key=f"draft_{text_id}")

                        if st.button("Enviar texto para evaluación formativa", key=f"btn_eval_{text_id}"):
                            if len(student_draft.split()) < 30:
                                st.warning("Tu texto es muy breve. Desarrolla un poco más tus ideas antes de enviar.")
                            else:
                                with st.spinner("El tutor IA está analizando tu texto con la rúbrica formativa..."):
                                    eval_res = evaluate_student_writing(text_content, l2_prompt, student_draft)
                                    
                                    # Mostrar resultados con pedagogía del sándwich
                                    st.subheader(f"Resultado: {eval_res.scores.total_score} / 100")
                                    
                                    # Rúbrica desglosada
                                    r_col1, r_col2, r_col3, r_col4 = st.columns(4)
                                    r_col1.metric("Apropiación (35)", eval_res.scores.content_mastery)
                                    r_col2.metric("Consigna (25)", eval_res.scores.prompt_fulfillment)
                                    r_col3.metric("Coherencia (25)", eval_res.scores.coherence_structure)
                                    r_col4.metric("Originalidad (15)", eval_res.scores.originality)

                                    st.success(f"**Fortaleza destacada:** {eval_res.feedback.strength}")
                                    st.info(f"**Oportunidad de crecimiento:** {eval_res.feedback.growth_area}")
                                    st.warning(f"**Micro-reto de mejora:** {eval_res.feedback.micro_revision_challenge}")

                                    if eval_res.status == "approved":
                                        st.balloons()
                                        st.success("🎉 ¡Misión cumplida! Tu borrador fue aprobado. Has ganado +100 XP.")
                                        c.execute("""
                                            UPDATE student_text_progress 
                                            SET level_2_completed = 1 
                                            WHERE student_id = ? AND text_id = ?
                                        """, (student_id, text_id))
                                        c.execute("UPDATE users SET xp_points = xp_points + 100 WHERE id = ?", (student_id,))
                                        conn.commit()
                                        st.rerun()
                                    else:
                                        st.warning("Tu borrador está en buen camino pero aún requiere un ajuste. Modifícalo según el micro-reto y vuelve a enviarlo.")

            # NIVEL 3
            with tab3:
                st.markdown("### 🧩 Nivel 3: El Cartógrafo Visual (Lectura Multimodal)")
                if not l2_ok:
                    st.info("Supera el Nivel 2 para desbloquear el reto multimodal.")
                else:
                    c.execute("SELECT prompt, payload FROM challenges WHERE text_id = ? AND level_type = 'level_3_multimodal'", (text_id,))
                    row_l3 = c.fetchone()
                    if row_l3:
                        l3_prompt = row_l3[0]
                        l3_payload = json.loads(row_l3[1])
                        st.markdown(f"**Reto Visual:** {l3_prompt}")
                        st.markdown(f"**Tipo de organizador:** `{l3_payload.get('organizer_type', 'organizador visual')}`")
                        
                        st.markdown("**Nodos y conceptos clave que debes incluir en tu esquema:**")
                        nodes = l3_payload.get('key_nodes', [])
                        st.write(" • " + " • ".join(nodes))

                        with st.expander("💡 Pistas para vincular conceptos con flechas"):
                            for h in l3_payload.get('hints', []):
                                st.markdown(f"• {h['text']}")
                            st.markdown(f"**Estructura sugerida:**
`{l3_payload.get('example_structure', '')}`")

                        student_diagram_text = st.text_area(
                            "Representa aquí tu esquema conceptual (o describe la relación entre nodos):",
                            placeholder="Ejemplo: [Causa A] --> produce --> [Efecto B] --> culmina en --> [Impacto C]",
                            height=140,
                            key=f"diagram_{text_id}"
                        )

                        if st.button("Finalizar Misión y Canjear Puntos Extra", type="primary", key=f"btn_l3_{text_id}"):
                            if len(student_diagram_text.strip()) < 20:
                                st.warning("Completa tu organizador con los nodos clave antes de finalizar.")
                            else:
                                # Completar texto y desbloquear el siguiente
                                c.execute("""
                                    UPDATE student_text_progress 
                                    SET level_3_completed = 1, status = 'completed', bonus_points_earned = 0.5
                                    WHERE student_id = ? AND text_id = ?
                                """, (student_id, text_id))
                                
                                # Desbloquear siguiente texto (order_index + 1)
                                c.execute("SELECT id FROM texts WHERE order_index = ?", (order_idx + 1,))
                                next_txt = c.fetchone()
                                if next_txt:
                                    c.execute("""
                                        UPDATE student_text_progress 
                                        SET status = 'unlocked' 
                                        WHERE student_id = ? AND text_id = ? AND status = 'locked'
                                    """, (student_id, next_txt[0]))
                                
                                c.execute("UPDATE users SET xp_points = xp_points + 150 WHERE id = ?", (student_id,))
                                conn.commit()
                                st.balloons()
                                st.success("🏆 ¡FELICITACIONES! Has completado todos los niveles de esta misión. Ganaste +150 XP y sumaste +0.5 puntos para tu nota final.")
                                st.info("¡El siguiente texto de la ruta ha sido desbloqueado en tu mapa de misiones!")
                                st.rerun()

    conn.close()
