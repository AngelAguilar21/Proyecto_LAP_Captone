"""Ventas, tráfico de accesos y comparaciones; datos reales y pruebas separados."""
import csv
import io
import json
import math
import hashlib
import random
import statistics
from collections import defaultdict
from datetime import datetime, timedelta, timezone


LIMA = timezone(timedelta(hours=-5), 'America/Lima')
SCHEMA = '''
CREATE TABLE IF NOT EXISTS commercial_sales (
 negocio_id TEXT NOT NULL REFERENCES negocios(id), fecha TEXT NOT NULL,
 hora INTEGER NOT NULL, monto REAL NOT NULL, transacciones INTEGER,
 dataset TEXT NOT NULL, import_id TEXT NOT NULL,
 PRIMARY KEY(negocio_id,fecha,hora,dataset));
CREATE TABLE IF NOT EXISTS commercial_imports (
 id TEXT PRIMARY KEY, nombre TEXT NOT NULL, dataset TEXT NOT NULL,
 filas INTEGER NOT NULL, creado TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS commercial_traffic (
 session TEXT NOT NULL, negocio_id TEXT NOT NULL REFERENCES negocios(id),
 fecha TEXT NOT NULL, hora INTEGER NOT NULL, entradas INTEGER NOT NULL,
 salidas INTEGER NOT NULL, coverage REAL NOT NULL, dataset TEXT NOT NULL,
 PRIMARY KEY(session,negocio_id,fecha,hora,dataset));
CREATE TABLE IF NOT EXISTS commercial_incidents (
 id TEXT PRIMARY KEY, negocio_id TEXT NOT NULL REFERENCES negocios(id),
 inicio TEXT NOT NULL, duracion REAL NOT NULL, pico INTEGER NOT NULL,
 dataset TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS commercial_bags (
 id TEXT PRIMARY KEY, session TEXT NOT NULL, negocio_id TEXT NOT NULL REFERENCES negocios(id),
 t REAL NOT NULL, matched INTEGER NOT NULL, changed INTEGER NOT NULL,
 similarity REAL, reason TEXT NOT NULL, dataset TEXT NOT NULL);
'''


def setup(con):
    con.executescript(SCHEMA)
    # La Fase 2 anterior guardaba CSV en ventas. Conserva sus franjas
    # horarias válidas; un total diario no se reparte artificialmente.
    if con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='ventas'").fetchone():
        legacy = con.execute("SELECT negocio_id,fecha,hora,SUM(monto) FROM ventas WHERE origen='csv' AND hora BETWEEN 0 AND 23 AND monto>=0 GROUP BY negocio_id,fecha,hora").fetchall()
        with con:
            for bid, day, hour, amount in legacy:
                try:
                    datetime.strptime(day, '%Y-%m-%d')
                    if not math.isfinite(amount):
                        continue
                    con.execute('INSERT OR IGNORE INTO commercial_sales VALUES (?,?,?,?,?,?,?)', (bid,day,hour,amount,None,'real','legacy-csv'))
                except (ValueError, TypeError):
                    continue


