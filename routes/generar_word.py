# ─────────────────────────────────────────────────────────────────────────────
# IMPORTS
# ─────────────────────────────────────────────────────────────────────────────
import io
import json
import os

import fitz
from flask import (
    Blueprint,
    Response,
    flash,
    redirect,
    send_file,
    stream_with_context,
    url_for,
)


from db.cache import pdf_cache, preview_cache
from db.conexion import get_connection, fetch_one
from config import ANIOS_DECRETADOS, now_pe

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTES Y CONFIGURACIÓN
# ─────────────────────────────────────────────────────────────────────────────
_BASE_DIR = os.path.dirname(os.path.dirname(__file__))
FONTS_DIR = os.path.join(_BASE_DIR, "static", "fonts")
IMAGES_DIR = os.path.join(_BASE_DIR, "plantillas_word", "Images")
PORTADA_IMG = os.path.join(IMAGES_DIR, "PORTADA.png")
CONTRAPORTADA_IMG = os.path.join(IMAGES_DIR, "CONTRAPORTADA.png")

MESES = {
    1: "enero",
    2: "febrero",
    3: "marzo",
    4: "abril",
    5: "mayo",
    6: "junio",
    7: "julio",
    8: "agosto",
    9: "septiembre",
    10: "octubre",
    11: "noviembre",
    12: "diciembre",
}

# Página A4
PAGE_W, PAGE_H = A4
MARGIN_L = 2.5 * cm
MARGIN_R = 2.0 * cm
MARGIN_T = 2.0 * cm
MARGIN_B = 2.0 * cm
CONTENT_W = PAGE_W - MARGIN_L - MARGIN_R

def get_anio_texto() -> str:
    """Retorna el texto del año basándose en la fecha actual."""
    anio_actual = now_pe().year
    row = fetch_one(
        "SELECT nombre FROM anios_decretados WHERE anio = %s AND estado = 'activo'",
        (anio_actual,),
    )
    if row:
        return row["nombre"]
    return ANIOS_DECRETADOS.get(anio_actual, f"Año {anio_actual}")


# Colores UAI
AZUL_OSCURO = colors.HexColor("#003B91")
AZUL_MEDIO = colors.HexColor("#003B91")
AZUL_TABLA = colors.HexColor("#003B91")
BLANCO = colors.white


# ─────────────────────────────────────────────────────────────────────────────
# FUENTES
# ─────────────────────────────────────────────────────────────────────────────
def _registrar_fuentes():
    regular = os.path.join(FONTS_DIR, "Poppins-Regular.ttf")
    bold = os.path.join(FONTS_DIR, "Poppins-Bold.ttf")
    if os.path.exists(regular) and os.path.exists(bold):
        pdfmetrics.registerFont(TTFont("Poppins", regular))
        pdfmetrics.registerFont(TTFont("Poppins-Bold", bold))
        return "Poppins", "Poppins-Bold"
    return "Helvetica", "Helvetica-Bold"


FONT_PRINCIPAL, FONT_BOLD = _registrar_fuentes()

# ─────────────────────────────────────────────────────────────────────────────
# BLUEPRINT
# ─────────────────────────────────────────────────────────────────────────────
bp_word = Blueprint("generar_word", __name__)

# ─────────────────────────────────────────────────────────────────────────────
# BASE DE DATOS
# ─────────────────────────────────────────────────────────────────────────────
_ORDEN_CICLO = "CASE cp.ciclo WHEN 'I' THEN 1 WHEN 'II' THEN 2 WHEN 'III' THEN 3 WHEN 'IV' THEN 4 WHEN 'V' THEN 5 WHEN 'VI' THEN 6 WHEN 'VII' THEN 7 WHEN 'VIII' THEN 8 WHEN 'IX' THEN 9 WHEN 'X' THEN 10 END"


