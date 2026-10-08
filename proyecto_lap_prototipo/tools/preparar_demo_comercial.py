"""Historical *synthetic* inputs matched to businesses in one recorded test.

Keeps video counts intact. Creates eight previous comparable dates and exports
exact imported sales and historical traffic. Never writes the real dataset.
"""
import argparse
import csv
import io
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from storage.environment import load_environment
from storage import operational
import projects
import business_data
import business_catalog
import commercial


def prepare(session):
    load_environment(ROOT.parent)
    operational.configure(ROOT)
    meta=json.loads((ROOT/'data/replays'/session/'manifest.json').read_text(encoding='utf-8'))
    if meta['status'] not in ('stopped','ended') or not meta.get('config',{}).get('testRun'):
        raise ValueError('Selecciona una sesión finalizada de Prueba con videos.')
    path=projects.project_path(ROOT,meta['projectId'])
    config=projects.read_document(path)
    con=business_data.connect(path)
    try:
        businesses=business_catalog.sync(con,config,ROOT/'dashboard/public')
        traffic=business_catalog.traffic(businesses,meta['cameraAnalytics'],{**meta['config'],'cameras':meta['cameras']},config)
        commercial.save_session(con,meta,traffic)
        measured=[b for b in traffic if b['entries'] is not None]
        origin=datetime.fromisoformat(meta['created']).astimezone(commercial.LIMA)
        sales_rows=[]; history=[]
        for index,b in enumerate(measured):
            for week in range(1,9):
                day=(origin-timedelta(weeks=week)).date().isoformat()
                for offset in (0,1):
                    hour=(origin.hour+offset)%24
                    date=day if origin.hour+offset<24 else (datetime.fromisoformat(day)+timedelta(days=1)).date().isoformat()
                    entries=40+index*10+week*3+offset*6
                    transactions=max(1,round(entries*(.15+index*.025)))
                    amount=round(transactions*(20+index*8),2)
                    sales_rows.append([b['id'],b['nombre'],date,hour,amount,'PEN',transactions])
                    history.append([f'demo-history-{session}',b['id'],date,hour,entries,max(0,entries-2),3600,'demo'])
        sales_io=io.StringIO(); writer=csv.writer(sales_io)
        writer.writerow(['negocio_id','negocio_nombre','fecha','hora','monto','moneda','transacciones'])
        writer.writerows(sales_rows)
        commercial.setup(con)
        # Idempotent: keep existing rows; never overwrite previously imported sales.
        missing=[row for row in sales_rows if not con.execute('SELECT 1 FROM commercial_sales WHERE negocio_id=? AND fecha=? AND hora=? AND dataset=?',(row[0],row[2],row[3],'demo')).fetchone()]
        if missing:
            payload=io.StringIO(); w=csv.writer(payload); w.writerow(['negocio_id','negocio_nombre','fecha','hora','monto','moneda','transacciones']); w.writerows(missing)
            report=commercial.import_sales(con,payload.getvalue(),businesses,f'Historico SINTETICO {session}.csv','demo')
            if report['errors']: raise ValueError(report['errors'])
        with con:
            con.executemany('INSERT OR IGNORE INTO commercial_traffic VALUES (?,?,?,?,?,?,?,?)',history)
        output=ROOT/'data/commercial-tests'/session
        output.mkdir(parents=True,exist_ok=True)
        # Export the actual persisted historical records, including any preexisting ones.
        persisted=[]
        for bid,name,date,hour,*_ in sales_rows:
            amount,transactions=con.execute('SELECT monto,transacciones FROM commercial_sales WHERE negocio_id=? AND fecha=? AND hora=? AND dataset=?',(bid,date,hour,'demo')).fetchone()
            persisted.append([bid,name,date,hour,amount,'PEN',transactions])
        sales_io=io.StringIO(); w=csv.writer(sales_io); w.writerow(['negocio_id','negocio_nombre','fecha','hora','monto','moneda','transacciones']);w.writerows(persisted)
        (output/'ventas_historicas_SINTETICAS.csv').write_text(sales_io.getvalue(),encoding='utf-8-sig')
        with (output/'trafico_historico_SINTETICO.csv').open('w',encoding='utf-8-sig',newline='') as f:
            w=csv.writer(f);w.writerow(['session','negocio_id','fecha','hora','entradas','salidas','cobertura_s','origen']);w.writerows(history)
        result=commercial.summary(con,businesses,traffic,'demo',origin.date().isoformat(),origin.hour)
        result['businesses']=[b for b in result['businesses'] if b['id'] in {m['id'] for m in measured}]
        result['videoSession']=session
        result['projectId']=meta['projectId']
        result['sourceNote']='Cruces del video; ventas y tráfico de las ocho fechas previas son SINTETICOS. No hay ventas confirmadas para el video.'
        result['observedCrossings']=[{'id':b['id'],'name':b['nombre'],'entries':b['entries'],'exits':b['exits']} for b in measured]
        result['historicalInputs']=[{'id':row[0],'name':row[1],'date':row[2],'hour':row[3],'sales':row[4],'transactions':row[6],
            'entries':next(h[4] for h in history if h[1]==row[0] and h[2]==row[2] and h[3]==row[3]),'coverage':3600} for row in persisted]
        (output/'resultado.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps({'folder':str(output),'date':result['date'],'hour':result['hour'],'session':session,'businesses':[{'name':b['name'],'entries':b['entries'],'coverage':b['coverage'],'estimate':b['forecast']['estimate'],'days':b['forecast']['days']} for b in result['businesses']]},ensure_ascii=True))
    finally:
        con.close()

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('session')
    prepare(parser.parse_args().session)