def parse_sales(text, businesses):
    if not isinstance(text, str) or not text.strip() or len(text) > 2_000_000:
        raise ValueError('Selecciona un CSV de ventas de hasta 2 MB.')
    text = text.lstrip('\ufeff')
    delimiter = ';' if ';' in text.splitlines()[0] else ','
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    required = {'negocio_id', 'fecha', 'hora', 'monto'}
    if not required.issubset(reader.fieldnames or []):
        raise ValueError('Faltan columnas: negocio_id, fecha, hora y monto. Usa la plantilla.')
    known = {b['id'] for b in businesses}
    rows, errors, seen = [], [], set()
    for number, row in enumerate(reader, 2):
        try:
            bid = row['negocio_id'].strip()
            if bid not in known:
                raise ValueError('el negocio_id no existe en este proyecto')
            day = row['fecha'].strip()
            if datetime.strptime(day, '%Y-%m-%d').strftime('%Y-%m-%d') != day:
                raise ValueError('usa fecha AAAA-MM-DD')
            hour = int(row['hora'])
            if not 0 <= hour <= 23:
                raise ValueError('la hora debe estar entre 0 y 23; no se admiten totales diarios')
            amount = float(row['monto'].replace(',', '.') if delimiter == ';' else row['monto'])
            if not math.isfinite(amount) or amount < 0:
                raise ValueError('el monto debe ser un número finito, mayor o igual a cero')
            if row.get('moneda', 'PEN').strip().upper() != 'PEN':
                raise ValueError('solo se admiten soles (PEN)')
            transactions = int(row['transacciones']) if row.get('transacciones', '').strip() else None
            if transactions is not None and transactions < 0:
                raise ValueError('transacciones debe ser un entero no negativo')
            key = (bid, day, hour)
            if key in seen:
                raise ValueError('negocio, fecha y hora repetidos en el archivo')
            seen.add(key)
            rows.append((bid, day, hour, amount, transactions))
        except (ValueError, TypeError, KeyError, AttributeError) as exc:
            errors.append(f'Fila {number}: {exc}')
    if not rows and not errors:
        errors.append('El CSV no contiene filas de ventas.')
    return rows, errors


def import_sales(con, text, businesses, name, dataset='real', preview=False):
    setup(con)
    if dataset not in ('real', 'demo'):
        raise ValueError('Origen de datos inválido.')
    rows, errors = parse_sales(text, businesses)
    for bid, day, hour, *_ in rows:
        if con.execute('SELECT 1 FROM commercial_sales WHERE negocio_id=? AND fecha=? AND hora=? AND dataset=?', (bid, day, hour, dataset)).fetchone():
            errors.append(f'Ya hay ventas para {bid}, {day}, {hour:02d}:00. No se sobrescribieron.')
    report = {'rows': len(rows), 'errors': errors[:30], 'errorCount': len(errors), 'imported': False}
    if errors or preview:
        return report
    ident = hashlib.sha256((dataset + text).encode()).hexdigest()
    with con:
        con.execute('INSERT INTO commercial_imports VALUES (?,?,?,?,?)', (ident, str(name)[:120], dataset, len(rows), datetime.now(timezone.utc).isoformat()))
        con.executemany('INSERT INTO commercial_sales VALUES (?,?,?,?,?,?,?)', [(*r, dataset, ident) for r in rows])
    return {**report, 'imported': True, 'importId': ident}


def template(businesses):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['negocio_id', 'negocio_nombre', 'empresa', 'fecha', 'hora', 'monto', 'moneda', 'transacciones'])
    for b in businesses:
        if b.get('estado') != 'cerrado':
            writer.writerow([b['id'], b['nombre'], b.get('empresa') or 'Sin empresa', '', '', '', 'PEN', ''])
    return output.getvalue()