def obtener_datos(solicitud_id: int) -> dict:
    conn = get_connection()
    cur = conn.cursor(dictionary=True)

    cur.execute(
        """
        SELECT s.*,
               COALESCE(p.apellidos_nombres, '')                              AS nombre,
               COALESCE(p.dni, '')                                            AS dni,
               CASE WHEN p.sexo IN ('F','FEMENINO','MUJER') THEN 'F'
                    ELSE 'M' END                                              AS genero,
               COALESCE(p.programa, '')                                       AS programa,
               COALESCE(p.modalidad_estudios, '')                             AS modalidad,
               COALESCE(NULLIF(p.institucion_procedencia,''), pe.nombre_plan, '') AS ies_origen,
               COALESCE(f.nombre, p.facultad, '')                             AS facultad_nombre,
               COALESCE(c.nombre, c2.nombre, p.programa, '')                  AS carrera_nombre
        FROM solicitudes s
        LEFT JOIN postulantes    p  ON s.postulante_id   = p.id
        LEFT JOIN planes_estudio pe ON s.plan_externo_id = pe.id
        LEFT JOIN carreras       c  ON s.carrera_id      = c.id
        LEFT JOIN carreras       c2 ON s.carrera_id IS NULL AND LOWER(TRIM(p.programa)) = LOWER(TRIM(c2.nombre))
        LEFT JOIN facultades     f  ON COALESCE(c.facultad_id, c2.facultad_id) = f.id
        WHERE s.id = %s
    """,
        (solicitud_id,),
    )
    solicitud = cur.fetchone()

    # Todos los cursos en una sola query, particionados en Python
    cur.execute(
        f"""
        SELECT cp.ciclo, cp.nombre_curso, cp.creditos, sc.nota, sc.estado, sc.periodo_lectivo
        FROM solicitud_cursos sc
        JOIN cursos_plan cp ON sc.curso_local_id = cp.id
        WHERE sc.solicitud_id = %s
        ORDER BY {_ORDEN_CICLO}
    """,
        (solicitud_id,),
    )
    todos = cur.fetchall()
    solicitud["convalidados"] = [c for c in todos if c["estado"] == "convalidado"]
    solicitud["examenes"] = [c for c in todos if c["estado"] == "examen_suficiencia"]
    solicitud["no_convalidados"] = [
        {"ciclo": c["ciclo"], "nombre_curso": c["nombre_curso"],
         "creditos": c["creditos"], "periodo_lectivo": c["periodo_lectivo"]}
        for c in todos if c["estado"] == "pendiente"
    ]
    cur.close()
    conn.close()
    return solicitud


