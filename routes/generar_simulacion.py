# generar_simulacion.py
"""
Genera el PDF "Simulación de Convalidación" usando ReportLab.

La PORTADA (página 1) y la CONTRAPORTADA (última página) se insertan
como imágenes completas. El resto del contenido se construye con
ReportLab (encabezado, cuerpo, tablas, pie de página con número).
"""

import os
import io
from flask import send_file

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm, mm
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, Image, HRFlowable, KeepTogether
)
from reportlab.platypus.flowables import Flowable
from reportlab.pdfgen import canvas

# Rutas de imágenes (configurables)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IMAGES_DIR = os.path.join(os.path.dirname(BASE_DIR), "plantillas_word", "Images")

# COLORES UAI
AZUL_OSCURO = colors.HexColor("#1B3A6B")
AZUL_MEDIO = colors.HexColor("#0070C0")
AZUL_CLARO = colors.HexColor("#00B0F0")
AZUL_TABLA = colors.HexColor("#0070C0")
AZUL_FILA = colors.HexColor("#DDEEFF")
GRIS_TEXTO = colors.HexColor("#595959")
BLANCO = colors.white

PAGE_W, PAGE_H = A4
MARGIN_L = 2.5 * cm
MARGIN_R = 2.0 * cm
MARGIN_T = 2.0 * cm
MARGIN_B = 2.0 * cm
CONTENT_W = PAGE_W - MARGIN_L - MARGIN_R


# ESTILOS
def build_styles():
    base = getSampleStyleSheet()

    def S(name, **kw):
        return ParagraphStyle(name, **kw)

    styles = {
        "header_facultad": S("header_facultad", fontName="Helvetica-Bold", fontSize=9, textColor=AZUL_OSCURO, leading=11),
        "header_carrera": S("header_carrera", fontName="Helvetica", fontSize=8, textColor=AZUL_OSCURO, leading=11),
        "decreto": S("decreto", fontName="Helvetica-Bold", fontSize=9, textColor=AZUL_MEDIO, alignment=TA_CENTER, leading=12, spaceAfter=4),
        "fecha": S("fecha", fontName="Helvetica", fontSize=10, textColor=AZUL_MEDIO, alignment=TA_RIGHT, leading=13, spaceAfter=12),
        "dest_codigo": S("dest_codigo", fontName="Helvetica-Bold", fontSize=10, textColor=AZUL_MEDIO, leading=14),
        "dest_nombre": S("dest_nombre", fontName="Helvetica", fontSize=10, textColor=AZUL_MEDIO, leading=14),
        "dest_presente": S("dest_presente", fontName="Helvetica-Bold", fontSize=10, textColor=AZUL_MEDIO, leading=14, spaceAfter=10),
        "asunto_label": S("asunto_label", fontName="Helvetica-Bold", fontSize=10, textColor=AZUL_MEDIO, leading=14),
        "asunto_texto": S("asunto_texto", fontName="Helvetica", fontSize=10, textColor=AZUL_MEDIO, leading=14, spaceAfter=10),
        "body": S("body", fontName="Helvetica", fontSize=10, textColor=AZUL_MEDIO, leading=15, alignment=TA_JUSTIFY, spaceAfter=8),
        "body_bold": S("body_bold", fontName="Helvetica-Bold", fontSize=10, textColor=AZUL_MEDIO, leading=15, alignment=TA_JUSTIFY, spaceAfter=8),
        "lista": S("lista", fontName="Helvetica", fontSize=10, textColor=AZUL_MEDIO, leading=15, alignment=TA_JUSTIFY, leftIndent=18, spaceAfter=6),
        "titulo_anexo": S("titulo_anexo", fontName="Helvetica-Bold", fontSize=12, textColor=AZUL_OSCURO, alignment=TA_CENTER, spaceBefore=10, spaceAfter=4),
        "titulo_resultado": S("titulo_resultado", fontName="Helvetica-Bold", fontSize=11, textColor=AZUL_MEDIO, alignment=TA_CENTER, spaceAfter=8),
        "titulo_cuadro": S("titulo_cuadro", fontName="Helvetica-Bold", fontSize=9.5, textColor=AZUL_MEDIO, alignment=TA_CENTER, spaceAfter=4),
        "num_item": S("num_item", fontName="Helvetica-Bold", fontSize=10, textColor=AZUL_MEDIO, leading=14, spaceAfter=2),
        "num_body": S("num_body", fontName="Helvetica", fontSize=10, textColor=AZUL_MEDIO, leading=14, alignment=TA_JUSTIFY, leftIndent=18, spaceAfter=6),
        "sublista": S("sublista", fontName="Helvetica", fontSize=10, textColor=AZUL_MEDIO, leading=14, alignment=TA_JUSTIFY, leftIndent=36, spaceAfter=5),
        "check": S("check", fontName="Helvetica-Bold", fontSize=10, textColor=AZUL_MEDIO, leading=14, leftIndent=18, spaceAfter=2),
        "check_body": S("check_body", fontName="Helvetica", fontSize=10, textColor=AZUL_MEDIO, leading=14, alignment=TA_JUSTIFY, leftIndent=36, spaceAfter=2),
        "check_detail": S("check_detail", fontName="Helvetica", fontSize=10, textColor=AZUL_MEDIO, leading=14, leftIndent=36, spaceAfter=6),
        "tabla_header": S("tabla_header", fontName="Helvetica-Bold", fontSize=9, textColor=BLANCO, alignment=TA_CENTER, leading=12),
        "tabla_cell": S("tabla_cell", fontName="Helvetica", fontSize=9, textColor=AZUL_OSCURO, alignment=TA_CENTER, leading=12),
        "tabla_cell_left": S("tabla_cell_left", fontName="Helvetica", fontSize=9, textColor=AZUL_OSCURO, alignment=TA_LEFT, leading=12),
        "tabla_footer": S("tabla_footer", fontName="Helvetica-Bold", fontSize=9, textColor=AZUL_OSCURO, alignment=TA_CENTER, leading=12),
    }
    return styles


