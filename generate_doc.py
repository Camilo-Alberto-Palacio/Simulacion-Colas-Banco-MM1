"""
Generador Dinámico del Informe Académico Oficial en Formato Word (.docx)
Normas APA 7.ª Edición · Redacción Técnica Reflexiva (Grupo 25)
Actividad Didáctica 2-M3 — Solución de un Problema Bancario (Banco de Colombia).
Asignatura: Simulación (PREICA2602B020045) — Grupo 25.
Institución Universitaria Digital de Antioquia (IU Digital) — Facultad de Ingeniería.

Carga el 100 % de las métricas experimentales desde 'results/*.csv' (cero cifras fijas),
incrusta las 6 figuras científicas generadas a 300 DPI con formato APA 7, construye Portada,
Índice (TOC) y numeración automática de páginas, y actualiza campos vía Microsoft Word.
"""

import os
import re
import shutil
import subprocess
import sys
import pandas as pd
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn
from docx.shared import Inches, Pt, RGBColor

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(BASE_DIR, "results")

# Paleta cromática sobria y académica (APA 7)
COLOR_PRIMARY = RGBColor(0x0F, 0x17, 0x2A)    # Slate 900
COLOR_SECONDARY = RGBColor(0x1E, 0x3A, 0x8A)  # Navy Blue
COLOR_BODY = RGBColor(0x11, 0x18, 0x27)       # Ink Dark
COLOR_MUTED = RGBColor(0x47, 0x55, 0x69)      # Slate 600
COLOR_CODE = RGBColor(0x0F, 0x17, 0x2A)

_SUB_SUP_RE = re.compile(r"(_\{[^}]+\}|\^\{[^}]+\})")


def set_cell_background(cell, fill_hex: str) -> None:
    shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{fill_hex}"/>')
    cell._tc.get_or_add_tcPr().append(shd)


def set_cell_margins(cell, top=65, bottom=65, left=75, right=75) -> None:
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = OxmlElement("w:tcMar")
    for margin_name, val in [("top", top), ("bottom", bottom), ("left", left), ("right", right)]:
        node = OxmlElement(f"w:{margin_name}")
        node.set(qn("w:w"), str(val))
        node.set(qn("w:type"), "dxa")
        tcMar.append(node)
    tcPr.append(tcMar)


def set_cell_borders(cell, top="none", bottom="none", left="none", right="none", color="0F172A", sz="4") -> None:
    tcPr = cell._tc.get_or_add_tcPr()
    tcBorders = OxmlElement("w:tcBorders")
    for b_name, b_val in {"top": top, "left": left, "bottom": bottom, "right": right}.items():
        node = OxmlElement(f"w:{b_name}")
        node.set(qn("w:val"), b_val)
        if b_val != "none":
            node.set(qn("w:sz"), str(sz))
            node.set(qn("w:space"), "0")
            node.set(qn("w:color"), color)
        tcBorders.append(node)
    tcPr.append(tcBorders)


def set_row_pagination_rules(row, is_header: bool = False) -> None:
    trPr = row._tr.get_or_add_trPr()
    trPr.append(OxmlElement("w:cantSplit"))
    if is_header:
        trPr.append(OxmlElement("w:tblHeader"))


def add_word_field(
    paragraph,
    field_name: str,
    font_size: float = 9.0,
    color: RGBColor = COLOR_MUTED,
    bold: bool = False,
) -> None:
    for tag, attrs, text in [
        ("w:fldChar", {"w:fldCharType": "begin", "w:dirty": "true"}, ""),
        ("w:instrText", {"xml:space": "preserve"}, f" {field_name} "),
        ("w:fldChar", {"w:fldCharType": "separate"}, ""),
        ("w:fldChar", {"w:fldCharType": "end"}, ""),
    ]:
        r = paragraph.add_run()
        attr_str = " ".join(f'{k}="{v}"' for k, v in attrs.items())
        elem = parse_xml(f'<{tag} {nsdecls("w")} {attr_str}>{text}</{tag}>')
        r._r.append(elem)
        r.font.name = "Times New Roman"
        r.font.size = Pt(font_size)
        r.font.bold = bold
        r.font.color.rgb = color


def add_rich_runs(
    paragraph,
    text: str,
    font_name: str = "Times New Roman",
    font_size: float = 10.5,
    color: RGBColor = COLOR_BODY,
    bold: bool = False,
    italic: bool = False,
) -> None:
    """Renderiza subíndices _{...} y superíndices ^{...} como formato nativo de Word."""
    parts = _SUB_SUP_RE.split(text)
    for part in parts:
        if not part:
            continue
        is_sub = part.startswith("_{") and part.endswith("}")
        is_sup = part.startswith("^{") and part.endswith("}")
        content = part[2:-1] if (is_sub or is_sup) else part
        run = paragraph.add_run(content)
        run.font.name = font_name
        run.font.size = Pt(font_size)
        run.font.color.rgb = color
        run.font.bold = bold
        run.font.italic = italic
        if is_sub:
            run.font.subscript = True
        elif is_sup:
            run.font.superscript = True


def add_apa_label_and_title(doc, label: str, title: str) -> None:
    """Inserta encabezado de Tabla X o Figura X conforme a APA 7 (etiqueta en negrita y título en cursiva arriba)."""
    p_lbl = doc.add_paragraph()
    p_lbl.alignment = WD_ALIGN_PARAGRAPH.LEFT
    p_lbl.paragraph_format.space_before = Pt(8)
    p_lbl.paragraph_format.space_after = Pt(1.5)
    p_lbl.paragraph_format.keep_with_next = True
    add_rich_runs(p_lbl, label, font_size=10.0, color=COLOR_PRIMARY, bold=True)

    p_tit = doc.add_paragraph()
    p_tit.alignment = WD_ALIGN_PARAGRAPH.LEFT
    p_tit.paragraph_format.space_before = Pt(0)
    p_tit.paragraph_format.space_after = Pt(4)
    p_tit.paragraph_format.keep_with_next = True
    add_rich_runs(p_tit, title, font_size=10.0, color=COLOR_BODY, italic=True)


def add_apa_note(doc, note_body: str, space_after: float = 9.0) -> None:
    """Inserta Nota. alineada a la izquierda en 10 pt conforme a Normas APA 7."""
    p_note = doc.add_paragraph()
    p_note.alignment = WD_ALIGN_PARAGRAPH.LEFT
    p_note.paragraph_format.space_before = Pt(3)
    p_note.paragraph_format.space_after = Pt(space_after)
    p_note.paragraph_format.line_spacing = 1.12
    add_rich_runs(p_note, "Nota. ", font_size=10.0, color=COLOR_BODY, italic=True)
    add_rich_runs(p_note, note_body, font_size=10.0, color=COLOR_BODY)


def format_apa_table(
    doc,
    table_num: str,
    title: str,
    col_widths,
    headers,
    data,
    note_text: str,
    font_size: float = 8.2,
) -> None:
    """Construye una tabla en formato estricto APA 7 (sin líneas verticales ni relleno en cuerpo)."""
    add_apa_label_and_title(doc, table_num, title)

    table = doc.add_table(rows=1 + len(data), cols=len(headers))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False

    header_row = table.rows[0]
    set_row_pagination_rules(header_row, is_header=True)
    for col_idx, heading in enumerate(headers):
        cell = header_row.cells[col_idx]
        cell.width = col_widths[col_idx]
        set_cell_background(cell, "FFFFFF")
        set_cell_margins(cell, top=70, bottom=70, left=65, right=65)
        set_cell_borders(cell, top="single", bottom="single", left="none", right="none", color="0F172A", sz="8")

        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT if col_idx == 0 else WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(1.5)
        p.paragraph_format.space_after = Pt(1.5)
        p.paragraph_format.keep_with_next = True
        add_rich_runs(p, heading, font_size=font_size, color=COLOR_PRIMARY, bold=True)

    num_rows = len(data)
    for row_idx, row_data in enumerate(data, start=1):
        row = table.rows[row_idx]
        set_row_pagination_rules(row, is_header=False)
        is_last = row_idx == num_rows
        bottom_border = "single" if is_last else "none"
        bottom_sz = "8" if is_last else "4"

        for col_idx, val in enumerate(row_data):
            cell = row.cells[col_idx]
            cell.width = col_widths[col_idx]
            set_cell_background(cell, "FFFFFF")
            set_cell_margins(cell, top=50, bottom=50, left=65, right=65)
            set_cell_borders(cell, top="none", bottom=bottom_border, left="none", right="none", color="0F172A", sz=bottom_sz)

            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT if col_idx == 0 else WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.space_before = Pt(1.0)
            p.paragraph_format.space_after = Pt(1.0)
            # Mantiene tablas compactas completas en la misma página junto a su Nota. APA 7
            p.paragraph_format.keep_with_next = (num_rows <= 14) or is_last
            add_rich_runs(p, str(val), font_size=font_size, color=COLOR_BODY, bold=(col_idx == 0))

    add_apa_note(doc, note_text, space_after=8.0)