# ─────────────────────────────────────────────────────────────────────────────
# ESTILOS
# ─────────────────────────────────────────────────────────────────────────────
def build_styles() -> dict:
    def S(name, **kw):
        return ParagraphStyle(name, **kw)

    FP, FB = FONT_PRINCIPAL, FONT_BOLD
    AM, AO = AZUL_MEDIO, AZUL_OSCURO

    return {
        # Encabezado de página
        "header_facultad": S(
            "header_facultad", fontName=FB, fontSize=9, textColor=AO, leading=11
        ),
        "header_carrera": S(
            "header_carrera", fontName=FP, fontSize=8, textColor=AO, leading=11
        ),
        # Bloque de identificación
        "decreto": S(
            "decreto",
            fontName=FB,
            fontSize=9,
            textColor=AM,
            alignment=TA_CENTER,
            leading=12,
            spaceAfter=4,
        ),
        "fecha": S(
            "fecha",
            fontName=FP,
            fontSize=10,
            textColor=AM,
            alignment=TA_RIGHT,
            leading=13,
            spaceAfter=12,
        ),
        "dest_codigo": S(
            "dest_codigo", fontName=FB, fontSize=10, textColor=AM, leading=14
        ),
        "dest_nombre": S(
            "dest_nombre", fontName=FP, fontSize=10, textColor=AM, leading=14
        ),
        "dest_presente": S(
            "dest_presente",
            fontName=FB,
            fontSize=10,
            textColor=AM,
            leading=14,
            spaceAfter=10,
        ),
        "asunto_label": S(
            "asunto_label", fontName=FB, fontSize=10, textColor=AM, leading=14
        ),
        "asunto_texto": S(
            "asunto_texto",
            fontName=FP,
            fontSize=10,
            textColor=AM,
            leading=14,
            spaceAfter=10,
        ),
        # Cuerpo y listas
        "body": S(
            "body",
            fontName=FP,
            fontSize=10,
            textColor=AM,
            leading=15,
            alignment=TA_JUSTIFY,
            spaceAfter=8,
        ),
        "body_bold": S(
            "body_bold",
            fontName=FB,
            fontSize=10,
            textColor=AM,
            leading=15,
            alignment=TA_JUSTIFY,
            spaceAfter=8,
        ),
        "lista": S(
            "lista",
            fontName=FP,
            fontSize=10,
            textColor=AM,
            leading=15,
            alignment=TA_JUSTIFY,
            leftIndent=18,
            spaceAfter=6,
        ),
        "lista1": S(
            "lista1",
            fontName=FP,
            fontSize=10,
            textColor=AM,
            leading=15,
            alignment=TA_JUSTIFY,
            leftIndent=33,
            spaceAfter=6,
        ),
        "lista2": S(
            "lista2",
            fontName=FP,
            fontSize=10,
            textColor=AM,
            leading=15,
            alignment=TA_JUSTIFY,
            leftIndent=50,
            spaceAfter=6,
        ),
        "lista3": S(
            "lista3",
            fontName=FP,
            fontSize=10,
            textColor=AM,
            leading=15,
            alignment=TA_JUSTIFY,
            leftIndent=65,
            spaceAfter=6,
        ),
        # Títulos de sección
        "titulo_anexo": S(
            "titulo_anexo",
            fontName=FB,
            fontSize=12,
            textColor=AO,
            alignment=TA_CENTER,
            spaceBefore=10,
            spaceAfter=4,
        ),
        "titulo_resultado": S(
            "titulo_resultado",
            fontName=FB,
            fontSize=11,
            textColor=AM,
            alignment=TA_CENTER,
            spaceAfter=8,
        ),
        "titulo_cuadro": S(
            "titulo_cuadro",
            fontName=FB,
            fontSize=9.5,
            textColor=AM,
            alignment=TA_CENTER,
            spaceAfter=4,
        ),
        # Listas numeradas / sub-listas
        "num_item": S(
            "num_item", fontName=FB, fontSize=10, textColor=AM, leading=14, spaceAfter=2
        ),
        "num_body": S(
            "num_body",
            fontName=FP,
            fontSize=10,
            textColor=AM,
            leading=14,
            alignment=TA_JUSTIFY,
            leftIndent=18,
            spaceAfter=6,
        ),
        "sublista": S(
            "sublista",
            fontName=FP,
            fontSize=10,
            textColor=AM,
            leading=14,
            alignment=TA_JUSTIFY,
            leftIndent=36,
            spaceAfter=5,
        ),
        "check": S(
            "check",
            fontName=FB,
            fontSize=10,
            textColor=AM,
            leading=14,
            leftIndent=18,
            spaceAfter=2,
        ),
        "check_body": S(
            "check_body",
            fontName=FP,
            fontSize=10,
            textColor=AM,
            leading=14,
            alignment=TA_JUSTIFY,
            leftIndent=36,
            spaceAfter=2,
        ),
        "check_detail": S(
            "check_detail",
            fontName=FP,
            fontSize=10,
            textColor=AM,
            leading=14,
            leftIndent=36,
            spaceAfter=6,
        ),
        # Celdas de tabla
        "tabla_header": S(
            "tabla_header",
            fontName=FB,
            fontSize=9,
            textColor=BLANCO,
            alignment=TA_CENTER,
            leading=12,
        ),
        "tabla_cell": S(
            "tabla_cell",
            fontName=FP,
            fontSize=9,
            textColor=AZUL_OSCURO,
            alignment=TA_CENTER,
            leading=12,
        ),
        "tabla_cell_left": S(
            "tabla_cell_left",
            fontName=FP,
            fontSize=9,
            textColor=AZUL_OSCURO,
            alignment=TA_LEFT,
            leading=12,
        ),
        "tabla_footer": S(
            "tabla_footer",
            fontName=FB,
            fontSize=9,
            textColor=AZUL_OSCURO,
            alignment=TA_CENTER,
            leading=12,
        ),
    }


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS DE TABLA
# ─────────────────────────────────────────────────────────────────────────────
def tabla_style_base(footer_row: int | None = None) -> TableStyle:
    """Estilo base para todas las tablas del documento."""
    last_data_row = -1 if footer_row is None else -2
    cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), AZUL_TABLA),
        ("TEXTCOLOR", (0, 0), (-1, 0), BLANCO),
        ("FONTNAME", (0, 0), (-1, 0), FONT_BOLD),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        (
            "ROWBACKGROUNDS",
            (0, 1),
            (-1, last_data_row),
            [colors.white, colors.HexColor("#EEF5FB")],
        ),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#AAAAAA")),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]
    if footer_row is not None:
        cmds += [
            (
                "BACKGROUND",
                (0, footer_row),
                (-1, footer_row),
                colors.HexColor("#D9E8F5"),
            ),
            ("FONTNAME", (0, footer_row), (-1, footer_row), FONT_BOLD),
            ("FONTSIZE", (0, footer_row), (-1, footer_row), 9),
        ]
    return TableStyle(cmds)


