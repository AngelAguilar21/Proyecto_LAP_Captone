import sys
import sqlite3
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from identity.spatial_graph import build_graph, persist_graph

class SpatialGraphTests(unittest.TestCase):
    def test_shared_business_does_not_authorize_identity_transition(self):
        config = {'clocksVerified':True,'cameras':[
            {'id':'A','countLines':[{'id':'door','name':'Acceso'}]},
            {'id':'B','analysisZones':[{'id':'z','businessId':'shop'}]}], 'cameraRoutes':[]}
        businesses = [{'id':'shop','nombre':'Tienda','puertas':[{'camaraId':'A','lineaId':'door'}]}]
        graph=build_graph(config,businesses)
        self.assertEqual(len(graph['nodes']),5)
        self.assertFalse(any(e['kind'] in ('overlap','transition') for e in graph['edges']))
        con=sqlite3.connect(':memory:')
        con.execute('PRAGMA foreign_keys=ON')
        persist_graph(con,graph)
        persist_graph(con,graph)
        self.assertEqual(con.execute('SELECT COUNT(*) FROM spatial_nodes').fetchone()[0],5)
        config['cameras'][0]['countLines']=[]
        revised=build_graph(config,businesses)
        self.assertEqual(len(revised['warnings']),1)
        persist_graph(con,revised)
        self.assertEqual(con.execute('SELECT COUNT(*) FROM spatial_nodes').fetchone()[0],4)
        con.close()