# FLOWABLE: imagen de página completa (portada / contraportada)
class FullPageImage(Flowable):
    def __init__(self, path):
        super().__init__()
        self.path = path
        self.width = PAGE_W
        self.height = PAGE_H

    def draw(self):
        self.canv.drawImage(self.path, 0, 0, width=PAGE_W, height=PAGE_H, preserveAspectRatio=False)

    def wrap(self, availW, availH):
        return (PAGE_W, PAGE_H)


# TEMPLATE: encabezado y pie en páginas interiores
def _draw_header_footer(canv, doc, datos):
    canv.saveState()
    header_y = PAGE_H - MARGIN_T + 0.3 * cm

    canv.setFont("Helvetica-Bold", 9)
    canv.setFillColor(AZUL_OSCURO)
    canv.drawString(MARGIN_L, header_y, datos.get("facultad", "Facultad"))
    canv.setFont("Helvetica", 8)
    canv.drawString(MARGIN_L, header_y - 11, datos.get("carrera", "Carrera"))

    logo_path = datos.get("logo_path", "")
    if logo_path and os.path.exists(logo_path):
        logo_w, logo_h = 2.2 * cm, 1.1 * cm
        canv.drawImage(logo_path, PAGE_W - MARGIN_R - logo_w, header_y - logo_h + 4, width=logo_w, height=logo_h, preserveAspectRatio=True, mask="auto")
    else:
        canv.setFont("Helvetica-Bold", 16)
        canv.setFillColor(AZUL_OSCURO)
        canv.drawRightString(PAGE_W - MARGIN_R, header_y - 2, "UAI")

    line_y = header_y - 16
    canv.setStrokeColor(colors.HexColor("#CCCCCC"))
    canv.setLineWidth(0.5)
    canv.line(MARGIN_L, line_y, PAGE_W - MARGIN_R, line_y)

    pg_num = doc.page - 1
    canv.setFont("Helvetica", 9)
    canv.setFillColor(AZUL_OSCURO)
    canv.drawCentredString(PAGE_W / 2, MARGIN_B - 0.5 * cm, str(pg_num))
    canv.restoreState()