def _tabla_asunto(S: dict) -> Table:
    """Tabla de dos columnas para la línea 'Asunto : ...'"""
    data = [
        [
            Paragraph("<b>Asunto</b>", S["asunto_label"]),
            Paragraph(": Simulacion de convalidación", S["asunto_texto"]),
        ]
    ]
    t = Table(data, colWidths=[3.0 * cm, CONTENT_W - 3.0 * cm])
    t.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return t


# ─────────────────────────────────────────────────────────────────────────────
# ENCABEZADO / PIE DE PÁGINA
# ─────────────────────────────────────────────────────────────────────────────
def _draw_header_footer(
    canv, doc, facultad: str, carrera: str, logo_path: str = ""
) -> None:
    canv.saveState()
    header_y = PAGE_H - MARGIN_T + 0.3 * cm

    # Texto izquierdo
    canv.setFont(FONT_BOLD, 9)
    canv.setFillColor(AZUL_OSCURO)
    canv.drawString(MARGIN_L, header_y, facultad)
    canv.setFont(FONT_PRINCIPAL, 8)
    canv.drawString(MARGIN_L, header_y - 11, carrera)

    # Logo o texto "UAI"
    if logo_path and os.path.exists(logo_path):
        lw, lh = 2.2 * cm, 1.1 * cm
        canv.drawImage(
            logo_path,
            PAGE_W - MARGIN_R - lw,
            header_y - lh + 4,
            width=lw,
            height=lh,
            preserveAspectRatio=True,
            mask="auto",
        )
    else:
        canv.setFont(FONT_BOLD, 16)
        canv.setFillColor(AZUL_OSCURO)
        canv.drawRightString(PAGE_W - MARGIN_R, header_y - 2, "UAI")

    # Línea separadora
    canv.setStrokeColor(colors.HexColor("#CCCCCC"))
    canv.setLineWidth(0.5)
    canv.line(MARGIN_L, header_y - 16, PAGE_W - MARGIN_R, header_y - 16)

    # Pie de página (número de página; la portada es página 0)
    canv.setFont(FONT_PRINCIPAL, 9)
    canv.setFillColor(AZUL_OSCURO)
    canv.drawCentredString(PAGE_W / 2, MARGIN_B - 0.5 * cm, str(doc.page - 1))

    canv.restoreState()


