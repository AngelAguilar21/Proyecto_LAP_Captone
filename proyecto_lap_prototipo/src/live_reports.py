"""Export observed session data. Optional document engines fail explicitly."""
import csv
from datetime import datetime, timezone
import io
import json
import os
from pathlib import Path
import subprocess
import sys


def report_data(config, state, kind):
    if not state.get("session"):
        raise ValueError("Inicia una sesión para generar un reporte.")
    if kind in ("zones", "comparison"):
        headers=["Sector X","Sector Y","Personas x segundos","Pico observado","IDs observados","Prioridad"]
        rows=[[c["x"],c["y"],round(c["seconds"],3),c["peak"],c.get("visits",0),i+1] for i,c in enumerate(state["analytics"]["heat"])]
        title="Zonas de ocupación" if kind=="zones" else "Comparación de sectores"
    elif kind=="occupancy":
        headers=["Zona","Ocupación actual","Personas x segundos","Pico observado","IDs observados"]
        rows=[[z["name"],z["count"],round(z.get("seconds",0),3),z.get("peak",0),z.get("visits",0)] for z in state["analytics"]["zones"]]
        title="Ocupación por zona"
    elif kind=="flow":
        bins={}
        for sample in state.get("series",[]):
            hour=int(sample["t"]//3600)
            item=bins.setdefault(hour,{"sum":0,"n":0,"peak":0})
            item["sum"]+=sample["count"]
            item["n"]+=1
            item["peak"]=max(item["peak"],sample["count"])
        headers=["Hora relativa de fuente","Personas observadas promedio","Pico observado","Muestras"]
        rows=[[h,round(v["sum"]/v["n"],3),v["peak"],v["n"]] for h,v in sorted(bins.items())]
        title="Flujo por hora relativa de fuente"
    elif kind=="trajectories":
        if state["status"] not in ("running","paused"):
            raise ValueError("Los recorridos individuales se eliminan al finalizar. Exporta durante una sesión activa o pausada.")
        headers=["ID temporal","Cámara actual","Asociación","Tiempo de fuente (s)","X","Y"]
        unique={p["id"]:p for p in state["people"]}
        rows=[[p["id"],p["camera"],p["association"],round(h[2],3),round(h[0],4),round(h[1],4)] for p in unique.values() for h in p["history"]]
        title="Trayectorias recientes de la sesión"
    else:
        raise ValueError("Tipo de reporte desconocido.")
    return {"title":title,"headers":headers,"rows":rows,"airport":config.get("airport","Aeropuerto"),"session":state["session"],"mode":"SIMULACIÓN SINTÉTICA" if state.get("mode")=="demo" else "FUENTE REAL - SIN VALIDACIÓN DE PRECISIÓN", "unit":"metros" if config["unit"]=="meters" else "unidades relativas","seconds":round(state["t"],2),"generated":datetime.now(timezone.utc).isoformat(),"note":"Datos observados; asociaciones estimadas. Ocupación no equivale a rentabilidad. Flujo horario calculado sobre las muestras retenidas (hasta 3600)."}


def safe_text(value):
    if isinstance(value,str) and value.lstrip().startswith(("=","+","-","@")):
        return "'"+value
    return value


def csv_bytes(data):
    output=io.StringIO(newline="")
    writer=csv.writer(output)
    writer.writerow(["AeroTrack",data["title"]])
    writer.writerow(["Origen",data["mode"],"Sesión",data["session"],"Unidad",data["unit"]])
    writer.writerow(data["headers"])
    writer.writerows([[safe_text(v) for v in row] for row in data["rows"]])
    return output.getvalue().encode("utf-8-sig")


def xlsx_bytes(data):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.utils import get_column_letter
    wb=Workbook()
    ws=wb.active
    ws.title="Reporte"
    columns=len(data["headers"])
    ws.merge_cells(start_row=1,start_column=1,end_row=1,end_column=columns)
    ws.cell(1,1,"AeroTrack | "+data["title"]).font=Font(name="Calibri",size=18,bold=True,color="0A3958")
    ws.row_dimensions[1].height=32
    ws.merge_cells(start_row=2,start_column=1,end_row=2,end_column=columns)
    ws.cell(2,1,data["mode"]+" · "+data["airport"]).font=Font(size=10,color="456577")
    ws.merge_cells(start_row=3,start_column=1,end_row=3,end_column=columns)
    ws.cell(3,1,f"Sesión {data['session']} · {data['seconds']} segundos de fuente · {data['unit']}")
    ws.append([])
    for i,title in enumerate(data["headers"],1):
        cell=ws.cell(5,i,title)
        cell.fill=PatternFill("solid",fgColor="0C4B74")
        cell.font=Font(name="Calibri",bold=True,color="FFFFFF")
        cell.alignment=Alignment(wrap_text=True,vertical="center")
        ws.column_dimensions[get_column_letter(i)].width=max(18,min(32,len(title)+3))
    ws.row_dimensions[5].height=32
    for ri,row in enumerate(data["rows"],6):
        for ci,value in enumerate(row,1):
            cell=ws.cell(ri,ci,safe_text(value))
            cell.font=Font(name="Calibri",size=11,color="173A50")
            if isinstance(value,float):
                cell.number_format="0.000"
            if ri%2==0:
                cell.fill=PatternFill("solid",fgColor="EDF4F8")
    ws.freeze_panes="A6"
    ws.auto_filter.ref=f"A5:{get_column_letter(columns)}{max(5,5+len(data['rows']))}"
    note=ws.cell(len(data["rows"])+8,1,data["note"])
    note.font=Font(size=10,color="526A79")
    ws.merge_cells(start_row=note.row,start_column=1,end_row=note.row,end_column=columns)
    note.alignment=Alignment(wrap_text=True)
    ws.row_dimensions[note.row].height=38
    output=io.BytesIO()
    wb.save(output)
    return output.getvalue()


def pdf_bytes(data):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import landscape,A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle
    from xml.sax.saxutils import escape
    buffer=io.BytesIO()
    document=SimpleDocTemplate(buffer,pagesize=landscape(A4),leftMargin=34,rightMargin=34,topMargin=30,bottomMargin=30,title=data["title"],author="AeroTrack")
    styles=getSampleStyleSheet()
    styles["Title"].textColor=colors.HexColor("#0a3958")
    styles["Title"].fontSize=20
    styles["Normal"].fontSize=9
    flow=[Paragraph("AeroTrack | "+escape(data["title"]),styles["Title"]),Paragraph(escape(data["airport"])+" · "+escape(data["mode"]),styles["Normal"]),Spacer(1,8),Paragraph(f"Sesión {escape(data['session'])} · {data['seconds']} segundos de fuente · {escape(data['unit'])}",styles["Normal"]),Spacer(1,18)]
    rows=[data["headers"]]+data["rows"]
    formatted=[[Paragraph(escape(str(v)),styles["Normal"]) for v in row] for row in rows]
    if len(rows)==1:
        flow.append(Paragraph("Sin observaciones para este reporte.",styles["Normal"]))
    else:
        table=Table(formatted,colWidths=[document.width/len(data["headers"])]*len(data["headers"]),repeatRows=1)
        table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#DBEAF3")),("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,colors.HexColor("#F0F5F8")]),("VALIGN",(0,0),(-1,-1),"TOP"),("TOPPADDING",(0,0),(-1,-1),7),("BOTTOMPADDING",(0,0),(-1,-1),7),("LINEBELOW",(0,0),(-1,0),.6,colors.HexColor("#2679AE"))]))
        flow.append(table)
    flow.extend([Spacer(1,16),Paragraph(escape(data["note"]),styles["Normal"])])
    def footer(canvas,doc):
        canvas.setFont("Helvetica",8)
        canvas.setFillColor(colors.HexColor("#608092"))
        canvas.drawString(34,16,"AeroTrack · Información de sesión · Sin identificación personal")
        canvas.drawRightString(landscape(A4)[0]-34,16,f"Página {doc.page}")
    document.build(flow,onFirstPage=footer,onLaterPages=footer)
    return buffer.getvalue()


def export(config,state,kind,format):
    data=report_data(config,state,kind)
    if format=="csv":
        return csv_bytes(data),"text/csv; charset=utf-8"
    function={"xlsx":xlsx_bytes,"pdf":pdf_bytes}.get(format)
    if not function:
        raise ValueError("Formato desconocido.")
    try:
        result=function(data)
    except ImportError:
        runtime=os.environ.get("AEROTRACK_DOCUMENT_PYTHON")
        bundled=Path.home()/".cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe"
        if not runtime and bundled.is_file():
            runtime=str(bundled)
        if not runtime or not Path(runtime).is_file():
            raise ValueError("Este reporte requiere reportlab (PDF) u openpyxl (Excel), o un AEROTRACK_DOCUMENT_PYTHON con esas dependencias.")
        process=subprocess.run([runtime,str(Path(__file__).resolve()),format],input=json.dumps(data).encode(),capture_output=True,timeout=45,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
        if process.returncode:
            raise ValueError("No se pudo generar el documento. Comprueba las dependencias de exportación.")
        result=process.stdout
    return result,"application/pdf" if format=="pdf" else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


if __name__=="__main__":
    data=json.loads(sys.stdin.buffer.read())
    sys.stdout.buffer.write((pdf_bytes if sys.argv[1]=="pdf" else xlsx_bytes)(data))