def simulate_demo(con, businesses, days=28, seed='aerotrack'):
    """Genera tráfico y ventas horarios sintéticos, separados del dato real.

    El objetivo es probar el flujo comercial completo: entradas por acceso,
    ventas, transacciones, conversión y pronóstico. Los valores no representan
    un negocio real y se guardan exclusivamente en el dataset ``demo``.
    """
    setup(con)
    active = [b for b in businesses if b.get('estado') != 'cerrado']
    if not active:
        raise ValueError('Crea al menos un negocio activo antes de generar datos de prueba.')
    try:
        days = max(7, min(int(days), 90))
    except (TypeError, ValueError):
        days = 28
    end = datetime.now(LIMA).date() - timedelta(days=1)
    start = end - timedelta(days=days - 1)
    project_seed = hashlib.sha256(str(seed).encode('utf-8')).hexdigest()
    session = f'demo-synthetic-{project_seed[:12]}'
    import_id = f'demo-synthetic-{project_seed[:16]}'
    rng = random.Random(int(project_seed[:12], 16))
    profiles = {8:.22, 9:.48, 10:.72, 11:.92, 12:1.12, 13:1.28,
                14:1.02, 15:.84, 16:.9, 17:1.08, 18:1.32, 19:1.46,
                20:1.28, 21:.96, 22:.56}
    traffic_rows, sales_rows = [], []
    for index, business in enumerate(active):
        local_seed = hashlib.sha256(f'{project_seed}:{business["id"]}'.encode()).hexdigest()
        local = random.Random(int(local_seed[:12], 16))
        base = 18 + (int(local_seed[12:16], 16) % 28)
        conversion = .075 + (int(local_seed[16:18], 16) % 80) / 1000
        ticket = 28 + (int(local_seed[18:22], 16) % 95)
        for day_index in range(days):
            day = start + timedelta(days=day_index)
            weekday_factor = 1.12 if day.weekday() >= 5 else (0.9 if day.weekday() == 0 else 1.0)
            for hour in range(24):
                profile = profiles.get(hour, 0.03)
                expected = base * profile * weekday_factor
                entries = max(0, int(round(expected + local.gauss(0, max(1.0, expected * .14)))))
                exits = max(0, int(round(entries * (0.72 + local.random() * .16))))
                coverage = 3600.0
                traffic_rows.append((session, business['id'], day.isoformat(), hour, entries, exits, coverage, 'demo'))
                transactions = max(0, int(round(entries * conversion + local.gauss(0, .7)))) if entries else 0
                amount = round(transactions * ticket * (0.88 + local.random() * .24), 2)
                sales_rows.append((business['id'], day.isoformat(), hour, amount, transactions, 'demo', import_id))
    with con:
        con.execute('DELETE FROM commercial_traffic WHERE session=? AND dataset="demo"', (session,))
        con.execute('DELETE FROM commercial_sales WHERE import_id=? AND dataset="demo"', (import_id,))
        con.execute('INSERT OR REPLACE INTO commercial_imports VALUES (?,?,?,?,?)', (import_id, 'simulacion-comercial.json', 'demo', len(sales_rows), datetime.now(timezone.utc).isoformat()))
        con.executemany('INSERT OR REPLACE INTO commercial_traffic VALUES (?,?,?,?,?,?,?,?)', traffic_rows)
        con.executemany('INSERT OR REPLACE INTO commercial_sales VALUES (?,?,?,?,?,?,?)', sales_rows)
    return {'dataset': 'demo', 'days': days, 'businesses': len(active), 'rows': len(sales_rows), 'session': session, 'start': start.isoformat(), 'end': end.isoformat()}


def save_session(con, meta, traffic):
    """Grabaciones sin fecha declarada no se atribuyen a la fecha de ejecución."""
    setup(con)
    dataset = 'demo' if meta.get('module') == 'demo' or meta.get('config', {}).get('testRun') else 'real'
    config = meta.get('config', {})
    start = meta.get('created') if config.get('sourceMode') == 'live' or dataset == 'demo' else config.get('recordingStartedAt')
    if not start:
        return False
    try:
        origin = datetime.fromisoformat(start.replace('Z', '+00:00'))
        if origin.tzinfo is None:
            raise ValueError('La fecha de grabación necesita zona horaria.')
        origin = origin.astimezone(LIMA)
    except (ValueError, TypeError):
        return False
    end = origin + timedelta(seconds=meta.get('end', 0))
    with con:
        for business in traffic:
            if business['entries'] is None:
                continue
            # Si una cámara termina antes, no atribuirle la duración de otra.
            observed_times = [meta.get('cameraAnalytics',{}).get(a['cameraId'],{}).get('t',meta.get('end',0)) for a in business.get('accesses',[])]
            business_end = min(end, origin + timedelta(seconds=min(observed_times))) if observed_times else end
            bins = {}
            cursor = origin.replace(minute=0, second=0, microsecond=0)
            while cursor <= business_end:
                right = cursor + timedelta(hours=1)
                coverage = max(0, (min(business_end, right)-max(origin, cursor)).total_seconds())
                bins[(cursor.date().isoformat(), cursor.hour)] = [0, 0, coverage]
                cursor = right
            for event in business['events']:
                when = origin + timedelta(seconds=event['t'])
                key = (when.date().isoformat(), when.hour)
                if key in bins:
                    bins[key][0 if event['direction'] == 'entries' else 1] += 1
            for (day, hour), (entries, exits, coverage) in bins.items():
                con.execute('INSERT OR REPLACE INTO commercial_traffic VALUES (?,?,?,?,?,?,?,?)', (meta['session'], business['id'], day, hour, entries, exits, coverage, dataset))
        for camera_id, analysis in meta.get('cameraAnalytics', {}).items():
            owners = [b for b in traffic if any(a['cameraId']==camera_id for a in b['accesses'])]
            camera = next((c for c in meta.get('cameras',[]) if c['id']==camera_id), {})
            for episode in analysis.get('occupancy',{}).get('episodes',[]):
                zone = next((z for z in camera.get('analysisZones',[]) if z.get('name')==episode.get('zone') or z.get('id')==episode.get('zone')), {})
                bid = zone.get('businessId') or (owners[0]['id'] if len(owners)==1 else None)
                if not bid or bid not in {b['id'] for b in traffic}:
                    continue
                when = origin+timedelta(seconds=episode.get('start',0))
                ident = f"{meta['session']}:{camera_id}:{episode.get('id',episode.get('start'))}"
                con.execute('INSERT OR REPLACE INTO commercial_incidents VALUES (?,?,?,?,?,?)', (ident,bid,when.isoformat(),float(episode.get('duration') or 0),int(episode.get('peak') or 0),dataset))
    return True