# ─────────────────────────────────────────────────────────────────────────────
# CONSTRUCCIÓN DEL STORY
# ─────────────────────────────────────────────────────────────────────────────
def _build_story(s: dict, S: dict) -> list:
    """Construye la lista de Flowables que conforman el documento."""
    story = []

    # Datos pre-calculados
    total_conv = sum(c["creditos"] for c in s["convalidados"])
    total_exam = sum(c["creditos"] for c in s["examenes"])

    subtotal_conv = total_conv * float(s.get("costo_credito") or 0)
    subtotal_exam = len(s["examenes"]) * float(s.get("costo_examen") or 0)
    total_costo = subtotal_conv + subtotal_exam

    facultad = s.get("facultad_nombre", "FACULTAD")
    ies_origen = s.get("ies_origen", "")
    programa = s.get("programa", "")
    tratamiento = "la interesada" if s["genero"] == "F" else "el interesado"

    fecha_actual = now_pe()
    fecha_str = f"Chincha Alta, {fecha_actual.day} de {MESES[fecha_actual.month]} del {fecha_actual.year}"

    # ── Salto de página (la portada ocupa la página 1 en el callback) ──────
    story.append(PageBreak())

    # Pagina 02
    # ── Decreto anual ────────────────────────────────────────────────────────
    story.append(
        Paragraph(
            f'"{get_anio_texto()}"',
            S["decreto"],
        )
    )
    story.append(Spacer(1, 1 * cm))

    # ── Fecha y destinatario ─────────────────────────────────────────────────
    story.append(Paragraph(fecha_str, S["fecha"]))
    story.append(
        Paragraph(
            f"<b><u>{s['codigo']}</u></b>",
            S["dest_codigo"],
        )
    )
    story.append(Spacer(1, 0.2 * cm))
    story.append(Paragraph(s["nombre"], S["dest_nombre"]))
    story.append(Spacer(1, 0.8 * cm))
    story.append(Paragraph("<b><u>Presente. –</u></b>", S["dest_presente"]))
    story.append(Spacer(1, 0.2 * cm))

    # ── Asunto ───────────────────────────────────────────────────────────────
    story.append(_tabla_asunto(S))
    story.append(Spacer(1, 0.5 * cm))

    # ── Párrafos de la carta ─────────────────────────────────────────────────
    story.append(
        Paragraph(
            f"Reciba usted un cordial saludo a nombre de la {facultad} de la Universidad Autónoma de Ica.",
            S["body"],
        )
    )
    story.append(
        Paragraph(
            f"De acuerdo con la solicitud de evaluación por convalidación solicitada a la instancia académica de la {facultad}, "
            f"se ha procedido a analizar los documentos presentados en mérito a criterios establecidos en nuestro Reglamento de Estudios vigente con el "
            f"cual se propone y cumple con emitir respuesta a su pedido específico, del cual se desprende el <b>Anexo 01</b> del presente documento.",
            S["body"],
        )
    )
    story.append(
        Paragraph(
            "La Universidad establece dos formas de convalidar una asignatura:",
            S["body"],
        )
    )

    # LISTAS
    story.append(
        Paragraph(
            "1.&nbsp;&nbsp;Mediante convalidación directa – Similitud de asignaturas y "
            "contenidos del sílabo según reglamento de estudios.",
            S["lista"],
        )
    )

    story.append(
        Paragraph(
            "2.&nbsp;&nbsp;Mediante convalidación por examen de suficiencia – Mecanismo que "
            "evalúa las competencias que acredite por el avance y asignaturas "
            "aprobadas en el plan de estudios de la institución de origen y que no "
            "cumplan con el punto 1, mediante un examen de conocimientos. Para "
            "aprobar se exige una nota mínima de 13. El número de asignaturas que se "
            "pueden rendir lo define la universidad. Esta propuesta es determinada "
            "por la universidad y no es solicitada por la persona interesada en ningún caso ",
            S["lista"],
        )
    )
    story.append(
        Paragraph(
            "Dicha propuesta está sujeta a términos y condiciones académicas y "
            "administrativas contenidas en el <b>Anexo 02</b>, que están asociadas a nuestro "
            "servicio educativo, por lo que adjuntamos la información detalladamente "
            "para que usted como persona interesada pueda revisarla. ",
            S["body"],
        )
    )

    story.append(
        Paragraph(
            "Asimismo, en la simulación se podrá verificar las asignaturas por "
            "convalidación directa y la cantidad de exámenes propuestos, mismos que "
            "deberán ser aplicados y aprobados para que se pueda dar por convalidado. ",
            S["body"],
        )
    )
    story.append(PageBreak())  # SALTO A NUEVA PAGINA
    
    # Pagina 03

    story.append(Paragraph("ANEXO 01", S["titulo_anexo"]))
    story.append(Spacer(1, 0.5 * cm))

    story.append(Paragraph("Resultado de convalidación", S["titulo_anexo"]))
    story.append(Spacer(1, 0.5 * cm))

    story.append(
        Paragraph(
            f"En la simulación se podrá verificar las asignaturas por convalidación "
            f"directa al programa de estudios de <b>{programa}</b>, para {tratamiento} "
            f"proveniente del <b>“{ies_origen}”</b>, así como el número de asignaturas no "
            f"convalidadas y exámenes de suficiencia propuestos por la Facultad.",
            S["body"],
        )
    )
    story.append(Spacer(1, 0.8 * cm))

    # ════════ CUADRO N°01: Asignaturas y créditos convalidados ════════
    story.append(
        Paragraph("Cuadro N°01. Asignaturas y créditos convalidados", S["titulo_anexo"])
    )
    story.append(Spacer(1, 0.2 * cm))
    if s["convalidados"]:
        filas = [
            [
                Paragraph("CICLO", S["tabla_header"]),
                Paragraph("NOMBRE DEL CURSO", S["tabla_header"]),
                Paragraph("CRÉDITOS", S["tabla_header"]),
            ],
        ]
        for c in s["convalidados"]:
            filas.append(
                [
                    Paragraph(str(c["ciclo"]), S["tabla_cell"]),
                    Paragraph(c["nombre_curso"][:50], S["tabla_cell_left"]),
                    Paragraph(str(c["creditos"]), S["tabla_cell"]),
                ]
            )
        filas.append(
            [
                Paragraph("", S["tabla_footer"]),
                Paragraph("TOTAL CRÉDITOS CONVALIDADOS", S["tabla_footer"]),
                Paragraph(str(total_conv), S["tabla_footer"]),
            ]
        )
        t = Table(
            filas, colWidths=[2.0 * cm, CONTENT_W - 5.0 * cm, 3.0 * cm], repeatRows=1
        )
        t.setStyle(tabla_style_base(footer_row=len(filas) - 1))
        story.append(t)
    else:
        story.append(Paragraph("No se registraron cursos convalidados.", S["body"]))
    story.append(Spacer(1, 0.5 * cm))

    # ════════ CUADRO N°02: Costo de créditos convalidados ════════
    costo_cred = float(s["costo_credito"])
    story.append(
        Paragraph("Cuadro N°02. Costo de créditos convalidados", S["titulo_anexo"])
    )
    story.append(Spacer(1, 0.2 * cm))
    filas = [
        [
            Paragraph("N° CRÉDITOS CONVALIDADOS", S["tabla_header"]),
            Paragraph("COSTO POR CRÉDITO", S["tabla_header"]),
            Paragraph("IMPORTE SUBTOTAL", S["tabla_header"]),
        ],
        [
            Paragraph(str(total_conv), S["tabla_cell"]),
            Paragraph(f"S/ {costo_cred:.2f}", S["tabla_cell"]),
            Paragraph(f"S/ {subtotal_conv:.2f}", S["tabla_cell"]),
        ],
    ]
    t = Table(filas, colWidths=[CONTENT_W / 3] * 3)
    t.setStyle(tabla_style_base())
    story.append(t)
    story.append(Spacer(1, 0.5 * cm))

    # ════════ CUADRO N°03: Asignaturas por examen de suficiencia ════════
    if s["examenes"]:
        story.append(
            Paragraph(
                "Cuadro N°03. Asignaturas y créditos por examen de suficiencia",
                S["titulo_anexo"],
            )
        )
        story.append(Spacer(1, 0.2 * cm))
        cw = [1.8 * cm, CONTENT_W - 8.0 * cm, 2.2 * cm, 3.8 * cm]
        filas = [
            [
                Paragraph("CICLO", S["tabla_header"]),
                Paragraph("NOMBRE DEL CURSO", S["tabla_header"]),
                Paragraph("CRÉDITOS", S["tabla_header"]),
                Paragraph("DENOMINACIÓN", S["tabla_header"]),
            ],
        ]
        for c in s["examenes"]:
            filas.append(
                [
                    Paragraph(str(c["ciclo"]), S["tabla_cell"]),
                    Paragraph(c["nombre_curso"][:40], S["tabla_cell_left"]),
                    Paragraph(str(c["creditos"]), S["tabla_cell"]),
                    Paragraph("EXAMEN DE SUFICIENCIA", S["tabla_cell"]),
                ]
            )
        filas.append(
            [
                Paragraph("", S["tabla_footer"]),
                Paragraph("TOTAL CRÉDITOS", S["tabla_footer"]),
                Paragraph(str(total_exam), S["tabla_footer"]),
                Paragraph("", S["tabla_footer"]),
            ]
        )
        t = Table(filas, colWidths=cw, repeatRows=1)
        t.setStyle(tabla_style_base(footer_row=len(filas) - 1))
        story.append(t)
        story.append(Spacer(1, 0.5 * cm))

    # ════════ CUADRO N°04: Costo del examen de suficiencia ════════
    costo_exam = float(s["costo_examen"])
    num_examenes = len(s["examenes"]) if s["examenes"] else 0
    story.append(
        Paragraph("Cuadro N°04. Costo del examen de suficiencia", S["titulo_anexo"])
    )
    story.append(Spacer(1, 0.2 * cm))
    filas = [
        [
            Paragraph("N° EXÁMENES DE SUFICIENCIA", S["tabla_header"]),
            Paragraph("COSTO POR EXAMEN", S["tabla_header"]),
            Paragraph("IMPORTE SUBTOTAL", S["tabla_header"]),
        ],
        [
            Paragraph(str(num_examenes), S["tabla_cell"]),
            Paragraph(f"S/ {costo_exam:.2f}", S["tabla_cell"]),
            Paragraph(f"S/ {subtotal_exam:.2f}", S["tabla_cell"]),
        ],
    ]
    t = Table(filas, colWidths=[CONTENT_W / 3] * 3)
    t.setStyle(tabla_style_base())
    story.append(t)
    story.append(Spacer(1, 0.5 * cm))

    # ════════ CUADRO N°05: Costo de convalidación total ════════
    story.append(
        Paragraph("Cuadro N°05. Costo de convalidación total", S["titulo_anexo"])
    )
    story.append(Spacer(1, 0.2 * cm))
    filas = [
        [
            Paragraph("CONVALIDACIÓN", S["tabla_header"]),
            Paragraph("IMPORTE TOTAL", S["tabla_header"]),
        ],
        [
            Paragraph("DIRECTA", S["tabla_cell"]),
            Paragraph(f"S/ {subtotal_conv:.2f}", S["tabla_cell"]),
        ],
    ]
    if s["examenes"]:
        filas.append(
            [
                Paragraph("POR E. S.", S["tabla_cell"]),
                Paragraph(f"S/ {subtotal_exam:.2f}", S["tabla_cell"]),
            ]
        )
    filas.append(
        [
            Paragraph("TOTAL", S["tabla_footer"]),
            Paragraph(f"S/ {total_costo:.2f}", S["tabla_footer"]),
        ]
    )
    cw = CONTENT_W / 2
    t = Table(filas, colWidths=[cw, cw])
    t.setStyle(tabla_style_base(footer_row=len(filas) - 1))
    story.append(t)
    story.append(Spacer(1, 0.5 * cm))

    # ════════ CUADRO N°06: Asignaturas no convalidadas ════════
    total_no = sum(c["creditos"] for c in s["no_convalidados"])
    story.append(
        Paragraph("Cuadro N°06. Asignaturas no convalidadas", S["titulo_anexo"])
    )
    story.append(Spacer(1, 0.2 * cm))
    if s["no_convalidados"]:
        cw = [1.8 * cm, CONTENT_W - 8.0 * cm, 2.2 * cm, 3.8 * cm]
        filas = [
            [
                Paragraph("CICLO", S["tabla_header"]),
                Paragraph("NOMBRE DEL CURSO", S["tabla_header"]),
                Paragraph("CRÉDITOS", S["tabla_header"]),
                Paragraph("PERIODO LECTIVO", S["tabla_header"]),
            ],
        ]
        for c in s["no_convalidados"]:
            filas.append(
                [
                    Paragraph(str(c["ciclo"]), S["tabla_cell"]),
                    Paragraph(c["nombre_curso"][:40], S["tabla_cell_left"]),
                    Paragraph(str(c["creditos"]), S["tabla_cell"]),
                    Paragraph(c.get("periodo_lectivo") or "", S["tabla_cell"]),
                ]
            )
        filas.append(
            [
                Paragraph("", S["tabla_footer"]),
                Paragraph("TOTAL CRÉDITOS", S["tabla_footer"]),
                Paragraph(str(total_no), S["tabla_footer"]),
                Paragraph("", S["tabla_footer"]),
            ]
        )
        t = Table(filas, colWidths=cw, repeatRows=1)
        t.setStyle(tabla_style_base(footer_row=len(filas) - 1))
        story.append(t)
    else:
        story.append(Paragraph("No hay asignaturas no convalidadas.", S["body"]))
    story.append(Spacer(1, 0.5 * cm))
    story.append(PageBreak())  # SALTO A NUEVA PAGINA

    
    return story


