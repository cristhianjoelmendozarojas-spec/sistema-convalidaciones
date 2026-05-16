# ─────────────────────────────────────────────────────────────────────────────
# IMPORTS
# ─────────────────────────────────────────────────────────────────────────────
import io
import json
import os

import fitz
from flask import Blueprint, Response, flash, redirect, send_file, stream_with_context, url_for


from db.cache import pdf_cache, preview_cache
from db.conexion import get_connection

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTES Y CONFIGURACIÓN
# ─────────────────────────────────────────────────────────────────────────────
_BASE_DIR   = os.path.dirname(os.path.dirname(__file__))
FONTS_DIR   = os.path.join(_BASE_DIR, "static", "fonts")
IMAGES_DIR  = os.path.join(_BASE_DIR, "plantillas_word", "Images")
PORTADA_IMG = os.path.join(IMAGES_DIR, "PORTADA.png")
CONTRAPORTADA_IMG = os.path.join(IMAGES_DIR, "CONTRAPORTADA.png")

MESES = {
    1: "enero",   2: "febrero",  3: "marzo",    4: "abril",
    5: "mayo",    6: "junio",    7: "julio",     8: "agosto",
    9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre",
}

# Página A4
PAGE_W, PAGE_H = A4
MARGIN_L  = 2.5 * cm
MARGIN_R  = 2.0 * cm
MARGIN_T  = 2.0 * cm
MARGIN_B  = 2.0 * cm
CONTENT_W = PAGE_W - MARGIN_L - MARGIN_R

# Años decretados por el gobierno peruano
from config import ANIOS_DECRETADOS, now_pe
from db.conexion import fetch_one

def get_anio_texto() -> str:
    """Retorna el texto del año basándose en la fecha actual."""
    anio_actual = now_pe().year
    row = fetch_one("SELECT nombre FROM anios_decretados WHERE anio = %s AND estado = 'activo'", (anio_actual,))
    if row:
        return row['nombre']
    return ANIOS_DECRETADOS.get(anio_actual, f"Año {anio_actual}")

# Colores UAI
AZUL_OSCURO = colors.HexColor("#003B91")
AZUL_MEDIO  = colors.HexColor("#003B91")
AZUL_TABLA  = colors.HexColor("#003B91")
BLANCO      = colors.white

# ─────────────────────────────────────────────────────────────────────────────
# FUENTES
# ─────────────────────────────────────────────────────────────────────────────
def _registrar_fuentes():
    regular = os.path.join(FONTS_DIR, "Poppins-Regular.ttf")
    bold    = os.path.join(FONTS_DIR, "Poppins-Bold.ttf")
    if os.path.exists(regular) and os.path.exists(bold):
        pdfmetrics.registerFont(TTFont("Poppins",      regular))
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

def _query_cursos(solicitud_id, estado):
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute(f"""
        SELECT cp.ciclo, cp.nombre_curso, cp.creditos, sc.nota
        FROM solicitud_cursos sc
        JOIN cursos_plan cp ON sc.curso_local_id = cp.id
        WHERE sc.solicitud_id = %s AND sc.estado = %s
        ORDER BY {_ORDEN_CICLO}
    """, (solicitud_id, estado))
    result = cur.fetchall()
    cur.close()
    conn.close()
    return result