def forecast(con, bid, day, hour, entries, dataset='real'):
    target = datetime.strptime(day, '%Y-%m-%d').date()
    # Selecciona una sesión completa por hora: repetir un video no duplica tráfico.
    traffic = con.execute('SELECT fecha,hora,entradas,coverage FROM commercial_traffic WHERE negocio_id=? AND dataset=? AND coverage>=3300 ORDER BY coverage DESC', (bid, dataset)).fetchall()
    by_day = {}
    for date, h, count, _ in traffic:
        if h == hour and date < day and datetime.strptime(date, '%Y-%m-%d').weekday() == target.weekday():
            by_day.setdefault(date, count)
    ratios = []
    for date, count in by_day.items():
        sale = con.execute('SELECT monto FROM commercial_sales WHERE negocio_id=? AND fecha=? AND hora=? AND dataset=?', (bid, date, hour, dataset)).fetchone()
        if sale and count > 0:
            ratios.append(sale[0] / count)
    if len(ratios) < 3:
        return {'estimate': None, 'days': len(ratios), 'reason': 'Se necesitan al menos 3 días anteriores del mismo día de semana y hora, con ventas y tráfico completo.'}
    rate = statistics.median(ratios)
    return {'estimate': round(entries * rate, 2), 'perEntry': round(rate, 2), 'days': len(ratios), 'range': [round(entries * min(ratios), 2), round(entries * max(ratios), 2)], 'reason': 'Proyección, no venta confirmada. Ingreso histórico por entrada; no ticket por compra.'}


def next_forecast(con, bid, day, hour, dataset='real'):
    """Pronostica la siguiente hora con trafico historico comparable."""
    target = datetime.strptime(day, '%Y-%m-%d') + timedelta(hours=int(hour) + 1)
    target_day, target_hour = target.date().isoformat(), target.hour
    target_weekday = target.weekday()
    by_date = {}
    for date, entries in con.execute(
        'SELECT fecha,entradas FROM commercial_traffic WHERE negocio_id=? AND dataset=? AND hora=? AND coverage>=3300 AND fecha<? ORDER BY coverage DESC,session',
        (bid, dataset, target_hour, target_day)).fetchall():
        if datetime.strptime(date, '%Y-%m-%d').weekday() == target_weekday and entries is not None and entries >= 0:
            by_date.setdefault(date, entries)
    counts = list(by_date.values())
    if not counts:
        return {'estimate': None, 'expectedEntries': None, 'days': 0, 'confidence': 'baja',
                'target': f'{target_day}T{target_hour:02d}:00',
                'reason': 'No hay trafico historico para pronosticar la siguiente hora.'}
    expected = int(round(statistics.median(counts)))
    result = forecast(con, bid, target_day, target_hour, expected, dataset)
    result['expectedEntries'] = expected
    result['target'] = f'{target_day}T{target_hour:02d}:00'
    result['confidence'] = 'alta' if result.get('days', 0) >= 7 else 'media' if result.get('days', 0) >= 3 else 'baja'
    return result