# ─────────────────────────────────────────────────────────────────────────────
# GENERACIÓN DEL PDF
# ─────────────────────────────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────────────
# GENERACIÓN DEL PDF
# ─────────────────────────────────────────────────────────────────────────────
def generar_pdf(solicitud_id: int) -> tuple[io.BytesIO, str]:
    """Genera el PDF de la solicitud. Retorna (BytesIO, nombre_archivo)."""
    cached = pdf_cache.get(solicitud_id)
    if cached is not None:
        buf, name = cached
        buf.seek(0)
        return buf, name

    s = obtener_datos(solicitud_id)
    if s is None:
        raise ValueError(f"Solicitud {solicitud_id} no encontrada")

    S = build_styles()
    story = _build_story(s, S)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=MARGIN_L,
        rightMargin=MARGIN_R,
        topMargin=MARGIN_T + 1.2 * cm,
        bottomMargin=MARGIN_B,
        title="Resolución de Convalidación",
        author="Universidad Autónoma de Ica",
    )

    def on_page(canv, doc):
        pn = canv.getPageNumber()
        if pn == 1:
            if os.path.exists(PORTADA_IMG):
                canv.drawImage(
                    PORTADA_IMG,
                    0,
                    0,
                    width=PAGE_W,
                    height=PAGE_H,
                    preserveAspectRatio=False,
                )
            return
        _draw_header_footer(
            canv,
            doc,
            s.get("facultad_nombre", "FACULTAD"),
            s.get("carrera_nombre", "Carrera"),
        )

    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    buffer.seek(0)

    data = buffer.read()
    buffer_final = io.BytesIO(data)
    buffer_final.seek(0)

    nombre = f"CONVALIDACION_{s['codigo']}.pdf"

    pdf_cache.set(solicitud_id, (buffer_final, nombre), ttl=600)
    buffer_final.seek(0)
    return buffer_final, nombre