def obtener_datos(solicitud_id: int) -> dict:
    conn = get_connection()
    cur  = conn.cursor(dictionary=True)

    cur.execute(f"""
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
    """, (solicitud_id,))
    solicitud = cur.fetchone()

    solicitud["convalidados"]   = _query_cursos(solicitud_id, "convalidado")
    solicitud["examenes"]       = _query_cursos(solicitud_id, "examen_suficiencia")

    cur.execute(f"""
        SELECT cp.ciclo, cp.nombre_curso, cp.creditos, sc.periodo_lectivo
        FROM solicitud_cursos sc
        JOIN cursos_plan cp ON sc.curso_local_id = cp.id
        WHERE sc.solicitud_id = %s AND sc.estado = 'pendiente'
        ORDER BY {_ORDEN_CICLO}
    """, (solicitud_id,))
    solicitud["no_convalidados"] = cur.fetchall()

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
        "header_facultad": S("header_facultad", fontName=FB, fontSize=9,  textColor=AO, leading=11),
        "header_carrera":  S("header_carrera",  fontName=FP, fontSize=8,  textColor=AO, leading=11),

        # Bloque de identificación
        "decreto":       S("decreto",      fontName=FB, fontSize=9,  textColor=AM, alignment=TA_CENTER, leading=12, spaceAfter=4),
        "fecha":         S("fecha",        fontName=FP, fontSize=10, textColor=AM, alignment=TA_RIGHT,  leading=13, spaceAfter=12),
        "dest_codigo":   S("dest_codigo",  fontName=FB, fontSize=10, textColor=AM, leading=14),
        "dest_nombre":   S("dest_nombre",  fontName=FP, fontSize=10, textColor=AM, leading=14),
        "dest_presente": S("dest_presente",fontName=FB, fontSize=10, textColor=AM, leading=14, spaceAfter=10),
        "asunto_label":  S("asunto_label", fontName=FB, fontSize=10, textColor=AM, leading=14),
        "asunto_texto":  S("asunto_texto", fontName=FP, fontSize=10, textColor=AM, leading=14, spaceAfter=10),

        # Cuerpo y listas
        "body":          S("body",         fontName=FP, fontSize=10, textColor=AM, leading=15, alignment=TA_JUSTIFY, spaceAfter=8),
        "body_bold":     S("body_bold",    fontName=FB, fontSize=10, textColor=AM, leading=15, alignment=TA_JUSTIFY, spaceAfter=8),
        "lista":         S("lista",        fontName=FP, fontSize=10, textColor=AM, leading=15, alignment=TA_JUSTIFY, leftIndent=18, spaceAfter=6),
        "lista1":         S("lista1",        fontName=FP, fontSize=10, textColor=AM, leading=15, alignment=TA_JUSTIFY, leftIndent=33, spaceAfter=6),
        "lista2":         S("lista2",        fontName=FP, fontSize=10, textColor=AM, leading=15, alignment=TA_JUSTIFY, leftIndent=50, spaceAfter=6),
        "lista3":         S("lista3",        fontName=FP, fontSize=10, textColor=AM, leading=15, alignment=TA_JUSTIFY, leftIndent=65, spaceAfter=6),
        
        # Títulos de sección
        "titulo_anexo":    S("titulo_anexo",    fontName=FB, fontSize=12,  textColor=AO, alignment=TA_CENTER, spaceBefore=10, spaceAfter=4),
        "titulo_resultado":S("titulo_resultado", fontName=FB, fontSize=11,  textColor=AM, alignment=TA_CENTER, spaceAfter=8),
        "titulo_cuadro":   S("titulo_cuadro",   fontName=FB, fontSize=9.5, textColor=AM, alignment=TA_CENTER, spaceAfter=4),

        # Listas numeradas / sub-listas
        "num_item":    S("num_item",    fontName=FB, fontSize=10, textColor=AM, leading=14, spaceAfter=2),
        "num_body":    S("num_body",    fontName=FP, fontSize=10, textColor=AM, leading=14, alignment=TA_JUSTIFY, leftIndent=18, spaceAfter=6),
        "sublista":    S("sublista",    fontName=FP, fontSize=10, textColor=AM, leading=14, alignment=TA_JUSTIFY, leftIndent=36, spaceAfter=5),
        "check":       S("check",       fontName=FB, fontSize=10, textColor=AM, leading=14, leftIndent=18, spaceAfter=2),
        "check_body":  S("check_body",  fontName=FP, fontSize=10, textColor=AM, leading=14, alignment=TA_JUSTIFY, leftIndent=36, spaceAfter=2),
        "check_detail":S("check_detail",fontName=FP, fontSize=10, textColor=AM, leading=14, leftIndent=36, spaceAfter=6),

        # Celdas de tabla
        "tabla_header":    S("tabla_header",    fontName=FB, fontSize=9, textColor=BLANCO,    alignment=TA_CENTER, leading=12),
        "tabla_cell":      S("tabla_cell",      fontName=FP, fontSize=9, textColor=AZUL_OSCURO, alignment=TA_CENTER, leading=12),
        "tabla_cell_left": S("tabla_cell_left", fontName=FP, fontSize=9, textColor=AZUL_OSCURO, alignment=TA_LEFT,   leading=12),
        "tabla_footer":    S("tabla_footer",    fontName=FB, fontSize=9, textColor=AZUL_OSCURO, alignment=TA_CENTER, leading=12),
    }


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS DE TABLA
# ─────────────────────────────────────────────────────────────────────────────
def tabla_style_base(footer_row: int | None = None) -> TableStyle:
    """Estilo base para todas las tablas del documento."""
    last_data_row = -1 if footer_row is None else -2
    cmds = [
        ("BACKGROUND",    (0, 0), (-1, 0),             AZUL_TABLA),
        ("TEXTCOLOR",     (0, 0), (-1, 0),             BLANCO),
        ("FONTNAME",      (0, 0), (-1, 0),             FONT_BOLD),
        ("FONTSIZE",      (0, 0), (-1, 0),             9),
        ("ALIGN",         (0, 0), (-1, -1),            "CENTER"),
        ("VALIGN",        (0, 0), (-1, -1),            "MIDDLE"),
        ("ROWBACKGROUNDS",(0, 1), (-1, last_data_row), [colors.white, colors.HexColor("#EEF5FB")]),
        ("GRID",          (0, 0), (-1, -1),            0.5, colors.HexColor("#AAAAAA")),
        ("TOPPADDING",    (0, 0), (-1, -1),            5),
        ("BOTTOMPADDING", (0, 0), (-1, -1),            5),
        ("LEFTPADDING",   (0, 0), (-1, -1),            6),
        ("RIGHTPADDING",  (0, 0), (-1, -1),            6),
    ]
    if footer_row is not None:
        cmds += [
            ("BACKGROUND", (0, footer_row), (-1, footer_row), colors.HexColor("#D9E8F5")),
            ("FONTNAME",   (0, footer_row), (-1, footer_row), FONT_BOLD),
            ("FONTSIZE",   (0, footer_row), (-1, footer_row), 9),
        ]
    return TableStyle(cmds)


