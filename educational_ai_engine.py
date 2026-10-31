"""
Módulo de Generación y Evaluación Formativa con IA (Gemini API)
Diseñado para la aplicación educativa gamificada:
- Nivel 1: Comprensión y memoria (con pistas progresivas)
- Nivel 2: Producción de textos (con rúbrica formativa y ejemplos guía)
- Nivel 3: Lectura multimodal (organizadores visuales / mapas conceptuales)
"""

import os
import json
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from typing import List, Optional


# =====================================================================
# 1. ESQUEMAS DE DATOS (PYDANTIC) PARA GENERACIÓN DE DESAFÍOS
# =====================================================================

class Hint(BaseModel):
    level: int = Field(description="Nivel de la pista (1, 2 o 3)")
    type: str = Field(description="Tipo: 'ubicate', 'concept', 'structure', etc.")
    text: str = Field(description="Texto de orientación pedagógica")

class Level1Question(BaseModel):
    prompt: str = Field(description="Pregunta de comprensión sobre el texto")
    options: List[str] = Field(description="4 opciones rotuladas A), B), C), D)")
    correct_answer: str = Field(description="Opción correcta: 'A', 'B', 'C' o 'D'")
    hints: List[Hint] = Field(description="3 pistas progresivas para no bloquear al alumno")
    explanation: str = Field(description="Explicación formativa de la respuesta")

class Level2WritingTask(BaseModel):
    title: str = Field(description="Título atractivo de la misión de escritura")
    prompt: str = Field(description="Consigna clara del texto a producir (carta, ensayo, etc.)")
    min_words: int = Field(default=80, description="Mínimo de palabras requerido")
    hints: List[Hint] = Field(description="Pistas sobre estructura y conectores recomendados")
    scaffolding_example: str = Field(description="Ejemplo modelo sobre un tema análogo para inspirar")

class Level3MultimodalTask(BaseModel):
    title: str = Field(description="Título de la misión visual")
    prompt: str = Field(description="Consigna para armar el mapa conceptual, organizador o diagrama")
    organizer_type: str = Field(description="Tipo: 'causa_efecto', 'diagrama_flujo', 'red_semantica', 'linea_tiempo'")
    key_nodes: List[str] = Field(description="Conceptos o nodos clave del texto que deben incluirse")
    hints: List[Hint] = Field(description="Pistas de cómo relacionar los nodos con flechas o conectores")
    example_structure: str = Field(description="Ejemplo en texto de cómo organizar los nodos")

class ChallengePackage(BaseModel):
    text_title: str
    summary: str
    level_1: List[Level1Question] = Field(description="2 o 3 preguntas de opción múltiple")
    level_2: Level2WritingTask = Field(description="Reto de redacción guiada")
    level_3: Level3MultimodalTask = Field(description="Reto de organizador visual")


# =====================================================================
# 2. ESQUEMA DE DATOS PARA EVALUACIÓN FORMATIVA
# =====================================================================

class RubricScores(BaseModel):
    content_mastery: int = Field(ge=0, le=35, description="Apropiación del contenido (máx 35)")
    prompt_fulfillment: int = Field(ge=0, le=25, description="Cumplimiento de la consigna y formato (máx 25)")
    coherence_structure: int = Field(ge=0, le=25, description="Coherencia, conectores y estructura (máx 25)")
    originality: int = Field(ge=0, le=15, description="Originalidad y voz propia (máx 15)")
    total_score: int = Field(ge=0, le=100, description="Suma de las 4 dimensiones (0 a 100)")

class PedagogicalFeedback(BaseModel):
    strength: str = Field(description="Felicitar un acierto concreto y específico del estudiante")
    growth_area: str = Field(description="Oportunidad de mejora explicada amablemente")
    micro_revision_challenge: str = Field(description="Un micro-reto accionable para mejorar el texto")

