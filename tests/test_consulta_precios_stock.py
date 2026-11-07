import csv
import io
import unittest
from types import SimpleNamespace as Obj
from services.consulta_precios_stock import disponible, filtrar_filas, exportar, importe_visible


class ConsultaTest(unittest.TestCase):
    def fila(self, **cambios):
        return dict(dict(codigo='PPH-3',nombre='Perchero negro',rubro='Hogar',subrubro='Pared',
            marca='Fierro',proveedor='LAF',stock=2,precios={'base':dict(final=12100,neto=10000)}),**cambios)

    def test_stock_distingue_cero_faltantes_y_control_inactivo(self):
        self.assertIsNone(disponible([]))
        self.assertIsNone(disponible([Obj(control_activo=False)]))
        self.assertEqual(disponible([Obj(control_activo=True,stock_actual=5,stock_reservado=3,stock_bloqueado=2)]),0)
        self.assertEqual(disponible([Obj(control_activo=True,stock_actual=5,stock_reservado=1,stock_bloqueado=1)]),3)

    def test_busqueda_combinada_y_sin_mayusculas(self):
        f=self.fila()
        self.assertEqual(filtrar_filas([f],dict(nombre='PERCHERO',proveedor='laf',codigo='PPH')), [f])
        self.assertEqual(filtrar_filas([f],dict(marca='otra')),[])

    def test_stock_sin_no_incluye_desconocido(self):
        desconocido=self.fila(stock=None);cero=self.fila(stock=0)
        self.assertEqual(filtrar_filas([desconocido,cero],dict(stock='sin')),[cero])
        self.assertEqual(filtrar_filas([desconocido,cero],dict(stock='pendiente')),[desconocido])

    def test_sin_precio_no_confunde_precio_cero(self):
        cero=self.fila(precios={'base':dict(final=0,neto=0)})
        pendiente=self.fila(precios={'base':None})
        self.assertEqual(filtrar_filas([cero,pendiente],dict(sin_precio='1')),[pendiente])

    def test_iva_solo_cambia_la_presentacion(self):
        p=dict(final=12100,neto=10000)
        self.assertEqual(importe_visible(p,True),12100)
        self.assertEqual(importe_visible(p,False),10000)
        self.assertEqual(p,dict(final=12100,neto=10000))
        self.assertIsNone(importe_visible(None,True))

    def test_exportacion_respeta_columnas_iva_y_seguridad(self):
        f=self.fila(codigo='=HYPERLINK("x")',nombre='+formula',stock=None)
        columnas=[dict(id='base',nombre='Mayorista')]
        data=exportar([f],columnas,False).getvalue().decode('utf-8-sig')
        rows=list(csv.reader(io.StringIO(data),delimiter=';'))
        self.assertEqual(rows[1],['\'=HYPERLINK("x")',"'+formula",'Sin control','100,00'])
        self.assertEqual(f['codigo'],'=HYPERLINK("x")')

    def test_exportacion_dato_faltante_vacio_no_cero(self):
        f=self.fila(precios={'base':None})
        filas=list(csv.reader(io.StringIO(exportar([f],[dict(id='base',nombre='Mayorista')],True).getvalue().decode('utf-8-sig')),delimiter=';'))
        self.assertEqual(filas[1][-1],'')

if __name__=='__main__': unittest.main()