def summary(con, businesses, traffic, dataset='real', day=None, hour=None, empresa=None):
    setup(con)
    now = datetime.now(LIMA)
    day, hour = day or now.date().isoformat(), now.hour if hour is None else int(hour)
    datetime.strptime(day, '%Y-%m-%d')
    if not 0 <= hour <= 23 or dataset not in ('real', 'demo'):
        raise ValueError('Fecha, hora u origen inválidos.')
    rows = []
    counts = {b['id']: b for b in traffic}
    for b in businesses:
        current = counts.get(b['id'], {})
        # El tráfico del momento se pasa solamente cuando coincide su hora civil.
        saved = con.execute('SELECT entradas,coverage,session FROM commercial_traffic WHERE negocio_id=? AND fecha=? AND hora=? AND dataset=? ORDER BY coverage DESC,session LIMIT 1', (b['id'], day, hour, dataset)).fetchone()
        entries = saved[0] if saved else None
        coverage = float(saved[1]) if saved else 0
        sales = con.execute('SELECT monto,transacciones FROM commercial_sales WHERE negocio_id=? AND fecha=? AND hora=? AND dataset=?', (b['id'], day, hour, dataset)).fetchone()
        projection = forecast(con, b['id'], day, hour, entries or 0, dataset) if entries is not None else {'estimate': None, 'days': 0, 'reason': 'No hay entradas medidas en esta franja.'}
        projection['confidence'] = 'alta' if projection.get('days', 0) >= 7 else 'media' if projection.get('days', 0) >= 3 else 'baja'
        next_projection = next_forecast(con, b['id'], day, hour, dataset)
        transactions = sales[1] if sales else None
        conversion = round(100 * transactions / entries, 1) if coverage >= 3300 and transactions is not None and entries and entries > 0 else None
        hourly = []
        seen_hours = set()
        for h, hourly_entries, hourly_exits, hour_coverage in con.execute('SELECT hora,entradas,salidas,coverage FROM commercial_traffic WHERE negocio_id=? AND fecha=? AND dataset=? ORDER BY hora,coverage DESC,session', (b['id'], day, dataset)):
            if h in seen_hours:
                continue
            seen_hours.add(h)
            hourly_sale = con.execute('SELECT monto,transacciones FROM commercial_sales WHERE negocio_id=? AND fecha=? AND hora=? AND dataset=?', (b['id'], day, h, dataset)).fetchone()
            hourly_estimate = forecast(con, b['id'], day, h, hourly_entries, dataset)
            hourly.append({'hour': h, 'entries': hourly_entries, 'exits': hourly_exits, 'coverage': round(hour_coverage),
                           'sales': hourly_sale[0] if hourly_sale else None,
                           'transactions': hourly_sale[1] if hourly_sale else None,
                           'estimate': hourly_estimate.get('estimate'),
                           'confidence': 'alta' if hourly_estimate.get('days', 0) >= 7 else 'media' if hourly_estimate.get('days', 0) >= 3 else 'baja'})
        incidents = []
        for ident, start, duration, peak in con.execute('SELECT id,inicio,duracion,pico FROM commercial_incidents WHERE negocio_id=? AND dataset=? ORDER BY inicio DESC LIMIT 100', (b['id'], dataset)):
            when = datetime.fromisoformat(start).astimezone(LIMA)
            if when.date().isoformat() != day:
                continue
            baseline = forecast(con, b['id'], day, when.hour, 1, dataset)
            # Ventas por hora no permiten comparar minutos de un incidente.
            sold = con.execute('SELECT monto FROM commercial_sales WHERE negocio_id=? AND fecha=? AND hora=? AND dataset=?', (b['id'], day, when.hour, dataset)).fetchone()
            historic = con.execute('SELECT fecha,monto FROM commercial_sales WHERE negocio_id=? AND hora=? AND dataset=? AND fecha<?', (b['id'], when.hour, dataset, day)).fetchall()
            amounts = [amount for date, amount in historic if datetime.strptime(date,'%Y-%m-%d').weekday()==when.weekday()]
            normal = statistics.median(amounts) if len(amounts)>=3 else None
            crossing_hour = (when + timedelta(seconds=duration)).hour != when.hour or duration >= 3600
            percent = round(100*(sold[0]/normal-1),1) if sold and normal and not crossing_hour else None
            incidents.append({'id':ident,'start':start,'duration':duration,'peak':peak,'sales':sold[0] if sold else None,'baseline':normal,'differencePercent':percent,'sampleDays':len(amounts),'scope':'Incidente asociado por la cámara del acceso. Hora que contiene el incidente; no ventas durante sus minutos.' if not crossing_hour else 'El incidente abarca varias horas; no se calcula variación.'})
        bags = con.execute('SELECT COUNT(*),COALESCE(SUM(matched),0),COALESCE(SUM(changed),0) FROM commercial_bags WHERE negocio_id=? AND dataset=? AND session IN (SELECT session FROM commercial_traffic WHERE negocio_id=? AND fecha=? AND dataset=?)', (b['id'],dataset,b['id'],day,dataset)).fetchone()
        rows.append({'id':b['id'],'name':b['nombre'],'empresa':b.get('empresa') or 'Sin empresa','accesses':len(b['puertas']),
                     'entries':entries,'coverage':coverage,'session':saved[2] if saved else None,
                     'conversionReason': 'Transacciones por entrada; no identifica compradores únicos.' if conversion is not None else 'Se necesitan ventas con transacciones y al menos 55 minutos de tráfico de la misma hora, con entradas mayores que cero.',
                     'estimateScope': 'Entradas observadas en el video; no extrapola a toda la hora.' if coverage < 3300 else 'Entradas de la hora seleccionada.',
                     'sales':sales[0] if sales else None,'transactions':transactions,'conversion':conversion,
                     'forecast':projection,'nextForecast':next_projection,'hourly':hourly,'incidents':incidents,
                     'bags':{'exits':bags[0],'matched':bags[1],'changed':bags[2],'unmatched':bags[0]-bags[1],'coverage':round(100*bags[1]/bags[0],1) if bags[0] else None}})
    companies = []
    grouped = defaultdict(list)
    for row in rows:
        grouped[row['empresa']].append(row)
    for name, group in sorted(grouped.items(), key=lambda item: item[0].lower()):
        entries_total = sum(row['entries'] or 0 for row in group)
        sales_total = sum(row['sales'] or 0 for row in group) if any(row['sales'] is not None for row in group) else None
        estimated_total = sum(row['forecast'].get('estimate') or 0 for row in group) if any(row['forecast'].get('estimate') is not None for row in group) else None
        transactions_total = sum(row['transactions'] or 0 for row in group) if any(row['transactions'] is not None for row in group) else None
        companies.append({'name': name, 'businesses': len(group), 'entries': entries_total, 'sales': sales_total,
                          'estimate': estimated_total, 'transactions': transactions_total,
                          'conversion': round(100 * transactions_total / entries_total, 1) if transactions_total is not None and entries_total and all(row['conversion'] is not None for row in group) else None})
    visible = [row for row in rows if not empresa or row['empresa'] == empresa]
    imports = [dict(zip(('id','name','dataset','rows','created'),r)) for r in con.execute('SELECT * FROM commercial_imports WHERE dataset=? ORDER BY creado DESC LIMIT 20',(dataset,))]
    return {'date':day,'hour':hour,'dataset':dataset,'empresa':empresa,'empresas':companies,'businesses':visible,'imports':imports,'currency':'PEN'}