class EvaluationResult(BaseModel):
    scores: RubricScores
    status: str = Field(description="'approved' si total_score >= 70, caso contrario 'needs_revision'")
    feedback: PedagogicalFeedback
    plagiarism_detected: bool = Field(description="True si copió y pegó literalmente párrafos del texto base")
    off_topic: bool = Field(description="True si el texto no responde en absoluto a la consigna")


# =====================================================================
# 3. FUNCIONES PRINCIPALES CON LA API DE GEMINI
# =====================================================================

def get_client() -> genai.Client:
    """Inicializa el cliente de Gemini usando la variable de entorno GEMINI_API_KEY."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("Por favor define la variable de entorno GEMINI_API_KEY.")
    return genai.Client(api_key=api_key)


def generate_challenges_from_text(source_text: str, grade_level: str = "Secundaria") -> ChallengePackage:
    """
    Toma un texto base y genera automáticamente los 3 niveles de juego:
    - Nivel 1: Comprensión con pistas
    - Nivel 2: Redacción con plantilla y ejemplo modelo
    - Nivel 3: Organizador gráfico / lectura multimodal
    """
    client = get_client()

    prompt = f"""
    Eres un diseñador curricular experto en gamificación y lectura crítica para nivel {grade_level}.
    A partir del siguiente texto fuente, genera un paquete pedagógico completo de desafíos.

    Texto fuente:
    """{source_text}"""

    Requisitos:
    - Nivel 1: 2 o 3 preguntas de opción múltiple bien formuladas con 3 pistas progresivas cada una.
    - Nivel 2: 1 consigna de producción escrita que invite a reflexionar o argumentar, con estructura guiada y un ejemplo modelo sobre un tema afín pero distinto.
    - Nivel 3: 1 reto para plasmar las relaciones del texto en un organizador gráfico (causa-efecto, flujo, etc.), indicando los nodos clave.
    """

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=ChallengePackage,
            temperature=0.4
        )
    )

    return ChallengePackage.model_validate_json(response.text)


def evaluate_student_writing(
    source_text: str,
    writing_prompt: str,
    student_essay: str,
    hints_used: int = 0
) -> EvaluationResult:
    """
    Evalúa formativamente el texto de un estudiante contra la rúbrica de 4 dimensiones,
    proporcionando retroalimentación empática y un micro-reto de mejora.
    """
    client = get_client()

    system_instruction = """
    Eres un tutor formativo empático pero riguroso en una app educativa de lectura y escritura.
    Tu objetivo es ayudar a los estudiantes a mejorar mediante andamiaje pedagógico.
    
    Rúbrica de evaluación (Total: 100 puntos):
    1. Apropiación del contenido (0-35): Uso de ideas y evidencias del texto base.
    2. Cumplimiento de la consigna (0-25): Respeta el tipo de texto y propósito solicitado.
    3. Coherencia y conectores (0-25): Fluidez de lectura y conexión lógica entre ideas.
    4. Originalidad y voz propia (0-15): Redacción en palabras propias sin copia literal.
    
    Criterio de aprobación:
    - Si total_score >= 70: status = 'approved'.
    - Si total_score < 70: status = 'needs_revision'. NUNCA uses la palabra 'reprobado'.
    """

    user_content = f"""
    Texto Base de la Lectura:
    """{source_text}"""

    Consigna dada al estudiante:
    """{writing_prompt}"""

    Pistas consultadas por el estudiante: {hints_used}

    Texto escrito por el estudiante:
    """{student_essay}"""
    """

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=user_content,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            response_mime_type="application/json",
            response_schema=EvaluationResult,
            temperature=0.2
        )
    )

    return EvaluationResult.model_validate_json(response.text)


# =====================================================================
# 4. EJEMPLO DE USO LOCAL
# =====================================================================
if __name__ == "__main__":
    print("Módulo educativo cargado exitosamente.")
    print("Para usarlo en tu servidor FastAPI o script:")
    print(">>> package = generate_challenges_from_text('Tu lectura aquí...')")
    print(">>> eval_result = evaluate_student_writing('Lectura...', 'Consigna...', 'Respuesta...')")