def _tabla_asunto(S: dict) -> Table:
    """Tabla de dos columnas para la línea 'Asunto : ...'"""
    data = [[
        Paragraph("<b>Asunto</b>", S["asunto_label"]),
        Paragraph(": Simulacion de convalidación", S["asunto_texto"]),
    ]]
    t = Table(data, colWidths=[3.0 * cm, CONTENT_W - 3.0 * cm])
    t.setStyle(TableStyle([
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
        ("TOPPADDING",    (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return t


# ─────────────────────────────────────────────────────────────────────────────
# ENCABEZADO / PIE DE PÁGINA
# ─────────────────────────────────────────────────────────────────────────────
def _draw_header_footer(canv, doc, facultad: str, carrera: str, logo_path: str = "") -> None:
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
            PAGE_W - MARGIN_R - lw, header_y - lh + 4,
            width=lw, height=lh,
            preserveAspectRatio=True, mask="auto",
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
    total_costo   = subtotal_conv + subtotal_exam

    facultad    = s.get("facultad_nombre", "FACULTAD")
    ies_origen  = s.get("ies_origen", "")
    programa    = s.get("programa", "")
    tratamiento = "la interesada" if s["genero"] == "F" else "el interesado"

    fecha_actual = now_pe()
    fecha_str = f"Chincha Alta, {fecha_actual.day} de {MESES[fecha_actual.month]} del {fecha_actual.year}"

    # ── Salto de página (la portada ocupa la página 1 en el callback) ──────
    story.append(PageBreak())

    #Pagina 02
    # ── Decreto anual ────────────────────────────────────────────────────────
    story.append(Paragraph(
        f'"{get_anio_texto()}"',
        S["decreto"],
    ))
    story.append(Spacer(1, 1 * cm))

    # ── Fecha y destinatario ─────────────────────────────────────────────────
    story.append(Paragraph(fecha_str, S["fecha"]))
    story.append(Paragraph(f'<b><u>{s["codigo"]}</u></b>', S["dest_codigo"],))
    story.append(Spacer(1, 0.2 * cm))
    story.append(Paragraph(s["nombre"], S["dest_nombre"]))
    story.append(Spacer(1, 0.8 * cm))
    story.append(Paragraph("<b><u>Presente. –</u></b>", S["dest_presente"]))
    story.append(Spacer(1, 0.2 * cm))

    # ── Asunto ───────────────────────────────────────────────────────────────
    story.append(_tabla_asunto(S))
    story.append(Spacer(1, 0.5 * cm))

    # ── Párrafos de la carta ─────────────────────────────────────────────────
    story.append(Paragraph(
        f"Reciba usted un cordial saludo a nombre de la {facultad} de la Universidad Autónoma de Ica.",
        S["body"],
    ))
    story.append(Paragraph(
        f"De acuerdo con la solicitud de evaluación por convalidación solicitada a la instancia académica de la {facultad}, "
        f"se ha procedido a analizar los documentos presentados en mérito a criterios establecidos en nuestro Reglamento de Estudios vigente con el "
        f"cual se propone y cumple con emitir respuesta a su pedido específico, del cual se desprende el <b>Anexo 01</b> del presente documento.",          
        S["body"],
    ))
    story.append(Paragraph(            
        f"La Universidad establece dos formas de convalidar una asignatura:",
             
        S["body"],
    ))
    
    #LISTAS
    story.append(Paragraph(            
        f"1.&nbsp;&nbsp;Mediante convalidación directa – Similitud de asignaturas y "
        f"contenidos del sílabo según reglamento de estudios.",
        S["lista"],
      ))    
    
    story.append(Paragraph(            
        f"2.&nbsp;&nbsp;Mediante convalidación por examen de suficiencia – Mecanismo que "
        f"evalúa las competencias que acredite por el avance y asignaturas "
        f"aprobadas en el plan de estudios de la institución de origen y que no "
        f"cumplan con el punto 1, mediante un examen de conocimientos. Para "
        f"aprobar se exige una nota mínima de 13. El número de asignaturas que se "
        f"pueden rendir lo define la universidad. Esta propuesta es determinada "
        f"por la universidad y no es solicitada por la persona interesada en ningún caso ",
        S["lista"],
    ))
    story.append(Paragraph(
        f"Dicha propuesta está sujeta a términos y condiciones académicas y "
        f"administrativas contenidas en el <b>Anexo 02</b>, que están asociadas a nuestro "
        f"servicio educativo, por lo que adjuntamos la información detalladamente "
        f"para que usted como persona interesada pueda revisarla. ",          
        S["body"],
    ))
    
    story.append(Paragraph(
        f"Asimismo, en la simulación se podrá verificar las asignaturas por "
        f"convalidación directa y la cantidad de exámenes propuestos, mismos que "
        f"deberán ser aplicados y aprobados para que se pueda dar por convalidado. ",              
        S["body"],        
    ))

    story.append(Paragraph(
        f"Es importante mencionar que para seguir con el procedimiento de "
        f"convalidación la persona interesada debe confirmar la aceptación del "
        f"presente documento a través del correo de "
        f"<b><u>admision.extraordinaria@autonomadeica.edu.pe</u></b> para lo cual tiene un "
        f"plazo de 48 horas después de notificada dicha respuesta. ",              
        S["body"],        
    ))

    

    story.append(PageBreak()) #SALTO A NUEVA PAGINA

    #Pagina 03

    story.append(Paragraph("ANEXO 01", S["titulo_anexo"]))
    story.append(Spacer(1, 0.5 * cm))

    story.append(Paragraph("Resultado de convalidación", S["titulo_anexo"]))
    story.append(Spacer(1, 0.5 * cm))

    story.append(Paragraph(
        f"En la simulación se podrá verificar las asignaturas por convalidación "
        f"directa al programa de estudios de <b>{programa}</b>, para {tratamiento} "
        f"proveniente del <b>“{ies_origen}”</b>, así como el número de asignaturas no "
        f"convalidadas y exámenes de suficiencia propuestos por la Facultad.",             
        S["body"],        
))
    story.append(Spacer(1, 0.8 * cm))

    # ════════ CUADRO N°01: Asignaturas y créditos convalidados ════════
    story.append(Paragraph("Cuadro N°01. Asignaturas y créditos convalidados", S["titulo_anexo"]))
    story.append(Spacer(1, 0.2 * cm))
    if s["convalidados"]:
        filas = [
            [Paragraph("CICLO", S["tabla_header"]), Paragraph("NOMBRE DEL CURSO", S["tabla_header"]), Paragraph("CRÉDITOS", S["tabla_header"])],
        ]
        for c in s["convalidados"]:
            filas.append([Paragraph(str(c["ciclo"]), S["tabla_cell"]), Paragraph(c["nombre_curso"][:50], S["tabla_cell_left"]), Paragraph(str(c["creditos"]), S["tabla_cell"])])
        filas.append([Paragraph("", S["tabla_footer"]), Paragraph("TOTAL CRÉDITOS CONVALIDADOS", S["tabla_footer"]), Paragraph(str(total_conv), S["tabla_footer"])])
        t = Table(filas, colWidths=[2.0 * cm, CONTENT_W - 5.0 * cm, 3.0 * cm], repeatRows=1)
        t.setStyle(tabla_style_base(footer_row=len(filas) - 1))
        story.append(t)
    else:
        story.append(Paragraph("No se registraron cursos convalidados.", S["body"]))
    story.append(Spacer(1, 0.5 * cm))

    # ════════ CUADRO N°02: Costo de créditos convalidados ════════
    costo_cred = float(s["costo_credito"])
    story.append(Paragraph("Cuadro N°02. Costo de créditos convalidados", S["titulo_anexo"]))
    story.append(Spacer(1, 0.2 * cm))
    filas = [
        [Paragraph("N° CRÉDITOS CONVALIDADOS", S["tabla_header"]), Paragraph("COSTO POR CRÉDITO", S["tabla_header"]), Paragraph("IMPORTE SUBTOTAL", S["tabla_header"])],
        [Paragraph(str(total_conv), S["tabla_cell"]), Paragraph(f"S/ {costo_cred:.2f}", S["tabla_cell"]), Paragraph(f"S/ {subtotal_conv:.2f}", S["tabla_cell"])],
    ]
    t = Table(filas, colWidths=[CONTENT_W / 3] * 3)
    t.setStyle(tabla_style_base())
    story.append(t)
    story.append(Spacer(1, 0.5 * cm))

    # ════════ CUADRO N°03: Asignaturas por examen de suficiencia ════════
    if s["examenes"]:
        story.append(Paragraph("Cuadro N°03. Asignaturas y créditos por examen de suficiencia", S["titulo_anexo"]))
        story.append(Spacer(1, 0.2 * cm))
        cw = [1.8 * cm, CONTENT_W - 8.0 * cm, 2.2 * cm, 3.8 * cm]
        filas = [
            [Paragraph("CICLO", S["tabla_header"]), Paragraph("NOMBRE DEL CURSO", S["tabla_header"]), Paragraph("CRÉDITOS", S["tabla_header"]), Paragraph("DENOMINACIÓN", S["tabla_header"])],
        ]
        for c in s["examenes"]:
            filas.append([Paragraph(str(c["ciclo"]), S["tabla_cell"]), Paragraph(c["nombre_curso"][:40], S["tabla_cell_left"]), Paragraph(str(c["creditos"]), S["tabla_cell"]), Paragraph("EXAMEN DE SUFICIENCIA", S["tabla_cell"])])
        filas.append([Paragraph("", S["tabla_footer"]), Paragraph("TOTAL CRÉDITOS", S["tabla_footer"]), Paragraph(str(total_exam), S["tabla_footer"]), Paragraph("", S["tabla_footer"])])
        t = Table(filas, colWidths=cw, repeatRows=1)
        t.setStyle(tabla_style_base(footer_row=len(filas) - 1))
        story.append(t)
        story.append(Spacer(1, 0.5 * cm))

    # ════════ CUADRO N°04: Costo del examen de suficiencia ════════
    costo_exam = float(s["costo_examen"])
    num_examenes = len(s["examenes"]) if s["examenes"] else 0
    story.append(Paragraph("Cuadro N°04. Costo del examen de suficiencia", S["titulo_anexo"]))
    story.append(Spacer(1, 0.2 * cm))
    filas = [
        [Paragraph("N° EXÁMENES DE SUFICIENCIA", S["tabla_header"]), Paragraph("COSTO POR EXAMEN", S["tabla_header"]), Paragraph("IMPORTE SUBTOTAL", S["tabla_header"])],
        [Paragraph(str(num_examenes), S["tabla_cell"]), Paragraph(f"S/ {costo_exam:.2f}", S["tabla_cell"]), Paragraph(f"S/ {subtotal_exam:.2f}", S["tabla_cell"])],
    ]
    t = Table(filas, colWidths=[CONTENT_W / 3] * 3)
    t.setStyle(tabla_style_base())
    story.append(t)
    story.append(Spacer(1, 0.5 * cm))

    # ════════ CUADRO N°05: Costo de convalidación total ════════
    story.append(Paragraph("Cuadro N°05. Costo de convalidación total", S["titulo_anexo"]))
    story.append(Spacer(1, 0.2 * cm))
    filas = [
        [Paragraph("CONVALIDACIÓN", S["tabla_header"]), Paragraph("IMPORTE TOTAL", S["tabla_header"])],
        [Paragraph("DIRECTA", S["tabla_cell"]), Paragraph(f"S/ {subtotal_conv:.2f}", S["tabla_cell"])],
    ]
    if s["examenes"]:
        filas.append([Paragraph("POR E. S.", S["tabla_cell"]), Paragraph(f"S/ {subtotal_exam:.2f}", S["tabla_cell"])])
    filas.append([Paragraph("TOTAL", S["tabla_footer"]), Paragraph(f"S/ {total_costo:.2f}", S["tabla_footer"])])
    cw = CONTENT_W / 2
    t = Table(filas, colWidths=[cw, cw])
    t.setStyle(tabla_style_base(footer_row=len(filas) - 1))
    story.append(t)
    story.append(Spacer(1, 0.5 * cm))

    # ════════ CUADRO N°06: Asignaturas no convalidadas ════════
    total_no = sum(c["creditos"] for c in s["no_convalidados"])
    story.append(Paragraph("Cuadro N°06. Asignaturas no convalidadas", S["titulo_anexo"]))
    story.append(Spacer(1, 0.2 * cm))
    if s["no_convalidados"]:
        cw = [1.8 * cm, CONTENT_W - 8.0 * cm, 2.2 * cm, 3.8 * cm]
        filas = [
            [Paragraph("CICLO", S["tabla_header"]), Paragraph("NOMBRE DEL CURSO", S["tabla_header"]), Paragraph("CRÉDITOS", S["tabla_header"]), Paragraph("PERIODO LECTIVO", S["tabla_header"])],
        ]
        for c in s["no_convalidados"]:
            filas.append([Paragraph(str(c["ciclo"]), S["tabla_cell"]), Paragraph(c["nombre_curso"][:40], S["tabla_cell_left"]), Paragraph(str(c["creditos"]), S["tabla_cell"]), Paragraph(c.get("periodo_lectivo", ""), S["tabla_cell"])])
        filas.append([Paragraph("", S["tabla_footer"]), Paragraph("TOTAL CRÉDITOS", S["tabla_footer"]), Paragraph(str(total_no), S["tabla_footer"]), Paragraph("", S["tabla_footer"])])
        t = Table(filas, colWidths=cw, repeatRows=1)
        t.setStyle(tabla_style_base(footer_row=len(filas) - 1))
        story.append(t)
    else:
        story.append(Paragraph("No hay asignaturas no convalidadas.", S["body"]))
    story.append(Spacer(1, 0.5 * cm))
    story.append(PageBreak()) #SALTO A NUEVA PAGINA

    # ════════ Anexo 02 ════════
    story.append(Paragraph("ANEXO 02", S["titulo_anexo"]))
    story.append(Spacer(1, 0.5 * cm))

    story.append(Paragraph("Términos del servicio educativo para estudios de pregrado de la UAI",
                            S["titulo_anexo"]))
    story.append(Spacer(1, 0.5 * cm))

    #1.	Definición de usuario: 
    story.append(Paragraph(            
        f"<b>1.&nbsp;&nbsp;Definición de usuario:</b>",
        S["lista"],
      ))   
    
    story.append(Paragraph(
        f"Denominamos usuario del servicio educativo a la persona que decide"
        f"voluntariamente postular, matricularse y/o convalidar en la Universidad "
        f"Autónoma de Ica, en adelante, UAI y que hace efectivo dicho proceso "
        f"administrativamente cancelando los derechos establecidos y presentando "
        f"la ficha de inscripción y los requisitos correspondientes.",
        S["lista1"],
    ))
    
    #2.	Voluntariedad de los procesos: 
    story.append(Paragraph(            
        f"<b>2.&nbsp;&nbsp;Voluntariedad de los procesos:</b>",
        S["lista"],
      ))   
    
    story.append(Paragraph(
        f"La postulación mediante el proceso de admisión, la matrícula y la solicitud "
        f"de evaluación por convalidación respectivamente, son actos voluntarios, por "
        f"lo que, al ejecutar su decisión, el usuario ha recibido información, ha "
        f"consultado y tiene clara la información proporcionada y vinculada nuestro "
        f"servicio a nivel académico y administrativo. Así mismo, después de realizado "
        f"los pagos no se harán devoluciones.",
        S["lista1"],
    ))
    #3.	Documentación Administrativa: 
    story.append(Paragraph(            
        f"<b>3.&nbsp;&nbsp;Documentación Administrativa:</b>",
        S["lista"],
      ))   
    
    story.append(Paragraph(
        f"LToda documentación presentada como parte del proceso de admisión, "
        f"matrícula o convalidación formará parte del expediente académico del "
        f"usuario y no será devuelta una vez iniciado el trámite.",
        S["lista1"],
    ))
    #4.	Tarifario y Costos Administrativos: 
    story.append(Paragraph(            
        f"<b>4.&nbsp;&nbsp;Tarifario y Costos Administrativos:</b>",
        S["lista"],
      ))   
    
    story.append(Paragraph(
        f"Los costos y procedimientos administrativos de la UAI se encuentran en el "
        f"Texto Único de Procedimientos Administrativos (TUPA), publicado en el portal "
        f"de transparencia de la universidad. El usuario es responsable de revisar los "
        f"requisitos y las tarifas vigentes antes de realizar cualquier trámite, ya que "
        f"estas pueden ser actualizadas. ",       
        S["lista1"],
    ))
    #5.	Solicitud de Trámites: 
    story.append(Paragraph(            
        f"<b>5.&nbsp;&nbsp;Solicitud de Trámites:</b>",
        S["lista"],
      ))   
    
    story.append(Paragraph(
        f"Todos los trámites deben ser solicitados formalmente según lo establecido "
        f"en el TUPA para la UAI, con la presentación de sus requisitos según se requiera ",       
        S["lista1"],
    ))
    #6.	Solicitudes no contempladas en el TUPA: 
    story.append(Paragraph(            
        f"<b>6.&nbsp;&nbsp;Solicitudes no contempladas en el TUPA:</b>",
        S["lista"],
      ))   
    
    story.append(Paragraph(
        f"Las solicitudes de carácter académico deberán estar dirigidas y serán "
        f"resueltas en primera instancia por la Dirección de su Escuela. En caso de "
        f"reconsideración, la instancia superior serán las Facultades (según el "
        f"programa matriculado) y como última, el Vicerrectorado Académico."
        f"Las solicitudes de carácter administrativo o económico deberán estar "
        f"dirigidas y serán resueltas en primera y última instancia por la Dirección "
        f"Administrativa. En cualquier caso, se requiere la presentación formal de la "
        f"solicitud a través de la oficina central de trámite documentario y archivo, ya "
        f"sea de manera presencial (en mesa de partes) o virtual a través del correo "
        f"oficial del área <b>octda@autonomadeica.edu.pe</b>. Y serán resueltas en un"
        f"plazo de 30 días calendario.",       
        S["lista1"],
    ))
    #7.	Atención de Solicitudes:
    story.append(Paragraph(            
        f"<b>7.&nbsp;&nbsp;Atención de Solicitudes:</b>",
        S["lista"],
      ))   
    
    story.append(Paragraph(
        f"Todos los trámites deben ser solicitados formalmente según lo establecido "
        f"En caso de que el usuario remita correos a instancias que no tienen "
        f"considerados como recibidos por la universidad. En tales casos, se informará "
        f"al usuario que debe revisar el TUPA para dirigir correctamente su solicitud o "
        f"lo contemplado en el punto 6, de ser necesario.",       
        S["lista1"],
    )) 
    #8.	Normativa Institucional:
    story.append(Paragraph(            
        f"<b>8.&nbsp;&nbsp;Normativa Institucional:</b>",
        S["lista"],
      ))   
    
    story.append(Paragraph(
        f"Las normativas generales de la UAI están publicadas en nuestro portal web,"
        f"así mismo podría consultarse en las plataformas académicas del usuario o "
        f"solicitarse por correo institucional a su instancia académica.",
        S["lista1"],
    ))
    #9.	Comunicaciones Oficiales: 
    story.append(Paragraph(            
        f"<b>9.&nbsp;&nbsp;Comunicaciones Oficiales:</b>",
        S["lista"],
      ))   
    
    story.append(Paragraph(
        f"Toda comunicación oficial se remitirá al correo personal y/o institucional del "
        f"usuario y a las plataformas académicas y/o página web de la universidad. "
        f"Se considerará notificado el usuario 48 horas después del envío al correo.",
        S["lista1"],
    ))
    #10.Plataformas Académicas:
    story.append(Paragraph(            
        f"<b>10.&nbsp;&nbsp;Plataformas Académica:</b>",
        S["lista"],
      ))   
    
    story.append(Paragraph(
        f"La universidad cuenta con plataformas académicas que serán "
        f"debidamente compartidos con los usuarios, para poder acceder a ellas es "
        f"necesario que el usuario cuente una conexión de internet estable.",
        S["lista1"],
    ))
    #11.Capacitación en Plataformas: 
    story.append(Paragraph(            
        f"<b>11.&nbsp;&nbsp;Plataformas Académica:</b>",
        S["lista"],
      ))   
    
    story.append(Paragraph(
        f"Es obligación del usuario participar en la charla inductiva y revisar los "
        f"tutoriales sobre el uso de plataformas académicas. No participar se "
        f"considerará como conocimiento implícito del uso adecuado de las "
        f"herramientas. De esa manera, la UAI cumplió con brindar los alcances "
        f"necesarios al usuario de su servicio educativo.",
        S["lista1"],
    ))
    #12.Planes de estudio:
    story.append(Paragraph(            
        f"<b>12.&nbsp;&nbsp;Planes de estudio:</b>",
        S["lista"],
      ))   
    
    story.append(Paragraph(
        f"La universidad se reserva el derecho de actualizar y modificar los planes de "
        f"estudio según su criterio académico, de conformidad con la legislación "
        f"vigente, en ese sentido y de ser necesario, la UAI brindarán los lineamientos "
        f"académicos para poder adecuarse a esos cambios realizados.",
        S["lista1"],
    )) 
    #13.Horarios y Modalidades de Estudio:
    story.append(Paragraph(            
        f"<b>13.&nbsp;&nbsp;Horarios y Modalidades de Estudio:</b>",
        S["lista"],
      ))   
    
    story.append(Paragraph(
        f"La universidad define las modalidades de estudio, los horarios y demás "
        f"estudio según su criterio académico, de conformidad con la legislación "
        f"semestre. En caso de circunstancias de fuerza mayor, los horarios podrán "
        f"ajustarse tanto antes del inicio como durante el desarrollo del semestre en curso.",
        S["lista1"],
    ))  
    #14.Auditoría de Documentos:
    story.append(Paragraph(            
        f"<b>14.&nbsp;&nbsp;Auditoría de Documentos:</b>",
        S["lista"],
      ))   
    
    story.append(Paragraph(
        f"La universidad podrá auditar la validez de los documentos presentados en "
        f"cualquier momento. En caso de irregularidades, se aplicarán las sanciones "        
        f"correspondientes y se podrán emprender acciones pertinentes.",
        S["lista1"],
    ))  
    #15.Requisitos de Grado y Título: 
    story.append(Paragraph(            
        f"<b>15.&nbsp;&nbsp;Requisitos de Grado y Título:</b>",
        S["lista"],
      ))   
    
    story.append(Paragraph(
        f"El usuario deberá informarse de los requisitos y procesos establecidos para"
        f"obtener su grado académico o título profesional, contemplados en la "
        f"normativa y TUPA vigente y aplicable en el momento en el que realice su "        
        f"proceso en la Universidad Autónoma de Ica.",
        S["lista1"],
    ))  
    #16.	Dominio de Idiomas:
    story.append(Paragraph(            
        f"<b>16.&nbsp;&nbsp;Dominio de Idiomas:</b>",
        S["lista"],
      ))   
    
    story.append(Paragraph(
        f"El usuario conoce los requisitos de la ley universitaria sobre el nivel y dominio "
        f"de idioma según el programa de posgrado elegido en el que desea obtener "        
        f"el grado o título, de modificarse dicha norma, deberá adaptarse.",
        S["lista1"],
    )) 
    #17.	Reprogramación de Clases: 
    story.append(Paragraph(            
        f"<b>17.&nbsp;&nbsp;Reprogramación de Clases:</b>",
        S["lista"],
      ))   
    
    story.append(Paragraph(
        f"En casos de fuerza mayor, la universidad podrá reprogramar sesiones o "        
        f"reemplazar docentes con otros de igual o mayor nivel académico.",
        S["lista1"],
    )) 
    #18.	Cambio de modalidad de estudios: 
    story.append(Paragraph(            
        f"<b>18.&nbsp;&nbsp;Cambio de modalidad de estudios:</b>",
        S["lista"],
      ))   
    
    story.append(Paragraph(
        f"En los casos en que la universidad decida que las clases presenciales, por "
        f"razones de fuerza, puedan pasar a dictarse en modalidad virtual o híbrida. El "
        f"usuario se compromete a contar con una conexión estable de internet y un "
        f"ambiente que le permita estar y participar en las sesiones de manera satisfactoria.",
        S["lista1"],
    )) 
    #19.	Postergación o cancelación de clases:
    story.append(Paragraph(            
        f"<b>19.&nbsp;&nbsp;Postergación o cancelación de clases:</b>",
        S["lista"],
      ))   
    
    story.append(Paragraph(
        f"ELa universidad se reserva el derecho de reprogramar o cancelar el inicio de "
        f"clases para las convocatorias de admisión, si no se alcanza el número "
        f"mínimo de participantes (25 matriculados por programa), sin perjuicio de la "
        f"devolución de pagos efectuados hasta la notificación del cambio.",
        S["lista1"],
    )) 
    #20.	Programación de Exámenes: 
    story.append(Paragraph(            
        f"<b>20.&nbsp;&nbsp;Programación de Exámenes:</b>",
        S["lista"],
      ))   
    
    story.append(Paragraph(
        f"Los exámenes y sesiones especiales podrán programarse fuera del horario "        
        f"regular, previa comunicación al usuario.",
        S["lista1"],
    )) 
    #21.	Disponibilidad de Clases Grabadas: 
    story.append(Paragraph(            
        f"<b>21.&nbsp;&nbsp;Disponibilidad de Clases Grabadas:</b>",
        S["lista"],
      ))   
    
    story.append(Paragraph(
        f"Las clases grabadas podrán ser revisadas en línea, pero no descargadas.",        
        S["lista1"],
    )) 
    #22.	Canales de Comunicación: 
    story.append(Paragraph(            
        f"<b>22.&nbsp;&nbsp;Canales de Comunicación:</b>",
        S["lista"],
      ))   
    
    story.append(Paragraph(
        f"Toda comunicación con los docentes o las áreas académicas o "
        f"administrativas de la universidad, después del proceso de admisión, será "
        f"registrada mediante el correo institucional del usuario; a partir del cual "
        f"nuestras áreas podrán contactarse vía telefónica o por plataforma de "
        f"videoconferencia para dar atención a su correo, pudiendo terminar esta "
        f"atención con un correo de respuesta que resuma la solución de su caso o "
        f"consulta, de ser necesario.",        
        S["lista1"],
    )) 
    #23.	Redes Sociales:
    story.append(Paragraph(            
        f"<b>23.&nbsp;&nbsp;Redes Sociales:</b>",
        S["lista"],
      ))   
    
    story.append(Paragraph(
        f"La Universidad no recomienda ni autoriza el uso aplicaciones de mensajería "
        f"instantánea (WhatsApp, Telegram principalmente) como medios de "
        f"comunicación oficial para su servicio o para la interacción entre docentes y "
        f"estudiantes, personal administrativo y autoridades. Cualquier información "
        f"difundida en estos medios no tendrá validez académica o administrativa. "
        f"Para una atención formal establecemos únicamente el correo institucional.",        
        S["lista1"],
    )) 
    #24.	Control de los grupos de mensajería:
    story.append(Paragraph(            
        f"<b>24.&nbsp;&nbsp;Control de los grupos de mensajería:</b>",
        S["lista"],
      ))   
    
    story.append(Paragraph(
        f"La universidad deslinda responsabilidad sobre grupos de mensajería "
        f"creados sin su autorización y no reconoce conversaciones en dichos "
        f"cespacios como pruebas válidas en trámites académicos. "
        f"La universidad comprende que, como un acto voluntario y personal, los "
        f"usuarios puedan decidir formar grupos creados en aplicaciones de "
        f"mensajería instantánea o también denominada “red social” pero sin el "
        f"conocimiento ni autorización de esta institución, deslindando toda "
        f"responsabilidad sobre el contenido compartido en dichos grupos, ya que no "
        f"tiene control ni supervisión sobre los mismos, ni mucho menos en la decisión "
        f"personal de sus usuarios. En consecuencia, cualquier información o "
        f"conversación sostenida en estos espacios no será considerada como "
        f"prueba válida en trámites con la universidad, ni será reconocida como un "
        f"canal formal de comunicación o atención entre estudiantes, docentes o áreas de la universidad."
        f"La Universidad no autoriza a ningún docente a exponer procedimientos y "
        f"costos de trámites, sino más bien a orientar toda consulta a los portales "
        f"oficiales en donde estén expuestos nuestros procedimientos",        
        S["lista1"],
    ))   
#25.	Pago de Matrícula: 
    story.append(Paragraph(            
        f"<b>25.&nbsp;&nbsp;Pago de Matrícula:</b>",
        S["lista"],
      ))   
    
    story.append(Paragraph(
        f"Para poder pagar y ejercer la matrícula de un nuevo semestre, el usuario "
        f"debe haber cancelado el servicio prestado del semestre anterior (valor total del semestre estudiado).",
        S["lista1"],
    )) 
#26.	Del Retiro:
    story.append(Paragraph(            
        f"<b>26.&nbsp;&nbsp;Del Retiro:</b>",
        S["lista"],
      ))   
    
    story.append(Paragraph(
        f"El usuario debe solicitar su retiro de manera formal según el procedimiento "
        f"establecido en el TUPA vigente. Dicho retiro no exime de cancelar las "
        f"pensiones de estudio, pues se contempla como deuda contraída. "
        f"El retiro académico debe formalizarse según el procedimiento del TUPA "
        f"vigente. Esto no exime al usuario de solicitar a la Dirección Administrativa "
        f"cualquier pedido debidamente motivado, de manera formal",
        S["lista1"],
    )) 
#27.	Medios de Pago: 
    story.append(Paragraph(            
        f"<b>27.&nbsp;&nbsp;Medios de Pago:</b>",
        S["lista"],
      ))   
    
    story.append(Paragraph(
        f"Todos los pagos deben efectuarse a nombre de la Razón Social Universidad "
        f"Autónoma de Ica S.A.C. mediante entidades bancarias o enlaces de pago "
        f"oficiales que serán debidamente comunicados.",        
        S["lista1"],
    )) 
#28.	Beneficios Económicos: 
    story.append(Paragraph(            
        f"<b>28.&nbsp;&nbsp;Beneficios Económicos:</b>",
        S["lista"],
      ))   
    
    story.append(Paragraph(
        f"La Universidad cuenta con un reglamento de beneficios económicos para "
        f"estudiantes de pregrado mismo que tiene por objetivo normar los "
        f"procedimientos para conceder o renovar beneficios económicos.",
        S["lista1"],
    )) 
#29.	Horarios de Atención: 
    story.append(Paragraph(            
        f"<b>29.&nbsp;&nbsp;Horarios de Atención:</b>",
        S["lista"],
      ))   
    
    story.append(Paragraph(
        f"La UAI comunicará los horarios de atención de sus áreas para una "
        f"comunicación oportuna.",
        S["lista1"],
    )) 
#30.	Sobre las prácticas e internados: 
    story.append(Paragraph(            
        f"<b>30.&nbsp;&nbsp;Sobre las prácticas e internados:</b>",
        S["lista"],
      ))   
    
    story.append(Paragraph(
        f"Es potestad de la {facultad}, "
        f"establecer la normativa de Prácticas Preprofesionales, misma que es "
        f"aplicable al ingresante de cada programa de estudios, así como asumir los "
        f"costos, trámites y demás conceptos administrativos aplicables del servicio educativo"
        f"El usuario de los programas de la {facultad} conoce "
        f"que todas las actividades académicas prácticas serán llevadas en la sede "
        f"y/o filial, y/o instituciones de salud de nuestra región o con las que se "
        f"hayamos suscritos convenios y se encuentren vigentes en el momento de "
        f"estas. En caso, la persona radique fuera de nuestra región, acepta los "
        f"lineamientos establecidos por la {facultad} que serán notificados por esta, "
        f"oportunamente. Dichos términos, también son aplicables para las "
        f"asignaturas de internado del plan de estudios. En cualquier caso, el usuario "
        f"deberá realizar los procedimientos y las indicaciones, trámites y costos "
        f"asociados que la universidad establezca para las mismas.",
        S["lista1"],
    )) 

#31.	Obligatoriedad del uso de uniforme: 
    story.append(Paragraph(            
        f"<b>31.&nbsp;&nbsp;Obligatoriedad del uso de uniforme:</b>",
        S["lista"],
      ))   
    
    story.append(Paragraph(
        f"El usuario ingresante a los programas de la {facultad}, "
        f"conoce y acepta el uso de los uniformes contemplados en el Reglamento de "
        f"Uniformes de la {facultad}, comprometiéndose a portarlo adecuadamente, "
        f"según se describe en el documento.",
        S["lista1"],
    ))
#32.	Atención a Reclamos y Protección de Derechos Estudiantiles: 
    story.append(Paragraph(            
        f"<b>32.&nbsp;&nbsp;Atención a Reclamos y Protección de Derechos Estudiantiles:</b>",
        S["lista"],
      ))   
    
    story.append(Paragraph(
        f"Para garantizar el bienestar y una experiencia académica de calidad para el "
        f"usuario, la universidad pone a tu disposición los siguientes canales de atención:"
        f"Uniformes de la Facultad, comprometiéndose a portarlo adecuadamente, "
        f"según se describe en el documento.",
        S["lista1"],
    ))
    
    #32.1. Defensoría Universitaria (Ley N° 30220) 
    story.append(Paragraph(            
        f"<b>✓&nbsp;&nbsp;Defensoría Universitaria (Ley N° 30220)</b>",
        S["lista2"],
      ))   
    
    story.append(Paragraph(
        f"Si enfrentas vulneración de derechos, maltrato o irregularidades en "
        f"normativas académicas, puedes presentar tu reclamo a:<br/>"
        f"<b><u>defensoria.universitaria@autonomadeica.edu.pe</u></b><br/>"
        f"Horario: lunes a viernes, 9:00 am - 12:30 pm / 4:00 pm - 6:00 pm",
        S["lista3"],
    ))

    #32.2. Canal de Atención al Estudiante:  
    story.append(Paragraph(            
        f"<b>✓&nbsp;&nbsp;Canal de Atención al Estudiante:</b>",
        S["lista2"],
      ))   
    
    story.append(Paragraph(
        f"Si tienes reclamos o sugerencias sobre matrícula, cursos, horarios,"
        f"evaluaciones, atención del personal o problemas con plataformas "
        f"digitales, principalmente (tras agotar la vía regular o instancia "
        f"estipulada en el TUPA, sin respuesta en 10 días calendario), escríbenos a:<br/>"
        f"<b><u>calidad@autonomadeica.edu.pe</u></b><br/>"
        f"Horario: lunes a viernes, 9:00 am - 12:30 pm / 4:00 pm - 6:00 pm",
        S["lista3"],
    ))

#33.	Criterios académicos para usuarios de traslados y evaluación por convalidación
    story.append(Paragraph(            
        f"<b>33.&nbsp;&nbsp;Atención a Reclamos y Protección de Derechos Estudiantiles:</b>",
        S["lista"],
      ))   
    
    story.append(Paragraph(
        f"a) Sobre los exámenes de suficiencia: El usuario que haya recibido la "
        f"respuesta a su solicitud de evaluación por traslado externo o "
        f"convalidación, en la que se proponga la evaluación mediante"
        f"examen de suficiencia para alguna asignatura, deberá presentarse o "
        f"rendir y cancelar estos exámenes en el primer periodo académico de "
        f"esta institución, conforme al cronograma y calendario informado. "
        f"Cada examen tiene un costo determinado, el cual deberá ser "
        f"abonado según las fechas establecidas en el cronograma. El pago de "
        f"los exámenes de suficiencia no será reembolsable.",
        S["lista3"],
    ))

    story.append(Paragraph(
        f"b)El usuario deberá presentarse al examen de suficiencia en la fecha "
        f"programada, la cual no será reprogramada en ninguna "
        f"circunstancia. En caso de no presentarse o de obtener una nota "
        f"desaprobatoria, deberá cursar la asignatura de manera regular a "
        f"partir del siguiente periodo académico, asumiendo los costos "
        f"correspondientes. Esto provocará cambios en su proyección a académica. ",        
        S["lista3"],
    ))

    story.append(Paragraph(
        f"c) Si el usuario se retira del semestre, pierde automáticamente la "
        f"oportunidad de presentar los exámenes de suficiencia (los que no "
        f"haya pagado y rendido) y deberá cursar las asignaturas de forma de "
        f"regular en el periodo académico en el que se reintegre.",
        S["lista3"],
    ))

    story.append(Paragraph(
        f"d) La proyección a término es referencial: La proyección al periodo de"
        f"término de los estudios de pregrado es una referencia tentativa que "
        f"podría sufrir cambios, ya que está sujeta a la planificación "
        f"académica de cada ciclo que es potestad de la universidad, el "
        f"desempeño académico del estudiante (de no aprobar alguna "
        f"asignatura, no se cumpliría con la proyección presentada en la carta) "
        f"así como a la disponibilidad y registro de matrícula del estudiante, "
        f"siendo este un acto voluntario y que depende exclusivamente del "
        f"usuario. Es decir, la proyección presentada en su carta de respuesta "
        f"es una guía más no una propuesta fáctica de la universidad. ",
        S["lista3"],
    ))

    story.append(Paragraph(
        f"e)	Comunicación específica del proceso: El usuario conoce que, para el "
        f"proceso de convalidación, nos contactaremos desde el área "
        f"académica desde el correo institucional "
        f"<b><u>admision.extraordinaria@autonomadeica.edu.pe</u></b> y de matrícula el "
        f"único canal oficial es el correo institucional de la secretaria "
        f"académica de su facultad, y/o correo de la dirección de su escuela"
        f"profesional, y/o correo de su facultad por parte de la universidad. ",
        S["lista3"],
    ))

    return story


# ─────────────────────────────────────────────────────────────────────────────
# GENERACIÓN DEL PDF
# ─────────────────────────────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────────────
# GENERACIÓN DEL PDF
# ─────────────────────────────────────────────────────────────────────────────
def generar_pdf(solicitud_id: int) -> tuple[io.BytesIO, str]:
    """
    Genera el PDF de la solicitud. Retorna (BytesIO, nombre_archivo).
    Siempre genera un PDF nuevo para evitar problemas de buffer cerrado.
    """
    pdf_cache.delete(solicitud_id)

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
                canv.drawImage(PORTADA_IMG, 0, 0, width=PAGE_W, height=PAGE_H, preserveAspectRatio=False)
            return
        _draw_header_footer(canv, doc, s.get("facultad_nombre", "FACULTAD"), s.get("carrera_nombre", "Carrera"))

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
        paginas = [pdf[i].get_pixmap(matrix=matrix).tobytes("png") for i in range(len(pdf))]
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
        return send_file(buffer_pdf, as_attachment=True,
                         download_name=nombre_pdf, mimetype="application/pdf")
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
    flash("Vista previa de Word no disponible. Use la previsualización del PDF.", "info")
    return redirect(url_for("solicitudes.ver", id=id))


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS PÚBLICOS (usados desde otros módulos)
# ─────────────────────────────────────────────────────────────────────────────
def generar_pdf_bytes(solicitud_id: int) -> bytes:
    buffer, _ = generar_pdf(solicitud_id)
    buffer.seek(0)
    return buffer.read()


# Aliases de compatibilidad hacia atrás
generar_documento_en_memoria   = generar_pdf_bytes
generar_documento_word_bytes   = generar_pdf_bytes