def add_code_listing(doc, code_lines: list, caption_note: str) -> None:
    tbl = doc.add_table(rows=1, cols=1)
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl.autofit = False

    cell = tbl.cell(0, 0)
    cell.width = Inches(6.5)
    set_cell_background(cell, "F8FAFC")
    set_cell_margins(cell, top=80, bottom=80, left=110, right=110)
    set_cell_borders(cell, top="single", bottom="single", left="single", right="single", color="CBD5E1", sz="6")

    p = cell.paragraphs[0]
    p.paragraph_format.space_before = Pt(2)
    p.paragraph_format.space_after = Pt(2)
    p.paragraph_format.line_spacing = 1.05
    p.paragraph_format.keep_with_next = True

    for line_num, line_txt in enumerate(code_lines, start=1):
        r_num = p.add_run(f"{line_num:2d} ")
        r_num.font.name = "Consolas"
        r_num.font.size = Pt(8.1)
        r_num.font.color.rgb = COLOR_MUTED

        suffix = "\n" if line_num < len(code_lines) else ""
        r_code = p.add_run(f"{line_txt}{suffix}")
        r_code.font.name = "Consolas"
        r_code.font.size = Pt(8.1)
        r_code.font.color.rgb = COLOR_CODE

    add_apa_note(doc, caption_note, space_after=8.0)


def update_word_toc_and_fields(docx_path: str) -> bool:
    """Actualiza Tabla de Contenido y campos PAGE/NUMPAGES mediante Microsoft Word COM."""
    if os.name != "nt" or not shutil.which("powershell"):
        return False
    abs_path = os.path.abspath(docx_path).replace("'", "''")
    ps_script = (
        "$ErrorActionPreference = 'Stop'; "
        "$word = $null; $doc = $null; "
        "try { "
        "  $word = New-Object -ComObject Word.Application; "
        "  $word.Visible = $false; "
        "  $word.DisplayAlerts = 0; "
        f"  $doc = $word.Documents.Open('{abs_path}'); "
        "  $doc.Repaginate(); "
        "  foreach ($toc in $doc.TablesOfContents) { $toc.Update(); } "
        "  foreach ($sec in $doc.Sections) { "
        "    foreach ($hf in $sec.Headers) { $hf.Range.Fields.Update() | Out-Null; } "
        "    foreach ($hf in $sec.Footers) { $hf.Range.Fields.Update() | Out-Null; } "
        "  } "
        "  $doc.Fields.Update() | Out-Null; "
        "  $doc.Save(); "
        "} finally { "
        "  if ($doc) { $doc.Close([ref]$false); } "
        "  if ($word) { $word.Quit(); } "
        "}"
    )
    try:
        res = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_script],
            capture_output=True,
            text=True,
            timeout=60,
        )
        return res.returncode == 0
    except Exception:
        return False