# TABLAS HELPER
def tabla_style_base(has_footer=True, footer_row=None):
    cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), AZUL_TABLA),
        ("TEXTCOLOR", (0, 0), (-1, 0), BLANCO),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1 if not has_footer else -2), [colors.white, colors.HexColor("#EEF5FB")]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#AAAAAA")),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]
    if has_footer and footer_row is not None:
        cmds += [
            ("BACKGROUND", (0, footer_row), (-1, footer_row), colors.HexColor("#D9E8F5")),
            ("FONTNAME", (0, footer_row), (-1, footer_row), "Helvetica-Bold"),
            ("FONTSIZE", (0, footer_row), (-1, footer_row), 9),
        ]
    return TableStyle(cmds)


# CONSTRUCTOR PRINCIPAL
def build_pdf(solicitud_id, datos):
    """
    Genera el PDF completo para una solicitud de convalidación.
    Retorna (buffer_bytes, nombre_archivo)
    """
    from db.conexion import get_connection
    
    S = build_styles()
    story = []

    # 1. PORTADA (imagen de página completa)
    portada_path = os.path.join(IMAGES_DIR, "PORTADA.png")
    if os.path.exists(portada_path):
        story.append(FullPageImage(portada_path))
    else:
        story.append(Paragraph("<b>[PORTADA – insertar imagen]</b>", S["body"]))
    story.append(PageBreak())

    # 2. CARTA PRINCIPAL
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph('"Año de la Esperanza y el Fortalecimiento de la Democracia"', S["decreto"]))
    story.append(Spacer(1, 0.4 * cm))

    story.append(Paragraph(f'{datos.get("fecha", "")} de {datos.get("mes", "")} del {datos.get("anio", "")}', S["fecha"]))

    story.append(Paragraph(f'<b><u>{datos.get("codigo", "")}</u></b>', S["dest_codigo"]))
    story.append(Paragraph(datos.get("nombre", ""), S["dest_nombre"]))
    story.append(Paragraph("<b><u>Presente. –</u></b>", S["dest_presente"]))
    story.append(Spacer(1, 0.2 * cm))

    asunto_data = [[Paragraph("<b>Asunto</b>", S["asunto_label"]), Paragraph(": Simulación de convalidación", S["asunto_texto"])]]
    asunto_table = Table(asunto_data, colWidths=[3.0 * cm, CONTENT_W - 3.0 * cm])
    asunto_table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    story.append(asunto_table)

    facultad = datos.get("facultad", "")
    story.append(Paragraph(f"Reciba usted un cordial saludo a nombre {facultad} de la Universidad Autónoma de Ica.", S["body"]))

    ies_origen = datos.get("ies_origen", "")
    story.append(Paragraph(f"De acuerdo con la solicitud de evaluación por convalidación solicitada a la instancia académica de la {facultad}, se ha procedido a analizar los documentos publicados en mérito a criterios establecidos en nuestro Reglamento de Estudios vigente con el cual se propone y cumple con emitir respuesta a su pedido específico, del cual se desprende el <b>Anexo 01</b> del presente documento.", S["body"]))

    story.append(Paragraph("La Universidad, establece dos formas de convalidar una asignatura:", S["body"]))
    story.append(Paragraph("1.&nbsp;&nbsp;Mediante convalidación directa – Similitud de asignaturas y contenidos del sílabo según reglamento de estudios.", S["lista"]))
    story.append(Paragraph("2.&nbsp;&nbsp;Mediante convalidación por examen de suficiencia – Mecanismo que evalúa las competencias que acredite por el avance y asignaturas aprobadas en el plan de estudios de la institución de origen y que no cumplan con el punto 1, mediante un examen de conocimientos. Para aprobar se exige una nota mínima de 13. El número de asignaturas que se pueden rendir lo define la universidad. Esta propuesta es determinada por la universidad y no es solicitada por la persona interesada en ningún caso.", S["lista"]))

    story.append(Paragraph("Dicha propuesta está sujeta a términos y condiciones académicas y administrativas contenidas en el <b>Anexo 02</b>, que están asociadas a nuestro servicio educativo, por lo que adjuntamos la información detalladamente para que usted como persona interesada pueda revisarla.", S["body"]))
    story.append(Paragraph("Asimismo, en la simulación se podrá verificar las asignaturas por convalidación directa y la cantidad de exámenes propuestos, mismos que deberán ser aplicados y aprobados para que se pueda dar por convalidado.", S["body"]))
    story.append(Paragraph("Es importante mencionar que para seguir con el procedimiento de convalidación la persona interesada debe confirmar la aceptación del presente documento a través del correo de <u><a href='mailto:admision.extraordinaria@autonomadeica.edu.pe' color='#0070C0'>admision.extraordinaria@autonomadeica.edu.pe</a></u> para lo cual tiene un plazo de 48 horas después de notificada dicha respuesta.", S["body"]))

    # 3. ANEXO 01
    story.append(Spacer(1, 0.5 * cm))
    story.append(Paragraph("Anexo 01", S["titulo_anexo"]))
    story.append(Paragraph("Resultado de la convalidación", S["titulo_resultado"]))

    programa = datos.get("programa", "")
    tratamiento = datos.get("tratamiento", "")
    story.append(Paragraph(f"En la simulación se podrá verificar las asignaturas por convalidación directa al programa de estudios de {programa}, para {tratamiento} proveniente del <b>\"{ies_origen}\"</b>, así como el número de asignaturas no convalidadas y exámenes de suficiencia propuestos por la Facultad.", S["body"]))
    story.append(Spacer(1, 0.3 * cm))

    # CUADRO 01: Asignaturas y créditos convalidados
    story.append(Paragraph("Cuadro N°01. Asignaturas y créditos convalidados", S["titulo_cuadro"]))

    cursos_conv = datos.get("cursos_convalidados", [])
    total_conv = datos.get("total_creditos_conv", 0)

    c01_data = [[Paragraph("CICLO", S["tabla_header"]), Paragraph("NOMBRE DEL CURSO", S["tabla_header"]), Paragraph("CRÉDITOS", S["tabla_header"])]]
    for r in cursos_conv:
        c01_data.append([Paragraph(str(r.get("ciclo", "")), S["tabla_cell"]), Paragraph(r.get("nombre", ""), S["tabla_cell_left"]), Paragraph(str(r.get("creditos", "")), S["tabla_cell"])])
    c01_data.append([Paragraph("", S["tabla_footer"]), Paragraph("TOTAL DE CRÉDITOS CONVALIDADOS", S["tabla_footer"]), Paragraph(str(total_conv), S["tabla_footer"])])

    c01 = Table(c01_data, colWidths=[2.0 * cm, CONTENT_W - 5.0 * cm, 3.0 * cm], repeatRows=1)
    c01.setStyle(tabla_style_base(footer_row=len(c01_data) - 1))
    story.append(c01)
    story.append(Spacer(1, 0.4 * cm))

    # CUADRO 02: Costo de créditos convalidados
    story.append(Paragraph("Cuadro N°02. Costo de créditos convalidados", S["titulo_cuadro"]))

    costo_credito = datos.get("costo_credito_conv", 0)
    subtotal_conv = total_conv * costo_credito

    c02_data = [[Paragraph("N° CRÉDITOS CONVALIDADOS", S["tabla_header"]), Paragraph("COSTO POR CRÉDITO", S["tabla_header"]), Paragraph("IMPORTE SUBTOTAL", S["tabla_header"])], [Paragraph(str(total_conv), S["tabla_cell"]), Paragraph(f"S/ {costo_credito:.2f}", S["tabla_cell"]), Paragraph(f"S/ {subtotal_conv:.2f}", S["tabla_cell"])]]
    cw2 = CONTENT_W / 3
    c02 = Table(c02_data, colWidths=[cw2, cw2, cw2])
    c02.setStyle(tabla_style_base(has_footer=False))
    story.append(c02)
    story.append(Spacer(1, 0.4 * cm))

    # CUADRO 03: Suficiencia
    story.append(Paragraph("Cuadro N°03. Asignaturas y créditos por convalidar mediante examen de suficiencia", S["titulo_cuadro"]))

    cursos_suf = datos.get("cursos_suficiencia", [])
    total_suf = datos.get("total_creditos_suf", 0)

    c03_data = [[Paragraph("CICLO", S["tabla_header"]), Paragraph("NOMBRE DEL CURSO", S["tabla_header"]), Paragraph("CRÉDITOS", S["tabla_header"]), Paragraph("DENOMINACIÓN", S["tabla_header"])]]
    for r in cursos_suf:
        c03_data.append([Paragraph(str(r.get("ciclo", "")), S["tabla_cell"]), Paragraph(r.get("nombre", ""), S["tabla_cell_left"]), Paragraph(str(r.get("creditos", "")), S["tabla_cell"]), Paragraph(r.get("denominacion", "EXAMEN DE SUFICIENCIA"), S["tabla_cell"])])
    c03_data.append([Paragraph("", S["tabla_footer"]), Paragraph("TOTAL DE CRÉDITOS", S["tabla_footer"]), Paragraph(str(total_suf), S["tabla_footer"]), Paragraph("", S["tabla_footer"])])

    cw3a, cw3b, cw3c, cw3d = 1.8 * cm, CONTENT_W - 8.0 * cm, 2.2 * cm, 3.8 * cm
    c03 = Table(c03_data, colWidths=[cw3a, cw3b, cw3c, cw3d], repeatRows=1)
    c03.setStyle(tabla_style_base(footer_row=len(c03_data) - 1))
    story.append(c03)
    story.append(Spacer(1, 0.4 * cm))

    # CUADRO 04: Costo examen de suficiencia
    story.append(Paragraph("Cuadro N°04. Costo del examen de suficiencia", S["titulo_cuadro"]))

    num_examenes = len([c for c in cursos_suf if c.get("denominacion", "").upper().startswith("EXAMEN")])
    costo_examen = datos.get("costo_examen_suf", 0)
    subtotal_suf = num_examenes * costo_examen

    c04_data = [[Paragraph("N° EXÁMENES DE SUFICIENCIA", S["tabla_header"]), Paragraph("COSTO POR EXAMEN", S["tabla_header"]), Paragraph("IMPORTE SUBTOTAL", S["tabla_header"])], [Paragraph(str(num_examenes), S["tabla_cell"]), Paragraph(f"S/ {costo_examen:.2f}", S["tabla_cell"]), Paragraph(f"S/ {subtotal_suf:.2f}", S["tabla_cell"])]]
    c04 = Table(c04_data, colWidths=[cw2, cw2, cw2])
    c04.setStyle(tabla_style_base(has_footer=False))
    story.append(c04)
    story.append(Spacer(1, 0.4 * cm))

    # CUADRO 05: Costo total
    story.append(Paragraph("Cuadro N°05. Costo de convalidación total", S["titulo_cuadro"]))

    total_general = subtotal_conv + subtotal_suf
    cw5 = CONTENT_W / 2
    c05_data = [[Paragraph("CONVALIDACIÓN", S["tabla_header"]), Paragraph("IMPORTE TOTAL", S["tabla_header"])], [Paragraph("DIRECTA", S["tabla_cell"]), Paragraph(f"S/ {subtotal_conv:.2f}", S["tabla_cell"])], [Paragraph("POR E. S.", S["tabla_cell"]), Paragraph(f"S/ {subtotal_suf:.2f}", S["tabla_cell"])], [Paragraph("TOTAL", S["tabla_footer"]), Paragraph(f"S/ {total_general:.2f}", S["tabla_footer"])]]
    c05 = Table(c05_data, colWidths=[cw5, cw5])
    c05.setStyle(tabla_style_base(footer_row=3))
    story.append(c05)
    story.append(Spacer(1, 0.4 * cm))

    # CUADRO 06: No convalidadas
    story.append(Paragraph("Cuadro N°06. Asignaturas no convalidadas", S["titulo_cuadro"]))

    cursos_no = datos.get("cursos_no_conv", [])
    total_no = datos.get("total_creditos_no_conv", 0)

    c06_data = [[Paragraph("CICLO", S["tabla_header"]), Paragraph("NOMBRE DEL CURSO", S["tabla_header"]), Paragraph("CRÉDITOS", S["tabla_header"]), Paragraph("PERIODO LECTIVO", S["tabla_header"])]]
    for r in cursos_no:
        c06_data.append([Paragraph(str(r.get("ciclo", "")), S["tabla_cell"]), Paragraph(r.get("nombre", ""), S["tabla_cell_left"]), Paragraph(str(r.get("creditos", "")), S["tabla_cell"]), Paragraph(r.get("periodo", ""), S["tabla_cell"])])
    c06_data.append([Paragraph("", S["tabla_footer"]), Paragraph("TOTAL DE CRÉDITOS", S["tabla_footer"]), Paragraph(str(total_no), S["tabla_footer"]), Paragraph("", S["tabla_footer"])])

    c06 = Table(c06_data, colWidths=[cw3a, cw3b, cw3c, cw3d], repeatRows=1)
    c06.setStyle(tabla_style_base(footer_row=len(c06_data) - 1))
    story.append(c06)

    # 4. ANEXO 02 - Términos del servicio
    story.append(Spacer(1, 0.5 * cm))
    story.append(Paragraph("Anexo 02", S["titulo_anexo"]))
    story.append(Paragraph("Términos del servicio educativo para estudios de pregrado de la UAI", S["titulo_resultado"]))

    terminos = [
        ("1.", "Definición de usuario:", "Denominamos usuario del servicio educativo a la persona que decide voluntariamente postular, matricularse y/o convalidar en la Universidad Autónoma de Ica, en adelante, UAI y que hace efectivo dicho proceso administrativamente cancelando los derechos establecidos y presentando la ficha de inscripción y los requisitos correspondientes."),
        ("2.", "Voluntariedad de los procesos:", "La postulación mediante el proceso de admisión, la matrícula y la solicitud de evaluación por convalidación respectivamente, son actos voluntarios, por lo que, al ejecutar su decisión, el usuario ha recibido información, ha consultado y tiene clara la información proporcionada y vinculada nuestro servicio a nivel académico y administrativo. Así mismo, después de realizado los pagos no se harán devoluciones."),
        ("3.", "Documentación Administrativa:", "Toda documentación presentada como parte del proceso de admisión, matrícula o convalidación formará parte del expediente académico del usuario y no será devuelta una vez iniciado el trámite."),
    ]

    for num, titulo, texto in terminos:
        story.append(Paragraph(f"<b>{num}&nbsp;&nbsp;{titulo}</b>", S["num_item"]))
        for parrafo in texto.split("\n\n"):
            story.append(Paragraph(parrafo.strip(), S["num_body"]))

    # 5. CONTRAPORTADA (imagen de página completa)
    story.append(PageBreak())
    contraportada_path = os.path.join(IMAGES_DIR, "CONTRAPORTADA.png")
    if os.path.exists(contraportada_path):
        story.append(FullPageImage(contraportada_path))
    else:
        story.append(Paragraph("<b>[CONTRAPORTADA – insertar imagen]</b>", S["body"]))

    # COMPILAR EL PDF
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=MARGIN_L, rightMargin=MARGIN_R, topMargin=MARGIN_T + 1.2 * cm, bottomMargin=MARGIN_B, title="Simulación de Convalidación", author="Universidad Autónoma de Ica")

    def on_page(canv, doc):
        if doc.page == 1:
            return
        _draw_header_footer(canv, doc, datos)

    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    buffer.seek(0)
    return buffer, f"SIMULACION_{datos.get('codigo', str(solicitud_id))}.pdf"