def generar_preview_images(solicitud_id: int) -> list[bytes]:
    """Genera imágenes PNG de cada página del PDF (con caché)."""
    cached = preview_cache.get(solicitud_id)
    if cached is not None:
        return cached

    try:
        pdf_buffer, _ = generar_pdf(solicitud_id)
        pdf_bytes = pdf_buffer.read()
    except Exception as e:
        raise RuntimeError(f"Error generando PDF: {e}")

    try:
        pdf = fitz.open(stream=pdf_bytes, filetype="pdf")
        matrix = fitz.Matrix(1.5, 1.5)
        paginas = [
            pdf[i].get_pixmap(matrix=matrix).tobytes("png") for i in range(len(pdf))
        ]
        pdf.close()
    except Exception as e:
        raise RuntimeError(f"Error generando previews: {e}")

    preview_cache.set(solicitud_id, paginas, ttl=600)
    return paginas


# ─────────────────────────────────────────────────────────────────────────────
# CACHÉ
# ─────────────────────────────────────────────────────────────────────────────
def invalidar_cache(solicitud_id: int) -> None:
    pdf_cache.delete(solicitud_id)
    preview_cache.delete(solicitud_id)


# ─────────────────────────────────────────────────────────────────────────────
# RUTAS FLASK
# ─────────────────────────────────────────────────────────────────────────────
@bp_word.route("/solicitudes/descargar-pdf/<int:id>")
def descargar_pdf(id: int):
    try:
        buffer_pdf, nombre_pdf = generar_pdf(id)
        return send_file(
            buffer_pdf,
            as_attachment=True,
            download_name=nombre_pdf,
            mimetype="application/pdf",
        )
    except Exception as e:
        flash(f"Error al generar PDF: {e}", "danger")
        return redirect(url_for("solicitudes.ver", id=id))