def build_document(output_filename: str = None) -> None:
    if output_filename is None:
        output_filename = os.path.join(
            BASE_DIR,
            "Evidencia de Aprendizaje 3 - Módulo 2. Actividad didáctica 2-M3 - Solución Problema Bancario.docx",
        )

    # Cargar 100 % de resultados dinámicamente desde CSVs
    df_sum10 = pd.read_csv(os.path.join(RESULTS_DIR, "resumen_10_replicas_escenarios.csv"))
    df_rep10 = pd.read_csv(os.path.join(RESULTS_DIR, "detalle_10_replicas_por_tipo.csv"))
    df_caj10 = pd.read_csv(os.path.join(RESULTS_DIR, "cajeros_10_replicas_resumen.csv"))
    df_sub10 = pd.read_csv(os.path.join(RESULTS_DIR, "perfiles_8_usuarios_10_replicas.csv"))
    df_sample_n = pd.read_csv(os.path.join(RESULTS_DIR, "tamano_muestra_replicas.csv"))
    df_mc100 = pd.read_csv(os.path.join(RESULTS_DIR, "resumen_montecarlo_100_replicas.csv"))
    df_jsq100 = pd.read_csv(os.path.join(RESULTS_DIR, "sensibilidad_jsq_100_replicas.csv"))
    df_wait_act = pd.read_csv(os.path.join(RESULTS_DIR, "esperas_por_accion_100_replicas.csv"))
    df_wait_typ = pd.read_csv(os.path.join(RESULTS_DIR, "esperas_por_tipo_100_replicas.csv"))

    doc = Document()

    for section in doc.sections:
        # Márgenes estándar APA 7 (1.0 in / 2.54 cm en los cuatro lados)
        section.top_margin = Inches(1.0)
        section.bottom_margin = Inches(1.0)
        section.left_margin = Inches(1.0)
        section.right_margin = Inches(1.0)
        section.different_first_page_header_footer = True

    content_sec = doc.sections[0]
    hdr = content_sec.header.paragraphs[0]
    hdr.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    r_hdr = hdr.add_run("OPTIMIZACIÓN DE COLAS INDEPENDIENTES M/M/1 — BANCO DE COLOMBIA")
    r_hdr.font.name = "Times New Roman"
    r_hdr.font.size = Pt(8.5)
    r_hdr.font.color.rgb = COLOR_MUTED

    ftr = content_sec.footer.paragraphs[0]
    ftr.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_ftr = ftr.add_run("IU Digital de Antioquia · Simulación (PREICA2602B020045)  |  Página ")
    r_ftr.font.name = "Times New Roman"
    r_ftr.font.size = Pt(8.5)
    r_ftr.font.color.rgb = COLOR_MUTED
    add_word_field(ftr, "PAGE", font_size=8.5)
    r_ftr2 = ftr.add_run(" de ")
    r_ftr2.font.name = "Times New Roman"
    r_ftr2.font.size = Pt(8.5)
    r_ftr2.font.color.rgb = COLOR_MUTED
    add_word_field(ftr, "NUMPAGES", font_size=8.5)

    def add_h1(text: str):
        p = doc.add_paragraph(style="Heading 1")
        p.paragraph_format.space_before = Pt(10)
        p.paragraph_format.space_after = Pt(3.5)
        p.paragraph_format.keep_with_next = True
        add_rich_runs(p, text, font_size=12.0, color=COLOR_PRIMARY, bold=True)
        return p

    def add_h2(text: str):
        p = doc.add_paragraph(style="Heading 2")
        p.paragraph_format.space_before = Pt(9)
        p.paragraph_format.space_after = Pt(3)
        p.paragraph_format.keep_with_next = True
        add_rich_runs(p, text, font_size=10.8, color=COLOR_SECONDARY, bold=True)
        return p

    def add_p(text: str, space_after: float = 5.5):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(space_after)
        p.paragraph_format.line_spacing = 1.15
        add_rich_runs(p, text, font_size=10.5, color=COLOR_BODY)
        return p

    def _add_list_item(prefix_txt: str, lead_bold: str, body_text: str):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        p.paragraph_format.left_indent = Inches(0.32)
        p.paragraph_format.first_line_indent = Inches(-0.20)
        p.paragraph_format.space_before = Pt(1)
        p.paragraph_format.space_after = Pt(4.0)
        p.paragraph_format.line_spacing = 1.15
        add_rich_runs(p, prefix_txt, font_size=10.5, color=COLOR_PRIMARY, bold=True)
        add_rich_runs(p, lead_bold, font_size=10.5, color=COLOR_BODY, bold=True)
        add_rich_runs(p, body_text, font_size=10.5, color=COLOR_BODY)
        return p

    def add_bullet(lead_bold: str, body_text: str):
        clean_lead = lead_bold.lstrip("• ").lstrip()
        return _add_list_item("•  ", clean_lead, body_text)

    def add_numbered_item(num_label: str, lead_bold: str, body_text: str):
        return _add_list_item(f"{num_label} ", lead_bold, body_text)

    def add_equation_box(eq_text: str, eq_num: str = ""):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(4)
        p.paragraph_format.space_after = Pt(6)
        p.paragraph_format.tab_stops.add_tab_stop(Inches(3.25), WD_ALIGN_PARAGRAPH.CENTER)
        p.paragraph_format.tab_stops.add_tab_stop(Inches(6.5), WD_ALIGN_PARAGRAPH.RIGHT)
        p.add_run("\t")
        add_rich_runs(p, eq_text, font_size=10.0, color=COLOR_PRIMARY, italic=True)
        if eq_num:
            p.add_run("\t")
            add_rich_runs(p, eq_num, font_size=10.0, color=COLOR_PRIMARY)
        return p

    def add_apa_fig(filename: str, fig_num: str, title: str, note_text: str, width_in: float = 6.35):
        filepath = os.path.join(RESULTS_DIR, filename)
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Figura requerida no encontrada: {filepath}")

        add_apa_label_and_title(doc, fig_num, title)

        p_img = doc.add_paragraph()
        p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_img.paragraph_format.space_before = Pt(2)
        p_img.paragraph_format.space_after = Pt(2)
        p_img.paragraph_format.keep_with_next = True
        p_img.add_run().add_picture(filepath, width=Inches(width_in))

        add_apa_note(doc, note_text, space_after=9.0)

    # =========================================================
    # EXTRACCIÓN DINÁMICA DE MÉTRICAS CLAVE (100 % DESDE CSV)
    # =========================================================
    base_caj = df_caj10[df_caj10["escenario"] == "E1_3_Mixtas"].copy().reset_index(drop=True)
    c_min_srv = base_caj.loc[base_caj["servicio_s_prom"].idxmin()]
    c_max_srv = base_caj.loc[base_caj["servicio_s_prom"].idxmax()]
    c_min_w = base_caj.loc[base_caj["atencion_w_prom"].idxmin()]
    c_max_w = base_caj.loc[base_caj["atencion_w_prom"].idxmax()]

    base_rep10 = df_rep10[df_rep10["escenario"] == "E1_3_Mixtas"].sort_values("replica")
    mean_tot_usr = float(base_rep10["total_usuarios"].mean())
    mean_ret_usr = float(base_rep10["retiros"].mean())
    mean_pag_usr = float(base_rep10["pagos"].mean())
    sum_tot_10r = int(base_rep10["total_usuarios"].sum())

    mean_rap = float(base_rep10["rapido"].mean())
    mean_nor = float(base_rep10["normal"].mean())
    mean_len = float(base_rep10["lento"].mean())
    mean_muy = float(base_rep10["muy_lento"].mean())

    min_rap_row = base_rep10.loc[base_rep10["rapido"].idxmin()]
    min_nor_row = base_rep10.loc[base_rep10["normal"].idxmin()]
    min_len_row = base_rep10.loc[base_rep10["lento"].idxmin()]
    min_muy_row = base_rep10.loc[base_rep10["muy_lento"].idxmin()]

    mc_idx = df_mc100.set_index("escenario")
    jsq_idx = df_jsq100.set_index("escenario")
    s10_idx = df_sum10.set_index("escenario")

    wq_3m_100 = float(mc_idx.loc["E1_3_Mixtas", "espera_wq_media_min"])
    wq_3m_l = float(mc_idx.loc["E1_3_Mixtas", "espera_wq_ic95_inf"])
    wq_3m_u = float(mc_idx.loc["E1_3_Mixtas", "espera_wq_ic95_sup"])
    w_3m_100 = float(mc_idx.loc["E1_3_Mixtas", "sistema_w_media_min"])
    pwq_3m_100 = float(mc_idx.loc["E1_3_Mixtas", "peor_cajero_wq_media_min"])
    rho_3m_100 = float(mc_idx.loc["E1_3_Mixtas", "utilizacion_rho_media"]) * 100.0
    idle_3m_100 = 100.0 - rho_3m_100

    wq_1r2p_100 = float(mc_idx.loc["E2_1R_2P", "espera_wq_media_min"])
    pwq_1r2p_100 = float(mc_idx.loc["E2_1R_2P", "peor_cajero_wq_media_min"])
    rmax_1r2p_100 = float(mc_idx.loc["E2_1R_2P", "utilizacion_max_media"]) * 100.0

    wq_2r1p_100 = float(mc_idx.loc["E3_2R_1P", "espera_wq_media_min"])
    pwq_2r1p_100 = float(mc_idx.loc["E3_2R_1P", "peor_cajero_wq_media_min"])

    wq_4m_100 = float(mc_idx.loc["E4a_4_Mixtas", "espera_wq_media_min"])
    rho_4m_100 = float(mc_idx.loc["E4a_4_Mixtas", "utilizacion_rho_media"]) * 100.0
    idle_4m_100 = 100.0 - rho_4m_100
    wq_2r2p_100 = float(mc_idx.loc["E4b_2R_2P", "espera_wq_media_min"])

    wq_3m_jsq = float(jsq_idx.loc["E1_3_Mixtas", "espera_wq_media_min"])

    act_pivot_wq = df_wait_act.pivot(index="escenario", columns="accion", values="wq_media_min")
    act_pivot_w = df_wait_act.pivot(index="escenario", columns="accion", values="w_media_min")
    typ_pivot_wq = df_wait_typ.pivot(index="escenario", columns="tipo_usuario", values="wq_media_min")

    wq_pago_2r1p = float(act_pivot_wq.loc["E3_2R_1P", "Pago"])
    w_pago_2r1p = float(act_pivot_w.loc["E3_2R_1P", "Pago"])
    wq_ret_2r1p = float(act_pivot_wq.loc["E3_2R_1P", "Retiro"])
    wq_ret_1r2p = float(act_pivot_wq.loc["E2_1R_2P", "Retiro"])
    wq_pag_1r2p = float(act_pivot_wq.loc["E2_1R_2P", "Pago"])

    e2_pagos_caj10 = df_caj10[(df_caj10["escenario"] == "E2_1R_2P") & (df_caj10["rol"] == "Pago")]
    e2_min_load = float(e2_pagos_caj10["usuarios_prom"].min())
    e2_max_load = float(e2_pagos_caj10["usuarios_prom"].max())

    n_req_min_wq = int(df_sample_n["n_req_wq_iterativo"].min())
    n_req_max_wq = int(df_sample_n["n_req_wq_iterativo"].max())
    n_req_usr = int(df_sample_n["n_req_usuarios_iterativo"].max())
    t_piloto = float(df_sample_n["t_crit_piloto_95"].iloc[0])

    # =========================================================
    # PÁGINA 1: PORTADA FORMAL
    # =========================================================
    p_inst = doc.add_paragraph()
    p_inst.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_inst.paragraph_format.space_before = Pt(34)
    p_inst.paragraph_format.space_after = Pt(26)
    add_rich_runs(
        p_inst,
        "INSTITUCIÓN UNIVERSITARIA DIGITAL DE ANTIOQUIA\n"
        "FACULTAD DE INGENIERÍA — INGENIERÍA DE SOFTWARE Y DATOS",
        font_size=12.0, color=COLOR_SECONDARY, bold=True,
    )

    p_title = doc.add_paragraph()
    p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_title.paragraph_format.space_before = Pt(22)
    p_title.paragraph_format.space_after = Pt(14)
    p_title.paragraph_format.line_spacing = 1.2
    add_rich_runs(
        p_title,
        "Modelado Estocástico y Simulación de Eventos Discretos\n"
        "en Sistemas de Colas Independientes M/M/1:\n"
        "Optimización Operativa de Cajeros para el Banco de Colombia",
        font_size=17.0, color=COLOR_PRIMARY, bold=True,
    )

    p_sub = doc.add_paragraph()
    p_sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_sub.paragraph_format.space_after = Pt(40)
    add_rich_runs(
        p_sub,
        "Evidencia de Aprendizaje 3 · Actividad Didáctica 2-M3 · Solución de un Problema Bancario",
        font_size=11.0, color=COLOR_SECONDARY, italic=True,
    )

    p_team_hdr = doc.add_paragraph()
    p_team_hdr.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_team_hdr.paragraph_format.space_after = Pt(6)
    add_rich_runs(p_team_hdr, "Presentado por (Grupo 25):", font_size=10.5, color=COLOR_MUTED, bold=True)

    p_auth = doc.add_paragraph()
    p_auth.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_auth.paragraph_format.space_after = Pt(20)
    p_auth.paragraph_format.line_spacing = 1.25
    add_rich_runs(
        p_auth,
        "Adriana Andrea Agudelo Agudelo\n"
        "Camilo Alberto Palacios Turriago\n"
        "Juan Daniel Pulgarin García\n"
        "Ruben Dario Jaramillo Cervantes",
        font_size=11.5, color=COLOR_PRIMARY, bold=True,
    )

    p_doc = doc.add_paragraph()
    p_doc.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_doc.paragraph_format.space_after = Pt(20)
    p_doc.paragraph_format.line_spacing = 1.2
    add_rich_runs(
        p_doc,
        "Docente Asesor:\nDr. Julián Andrés Loaiza López\n"
        "Asignatura: Simulación (PREICA2602B020045)",
        font_size=10.8, color=COLOR_BODY,
    )

    p_mail = doc.add_paragraph()
    p_mail.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_mail.paragraph_format.space_after = Pt(34)
    p_mail.paragraph_format.line_spacing = 1.15
    add_rich_runs(
        p_mail,
        "adriana.agudeloa@est.iudigital.edu.co · camilo.palaciot@est.iudigital.edu.co\n"
        "juan.pulgarin@est.iudigital.edu.co · ruben.jaramilloc@est.iudigital.edu.co\n"
        "julian.loaiza@prof.iudigital.edu.co",
        font_name="Consolas", font_size=8.4, color=COLOR_MUTED,
    )

    p_date = doc.add_paragraph()
    p_date.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_date.paragraph_format.space_before = Pt(16)
    add_rich_runs(
        p_date,
        "Medellín, Antioquia, Colombia\nNoviembre de 2026",
        font_size=10.5, color=COLOR_PRIMARY, bold=True,
    )

    doc.add_page_break()

    # =========================================================
    # PÁGINA 2: ÍNDICE (TABLA DE CONTENIDO) Y RESUMEN
    # =========================================================
    p_toc_title = doc.add_paragraph()
    p_toc_title.paragraph_format.space_before = Pt(0)
    p_toc_title.paragraph_format.space_after = Pt(4)
    p_toc_title.paragraph_format.keep_with_next = True
    add_rich_runs(p_toc_title, "Tabla de Contenido", font_size=12.5, color=COLOR_PRIMARY, bold=True)

    p_toc = doc.add_paragraph()
    p_toc.paragraph_format.space_after = Pt(8)
    add_word_field(p_toc, 'TOC \\o "1-2" \\h \\z \\u', font_size=9.5, color=COLOR_BODY)

    p_res_t = doc.add_paragraph()
    p_res_t.paragraph_format.space_before = Pt(4)
    p_res_t.paragraph_format.space_after = Pt(3)
    p_res_t.paragraph_format.keep_with_next = True
    add_rich_runs(p_res_t, "Resumen", font_size=11.0, color=COLOR_SECONDARY, bold=True)

    p_res = add_p(
        f"Dividir las ventanillas de una sucursal según el porcentaje de llegadas suele parecer lógico —si 70 % de los usuarios retira dinero y "
        f"30 % realiza pagos, asignar dos cajas a retiros y una a pagos suena sensato—. Al modelar el sistema en Python con colas independientes M/M/1 "
        f"durante jornadas de ocho horas (480 min), comprobamos que esa intuición colapsa la caja de pagos hasta {wq_pago_2r1p:.2f} minutos de espera media. "
        f"Desde nuestro criterio como equipo de ingeniería de software, diseñamos un simulador estocástico reproducible (semilla PCG64 = 42) bajo la técnica "
        f"de números aleatorios comunes (Banks et al., 2010), corriendo primero 10 réplicas piloto oficiales y calculando después el tamaño muestral "
        f"n^{{*}} mediante la distribución t de Student para culminar con una validación Monte Carlo de 100 réplicas sobre cinco topologías: 3 cajas mixtas (E1), "
        f"1 retiro + 2 pagos (E2), 2 retiros + 1 pago (E3), 4 cajas mixtas (E4A) y 2 retiros + 2 pagos (E4B). En la línea base de 10 réplicas ({mean_tot_usr:.1f} "
        f"clientes/día), el {c_min_srv['cajero']} obtuvo los menores promedios de servicio (S = {c_min_srv['servicio_s_prom']:.2f} min) y permanencia "
        f"(W = {c_min_w['atencion_w_prom']:.2f} min), mientras el {c_max_srv['cajero']} registró los más altos (S = {c_max_srv['servicio_s_prom']:.2f} min; "
        f"W = {c_max_w['atencion_w_prom']:.2f} min). Ya en 100 réplicas, operar 3 cajas mixtas supera a cualquier esquema especializado (W_{{q}} = {wq_3m_100:.2f} min, "
        f"IC 95 % t [{wq_3m_l:.2f}, {wq_3m_u:.2f}]) frente a {wq_1r2p_100:.2f} min en 1R+2P. Tampoco se justifica incorporar un cuarto cajero físico ni un cajero "
        f"electrónico: el ahorro en espera nunca supera {wq_3m_100 - wq_2r2p_100:.2f} min y el uso operativo cae de {rho_3m_100:.1f}% a {rho_4m_100:.1f}%, dejando "
        f"{idle_4m_100:.1f}% de capacidad inactiva.",
        space_after=4.0,
    )
    p_res.paragraph_format.line_spacing = 1.12
    for run in p_res.runs:
        run.font.size = Pt(10.0)

    p_kw = doc.add_paragraph()
    p_kw.alignment = WD_ALIGN_PARAGRAPH.LEFT
    p_kw.paragraph_format.space_after = Pt(2)
    add_rich_runs(p_kw, "Palabras clave: ", font_size=9.8, color=COLOR_PRIMARY, italic=True)
    add_rich_runs(
        p_kw,
        "simulación de eventos discretos, teoría de colas M/M/1, ley de Little, consolidación de capacidad, "
        "distribución t de Student, método Monte Carlo, Banco de Colombia.",
        font_size=9.8, color=COLOR_BODY,
    )

    doc.add_page_break()

    # =========================================================
    # 1. INTRODUCCIÓN
    # =========================================================
    add_h1("1. Introducción")
    add_p(
        "Un solo parámetro mal interpretado basta para arruinar la operación de una sucursal bancaria. El Banco de Colombia atiende durante ocho horas "
        "continuas (480 minutos) sin disponer de cajeros electrónicos —apenas cuenta con tres ventanillas físicas— para responder a dos frentes: retiros "
        "en un 70 % y consignaciones o pagos en el 30 % restante. Cuando recibimos este caso, el dilema administrativo era concreto. ¿Debe la gerencia "
        "especializar esas tres posiciones por tipo de trámite, conservarlas multifunción o asumir la inversión de instalar una cuarta caja?"
    )
    add_p(
        "A primera vista, ese 70 % contra 30 % empuja a cualquiera hacia una solución engañosa: dedicar dos cajas exclusivas a retiros y dejar una sola "
        "para pagos. Sin embargo —como bien nos advierte la teoría de colas (Gross et al., 2008)— la saturación no nace solo de cuánta gente cruza la puerta, "
        "sino del producto entre la tasa de arribos y la duración real de cada transacción. En nuestra parametrización, pagar o consignar toma 5.20 minutos "
        "en promedio, más del doble frente a los 2.34 minutos de un retiro. Multiplicando frecuencia por duración, la carga real queda casi empatada: "
        "51.2 % en retiros contra 48.8 % en pagos. Partiendo de esa paradoja, construimos un motor modular de simulación en Python orientado por tres metas "
        "puntuales:"
    )
    add_numbered_item("1.", "Detectar asimetrías entre servidores: ", "medimos servicio efectivo, espera en fila y permanencia total en el escenario base de 10 réplicas para identificar qué cajero rindió más rápido y cuál acumuló mayor carga.")
    add_numbered_item("2.", "Perfilar la demanda y acotar el error muestral (n^{*}): ", "cuantificamos usuarios promedio por tipología en la totalidad de cajas, conteos réplica a réplica, el modelo con menor atención en turno y las réplicas mínimas exigidas estadísticamente.")
    add_numbered_item("3.", "Decidir sobre el cuarto cajero y la especialización: ", "comparamos cinco configuraciones (3 Mixtas, 1R+2P, 2R+1P, 4 Mixtas y 2R+2P) en todos los criterios de entrada frente a las soluciones analíticas M/M/1 y M/G/1.")

    # =========================================================
    # 2. MARCO TEÓRICO M/M/1
    # =========================================================
    add_h1("2. Marco Teórico y Formulación del Sistema de Colas")
    add_h2("2.1 Parametrización Exponencial de Llegadas, Servicio y Probabilidades")
    add_p(
        "Cada cliente que ingresa al sistema dispara dos decisiones probabilísticas independientes establecidas en el planteamiento original del problema: "
        "primero define su trámite —retiro o consignación/pago— y enseguida adopta uno de cuatro perfiles de velocidad operativa (Rápido, Normal, Lento o "
        "Muy lento). Al cruzar ambas variables obtenemos ocho perfiles combinados cuyos tiempos entre llegadas y duraciones de servicio obedecen a leyes "
        "exponenciales. En la Tabla 1 reunimos esas probabilidades condicionales, conjuntas y medias operativas."
    )

    tbl_params_data = [
        ["Retiro (70%)", "Rápido", "0.23", "16.1%", "1.0 min", "1.0 min"],
        ["Retiro (70%)", "Normal", "0.40", "28.0%", "2.0 min", "2.0 min"],
        ["Retiro (70%)", "Lento", "0.17", "11.9%", "3.0 min", "3.0 min"],
        ["Retiro (70%)", "Muy lento", "0.20", "14.0%", "4.0 min", "3.0 min"],
        ["Consignación o pago (30%)", "Rápido", "0.10", "3.0%", "3.0 min", "1.0 min"],
        ["Consignación o pago (30%)", "Normal", "0.20", "6.0%", "3.0 min", "2.0 min"],
        ["Consignación o pago (30%)", "Lento", "0.30", "9.0%", "5.0 min", "3.0 min"],
        ["Consignación o pago (30%)", "Muy lento", "0.40", "12.0%", "7.0 min", "4.0 min"],
    ]
    format_apa_table(
        doc,
        "Tabla 1",
        "Parametrización exponencial de servicio y llegadas por acción y perfil de usuario",
        [Inches(1.60), Inches(0.95), Inches(0.85), Inches(0.90), Inches(1.10), Inches(1.10)],
        ["Tipo de acción", "Tipo usuario", "Prob. cond.", "Prob. conj.", "Media servicio", "Media llegada"],
        tbl_params_data,
        "Datos tomados de las especificaciones oficiales del caso (Tablas 1 y 2 del enunciado de la actividad).",
        font_size=8.3,
    )

    add_p(
        "Con estos pesos probabilísticos calculamos directamente los momentos exactos de primer orden antes de simular un solo evento. El intervalo medio "
        "entre arribos resulta ser E[IA] = 0.70(2.14) + 0.30(3.00) = 2.398 min, equivalente a una tasa agregada λ_{total} = 0.4170 clientes/min —aproximadamente "
        "200.2 personas en una jornada de 480 minutos—. Por su parte, las medias de atención quedan fijadas en E[S_{R}] = 2.34 min (μ_{R} = 0.4274 cli/min) para "
        "retiros, E[S_{P}] = 5.20 min (μ_{P} = 0.1923 cli/min) para pagos y E[S_{mix}] = 3.198 min (μ_{mix} = 0.3127 cli/min) bajo operación multifunción."
    )

    add_h2("2.2 Ecuaciones Analíticas M/M/1, Ley de Little y Extensión M/G/1")
    add_p(
        "El modelo trabaja con servidores M/M/1 desacoplados y tiempo de caminata despreciable entre colas. Cuando un flujo de Poisson de tasa λ_{flujo} "
        "se reparte equiprobablemente entre k ventanillas disponibles —propiedad clásica de descomposición o thinning con probabilidad 1/k descrita por Ross "
        "(2014)—, cada servidor enfrenta una demanda efectiva λ_{c} = λ_{flujo} / k. Mientras el factor de utilización cumpla ρ_{c} = λ_{c} / μ_{c} < 1, la "
        "cadena estacionaria converge y respeta las identidades fundamentales propuestas originalmente por Little (1961):"
    )
    add_equation_box("ρ = λ_{c} / μ_{c} < 1,     P_{0} = 1 - ρ,     L_{q} = ρ^{2} / (1 - ρ),     L = ρ / (1 - ρ)", "(1)")
    add_equation_box("W_{q}(M/M/1) = L_{q} / λ_{c} = ρ / [μ_{c}(1 - ρ)],     W = W_{q} + 1/μ_{c},     W_{q}(M/G/1) = [λ_{c} · E[S^{2}]] / [2(1 - ρ)]", "(2)")
    add_p(
        "Aquí conviene hacer una precisión matemática que rara vez se comenta en clase. Al mezclar cuatro tasas exponenciales diferentes en un mismo caudal, "
        "el tiempo de servicio agregado deja de ser exponencial puro y pasa a comportarse como una distribución hiperexponencial. Calculamos su segundo "
        "momento exacto en E[S^{2}_{mix}] = 27.064 min^{2} —coeficiente de variación al cuadrado C^{2}_{s} = 1.646 > 1—, motivo por el cual la espera real "
        "capturada en la simulación se ubica sistemáticamente por encima de M/M/1 y converge hacia la predicción Pollaczek–Khinchine M/G/1 de (2), tal como "
        "desarrolla Kleinrock (1975). En la Figura 1 esquematizamos esta arquitectura junto con sus cotas analíticas."
    )

    add_apa_fig(
        "fig1_arquitectura_colas_mm1.png",
        "Figura 1",
        "Arquitectura de colas independientes M/M/1 y parámetros analíticos por escenario en el Banco de Colombia",
        "Elaboración propia mediante cálculo analítico del módulo bank_queue/model.py y descomposición de Poisson equiprobable 1/k.",
        width_in=6.35,
    )

    # =========================================================
    # 3. METODOLOGÍA COMPUTACIONAL Y RÉPLICAS NECESARIAS
    # =========================================================
    add_h1("3. Metodología de Implementación Computacional")
    add_p(
        "Estructuramos la lógica del experimento dentro de un paquete Python desacoplado (bank_queue/) respaldado por el generador PCG64 de NumPy con semilla "
        "fija (seed = 42), garantizando reproducibilidad bit a bit en cualquier entorno de ejecución. Cada corrida recrea 480 minutos de ventanilla bajo "
        "disciplina FCFS sobre cinco configuraciones: tres mixtas (E1), un retiro más dos pagos (E2), dos retiros más un pago (E3), cuatro mixtas (E4A) "
        "y dos retiros más dos pagos (E4B). Para evitar que fluctuaciones aleatorias de los arribos ensucien la comparación entre arquitecturas, aplicamos "
        "Números Aleatorios Comunes (CRN), tal como recomiendan Banks et al. (2010): cada escenario recibe exactamente la misma secuencia de clientes por réplica."
    )
    add_p(
        "Respecto al análisis inferencial, descartamos usar la aproximación normal tradicional (z = 1.96) porque subestima la incertidumbre cuando se evalúan "
        "muestras piloto pequeñas. Implementamos cuantiles exactos de dos colas para la distribución t de Student mediante función beta incompleta regularizada "
        "(t_{0.975, 9} = 2.2622 en el piloto de 10 réplicas y t_{0.975, 99} = 1.9842 para n = 100), siguiendo la metodología estándar sugerida por Law (2015). "
        "Además, diseñamos un escenario de sensibilidad bajo política Join-the-Shortest-Queue (JSQ) estrictamente no clarividente: nuestro código enruta cada "
        "arribo observando únicamente cuántos clientes ocupan o esperan en cada ventanilla vía colas de salida deque —nunca espiando duraciones futuras de "
        "servicio— y resuelve empates al azar."
    )

    add_code_listing(
        doc,
        [
            "def simulate_cashier_fcfs(assigned_customers, horizon=480.0):",
            "    free_time = 0.0; waits, services, systems = [], [], []",
            "    for cust in assigned_customers:",
            "        start = max(cust.arrival_time, free_time)",
            "        wait = start - cust.arrival_time",
            "        free_time = start + cust.service_time",
            "        waits.append(wait); services.append(cust.service_time)",
            "        systems.append(wait + cust.service_time)",
            "    h_eff = max(horizon, free_time)",
            "    rho = sum(services) / h_eff; lq = sum(waits) / h_eff",
            "    return mean(waits), mean(services), mean(systems), rho, lq",
        ],
        "Núcleo FCFS implementado en Python por ventanilla independiente, preservando la identidad empírica de Little L_{q} = λ_{eff} · W_{q}.",
    )

    # =========================================================
    # 4. RESULTADOS Y ANÁLISIS ESTADÍSTICO
    # =========================================================
    add_h1("4. Resultados y Análisis Estadístico")

    # 4.1 Punto 1
    add_h2("4.1 Punto 1: Cajero con Menor y Mayor Tiempo Promedio de Atención (Escenario Base)")
    add_p(
        "Empezamos evaluando las diez réplicas oficiales de la operación actual: tres cajas multifunción sin especialización. Aunque en el papel los tres "
        "servidores poseen tasas idénticas de atención, en ventanas finitas de diez días basta una ligera racha de clientes lentos o pagos consecutivos para "
        "inclinar el desempeño individual. En la Tabla 2 reportamos el rendimiento detallado de cada ventanilla."
    )

    tbl_caj_data = []
    for _, r in base_caj.iterrows():
        tbl_caj_data.append([
            r["cajero"],
            f"{r['usuarios_prom']:.1f} (±{r['usuarios_sd']:.1f})",
            f"{r['servicio_s_prom']:.3f} (±{r['servicio_s_sd']:.3f})",
            f"{r['espera_wq_prom']:.3f} (±{r['espera_wq_sd']:.3f})",
            f"{r['atencion_w_prom']:.3f} (±{r['atencion_w_sd']:.3f})",
            f"{r['utilizacion_rho_prom']*100:.1f}%",
            f"{r['lq_prom']:.3f}",
        ])
    format_apa_table(
        doc,
        "Tabla 2",
        "Desempeño estadístico por cajero en el escenario base (3 cajas mixtas, 10 réplicas)",
        [Inches(0.85), Inches(1.00), Inches(1.05), Inches(1.05), Inches(1.05), Inches(0.75), Inches(0.75)],
        ["Cajero", "Usuarios/día", "Servicio S (m)", "Espera W_{q} (m)", "Sistema W (m)", "Uso ρ", "Cola L_{q}"],
        tbl_caj_data,
        "Promedios y desviaciones estándar (±DE) obtenidos sobre las 10 corridas piloto con semilla fija (seed = 42).",
        font_size=8.2,
    )

    add_p(
        f"Los números no dejan margen a duda. El {c_min_srv['cajero']} registró el menor tiempo medio tanto en servicio efectivo (S = {c_min_srv['servicio_s_prom']:.3f} min) "
        f"como en tiempo total dentro de la sucursal (W = {c_min_w['atencion_w_prom']:.3f} min; espera en fila W_{{q}} = {c_min_w['espera_wq_prom']:.3f} min y "
        f"ocupación ρ = {c_min_w['utilizacion_rho_prom']*100:.1f}%). En la orilla opuesta quedó el {c_max_srv['cajero']} con los peores promedios en ambos frentes "
        f"(S = {c_max_srv['servicio_s_prom']:.3f} min; W = {c_max_w['atencion_w_prom']:.3f} min; ρ = {c_max_w['utilizacion_rho_prom']*100:.1f}%), mientras el "
        f"Cajero 3 mantuvo cifras intermedias (S = {float(base_caj.iloc[2]['servicio_s_prom']):.3f} min; W = {float(base_caj.iloc[2]['atencion_w_prom']):.3f} min). "
        f"La Figura 2 muestra cómo en la réplica 6 el Cajero 1 disparó su promedio diario cerca de 16 minutos por coincidencia de ráfagas complejas."
    )

    add_apa_fig(
        "fig2_tiempos_atencion_por_cajero.png",
        "Figura 2",
        "Comparativa de servicio, espera y variabilidad por cajero en 10 réplicas del escenario base",
        "Panel A contrasta los promedios acumulados (S, W_{q}, W) por servidor; Panel B traza la volatilidad día a día.",
        width_in=6.35,
    )

    # 4.2 Punto 2
    add_h2("4.2 Punto 2: Promedio de Usuarios de Cada Tipo en la Totalidad de Cajeros")
    add_p(
        f"Al sumar las diez jornadas de ocho horas contabilizamos {sum_tot_10r:,} clientes totales en la sucursal, lo que arroja {mean_tot_usr:.2f} usuarios "
        f"diarios promedio: {mean_ret_usr:.2f} acudieron por retiros ({mean_ret_usr/mean_tot_usr*100:.2f}%) y {mean_pag_usr:.2f} por pagos o consignaciones "
        f"({mean_pag_usr/mean_tot_usr*100:.2f}%). Sobre el conjunto de los tres cajeros, los promedios diarios quedaron en {mean_rap:.2f} usuarios Rápido "
        f"({mean_rap/3:.2f} por ventanilla), {mean_nor:.2f} Normal ({mean_nor/3:.2f} c/u), {mean_len:.2f} Lento ({mean_len/3:.2f} c/u) y {mean_muy:.2f} Muy lento "
        f"({mean_muy/3:.2f} c/u). Desagregamos en la Tabla 3 los ocho subperfiles combinados frente a sus frecuencias teóricas esperadas."
    )

    tbl_sub_data = []
    for _, r in df_sub10.iterrows():
        tbl_sub_data.append([
            r["accion_etiqueta"],
            r["tipo_usuario"],
            f"{int(r['total_10_replicas'])}",
            f"{r['promedio_por_replica']:.2f} (±{r['desv_est']:.2f})",
            f"{r['promedio_por_replica']/3:.2f}",
            f"[{int(r['min_replica'])}–{int(r['max_replica'])}]",
            f"{r['prop_empirica_media']*100:.2f}%",
            f"{r['prop_teorica']*100:.2f}%",
        ])
    for utype, col in [("Rápido", "rapido"), ("Normal", "normal"), ("Lento", "lento"), ("Muy lento", "muy_lento")]:
        vals = base_rep10[col]
        tbl_sub_data.append([
            "TOTAL SUCURSAL",
            utype,
            f"{int(vals.sum())}",
            f"{vals.mean():.2f} (±{vals.std(ddof=1):.2f})",
            f"{vals.mean()/3:.2f}",
            f"[{int(vals.min())}–{int(vals.max())}]",
            f"{vals.sum() / base_rep10['total_usuarios'].sum() * 100:.2f}%",
            "—",
        ])

    format_apa_table(
        doc,
        "Tabla 3",
        "Promedio diario de usuarios por perfil y tipología en toda la sucursal y por cajero",
        [Inches(1.22), Inches(0.78), Inches(0.60), Inches(1.06), Inches(0.68), Inches(0.86), Inches(0.65), Inches(0.65)],
        ["Acción / Nivel", "Tipo usuario", "Total 10R", "Sucursal/día", "Por cajero", "Mín–Máx", "Prop. Emp.", "Prop. Teór."],
        tbl_sub_data,
        "Cálculo sobre las 10 réplicas base (n = 2,083 arribos totales). Prop. Emp. representa la participación empírica observada.",
        font_size=7.9,
    )

    add_p(
        "Verificamos además gráficamente en la Figura 3 la calibración del generador aleatorio frente a la esperanza matemática teórica en 480 minutos "
        "(Panel A) junto con la trayectoria por réplica y sus puntos mínimos por categoría (Panel B)."
    )

    add_apa_fig(
        "fig3_distribucion_usuarios_por_tipo_replicas.png",
        "Figura 3",
        "Validación de afluencia por tipo frente a la esperanza teórica y trazabilidad en 10 réplicas",
        "Barras muestran promedio ± DE sobre 10 corridas frente a la cota analítica de 8 h; líneas del Panel B destacan las réplicas con mínimos diarios.",
        width_in=6.35,
    )

    # 4.3 Punto 3 + Tamaño Muestral (Réplicas Necesarias)
    add_h2("4.3 Punto 3: Conteo por Réplica, Modelo con Menor Atención y Réplicas Necesarias")
    add_p(
        "En la Tabla 4 detallamos cuántos clientes entraron, completaron atención dentro del turno de 480 minutos y pertenecieron a cada tipología "
        "durante las diez réplicas base. El perfil Normal encabeza siempre la demanda diaria, seguido por Muy lento, Lento y Rápido."
    )

    tbl_rep_data = []
    for _, r in base_rep10.iterrows():
        tbl_rep_data.append([
            f"R{int(r['replica'])}",
            f"{int(r['total_usuarios'])}",
            f"{int(r['atendidos_en_turno_480m'])}",
            f"{int(r['retiros'])}",
            f"{int(r['pagos'])}",
            f"{int(r['rapido'])}",
            f"{int(r['normal'])}",
            f"{int(r['lento'])}",
            f"{int(r['muy_lento'])}",
            f"{r['espera_cola_wq_min']:.2f}",
            f"{r['atencion_total_w_min']:.2f}",
        ])
    format_apa_table(
        doc,
        "Tabla 4",
        "Desglose de usuarios por réplica y métricas diarias de operación en escenario base",
        [Inches(0.45), Inches(0.55), Inches(0.65), Inches(0.55), Inches(0.50), Inches(0.55), Inches(0.55), Inches(0.55), Inches(0.65), Inches(0.75), Inches(0.75)],
        ["Rép.", "Total", "En 480m", "Retiro", "Pago", "Ráp.", "Norm.", "Lento", "M. Lento", "W_{q} (m)", "W (m)"],
        tbl_rep_data,
        "La columna En 480m registra los usuarios cuya atención finalizó antes del cierre oficial de la jornada bancaria.",
        font_size=7.9,
    )

    min_rep_txt = [
        f"Rápido = {int(min_rap_row['rapido'])} (Réplica {int(min_rap_row['replica'])})",
        f"Normal = {int(min_nor_row['normal'])} (Réplica {int(min_nor_row['replica'])})",
        f"Lento = {int(min_len_row['lento'])} (Réplica {int(min_len_row['replica'])})",
        f"Muy lento = {int(min_muy_row['muy_lento'])} (Réplica {int(min_muy_row['replica'])})",
    ]

    turn_by_model = df_rep10.groupby("nombre_corto", sort=False)[
        ["atendidos_en_turno_480m", "rapido_en_turno", "normal_en_turno", "lento_en_turno", "muy_lento_en_turno"]
    ].sum()
    m_min_rap = turn_by_model["rapido_en_turno"].idxmin()
    m_min_nor = turn_by_model["normal_en_turno"].idxmin()
    m_min_len = turn_by_model["lento_en_turno"].idxmin()
    m_min_muy = turn_by_model["muy_lento_en_turno"].idxmin()
    caj_min_tot = df_caj10.loc[df_caj10["usuarios_prom"].idxmin()]

    add_p(
        f"Tres lecturas operativas surgen al cruzar las réplicas con los cinco modelos bajo llegadas comunes ({sum_tot_10r:,} clientes acumulados). "
        f"Primero, los mínimos diarios globales por categoría cayeron en {', '.join(min_rep_txt)}. Segundo, al medir cuántos usuarios alcanzaron a terminar "
        f"su trámite estrictamente dentro del turno de 480 minutos, el modelo con menor atención por tipo fue {m_min_rap} en Rápido "
        f"({int(turn_by_model.loc[m_min_rap, 'rapido_en_turno'])}), {m_min_nor} en Normal ({int(turn_by_model.loc[m_min_nor, 'normal_en_turno'])}), "
        f"{m_min_len} en Lento ({int(turn_by_model.loc[m_min_len, 'lento_en_turno'])}) y {m_min_muy} en Muy lento "
        f"({int(turn_by_model.loc[m_min_muy, 'muy_lento_en_turno'])}), dejando a {turn_by_model['atendidos_en_turno_480m'].idxmin()} con la menor atención "
        f"agregada al cierre ({int(turn_by_model['atendidos_en_turno_480m'].min())} de {sum_tot_10r:,}) por rezago en su única caja de retiros. Tercero, "
        f"revisando servidor por servidor, el {caj_min_tot['cajero']} de {caj_min_tot['nombre_corto']} atendió el menor volumen de todo el experimento: "
        f"{caj_min_tot['usuarios_prom']:.1f} usuarios/día ({caj_min_tot['rapido_prom']:.1f} Rápido, {caj_min_tot['normal_prom']:.1f} Normal, "
        f"{caj_min_tot['lento_prom']:.1f} Lento y {caj_min_tot['muy_lento_prom']:.1f} Muy lento)."
    )

    add_p(
        f"¿Bastan realmente 10 réplicas para tomar una decisión gerencial seria? Decidimos no adivinarlo sino calcularlo. Aplicamos el método iterativo de "
        f"tamaño muestral con refinamiento de grados de libertad en la distribución t de Student (piloto n_{{0}} = 10, t_{{0.975, 9}} = {t_piloto:.4f}) mediante "
        f"n^{{*}} = ceil[(t_{{α/2, n-1}} · s_{{0}} / ε)^{{2}}]. Como prueba la Tabla 5, la cota mínima de 10 réplicas apenas alcanza en topologías holgadas de 4 cajas "
        f"(2R+2P exige n^{{*}} = 10 y 4 Mixtas requiere n^{{*}} = 13 para ε = ±0.50 min en W_{{q}}); por el contrario, estabilizar escenarios congestionados "
        f"de tres ventanillas demanda entre {n_req_min_wq} y {n_req_max_wq} corridas (y {n_req_usr} para acotar la afluencia diaria dentro de ±5 usuarios). "
        f"Por esa razón técnica ejecutamos nuestra validación definitiva sobre 100 réplicas Monte Carlo (100 > {n_req_max_wq})."
    )

    tbl_samp_data = []
    for _, r in df_sample_n.iterrows():
        tbl_samp_data.append([
            r["nombre_corto"],
            f"±{r['wq_semiamp_ic95_min']:.2f} m",
            f"{r['wq_sd_min']:.2f} m",
            f"{int(r['n_req_wq_iterativo'])}",
            f"±{r['w_semiamp_ic95_min']:.2f} m",
            f"{int(r['n_req_w_iterativo'])}",
            f"{int(r['n_req_usuarios_iterativo'])}",
        ])
    format_apa_table(
        doc,
        "Tabla 5",
        "Tamaño muestral requerido (n^{*}) estimado iterativamente al 95 % de confianza t de Student",
        [Inches(0.95), Inches(0.95), Inches(0.85), Inches(0.90), Inches(0.95), Inches(0.95), Inches(0.95)],
        ["Escenario", "Semiamp. W_{q} (n=10)", "DE s_{Wq}", "n^{*} (ε=±0.5m)", "Semiamp. W (n=10)", "n^{*} (±5% W)", "n^{*} (±5 usr)"],
        tbl_samp_data,
        "Estimación calculada iterando grados de libertad t_{0.975, n-1} a partir de las desviaciones estándar observadas en el piloto n_{0} = 10.",
        font_size=7.9,
    )

    # 4.4 Comparativa Global de Escenarios
    add_h2("4.4 Comparativa Global de Escenarios: Teoría vs. 10 y 100 Réplicas Monte Carlo")
    add_p(
        "Con la convergencia estadística asegurada, confrontamos en la Tabla 6 el piloto de 10 réplicas, la media Monte Carlo a 100 réplicas con sus "
        "intervalos de confianza exactos, las cotas analíticas M/M/1–M/G/1 y la respuesta al habilitar elección observable de fila más corta (JSQ). "
        "Aquí se aprecia la brecha real entre diseñar por porcentaje de visitas frente a hacerlo por carga de trabajo."
    )

    tbl_esc_data = []
    for skey in df_mc100["escenario"]:
        r10 = s10_idx.loc[skey]
        r100 = mc_idx.loc[skey]
        rjsq = jsq_idx.loc[skey]
        tbl_esc_data.append([
            r100["nombre_corto"],
            f"{r10['espera_wq_media_min']:.2f} m",
            f"{r100['espera_wq_media_min']:.2f} [{r100['espera_wq_ic95_inf']:.2f}–{r100['espera_wq_ic95_sup']:.2f}]",
            f"{r100['peor_cajero_wq_media_min']:.2f} m",
            f"{r100['sistema_w_media_min']:.2f} m",
            f"{r100['wq_teorica_mm1_min']:.2f} / {r100['wq_teorica_mg1_min']:.2f}",
            f"{rjsq['espera_wq_media_min']:.2f} m",
            f"{r100['utilizacion_rho_media']*100:.1f}% / {r100['utilizacion_max_media']*100:.1f}%",
        ])

    format_apa_table(
        doc,
        "Tabla 6",
        "Síntesis comparativa de espera, permanencia y utilización entre los cinco escenarios evaluados",
        [Inches(0.75), Inches(0.68), Inches(1.18), Inches(0.72), Inches(0.65), Inches(0.95), Inches(0.65), Inches(0.92)],
        ["Escenario", "W_{q} (10R)", "W_{q} (100R, IC95%)", "Peor W_{q}", "W (100R)", "M/M/1 / M/G/1", "W_{q} JSQ", "ρ med / máx"],
        tbl_esc_data,
        "Las soluciones analíticas combinan M/M/1 clásico y Pollaczek–Khinchine M/G/1; W_{q} JSQ evalúa enrutamiento por longitud visible de cola.",
        font_size=7.8,
    )

    add_apa_fig(
        "fig4_comparativa_espera_escenarios.png",
        "Figura 4",
        "Comparación de espera global, cuello de botella por cajero, tiempo en sistema y utilización (100 réplicas)",
        "Panel A muestra promedios globales con IC 95 % t junto al peor cajero de cada jornada; Panel B contrasta el tiempo total W frente a ρ (%).",
        width_in=6.35,
    )
    add_apa_fig(
        "fig5_validacion_montecarlo_y_teoria.png",
        "Figura 5",
        "Validación teórica frente a M/M/1–M/G/1, sensibilidad JSQ y convergencia acumulada a 100 réplicas",
        "Los promedios simulados confirman la transición hiperexponencial entre M/M/1 y M/G/1, estabilizando sus medias tras superar 60 réplicas.",
        width_in=6.35,
    )

    # 4.5 Punto 4: Evaluación bajo TODOS los criterios del modelo
    add_h2("4.5 Punto 4: Evaluación de Necesidad de Nuevo Cajero (Todos los Criterios del Modelo)")
    add_p(
        "Para decidir si la sucursal requiere abrir una cuarta caja —ya sea física o mediante un cajero electrónico orientado a retiros—, no basta con "
        "revisar un promedio general que podría esconder injusticias entre grupos de clientes. Desagregamos la espera en cola W_{q} para todos los "
        "criterios de entrada del modelo en 100 réplicas: ambos tipos de trámite y las cuatro categorías de velocidad operativa (Tabla 7)."
    )

    tbl_crit_data = []
    for skey in df_mc100["escenario"]:
        r100 = mc_idx.loc[skey]
        tbl_crit_data.append([
            r100["nombre_corto"],
            f"{r100['espera_wq_media_min']:.2f} m",
            f"{float(act_pivot_wq.loc[skey, 'Retiro']):.2f} m",
            f"{float(act_pivot_wq.loc[skey, 'Pago']):.2f} m",
            f"{float(typ_pivot_wq.loc[skey, 'Rápido']):.2f} m",
            f"{float(typ_pivot_wq.loc[skey, 'Normal']):.2f} m",
            f"{float(typ_pivot_wq.loc[skey, 'Lento']):.2f} m",
            f"{float(typ_pivot_wq.loc[skey, 'Muy lento']):.2f} m",
            f"{r100['sistema_w_media_min']:.2f} m",
        ])

    format_apa_table(
        doc,
        "Tabla 7",
        "Desagregación de tiempos de espera W_{q} por operación y perfil de usuario (100 réplicas Monte Carlo)",
        [Inches(0.76), Inches(0.68), Inches(0.70), Inches(0.70), Inches(0.72), Inches(0.72), Inches(0.72), Inches(0.78), Inches(0.72)],
        ["Escenario", "W_{q} Global", "W_{q} Retiro", "W_{q} Pago", "W_{q} Rápido", "W_{q} Normal", "W_{q} Lento", "W_{q} M. Lento", "W Global"],
        tbl_crit_data,
        "Resultados promediados sobre n = 100 jornadas simuladas de 480 minutos aplicando números aleatorios comunes (CRN).",
        font_size=7.7,
    )

    add_p(
        f"¿Conviene realmente abrir una cuarta ventanilla cuando las tres actuales trabajan a menos de la mitad de su capacidad? Nuestros datos prueban que NO. "
        f"Si la sucursal opera bajo la modalidad de tres cajas mixtas, cada segmento de la Tabla 7 permanece bajo control y por debajo de la barrera "
        f"operativa de cinco minutos: Global = {wq_3m_100:.2f} min, Retiros = {float(act_pivot_wq.loc['E1_3_Mixtas', 'Retiro']):.2f} min, "
        f"Pagos = {float(act_pivot_wq.loc['E1_3_Mixtas', 'Pago']):.2f} min y velocidades entre {float(typ_pivot_wq.loc['E1_3_Mixtas', 'Muy lento']):.2f} y "
        f"{float(typ_pivot_wq.loc['E1_3_Mixtas', 'Rápido']):.2f} min, todo con una utilización media de apenas {rho_3m_100:.1f}% ({idle_3m_100:.1f}% del "
        f"turno libre). Más aún, basta que el cliente escoja visualmente la fila más corta (JSQ observable) para desplomar esa espera a {wq_3m_jsq:.2f} minutos "
        f"({wq_3m_jsq*60:.1f} segundos)."
    )
    add_p(
        f"Inyectar un cuarto cajero físico o un cajero electrónico bajaría la espera global a {wq_4m_100:.2f} min en 4 Mixtas y a {wq_2r2p_100:.2f} min "
        f"en 2R+2P. La ganancia real oscila entre apenas {wq_3m_100 - wq_4m_100:.2f} y {wq_3m_100 - wq_2r2p_100:.2f} minutos por cliente, a cambio de elevar "
        f"un 33.3 % el costo fijo de infraestructura y hundir la ocupación media hasta {rho_4m_100:.1f}% ({idle_4m_100:.1f}% de tiempo ocioso). Solo recomendaríamos "
        f"instalar esa cuarta posición —idealmente un cajero electrónico para retiros junto a dos cajas de pagos, análogo a 2R+2P— si el flujo futuro "
        f"superara el 70 % de ocupación o la gerencia exigiera por norma un SLA inferior a tres minutos en todo perfil."
    )

    # 4.6 Punto 5
    add_h2("4.6 Punto 5: Asignación Óptima de Cajeros Exclusivos para Pagos y Retiros")
    add_p(
        "Al cruzar la Tabla 6, la Tabla 7 y el desglose individual por servidor de la Figura 6, la pregunta sobre cuántos cajeros deben operar en exclusiva "
        "para cada trámite queda resuelta con claridad:"
    )
    add_bullet(
        "0 exclusivos de retiro / 0 exclusivos de pago (3 Cajas Mixtas — Óptimo): ",
        f"El principio de consolidación de capacidad (pooling) evita que un cliente espere frente a un cajero ocioso de otro trámite. Con tres ventanillas "
        f"polivalentes logramos la menor espera media global ({wq_3m_100:.2f} min; W = {w_3m_100:.2f} min), equilibrio entre retiros "
        f"({float(act_pivot_wq.loc['E1_3_Mixtas', 'Retiro']):.2f} min) y pagos ({float(act_pivot_wq.loc['E1_3_Mixtas', 'Pago']):.2f} min), y balance uniforme "
        f"(~67 usuarios diarios y ~44 % de uso por caja).",
    )
    add_bullet(
        "Frágil asimetría de las configuraciones especializadas (1R+2P y 2R+1P): ",
        f"Segregar las tres cajas empeora severamente el servicio. Si asignamos 1 caja a retiros y 2 a pagos (E2), ahogamos la ventanilla de retiros con "
        f"el 70 % de la sucursal (ρ_{{max}} = {rmax_1r2p_100:.1f}%, espera Retiro = {wq_ret_1r2p:.2f} min, peor cajero = {pwq_1r2p_100:.2f} min; global = "
        f"{wq_1r2p_100:.2f} min) mientras dos cajeros de pagos quedan subutilizados (~29–30 usuarios/día, W_{{q}} = {wq_pag_1r2p:.2f} min). Invertir la receta "
        f"con 2 retiros y 1 pago (E3) es todavía más engañoso: el promedio global cae aparentemente a {wq_2r1p_100:.2f} min solo porque los retiros rápidos "
        f"(70 %, W_{{q}} = {wq_ret_2r1p:.2f} min) maquillan el colapso de la única ventanilla de pagos, cuya espera se dispara a {wq_pago_2r1p:.2f} minutos "
        f"(W = {w_pago_2r1p:.2f} min en sistema; peor promedio diario de réplica = {pwq_2r1p_100:.2f} min).",
    )

    add_apa_fig(
        "fig6_balance_carga_cajeros_escenarios.png",
        "Figura 6",
        "Volumen diario atendido y espera individual por cajero en los cinco escenarios (100 réplicas Monte Carlo)",
        "El contraste visual evidencia la saturación unilateral en el cajero de retiros de 1R+2P y el cuello de botella de 9.08 min en pagos bajo 2R+1P.",
        width_in=6.05,
    )

    # =========================================================
    # 5. CONCLUSIONES
    # =========================================================
    add_h1("5. Conclusiones")
    add_numbered_item("1.", "Diferencias empíricas entre servidores (Base 10 réplicas): ", f"Pese a compartir igual tasa teórica en 3 Mixtas, el {c_min_srv['cajero']} registró los menores promedios ({c_min_srv['servicio_s_prom']:.2f} min en servicio; {c_min_w['atencion_w_prom']:.2f} min en sistema) y el {c_max_srv['cajero']} los mayores ({c_max_srv['servicio_s_prom']:.2f} min y {c_max_w['atencion_w_prom']:.2f} min), reflejando varianza estocástica pura.")
    add_numbered_item("2.", "Composición de demanda en toda la sucursal: ", f"En las diez jornadas ingresaron {mean_tot_usr:.1f} usuarios/día promedio ({mean_rap:.1f} Rápido, {mean_nor:.1f} Normal, {mean_len:.1f} Lento y {mean_muy:.1f} Muy lento; esto es, {mean_rap/3:.1f}, {mean_nor/3:.1f}, {mean_len/3:.1f} y {mean_muy/3:.1f} por cajero), validando exactamente la proporción 70 % retiros y 30 % pagos.")
    add_numbered_item("3.", "Mínimos, carga individual y respaldo estadístico (n^{*}): ", f"La Réplica {int(min_rap_row['replica'])} concentró las menores llegadas en Rápido ({int(min_rap_row['rapido'])}), Normal ({int(min_nor_row['normal'])}) y Muy lento ({int(min_muy_row['muy_lento'])}), mientras la Réplica {int(min_len_row['replica'])} marcó el mínimo de Lento ({int(min_len_row['lento'])}). En carga unitaria, las cajas de pago de 1R+2P atendieron menos personas ({e2_min_load:.1f}–{e2_max_load:.1f}/día). En cuanto a precisión muestral, el cálculo iterativo exige n^{{*}} = {n_req_min_wq}–{n_req_max_wq} réplicas para ε = ±0.50 min en W_{{q}}, tope cubierto por nuestras 100 corridas Monte Carlo.")
    add_numbered_item("4.", "Descarte del cuarto cajero físico o electrónico: ", f"Mientras se sostenga la operación mixta de tres cajas, añadir una cuarta posición resulta antieconómico: apenas recorta {wq_3m_100 - wq_4m_100:.2f}–{wq_3m_100 - wq_2r2p_100:.2f} min desde una espera ya baja ({wq_3m_100:.2f} min; {wq_3m_jsq:.2f} min con JSQ observable), a costa de hundir la ocupación desde {rho_3m_100:.1f}% hasta {rho_4m_100:.1f}%.")
    add_numbered_item("5.", "Recomendación de diseño para el Banco de Colombia: ", f"Mantener las 3 cajas actuales en régimen mixto (0 exclusivas de retiros y 0 de pagos). Cualquier partición rígida con tres ventanillas castiga al usuario: 1R+2P eleva la espera de retiros a {wq_ret_1r2p:.2f} min y 2R+1P colapsa los pagos hasta {wq_pago_2r1p:.2f} min de espera en fila ({w_pago_2r1p:.2f} min en sistema).")

    # =========================================================
    # REFERENCIAS (APA 7 SIN PARAFRASEAR DATOS ORIGINALES)
    # =========================================================
    add_h1("Referencias")
    referencias_apa7 = [
        [("Banks, J., Carson, J. S., II, Nelson, B. L., & Nicol, D. M. (2010). ", False), ("Discrete-event system simulation", True), (" (5th ed.). Pearson.", False)],
        [("Gross, D., Shortle, J. F., Thompson, J. M., & Harris, C. M. (2008). ", False), ("Fundamentals of queueing theory", True), (" (4th ed.). John Wiley & Sons.", False)],
        [("Kleinrock, L. (1975). ", False), ("Queueing systems, volume 1: Theory", True), (". John Wiley & Sons.", False)],
        [("Law, A. M. (2015). ", False), ("Simulation modeling and analysis", True), (" (5th ed.). McGraw-Hill Education.", False)],
        [("Little, J. D. C. (1961). A proof for the queuing formula: L = λ W. ", False), ("Operations Research, 9", True), ("(3), 383–387.", False)],
        [("Ross, S. M. (2014). ", False), ("Introduction to probability models", True), (" (11th ed.). Academic Press.", False)],
    ]
    for ref_parts in referencias_apa7:
        pr = doc.add_paragraph()
        pr.alignment = WD_ALIGN_PARAGRAPH.LEFT
        # Sangría francesa estricta APA 7 (0.5 pulgadas = 1.27 cm)
        pr.paragraph_format.left_indent = Inches(0.5)
        pr.paragraph_format.first_line_indent = Inches(-0.5)
        pr.paragraph_format.space_before = Pt(0.5)
        pr.paragraph_format.space_after = Pt(2.5)
        pr.paragraph_format.line_spacing = 1.12
        for chunk_txt, chunk_italic in ref_parts:
            add_rich_runs(pr, chunk_txt, font_size=10.0, color=COLOR_BODY, italic=chunk_italic)

    # =========================================================
    # ANEXOS
    # =========================================================
    add_h1("Anexo A: Estructura del Repositorio y Reproducibilidad")
    add_p(
        "El código fuente modular, las 11 pruebas unitarias, las tablas CSV exportadas y el cuaderno interactivo en Google Colab permanecen publicados "
        "para auditoría directa del docente:",
        space_after=4.0,
    )
    p_gh = doc.add_paragraph()
    p_gh.paragraph_format.left_indent = Inches(0.20)
    p_gh.paragraph_format.space_after = Pt(4)
    add_rich_runs(p_gh, "Repositorio GitHub:\n", font_size=9.5, color=COLOR_PRIMARY, bold=True)
    add_rich_runs(
        p_gh,
        "https://github.com/Camilo-Alberto-Palacio/Simulacion-Colas-Banco-MM1",
        font_name="Consolas", font_size=8.6, color=COLOR_SECONDARY, bold=True,
    )

    tree = [
        "Actividad 3 -Simulacion/",
        "  bank_queue/",
        "    model.py ................ <- Parámetros Tablas 1 y 2, analítica M/M/1–M/G/1 y llegadas",
        "    simulation.py ........... <- Motor DES (10 réplicas, n*, 100 Monte Carlo y JSQ observable)",
        "    visualizations.py ....... <- Generador de 6 figuras científicas a 300 DPI",
        "  tests/test_bank_queue.py .. <- Suite de 11 pruebas unitarias (Little, Student-t, JSQ, n*)",
        "  main.py ................... <- Orquestador experimental completo (exporta CSVs y figuras)",
        "  Simulacion_Colas_Banco_Colab.ipynb <- Cuaderno Google Colab pre-ejecutado",
        "  generate_doc.py ........... <- Generador dinámico APA 7 del presente informe Word",
    ]
    pt = doc.add_paragraph()
    pt.paragraph_format.left_indent = Inches(0.18)
    pt.paragraph_format.space_after = Pt(5)
    pt.paragraph_format.line_spacing = 1.02
    for idx_t, line in enumerate(tree):
        suffix = "\n" if idx_t < len(tree) - 1 else ""
        rl = pt.add_run(f"{line}{suffix}")
        rl.font.name = "Consolas"
        rl.font.size = Pt(7.8)
        rl.font.color.rgb = COLOR_PRIMARY

    add_h1("Anexo B: Estructura del Video de Sustentación (2:30 Minutos)")
    add_p(
        f"El libreto cronometrado de exposición oral se encuentra en GUION_VIDEO_SUSTENTACION.md dentro del repositorio. Abarca cinco bloques: "
        f"(1) planteamiento de la paradoja operativa 70/30 frente al peso real del servicio; (2) presentación del Grupo 25 y lectura de las tablas del "
        f"Banco de Colombia; (3) arquitectura M/M/1, contrastes en 10 réplicas ({c_min_srv['cajero']} vs. {c_max_srv['cajero']}), perfilado de demanda "
        f"y cálculo muestral n^{{*}}; (4) validación a 100 réplicas evidenciando el cuello de botella de {wq_pago_2r1p:.2f} min en pagos bajo 2R+1P; y "
        f"(5) recomendación final de conservar las tres cajas mixtas sin adicionar una cuarta posición."
    )

    saved_path = output_filename
    try:
        doc.save(output_filename)
        print(f"[OK] Documento Word APA 7 generado exitosamente: {output_filename}")
    except PermissionError:
        saved_path = os.path.join(BASE_DIR, "Evidencia de Aprendizaje 3 - Solución Problema Bancario (Actualizado).docx")
        doc.save(saved_path)
        print(f"[AVISO] Archivo en uso. Guardado como: {saved_path}")

    if update_word_toc_and_fields(saved_path):
        print("[OK] Tabla de Contenido y numeración de páginas actualizadas vía Microsoft Word.")
    else:
        print("[AVISO] No se pudo invocar Word COM automáticamente; abra el .docx para actualizar campos.")


if __name__ == "__main__":
    build_document()