@bp_word.route("/solicitudes/descargar-word/<int:id>")
def descargar_word(id: int):
    flash("Descarga de Word no disponible. Solo se genera PDF.", "info")
    return redirect(url_for("solicitudes.ver", id=id))


@bp_word.route("/solicitudes/preview-generar/<int:id>")
def preview_generar(id: int):
    def _stream():
        try:
            cached = preview_cache.get(id)
            if cached is not None:
                yield f"data: {json.dumps({'pct': 100, 'msg': 'Cargando desde caché', 'cached': True, 'paginas': len(cached)})}\n\n"
                return

            yield f"data: {json.dumps({'pct': 30, 'msg': 'Generando PDF…'})}\n\n"
            paginas = generar_preview_images(id)
            yield f"data: {json.dumps({'pct': 100, 'msg': 'Listo', 'paginas': len(paginas)})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return Response(
        stream_with_context(_stream()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@bp_word.route("/solicitudes/preview-pagina/<int:id>/<int:pagina>")
def preview_pagina(id: int, pagina: int):
    paginas = preview_cache.get(id)
    if paginas is None:
        paginas = generar_preview_images(id)
    if not paginas or pagina < 0 or pagina >= len(paginas):
        return Response("Página no encontrada", status=404)
    return Response(paginas[pagina], mimetype="image/png")


@bp_word.route("/solicitudes/preview-word/<int:id>")
def preview_word(id: int):
    flash(
        "Vista previa de Word no disponible. Use la previsualización del PDF.", "info"
    )
    return redirect(url_for("solicitudes.ver", id=id))


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS PÚBLICOS (usados desde otros módulos)
# ─────────────────────────────────────────────────────────────────────────────
def generar_pdf_bytes(solicitud_id: int) -> bytes:
    buffer, _ = generar_pdf(solicitud_id)
    buffer.seek(0)
    return buffer.read()


# Aliases de compatibilidad hacia atrás
generar_documento_en_memoria = generar_pdf_bytes
generar_documento_word_bytes = generar_pdf_bytes
